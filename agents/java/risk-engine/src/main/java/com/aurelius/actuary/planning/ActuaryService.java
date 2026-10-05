package com.aurelius.actuary.planning;

import com.aurelius.actuary.contract.InvokeContext;
import com.aurelius.actuary.mcp.PortfolioSource;
import com.aurelius.actuary.planning.Profiles.Member;
import com.aurelius.actuary.planning.Profiles.Profile;
import com.aurelius.actuary.risk.RiskScorer;
import com.aurelius.actuary.risk.StressTester;
import com.aurelius.actuary.skills.SkillInputs.ProjectRetirementInput;
import com.aurelius.actuary.skills.SkillInputs.StressTestInput;
import com.aurelius.actuary.support.NotFoundException;

import java.text.NumberFormat;
import java.time.Clock;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * The Actuary's use cases. Plain Java (no Spring), so tests build it with `new`.
 *
 * LEARN: the LLM agents (Conductor, Analyst) EXPLAIN numbers; this agent
 * COMPUTES them. Every answer carries its inputs, assumptions and a disclosure,
 * so the explanation can never drift from the math.
 */
public class ActuaryService {

    public record Settings(int defaultSimulations, int maxSimulations) {
        public static final Settings DEFAULT = new Settings(5000, 20000);
    }

    public static final String DISCLOSURE = "Hypothetical illustration based on assumed returns, in today's dollars. "
            + "Not a guarantee of future results. Review with the client before acting.";

    private static final NumberFormat USD = NumberFormat.getCurrencyInstance(Locale.US);
    static {
        USD.setMaximumFractionDigits(0);
    }

    private final Profiles profiles;
    private final PortfolioSource portfolios;
    private final Assumptions assumptions;
    private final Clock clock;
    private final Settings settings;

    public ActuaryService(Profiles profiles, PortfolioSource portfolios, Assumptions assumptions, Clock clock,
                          Settings settings) {
        this.profiles = profiles;
        this.portfolios = portfolios;
        this.assumptions = assumptions;
        this.clock = clock;
        this.settings = settings;
    }

    // ------------------------------------------------------------------ risk_score
    public Map<String, Object> riskScore(String clientId, InvokeContext ctx) {
        Profile p = profile(clientId);
        Portfolio pf = portfolios.get(clientId, ctx.traceId());
        RiskScorer.Result r = RiskScorer.score(p, pf);

        Map<String, Object> out = header(clientId, p, pf);
        out.put("risk_score", r.riskScore());
        out.put("band", r.band());
        out.put("headline", "Risk score " + r.riskScore() + " (" + r.band() + "), set by "
                + r.limitingFactor() + ". Portfolio: " + r.alignment().replace('_', ' ') + ".");
        out.put("willingness", r.willingness());
        out.put("capacity", r.capacity());
        out.put("limiting_factor", r.limitingFactor());
        out.put("suggested_equity_pct", r.suggestedEquityPct());
        out.put("current_equity_pct", r.currentEquityPct());
        out.put("target_equity_pct_on_file", r.targetEquityPct());
        out.put("risk_profile_on_file", r.profileOnFile());
        out.put("alignment", r.alignment());
        out.put("notes", r.notes());
        out.put("bands", RiskScorer.BANDS);
        return out;
    }

    // ------------------------------------------------------------------ project_retirement
    public Map<String, Object> projectRetirement(ProjectRetirementInput in, InvokeContext ctx) {
        Profile p = profile(in.clientId());
        Member primary = p.primary();
        boolean retired = primary.retirementAge() == null || primary.retirementAge() <= primary.age();

        List<Integer> ages = in.retireAges();
        if (retired && !ages.isEmpty()) {
            throw new IllegalArgumentException(primary.name() + " is already retired (age " + primary.age()
                    + "): leave retire_ages out, or change annual_spending instead");
        }
        if (ages.isEmpty()) ages = List.of(retired ? primary.age() : primary.retirementAge());
        for (int a : ages) {
            if (!retired && a <= primary.age()) {
                throw new IllegalArgumentException("retire_ages must be after " + primary.name() + "'s current age ("
                        + primary.age() + ")");
            }
        }
        int sims = in.simulations() != null ? in.simulations() : settings.defaultSimulations();
        if (sims > settings.maxSimulations()) {
            throw new IllegalArgumentException("simulations must be at most " + settings.maxSimulations());
        }
        double spending = in.annualSpending() != null ? in.annualSpending() : p.retirementSpending();
        double savings = p.annualSavings() + (in.extraAnnualSavings() != null ? in.extraAnnualSavings() : 0);
        int planTo = in.planToAge() != null ? in.planToAge() : p.planToAge();

        Portfolio pf = portfolios.get(in.clientId(), ctx.traceId());
        int startYear = LocalDate.now(clock).getYear();
        List<MonteCarlo.Result> results = new ArrayList<>();
        for (int age : ages) {
            MonteCarlo.Scenario s = new MonteCarlo.Scenario(age, spending, savings, sims, planTo);
            results.add(MonteCarlo.run(p, pf, s, assumptions, startYear,
                    MonteCarlo.seedFor(in.clientId(), s, pf.totalMarketValue())));
        }

        Map<String, Object> out = header(in.clientId(), p, pf);
        MonteCarlo.Result first = results.get(0);
        String headline = retired
                ? String.format("Already retired: %s probability the money lasts to age %d, spending %s/yr.",
                        MonteCarlo.pctText(first.probabilityOfSuccessPct()), planTo, USD.format(spending))
                : String.format("Retire at %d: %s probability of success, spending %s/yr.",
                        first.retireAge(), MonteCarlo.pctText(first.probabilityOfSuccessPct()), USD.format(spending));
        List<String> comparison = retired ? List.of() : MonteCarlo.compare(results);
        if (!comparison.isEmpty()) headline += " " + String.join(" ", comparison);
        out.put("headline", headline);
        out.put("already_retired", retired);
        out.put("ages_are_of", primary.name());
        out.put("scenarios", results);
        out.put("comparison", comparison);

        Map<String, Object> inputs = new LinkedHashMap<>();
        inputs.put("annual_spending", Math.round(spending));
        inputs.put("annual_savings_until_retirement", Math.round(savings));
        inputs.put("social_security", p.adults().stream().map(m -> Map.of("name", m.name(),
                "annual", m.socialSecurityAnnual() == null ? 0 : m.socialSecurityAnnual(),
                "from_age", m.socialSecurityAge() == null ? 0 : m.socialSecurityAge())).toList());
        inputs.put("one_time_withdrawals", p.oneTimeWithdrawals());
        inputs.put("plan_to_age", planTo);
        inputs.put("simulations", sims);
        out.put("inputs", inputs);
        out.put("assumptions", assumptions);
        out.put("disclosure", DISCLOSURE);
        return out;
    }

    // ------------------------------------------------------------------ stress_test
    public Map<String, Object> stressTest(StressTestInput in, InvokeContext ctx) {
        if (in.scenario() != null && !StressTester.ids().contains(in.scenario())) {
            throw new IllegalArgumentException("scenario must be one of " + StressTester.ids());
        }
        Profile p = profile(in.clientId());
        Portfolio pf = portfolios.get(in.clientId(), ctx.traceId());
        if (StressTester.SINGLE_STOCK.equals(in.scenario()) && pf.largestSingleStock() == null) {
            throw new IllegalArgumentException(p.household() + " holds no single stock");
        }
        List<StressTester.Row> rows = StressTester.run(pf, p.retirementSpending(), in.scenario());
        StressTester.Row worst = rows.get(0);

        Map<String, Object> out = header(in.clientId(), p, pf);
        out.put("headline", String.format("Worst case: %s would cost about %s (%.1f%%), about %.1f years of retirement spending.",
                worst.name(), USD.format(worst.loss()), worst.lossPct(), worst.yearsOfSpending()));
        out.put("scenarios", rows);
        out.put("allocation_pct", Map.of("equity", pct(pf.weight("equity")), "fixed_income", pct(pf.weight("fixed_income")),
                "cash", pct(pf.weight("cash"))));
        out.put("disclosure", "Approximate historical index moves applied to today's mix. Illustrative only; "
                + "a real portfolio would not move exactly like the indexes.");
        return out;
    }

    // ------------------------------------------------------------------ browse
    public List<Map<String, Object>> clients() {
        return profiles.clientIds().stream().map(id -> {
            Profile p = profiles.get(id).orElseThrow();
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("client_id", id);
            row.put("household", p.household());
            row.put("primary", p.primary().name());
            row.put("age", p.primary().age());
            row.put("planned_retirement_age", p.primary().retirementAge());
            row.put("retirement_spending", Math.round(p.retirementSpending()));
            return row;
        }).toList();
    }

    public Assumptions assumptions() {
        return assumptions;
    }

    public int clientCount() {
        return profiles.clientIds().size();
    }

    private Map<String, Object> header(String clientId, Profile p, Portfolio pf) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("client_id", clientId);
        out.put("household", p.household());
        out.put("portfolio_value", Math.round(pf.totalMarketValue()));
        out.put("portfolio_source", pf.source());
        out.put("as_of", pf.asOf());
        return out;
    }

    private Profile profile(String clientId) {
        return profiles.get(clientId).orElseThrow(() -> new NotFoundException("No planning profile for client '" + clientId + "'"));
    }

    private static double pct(double w) {
        return Math.round(w * 1000) / 10.0;
    }
}
