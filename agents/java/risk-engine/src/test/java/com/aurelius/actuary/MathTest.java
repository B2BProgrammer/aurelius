package com.aurelius.actuary;

import com.aurelius.actuary.planning.Assumptions;
import com.aurelius.actuary.planning.MonteCarlo;
import com.aurelius.actuary.planning.MonteCarlo.Result;
import com.aurelius.actuary.planning.MonteCarlo.Scenario;
import com.aurelius.actuary.planning.Portfolio;
import com.aurelius.actuary.planning.Profiles.Member;
import com.aurelius.actuary.planning.Profiles.Profile;
import com.aurelius.actuary.planning.Profiles.Questionnaire;
import com.aurelius.actuary.risk.RiskScorer;
import com.aurelius.actuary.risk.StressTester;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** The three engines: Monte Carlo, risk score, stress test. */
class MathTest {

    private TestSupport.Agent agent;
    private Profile patel;
    private Portfolio patelPf;

    @BeforeEach
    void setUp() throws Exception {
        agent = TestSupport.newAgent();
        patel = agent.profiles().get("patel-001").orElseThrow();
        patelPf = agent.snapshot().get("patel-001");
    }

    private Result run(Profile p, Portfolio pf, int retireAge, double spending) {
        Scenario s = new Scenario(retireAge, spending, p.annualSavings(), 2000, p.planToAge());
        return MonteCarlo.run(p, pf, s, Assumptions.DEFAULT, 2026, MonteCarlo.seedFor("x", s, pf.totalMarketValue()));
    }

    // ------------------------------------------------------------ Monte Carlo
    @Test
    void sameInputsSameNumbers() {
        assertEquals(run(patel, patelPf, 62, 140000), run(patel, patelPf, 62, 140000));
    }

    @Test
    void laterRetirementAndLowerSpendingHelp() {
        double at62 = run(patel, patelPf, 62, 140000).probabilityOfSuccessPct();
        double at63 = run(patel, patelPf, 63, 140000).probabilityOfSuccessPct();
        double spendLess = run(patel, patelPf, 62, 120000).probabilityOfSuccessPct();
        assertTrue(at63 > at62, at62 + " -> " + at63);
        assertTrue(spendLess > at62, at62 + " -> " + spendLess);
        assertTrue(at62 > 70 && at62 < 97, "plausible: " + at62);
    }

    @Test
    void withNoVolatilityTheResultIsCertain() {
        Assumptions flat = new Assumptions(0.03, 0, 0.03, 0, 0.03, 0, 0);
        Scenario s = new Scenario(62, 140000, 60000, 200, 95);
        assertEquals(100.0, MonteCarlo.run(patel, patelPf, s, flat, 2026, 1).probabilityOfSuccessPct());
        Scenario impossible = new Scenario(62, 900000, 0, 200, 95);
        Result r = MonteCarlo.run(patel, patelPf, impossible, flat, 2026, 1);
        assertEquals(0.0, r.probabilityOfSuccessPct());
        assertTrue(r.worstCaseAgeMoneyLasts() < 70, "runs out within a few years: " + r.worstCaseAgeMoneyLasts());
    }

    @Test
    void oneYearByHandMatchesTheCode() {
        // 1 year, flat 5% return, still working: 1,000,000 x 1.05 + 10,000 savings = 1,060,000
        Member m = new Member("Solo", "primary", 94, 99, 0.0, 99);
        Profile solo = new Profile("Solo", List.of(m), 10000, 50000, 95, List.of(), new Questionnaire(3, 3, 3, 3, 3));
        Portfolio pf = new Portfolio("test", null, null, Map.of(), 1_000_000, Map.of("equity", 1_000_000.0), null);
        Assumptions flat = new Assumptions(0.05, 0, 0, 0, 0, 0, 0);
        Result r = MonteCarlo.run(solo, pf, new Scenario(99, 50000, 10000, 100, 95), flat, 2026, 7);
        assertEquals(Long.valueOf(1_060_000), r.balanceAtPlanEnd().get("p50"));
    }

    @Test
    void neverSoundsCertain() {
        assertEquals("over 99%", MonteCarlo.pctText(99.7));
        assertEquals("under 1%", MonteCarlo.pctText(0.2));
        assertEquals("87%", MonteCarlo.pctText(87.4));
    }

    @Test
    void portfolioMath() {
        Assumptions a = Assumptions.DEFAULT;
        assertEquals(3.98, Math.round(a.expectedReturn(patelPf) * 10000) / 100.0);      // 68/28/4 mix
        assertTrue(a.volatility(patelPf) > 0.10 && a.volatility(patelPf) < 0.12);
    }

    // ------------------------------------------------------------ risk score
    @Test
    void riskScoresForTheThreeHouseholds() {
        RiskScorer.Result p = RiskScorer.score(patel, patelPf);
        assertEquals(60, p.riskScore());
        assertEquals("Moderate growth", p.band());
        assertEquals("aligned", p.alignment());

        RiskScorer.Result g = RiskScorer.score(agent.profiles().get("garcia-003").orElseThrow(), agent.snapshot().get("garcia-003"));
        assertEquals("Moderate", g.band());
        assertEquals("portfolio_riskier_than_profile", g.alignment());
        assertTrue(g.notes().stream().anyMatch(n -> n.contains("ABC is 22%")));
        assertTrue(g.notes().stream().anyMatch(n -> n.contains("target on file (80% equity")));

        RiskScorer.Result c = RiskScorer.score(agent.profiles().get("chen-002").orElseThrow(), agent.snapshot().get("chen-002"));
        assertEquals("Moderately conservative", c.band());
        assertEquals("aligned", c.alignment());
    }

    @Test
    void capacityCapsAnEagerInvestor() {
        Member old = new Member("Eager", "primary", 64, 65, 20000.0, 67);
        Profile eager = new Profile("Eager", List.of(old), 0, 90000, 95, List.of(), new Questionnaire(5, 5, 2, 5, 5));
        Portfolio thin = new Portfolio("test", null, null, Map.of(), 400000, Map.of("equity", 400000.0), null);
        RiskScorer.Result r = RiskScorer.score(eager, thin);
        assertEquals(85, r.willingness());                              // loves risk...
        assertEquals("capacity", r.limitingFactor());                   // ...but can't afford much
        assertTrue(r.riskScore() < 50, "score " + r.riskScore());
    }

    @Test
    void everyScoreHasABand() {
        for (int s = 0; s <= 100; s++) assertTrue(RiskScorer.band(s).min() <= s && RiskScorer.band(s).max() >= s);
    }

    // ------------------------------------------------------------ stress test
    @Test
    void stressTestByHand() {
        // 2008 on Patel: equity 1,598,000 x -37% + bonds 658,000 x +5% + cash 94,000 x +2% = -556,280
        StressTester.Row gfc = StressTester.run(patelPf, 140000, "gfc_2008").get(0);
        assertEquals(556000L, gfc.loss());
        assertEquals(23.7, gfc.lossPct());
        assertEquals(Double.valueOf(4.0), gfc.yearsOfSpending());
    }

    @Test
    void singleStockShockOnlyWhenThereIsOne() {
        assertTrue(StressTester.run(patelPf, 140000, null).stream().anyMatch(r -> r.name().startsWith("XYZ falls 50%")));
        assertTrue(StressTester.run(agent.snapshot().get("chen-002"), 78000, null).stream()
                .noneMatch(r -> r.scenario().equals(StressTester.SINGLE_STOCK)));
    }
}
