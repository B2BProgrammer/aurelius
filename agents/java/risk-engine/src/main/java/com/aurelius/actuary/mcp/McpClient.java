package com.aurelius.actuary.mcp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

/**
 * A minimal MCP client (Model Context Protocol, "streamable HTTP" transport),
 * written with Java's built-in HttpClient. No SDK needed.
 *
 * LEARN: MCP is JSON-RPC 2.0 over HTTP. One tool call is three POSTs to /mcp:
 *   1. initialize                 -> the reply header "mcp-session-id" names our session
 *   2. notifications/initialized  -> "I'm ready" (no reply body, HTTP 202)
 *   3. tools/call {name, arguments} -> result.structuredContent (the tool's JSON)
 * then DELETE /mcp ends the session. Replies may come as plain JSON or as
 * Server-Sent Events ("event: message" / "data: {...}"); we accept both.
 *
 * The Python Analyst talks to the SAME server with the official Python SDK.
 * Same protocol, two languages: that's the point of a standard.
 */
public class McpClient {

    /** The server is unreachable, slow, or refused us: callers may fall back. */
    public static class McpUnavailableException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public McpUnavailableException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    /** The tool ran and reported an error (e.g. "No client with id ..."): not a connectivity problem. */
    public static class McpToolException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public McpToolException(String message) {
            super(message);
        }
    }

    public static final String PROTOCOL_VERSION = "2025-06-18";

    private final URI url;
    private final String token;
    private final Duration timeout;
    private final ObjectMapper mapper;
    private final HttpClient http;
    private final AtomicLong ids = new AtomicLong();

    public McpClient(String url, String token, Duration timeout, ObjectMapper mapper) {
        this.url = URI.create(url);
        this.token = token;
        this.timeout = timeout;
        this.mapper = mapper;
        // HTTP/1.1 on purpose: Java's default tries an "Upgrade: h2c" to HTTP/2 on plain http://,
        // which Python's uvicorn doesn't support, and the request body gets lost (-32700 Parse error).
        this.http = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(timeout).build();
    }

    public String url() {
        return url.toString();
    }

    /** Open a session, call one tool, close the session. Returns the tool's structured JSON. */
    public JsonNode callTool(String tool, Map<String, Object> arguments, String traceId) {
        String session = null;
        try {
            Reply init = post(null, traceId, request("initialize", Map.of(
                    "protocolVersion", PROTOCOL_VERSION,
                    "capabilities", Map.of(),
                    "clientInfo", Map.of("name", "aurelius-actuary", "version", "0.1.0"))));
            session = init.session();
            post(session, traceId, notification("notifications/initialized"));
            Reply call = post(session, traceId, request("tools/call", Map.of("name", tool, "arguments", arguments)));
            return toolResult(call.body(), tool);
        } finally {
            if (session != null) closeQuietly(session);
        }
    }

    private record Reply(String session, JsonNode body) {}

    private Reply post(String session, String traceId, ObjectNode message) {
        HttpRequest.Builder b = HttpRequest.newBuilder(url).timeout(timeout)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json, text/event-stream")
                .header("Authorization", "Bearer " + token)
                .header("X-Trace-Id", traceId)
                .POST(HttpRequest.BodyPublishers.ofString(message.toString()));
        if (session != null) {
            b.header("mcp-session-id", session).header("mcp-protocol-version", PROTOCOL_VERSION);
        }
        HttpResponse<String> res;
        try {
            res = http.send(b.build(), HttpResponse.BodyHandlers.ofString());
        } catch (IOException e) {
            throw new McpUnavailableException("MCP server not reachable at " + url + " (" + e.getClass().getSimpleName() + ")", e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new McpUnavailableException("interrupted", e);
        }
        if (res.statusCode() == 401) throw new McpUnavailableException("MCP server rejected our token (401)", null);
        if (res.statusCode() == 202 || res.body().isBlank()) {
            return new Reply(res.headers().firstValue("mcp-session-id").orElse(session), null);
        }
        if (res.statusCode() >= 400) {
            String detail = res.body().length() > 200 ? res.body().substring(0, 200) : res.body();
            throw new McpUnavailableException("MCP server answered HTTP " + res.statusCode() + ": " + detail.strip(), null);
        }
        String contentType = res.headers().firstValue("content-type").orElse("");
        JsonNode body = parse(contentType.contains("text/event-stream") ? sseData(res.body()) : res.body());
        if (body.has("error")) {
            throw new McpUnavailableException("MCP error: " + body.path("error").path("message").asText(), null);
        }
        return new Reply(res.headers().firstValue("mcp-session-id").orElse(session), body);
    }

    /** SSE body -> the JSON in its "data:" lines. */
    public static String sseData(String body) {
        StringBuilder data = new StringBuilder();
        for (String line : body.split("\r?\n")) {
            if (!line.startsWith("data:")) continue;
            if (!data.isEmpty()) data.append('\n');                     // SSE: several data lines join with \n
            data.append(line.substring(5).strip());
        }
        return data.toString();
    }

    private JsonNode toolResult(JsonNode body, String tool) {
        if (body == null) throw new McpUnavailableException("empty reply to tools/call " + tool, null);
        JsonNode result = body.path("result");
        if (result.path("isError").asBoolean(false)) {
            String text = result.path("content").path(0).path("text").asText("tool error");
            throw new McpToolException(text.replaceFirst("^Error executing tool \\w+: ", ""));
        }
        if (result.hasNonNull("structuredContent")) return result.get("structuredContent");
        return parse(result.path("content").path(0).path("text").asText("{}"));   // older servers: JSON as text
    }

    private JsonNode parse(String json) {
        try {
            return mapper.readTree(json);
        } catch (IOException e) {
            throw new McpUnavailableException("MCP reply is not JSON", e);
        }
    }

    private ObjectNode request(String method, Map<String, Object> params) {
        ObjectNode m = notification(method);
        m.put("id", ids.incrementAndGet());
        m.set("params", mapper.valueToTree(params));
        return m;
    }

    private ObjectNode notification(String method) {
        ObjectNode m = mapper.createObjectNode();
        m.put("jsonrpc", "2.0");
        m.put("method", method);
        return m;
    }

    private void closeQuietly(String session) {
        try {
            http.send(HttpRequest.newBuilder(url).timeout(timeout).header("Authorization", "Bearer " + token)
                    .header("mcp-session-id", session).DELETE().build(), HttpResponse.BodyHandlers.discarding());
        } catch (IOException e) {
            // closing is best effort
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
