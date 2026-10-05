package com.aurelius.notary.contract;

import com.aurelius.notary.support.Checks;

import java.util.Map;

/**
 * POST /invoke body: { skill, input, context }.
 *
 * LEARN: The checks live in the record's "compact constructor". Jackson calls
 * that constructor while reading the JSON, so an invalid request can't even
 * become an object. The web layer turns the failure into HTTP 422.
 */
public record AgentRequest(String skill, Map<String, Object> input, InvokeContext context) {
    public AgentRequest {
        skill = Checks.text("skill", skill, 1, 64);
        input = input == null ? Map.of() : input;
        if (context == null) throw new IllegalArgumentException("context is required");
    }
}
