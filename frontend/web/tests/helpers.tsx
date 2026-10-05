/**
 * Test helpers: a fake Conductor (a fetch that answers from recorded agent outputs)
 * and a render() that wraps a screen in the same providers the app uses.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

import { AuthProvider } from "../src/lib/auth";
import overview from "./fixtures/overview-patel.json";
import skills from "./fixtures/skills-patel.json";

export { overview, skills };

type Handler = (url: string, init: RequestInit | undefined) => Response | Promise<Response>;

export function json(body: unknown, status = 200, traceId = "trace-test-1"): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Trace-Id": traceId },
  });
}

/** A JWT with only an "exp" claim: enough for the app to read the expiry. */
export function fakeJwt(expSeconds = Math.floor(Date.now() / 1000) + 3600): string {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "");
  return `${b64({ alg: "HS256" })}.${b64({ sub: "advisor", exp: expSeconds })}.sig`;
}

export function signedIn(): void {
  sessionStorage.setItem(
    "atrium.session",
    JSON.stringify({ token: fakeJwt(), user: "advisor", expiresAt: Date.now() + 3_600_000 }),
  );
}

const skill = (agent: string, name: string, output: unknown) => ({
  agent, skill: name, status: "ok", error: null, trace_id: "trace-test-1", duration_ms: 20, output, guardrail_notes: [],
});

/** The default fake Conductor. Pass `extra` to override a route. */
export function fakeConductor(extra: Handler | null = null) {
  const calls: Array<{ url: string; body: unknown }> = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (extra) {
      const r = await extra(url, init);
      if (r.status !== 599) return r;
    }
    if (url === "/v1/clients")
      return json([
        { client_id: "patel-001", household: "Patel household" },
        { client_id: "chen-002", household: "Chen household" },
      ]);
    if (url === "/v1/clients/patel-001/overview") return json(overview);
    if (url === "/v1/skills/actuary/project_retirement") return json(skill("actuary", "project_retirement", skills["actuary.project_retirement"]));
    if (url === "/v1/skills/actuary/stress_test") return json(skill("actuary", "stress_test", skills["actuary.stress_test"]));
    if (url === "/v1/skills/herald/draft_email") return json(skill("herald", "draft_email", skills["herald.draft_email"]));
    if (url.startsWith("/v1/stream")) return new Response(new ReadableStream({ start() {} }), { status: 200 });
    return json({ detail: "Not Found" }, 404);
  });
  vi.stubGlobal("fetch", fn);
  return { fn, calls };
}

/** Lets a test's own handler fall through to the defaults. */
export const PASS = () => new Response(null, { status: 599 });

export function renderApp(ui: ReactNode, path = "/") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}
