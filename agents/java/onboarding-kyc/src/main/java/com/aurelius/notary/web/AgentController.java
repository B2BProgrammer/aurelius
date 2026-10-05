package com.aurelius.notary.web;

import com.aurelius.notary.contract.AgentRequest;
import com.aurelius.notary.contract.AgentResponse;
import com.aurelius.notary.kyc.NotFoundException;
import com.aurelius.notary.skills.SkillRegistry;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * POST /invoke: the agent contract (what the Conductor calls).
 *
 * Errors in the SKILL (bad input, unknown client) -> HTTP 200, status "error".
 * Errors in the CONTRACT (not JSON, no context)    -> HTTP 422 (ApiErrorHandler).
 */
@RestController
@Tag(name = "agent", description = "The agent contract (what the Conductor calls)")
public class AgentController {

    private static final Logger log = LoggerFactory.getLogger(AgentController.class);
    private final SkillRegistry skills;

    public AgentController(SkillRegistry skills) {
        this.skills = skills;
    }

    @Operation(summary = "Run a skill (the agent contract)",
            description = "Skills: check_kyc, list_documents, screen_name, record_document. "
                    + "Pick one from the Examples list.",
            security = @SecurityRequirement(name = "serviceToken"))
    @PostMapping("/invoke")
    public AgentResponse invoke(@RequestBody AgentRequest request) {
        long start = System.nanoTime();
        String trace = request.context().traceId();
        Object rawClient = request.input().get("client_id");
        String clientId = String.valueOf(rawClient != null ? rawClient
                : request.context().clientId() != null ? request.context().clientId() : "");
        try {
            Object output = skills.invoke(request.skill(), request.input(), request.context());
            log.info("invoke skill={} client={} ms={} trace={}", request.skill(), clientId,
                    (System.nanoTime() - start) / 1_000_000, trace);
            return AgentResponse.ok(output);
        } catch (SkillRegistry.UnknownSkillException | IllegalArgumentException | NotFoundException e) {
            log.info("invoke_failed skill={} client={} reason={} trace={}", request.skill(), clientId, e.getMessage(), trace);
            return AgentResponse.fail(e.getMessage());
        }
    }
}
