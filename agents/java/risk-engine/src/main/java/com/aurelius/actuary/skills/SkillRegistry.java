package com.aurelius.actuary.skills;

import com.aurelius.actuary.contract.InvokeContext;
import com.aurelius.actuary.planning.ActuaryService;
import com.aurelius.actuary.risk.StressTester;
import com.aurelius.actuary.skills.SkillInputs.ProjectRetirementInput;
import com.aurelius.actuary.skills.SkillInputs.RiskScoreInput;
import com.aurelius.actuary.skills.SkillInputs.StressTestInput;
import com.aurelius.actuary.support.Checks;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.exc.MismatchedInputException;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.BiFunction;

/**
 * The skills table: ONE place that feeds POST /invoke, the agent card and the
 * Swagger examples (same pattern as the Notary and the TypeScript agents).
 */
public class SkillRegistry {

    public static class UnknownSkillException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public UnknownSkillException(String skill) {
            super("unknown skill " + skill);
        }
    }

    public record Skill<I>(String description, Class<I> inputType, Map<String, Object> inputSchema,
                           Map<String, Map<String, Object>> examples, BiFunction<I, InvokeContext, Object> run) {}

    private final Map<String, Skill<?>> skills = new LinkedHashMap<>();
    private final ObjectMapper mapper;

    public SkillRegistry(ActuaryService service, ObjectMapper mapper) {
        this.mapper = mapper;

        skills.put("risk_score", new Skill<>(
                "Risk score 0-100 and band: the lower of willingness (questionnaire) and capacity (horizon, "
                        + "funding, income). Compares the portfolio's equity share with the profile.",
                RiskScoreInput.class,
                schema(Map.of("client_id", str("Household id, e.g. patel-001")), List.of("client_id")),
                examples("risk_score", Map.of("client_id", "patel-001"),
                         "risk_score (portfolio too risky)", Map.of("client_id", "garcia-003")),
                (in, ctx) -> service.riskScore(in.clientId(), ctx)));

        skills.put("project_retirement", new Skill<>(
                "Monte Carlo retirement projection (reproducible). Compare up to 3 retirement ages; override "
                        + "spending or add savings to test what-ifs.",
                ProjectRetirementInput.class,
                schema(Map.of(
                        "client_id", str("Household id"),
                        "retire_ages", Map.of("type", "array", "items", Map.of("type", "integer", "minimum", 50, "maximum", 80),
                                "maxItems", 3, "description", "Ages to compare, e.g. [62, 63]. Default: the planned age"),
                        "annual_spending", num("Yearly spending in retirement, today's dollars"),
                        "extra_annual_savings", num("Added to planned savings until retirement"),
                        "simulations", Map.of("type", "integer", "minimum", 100, "description", "Default 5000"),
                        "plan_to_age", Map.of("type", "integer", "minimum", 80, "maximum", 105)),
                       List.of("client_id")),
                examples("project_retirement (62 vs 63)", Map.of("client_id", "patel-001", "retire_ages", List.of(62, 63)),
                         "project_retirement (spend less)", Map.of("client_id", "patel-001", "retire_ages", List.of(62),
                                 "annual_spending", 125000),
                         "project_retirement (already retired)", Map.of("client_id", "chen-002")),
                (in, ctx) -> service.projectRetirement(in, ctx)));

        skills.put("stress_test", new Skill<>(
                "Losses if a historical crisis happened again (2008, 2000-02, 2020, 2022) plus a single-stock shock, "
                        + "in dollars and in years of retirement spending.",
                StressTestInput.class,
                schema(Map.of("client_id", str("Household id"),
                              "scenario", Map.of("type", "string", "enum", StressTester.ids(),
                                      "description", "Optional: run just one")),
                       List.of("client_id")),
                examples("stress_test", Map.of("client_id", "patel-001"),
                         "stress_test (one scenario)", Map.of("client_id", "garcia-003", "scenario", "rates_2022")),
                (in, ctx) -> service.stressTest(in, ctx)));
    }

    public Object invoke(String name, Map<String, Object> input, InvokeContext ctx) {
        Skill<?> skill = skills.get(name);
        if (skill == null) throw new UnknownSkillException(name);
        return run(skill, input, ctx);
    }

    private <I> Object run(Skill<I> skill, Map<String, Object> input, InvokeContext ctx) {
        Map<String, Object> raw = new HashMap<>(input);
        if (!raw.containsKey("client_id") && ctx.clientId() != null) raw.put("client_id", ctx.clientId());
        I parsed;
        try {
            parsed = mapper.convertValue(raw, skill.inputType());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("invalid input: " + readable(e), e);
        }
        return skill.run().apply(parsed, ctx);
    }

    /** Jackson's errors -> "retire_ages has the wrong type", without Java class names. */
    private static String readable(Throwable e) {
        for (Throwable t = e; t != null; t = t.getCause()) {
            if (t instanceof MismatchedInputException m) {
                String field = m.getPath().stream().map(JsonMappingException.Reference::getFieldName)
                        .filter(f -> f != null).reduce((a, b) -> b).orElse("value");
                return field + " has the wrong type";
            }
        }
        return Checks.rootMessage(e);
    }

    public Map<String, Skill<?>> all() {
        return skills;
    }

    public Map<String, Object> describe() {
        Map<String, Object> out = new LinkedHashMap<>();
        skills.forEach((name, s) -> out.put(name, Map.of("description", s.description(), "writes", false,
                "input_schema", s.inputSchema())));
        return out;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Map<String, Object>> examples(Object... labelThenInput) {
        Map<String, Map<String, Object>> out = new LinkedHashMap<>();
        for (int i = 0; i < labelThenInput.length; i += 2) {
            out.put((String) labelThenInput[i], (Map<String, Object>) labelThenInput[i + 1]);
        }
        return out;
    }

    private static Map<String, Object> str(String description) {
        return Map.of("type", "string", "description", description);
    }

    private static Map<String, Object> num(String description) {
        return Map.of("type", "number", "description", description);
    }

    private static Map<String, Object> schema(Map<String, Object> properties, List<String> required) {
        return Map.of("type", "object", "properties", new LinkedHashMap<>(properties), "required", required);
    }
}
