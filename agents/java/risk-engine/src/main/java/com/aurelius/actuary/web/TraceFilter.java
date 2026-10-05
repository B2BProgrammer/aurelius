package com.aurelius.actuary.web;

import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * First thing every request passes through (a servlet Filter = Express middleware).
 *  * trace id: reuse the caller's X-Trace-Id (so one id follows the request
 *    across agents) or make one; echo it back.
 *  * security headers: nosniff, no-store.
 *  * body limit: refuse bodies over 64 KB before anything parses them.
 */
public class TraceFilter implements Filter {

    public static final String TRACE_ATTR = "traceId";
    public static final long MAX_BODY_BYTES = 64 * 1024;
    private static final Pattern SAFE_TRACE = Pattern.compile("^[A-Za-z0-9_.:-]{1,128}$");

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) req;
        HttpServletResponse response = (HttpServletResponse) res;

        String trace = request.getHeader("X-Trace-Id");
        if (trace == null || !SAFE_TRACE.matcher(trace).matches()) {       // never echo unsafe text into headers/logs
            trace = UUID.randomUUID().toString().replace("-", "");
        }
        request.setAttribute(TRACE_ATTR, trace);
        response.setHeader("X-Trace-Id", trace);
        response.setHeader("X-Content-Type-Options", "nosniff");
        response.setHeader("Cache-Control", "no-store");

        if (request.getContentLengthLong() > MAX_BODY_BYTES) {
            JsonReply.send(response, 413, "Body too large");
            return;
        }
        chain.doFilter(req, res);
    }
}
