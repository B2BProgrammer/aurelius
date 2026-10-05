package com.aurelius.actuary.contract;

import com.aurelius.actuary.support.Checks;

/** Who is asking and which trace this belongs to. Same fields in every agent. */
public record InvokeContext(String traceId, String userId, String clientId) {
    public InvokeContext {
        traceId = Checks.text("context.trace_id", traceId, 1, 128);   // no control chars: no log injection
        userId = Checks.text("context.user_id", userId, 1, 128);
    }
}
