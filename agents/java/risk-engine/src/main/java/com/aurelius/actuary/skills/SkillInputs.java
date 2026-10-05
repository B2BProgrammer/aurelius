package com.aurelius.actuary.skills;

import com.aurelius.actuary.support.Checks;

import java.util.List;

/** One record per skill input; each validates itself in its compact constructor. */
public final class SkillInputs {
    private SkillInputs() {}

    public record RiskScoreInput(String clientId) {
        public RiskScoreInput {
            clientId = Checks.id("client_id", clientId);
        }
    }

    /**
     * @param retireAges         0-3 ages to compare (default: the planned age)
     * @param annualSpending     override yearly spending in retirement (today's dollars)
     * @param extraAnnualSavings added to the planned yearly savings until retirement
     * @param simulations        how many futures to simulate (limit set in application.yml)
     * @param planToAge          plan until the youngest adult reaches this age
     */
    public record ProjectRetirementInput(String clientId, List<Integer> retireAges, Double annualSpending,
                                         Double extraAnnualSavings, Integer simulations, Integer planToAge) {
        public ProjectRetirementInput {
            clientId = Checks.id("client_id", clientId);
            retireAges = retireAges == null ? List.of() : List.copyOf(retireAges);
            if (retireAges.size() > 3) throw new IllegalArgumentException("retire_ages: at most 3 ages to compare");
            for (Integer a : retireAges) {
                if (a == null || a < 50 || a > 80) throw new IllegalArgumentException("retire_ages must be between 50 and 80");
            }
            if (retireAges.stream().distinct().count() != retireAges.size()) {
                throw new IllegalArgumentException("retire_ages has duplicates");
            }
            if (annualSpending != null && (annualSpending < 10_000 || annualSpending > 2_000_000)) {
                throw new IllegalArgumentException("annual_spending must be between 10,000 and 2,000,000");
            }
            if (extraAnnualSavings != null && (extraAnnualSavings < 0 || extraAnnualSavings > 1_000_000)) {
                throw new IllegalArgumentException("extra_annual_savings must be between 0 and 1,000,000");
            }
            if (simulations != null && simulations < 100) throw new IllegalArgumentException("simulations must be at least 100");
            if (planToAge != null && (planToAge < 80 || planToAge > 105)) {
                throw new IllegalArgumentException("plan_to_age must be between 80 and 105");
            }
        }
    }

    public record StressTestInput(String clientId, String scenario) {
        public StressTestInput {
            clientId = Checks.id("client_id", clientId);
            if (scenario != null) scenario = Checks.id("scenario", scenario);
        }
    }
}
