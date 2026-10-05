package com.aurelius.actuary.web;

import com.aurelius.actuary.support.NotFoundException;
import com.aurelius.actuary.support.Checks;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.ErrorResponse;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Turns exceptions into the same {"detail": ...} errors the other agents return.
 * Rule: never send a stack trace or internal message to the caller; log it with the trace id.
 */
@RestControllerAdvice
public class ApiErrorHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiErrorHandler.class);

    /** Not JSON, or the contract's own checks failed (e.g. no context). */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, Object>> unreadable(HttpMessageNotReadableException e) {
        return detail(422, "invalid request: " + Checks.rootMessage(e));
    }

    @ExceptionHandler(NotFoundException.class)
    public ResponseEntity<Map<String, Object>> notFound(NotFoundException e) {
        return detail(404, e.getMessage());
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> badArgument(IllegalArgumentException e) {
        return detail(422, e.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> other(Exception e, HttpServletRequest request) {
        if (e instanceof ErrorResponse er) {        // Spring's own: 404 unknown path, 405 wrong method, 415...
            int status = er.getStatusCode().value();
            return detail(status, status == 404 ? "Not found" : e.getMessage());
        }
        Object trace = request.getAttribute(TraceFilter.TRACE_ATTR);
        log.error("unhandled_error trace={} error={}", trace, e.toString(), e);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("detail", "Internal error");
        body.put("trace_id", trace);
        return ResponseEntity.status(500).body(body);
    }

    private static ResponseEntity<Map<String, Object>> detail(int status, String message) {
        return ResponseEntity.status(status).body(Map.of("detail", message));
    }
}
