package com.aurelius.actuary.planning;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;

/**
 * Planning profiles: ages, retirement plans, savings, spending, questionnaire answers.
 * (In a real firm this comes from the planning system; here it's data\profiles.json.)
 * All money is in TODAY'S dollars, so inflation is already accounted for.
 */
public final class Profiles {

    public record Member(String name, String role, int age, Integer retirementAge,
                         Double socialSecurityAnnual, Integer socialSecurityAge) {
        public boolean isAdultEarner() {
            return !"dependent".equals(role);
        }

        public double socialSecurityAt(int ageNow) {
            return socialSecurityAnnual != null && socialSecurityAge != null && ageNow >= socialSecurityAge
                    ? socialSecurityAnnual : 0.0;
        }
    }

    public record Withdrawal(int year, double amount, String label) {}

    /** Answers 1-5; higher = more willing / able to take risk (liquidity_need 5 = needs little cash). */
    public record Questionnaire(int lossReaction, int investmentExperience, int incomeStability,
                                int liquidityNeed, int primaryGoal) {
        public List<Integer> all() {
            return List.of(lossReaction, investmentExperience, incomeStability, liquidityNeed, primaryGoal);
        }
    }

    public record Profile(String household, List<Member> members, double annualSavings, double retirementSpending,
                          int planToAge, List<Withdrawal> oneTimeWithdrawals, Questionnaire questionnaire) {
        public Profile {
            members = members == null ? List.of() : List.copyOf(members);
            oneTimeWithdrawals = oneTimeWithdrawals == null ? List.of() : List.copyOf(oneTimeWithdrawals);
        }

        public Member primary() {
            return members.stream().filter(m -> "primary".equals(m.role())).findFirst()
                    .orElseThrow(() -> new IllegalStateException(household + " has no primary member"));
        }

        public List<Member> adults() {
            return members.stream().filter(Member::isAdultEarner).toList();
        }

        /** Plan until the YOUNGEST adult reaches planToAge. */
        public int yearsToPlan() {
            int youngest = adults().stream().mapToInt(Member::age).min().orElse(primary().age());
            return Math.max(1, planToAge - youngest);
        }

        public double socialSecurityTotal() {
            return adults().stream().mapToDouble(m -> m.socialSecurityAnnual() == null ? 0 : m.socialSecurityAnnual()).sum();
        }
    }

    private record Book(Map<String, Profile> clients) {}

    private final Map<String, Profile> clients;

    public Profiles(Map<String, Profile> clients) {
        this.clients = new TreeMap<>(clients);
    }

    public static Profiles load(Path file, ObjectMapper mapper) throws IOException {
        return new Profiles(mapper.readValue(Files.readString(file), Book.class).clients());
    }

    public Optional<Profile> get(String clientId) {
        return Optional.ofNullable(clients.get(clientId));
    }

    public List<String> clientIds() {
        return List.copyOf(clients.keySet());
    }
}
