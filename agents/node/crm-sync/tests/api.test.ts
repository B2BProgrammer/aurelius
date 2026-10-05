import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, before, describe, it } from "node:test";

import { checkStartupSecurity, getConfig } from "../src/config.js";
import type { HouseholdView, Task } from "../src/types.js";
import { startTestServer, type TestServer } from "./helpers.js";

let t: TestServer;
before(async () => { t = await startTestServer(); });
after(async () => { await t.close(); });

describe("public endpoints", () => {
  it("health", async () => {
    const h = (await (await t.call("/health", { token: null })).json()) as { agent: string; households: number };
    assert.equal(h.agent, "liaison");
    assert.equal(h.households, 3);
  });

  it("agent card lists 5 skills with JSON schemas", async () => {
    const card = (await (await t.call("/.well-known/agent.json", { token: null })).json()) as {
      skills: Record<string, { writes: boolean; input_schema: { properties: Record<string, unknown> } }>;
    };
    assert.deepEqual(Object.keys(card.skills).sort(),
      ["add_task", "complete_task", "get_household", "list_tasks", "log_note"]);
    assert.equal(card.skills["log_note"]?.writes, true);
    assert.ok(card.skills["get_household"]?.input_schema.properties["client_id"]);
  });

  it("security headers, no framework banner", async () => {
    const res = await t.call("/health", { token: null });
    assert.equal(res.headers.get("x-content-type-options"), "nosniff");
    assert.equal(res.headers.get("x-powered-by"), null);
  });
});

describe("authentication", () => {
  it("rejects missing and wrong tokens", async () => {
    assert.equal((await t.call("/v1/households", { token: null })).status, 401);
    assert.equal((await t.call("/v1/households", { token: "wrong-token-wrong-token-wrong" })).status, 401);
    assert.equal((await t.call("/invoke", { method: "POST", token: null, body: {} })).status, 401);
  });

  it("refuses to start with a weak token", () => {
    assert.throws(() => checkStartupSecurity(getConfig({ serviceToken: "replace-me" })));
  });
});

describe("reads", () => {
  it("get_household masks contacts and flags overdue tasks", async () => {
    const { status, output } = await t.invoke<HouseholdView>("get_household", { client_id: "patel-001" });
    assert.equal(status, "ok");
    assert.equal(output.members[0]?.email, "r***@example.com");
    assert.equal(output.members[0]?.phone, "***-***-0101");
    assert.ok(!JSON.stringify(output).includes("raj.patel@example.com"));
    assert.equal(output.overdue_tasks, 2);                 // T-1001 (Apr 30) and T-1002 (Oct 1)
    assert.equal(output.recent_notes[0]?.date, "2026-07-14");
  });

  it("client_id can come from the context", async () => {
    const r = await t.invoke<HouseholdView>("get_household", {}, { client_id: "chen-002" });
    assert.equal(r.output.household, "Chen family");
  });

  it("list_tasks filters by status", async () => {
    assert.equal((await t.invoke<{ count: number }>("list_tasks", { client_id: "patel-001", status: "done" })).output.count, 1);
    assert.equal((await t.invoke<{ count: number }>("list_tasks", { client_id: "patel-001", status: "all" })).output.count, 3);
  });

  it("REST view of a household", async () => {
    assert.equal((await t.call("/v1/households/garcia-003")).status, 200);
    assert.equal((await t.call("/v1/households/nobody-1")).status, 404);
    assert.equal((await t.call("/v1/households/bad%20id")).status, 422);
  });
});

interface NoteOut { saved: boolean; note_id: string; pii_masked: string[]; duplicate: boolean }
interface TaskOut { saved: boolean; already_done?: boolean; task: Task; duplicate: boolean }

describe("writes", () => {
  it("log_note saves, masks PII, updates last_contact", async () => {
    const r = await t.invoke<NoteOut>("log_note",
      { client_id: "garcia-003", note: "Call with Maria. Acct 123456789012 mentioned.", type: "call" },
      { trace_id: "trace-note-1" });
    assert.equal(r.output.saved, true);
    assert.deepEqual(r.output.pii_masked, ["ACCOUNT_NUMBER"]);
    const h = t.store.household("garcia-003");
    assert.ok(h.notes.at(-1)?.text.includes("[ACCOUNT_NUMBER]"));
    assert.equal(h.last_contact, "2026-10-03");
  });

  it("a RETRY of the same request does not create a duplicate", async () => {
    const body = { client_id: "chen-002", note: "Left voicemail about QCDs.", type: "call" };
    const first = await t.invoke<NoteOut>("log_note", body, { trace_id: "trace-retry" });
    const again = await t.invoke<NoteOut>("log_note", body, { trace_id: "trace-retry" });
    assert.equal(first.output.note_id, again.output.note_id);
    assert.equal(again.output.duplicate, true);
    assert.equal(t.store.household("chen-002").notes.filter((n) => n.text === body.note).length, 1);
  });

  it("explicit idempotency_key works across different traces", async () => {
    const body = { client_id: "patel-001", title: "Send wedding savings options", idempotency_key: "key-12345678" };
    const a = await t.invoke<TaskOut>("add_task", body, { trace_id: "trace-a" });
    const b = await t.invoke<TaskOut>("add_task", body, { trace_id: "trace-b" });
    assert.equal(a.output.task.task_id, b.output.task.task_id);
    assert.equal(b.output.duplicate, true);
  });

  it("concurrent writes get unique ids (no lost updates)", async () => {
    const results = await Promise.all(Array.from({ length: 10 }, (_, i) =>
      t.invoke<TaskOut>("add_task", { client_id: "chen-002", title: `Parallel task ${i}` }, { trace_id: `par-${i}` })));
    assert.equal(new Set(results.map((r) => r.output.task.task_id)).size, 10);
    const onDisk = JSON.parse(readFileSync(t.config.dataFile, "utf-8")) as {
      households: Record<string, { tasks: Task[] }>;
    };
    assert.equal(onDisk.households["chen-002"]?.tasks.filter((x) => x.title.startsWith("Parallel")).length, 10);
  });

  it("complete_task is idempotent", async () => {
    const a = await t.invoke<TaskOut>("complete_task", { client_id: "chen-002", task_id: "T-1005" }, { trace_id: "c1" });
    const b = await t.invoke<TaskOut>("complete_task", { client_id: "chen-002", task_id: "T-1005" }, { trace_id: "c2" });
    assert.equal(a.output.saved, true);
    assert.equal(b.output.already_done, true);
  });

  it("every write is audited without the note text", () => {
    const text = readFileSync(t.config.auditFile, "utf-8");
    const lines = text.trim().split("\n").map((l) => JSON.parse(l) as { skill: string; trace_id: string });
    assert.ok(lines.some((l) => l.skill === "log_note" && l.trace_id === "trace-note-1"));
    assert.ok(!text.includes("Acct"));
  });
});

describe("errors", () => {
  const cases: Array<[string, Record<string, unknown>, string]> = [
    ["get_household", { client_id: "nobody-1" }, "No household with id"],
    ["get_household", { client_id: "bad id!" }, "invalid input: client_id"],
    ["get_household", {}, "invalid input: client_id"],
    ["list_tasks", { client_id: "patel-001", status: "maybe" }, "invalid input: status"],
    ["add_task", { client_id: "patel-001", title: "x" }, "invalid input: title"],
    ["add_task", { client_id: "patel-001", title: "Valid title", due: "next week" }, "invalid input: due"],
    ["complete_task", { client_id: "patel-001", task_id: "T-9999" }, "No task 'T-9999'"],
    ["complete_task", { client_id: "patel-001", task_id: "drop table" }, "invalid input: task_id"],
    ["log_note", { client_id: "patel-001", note: "x".repeat(5001) }, "longer than 5000"],
    ["delete_household", { client_id: "patel-001" }, "unknown skill delete_household"],
  ];
  for (const [skill, input, expected] of cases) {
    it(`${skill} ${JSON.stringify(input).slice(0, 50)}`, async () => {
      const r = await t.invoke(skill, input);
      assert.equal(r.status, "error");
      assert.ok(r.error?.includes(expected), r.error ?? "");
    });
  }

  it("missing context is 422, bad JSON is 422", async () => {
    assert.equal((await t.call("/invoke", { method: "POST", body: { skill: "get_household", input: {} } })).status, 422);
    assert.equal((await t.call("/invoke", { method: "POST", raw: "{bad" })).status, 422);
  });
});
