import { describe, expect, it, vi } from "vitest";

import { ApiError, api, setToken, setUnauthorizedHandler } from "../src/api/client";
import type { Overview } from "../src/api/types";
import { parseSSE } from "../src/api/stream";
import { collectNeeds } from "../src/components/NeedsYou";
import { jwtExpiry } from "../src/lib/auth";
import { chance, day, moneyShort, signedMoney } from "../src/lib/format";
import { fakeJwt, json, overview } from "./helpers";

describe("format", () => {
  it("never says a projection is certain", () => {
    expect(chance(99.8)).toBe("over 99%");
    expect(chance(0.2)).toBe("under 1%");
    expect(chance(87.4)).toBe("87%");
  });
  it("writes money for tight spaces and with a real minus sign", () => {
    expect(moneyShort(2_350_000)).toBe("$2.35M");
    expect(moneyShort(329_000)).toBe("$329k");
    expect(signedMoney(-29_610)).toBe("−$29,610");
    expect(signedMoney(11_000)).toBe("+$11,000");
  });
  it("reads dates as calendar days, whatever the time zone", () => {
    expect(day("2026-10-08")).toBe("Thu, Oct 8");
  });
});

describe("parseSSE", () => {
  it("splits events and keeps the event name", () => {
    const msgs = parseSSE('event: hello\ndata: {"a":1}\n\nevent: market_event\ndata: {"event_id":"EV-1"}\n\n: ping\n\n');
    expect(msgs).toEqual([
      { event: "hello", data: '{"a":1}' },
      { event: "market_event", data: '{"event_id":"EV-1"}' },
    ]);
  });
  it("handles Windows line endings", () => {
    expect(parseSSE("event: x\r\ndata: 1\r\n\r\n")).toEqual([{ event: "x", data: "1" }]);
  });
});

describe("jwtExpiry", () => {
  it("reads exp in milliseconds", () => {
    expect(jwtExpiry(fakeJwt(2_000_000_000))).toBe(2_000_000_000_000);
  });
  it("returns null for junk instead of throwing", () => {
    expect(jwtExpiry("not-a-token")).toBeNull();
  });
});

describe("api client", () => {
  it("sends the token and keeps the trace id on errors", async () => {
    const fetchMock = vi.fn(async () => json({ detail: "agent.skill is not available to the apps" }, 403, "trace-xyz"));
    vi.stubGlobal("fetch", fetchMock);
    setToken("tok-123");
    const err = await api.get("/v1/clients").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(403);
    expect((err as ApiError).traceId).toBe("trace-xyz");
    expect((err as ApiError).message).toMatch(/not available/);
    const init = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((init[1].headers as Record<string, string>)["Authorization"]).toBe("Bearer tok-123");
    setToken(null);
  });
  it("signs out on 401", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "expired" }, 401)));
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    setToken("tok-old");
    await api.get("/v1/me").catch(() => undefined);
    expect(onUnauthorized).toHaveBeenCalledOnce();
    setToken(null);
  });
});

describe("collectNeeds", () => {
  const o = overview as unknown as Overview;
  it("puts paperwork, overdue tasks, market news and drift in front of the advisor", () => {
    const needs = collectNeeds(o);
    const kinds = needs.map((n) => n.kind);
    expect(kinds[0]).toBe("Paperwork"); // the expiring ID comes first
    expect(kinds).toContain("Overdue");
    expect(kinds).toContain("Market");
    expect(kinds).toContain("Rebalance");
    expect(kinds).toContain("Concentration");
    expect(needs.find((n) => n.kind === "Rebalance")?.text).toBe("Stocks are 8 points over target.");
  });
  it("skips a section whose agent failed, instead of crashing", () => {
    const broken = structuredClone(o);
    broken.sections.kyc = { ...broken.sections.kyc, status: "error", error: "timeout" };
    expect(collectNeeds(broken).some((n) => n.kind === "Paperwork")).toBe(false);
  });
});
