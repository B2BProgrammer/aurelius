package com.aurelius.notary.config;

import com.aurelius.notary.NotaryApplication;
import com.aurelius.notary.kyc.KycRules;
import com.aurelius.notary.kyc.KycService;
import com.aurelius.notary.screening.NameScreener;
import com.aurelius.notary.skills.SkillRegistry;
import com.aurelius.notary.store.AuditLog;
import com.aurelius.notary.store.KycStore;
import com.aurelius.notary.support.Json;
import com.aurelius.notary.web.ServiceTokenFilter;
import com.aurelius.notary.web.TraceFilter;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.context.event.EventListener;
import org.springframework.core.Ordered;

import java.io.IOException;
import java.nio.file.Path;
import java.time.Clock;

/**
 * Wiring: builds every object once and hands them to whoever needs them.
 *
 * LEARN: This is Dependency Injection. A @Bean method creates an object; Spring
 * passes beans into other @Bean methods and into controller constructors. The
 * business classes (KycService, KycStore...) don't know Spring exists, which
 * is why they're testable with plain `new`.
 */
@Configuration
@EnableConfigurationProperties(NotaryProperties.class)
public class AppConfig {

    private static final Logger log = LoggerFactory.getLogger(AppConfig.class);

    /** One JSON style for the whole API (snake_case, ISO dates). Replaces Spring's default mapper. */
    @Bean
    @Primary
    public ObjectMapper objectMapper() {
        return Json.newMapper();
    }

    /** Injected clock: tests replace it with a fixed date. */
    @Bean
    public Clock clock() {
        return Clock.systemDefaultZone();
    }

    @Bean
    public KycStore kycStore(NotaryProperties p) {
        return new KycStore(Path.of(p.dataFile()), Path.of(p.seedFile()), Json.newFileMapper());
    }

    @Bean
    public NameScreener nameScreener(NotaryProperties p, ObjectMapper mapper) throws IOException {
        return NameScreener.load(Path.of(p.watchlistFile()), mapper, p.matchThreshold());
    }

    @Bean
    public AuditLog auditLog(NotaryProperties p, ObjectMapper mapper) {
        return new AuditLog(Path.of(p.auditFile()), mapper);
    }

    @Bean
    public KycService kycService(KycStore store, NameScreener screener, AuditLog audit, Clock clock, NotaryProperties p) {
        return new KycService(store, screener, audit, clock, new KycRules.Settings(p.expiringWindowDays()));
    }

    @Bean
    public SkillRegistry skillRegistry(KycService service, ObjectMapper mapper) {
        return new SkillRegistry(service, mapper);
    }

    /** Runs first, on every path: trace id, security headers, body-size limit. */
    @Bean
    public FilterRegistrationBean<TraceFilter> traceFilter() {
        FilterRegistrationBean<TraceFilter> reg = new FilterRegistrationBean<>(new TraceFilter());
        reg.addUrlPatterns("/*");
        reg.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return reg;
    }

    /** Service token only on the agent endpoints. /health, /docs and the agent card stay public. */
    @Bean
    public FilterRegistrationBean<ServiceTokenFilter> serviceTokenFilter(NotaryProperties p) {
        FilterRegistrationBean<ServiceTokenFilter> reg = new FilterRegistrationBean<>(new ServiceTokenFilter(p.serviceToken()));
        reg.addUrlPatterns("/invoke", "/v1/*");
        reg.setOrder(Ordered.HIGHEST_PRECEDENCE + 10);
        return reg;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void ready(ApplicationReadyEvent event) {
        String host = event.getApplicationContext().getEnvironment().getProperty("server.address", "127.0.0.1");
        String port = event.getApplicationContext().getEnvironment().getProperty("local.server.port", "8201");
        KycService service = event.getApplicationContext().getBean(KycService.class);
        log.info("notary_started version={} port={} clients={}", NotaryApplication.VERSION, port, service.clientCount());
        System.out.println();
        System.out.println("Notary (onboarding-kyc) on http://" + host + ":" + port);
        System.out.println("Swagger UI:              http://" + host + ":" + port + "/docs");
        System.out.println();
    }
}
