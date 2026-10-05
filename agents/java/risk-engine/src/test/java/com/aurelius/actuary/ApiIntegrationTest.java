package com.aurelius.actuary;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Clock;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The REAL server over HTTP. The MCP URL points at a closed port on purpose,
 * so these tests also prove the snapshot fallback works end to end.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ApiIntegrationTest {

    static final String TOKEN = "integration-test-token-abcdefghij";

    @DynamicPropertySource
    static void testProperties(DynamicPropertyRegistry registry) {
        registry.add("actuary.service-token", () -> TOKEN);
        registry.add("actuary.mcp-url", () -> "http://127.0.0.1:1/mcp");
        registry.add("actuary.mcp-timeout-ms", () -> "500");
        registry.add("actuary.default-simulations", () -> "1000");
    }

    @TestConfiguration
    static class FixedClockConfig {
        @Bean
        @Primary
        Clock fixedClock() {
            return TestSupport.FIXED;
        }
    }

    @LocalServerPort
    int port;

    private final HttpClient http = HttpClient.newHttpClient();
    private final ObjectMapper json = new ObjectMapper();

    private HttpResponse<String> get(String path, String token) throws Exception {
        HttpRequest.Builder b = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path)).GET();
        if (token != null) b.header("Authorization", "Bearer " + token);
        return http.send(b.build(), HttpResponse.BodyHandlers.ofString());
    }

    private HttpResponse<String> post(String path, String body, String token) throws Exception {
        HttpRequest.Builder b = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
                .header("Content-Type", "application/json").header("X-Trace-Id", "it-trace-1")
                .POST(HttpRequest.BodyPublishers.ofString(body));
        if (token != null) b.header("Authorization", "Bearer " + token);
        return http.send(b.build(), HttpResponse.BodyHandlers.ofString());
    }

    private JsonNode invoke(String skill, Map<String, Object> input) throws Exception {
        String body = json.writeValueAsString(Map.of("skill", skill, "input", input,
                "context", Map.of("trace_id", "it-trace-1", "user_id", "dev-advisor")));
        HttpResponse<String> r = post("/invoke", body, TOKEN);
        assertEquals(200, r.statusCode(), r.body());
        return json.readTree(r.body());
    }

    @Test
    void healthAndAgentCardArePublic() throws Exception {
        HttpResponse<String> r = get("/health", null);
        assertEquals(200, r.statusCode());
        assertEquals("actuary", json.readTree(r.body()).get("agent").asText());
        assertEquals("nosniff", r.headers().firstValue("X-Content-Type-Options").orElse(""));
        assertEquals(3, json.readTree(get("/.well-known/agent.json", null).body()).get("skills").size());
    }

    @Test
    void invokeNeedsTheServiceToken() throws Exception {
        HttpResponse<String> r = post("/invoke", "{}", null);
        assertEquals(401, r.statusCode());
        assertEquals("Bearer", r.headers().firstValue("WWW-Authenticate").orElse(""));
        assertEquals(401, get("/v1/assumptions", "wrong-token").statusCode());
    }

    @Test
    void riskScoreFallsBackToTheSnapshot() throws Exception {
        JsonNode r = invoke("risk_score", Map.of("client_id", "patel-001"));
        assertEquals("ok", r.get("status").asText());
        assertEquals(60, r.get("output").get("risk_score").asInt());
        assertTrue(r.get("output").get("portfolio_source").asText().startsWith("snapshot (MCP unavailable"));
    }

    @Test
    void projectionSpeaksSnakeCaseWithWholeDollars() throws Exception {
        JsonNode out = invoke("project_retirement", Map.of("client_id", "patel-001", "retire_ages", List.of(62, 63))).get("output");
        JsonNode first = out.get("scenarios").get(0);
        assertEquals(62, first.get("retire_age").asInt());
        assertTrue(first.get("probability_of_success_pct").asDouble() > 0);
        assertTrue(first.get("balance_at_plan_end").get("p90").isIntegralNumber(), "no 1.2E7 notation");
        assertTrue(out.get("disclosure").asText().contains("Not a guarantee"));
    }

    @Test
    void errors() throws Exception {
        assertEquals("unknown skill buy_stock", invoke("buy_stock", Map.of()).get("error").asText());
        assertTrue(invoke("risk_score", Map.of("client_id", "nobody-1")).get("error").asText().contains("No planning profile"));
        assertEquals(422, post("/invoke", "{\"skill\":\"risk_score\",\"input\":{}}", TOKEN).statusCode());   // no context
        assertEquals(422, post("/invoke", "{not json", TOKEN).statusCode());
        String huge = "{\"skill\":\"x\",\"input\":{\"x\":\"" + "a".repeat(70_000) + "\"}}";
        assertEquals(413, post("/invoke", huge, TOKEN).statusCode());
        HttpResponse<String> unknown = get("/no-such-page", null);
        assertEquals(404, unknown.statusCode());
        assertEquals("Not found", json.readTree(unknown.body()).get("detail").asText());
    }

    @Test
    void browseEndpoints() throws Exception {
        assertEquals(3, json.readTree(get("/v1/clients", TOKEN).body()).size());
        JsonNode a = json.readTree(get("/v1/assumptions", TOKEN).body());
        assertEquals(0.05, a.get("capital_market_assumptions").get("equity_mean").asDouble());
        assertEquals(5, a.get("risk_bands").size());
    }

    @Test
    void swaggerAndEveryExample() throws Exception {
        JsonNode doc = json.readTree(get("/openapi.json", null).body());
        assertEquals("bearer", doc.get("components").get("securitySchemes").get("serviceToken").get("scheme").asText());
        assertTrue(doc.at("/components/schemas/InvokeContext/properties").has("trace_id"));
        HttpResponse<String> docs = get("/docs", null);
        assertEquals(302, docs.statusCode());
        assertTrue(docs.headers().firstValue("Location").orElse("").contains("swagger-ui"));

        JsonNode examples = doc.at("/paths/~1invoke/post/requestBody/content/application~1json/examples");
        assertEquals(7, examples.size());
        for (Map.Entry<String, JsonNode> e : examples.properties()) {
            HttpResponse<String> r = post("/invoke", json.writeValueAsString(e.getValue().get("value")), TOKEN);
            assertEquals("ok", json.readTree(r.body()).get("status").asText(), e.getKey() + ": " + r.body());
        }
    }
}
