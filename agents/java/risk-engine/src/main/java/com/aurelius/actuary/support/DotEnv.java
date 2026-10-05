package com.aurelius.actuary.support;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Reads .env files (KEY=VALUE lines) so the Actuary shares aurelius\.env with every other agent.
 *
 * Precedence (highest first): real environment variables > risk-engine\.env > aurelius\.env.
 * Spring applies the first one itself; this class merges the two files (agent file wins).
 */
public final class DotEnv {
    private DotEnv() {}

    /** Parse one file. Supports comments, blank lines, "export ", quotes and trailing "   # comment". */
    public static Map<String, String> parse(List<String> lines) {
        Map<String, String> out = new LinkedHashMap<>();
        for (String raw : lines) {
            String line = raw.strip();
            if (line.isEmpty() || line.startsWith("#")) continue;
            if (line.startsWith("export ")) line = line.substring(7).strip();
            int eq = line.indexOf('=');
            if (eq <= 0) continue;
            String key = line.substring(0, eq).strip();
            String value = line.substring(eq + 1).strip();
            if (value.length() >= 2 && (value.startsWith("\"") && value.endsWith("\"")
                    || value.startsWith("'") && value.endsWith("'"))) {
                value = value.substring(1, value.length() - 1);
            } else {
                int hash = value.indexOf(" #");
                if (hash < 0) hash = value.indexOf("\t#");
                if (hash >= 0) value = value.substring(0, hash).strip();
            }
            out.put(key, value);
        }
        return out;
    }

    /**
     * Load agentDir\.env and the first .env found in a parent folder (aurelius\.env).
     * Returns the merged map; the agent's own file wins.
     */
    public static Map<String, String> load(Path agentDir) {
        Map<String, String> merged = new LinkedHashMap<>();
        Path dir = agentDir.toAbsolutePath().normalize().getParent();
        for (int i = 0; i < 5 && dir != null; i++, dir = dir.getParent()) {
            Path candidate = dir.resolve(".env");
            if (Files.isRegularFile(candidate)) {
                merged.putAll(read(candidate));
                break;
            }
        }
        Path own = agentDir.resolve(".env");
        if (Files.isRegularFile(own)) merged.putAll(read(own));
        return merged;
    }

    private static Map<String, String> read(Path file) {
        try {
            return parse(Files.readAllLines(file));
        } catch (IOException e) {
            throw new IllegalStateException("Cannot read " + file + ": " + e.getMessage(), e);
        }
    }
}
