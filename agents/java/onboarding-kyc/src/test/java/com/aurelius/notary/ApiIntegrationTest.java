package com.aurelius.notary;

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

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The REAL server (Tomcat + filters + controllers + Swagger) on a random port,
 * called over HTTP with Java's built-in HttpClient.
 *
 * LEARN: @SpringBootTest starts the whole application like `mvn spring-boot:run`,
 * but with test settings: a temp data folder, a test token, a fixed clock.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ApiIntegrationTest {

    static final String TOKEN = "integration-test-token-abcdefghij";
    static Path dir;

    @DynamicPropertySource
    static void testProperties(DynamicPropertyRegistry registry) throws IOException {
        dir = Files.createTempDirectory("notary-it-");
        registry.add("notary.service-token", () -> TOKEN);
        registry.add("notary.data-file", () -> dir.resolve("kyc.json").toString());
        registry.add("notary.audit-file", () -> dir.resolve("audit.jsonl").toString());
    }

    @TestConfiguration
    static class FixedClockConfig {
        @Bean
        @Primary
        Clock fixedClock() {
            return TestSupport.FIXED;              // 2026-10-03, so "expires in 43 days" is stable
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
                .header("Content-Type", "application/json")
                .header("X-Trace-Id", "it-trace-1")
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
    void healthIsPublicWithSecurityHeaders() throws Exception {
        HttpResponse<String> r = get("/health", null);
        assertEquals(200, r.statusCode());
        assertEquals("notary", json.readTree(r.body()).get("agent").asText());
        assertEquals("nosniff", r.headers().firstValue("X-Content-Type-Options").orElse(""));
        assertTrue(r.headers().firstValue("X-Trace-Id").isPresent());
    }

    @Test
    void agentCardListsFourSkills() throws Exception {
        JsonNode card = json.readTree(get("/.well-known/agent.json", null).body());
        assertEquals(4, card.get("skills").size());
        assertTrue(card.get("skills").get("record_document").get("writes").asBoolean());
    }

    @Test
    void invokeNeedsTheServiceToken() throws Exception {
        HttpResponse<String> r = post("/invoke", "{}", null);
        assertEquals(401, r.statusCode());
        assertEquals("Bearer", r.headers().firstValue("WWW-Authenticate").orElse(""));
        assertEquals(401, post("/invoke", "{}", "wrong-token").statusCode());
        assertEquals(401, get("/v1/clients", null).statusCode());
    }

    @Test
    void checkKycSpeaksSnakeCase() throws Exception {
        // chen-002: no Swagger example writes to it, so test order doesn't matter
        JsonNode r = invoke("check_kyc", Map.of("client_id", "chen-002"));
        assertEquals("notary", r.get("agent").asText());
        assertEquals("ok", r.get("status").asText());
        assertTrue(r.get("error").isNull());
        assertEquals("action_needed", r.get("output").get("status").asText());
        assertEquals("2026-10-03", r.get("output").get("as_of").asText());
        assertEquals("KYC_TRUSTED_CONTACT_MISSING", r.get("output").get("issues").get(0).get("rule").asText());
        assertEquals(72, r.get("output").get("members").get(0).get("age").asInt());
    }

    @Test
    void skillErrorsAreStatusErrorNotHttpErrors() throws Exception {
        assertEquals("unknown skill open_account", invoke("open_account", Map.of()).get("error").asText());
        assertTrue(invoke("check_kyc", Map.of("client_id", "nobody-1")).get("error").asText().contains("No KYC file"));
        assertEquals("invalid input: client_id is required", invoke("check_kyc", Map.of()).get("error").asText());
    }

    @Test
    void contractErrorsAre422And413() throws Exception {
        assertEquals(422, post("/invoke", "{\"skill\":\"check_kyc\",\"input\":{}}", TOKEN).statusCode());  // no context
        assertEquals(422, post("/invoke", "{not json", TOKEN).statusCode());
        String huge = "{\"skill\":\"check_kyc\",\"input\":{\"x\":\"" + "a".repeat(70_000) + "\"}}";
        assertEquals(413, post("/invoke", huge, TOKEN).statusCode());
    }

    @Test
    void browseEndpoints() throws Exception {
        JsonNode clients = json.readTree(get("/v1/clients", TOKEN).body());
        assertEquals(3, clients.size());
        assertEquals(200, get("/v1/clients/garcia-003/kyc", TOKEN).statusCode());
        assertEquals(404, get("/v1/clients/nobody-1/kyc", TOKEN).statusCode());
        assertEquals(14, json.readTree(get("/v1/rules", TOKEN).body()).size());
        HttpResponse<String> unknown = get("/no-such-page", null);
        assertEquals(404, unknown.statusCode());
        assertEquals("Not found", json.readTree(unknown.body()).get("detail").asText());
    }

    @Test
    void swaggerAndOpenApi() throws Exception {
        JsonNode doc = json.readTree(get("/openapi.json", null).body());
        assertTrue(doc.get("openapi").asText().startsWith("3."));
        assertEquals("bearer", doc.get("components").get("securitySchemes").get("serviceToken").get("scheme").asText());
        for (String path : new String[] {"/health", "/.well-known/agent.json", "/invoke", "/v1/clients", "/v1/rules"}) {
            assertTrue(doc.get("paths").has(path), path);
        }
        JsonNode context = doc.at("/components/schemas/InvokeContext/properties");
        assertTrue(context.has("trace_id"), "schemas are snake_case like the API: " + context);
        HttpResponse<String> docs = get("/docs", null);
        assertEquals(302, docs.statusCode());
        assertTrue(docs.headers().firstValue("Location").orElse("").contains("swagger-ui"));
        assertEquals(200, get("/swagger-ui/index.html", null).statusCode());
    }

    @Test
    void everySwaggerExampleWorks() throws Exception {
        JsonNode doc = json.readTree(get("/openapi.json", null).body());
        JsonNode examples = doc.at("/paths/~1invoke/post/requestBody/content/application~1json/examples");
        assertTrue(examples.size() >= 6, "examples from SkillRegistry: " + examples.size());
        for (Map.Entry<String, JsonNode> e : examples.properties()) {
            HttpResponse<String> r = post("/invoke", json.writeValueAsString(e.getValue().get("value")), TOKEN);
            assertEquals("ok", json.readTree(r.body()).get("status").asText(), e.getKey() + ": " + r.body());
        }
    }
}
