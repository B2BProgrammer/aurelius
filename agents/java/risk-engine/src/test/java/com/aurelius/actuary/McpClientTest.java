package com.aurelius.actuary;

import com.aurelius.actuary.mcp.McpClient;
import com.aurelius.actuary.mcp.PortfolioSource;
import com.aurelius.actuary.planning.Portfolio;
import com.aurelius.actuary.support.NotFoundException;
import com.fasterxml.jackson.databind.JsonNode;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The MCP client against a FAKE MCP server (the JDK's built-in HttpServer) that
 * answers like the real Python one: SSE replies, a session header, 401 on a bad token.
 */
class McpClientTest {

    static final String TOKEN = "test-service-token-abcdefghijklmnop";
    private final List<String> seen = new ArrayList<>();
    private int port;
    private HttpServer server;

    private static final String HOLDINGS = """
            {"client_id":"patel-001","as_of":"2026-10-01","total_market_value":1000.0,"positions":[
              {"symbol":"XYZ","asset_class":"equity","security_type":"stock","market_value":300.0},
              {"symbol":"XYZ","asset_class":"equity","security_type":"stock","market_value":100.0},
              {"symbol":"USTM","asset_class":"equity","security_type":"fund","market_value":200.0},
              {"symbol":"AGGB","asset_class":"fixed_income","security_type":"fund","market_value":350.0},
              {"symbol":"MMKT","asset_class":"cash","security_type":"fund","market_value":50.0}]}""";
    private static final String PROFILE = """
            {"client_id":"patel-001","risk_profile":"moderate","target_allocation_pct":{"equity":60,"fixed_income":35,"cash":5}}""";

    @BeforeEach
    void startFakeServer() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/mcp", ex -> {
            String body = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            seen.add(ex.getRequestMethod() + " " + body + " session=" + ex.getRequestHeaders().getFirst("mcp-session-id")
                    + " trace=" + ex.getRequestHeaders().getFirst("X-Trace-Id")
                    + " upgrade=" + ex.getRequestHeaders().getFirst("Upgrade"));
            if (!("Bearer " + TOKEN).equals(ex.getRequestHeaders().getFirst("Authorization"))) {
                ex.sendResponseHeaders(401, -1);
                ex.close();
                return;
            }
            if (ex.getRequestMethod().equals("DELETE") || body.contains("notifications/initialized")) {
                ex.sendResponseHeaders(202, -1);
                ex.close();
                return;
            }
            String id = body.replaceAll(".*\"id\":(\\d+).*", "$1");
            String result;
            if (body.contains("\"initialize\"")) {
                ex.getResponseHeaders().add("mcp-session-id", "sess-123");
                result = "{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"serverInfo\":{\"name\":\"fake\"}}";
            } else if (body.contains("nobody-1")) {
                result = "{\"content\":[{\"type\":\"text\",\"text\":\"Error executing tool get_holdings: No client with id 'nobody-1'\"}],\"isError\":true}";
            } else if (body.contains("get_holdings")) {
                result = "{\"content\":[],\"isError\":false,\"structuredContent\":" + HOLDINGS + "}";
            } else {
                result = "{\"content\":[],\"isError\":false,\"structuredContent\":" + PROFILE + "}";
            }
            result = result.replaceAll("\\s*\\n\\s*", "");                       // one JSON line per data: line, like a real server
            byte[] sse = ("event: message\r\ndata: {\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":" + result + "}\r\n\r\n")
                    .getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("content-type", "text/event-stream");
            ex.sendResponseHeaders(200, sse.length);
            ex.getResponseBody().write(sse);
            ex.close();
        });
        server.start();
        port = server.getAddress().getPort();
    }

    @AfterEach
    void stopFakeServer() {
        server.stop(0);
    }

    private McpClient client(String token) {
        return new McpClient("http://127.0.0.1:" + port + "/mcp", token, Duration.ofSeconds(2), TestSupport.MAPPER);
    }

    @Test
    void handshakeThenToolCallThenClose() {
        JsonNode r = client(TOKEN).callTool("get_holdings", Map.of("client_id", "patel-001"), "trace-42");
        assertEquals(1000.0, r.path("total_market_value").asDouble());
        assertTrue(seen.get(0).contains("\"initialize\"") && seen.get(0).contains("session=null"));
        assertTrue(seen.get(1).contains("notifications/initialized") && seen.get(1).contains("session=sess-123"));
        assertTrue(seen.get(2).contains("tools/call") && seen.get(2).contains("trace=trace-42"));
        assertTrue(seen.get(3).startsWith("DELETE"), "session closed");
        // HTTP/1.1 only: an "Upgrade: h2c" makes Python's uvicorn drop the body (real bug, found live)
        assertTrue(seen.stream().allMatch(line -> line.endsWith("upgrade=null")), seen.toString());
    }

    @Test
    void toolErrorsAreNotConnectivityErrors() {
        assertThrows(McpClient.McpToolException.class,
                () -> client(TOKEN).callTool("get_holdings", Map.of("client_id", "nobody-1"), "t"));
    }

    @Test
    void wrongTokenIsUnavailable() {
        McpClient.McpUnavailableException e = assertThrows(McpClient.McpUnavailableException.class,
                () -> client("wrong-token").callTool("get_holdings", Map.of("client_id", "patel-001"), "t"));
        assertTrue(e.getMessage().contains("401"));
    }

    @Test
    void portfolioFromMcpAggregatesPositions() throws Exception {
        PortfolioSource source = new PortfolioSource(client(TOKEN), Map.of());
        Portfolio p = source.get("patel-001", "t");
        assertEquals("mcp", p.source());
        assertEquals(0.6, p.weight("equity"), 1e-9);
        assertEquals("XYZ", p.largestSingleStock().symbol());
        assertEquals(400.0, p.largestSingleStock().marketValue());       // same stock in two accounts, added up
        assertEquals(Double.valueOf(60), p.targetAllocationPct().get("equity"));
        assertEquals("moderate", p.riskProfile());
        assertThrows(NotFoundException.class, () -> source.get("nobody-1", "t"));
    }

    @Test
    void fallsBackToTheSnapshotWhenMcpIsDown() throws Exception {
        Map<String, Portfolio> snapshot = PortfolioSource.loadSnapshot(Path.of("data", "portfolio-snapshot.json"), TestSupport.MAPPER);
        McpClient dead = new McpClient("http://127.0.0.1:1/mcp", TOKEN, Duration.ofMillis(500), TestSupport.MAPPER);
        Portfolio p = new PortfolioSource(dead, snapshot).get("chen-002", "t");
        assertTrue(p.source().startsWith("snapshot (MCP unavailable"), p.source());
        assertEquals(900000.25, p.totalMarketValue());
        assertNull(p.largestSingleStock());
    }

    @Test
    void sseParsing() {
        assertEquals("{\"a\":1}", McpClient.sseData("event: message\ndata: {\"a\":1}\n\n"));
    }
}
