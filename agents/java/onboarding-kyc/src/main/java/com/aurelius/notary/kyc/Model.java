package com.aurelius.notary.kyc;

import java.time.LocalDate;
import java.time.Period;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * The KYC data model, as Java RECORDS.
 *
 * LEARN: A record is an immutable data class: fields, constructor, equals,
 * hashCode and toString in one line. Immutable means a change creates a NEW
 * object (see withDocument / withMember), so two threads can never see a
 * half-updated client. Jackson reads and writes records directly; the
 * snake_case JSON names come from the mapper (see support/Json.java).
 */
public final class Model {
    private Model() {}

    public enum DocType { GOVERNMENT_ID, PROOF_OF_ADDRESS, W9, BENEFICIARY_DESIGNATION, TRUSTED_CONTACT_FORM, OTHER }

    /** Result of the last AML watchlist screening for a person. */
    public record Screening(LocalDate lastScreened, String result) {}

    public record Member(String memberId, String name, String role, LocalDate dob, String citizenship,
                         boolean trustedContact, Screening screening) {

        public int ageOn(LocalDate day) {
            return Period.between(dob, day).getYears();
        }

        public boolean isAdultOn(LocalDate day) {
            return ageOn(day) >= 18;
        }

        public Member withScreening(Screening s) {
            return new Member(memberId, name, role, dob, citizenship, trustedContact, s);
        }
    }

    public record Account(String accountId, String type, String owner) {
        /** Retirement accounts pass to beneficiaries named on a form, not by will. */
        public boolean needsBeneficiary() {
            return type != null && (type.equals("IRA") || type.equals("ROTH_IRA") || type.equals("401K"));
        }
    }

    /** We keep only the LAST 4 characters of any document number (minimum necessary). */
    public record Document(String docId, String memberId, DocType type, String label, String numberLast4,
                           LocalDate issued, LocalDate expires, String accountId, boolean verified,
                           LocalDate recorded) {}

    public record ClientFile(String household, String sourceOfFunds, LocalDate riskQuestionnaireDate,
                             List<Member> members, List<Account> accounts, List<Document> documents) {

        public ClientFile {
            members = members == null ? List.of() : List.copyOf(members);
            accounts = accounts == null ? List.of() : List.copyOf(accounts);
            documents = documents == null ? List.of() : List.copyOf(documents);
        }

        public ClientFile withDocument(Document d) {
            List<Document> docs = new ArrayList<>(documents);
            docs.add(d);
            return new ClientFile(household, sourceOfFunds, riskQuestionnaireDate, members, accounts, docs);
        }

        public ClientFile withMember(Member updated) {
            List<Member> list = members.stream()
                    .map(m -> m.memberId().equals(updated.memberId()) ? updated : m).toList();
            return new ClientFile(household, sourceOfFunds, riskQuestionnaireDate, list, accounts, documents);
        }

        public Member member(String memberId) {
            return members.stream().filter(m -> m.memberId().equals(memberId)).findFirst().orElse(null);
        }

        public List<Document> docsOf(String memberId, DocType type) {
            return documents.stream().filter(d -> d.type() == type && d.verified()
                    && (memberId == null || memberId.equals(d.memberId()))).toList();
        }
    }

    /** The whole file on disk. "processed" maps idempotency keys to the doc_id they created. */
    public record KycData(Map<String, ClientFile> clients, Map<String, String> processed, int nextDocNumber) {
        public KycData {
            clients = clients == null ? Map.of() : Map.copyOf(clients);
            processed = processed == null ? Map.of() : Map.copyOf(processed);
        }
    }
}
