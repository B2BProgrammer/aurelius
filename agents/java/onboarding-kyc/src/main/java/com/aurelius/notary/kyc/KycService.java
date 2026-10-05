package com.aurelius.notary.kyc;

import com.aurelius.notary.contract.InvokeContext;
import com.aurelius.notary.kyc.KycRules.Issue;
import com.aurelius.notary.kyc.KycRules.Severity;
import com.aurelius.notary.kyc.Model.ClientFile;
import com.aurelius.notary.kyc.Model.DocType;
import com.aurelius.notary.kyc.Model.Document;
import com.aurelius.notary.kyc.Model.Member;
import com.aurelius.notary.kyc.Model.Screening;
import com.aurelius.notary.screening.NameScreener;
import com.aurelius.notary.skills.SkillInputs.ListDocumentsInput;
import com.aurelius.notary.skills.SkillInputs.RecordDocumentInput;
import com.aurelius.notary.skills.SkillInputs.ScreenNameInput;
import com.aurelius.notary.store.AuditLog;
import com.aurelius.notary.store.KycStore;
import com.aurelius.notary.support.Checks;

import java.time.Clock;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * What the Notary can do (the use cases). Plain Java: no web, no Spring, so
 * it's easy to test. The web layer only translates HTTP <-> these methods.
 */
public class KycService {

    public record MemberSummary(String memberId, String name, String role, int age,
                                LocalDate idValidUntil, LocalDate lastScreened, String screeningResult) {}

    public record KycReport(String clientId, String household, LocalDate asOf, String status,
                            Map<String, Long> counts, String headline, List<Issue> issues, List<MemberSummary> members) {}

    private final KycStore store;
    private final NameScreener screener;
    private final AuditLog audit;
    private final Clock clock;
    private final KycRules.Settings settings;

    public KycService(KycStore store, NameScreener screener, AuditLog audit, Clock clock, KycRules.Settings settings) {
        this.store = store;
        this.screener = screener;
        this.audit = audit;
        this.clock = clock;
        this.settings = settings;
    }

    public LocalDate today() {
        return LocalDate.now(clock);
    }

    // ------------------------------------------------------------------ check_kyc
    public KycReport checkKyc(String clientId) {
        ClientFile c = client(clientId);
        LocalDate today = today();
        List<Issue> issues = KycRules.evaluate(c, today, settings);

        Map<Severity, Long> bySeverity = new EnumMap<>(Severity.class);
        for (Severity s : Severity.values()) bySeverity.put(s, 0L);
        issues.forEach(i -> bySeverity.merge(i.severity(), 1L, Long::sum));
        Map<String, Long> counts = new LinkedHashMap<>();
        bySeverity.forEach((k, v) -> counts.put(k.name().toLowerCase(), v));

        String status = bySeverity.get(Severity.BLOCKER) > 0 ? "blocked"
                : bySeverity.get(Severity.ACTION) > 0 ? "action_needed" : "complete";
        return new KycReport(clientId, c.household(), today, status, counts, headline(status, counts, issues),
                issues, c.members().stream().map(m -> summary(c, m, today)).toList());
    }

    private static String headline(String status, Map<String, Long> counts, List<Issue> issues) {
        if (status.equals("complete")) {
            return "KYC complete. " + (counts.get("info") > 0 ? counts.get("info") + " suggestion(s)." : "Nothing outstanding.");
        }
        long n = status.equals("blocked") ? counts.get("blocker") : counts.get("action");
        String what = status.equals("blocked") ? (n == 1 ? "1 blocker" : n + " blockers")
                : (n == 1 ? "1 action item" : n + " action items");
        return (status.equals("blocked") ? "BLOCKED: " : "") + what + ". " + issues.get(0).message();
    }

    private static MemberSummary summary(ClientFile c, Member m, LocalDate today) {
        LocalDate idUntil = c.docsOf(m.memberId(), DocType.GOVERNMENT_ID).stream()
                .map(Document::expires).filter(d -> d != null).max(Comparator.naturalOrder()).orElse(null);
        Screening s = m.screening();
        return new MemberSummary(m.memberId(), m.name(), m.role(), m.ageOn(today), idUntil,
                s == null ? null : s.lastScreened(), s == null ? "never" : s.result());
    }

    // ------------------------------------------------------------------ list_documents
    public Map<String, Object> listDocuments(ListDocumentsInput in) {
        ClientFile c = client(in.clientId());
        if (in.memberId() != null && c.member(in.memberId()) == null) {
            throw new IllegalArgumentException("No member '" + in.memberId() + "' in " + in.clientId());
        }
        LocalDate today = today();
        Map<String, String> names = c.members().stream().collect(Collectors.toMap(Member::memberId, Member::name));
        List<Map<String, Object>> docs = new ArrayList<>();
        for (Document d : c.documents()) {
            if (in.memberId() != null && !in.memberId().equals(d.memberId())) continue;
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("doc_id", d.docId());
            row.put("member", names.getOrDefault(d.memberId(), d.memberId()));
            row.put("type", d.type());
            row.put("label", d.label());
            row.put("number", d.numberLast4() == null ? null : "****" + d.numberLast4());   // masked
            row.put("issued", d.issued());
            row.put("expires", d.expires());
            row.put("account_id", d.accountId());
            row.put("state", state(d, today));
            docs.add(row);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("client_id", in.clientId());
        out.put("household", c.household());
        out.put("documents", docs);
        return out;
    }

    private String state(Document d, LocalDate today) {
        if (!d.verified()) return "unverified";
        if (d.expires() == null) return "valid";
        long days = ChronoUnit.DAYS.between(today, d.expires());
        return days < 0 ? "expired" : days <= settings.expiringWindowDays() ? "expiring" : "valid";
    }

    // ------------------------------------------------------------------ screen_name
    public Map<String, Object> screenName(ScreenNameInput in, InvokeContext ctx) {
        Member member = null;
        if (in.memberId() != null) {
            member = client(in.clientId()).member(in.memberId());
            if (member == null) throw new IllegalArgumentException("No member '" + in.memberId() + "' in " + in.clientId());
        }
        LocalDate dob = in.dob() != null ? in.dob() : member != null ? member.dob() : null;
        String country = in.country() != null ? in.country() : member != null ? member.citizenship() : null;
        NameScreener.Result result = screener.screen(in.name(), dob, country);
        LocalDate today = today();

        if (member != null) store.recordScreening(in.clientId(), in.memberId(), new Screening(today, result.result()));

        Map<String, Object> log = new LinkedHashMap<>();
        log.put("trace_id", ctx.traceId());
        log.put("user_id", ctx.userId());
        log.put("skill", "screen_name");
        log.put("client_id", in.clientId());
        log.put("member_id", in.memberId());
        log.put("name_sha256", Checks.sha256(NameScreener.normalize(in.name())).substring(0, 16));
        log.put("result", result.result());
        log.put("match_ids", result.matches().stream().map(NameScreener.Match::listId).toList());
        audit.record(log);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("result", result.result());
        out.put("requires_review", result.requiresReview());
        out.put("matches", result.matches());
        out.put("threshold", screener.threshold());
        out.put("used_dob", dob != null);
        out.put("screened_on", today);
        out.put("recorded_on", member == null ? null : in.memberId());
        out.put("note", result.requiresReview()
                ? "Potential match only. A compliance officer must review. Do not tell the client about the screening."
                : "No watchlist entry at or above the threshold.");
        return out;
    }

    // ------------------------------------------------------------------ record_document
    public Map<String, Object> recordDocument(RecordDocumentInput in, InvokeContext ctx) {
        ClientFile c = client(in.clientId());
        Member member = c.member(in.memberId());
        if (member == null) throw new IllegalArgumentException("No member '" + in.memberId() + "' in " + in.clientId());
        if (in.accountId() != null && c.accounts().stream().noneMatch(a -> a.accountId().equals(in.accountId()))) {
            throw new IllegalArgumentException("No account '" + in.accountId() + "' in " + in.clientId());
        }
        LocalDate today = today();
        if (in.issued().isAfter(today)) throw new IllegalArgumentException("issued can't be in the future");

        // Explicit key, or derived from trace + content: a retried request can't create a second document.
        // Only the last 4 of the number go into the key (the key is stored on disk).
        String key = in.idempotencyKey() != null ? in.idempotencyKey()
                : Checks.sha256(String.join("|", ctx.traceId(), "record_document", in.clientId(), in.memberId(),
                        in.type().name(), String.valueOf(in.issued()), String.valueOf(in.expires()),
                        String.valueOf(in.numberLast4()), String.valueOf(in.accountId())));

        Function<String, Document> make = docId -> new Document(docId, in.memberId(), in.type(),
                in.label() != null ? in.label() : in.type().name().replace('_', ' ').toLowerCase(),
                in.numberLast4(), in.issued(), in.expires(), in.accountId(), true, today);
        KycStore.Added added = store.addDocument(in.clientId(), key, make);

        Map<String, Object> log = new LinkedHashMap<>();
        log.put("trace_id", ctx.traceId());
        log.put("user_id", ctx.userId());
        log.put("skill", "record_document");
        log.put("client_id", in.clientId());
        log.put("member_id", in.memberId());
        log.put("doc_id", added.document().docId());
        log.put("type", in.type().name());
        log.put("duplicate", added.duplicate());
        audit.record(log);

        List<String> warnings = new ArrayList<>();
        if (in.expires() != null && in.expires().isBefore(today)) warnings.add("This document is already expired.");
        KycReport after = checkKyc(in.clientId());

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("doc_id", added.document().docId());
        out.put("duplicate", added.duplicate());
        out.put("document", added.document());
        out.put("warnings", warnings);
        out.put("kyc_status_now", after.status());
        out.put("kyc_headline_now", after.headline());
        return out;
    }

    // ------------------------------------------------------------------ browse
    public List<Map<String, Object>> clientSummaries() {
        return store.clientIds().stream().map(id -> {
            KycReport r = checkKyc(id);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("client_id", id);
            row.put("household", r.household());
            row.put("status", r.status());
            row.put("headline", r.headline());
            return row;
        }).toList();
    }

    public int clientCount() {
        return store.clientIds().size();
    }

    private ClientFile client(String clientId) {
        return store.get(clientId).orElseThrow(() -> new NotFoundException("No KYC file for client '" + clientId + "'"));
    }
}
