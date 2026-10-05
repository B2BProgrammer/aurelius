package com.aurelius.actuary.support;

/** Unknown client: a skill error ("status": "error"), or HTTP 404 on the browse endpoints. */
public class NotFoundException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    public NotFoundException(String message) {
        super(message);
    }
}
