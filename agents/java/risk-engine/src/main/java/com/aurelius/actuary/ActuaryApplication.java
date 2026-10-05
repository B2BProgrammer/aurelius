package com.aurelius.actuary;

import com.aurelius.actuary.support.Checks;
import com.aurelius.actuary.support.DotEnv;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/**
 * ENTRY POINT of the Actuary (risk-engine).
 *
 * Run from the risk-engine folder:
 *     mvn spring-boot:run                          compile + start (development)
 *     mvn package; java -jar target\actuary.jar    build the runnable jar, then start it
 *
 * What starts:
 *     main() -> reads aurelius\.env -> fail-closed token check -> Spring Boot
 *       config/AppConfig           builds the objects (MCP client, profiles, service, skills, filters)
 *       web/*Controller            the HTTP endpoints
 *       planning/MonteCarlo        the retirement simulation (read this one!)
 *       risk/RiskScorer, StressTester
 *       mcp/McpClient              talks to the advisor-tools MCP server for portfolios
 */
@SpringBootApplication
public class ActuaryApplication {

    public static final String VERSION = "0.1.0";

    public static void main(String[] args) {
        Map<String, String> dotenv = DotEnv.load(Path.of(""));
        String token = System.getenv("SERVICE_TOKEN") != null ? System.getenv("SERVICE_TOKEN") : dotenv.get("SERVICE_TOKEN");
        try {
            Checks.serviceToken(token);                       // fail closed, before anything starts
        } catch (IllegalStateException e) {
            System.err.println("ERROR: " + e.getMessage());
            System.exit(1);
        }
        SpringApplication app = new SpringApplication(ActuaryApplication.class);
        app.setDefaultProperties(new HashMap<String, Object>(dotenv));   // real env vars still win
        app.run(args);
    }
}
