/** HTTP tests: the agent contract, auth, errors, audit log. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, before, describe, it } from "node:test";

import type { DraftResult } from "../src/types.js";
import { startTestServer, type TestServer } from "./helpers.js";

let t: TestServer;
before(async () => { t = await startTestServer(); });
after(async () => { await t.close(); });

describe("public endpoints", () => {
  it("GET /health without a token", async () => {
    const res = await t.call("/health", { token: null });
    assert.equal(res.status, 200);
    const body = (await res.json()) as Record<string, unknown>;
    assert.equal(body["agent"], "herald");
    assert.equal(body["mode"], "template");
    assert.equal(res.headers.get("x-content-type-options"), "nosniff");
    assert.equal(res.headers.get("x-powered-by"), null);
  });

  it("agent card lists both skills with schemas", async () => {
    const card = (await (await t.call("/.well-known/agent.json", { token: null })).json()) as
      { skills: Record<string, { input_schema: unknown }> };
    assert.deepEqual(Object.keys(card.skills).sort(), ["draft_email", "review_email"]);
    assert.ok(card.skills["draft_email"]?.input_schema);
  });
});

describe("auth", () => {
  it("rejects a missing or wrong token", async () => {
    for (const token of [null, "wrong-token"]) {
      const res = await t.call("/invoke", { method: "POST", token, body: {} });
      assert.equal(res.status, 401);
      assert.equal(res.headers.get("www-authenticate"), "Bearer");
    }
  });

  it("protects /v1/rules", async () => {
    assert.equal((await t.call("/v1/rules", { token: null })).status, 401);
    const rules = (await (await t.call("/v1/rules")).json()) as Array<{ id: string }>;
    assert.ok(rules.some((r) => r.id === "CMP_GUARANTEE"));
  });
});

describe("POST /invoke", () => {
  it("draft_email returns a personalized draft that needs approval", async () => {
    const r = await t.invoke<DraftResult>("draft_email",
      { client_id: "patel-001", purpose: "Follow up on today's review", points: ["Raise the 529 contribution"] },
      { trace_id: "api-trace-1" });
    assert.equal(r.status, "ok");
    assert.equal(r.agent, "herald");
    assert.equal(r.output.intent, "meeting_follow_up");
    assert.equal(r.output.requires_approval, true);
    assert.ok(r.output.body.includes("Raise the 529 contribution."));
    assert.equal(t.liaison.calls.at(-1)?.trace, "api-trace-1");   // trace id flows to the Liaison
    assert.equal(t.liaison.calls.at(-1)?.auth, `Bearer ${t.config.serviceToken}`);
  });

  it("takes client_id from the context when missing in input", async () => {
    const r = await t.invoke<DraftResult>("draft_email", { purpose: "Check in" }, { client_id: "chen-002" });
    assert.equal(r.status, "ok");
    assert.equal(r.output.salutation, "Mr. and Mrs. Chen");
  });

  it("review_email fixes and flags", async () => {
    const r = await t.invoke<{ changed: boolean; verdict: string; revised_text: string }>("review_email",
      { text: "This is risk-free. SSN 123-45-6789." });
    assert.equal(r.status, "ok");
    assert.equal(r.output.changed, true);
    assert.equal(r.output.verdict, "needs_edits");
    assert.ok(!r.output.revised_text.includes("123-45-6789"));
  });

  it("unknown skill / bad input / unknown client -> status error", async () => {
    assert.match((await t.invoke("send_email", {})).error ?? "", /unknown skill/);
    assert.match((await t.invoke("draft_email", { client_id: "patel-001", purpose: "x" })).error ?? "", /purpose/);
    assert.match((await t.invoke("draft_email", { client_id: "../etc", purpose: "hello" })).error ?? "", /client_id/);
    assert.match((await t.invoke("draft_email", { client_id: "nobody-1", purpose: "hello" })).error ?? "", /No household/);
  });

  it("rejects an over-long purpose", async () => {
    const r = await t.invoke("draft_email", { client_id: "patel-001", purpose: "a".repeat(2001) });
    assert.match(r.error ?? "", /too long/);
  });

  it("contract errors are HTTP 422; bad JSON 422; huge body 413", async () => {
    assert.equal((await t.call("/invoke", { method: "POST", body: { skill: "draft_email" } })).status, 422);
    assert.equal((await t.call("/invoke", { method: "POST", raw: "{not json" })).status, 422);
    assert.equal((await t.call("/invoke", { method: "POST", raw: JSON.stringify({ x: "a".repeat(70_000) }) })).status, 413);
  });

  it("unknown path is 404", async () => {
    assert.equal((await t.call("/nope")).status, 404);
  });

  it("audit log has a fingerprint, never the email text", async () => {
    await t.invoke("draft_email", { client_id: "patel-001", purpose: "Check in about the secret-word plan" });
    const log = readFileSync(t.config.auditFile, "utf8");
    const last = JSON.parse(log.trim().split("\n").at(-1)!) as Record<string, unknown>;
    assert.equal(last["skill"], "draft_email");
    assert.match(String(last["body_sha256"]), /^[0-9a-f]{16}$/);
    assert.ok(!log.includes("secret-word"));
  });
});
