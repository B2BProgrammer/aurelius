package com.aurelius.actuary.risk;

import com.aurelius.actuary.planning.Portfolio;
import com.aurelius.actuary.planning.Profiles.Member;
import com.aurelius.actuary.planning.Profiles.Profile;

import java.util.ArrayList;
import java.util.List;

/**
 * Risk score 0-100 = how much investment risk this household should take.
 *
 * LEARN: Two different things, and the LOWER one wins:
 *   WILLINGNESS  how much risk they WANT      (questionnaire answers)
 *   CAPACITY     how much risk they CAN AFFORD (time to retirement, how well funded, income stability)
 * A client who loves risk but retires next year with a thin cushion gets the
 * capacity score, not the willingness score. That's the suitability idea.
 */
public final class RiskScorer {
    private RiskScorer() {}

    public record Band(String name, int min, int max, int suggestedEquityPct) {}

    public static final List<Band> BANDS = List.of(
            new Band("Conservative", 0, 20, 25),
            new Band("Moderately conservative", 21, 40, 40),
            new Band("Moderate", 41, 55, 55),
            new Band("Moderate growth", 56, 70, 65),
            new Band("Growth", 71, 100, 80));

    public record Capacity(int score, int yearsToRetirement, double coverageRatio, int horizonScore,
                           int coverageScore, int incomeScore) {}

    public record Result(int riskScore, String band, int willingness, Capacity capacity, String limitingFactor,
                         int suggestedEquityPct, double currentEquityPct, Double targetEquityPct,
                         String profileOnFile, String alignment, List<String> notes) {}

    public static int willingness(Profile p) {
        double avg = p.questionnaire().all().stream().mapToInt(Integer::intValue).average().orElse(3);
        return (int) Math.round((avg - 1) / 4 * 100);
    }

    /**
     * horizon:  30 + 5 per year until retirement (capped at 100). Retired = 30.
     * coverage: portfolio / (25 x yearly gap between spending and Social Security)
     *           (the "25x" rule of thumb ~ a 4% withdrawal rate); 1.0 = fully covered.
     * income:   questionnaire income-stability answer, 1-5 -> 0-100.
     */
    public static Capacity capacity(Profile p, Portfolio pf) {
        Member primary = p.primary();
        int years = Math.max(0, (primary.retirementAge() == null ? primary.age() : primary.retirementAge()) - primary.age());
        int horizon = Math.min(100, 30 + 5 * years);
        double gap = Math.max(1, p.retirementSpending() - p.socialSecurityTotal());
        double coverage = pf.totalMarketValue() / (25 * gap);
        int coverageScore = (int) Math.round(Math.max(0, Math.min(100, 20 + 50 * coverage)));
        int income = (int) Math.round((p.questionnaire().incomeStability() - 1) / 4.0 * 100);
        int score = (int) Math.round((horizon + coverageScore + income) / 3.0);
        return new Capacity(score, years, Math.round(coverage * 100) / 100.0, horizon, coverageScore, income);
    }

    public static Band band(int score) {
        return BANDS.stream().filter(b -> score >= b.min() && score <= b.max()).findFirst().orElse(BANDS.get(2));
    }

    public static Result score(Profile p, Portfolio pf) {
        int w = willingness(p);
        Capacity c = capacity(p, pf);
        int score = Math.min(w, c.score());
        Band band = band(score);
        double equityNow = Math.round(pf.weight("equity") * 1000) / 10.0;
        Double target = pf.targetAllocationPct().get("equity");

        List<String> notes = new ArrayList<>();
        String alignment;
        if (equityNow > band.suggestedEquityPct() + 10) {
            alignment = "portfolio_riskier_than_profile";
            notes.add(String.format("Portfolio is %.0f%% equity; a %s profile suggests about %d%%.",
                    equityNow, band.name(), band.suggestedEquityPct()));
        } else if (equityNow < band.suggestedEquityPct() - 10) {
            alignment = "portfolio_more_conservative_than_profile";
            notes.add(String.format("Portfolio is %.0f%% equity; a %s profile could hold about %d%%.",
                    equityNow, band.name(), band.suggestedEquityPct()));
        } else {
            alignment = "aligned";
        }
        if (target != null && Math.abs(target - band.suggestedEquityPct()) > 10) {
            notes.add(String.format("The target on file (%.0f%% equity, \"%s\") differs from the computed profile: "
                    + "review the target with the client.", target, pf.riskProfile()));
        }
        if (w > c.score() + 10) {
            notes.add("They are more willing to take risk than they can afford: capacity sets the score.");
        }
        if (pf.largestSingleStock() != null && pf.largestSingleStock().marketValue() / pf.totalMarketValue() > 0.10) {
            notes.add(String.format("%s is %.0f%% of the portfolio: single-stock risk on top of the market risk.",
                    pf.largestSingleStock().symbol(), 100 * pf.largestSingleStock().marketValue() / pf.totalMarketValue()));
        }
        return new Result(score, band.name(), w, c, w <= c.score() ? "willingness" : "capacity",
                band.suggestedEquityPct(), equityNow, target, pf.riskProfile(), alignment, notes);
    }
}
