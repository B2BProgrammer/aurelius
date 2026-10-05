/**
 * OpenAPI 3.1 document for the Swagger page at /docs, built from the SAME
 * Zod schemas and skills table the code uses (see the Liaison for the idea).
 */
import { z } from "zod";

import { VERSION } from "./config.js";
import { InvokeContext } from "./contract.js";
import { SKILLS } from "./skills/index.js";

type JsonSchema = Record<string, unknown>;

function toSchema(schema: z.ZodType): JsonSchema {
  const { $schema: _drop, ...rest } = z.toJSONSchema(schema, { io: "input" }) as JsonSchema;
  return rest;
}

const ref = (name: string): JsonSchema => ({ $ref: `#/components/schemas/${name}` });

export function buildOpenApi(serverUrl: string): JsonSchema {
  const skillNames = Object.keys(SKILLS);
  const inputSchemas: Record<string, JsonSchema> = {};
  const examples: Record<string, JsonSchema> = {};
  for (const [name, s] of Object.entries(SKILLS)) {
    inputSchemas[`${name}_input`] = { ...toSchema(s.input), description: s.description };
    for (const [label, input] of Object.entries(s.examples)) {
      examples[label.replace(/[^A-Za-z0-9_]+/g, "_").replace(/_$/, "")] = {
        summary: label,
        value: { skill: name, input, context: { trace_id: `swagger-${name}`, user_id: "dev-advisor" } },
      };
    }
  }

  const unauthorized = {
    description: "Missing or wrong SERVICE_TOKEN",
    content: { "application/json": { schema: ref("Detail") } },
  };

  return {
    openapi: "3.1.0",
    info: {
      title: "Aurelius Herald (client-comms)",
      version: VERSION,
      description:
        "Client-communication agent of the Aurelius swarm (TypeScript / Express 5).\n\n" +
        "Drafts personalized client emails (household details come from the **Liaison** on :8102) and " +
        "checks emails for compliance. **It never sends anything**: every result has `requires_approval: true`.\n\n" +
        "**How to try it:** click **Authorize**, paste the `SERVICE_TOKEN` from `aurelius\\.env`, " +
        "then **POST /invoke** → *Try it out* → pick an example from the **Examples** dropdown.",
    },
    servers: [{ url: serverUrl }],
    tags: [
      { name: "public", description: "No token needed" },
      { name: "agent", description: "The agent contract (what the Conductor calls)" },
      { name: "browse", description: "Read-only helpers" },
    ],
    components: {
      securitySchemes: {
        serviceToken: { type: "http", scheme: "bearer", description: "SERVICE_TOKEN from aurelius\\.env" },
      },
      schemas: {
        InvokeContext: toSchema(InvokeContext),
        AgentRequest: {
          type: "object",
          required: ["skill", "context"],
          properties: {
            skill: { type: "string", enum: skillNames },
            input: { oneOf: Object.keys(inputSchemas).map(ref), description: "Depends on the skill" },
            context: ref("InvokeContext"),
          },
        },
        AgentResponse: {
          type: "object",
          required: ["agent", "status", "output", "error"],
          properties: {
            agent: { const: "herald" },
            status: { type: "string", enum: ["ok", "error"] },
            output: { type: "object", description: "The skill's result (empty on error)" },
            error: { type: ["string", "null"] },
          },
        },
        Detail: { type: "object", properties: { detail: { type: "string" } } },
        ...inputSchemas,
      },
    },
    paths: {
      "/health": {
        get: {
          tags: ["public"], summary: "Liveness check",
          responses: { 200: { description: "OK", content: { "application/json": {
            example: { status: "ok", agent: "herald", version: VERSION, mode: "template", liaison_url: "http://127.0.0.1:8102" } } } } },
        },
      },
      "/.well-known/agent.json": {
        get: { tags: ["public"], summary: "Agent card: skills and their input schemas",
               responses: { 200: { description: "Agent card" } } },
      },
      "/invoke": {
        post: {
          tags: ["agent"],
          summary: "Run a skill (the agent contract)",
          description: `Skills: ${skillNames.map((n) => `\`${n}\``).join(", ")}. Pick one from the Examples list.`,
          security: [{ serviceToken: [] }],
          requestBody: { required: true, content: { "application/json": { schema: ref("AgentRequest"), examples } } },
          responses: {
            200: { description: "Envelope with status ok or error (still HTTP 200 on a skill error)",
                   content: { "application/json": { schema: ref("AgentResponse"), examples: { error: {
                     value: { agent: "herald", status: "error", output: {}, error: "No household with id 'nobody-1'" } } } } } },
            401: unauthorized,
            422: { description: "Body isn't valid JSON or breaks the contract (e.g. missing context)",
                   content: { "application/json": { schema: ref("Detail") } } },
          },
        },
      },
      "/v1/rules": {
        get: {
          tags: ["browse"], summary: "The compliance rules every email goes through", security: [{ serviceToken: [] }],
          responses: { 200: { description: "Rule ids, actions and descriptions" }, 401: unauthorized },
        },
      },
    },
  };
}
