/**
 * Liaison HTTP API (Express 5).
 *
 * Endpoints
 *   GET  /docs                     Swagger UI (no auth to view; Authorize to call)
 *   GET  /openapi.json             the OpenAPI 3.1 document behind /docs
 *   GET  /health                   liveness (no auth)
 *   GET  /.well-known/agent.json   agent card with JSON schemas (no auth)
 *   POST /invoke                   the agent contract (service token)
 *   GET  /v1/households            ids + names (service token)
 *   GET  /v1/households/:clientId  same as get_household (service token)
 *
 * LEARN: compare with the Python agents' api/app.py. Same endpoints, same JSON,
 * same headers and error handling. Different language, same contract.
 */
import { randomUUID } from "node:crypto";

import express, { type ErrorRequestHandler, type Express } from "express";
import swaggerUi from "swagger-ui-express";
import { z } from "zod";

import type { AuditLog } from "./audit.js";
import { requireService } from "./auth.js";
import { type Config, VERSION } from "./config.js";
import { AgentRequest, ClientId, describeZodError, fail, ok } from "./contract.js";
import { getLogger } from "./logger.js";
import { buildOpenApi } from "./openapi.js";
import { SKILLS } from "./skills/index.js";
import { householdView } from "./skills/views.js";
import { type CrmStore, NotFoundError } from "./store/crmStore.js";

const log = getLogger("liaison.api");

export interface AppDeps {
  config: Config;
  store: CrmStore;
  audit: AuditLog;
}

interface WriteOutput {
  duplicate?: boolean;
  note_id?: string;
  task?: { task_id?: string };
}

export function createApp({ config, store, audit }: AppDeps): Express {
  const app = express();
  app.disable("x-powered-by");                 // don't advertise the framework
  app.use(express.json({ limit: "64kb" }));    // reject huge bodies early

  // trace id + security headers on every response
  app.use((req, res, next) => {
    const traceId = req.get("x-trace-id") ?? randomUUID().replaceAll("-", "");
    res.locals["traceId"] = traceId;
    res.set({ "X-Trace-Id": traceId, "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store" });
    next();
  });

  const service = requireService(config);
  const deps = { store, config };

  // ------------------------------------------------------------ docs
  const openapi = buildOpenApi(`http://${config.host}:${config.port}`);
  app.get("/openapi.json", (_req, res) => { res.json(openapi); });
  app.use("/docs", swaggerUi.serve, swaggerUi.setup(openapi, {
    customSiteTitle: "Liaison (crm-sync) API",
    swaggerOptions: { persistAuthorization: true, displayRequestDuration: true },
  }));

  // ------------------------------------------------------------ public
  app.get("/health", (_req, res) => {
    res.json({ status: "ok", agent: "liaison", version: VERSION, households: store.clientIds().length });
  });

  app.get("/.well-known/agent.json", (_req, res) => {
    res.json({
      name: "liaison", codename: "Liaison", folder: "crm-sync", language: "TypeScript (Node.js)", version: VERSION,
      description: "CRM read/write: households, tasks and notes.",
      auth: "Bearer SERVICE_TOKEN",
      endpoints: { invoke: "/invoke", households: "/v1/households", docs: "/docs", openapi: "/openapi.json" },
      skills: Object.fromEntries(Object.entries(SKILLS).map(([name, s]) => [name, {
        description: s.description, writes: s.writes, input_schema: z.toJSONSchema(s.input, { io: "input" }),
      }])),
    });
  });

  // ------------------------------------------------------------ protected
  app.get("/v1/households", service, (_req, res) => {
    res.json(store.clientIds().map((id) => ({ client_id: id, household: store.household(id).household })));
  });

  app.get("/v1/households/:clientId", service, (req, res) => {
    const id = ClientId.safeParse(req.params["clientId"]);
    if (!id.success) {
      res.status(422).json({ detail: "invalid client_id" });
      return;
    }
    try {
      res.json(householdView(id.data, store.household(id.data), config.today()));
    } catch (err: unknown) {
      if (err instanceof NotFoundError) {
        res.status(404).json({ detail: err.message });
        return;
      }
      throw err;
    }
  });

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
      const output = await def.run(params.data, context, deps);
      const clientId = String((params.data as { client_id?: string }).client_id ?? "");
      if (def.writes) {
        const w = output as WriteOutput;
        audit.record({
          trace_id: context.trace_id, user_id: context.user_id, skill, client_id: clientId,
          duplicate: w.duplicate ?? false, ids: { note_id: w.note_id, task_id: w.task?.task_id },
        });
      }
      log.info(`invoke skill=${skill} client=${clientId} ms=${Math.round(performance.now() - start)} trace=${context.trace_id}`);
      res.json(ok(output));
    } catch (err: unknown) {
      if (err instanceof NotFoundError || err instanceof RangeError) {
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
    res.status(500).json({ detail: "Internal error", trace_id: traceId }); // never leak stack traces
  };
  app.use(onError);

  return app;
}
