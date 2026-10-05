package com.aurelius.actuary.support;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

/**
 * ONE place that decides how JSON looks, used by the web layer, the store and the tests.
 *
 * LEARN: Java fields are camelCase (clientId); every other agent speaks
 * snake_case (client_id). SNAKE_CASE translates automatically, so the Java
 * code stays idiomatic and the JSON matches the swarm's contract.
 */
public final class Json {
    private Json() {}

    /** For the API: nulls are written (the contract has "error": null). */
    public static ObjectMapper newMapper() {
        return builder().build();
    }

    /** For the data file: skip nulls to keep it readable. */
    public static ObjectMapper newFileMapper() {
        return builder()
                .defaultPropertyInclusion(JsonInclude.Value.construct(JsonInclude.Include.NON_NULL, JsonInclude.Include.NON_NULL))
                .enable(SerializationFeature.INDENT_OUTPUT)
                .build();
    }

    private static JsonMapper.Builder builder() {
        return JsonMapper.builder()
                .propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
                .addModule(new JavaTimeModule())                                  // LocalDate <-> "2026-10-03"
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
                .enable(MapperFeature.ACCEPT_CASE_INSENSITIVE_ENUMS)                // "government_id" works too
                .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
    }
}
