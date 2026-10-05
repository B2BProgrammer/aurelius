package com.aurelius.notary.config;

import com.aurelius.notary.NotaryApplication;
import com.aurelius.notary.skills.SkillRegistry;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.swagger.v3.core.jackson.ModelResolver;
import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.PathItem;
import io.swagger.v3.oas.models.examples.Example;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.media.MediaType;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springdoc.core.customizers.OpenApiCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Swagger / OpenAPI.
 *
 * LEARN: springdoc reads the controllers (@GetMapping, @Operation...) and
 * builds the OpenAPI document by itself, like FastAPI does in Python. We add:
 *   * the "serviceToken" bearer scheme -> the Authorize button
 *   * one example per skill in the /invoke dropdown, taken from SkillRegistry
 *     (the same table the code runs), so the examples can't go stale.
 * No "servers" entry: Swagger then calls whatever host you opened /docs on
 * (localhost or 127.0.0.1), which avoids cross-origin "Failed to fetch".
 */
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI notaryOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("Aurelius Notary (onboarding-kyc)")
                        .version(NotaryApplication.VERSION)
                        .description("KYC/AML agent of the Aurelius swarm (Java 21 / Spring Boot).\n\n"
                                + "**How to try it:** click **Authorize**, paste the `SERVICE_TOKEN` from `aurelius\\.env`, "
                                + "then **POST /invoke** → *Try it out* → pick an example from the **Examples** dropdown.\n\n"
                                + "Rules are plain code (no LLM): a KYC decision must be the same every time and explainable. "
                                + "The watchlist is a **fictional demo list**."))
                .components(new Components().addSecuritySchemes("serviceToken", new SecurityScheme()
                        .type(SecurityScheme.Type.HTTP).scheme("bearer")
                        .description("SERVICE_TOKEN from aurelius\\.env")));
    }

    /**
     * springdoc builds schemas with its own JSON mapper. Giving it OUR mapper makes the
     * Swagger schemas snake_case (trace_id), exactly like the real API.
     */
    @Bean
    public ModelResolver modelResolver(ObjectMapper objectMapper) {
        return new ModelResolver(objectMapper.copy());     // a copy: springdoc adds its own module to it
    }

    @Bean
    public OpenApiCustomizer skillExamples(SkillRegistry skills) {
        return openApi -> {
            PathItem invoke = openApi.getPaths() == null ? null : openApi.getPaths().get("/invoke");
            if (invoke == null || invoke.getPost() == null || invoke.getPost().getRequestBody() == null
                    || invoke.getPost().getRequestBody().getContent() == null) {
                return;
            }
            MediaType json = invoke.getPost().getRequestBody().getContent().get("application/json");
            if (json == null) return;
            Map<String, Example> examples = new LinkedHashMap<>();
            skills.all().forEach((name, skill) -> skill.examples().forEach((label, input) -> {
                Map<String, Object> body = new LinkedHashMap<>();
                body.put("skill", name);
                body.put("input", input);
                body.put("context", Map.of("trace_id", "swagger-" + name, "user_id", "dev-advisor"));
                examples.put(label.replaceAll("[^A-Za-z0-9_]+", "_").replaceAll("_$", ""),
                        new Example().summary(label + (skill.writes() ? "  (writes)" : "")).description(skill.description()).value(body));
            }));
            json.setExamples(examples);
        };
    }
}
