package com.aurelius.notary;

import com.aurelius.notary.kyc.KycRules;
import com.aurelius.notary.kyc.KycRules.Issue;
import com.aurelius.notary.kyc.KycRules.Severity;
import com.aurelius.notary.kyc.KycService.KycReport;
import com.aurelius.notary.kyc.Model.Account;
import com.aurelius.notary.kyc.Model.ClientFile;
import com.aurelius.notary.kyc.Model.DocType;
import com.aurelius.notary.kyc.Model.Document;
import com.aurelius.notary.kyc.Model.Member;
import com.aurelius.notary.kyc.Model.Screening;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** The rule book, on the seed data and on hand-made client files. */
class KycRulesTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 10, 3);
    private TestSupport.Agent agent;

    @BeforeEach
    void setUp() throws Exception {
        agent = TestSupport.newAgent();
    }

    private static List<String> rules(List<Issue> issues) {
        return issues.stream().map(Issue::rule).toList();
    }

    @Test
    void patelNeedsOneActionTheExpiringLicense() {
        KycReport r = agent.service().checkKyc("patel-001");
        assertEquals("action_needed", r.status());
        assertEquals(Long.valueOf(1), r.counts().get("action"));
        assertEquals("KYC_ID_EXPIRING", r.issues().get(0).rule());
        assertTrue(r.headline().contains("Raj Patel's driver's license expires on 2026-11-15 (in 43 days)"), r.headline());
        assertTrue(rules(r.issues()).contains("KYC_BENEFICIARY_REVIEW"), "2009 beneficiary form -> review suggested");
    }

    @Test
    void chenIsOver65WithoutTrustedContactsAndStalePaperwork() {
        List<String> found = rules(agent.service().checkKyc("chen-002").issues());
        assertEquals(2, found.stream().filter("KYC_TRUSTED_CONTACT_MISSING"::equals).count());
        assertTrue(found.containsAll(List.of("AML_SCREENING_STALE", "KYC_ADDRESS_STALE", "KYC_RISK_PROFILE_STALE")));
    }

    @Test
    void garciaIsBlockedByLuisButNotByTheMinor() {
        KycReport r = agent.service().checkKyc("garcia-003");
        assertEquals("blocked", r.status());
        assertEquals(List.of("KYC_ID_MISSING", "AML_NOT_SCREENED"),
                r.issues().stream().filter(i -> i.severity() == Severity.BLOCKER).map(Issue::rule).toList());
        assertTrue(r.issues().stream().noneMatch(i -> "Diego Garcia".equals(i.member())), "17-year-old has no own KYC");
        assertTrue(rules(r.issues()).containsAll(List.of("KYC_SOURCE_OF_FUNDS_MISSING", "KYC_BENEFICIARY_MISSING")));
    }

    @Test
    void blockersAreListedFirst() {
        List<Issue> issues = agent.service().checkKyc("garcia-003").issues();
        for (int i = 1; i < issues.size(); i++) {
            assertTrue(issues.get(i - 1).severity().compareTo(issues.get(i).severity()) <= 0);
        }
    }

    private static ClientFile cleanFile(LocalDate idExpires) {
        Member m = new Member("x-m1", "Sam Doe", "primary", LocalDate.of(1980, 1, 1), "US", true,
                new Screening(LocalDate.of(2026, 9, 1), "clear"));
        return new ClientFile("Doe household", "Salary", LocalDate.of(2026, 5, 1), List.of(m),
                List.of(new Account("X-IRA", "IRA", "x-m1")),
                List.of(new Document("D-1", "x-m1", DocType.GOVERNMENT_ID, "Passport", "1234",
                                LocalDate.of(2020, 1, 1), idExpires, null, true, null),
                        new Document("D-2", "x-m1", DocType.PROOF_OF_ADDRESS, "Bill", null,
                                LocalDate.of(2026, 1, 1), null, null, true, null),
                        new Document("D-3", "x-m1", DocType.W9, "W-9", null, LocalDate.of(2026, 1, 1), null, null, true, null),
                        new Document("D-4", "x-m1", DocType.BENEFICIARY_DESIGNATION, "Bene", null,
                                LocalDate.of(2025, 1, 1), null, "X-IRA", true, null)));
    }

    @Test
    void aCompleteFileHasNoIssues() {
        assertTrue(KycRules.evaluate(cleanFile(LocalDate.of(2030, 1, 1)), TODAY, KycRules.Settings.DEFAULT).isEmpty());
    }

    @Test
    void expiredVersusExpiringVersusWindow() {
        assertEquals(List.of("KYC_ID_EXPIRED"),
                rules(KycRules.evaluate(cleanFile(LocalDate.of(2026, 10, 2)), TODAY, KycRules.Settings.DEFAULT)));
        assertEquals(List.of("KYC_ID_EXPIRING"),
                rules(KycRules.evaluate(cleanFile(LocalDate.of(2026, 12, 2)), TODAY, KycRules.Settings.DEFAULT)));
        assertTrue(KycRules.evaluate(cleanFile(LocalDate.of(2026, 12, 2)), TODAY, new KycRules.Settings(30)).isEmpty(),
                "60 days out is fine with a 30-day window");
    }

    @Test
    void unverifiedDocumentsDoNotCount() {
        ClientFile f = cleanFile(LocalDate.of(2030, 1, 1));
        List<Document> docs = f.documents().stream()
                .map(d -> d.type() == DocType.GOVERNMENT_ID
                        ? new Document(d.docId(), d.memberId(), d.type(), d.label(), d.numberLast4(), d.issued(), d.expires(),
                                d.accountId(), false, d.recorded())
                        : d).toList();
        ClientFile unverified = new ClientFile(f.household(), f.sourceOfFunds(), f.riskQuestionnaireDate(), f.members(),
                f.accounts(), docs);
        assertEquals(List.of("KYC_ID_MISSING"), rules(KycRules.evaluate(unverified, TODAY, KycRules.Settings.DEFAULT)));
    }

    @Test
    void openPotentialMatchBlocks() {
        ClientFile f = cleanFile(LocalDate.of(2030, 1, 1));
        ClientFile flagged = f.withMember(f.members().get(0).withScreening(new Screening(TODAY, "potential_match")));
        assertEquals(List.of("AML_POTENTIAL_MATCH"), rules(KycRules.evaluate(flagged, TODAY, KycRules.Settings.DEFAULT)));
    }

    @Test
    void everyRuleIsDocumented() {
        assertEquals(14, KycRules.RULES.size());
        assertFalse(KycRules.RULES.stream().anyMatch(r -> r.description().isBlank()));
    }
}
