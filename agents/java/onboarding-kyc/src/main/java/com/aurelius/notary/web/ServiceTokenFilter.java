package com.aurelius.notary.web;

import com.aurelius.notary.support.Checks;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;

/**
 * Only other agents (holding SERVICE_TOKEN) may call /invoke and /v1/*.
 *
 * LEARN: Same check as auth.py / auth.ts, in Java: read "Authorization: Bearer X",
 * compare in CONSTANT time (Checks.tokenEquals -> MessageDigest.isEqual),
 * answer 401 + WWW-Authenticate when it's missing or wrong.
 */
public class ServiceTokenFilter implements Filter {

    private final String expected;

    public ServiceTokenFilter(String expected) {
        this.expected = expected == null ? "" : expected;
    }

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) req;
        HttpServletResponse response = (HttpServletResponse) res;
        String header = request.getHeader("Authorization");
        String supplied = header != null && header.regionMatches(true, 0, "Bearer ", 0, 7) ? header.substring(7) : null;
        if (expected.isEmpty() || !Checks.tokenEquals(expected, supplied)) {
            response.setHeader("WWW-Authenticate", "Bearer");
            JsonReply.send(response, 401, "Invalid or missing service token");
            return;
        }
        chain.doFilter(req, res);
    }
}
