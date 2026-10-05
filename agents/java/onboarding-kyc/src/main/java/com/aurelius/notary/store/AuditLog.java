package com.aurelius.notary.store;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Audit trail: one JSON line per WRITE and per SCREENING.
 *
 * LEARN: AML rules expect firms to prove WHEN a person was screened and by WHOM.
 * We log trace, user, skill, ids and outcome. Names are logged as a SHA-256
 * fingerprint, so the log proves which name was checked without holding it.
 */
public class AuditLog {
    private final Path file;
    private final ObjectMapper mapper;

    public AuditLog(Path file, ObjectMapper mapper) {
        this.file = file;
        this.mapper = mapper;
        try {
            if (file.getParent() != null) Files.createDirectories(file.getParent());
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    public synchronized void record(Map<String, Object> entry) {
        Map<String, Object> line = new LinkedHashMap<>();
        line.put("ts", Instant.now().toString());
        line.putAll(entry);
        try {
            Files.writeString(file, mapper.writeValueAsString(line) + System.lineSeparator(),
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(e);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    public Path file() {
        return file;
    }
}
