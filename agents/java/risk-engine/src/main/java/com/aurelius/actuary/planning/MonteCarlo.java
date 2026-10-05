package com.aurelius.actuary.planning;

import com.aurelius.actuary.planning.Profiles.Member;
import com.aurelius.actuary.planning.Profiles.Profile;
import com.aurelius.actuary.planning.Profiles.Withdrawal;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;

/**
 * Monte Carlo retirement projection.
 *
 * LEARN: Instead of assuming "6% every year", we play the future thousands of
 * times with RANDOM yearly returns (normal distribution with the portfolio's
 * mean and volatility) and count how often the money lasts. "82% success" means
 * the money lasted to the end of the plan in 82 of every 100 simulated futures.
 *
 * One simulated year, in today's dollars:
 *     balance = balance x (1 + random return)
 *             + savings                         (before retirement)
 *             - (spending - Social Security)    (after retirement)
 *             - one-time withdrawals            (wedding, college...)
 * If the balance hits zero, that future "failed" at that age.
 *
 * REPRODUCIBLE: the random generator is seeded from the inputs, so the same
 * question always gets the same numbers (an advisor can't "re-roll" until the
 * answer looks better, and an auditor can re-run it).
 */
public final class MonteCarlo {
    private MonteCarlo() {}

    public record Scenario(int retireAge, double annualSpending, double annualSavings, int simulations, int planToAge) {}

    /**
     * Money is in whole dollars (rounded to $1,000): no false precision, no "1.2E7" in JSON.
     * worstCaseAgeMoneyLasts: in 9 of 10 simulated futures the money lasts at least to this age
     * (the primary member's age; the 10th percentile).
     */
    public record Result(int retireAge, long annualSpending, double probabilityOfSuccessPct,
                         long medianAtRetirement, Map<String, Long> balanceAtPlanEnd,
                         int worstCaseAgeMoneyLasts, Map<Integer, Long> medianPathByAge,
                         double expectedReturnPct, double volatilityPct, int simulations, int years, long seed) {}

    public static Result run(Profile profile, Portfolio portfolio, Scenario s, Assumptions a, int startYear, long seed) {
        Member primary = profile.primary();
        List<Member> adults = profile.adults();
        int youngest = adults.stream().mapToInt(Member::age).min().orElse(primary.age());
        int years = Math.max(1, s.planToAge() - youngest);
        double mu = a.expectedReturn(portfolio), sigma = a.volatility(portfolio);

        Map<Integer, Double> oneTime = new LinkedHashMap<>();
        for (Withdrawal w : profile.oneTimeWithdrawals()) oneTime.merge(w.year(), w.amount(), Double::sum);

        SplittableRandom rng = new SplittableRandom(seed);
        double[] atRetirement = new double[s.simulations()];
        double[] atEnd = new double[s.simulations()];
        int[] lastsTo = new int[s.simulations()];
        double[][] path = new double[years + 1][s.simulations()];
        int successes = 0;

        for (int i = 0; i < s.simulations(); i++) {
            double balance = portfolio.totalMarketValue();
            atRetirement[i] = primary.age() >= s.retireAge() ? balance : Double.NaN;
            path[0][i] = balance;
            int depletedAt = -1;
            for (int t = 1; t <= years; t++) {
                int ageNow = primary.age() + t;
                double r = mu + sigma * rng.nextGaussian();
                balance = balance * (1 + r);
                if (ageNow <= s.retireAge()) {
                    balance += s.annualSavings();
                } else {
                    double socialSecurity = 0;
                    for (Member m : adults) socialSecurity += m.socialSecurityAt(m.age() + t);
                    balance -= Math.max(0, s.annualSpending() - socialSecurity);
                }
                balance -= oneTime.getOrDefault(startYear + t, 0.0);
                if (ageNow == s.retireAge()) atRetirement[i] = balance;
                if (balance <= 0) {
                    depletedAt = ageNow;
                    for (int rest = t; rest <= years; rest++) path[rest][i] = 0;
                    break;
                }
                path[t][i] = balance;
            }
            if (depletedAt < 0) successes++;
            atEnd[i] = depletedAt < 0 ? balance : 0;
            lastsTo[i] = depletedAt < 0 ? primary.age() + years : depletedAt;
        }

        Map<String, Long> end = new LinkedHashMap<>();
        double[] sortedEnd = sorted(atEnd);
        end.put("p10", round(percentile(sortedEnd, 10)));
        end.put("p50", round(percentile(sortedEnd, 50)));
        end.put("p90", round(percentile(sortedEnd, 90)));

        Map<Integer, Long> median = new LinkedHashMap<>();
        for (int t = 0; t <= years; t += 5) median.put(primary.age() + t, round(percentile(sorted(path[t]), 50)));

        double[] retirementValues = Arrays.stream(atRetirement).filter(v -> !Double.isNaN(v)).toArray();
        int[] sortedLasts = lastsTo.clone();
        Arrays.sort(sortedLasts);
        return new Result(s.retireAge(), Math.round(s.annualSpending()),
                Math.round(1000.0 * successes / s.simulations()) / 10.0,
                retirementValues.length == 0 ? 0 : round(percentile(sorted(retirementValues), 50)),
                end, sortedLasts[(int) Math.floor(0.10 * (sortedLasts.length - 1))], median,
                Math.round(mu * 10000) / 100.0, Math.round(sigma * 10000) / 100.0, s.simulations(), years, seed);
    }

    /** Same inputs -> same seed -> same numbers. */
    public static long seedFor(String clientId, Scenario s, double portfolioValue) {
        String key = clientId + "|" + s.retireAge() + "|" + s.annualSpending() + "|" + s.annualSavings() + "|"
                + s.simulations() + "|" + s.planToAge() + "|" + Math.round(portfolioValue);
        long h = 1125899906842597L;                                    // simple stable 64-bit string hash
        for (int i = 0; i < key.length(); i++) h = 31 * h + key.charAt(i);
        return h;
    }

    static double percentile(double[] sortedValues, double pct) {
        if (sortedValues.length == 0) return 0;
        double rank = pct / 100.0 * (sortedValues.length - 1);
        int lo = (int) Math.floor(rank), hi = (int) Math.ceil(rank);
        return sortedValues[lo] + (sortedValues[hi] - sortedValues[lo]) * (rank - lo);
    }

    private static double[] sorted(double[] values) {
        double[] copy = values.clone();
        Arrays.sort(copy);
        return copy;
    }

    private static long round(double v) {
        return Math.round(v / 1000.0) * 1000L;                        // nearest $1,000: no false precision
    }

    /** Human sentence comparing scenarios, e.g. "Retiring at 63 instead of 62 raises ... from 78% to 86%." */
    public static List<String> compare(List<Result> results) {
        List<String> out = new ArrayList<>();
        for (int i = 1; i < results.size(); i++) {
            Result a = results.get(i - 1), b = results.get(i);
            String verb = b.probabilityOfSuccessPct() >= a.probabilityOfSuccessPct() ? "raises" : "lowers";
            out.add(String.format("Retiring at %d instead of %d %s the probability of success from %s to %s.",
                    b.retireAge(), a.retireAge(), verb, pctText(a.probabilityOfSuccessPct()), pctText(b.probabilityOfSuccessPct())));
        }
        return out;
    }

    /** "87%", but never "100%" or "0%": a projection must not sound like a certainty. */
    public static String pctText(double pct) {
        if (pct >= 99.5) return "over 99%";
        if (pct < 0.5) return "under 1%";
        return String.format("%.0f%%", pct);
    }
}
