package com.aurelius.actuary.config;

import com.aurelius.actuary.ActuaryApplication;
import com.aurelius.actuary.mcp.McpClient;
import com.aurelius.actuary.mcp.PortfolioSource;
import com.aurelius.actuary.planning.ActuaryService;
import com.aurelius.actuary.planning.Assumptions;
import com.aurelius.actuary.planning.Profiles;
import com.aurelius.actuary.skills.SkillRegistry;
import com.aurelius.actuary.support.Json;
import com.aurelius.actuary.web.ServiceTokenFilter;
import com.aurelius.actuary.web.TraceFilter;
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
import java.time.Duration;

/** Wiring: builds every object once (dependency injection), same pattern as the Notary. */
@Configuration
@EnableConfigurationProperties(ActuaryProperties.class)
public class AppConfig {

    private static final Logger log = LoggerFactory.getLogger(AppConfig.class);

    @Bean
    @Primary
    public ObjectMapper objectMapper() {
        return Json.newMapper();
    }

    @Bean
    public Clock clock() {
        return Clock.systemDefaultZone();
    }

    /** The MCP client uses the SAME service token as every agent (the MCP server checks it). */
    @Bean
    public McpClient mcpClient(ActuaryProperties p, ObjectMapper mapper) {
        return new McpClient(p.mcpUrl(), p.serviceToken(), Duration.ofMillis(p.mcpTimeoutMs()), mapper);
    }

    @Bean
    public PortfolioSource portfolioSource(McpClient mcp, ActuaryProperties p, ObjectMapper mapper) throws IOException {
        return new PortfolioSource(mcp, PortfolioSource.loadSnapshot(Path.of(p.snapshotFile()), mapper));
    }

    @Bean
    public Profiles profiles(ActuaryProperties p, ObjectMapper mapper) throws IOException {
        return Profiles.load(Path.of(p.profilesFile()), mapper);
    }

    @Bean
    public ActuaryService actuaryService(Profiles profiles, PortfolioSource portfolios, Clock clock, ActuaryProperties p) {
        return new ActuaryService(profiles, portfolios, Assumptions.DEFAULT, clock,
                new ActuaryService.Settings(p.defaultSimulations(), p.maxSimulations()));
    }

    @Bean
    public SkillRegistry skillRegistry(ActuaryService service, ObjectMapper mapper) {
        return new SkillRegistry(service, mapper);
    }

    @Bean
    public FilterRegistrationBean<TraceFilter> traceFilter() {
        FilterRegistrationBean<TraceFilter> reg = new FilterRegistrationBean<>(new TraceFilter());
        reg.addUrlPatterns("/*");
        reg.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return reg;
    }

    @Bean
    public FilterRegistrationBean<ServiceTokenFilter> serviceTokenFilter(ActuaryProperties p) {
        FilterRegistrationBean<ServiceTokenFilter> reg = new FilterRegistrationBean<>(new ServiceTokenFilter(p.serviceToken()));
        reg.addUrlPatterns("/invoke", "/v1/*");
        reg.setOrder(Ordered.HIGHEST_PRECEDENCE + 10);
        return reg;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void ready(ApplicationReadyEvent event) {
        String host = event.getApplicationContext().getEnvironment().getProperty("server.address", "127.0.0.1");
        String port = event.getApplicationContext().getEnvironment().getProperty("local.server.port", "8202");
        McpClient mcp = event.getApplicationContext().getBean(McpClient.class);
        log.info("actuary_started version={} port={} mcp={}", ActuaryApplication.VERSION, port, mcp.url());
        System.out.println();
        System.out.println("Actuary (risk-engine) on http://" + host + ":" + port);
        System.out.println("Swagger UI:            http://" + host + ":" + port + "/docs");
        System.out.println("Portfolios from MCP:   " + mcp.url() + "   (snapshot file if it's down)");
        System.out.println();
    }
}
