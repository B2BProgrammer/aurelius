package com.aurelius.notary.web;

import com.aurelius.notary.NotaryApplication;
import com.aurelius.notary.kyc.KycService;
import com.aurelius.notary.screening.NameScreener;
import com.aurelius.notary.skills.SkillRegistry;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/** No token needed: liveness and the agent card (what the Conductor reads to know our skills). */
@RestController
@Tag(name = "public", description = "No token needed")
public class PublicController {

    private final KycService service;
    private final NameScreener screener;
    private final SkillRegistry skills;

    /** LEARN: constructor injection. Spring sees the parameters and passes the beans from AppConfig. */
    public PublicController(KycService service, NameScreener screener, SkillRegistry skills) {
        this.service = service;
        this.screener = screener;
        this.skills = skills;
    }

    @Operation(summary = "Liveness check")
    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("status", "ok");
        out.put("agent", "notary");
        out.put("version", NotaryApplication.VERSION);
        out.put("clients", service.clientCount());
        out.put("watchlist_entries", screener.size());
        return out;
    }

    @Operation(summary = "Agent card: skills and their input schemas")
    @GetMapping("/.well-known/agent.json")
    public Map<String, Object> agentCard() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("name", "notary");
        out.put("codename", "Notary");
        out.put("folder", "onboarding-kyc");
        out.put("language", "Java 21 (Spring Boot)");
        out.put("version", NotaryApplication.VERSION);
        out.put("description", "KYC/AML: document checks, watchlist screening, idempotent document records.");
        out.put("auth", "Bearer SERVICE_TOKEN");
        out.put("endpoints", Map.of("invoke", "/invoke", "clients", "/v1/clients", "rules", "/v1/rules",
                "docs", "/docs", "openapi", "/openapi.json"));
        out.put("skills", skills.describe());
        return out;
    }
}
