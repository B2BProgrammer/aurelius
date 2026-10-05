package com.aurelius.notary.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Everything under "notary:" in application.yml, as one typed, immutable record.
 *
 * LEARN: instead of reading strings with @Value all over the code, Spring
 * binds the whole block once (notary.data-file -> dataFile) and checks the types.
 */
@ConfigurationProperties(prefix = "notary")
public record NotaryProperties(
        String serviceToken,
        String dataFile,
        String seedFile,
        String watchlistFile,
        String auditFile,
        int expiringWindowDays,
        double matchThreshold) {
}
