/**
 * Test helpers.
 *
 * LEARN: The Herald depends on two things outside itself: the Liaison (HTTP)
 * and Claude (HTTP). Tests replace both:
 *  * startFakeLiaison(): a tiny real HTTP server that answers get_household,
 *    so the Herald's REAL LiaisonClient (fetch, token, timeout) is tested.
 *  * FakeMessages: pretends to be the Anthropic SDK, returns whatever we want
 *    (good JSON, bad JSON, an exception).
 * No network, no API key, same result every run.
 */
import { createServer, type IncomingMessage, type Server } from "node:http";
import { mkdtempSync } from "node:fs";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type Anthropic from "@anthropic-ai/sdk";

import { createApp } from "../src/app.js";
import { AuditLog } from "../src/audit.js";
import { LiaisonClient } from "../src/clients/liaison.js";
import { Composer } from "../src/compose/composer.js";
import { ClaudeWriter, type MessagesApi } from "../src/compose/llm.js";
import { type Config, getConfig } from "../src/config.js";
import type { HouseholdInfo } from "../src/types.js";

export const TOKEN = "test-service-token-abcdefghijklmnop";

// ------------------------------------------------------------------ fake Liaison
export const HOUSEHOLDS: Record<string, HouseholdInfo> = {
  "patel-001": {
    client_id: "patel-001", household: "Patel household",
    members: [
      { name: "Raj Patel", role: "primary", age: 58, email: "r***@example.com", phone: "***-***-0142" },
      { name: "Anita Patel", role: "spouse", age: 56, email: "a***@example.com", phone: null },
    ],
    preferences: { contact_channel: "email", salutation: "Raj and Anita",
                   communication_style: "Prefers short, plain-language emails. Anita handles scheduling. Use first names." },
    next_review: "2026-10-08",
    service_alerts: [],
    open_tasks: [
      { task_id: "T-1001", title: "Send updated beneficiary form", owner: "client", due: "2026-09-20", overdue: true },
      { task_id: "T-1002", title: "Model retirement at 62 and 63", owner: "advisor", due: "2026-09-30", overdue: true },
    ],
  },
  "chen-002": {
    client_id: "chen-002", household: "Chen family",
    members: [{ name: "Wei Chen", role: "primary", age: 64, email: "w***@example.com", phone: "***-***-7781" }],
    preferences: { contact_channel: "phone", salutation: "Mr. and Mrs. Chen",
                   communication_style: "Formal. Prefers a phone call before anything in writing." },
    next_review: "2026-11-02",
    service_alerts: [],
    open_tasks: [],
  },
  "garcia-003": {
    client_id: "garcia-003", household: "Garcia household",
    members: [{ name: "Maria Garcia", role: "primary", age: 47, email: "m***@example.com", phone: null }],
    preferences: { contact_channel: "email", salutation: "Maria and Luis", communication_style: "Friendly." },
    next_review: "2026-12-10",
    service_alerts: ["Maria was unhappy that last year's report arrived late."],
    open_tasks: [],
  },
};

export interface FakeLiaison {
  url: string;
  calls: Array<{ auth: string | undefined; trace: string | undefined; body: Record<string, unknown> }>;
  /** "ok" (default), "down" (HTTP 503), "slow" (never answers in time) */
  mode: "ok" | "down" | "slow";
  close: () => Promise<void>;
}

async function readJson(req: IncomingMessage): Promise<Record<string, unknown>> {
  let raw = "";
  for await (const chunk of req) raw += String(chunk);
  return JSON.parse(raw || "{}") as Record<string, unknown>;
}

export async function startFakeLiaison(): Promise<FakeLiaison> {
  const fake: FakeLiaison = { url: "", calls: [], mode: "ok", close: async () => {} };
  const server: Server = createServer((req, res) => {
    void (async () => {
      const body = await readJson(req);
      fake.calls.push({ auth: req.headers.authorization, trace: req.headers["x-trace-id"] as string | undefined, body });
      if (fake.mode === "slow") return;                       // never respond -> client timeout
      if (fake.mode === "down") { res.writeHead(503).end(); return; }
      if (req.headers.authorization !== `Bearer ${TOKEN}`) { res.writeHead(401).end(); return; }
      const id = String((body["input"] as Record<string, unknown>)["client_id"]);
      const h = HOUSEHOLDS[id];
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(h
        ? { agent: "liaison", status: "ok", output: h, error: null }
        : { agent: "liaison", status: "error", output: {}, error: `No household with id '${id}'` }));
    })();
  });
  server.listen(0);
  await new Promise<void>((resolve) => server.once("listening", () => resolve()));
  fake.url = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  fake.close = () => new Promise<void>((resolve) => { server.closeAllConnections(); server.close(() => resolve()); });
  return fake;
}

// ------------------------------------------------------------------ fake Claude
export class FakeMessages implements MessagesApi {
  calls: Anthropic.MessageCreateParamsNonStreaming[] = [];
  constructor(public reply: unknown | Error) {}

  create(params: Anthropic.MessageCreateParamsNonStreaming): Promise<Anthropic.Message> {
    this.calls.push(params);
    if (this.reply instanceof Error) return Promise.reject(this.reply);
    return Promise.resolve({
      id: "msg_fake", type: "message", role: "assistant", model: params.model,
      content: [{ type: "tool_use", id: "tu_1", name: "write_email", input: this.reply }],
      stop_reason: "tool_use", stop_sequence: null,
      usage: { input_tokens: 100, output_tokens: 50 },
    } as unknown as Anthropic.Message);
  }
}

// ------------------------------------------------------------------ config + server
export function testConfig(overrides: Partial<Config> = {}): Config {
  const dir = mkdtempSync(join(tmpdir(), "herald-test-"));
  return getConfig({
    serviceToken: TOKEN, llmMock: true, liaisonTimeoutMs: 500,
    signature: "Sam Rivera\nAurelius Wealth", auditFile: join(dir, "drafts.jsonl"),
    today: () => "2026-10-03",
    ...overrides,
  });
}

export function makeComposer(config: Config, messages?: FakeMessages): Composer {
  const writer = messages ? new ClaudeWriter(config, messages) : null;
  return new Composer(config, new LiaisonClient(config), writer);
}

export interface InvokeResult<T = Record<string, unknown>> {
  agent: string;
  status: "ok" | "error";
  output: T;
  error: string | null;
}

export interface TestServer {
  base: string;
  config: Config;
  liaison: FakeLiaison;
  call: (path: string, opts?: { method?: string; body?: unknown; token?: string | null; raw?: string;
                                headers?: Record<string, string> }) => Promise<Response>;
  invoke: <T = Record<string, unknown>>(skill: string, input?: Record<string, unknown>,
                                        context?: Record<string, unknown>) => Promise<InvokeResult<T>>;
  close: () => Promise<void>;
}

export async function startTestServer(messages?: FakeMessages): Promise<TestServer> {
  const liaison = await startFakeLiaison();
  const config = testConfig({ liaisonUrl: liaison.url });
  const app = createApp({ config, composer: makeComposer(config, messages), audit: new AuditLog(config.auditFile) });
  const server = app.listen(0);
  await new Promise<void>((resolve) => server.once("listening", () => resolve()));
  const base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;

  const call: TestServer["call"] = (path, { method = "GET", body, token = TOKEN, raw, headers = {} } = {}) => {
    const init: RequestInit = {
      method,
      headers: { "content-type": "application/json", ...(token ? { authorization: `Bearer ${token}` } : {}), ...headers },
    };
    if (raw !== undefined) init.body = raw;
    else if (body !== undefined) init.body = JSON.stringify(body);
    return fetch(base + path, init);
  };

  const invoke: TestServer["invoke"] = async (skill, input = {}, context = {}) => {
    const res = await call("/invoke", {
      method: "POST",
      body: { skill, input, context: { trace_id: "test-trace", user_id: "dev-advisor", ...context } },
    });
    return res.json() as never;
  };

  return {
    base, config, liaison, call, invoke,
    close: async () => {
      await new Promise<void>((resolve) => server.close(() => resolve()));
      await liaison.close();
    },
  };
}
