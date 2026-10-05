package com.aurelius.notary;

import com.aurelius.notary.support.Checks;
import com.aurelius.notary.support.DotEnv;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/**
 * ENTRY POINT of the Notary (onboarding-kyc).
 *
 * Run from the onboarding-kyc folder:
 *     mvn spring-boot:run                    compile + start (development)
 *     mvn package; java -jar target\notary.jar   build the runnable jar, then start it
 *
 * What starts:
 *     main() -> reads aurelius\.env -> fail-closed token check -> Spring Boot
 *       config/AppConfig     builds the objects (store, screener, service, skills, filters)
 *       web/*Controller      the HTTP endpoints
 *       kyc/KycRules         the rule book (pure Java, read this one!)
 *
 * LEARN: @SpringBootApplication = "scan this package for @Configuration and
 * @RestController classes, and auto-configure Tomcat, Jackson and Swagger".
 */
@SpringBootApplication
public class NotaryApplication {

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
        SpringApplication app = new SpringApplication(NotaryApplication.class);
        app.setDefaultProperties(new HashMap<String, Object>(dotenv));   // real env vars still win
        app.run(args);
    }
}
