package com.aurelius.notary.skills;

import com.aurelius.notary.contract.InvokeContext;
import com.aurelius.notary.kyc.KycService;
import com.aurelius.notary.skills.SkillInputs.CheckKycInput;
import com.aurelius.notary.skills.SkillInputs.ListDocumentsInput;
import com.aurelius.notary.skills.SkillInputs.RecordDocumentInput;
import com.aurelius.notary.skills.SkillInputs.ScreenNameInput;
import com.aurelius.notary.support.Checks;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.exc.InvalidFormatException;

import java.time.LocalDate;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.BiFunction;

/**
 * The skills table: name -> description, input type, schema, examples, handler.
 *
 * LEARN: Same idea as skills/index.ts in the TypeScript agents. ONE table feeds
 * POST /invoke, the agent card and the Swagger examples, so docs can't drift
 * from code. Input JSON becomes a validated record via Jackson's convertValue.
 */
public class SkillRegistry {

    public static class UnknownSkillException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public UnknownSkillException(String skill) {
            super("unknown skill " + skill);
        }
    }

    public record Skill<I>(String description, boolean writes, Class<I> inputType, Map<String, Object> inputSchema,
                           Map<String, Map<String, Object>> examples, BiFunction<I, InvokeContext, Object> run) {}

    private final Map<String, Skill<?>> skills = new LinkedHashMap<>();
    private final ObjectMapper mapper;

    public SkillRegistry(KycService service, ObjectMapper mapper) {
        this.mapper = mapper;

        skills.put("check_kyc", new Skill<>(
                "KYC/AML status for a household: blockers, action items and suggestions, each with the fix.",
                false, CheckKycInput.class,
                schema(Map.of("client_id", str("Household id, e.g. patel-001")), List.of("client_id")),
                examples("check_kyc", Map.of("client_id", "patel-001"),
                       "check_kyc (blocked)", Map.of("client_id", "garcia-003"),
                       "check_kyc (65+ clients)", Map.of("client_id", "chen-002")),
                (in, ctx) -> service.checkKyc(in.clientId())));

        skills.put("list_documents", new Skill<>(
                "Documents on file with masked numbers and state (valid / expiring / expired).",
                false, ListDocumentsInput.class,
                schema(Map.of("client_id", str("Household id"), "member_id", str("Optional: one person, e.g. patel-001-m1")),
                       List.of("client_id")),
                examples("list_documents", Map.of("client_id", "patel-001", "member_id", "patel-001-m1")),
                (in, ctx) -> service.listDocuments(in)));

        skills.put("screen_name", new Skill<>(
                "Screen a name against the (demo) AML watchlist with fuzzy matching. With client_id + member_id "
                        + "the result is recorded on that person's KYC file.",
                true, ScreenNameInput.class,
                schema(Map.of("name", str("Full name"), "dob", str("Optional date of birth YYYY-MM-DD (cuts false positives)"),
                              "country", str("Optional 2-letter country code"), "client_id", str("Optional"),
                              "member_id", str("Optional: record the result on this person")),
                       List.of("name")),
                examples("screen_name (potential match)", Map.of("name", "Victor Morozenko"),
                       "screen_name (record for Luis)", Map.of("name", "Luis Garcia", "client_id", "garcia-003",
                                                              "member_id", "garcia-003-m2")),
                (in, ctx) -> service.screenName(in, ctx)));

        skills.put("record_document", new Skill<>(
                "Record a verified document (only the last 4 of its number are kept). Idempotent: the same "
                        + "idempotency_key (or the same trace + content) never creates a second document.",
                true, RecordDocumentInput.class,
                schema(Map.of("client_id", str("Household id"), "member_id", str("Person, e.g. patel-001-m1"),
                              "type", Map.of("type", "string", "enum", List.of("GOVERNMENT_ID", "PROOF_OF_ADDRESS", "W9",
                                      "BENEFICIARY_DESIGNATION", "TRUSTED_CONTACT_FORM", "OTHER")),
                              "label", str("e.g. Driver's license"), "number", str("Document number (only last 4 kept)"),
                              "issued", str("YYYY-MM-DD"), "expires", str("YYYY-MM-DD, optional"),
                              "account_id", str("Required for BENEFICIARY_DESIGNATION"),
                              "idempotency_key", str("Optional; same key = same document")),
                       List.of("client_id", "member_id", "type", "issued")),
                examples("record_document (renewed license)", Map.of(
                        "client_id", "patel-001", "member_id", "patel-001-m1", "type", "GOVERNMENT_ID",
                        "label", "Driver's license (renewed)", "number", "D123-4567-8901",
                        "issued", "2026-10-01", "expires", "2034-10-01", "idempotency_key", "swagger-raj-license-2026")),
                (in, ctx) -> service.recordDocument(in, ctx)));
    }

    /** Validate the input against the skill's record, then run it. */
    public Object invoke(String name, Map<String, Object> input, InvokeContext ctx) {
        Skill<?> skill = skills.get(name);
        if (skill == null) throw new UnknownSkillException(name);
        return run(skill, input, ctx);
    }

    private <I> Object run(Skill<I> skill, Map<String, Object> input, InvokeContext ctx) {
        Map<String, Object> raw = new HashMap<>(input);
        if (!raw.containsKey("client_id") && ctx.clientId() != null && skill.inputType() != ScreenNameInput.class) {
            raw.put("client_id", ctx.clientId());          // the Conductor may put client_id in the context
        }
        I parsed;
        try {
            parsed = mapper.convertValue(raw, skill.inputType());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("invalid input: " + readable(e), e);
        }
        return skill.run().apply(parsed, ctx);
    }

    /** Turn Jackson's errors into messages a caller can act on, without internal class names. */
    private static String readable(Throwable e) {
        for (Throwable t = e; t != null; t = t.getCause()) {
            if (t instanceof InvalidFormatException f && f.getTargetType() != null) {
                String field = f.getPath().isEmpty() ? "value" : f.getPath().get(f.getPath().size() - 1).getFieldName();
                if (f.getTargetType().isEnum()) {
                    return field + " must be one of " + Arrays.toString(f.getTargetType().getEnumConstants());
                }
                if (f.getTargetType() == LocalDate.class) return field + " must be a date like 2026-10-03";
                return field + " has the wrong type";
            }
        }
        return Checks.rootMessage(e);
    }

    public Map<String, Skill<?>> all() {
        return skills;
    }

    /** For the agent card: description, writes flag and JSON schema per skill. */
    public Map<String, Object> describe() {
        Map<String, Object> out = new LinkedHashMap<>();
        skills.forEach((name, s) -> out.put(name, Map.of(
                "description", s.description(), "writes", s.writes(), "input_schema", s.inputSchema())));
        return out;
    }

    /** Ordered on purpose: the first example is the one Swagger shows first. */
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

    private static Map<String, Object> schema(Map<String, Object> properties, List<String> required) {
        return Map.of("type", "object", "properties", new LinkedHashMap<>(properties), "required", required);
    }
}
