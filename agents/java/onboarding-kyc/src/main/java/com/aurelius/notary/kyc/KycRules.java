package com.aurelius.notary.kyc;

import com.aurelius.notary.kyc.Model.Account;
import com.aurelius.notary.kyc.Model.ClientFile;
import com.aurelius.notary.kyc.Model.DocType;
import com.aurelius.notary.kyc.Model.Document;
import com.aurelius.notary.kyc.Model.Member;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * The KYC/AML rule book. Pure functions: (client file, today) -> issues.
 *
 * LEARN: Why no LLM here? "Is this client allowed to trade?" is a regulatory
 * decision. It must be the SAME answer every time, explainable rule by rule,
 * and testable. So it's plain code. (The LLM agents explain and write; the
 * rules decide.)
 *
 * Severity:
 *   BLOCKER  account can't be opened or traded until fixed
 *   ACTION   fix soon (expiring, stale, missing paperwork)
 *   INFO     good practice
 */
public final class KycRules {
    private KycRules() {}

    public enum Severity { BLOCKER, ACTION, INFO }

    public record Issue(String rule, Severity severity, String member, String message, String fix) {}

    public record RuleInfo(String id, Severity severity, String description) {}

    public record Settings(int expiringWindowDays) {
        public static final Settings DEFAULT = new Settings(60);
    }

    public static final List<RuleInfo> RULES = List.of(
            new RuleInfo("KYC_ID_MISSING", Severity.BLOCKER, "Adult without a verified government ID"),
            new RuleInfo("KYC_ID_EXPIRED", Severity.BLOCKER, "Government ID has expired"),
            new RuleInfo("AML_NOT_SCREENED", Severity.BLOCKER, "Adult never screened against the watchlist"),
            new RuleInfo("AML_POTENTIAL_MATCH", Severity.BLOCKER, "Open potential watchlist match: compliance review needed"),
            new RuleInfo("KYC_ID_EXPIRING", Severity.ACTION, "Government ID expires within the window (default 60 days)"),
            new RuleInfo("AML_SCREENING_STALE", Severity.ACTION, "Last screening older than 365 days"),
            new RuleInfo("KYC_ADDRESS_STALE", Severity.ACTION, "Proof of address missing or older than 3 years"),
            new RuleInfo("KYC_W9_MISSING", Severity.ACTION, "Primary account holder has no W-9 tax certification"),
            new RuleInfo("KYC_RISK_PROFILE_STALE", Severity.ACTION, "Risk questionnaire missing or older than 1 year (suitability)"),
            new RuleInfo("KYC_SOURCE_OF_FUNDS_MISSING", Severity.ACTION, "Source of funds not documented (AML)"),
            new RuleInfo("KYC_TRUSTED_CONTACT_MISSING", Severity.ACTION, "Client 65+ without a trusted contact (FINRA Rule 4512)"),
            new RuleInfo("KYC_BENEFICIARY_MISSING", Severity.ACTION, "Retirement account without a beneficiary designation"),
            new RuleInfo("KYC_TRUSTED_CONTACT_SUGGESTED", Severity.INFO, "Adult under 65 without a trusted contact"),
            new RuleInfo("KYC_BENEFICIARY_REVIEW", Severity.INFO, "Beneficiary designation older than 10 years"));

    public static List<Issue> evaluate(ClientFile c, LocalDate today, Settings s) {
        List<Issue> out = new ArrayList<>();

        for (Member m : c.members()) {
            if (!m.isAdultOn(today)) continue;           // minors: no ID or screening of their own
            checkId(c, m, today, s, out);
            checkScreening(m, today, out);
            if (!m.trustedContact()) {
                if (m.ageOn(today) >= 65) {
                    out.add(new Issue("KYC_TRUSTED_CONTACT_MISSING", Severity.ACTION, m.name(),
                            m.name() + " is " + m.ageOn(today) + " and has no trusted contact on file.",
                            "Ask " + first(m) + " to name a trusted contact (FINRA Rule 4512)."));
                } else {
                    out.add(new Issue("KYC_TRUSTED_CONTACT_SUGGESTED", Severity.INFO, m.name(),
                            m.name() + " has no trusted contact on file.",
                            "Offer the trusted contact form at the next meeting."));
                }
            }
        }

        // Household-level paperwork
        Member primary = c.members().stream().filter(m -> "primary".equals(m.role())).findFirst().orElse(null);
        List<Document> address = c.docsOf(null, DocType.PROOF_OF_ADDRESS);
        LocalDate latestAddress = address.stream().map(Document::issued).max(Comparator.naturalOrder()).orElse(null);
        if (latestAddress == null || latestAddress.isBefore(today.minusYears(3))) {
            out.add(new Issue("KYC_ADDRESS_STALE", Severity.ACTION, null,
                    latestAddress == null ? "No proof of address on file."
                            : "Proof of address is from " + latestAddress + " (older than 3 years).",
                    "Request a recent utility bill, bank or tax statement."));
        }
        if (primary != null && c.docsOf(primary.memberId(), DocType.W9).isEmpty()) {
            out.add(new Issue("KYC_W9_MISSING", Severity.ACTION, primary.name(),
                    "No W-9 on file for " + primary.name() + ".", "Collect a signed Form W-9."));
        }
        LocalDate rq = c.riskQuestionnaireDate();
        if (rq == null || rq.isBefore(today.minusYears(1))) {
            out.add(new Issue("KYC_RISK_PROFILE_STALE", Severity.ACTION, null,
                    rq == null ? "No risk questionnaire on file."
                            : "Risk questionnaire is from " + rq + " (older than 1 year).",
                    "Re-run the risk questionnaire at the next review."));
        }
        if (c.sourceOfFunds() == null || c.sourceOfFunds().isBlank()) {
            out.add(new Issue("KYC_SOURCE_OF_FUNDS_MISSING", Severity.ACTION, null,
                    "Source of funds is not documented.", "Ask how the invested money was earned and record it."));
        }

        // Retirement accounts
        for (Account a : c.accounts()) {
            if (!a.needsBeneficiary()) continue;
            Member owner = c.member(a.owner());
            String ownerName = owner == null ? null : owner.name();
            LocalDate latest = c.documents().stream()
                    .filter(d -> d.type() == DocType.BENEFICIARY_DESIGNATION && d.verified() && a.accountId().equals(d.accountId()))
                    .map(Document::issued).max(Comparator.naturalOrder()).orElse(null);
            if (latest == null) {
                out.add(new Issue("KYC_BENEFICIARY_MISSING", Severity.ACTION, ownerName,
                        a.type() + " " + a.accountId() + " has no beneficiary designation.",
                        "Collect a beneficiary designation form for " + a.accountId() + "."));
            } else if (latest.isBefore(today.minusYears(10))) {
                out.add(new Issue("KYC_BENEFICIARY_REVIEW", Severity.INFO, ownerName,
                        "Beneficiary designation for " + a.accountId() + " is from " + latest + ".",
                        "Review beneficiaries; life events may have changed them."));
            }
        }

        out.sort(Comparator.comparing(Issue::severity));     // BLOCKER first
        return out;
    }

    private static void checkId(ClientFile c, Member m, LocalDate today, Settings s, List<Issue> out) {
        // The ID that is valid the LONGEST counts (a renewed license replaces the old one).
        Document best = c.docsOf(m.memberId(), DocType.GOVERNMENT_ID).stream()
                .max(Comparator.comparing(d -> d.expires() == null ? LocalDate.MAX : d.expires()))
                .orElse(null);
        if (best == null) {
            out.add(new Issue("KYC_ID_MISSING", Severity.BLOCKER, m.name(),
                    m.name() + " has no verified government ID.",
                    "Collect and verify a passport or driver's license for " + first(m) + "."));
            return;
        }
        if (best.expires() == null) return;
        long days = ChronoUnit.DAYS.between(today, best.expires());
        String label = best.label() == null ? "government ID" : best.label().toLowerCase();
        if (days < 0) {
            out.add(new Issue("KYC_ID_EXPIRED", Severity.BLOCKER, m.name(),
                    m.name() + "'s " + label + " expired on " + best.expires() + ".",
                    "Ask " + first(m) + " for the renewed ID, then record it (record_document)."));
        } else if (days <= s.expiringWindowDays()) {
            out.add(new Issue("KYC_ID_EXPIRING", Severity.ACTION, m.name(),
                    m.name() + "'s " + label + " expires on " + best.expires() + " (in " + days + " days).",
                    "Ask " + first(m) + " for the renewed ID, then record it (record_document)."));
        }
    }

    private static void checkScreening(Member m, LocalDate today, List<Issue> out) {
        Model.Screening sc = m.screening();
        if (sc == null || sc.lastScreened() == null) {
            out.add(new Issue("AML_NOT_SCREENED", Severity.BLOCKER, m.name(),
                    m.name() + " has never been screened against the watchlist.",
                    "Run screen_name for " + first(m) + " with date of birth."));
        } else if ("potential_match".equals(sc.result())) {
            out.add(new Issue("AML_POTENTIAL_MATCH", Severity.BLOCKER, m.name(),
                    m.name() + " has an open potential watchlist match.",
                    "Compliance officer must review and clear or escalate. Do not tip off the client."));
        } else if (sc.lastScreened().isBefore(today.minusDays(365))) {
            out.add(new Issue("AML_SCREENING_STALE", Severity.ACTION, m.name(),
                    m.name() + " was last screened on " + sc.lastScreened() + ".",
                    "Re-run screen_name for " + first(m) + "."));
        }
    }

    private static String first(Member m) {
        return m.name().split(" ")[0];
    }
}
