package com.aurelius.notary.web;

import com.aurelius.notary.kyc.KycRules;
import com.aurelius.notary.kyc.KycService;
import com.aurelius.notary.support.Checks;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** Plain REST views for exploring (handy in Swagger and later in the Atrium UI). */
@RestController
@Tag(name = "browse", description = "REST views for exploring KYC files")
@SecurityRequirement(name = "serviceToken")
public class BrowseController {

    private final KycService service;

    public BrowseController(KycService service) {
        this.service = service;
    }

    @Operation(summary = "All households with their KYC status")
    @GetMapping("/v1/clients")
    public List<Map<String, Object>> clients() {
        return service.clientSummaries();
    }

    @Operation(summary = "KYC report for one household (same as check_kyc)")
    @GetMapping("/v1/clients/{clientId}/kyc")
    public KycService.KycReport kyc(@Parameter(example = "patel-001") @PathVariable("clientId") String clientId) {
        return service.checkKyc(Checks.id("client_id", clientId));   // NotFound -> 404, bad id -> 422
    }

    @Operation(summary = "The KYC/AML rule book")
    @GetMapping("/v1/rules")
    public List<KycRules.RuleInfo> rules() {
        return KycRules.RULES;
    }
}
