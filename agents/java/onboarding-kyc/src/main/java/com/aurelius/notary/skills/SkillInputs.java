package com.aurelius.notary.skills;

import com.aurelius.notary.kyc.Model.DocType;
import com.aurelius.notary.support.Checks;

import java.time.LocalDate;
import java.util.regex.Pattern;

/**
 * One record per skill input. Each validates itself in its compact constructor
 * (the Java equivalent of the Zod schemas in the TypeScript agents).
 */
public final class SkillInputs {
    private SkillInputs() {}

    private static final Pattern PERSON_NAME = Pattern.compile("^[\\p{L} .'-]{2,120}$");
    private static final Pattern DOC_NUMBER = Pattern.compile("^[A-Za-z0-9 -]{4,40}$");

    public record CheckKycInput(String clientId) {
        public CheckKycInput {
            clientId = Checks.id("client_id", clientId);
        }
    }

    public record ListDocumentsInput(String clientId, String memberId) {
        public ListDocumentsInput {
            clientId = Checks.id("client_id", clientId);
            memberId = Checks.optionalId("member_id", memberId);
        }
    }

    /** With client_id + member_id, the result is also recorded on that person's KYC file. */
    public record ScreenNameInput(String name, LocalDate dob, String country, String clientId, String memberId) {
        public ScreenNameInput {
            name = Checks.text("name", name, 2, 120);
            if (!PERSON_NAME.matcher(name).matches()) {
                throw new IllegalArgumentException("name may contain only letters, spaces, '.', '-' and apostrophes");
            }
            if (country != null && !country.matches("^[A-Za-z]{2}$")) {
                throw new IllegalArgumentException("country must be a 2-letter code, e.g. US");
            }
            clientId = Checks.optionalId("client_id", clientId);
            memberId = Checks.optionalId("member_id", memberId);
            if (memberId != null && clientId == null) {
                throw new IllegalArgumentException("client_id is required when member_id is given");
            }
        }
    }

    public record RecordDocumentInput(String clientId, String memberId, DocType type, String label, String number,
                                      LocalDate issued, LocalDate expires, String accountId, String idempotencyKey) {
        public RecordDocumentInput {
            clientId = Checks.id("client_id", clientId);
            memberId = Checks.id("member_id", memberId);
            if (type == null) throw new IllegalArgumentException("type is required, e.g. GOVERNMENT_ID");
            if (label != null) label = Checks.text("label", label, 2, 60);
            if (number != null && !DOC_NUMBER.matcher(number).matches()) {
                throw new IllegalArgumentException("number must be 4-40 letters, digits, spaces or '-'");
            }
            if (issued == null) throw new IllegalArgumentException("issued is required (YYYY-MM-DD)");
            if (expires != null && !expires.isAfter(issued)) {
                throw new IllegalArgumentException("expires must be after issued");
            }
            accountId = Checks.optionalId("account_id", accountId);
            if (type == DocType.BENEFICIARY_DESIGNATION && accountId == null) {
                throw new IllegalArgumentException("account_id is required for a BENEFICIARY_DESIGNATION");
            }
            if (idempotencyKey != null) idempotencyKey = Checks.text("idempotency_key", idempotencyKey, 1, 128);
        }

        /** Keep only the last 4 letters/digits of a document number. The full number is never stored. */
        public String numberLast4() {
            if (number == null) return null;
            String clean = number.replaceAll("[^A-Za-z0-9]", "");
            return clean.substring(Math.max(0, clean.length() - 4));
        }
    }
}
