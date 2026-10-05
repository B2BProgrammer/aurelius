/**
 * Test helpers: start the real app on a random port with a TEMPORARY copy of
 * the seed data, so tests never touch data\crm.json.
 *
 * LEARN: node:test and fetch are built into Node 20+. tsx lets Node run the
 * .ts test files directly, so the tests are TypeScript too.
 */
import { mkdtempSync } from "node:fs";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createApp } from "../src/app.js";
import { AuditLog } from "../src/audit.js";
import { type Config, getConfig } from "../src/config.js";
import { CrmStore } from "../src/store/crmStore.js";

export const TOKEN = "test-service-token-abcdefghijklmnop";

export interface InvokeResult<T = Record<string, unknown>> {
  agent: string;
  status: "ok" | "error";
  output: T;
  error: string | null;
}

export interface TestServer {
  base: string;
  config: Config;
  store: CrmStore;
  call: (path: string, opts?: { method?: string; body?: unknown; token?: string | null; raw?: string }) => Promise<Response>;
  invoke: <T = Record<string, unknown>>(skill: string, input?: Record<string, unknown>,
                                        context?: Record<string, unknown>) => Promise<InvokeResult<T>>;
  close: () => Promise<void>;
}

export async function startTestServer(): Promise<TestServer> {
  const dir = mkdtempSync(join(tmpdir(), "liaison-test-"));
  const config = getConfig({
    serviceToken: TOKEN,
    dataFile: join(dir, "crm.json"),
    auditFile: join(dir, "audit.jsonl"),
    today: () => "2026-10-03",               // fixed clock = predictable "overdue"
  });
  const store = new CrmStore(config);
  const server = createApp({ config, store, audit: new AuditLog(config.auditFile) }).listen(0);
  await new Promise<void>((resolve) => server.once("listening", () => resolve()));
  const base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;

  const call: TestServer["call"] = (path, { method = "GET", body, token = TOKEN, raw } = {}) => {
    const init: RequestInit = {
      method,
      headers: { "content-type": "application/json", ...(token ? { authorization: `Bearer ${token}` } : {}) },
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
    base, config, store, call, invoke,
    close: () => new Promise<void>((resolve) => server.close(() => resolve())),
  };
}
