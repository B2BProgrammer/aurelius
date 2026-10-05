package com.aurelius.notary;

import com.aurelius.notary.contract.InvokeContext;
import com.aurelius.notary.kyc.KycService.KycReport;
import com.aurelius.notary.kyc.NotFoundException;
import com.aurelius.notary.skills.SkillRegistry;
import com.aurelius.notary.store.KycStore;
import com.aurelius.notary.support.Json;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** The four skills through the registry: JSON in -> validated record -> service -> output. */
class SkillsTest {

    private TestSupport.Agent agent;
    private SkillRegistry skills;

    @BeforeEach
    void setUp() throws Exception {
        agent = TestSupport.newAgent();
        skills = agent.skills();
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> run(String skill, Map<String, Object> input) {
        Object out = skills.invoke(skill, input, TestSupport.CTX);
        return out instanceof Map<?, ?> m ? (Map<String, Object>) m : agent.mapper().convertValue(out, Map.class);
    }

    @Test
    void everyExampleWorks() {
        skills.all().forEach((name, s) -> s.examples().forEach((label, input) ->
                skills.invoke(name, input, TestSupport.CTX)));
    }

    @Test
    void clientIdCanComeFromTheContext() {
        Object out = skills.invoke("check_kyc", Map.of(), new InvokeContext("t", "u", "chen-002"));
        assertEquals("chen-002", ((KycReport) out).clientId());
    }

    @Test
    void validationErrorsAreReadable() {
        assertEquals("invalid input: client_id is required",
                assertThrows(IllegalArgumentException.class, () -> run("check_kyc", Map.of())).getMessage());
        assertTrue(assertThrows(IllegalArgumentException.class,
                () -> run("check_kyc", Map.of("client_id", "../../etc"))).getMessage().contains("1-64 letters"));
        assertTrue(assertThrows(IllegalArgumentException.class, () -> run("record_document", Map.of(
                "client_id", "patel-001", "member_id", "patel-001-m1", "type", "W9",
                "issued", "2026-01-01", "expires", "2025-01-01"))).getMessage().contains("expires must be after issued"));
        assertEquals("invalid input: type must be one of [GOVERNMENT_ID, PROOF_OF_ADDRESS, W9, BENEFICIARY_DESIGNATION, "
                + "TRUSTED_CONTACT_FORM, OTHER]", assertThrows(IllegalArgumentException.class, () -> run("record_document", Map.of(
                "client_id", "patel-001", "member_id", "patel-001-m1", "type", "passport", "issued", "2026-01-01"))).getMessage());
        assertEquals("invalid input: issued must be a date like 2026-10-03", assertThrows(IllegalArgumentException.class,
                () -> run("record_document", Map.of("client_id", "patel-001", "member_id", "patel-001-m1", "type", "W9",
                        "issued", "2026-13-45"))).getMessage());
        assertTrue(assertThrows(IllegalArgumentException.class, () -> run("screen_name", Map.of(
                "name", "Robert'); DROP TABLE--"))).getMessage().contains("only letters"));
    }

    @Test
    void unknownSkillAndUnknownClient() {
        assertThrows(SkillRegistry.UnknownSkillException.class, () -> run("open_account", Map.of()));
        assertThrows(NotFoundException.class, () -> run("check_kyc", Map.of("client_id", "nobody-1")));
    }

    @Test
    void listDocumentsMasksNumbers() {
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> docs = (List<Map<String, Object>>) run("list_documents",
                Map.of("client_id", "patel-001", "member_id", "patel-001-m1")).get("documents");
        Map<String, Object> license = docs.get(0);
        assertEquals("****4417", license.get("number"));
        assertEquals("expiring", license.get("state"));
        assertTrue(docs.stream().allMatch(d -> "Raj Patel".equals(d.get("member"))));
    }

    @Test
    void recordingTheRenewedLicenseFixesPatel() {
        Map<String, Object> input = Map.of("client_id", "patel-001", "member_id", "patel-001-m1",
                "type", "government_id", "label", "Driver's license (renewed)", "number", "D123-4567-8901",
                "issued", "2026-10-01", "expires", "2034-10-01");
        Map<String, Object> first = run("record_document", input);
        assertEquals(false, first.get("duplicate"));
        assertEquals("complete", first.get("kyc_status_now"));

        // Same trace + same content = a retry: no second document
        Map<String, Object> retry = run("record_document", input);
        assertEquals(true, retry.get("duplicate"));
        assertEquals(first.get("doc_id"), retry.get("doc_id"));
        long licenses = agent.store().get("patel-001").orElseThrow().documents().stream()
                .filter(d -> d.label().contains("renewed")).count();
        assertEquals(1, licenses);
    }

    @Test
    void fullDocumentNumberIsNeverStored() throws Exception {
        run("record_document", Map.of("client_id", "garcia-003", "member_id", "garcia-003-m2", "type", "GOVERNMENT_ID",
                "number", "MX-99887766", "issued", "2025-05-01", "expires", "2035-05-01"));
        String file = Files.readString(agent.dir().resolve("kyc.json"));
        assertFalse(file.contains("99887766"));
        assertTrue(file.contains("\"number_last4\" : \"7766\""));
    }

    @Test
    void screeningLuisWithHisFileClearsTheAmlBlocker() {
        Map<String, Object> out = run("screen_name",
                Map.of("name", "Luis Garcia", "client_id", "garcia-003", "member_id", "garcia-003-m2"));
        assertEquals("clear", out.get("result"));
        assertEquals(true, out.get("used_dob"));                  // DOB taken from his KYC file
        assertEquals("garcia-003-m2", out.get("recorded_on"));
        List<String> rules = agent.service().checkKyc("garcia-003").issues().stream().map(i -> i.rule()).toList();
        assertFalse(rules.contains("AML_NOT_SCREENED"));
        assertTrue(rules.contains("KYC_ID_MISSING"));
    }

    @Test
    void adHocScreeningIsNotRecorded() {
        Map<String, Object> out = run("screen_name", Map.of("name", "Victor Morozenko"));
        assertEquals("potential_match", out.get("result"));
        assertNull(out.get("recorded_on"));
    }

    @Test
    void auditLogHasFingerprintsNotNames() throws Exception {
        run("screen_name", Map.of("name", "Victor Morozenko"));
        String log = Files.readString(agent.audit().file());
        assertTrue(log.contains("\"name_sha256\""));
        assertFalse(log.toLowerCase().contains("morozenko"));
    }

    @Test
    void dataSurvivesARestart() throws Exception {
        run("record_document", Map.of("client_id", "chen-002", "member_id", "chen-002-m1", "type", "PROOF_OF_ADDRESS",
                "label", "Utility bill", "issued", "2026-09-15", "idempotency_key", "chen-address-2026"));
        KycStore reopened = new KycStore(agent.dir().resolve("kyc.json"), Path.of("does-not-matter.json"),
                Json.newFileMapper());
        assertTrue(reopened.get("chen-002").orElseThrow().documents().stream().anyMatch(d -> "Utility bill".equals(d.label())));
        assertFalse(Files.exists(agent.dir().resolve("kyc.json.tmp")), "temp file was renamed away");
    }
}
