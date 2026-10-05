package com.aurelius.actuary;

import com.aurelius.actuary.contract.InvokeContext;
import com.aurelius.actuary.mcp.McpClient;
import com.aurelius.actuary.mcp.PortfolioSource;
import com.aurelius.actuary.planning.ActuaryService;
import com.aurelius.actuary.planning.Assumptions;
import com.aurelius.actuary.planning.Portfolio;
import com.aurelius.actuary.planning.Profiles;
import com.aurelius.actuary.skills.SkillRegistry;
import com.aurelius.actuary.support.Json;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;

/** Builds the agent WITHOUT Spring: snapshot portfolios (or a given MCP client), fixed clock. */
public final class TestSupport {
    private TestSupport() {}

    public static final Clock FIXED = Clock.fixed(Instant.parse("2026-10-03T12:00:00Z"), ZoneOffset.UTC);
    public static final InvokeContext CTX = new InvokeContext("test-trace", "dev-advisor", null);
    public static final ObjectMapper MAPPER = Json.newMapper();

    public record Agent(Profiles profiles, Map<String, Portfolio> snapshot, ActuaryService service, SkillRegistry skills) {}

    public static Agent newAgent() throws IOException {
        return newAgent(null);
    }

    /** mcp == null: portfolios come from the snapshot file only. */
    public static Agent newAgent(McpClient mcp) throws IOException {
        Profiles profiles = Profiles.load(Path.of("data", "profiles.json"), MAPPER);
        Map<String, Portfolio> snapshot = PortfolioSource.loadSnapshot(Path.of("data", "portfolio-snapshot.json"), MAPPER);
        ActuaryService service = new ActuaryService(profiles, new PortfolioSource(mcp, snapshot), Assumptions.DEFAULT,
                FIXED, new ActuaryService.Settings(2000, 20000));          // 2000 sims keeps tests fast
        return new Agent(profiles, snapshot, service, new SkillRegistry(service, MAPPER));
    }
}
