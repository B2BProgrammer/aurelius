package com.aurelius.actuary;

import com.aurelius.actuary.contract.InvokeContext;
import com.aurelius.actuary.planning.MonteCarlo;
import com.aurelius.actuary.skills.SkillRegistry;
import com.aurelius.actuary.support.NotFoundException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** The three skills through the registry: JSON in -> validated record -> service -> output. */
class SkillsTest {

    private SkillRegistry skills;

    @BeforeEach
    void setUp() throws Exception {
        skills = TestSupport.newAgent().skills();
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> run(String skill, Map<String, Object> input) {
        return (Map<String, Object>) skills.invoke(skill, input, TestSupport.CTX);
    }

    private String error(String skill, Map<String, Object> input) {
        return assertThrows(IllegalArgumentException.class, () -> run(skill, input)).getMessage();
    }

    @Test
    void everyExampleWorks() {
        skills.all().forEach((name, s) -> s.examples().forEach((label, input) -> skills.invoke(name, input, TestSupport.CTX)));
    }

    @Test
    void riskScoreOutput() {
        Map<String, Object> r = run("risk_score", Map.of("client_id", "patel-001"));
        assertEquals(60, r.get("risk_score"));
        assertEquals("Moderate growth", r.get("band"));
        assertEquals("snapshot", r.get("portfolio_source"));
        assertTrue(r.get("headline").toString().startsWith("Risk score 60 (Moderate growth)"));
    }

    @Test
    @SuppressWarnings("unchecked")
    void retirement62Versus63() {
        Map<String, Object> r = run("project_retirement", Map.of("client_id", "patel-001", "retire_ages", List.of(62, 63)));
        List<MonteCarlo.Result> scenarios = (List<MonteCarlo.Result>) r.get("scenarios");
        assertEquals(2, scenarios.size());
        assertTrue(scenarios.get(1).probabilityOfSuccessPct() > scenarios.get(0).probabilityOfSuccessPct());
        assertTrue(((List<String>) r.get("comparison")).get(0).startsWith("Retiring at 63 instead of 62 raises"));
        assertTrue(r.get("headline").toString().startsWith("Retire at 62: "));
        assertEquals("Raj Patel", r.get("ages_are_of"));
        assertTrue(r.get("disclosure").toString().contains("Not a guarantee"));
    }

    @Test
    void clientIdFromContextAndDefaultsFromTheProfile() {
        @SuppressWarnings("unchecked")
        Map<String, Object> r = (Map<String, Object>) skills.invoke("project_retirement", Map.of(),
                new InvokeContext("t", "u", "patel-001"));
        assertTrue(r.get("headline").toString().startsWith("Retire at 62"));      // planned age from the profile
    }

    @Test
    void alreadyRetiredHouseholds() {
        Map<String, Object> r = run("project_retirement", Map.of("client_id", "chen-002"));
        assertEquals(true, r.get("already_retired"));
        assertTrue(r.get("headline").toString().startsWith("Already retired: over 99% probability"), r.get("headline").toString());
        assertTrue(error("project_retirement", Map.of("client_id", "chen-002", "retire_ages", List.of(75)))
                .contains("already retired"));
    }

    @Test
    void stressTestOutput() {
        Map<String, Object> r = run("stress_test", Map.of("client_id", "patel-001"));
        assertTrue(r.get("headline").toString().startsWith("Worst case: 2008 global financial crisis would cost about $556,000"));
        Map<String, Object> one = run("stress_test", Map.of("client_id", "garcia-003", "scenario", "rates_2022"));
        assertEquals(1, ((List<?>) one.get("scenarios")).size());
        assertTrue(error("stress_test", Map.of("client_id", "chen-002", "scenario", "single_stock_halved"))
                .contains("holds no single stock"));
    }

    @Test
    void validation() {
        assertEquals("invalid input: client_id is required", error("risk_score", Map.of()));
        assertTrue(error("project_retirement", Map.of("client_id", "patel-001", "retire_ages", List.of(62, 63, 64, 65)))
                .contains("at most 3"));
        assertTrue(error("project_retirement", Map.of("client_id", "patel-001", "retire_ages", List.of(45)))
                .contains("between 50 and 80"));
        assertTrue(error("project_retirement", Map.of("client_id", "patel-001", "retire_ages", List.of(57)))
                .contains("after Raj Patel's current age"));
        assertTrue(error("project_retirement", Map.of("client_id", "patel-001", "simulations", 1_000_000))
                .contains("at most 20000"));
        assertEquals("invalid input: retire_ages has the wrong type",
                error("project_retirement", Map.of("client_id", "patel-001", "retire_ages", List.of("sixty"))));
        assertTrue(error("stress_test", Map.of("client_id", "patel-001", "scenario", "zombies")).contains("must be one of"));
    }

    @Test
    void unknownSkillAndClient() {
        assertThrows(SkillRegistry.UnknownSkillException.class, () -> run("buy_stock", Map.of()));
        assertThrows(NotFoundException.class, () -> run("risk_score", Map.of("client_id", "nobody-1")));
    }
}
