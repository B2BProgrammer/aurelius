package com.aurelius.notary.web;

import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;

/** Filters run before Spring MVC, so they write their small JSON error replies by hand. */
final class JsonReply {
    private JsonReply() {}

    static void send(HttpServletResponse response, int status, String detail) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");
        // detail is always one of our own constant messages: no user text, so no escaping needed
        response.getWriter().write("{\"detail\":\"" + detail + "\"}");
    }
}
