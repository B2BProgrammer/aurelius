package com.aurelius.notary.support;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Set;
import java.util.regex.Pattern;

/** Small validation and security helpers shared by the whole agent. */
public final class Checks {
    private Checks() {}

    private static final Pattern ID = Pattern.compile("^[A-Za-z0-9_-]{1,64}$");
    private static final Set<String> WEAK = Set.of("", "replace-me", "replace-with-long-random-string");

    /** Ids go into file lookups and logs: allow only safe characters (no "../"). */
    public static String id(String field, String value) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(field + " is required");
        if (!ID.matcher(value).matches()) {
            throw new IllegalArgumentException(field + " must be 1-64 letters, digits, '-' or '_'");
        }
        return value;
    }

    public static String optionalId(String field, String value) {
        return value == null ? null : id(field, value);
    }

    public static String text(String field, String value, int min, int max) {
        if (value == null) throw new IllegalArgumentException(field + " is required");
        String v = value.strip();
        if (v.length() < min || v.length() > max) {
            throw new IllegalArgumentException(field + " must be " + min + "-" + max + " characters");
        }
        if (v.chars().anyMatch(ch -> ch < 0x20)) throw new IllegalArgumentException(field + " has control characters");
        return v;
    }

    /** Fail closed: refuse to start with a guessable service token. */
    public static void serviceToken(String token) {
        if (token == null || WEAK.contains(token) || token.length() < 24) {
            throw new IllegalStateException("SERVICE_TOKEN is missing or too short (need 24+ chars) in aurelius\\.env. "
                    + "Use the same value as the other agents.");
        }
    }

    /**
     * Constant-time comparison (like Python's hmac.compare_digest / Node's timingSafeEqual).
     * MessageDigest.isEqual doesn't stop at the first different byte, so timing can't leak the token.
     */
    public static boolean tokenEquals(String expected, String supplied) {
        if (supplied == null) return false;
        return MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8));
    }

    public static String sha256(String text) {
        try {
            byte[] h = MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(h);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Deepest cause message: turns Jackson's wrapped errors into "client_id is required". */
    public static String rootMessage(Throwable t) {
        Throwable cur = t;
        while (cur.getCause() != null && cur.getCause() != cur) cur = cur.getCause();
        String msg = cur.getMessage() == null ? cur.getClass().getSimpleName() : cur.getMessage();
        int nl = msg.indexOf('\n');
        return nl > 0 ? msg.substring(0, nl) : msg;
    }
}
