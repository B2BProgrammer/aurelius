package com.aurelius.notary;

import com.aurelius.notary.contract.InvokeContext;
import com.aurelius.notary.kyc.KycRules;
import com.aurelius.notary.kyc.KycService;
import com.aurelius.notary.screening.NameScreener;
import com.aurelius.notary.skills.SkillRegistry;
import com.aurelius.notary.store.AuditLog;
import com.aurelius.notary.store.KycStore;
import com.aurelius.notary.support.Json;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

/**
 * Builds the whole agent WITHOUT Spring: a temp copy of the data, a fixed clock.
 *
 * LEARN: because KycService, KycStore etc. are plain classes, tests can create
 * them with `new` in milliseconds. Only ApiIntegrationTest starts Spring.
 */
public final class TestSupport {
    private TestSupport() {}

    public static final Clock FIXED = Clock.fixed(Instant.parse("2026-10-03T12:00:00Z"), ZoneOffset.UTC);
    public static final InvokeContext CTX = new InvokeContext("test-trace", "dev-advisor", null);

    public record Agent(Path dir, KycStore store, NameScreener screener, KycService service, SkillRegistry skills,
                        AuditLog audit, ObjectMapper mapper) {}

    public static Agent newAgent() throws IOException {
        Path dir = Files.createTempDirectory("notary-test-");
        ObjectMapper mapper = Json.newMapper();
        KycStore store = new KycStore(dir.resolve("kyc.json"), Path.of("data", "kyc.seed.json"), Json.newFileMapper());
        NameScreener screener = NameScreener.load(Path.of("data", "watchlist.json"), mapper, 0.88);
        AuditLog audit = new AuditLog(dir.resolve("audit.jsonl"), mapper);
        KycService service = new KycService(store, screener, audit, FIXED, KycRules.Settings.DEFAULT);
        return new Agent(dir, store, screener, service, new SkillRegistry(service, mapper), audit, mapper);
    }
}
