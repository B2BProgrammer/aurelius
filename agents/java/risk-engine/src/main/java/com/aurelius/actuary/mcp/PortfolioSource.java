package com.aurelius.actuary.mcp;

import com.aurelius.actuary.planning.Portfolio;
import com.aurelius.actuary.support.NotFoundException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/**
 * Where portfolios come from: LIVE from the MCP server, or (only if it's down)
 * a snapshot file. The answer always says which one was used.
 *
 * LEARN: graceful degradation (same idea as the Herald when the Liaison is down):
 * a projection from slightly old numbers, clearly labelled, beats no projection.
 * But "unknown client" is NOT a reason to fall back: that's a real error.
 */
public class PortfolioSource {

    private static final Logger log = LoggerFactory.getLogger(PortfolioSource.class);

    private final McpClient mcp;              // null = MCP disabled (tests)
    private final Map<String, Portfolio> snapshot;

    public PortfolioSource(McpClient mcp, Map<String, Portfolio> snapshot) {
        this.mcp = mcp;
        this.snapshot = Map.copyOf(snapshot);
    }

    private record SnapshotFile(Map<String, Portfolio> clients) {}

    public static Map<String, Portfolio> loadSnapshot(Path file, ObjectMapper mapper) throws IOException {
        Map<String, Portfolio> out = new HashMap<>();
        mapper.readValue(Files.readString(file), SnapshotFile.class).clients()
                .forEach((id, p) -> out.put(id, p.withSource("snapshot")));
        return out;
    }

    public Portfolio get(String clientId, String traceId) {
        if (mcp != null) {
            try {
                return fromMcp(clientId, traceId);
            } catch (McpClient.McpToolException e) {
                throw new NotFoundException(e.getMessage());                     // e.g. "No client with id 'x'"
            } catch (McpClient.McpUnavailableException e) {
                log.warn("mcp_unavailable reason={} trace={}", e.getMessage(), traceId);
                Portfolio p = fromSnapshot(clientId);
                return p.withSource("snapshot (MCP unavailable: " + e.getMessage() + ")");
            }
        }
        return fromSnapshot(clientId);
    }

    private Portfolio fromSnapshot(String clientId) {
        Portfolio p = snapshot.get(clientId);
        if (p == null) throw new NotFoundException("No portfolio for client '" + clientId + "'");
        return p;
    }

    /** Two MCP tools: get_client_profile (label, target mix) + get_holdings (positions). */
    private Portfolio fromMcp(String clientId, String traceId) {
        JsonNode profile = mcp.callTool("get_client_profile", Map.of("client_id", clientId), traceId);
        JsonNode holdings = mcp.callTool("get_holdings", Map.of("client_id", clientId), traceId);

        Map<String, Double> byClass = new HashMap<>();
        Map<String, Double> stocks = new HashMap<>();
        for (JsonNode pos : holdings.path("positions")) {
            double value = pos.path("market_value").asDouble();
            byClass.merge(pos.path("asset_class").asText("other"), value, Double::sum);
            if ("stock".equals(pos.path("security_type").asText())) {
                stocks.merge(pos.path("symbol").asText(), value, Double::sum);   // same stock in 2 accounts = 1 position
            }
        }
        Portfolio.Stock largest = stocks.entrySet().stream().max(Map.Entry.comparingByValue())
                .map(e -> new Portfolio.Stock(e.getKey(), e.getValue())).orElse(null);
        Map<String, Double> target = new HashMap<>();
        profile.path("target_allocation_pct").properties().forEach(e -> target.put(e.getKey(), e.getValue().asDouble()));

        return new Portfolio("mcp", holdings.path("as_of").asText(null), profile.path("risk_profile").asText(null),
                target, holdings.path("total_market_value").asDouble(), byClass, largest);
    }
}
