package com.aurelius.actuary.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Everything under "actuary:" in application.yml, as one typed record. */
@ConfigurationProperties(prefix = "actuary")
public record ActuaryProperties(
        String serviceToken,
        String profilesFile,
        String snapshotFile,
        String mcpUrl,
        int mcpTimeoutMs,
        int defaultSimulations,
        int maxSimulations) {
}
