/**
 * Herald HTTP API (Express 5).
 *
 * Endpoints
 *   GET  /docs                     Swagger UI
 *   GET  /openapi.json             the OpenAPI 3.1 document behind /docs
 *   GET  /health                   liveness (no auth)
 *   GET  /.well-known/agent.json   agent card (no auth)
 *   POST /invoke                   the agent contract (service token)
 *   GET  /v1/rules                 compliance rules (service token)
 */
import { randomUUID } from "node:crypto";

import express, { type ErrorRequestHandler, type Express } from "express";
import swaggerUi from "swagger-ui-express";
import { z } from "zod";

import type { AuditLog } from "./audit.js";
import { requireService } from "./auth.js";
import { listRules } from "./compose/compliance.js";
import { type Composer, SkillError } from "./compose/composer.js";
import { type Config, VERSION } from "./config.js";
import { AgentRequest, describeZodError, fail, ok } from "./contract.js";
import { getLogger } from "./logger.js";
import { buildOpenApi } from "./openapi.js";
import { SKILLS } from "./skills/index.js";

const log = getLogger("herald.api");

export interface AppDeps {
  config: Config;
  composer: Composer;
  audit: AuditLog;
}

interface AuditableOutput {
  body?: string;
  revised_text?: string;
  intent?: string;
  drafted_by?: string;
  compliance?: { fixes: string[] };
  warnings?: string[];
}

export function createApp({ config, composer, audit }: AppDeps): Express {
  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "64kb" }));

  app.use((req, res, next) => {
    const traceId = req.get("x-trace-id") ?? randomUUID().replaceAll("-", "");
    res.locals["traceId"] = traceId;
    res.set({ "X-Trace-Id": traceId, "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store" });
    next();
  });

  const service = requireService(config);

  // ------------------------------------------------------------ docs
  const openapi = buildOpenApi(`http://${config.host}:${config.port}`);
  app.get("/openapi.json", (_req, res) => { res.json(openapi); });
  app.use("/docs", swaggerUi.serve, swaggerUi.setup(openapi, {
    customSiteTitle: "Herald (client-comms) API",
    swaggerOptions: { persistAuthorization: true, displayRequestDuration: true },
  }));

  // ------------------------------------------------------------ public
  app.get("/health", (_req, res) => {
    res.json({ status: "ok", agent: "herald", version: VERSION, mode: composer.mode, liaison_url: config.liaisonUrl });
  });

  app.get("/.well-known/agent.json", (_req, res) => {
    res.json({
      name: "herald", codename: "Herald", folder: "client-comms", language: "TypeScript (Node.js)", version: VERSION,
      description: "Drafts and compliance-checks client emails. Never sends; a human approves.",
      auth: "Bearer SERVICE_TOKEN",
      depends_on: { liaison: config.liaisonUrl },
      endpoints: { invoke: "/invoke", rules: "/v1/rules", docs: "/docs", openapi: "/openapi.json" },
      skills: Object.fromEntries(Object.entries(SKILLS).map(([name, s]) => [name, {
        description: s.description, input_schema: z.toJSONSchema(s.input, { io: "input" }),
      }])),
    });
  });

  // ------------------------------------------------------------ protected
  app.get("/v1/rules", service, (_req, res) => { res.json(listRules()); });

  app.post("/invoke", service, async (req, res) => {
    const start = performance.now();
    const parsed = AgentRequest.safeParse(req.body);
    if (!parsed.success) {
      res.status(422).json({ detail: describeZodError(parsed.error) });
      return;
    }
    const { skill, input, context } = parsed.data;
    const def = SKILLS[skill];
    if (!def) {
      res.json(fail(`unknown skill ${skill}`));
      return;
    }

    const raw: Record<string, unknown> = { ...input };
    if (raw["client_id"] === undefined && context.client_id) raw["client_id"] = context.client_id;
    const params = def.input.safeParse(raw);
    if (!params.success) {
      res.json(fail(describeZodError(params.error)));
      return;
    }

    try {
      const output = (await def.run(params.data, context, { composer })) as AuditableOutput;
      const clientId = String((params.data as { client_id?: string }).client_id ?? "");
      const entry = {
        trace_id: context.trace_id, user_id: context.user_id, skill, client_id: clientId,
        fixes: output.compliance?.fixes ?? [], warnings: output.warnings?.length ?? 0,
        body: output.body ?? output.revised_text ?? "",
        ...(output.intent ? { intent: output.intent } : {}),
        ...(output.drafted_by ? { drafted_by: output.drafted_by } : {}),
      };
      audit.record(entry);
      log.info(`invoke skill=${skill} client=${clientId} fixes=${entry.fixes.length} ` +
               `ms=${Math.round(performance.now() - start)} trace=${context.trace_id}`);
      res.json(ok(output));
    } catch (err: unknown) {
      if (err instanceof SkillError) {
        res.json(fail(err.message));
        return;
      }
      throw err;
    }
  });

  // ------------------------------------------------------------ errors
  app.use((_req, res) => { res.status(404).json({ detail: "Not found" }); });

  const onError: ErrorRequestHandler = (err: unknown, _req, res, _next) => {
    const e = err as { type?: string; name?: string; message?: string };
    if (e.type === "entity.parse.failed") { res.status(422).json({ detail: "Body is not valid JSON" }); return; }
    if (e.type === "entity.too.large") { res.status(413).json({ detail: "Body too large" }); return; }
    const traceId = String(res.locals["traceId"] ?? "unknown");
    log.error(`unhandled_error trace=${traceId} error=${e.name}: ${e.message}`);
    res.status(500).json({ detail: "Internal error", trace_id: traceId });
  };
  app.use(onError);

  return app;
}
