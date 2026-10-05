/** The Swagger page and the OpenAPI document behind it. */
import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";

import { SKILLS } from "../src/skills/index.js";
import { startTestServer, type TestServer } from "./helpers.js";

interface OpenApiDoc {
  openapi: string;
  paths: Record<string, Record<string, { security?: unknown[];
    requestBody?: { content: { "application/json": { examples: Record<string, { value: { skill: string } }> } } } }>>;
  components: { securitySchemes: Record<string, { scheme: string }>; schemas: Record<string, unknown> };
}

let t: TestServer;
let doc: OpenApiDoc;
before(async () => {
  t = await startTestServer();
  doc = (await (await t.call("/openapi.json", { token: null })).json()) as OpenApiDoc;
});
after(async () => { await t.close(); });

describe("OpenAPI / Swagger", () => {
  it("serves an OpenAPI 3.1 document without a token", () => {
    assert.equal(doc.openapi, "3.1.0");
    assert.equal(doc.components.securitySchemes["serviceToken"]?.scheme, "bearer");
  });

  it("documents every endpoint", () => {
    for (const path of ["/health", "/.well-known/agent.json", "/invoke", "/v1/households", "/v1/households/{clientId}"]) {
      assert.ok(doc.paths[path], `missing ${path}`);
    }
  });

  it("has one input schema and one example per skill (generated from the code)", () => {
    const examples = doc.paths["/invoke"]?.["post"]?.requestBody?.content["application/json"].examples ?? {};
    for (const name of Object.keys(SKILLS)) {
      assert.ok(doc.components.schemas[`${name}_input`], `schema for ${name}`);
      assert.equal(examples[name]?.value.skill, name);
    }
  });

  it("protected endpoints declare the bearer token", () => {
    assert.deepEqual(doc.paths["/invoke"]?.["post"]?.security, [{ serviceToken: [] }]);
  });

  it("every example in Swagger actually works against the API", async () => {
    const examples = doc.paths["/invoke"]?.["post"]?.requestBody?.content["application/json"].examples ?? {};
    for (const [name, ex] of Object.entries(examples)) {
      const r = await t.call("/invoke", { method: "POST", body: ex.value });
      const body = (await r.json()) as { status: string; error: string | null };
      assert.equal(body.status, "ok", `${name}: ${body.error}`);
    }
  });

  it("serves the Swagger UI page", async () => {
    const res = await t.call("/docs/", { token: null });
    assert.equal(res.status, 200);
    assert.match(await res.text(), /swagger-ui/i);
  });
});
