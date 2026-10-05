/**
 * Calls ANOTHER AGENT: the Liaison (CRM), for household details.
 *
 * LEARN: This is agent-to-agent communication without the Conductor in the middle.
 *  * Same contract as always: POST /invoke with { skill, input, context }.
 *  * Same SERVICE_TOKEN, sent as a Bearer token.
 *  * The trace_id is PASSED THROUGH, so one search in the logs follows the
 *    request from Conductor -> Herald -> Liaison.
 *  * A TIMEOUT (AbortSignal.timeout): a slow CRM must not hang the Herald.
 *  * GRACEFUL DEGRADATION: if the Liaison is down, the Herald still drafts a
 *    generic email and says so, instead of failing the whole request.
 */
import type { Config } from "../config.js";
import type { InvokeContext } from "../contract.js";
import { getLogger } from "../logger.js";
import type { HouseholdInfo } from "../types.js";

const log = getLogger("herald.liaison");

export type HouseholdLookup =
  | { ok: true; household: HouseholdInfo }
  | { ok: false; reason: string; notFound: boolean };

export interface HouseholdSource {
  getHousehold(clientId: string, ctx: InvokeContext): Promise<HouseholdLookup>;
}

interface LiaisonResponse {
  status: "ok" | "error";
  output: HouseholdInfo;
  error: string | null;
}

export class LiaisonClient implements HouseholdSource {
  constructor(private readonly config: Config) {}

  async getHousehold(clientId: string, ctx: InvokeContext): Promise<HouseholdLookup> {
    const body = { skill: "get_household", input: { client_id: clientId },
                   context: { trace_id: ctx.trace_id, user_id: ctx.user_id } };
    for (let attempt = 1; attempt <= 2; attempt++) {           // one retry: it's a safe read
      try {
        const res = await fetch(`${this.config.liaisonUrl}/invoke`, {
          method: "POST",
          headers: { "content-type": "application/json", authorization: `Bearer ${this.config.serviceToken}`,
                     "x-trace-id": ctx.trace_id },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(this.config.liaisonTimeoutMs),
        });
        if (res.status === 401) return { ok: false, reason: "Liaison rejected our token (401)", notFound: false };
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as LiaisonResponse;
        if (data.status === "ok") return { ok: true, household: data.output };
        const notFound = (data.error ?? "").startsWith("No household");
        return { ok: false, reason: data.error ?? "Liaison error", notFound };
      } catch (err: unknown) {
        const reason = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
        log.warn(`liaison_call_failed attempt=${attempt} reason=${reason} trace=${ctx.trace_id}`);
        if (attempt === 2) return { ok: false, reason: `Liaison unavailable (${reason})`, notFound: false };
      }
    }
    return { ok: false, reason: "Liaison unavailable", notFound: false };
  }
}
