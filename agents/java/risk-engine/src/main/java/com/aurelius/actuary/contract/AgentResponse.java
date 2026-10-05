package com.aurelius.actuary.contract;

import java.util.Map;

/** The reply envelope. A skill error is still HTTP 200 with status "error" (same as every agent). */
public record AgentResponse(String agent, String status, Object output, String error) {
    public static final String AGENT = "actuary";

    public static AgentResponse ok(Object output) {
        return new AgentResponse(AGENT, "ok", output, null);
    }

    public static AgentResponse fail(String error) {
        return new AgentResponse(AGENT, "error", Map.of(), error);
    }
}
