package com.aurelius.actuary.web;

import com.aurelius.actuary.planning.ActuaryService;
import com.aurelius.actuary.planning.Assumptions;
import com.aurelius.actuary.risk.RiskScorer;
import com.aurelius.actuary.risk.StressTester;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** Read-only views: who we have profiles for, and the assumptions behind every number. */
@RestController
@Tag(name = "browse", description = "Profiles and the assumptions behind the math")
@SecurityRequirement(name = "serviceToken")
public class BrowseController {

    private final ActuaryService service;

    public BrowseController(ActuaryService service) {
        this.service = service;
    }

    @Operation(summary = "Households with planning profiles")
    @GetMapping("/v1/clients")
    public List<Map<String, Object>> clients() {
        return service.clients();
    }

    @Operation(summary = "Capital market assumptions, risk bands and stress scenarios")
    @GetMapping("/v1/assumptions")
    public Map<String, Object> assumptions() {
        Assumptions a = service.assumptions();
        return Map.of(
                "capital_market_assumptions", a,
                "note", "Real (after-inflation) yearly returns and volatility. Illustrative, set for this learning project.",
                "risk_bands", RiskScorer.BANDS,
                "stress_scenarios", StressTester.SCENARIOS);
    }
}
