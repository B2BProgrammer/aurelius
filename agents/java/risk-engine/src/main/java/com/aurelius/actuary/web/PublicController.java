package com.aurelius.actuary.web;

import com.aurelius.actuary.ActuaryApplication;
import com.aurelius.actuary.mcp.McpClient;
import com.aurelius.actuary.planning.ActuaryService;
import com.aurelius.actuary.skills.SkillRegistry;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/** No token needed: liveness and the agent card. */
@RestController
@Tag(name = "public", description = "No token needed")
public class PublicController {

    private final ActuaryService service;
    private final McpClient mcp;
    private final SkillRegistry skills;

    public PublicController(ActuaryService service, McpClient mcp, SkillRegistry skills) {
        this.service = service;
        this.mcp = mcp;
        this.skills = skills;
    }

    @Operation(summary = "Liveness check")
    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("status", "ok");
        out.put("agent", "actuary");
        out.put("version", ActuaryApplication.VERSION);
        out.put("clients", service.clientCount());
        out.put("mcp_url", mcp.url());
        return out;
    }

    @Operation(summary = "Agent card: skills and their input schemas")
    @GetMapping("/.well-known/agent.json")
    public Map<String, Object> agentCard() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("name", "actuary");
        out.put("codename", "Actuary");
        out.put("folder", "risk-engine");
        out.put("language", "Java 21 (Spring Boot)");
        out.put("version", ActuaryApplication.VERSION);
        out.put("description", "Risk score, Monte Carlo retirement projections and stress tests.");
        out.put("auth", "Bearer SERVICE_TOKEN");
        out.put("depends_on", Map.of("advisor-tools MCP server", mcp.url()));
        out.put("endpoints", Map.of("invoke", "/invoke", "clients", "/v1/clients", "assumptions", "/v1/assumptions",
                "docs", "/docs", "openapi", "/openapi.json"));
        out.put("skills", skills.describe());
        return out;
    }
}
