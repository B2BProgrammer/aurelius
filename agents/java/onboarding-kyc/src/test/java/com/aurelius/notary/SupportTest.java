package com.aurelius.notary;

import com.aurelius.notary.support.Checks;
import com.aurelius.notary.support.DotEnv;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** .env parsing, the fail-closed token check, constant-time compare. */
class SupportTest {

    @Test
    void parsesDotEnvLikeTheOtherAgents() {
        Map<String, String> env = DotEnv.parse(List.of(
                "# comment",
                "",
                "SERVICE_TOKEN=abc123     # same token everywhere",
                "export LLM_MOCK=true",
                "QUOTED=\"has # hash\"",
                "EMPTY=",
                "URL=http://127.0.0.1:8102"));
        assertEquals("abc123", env.get("SERVICE_TOKEN"));
        assertEquals("true", env.get("LLM_MOCK"));
        assertEquals("has # hash", env.get("QUOTED"));
        assertEquals("", env.get("EMPTY"));
        assertEquals("http://127.0.0.1:8102", env.get("URL"));
    }

    @Test
    void weakTokensAreRejected() {
        for (String weak : new String[] {null, "", "replace-me", "replace-with-long-random-string", "short-token"}) {
            assertThrows(IllegalStateException.class, () -> Checks.serviceToken(weak));
        }
        Checks.serviceToken("a-long-enough-service-token-123");
    }

    @Test
    void tokenCompare() {
        assertTrue(Checks.tokenEquals("secret-token", "secret-token"));
        assertFalse(Checks.tokenEquals("secret-token", "secret-tokeN"));
        assertFalse(Checks.tokenEquals("secret-token", null));
    }

    @Test
    void controlCharactersAreRejected() {
        assertThrows(IllegalArgumentException.class, () -> Checks.text("trace_id", "abc\ninjected", 1, 128));
    }
}
