/**
 * OpenAPI 3.1 document for the Swagger page at /docs.
 *
 * LEARN: FastAPI writes this document automatically from your Python types.
 * Express doesn't, so we build it here, from the SAME Zod schemas and the
 * SAME skills table the code uses. Change a schema and both the validation
 * and the Swagger page change together; they can't drift apart.
 */
import { z } from "zod";

import { VERSION } from "./config.js";
import { InvokeContext } from "./contract.js";
import { SKILLS } from "./skills/index.js";

type JsonSchema = Record<string, unknown>;

/** Zod -> JSON Schema (draft 2020-12, which OpenAPI 3.1 uses), minus the $schema header. */
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
    const schemaName = `${name}_input`;
    inputSchemas[schemaName] = { ...toSchema(s.input), description: s.description };
    examples[name] = {
      summary: `${name}${s.writes ? "  (writes)" : ""}`,
      description: s.description,
      value: { skill: name, input: s.example, context: { trace_id: `swagger-${name}`, user_id: "dev-advisor" } },
    };
  }

  const errorEnvelope = {
    description: "Skill failed (bad input, unknown household...). Note: still HTTP 200, status=error.",
    value: { agent: "liaison", status: "error", output: {}, error: "No household with id 'nobody-1'" },
  };
  const unauthorized = {
    description: "Missing or wrong SERVICE_TOKEN",
    content: { "application/json": { schema: ref("Detail") } },
  };

  return {
    openapi: "3.1.0",
    info: {
      title: "Aurelius Liaison (crm-sync)",
      version: VERSION,
      description:
        "CRM agent of the Aurelius swarm (TypeScript / Express 5).\n\n" +
        "**How to try it:** click **Authorize**, paste the `SERVICE_TOKEN` from `aurelius\\.env`, " +
        "then open **POST /invoke** → *Try it out* → pick an example from the **Examples** dropdown.\n\n" +
        "Writes are idempotent: send the same `log_note` twice with the same `trace_id` and you get the " +
        "same `note_id` back with `duplicate: true`.",
    },
    servers: [{ url: serverUrl }],
    tags: [
      { name: "public", description: "No token needed" },
      { name: "agent", description: "The agent contract (what the Conductor calls)" },
      { name: "browse", description: "REST views for exploring the CRM" },
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
            agent: { const: "liaison" },
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
            example: { status: "ok", agent: "liaison", version: VERSION, households: 3 } } } } },
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
            200: { description: "Envelope with status ok or error",
                   content: { "application/json": { schema: ref("AgentResponse"), examples: { error: errorEnvelope } } } },
            401: unauthorized,
            422: { description: "Body isn't valid JSON or breaks the contract (e.g. missing context)",
                   content: { "application/json": { schema: ref("Detail") } } },
          },
        },
      },
      "/v1/households": {
        get: {
          tags: ["browse"], summary: "List households", security: [{ serviceToken: [] }],
          responses: { 200: { description: "client_id + household name" }, 401: unauthorized },
        },
      },
      "/v1/households/{clientId}": {
        get: {
          tags: ["browse"], summary: "One household (same as get_household)", security: [{ serviceToken: [] }],
          parameters: [{ name: "clientId", in: "path", required: true, schema: { type: "string" }, example: "patel-001" }],
          responses: { 200: { description: "Household view (contacts masked)" }, 401: unauthorized,
                       404: { description: "Unknown household" }, 422: { description: "Invalid client_id" } },
        },
      },
    },
  };
}
