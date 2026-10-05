/**
 * The Herald's pipeline. Read this file top to bottom: it IS the agent.
 *
 *   draft_email:
 *     1. Ask the Liaison for the household (names, style, tasks, next review)
 *     2. Decide intent (from the purpose) and tone (from the household's style)
 *     3. Template draft  (code: facts are always right)
 *     4. Claude rewrites it in the household's voice (optional; falls back to 3)
 *     5. Compliance pass (code: promises removed, PII masked, disclosure added)
 *     6. Warnings for the advisor + requires_approval: true (a human always sends)
 *
 *   review_email: step 5 (+ household warnings) on text the advisor wrote.
 */
import type { Config } from "../config.js";
import type { DraftEmailInput, InvokeContext, ReviewEmailInput } from "../contract.js";
import type { HouseholdSource } from "../clients/liaison.js";
import type { ComplianceReport, DraftResult, HouseholdInfo } from "../types.js";
import { checkEmail } from "./compliance.js";
import type { EmailWriter } from "./llm.js";
import { detectIntent, templateDraft, toneFromStyle } from "./templates.js";

/** A problem with the request itself (unknown client, text too long): returned as status=error. */
export class SkillError extends Error {}

export interface ReviewResult {
  revised_text: string;
  changed: boolean;
  compliance: ComplianceReport;
  warnings: string[];
  verdict: "ready_for_approval" | "needs_edits";
  requires_approval: true;
}

export class Composer {
  constructor(
    private readonly config: Config,
    private readonly households: HouseholdSource,
    private readonly writer: EmailWriter | null,
  ) {}

  get mode(): string {
    return this.writer ? `llm (${this.writer.name})` : "template";
  }

  async draft(input: DraftEmailInput, ctx: InvokeContext): Promise<DraftResult> {
    if (input.purpose.length > this.config.maxPurposeChars) {
      throw new SkillError(`purpose is too long (max ${this.config.maxPurposeChars} characters)`);
    }
    const warnings: string[] = [];

    // 1. household
    const household = await this.lookup(input.client_id, ctx, warnings);

    // 2. intent + tone
    const intent = detectIntent(input.purpose);
    const tone = input.tone ?? toneFromStyle(household?.preferences.communication_style);

    // 3. template
    const template = templateDraft({
      purpose: input.purpose, points: input.points, intent, tone, household, signature: this.config.signature,
    });

    // 4. LLM (optional)
    let draft = template;
    let draftedBy = "template";
    if (this.writer) {
      const better = await this.writer.write({
        intent, tone, purpose: input.purpose, points: input.points, household, template,
        signature: this.config.signature, traceId: ctx.trace_id,
      });
      if (better) {
        draft = better;
        draftedBy = this.writer.name;
      } else {
        draftedBy = "template (llm_fallback)";
        warnings.push("The AI rewrite failed, so this is the template version.");
      }
    }

    // 5. compliance on subject AND body
    const body = checkEmail(draft.body, { signature: this.config.signature });
    const subject = checkEmail(draft.subject);

    // 6. advisor warnings from the CRM
    if (household) warnings.push(...this.householdWarnings(household));

    return {
      subject: subject.text.split("\n\n")[0] ?? subject.text,   // never put the disclosure in a subject
      body: body.text,
      to: household ? household.members.filter((m) => m.email).map((m) => `${m.name} <${m.email}>`) : [],
      salutation: household?.preferences.salutation ?? "",
      intent,
      tone,
      channel_preference: household?.preferences.contact_channel ?? "unknown",
      personalized: household !== null,
      compliance: {
        fixes: [...new Set([...subject.report.fixes, ...body.report.fixes])],
        disclosure_added: body.report.disclosure_added,
        warnings: [...subject.report.warnings, ...body.report.warnings],
      },
      warnings,
      requires_approval: true,
      drafted_by: draftedBy,
    };
  }

  async review(input: ReviewEmailInput, ctx: InvokeContext): Promise<ReviewResult> {
    if (input.text.length > this.config.maxEmailChars) {
      throw new SkillError(`text is too long (max ${this.config.maxEmailChars} characters)`);
    }
    const warnings: string[] = [];
    const { text, report } = checkEmail(input.text);
    if (input.client_id) {
      const household = await this.lookup(input.client_id, ctx, warnings);
      if (household) {
        warnings.push(...this.householdWarnings(household));
        const firstName = household.preferences.salutation.split(/\s+and\s+|\s+/)[0] ?? "";
        if (firstName && !input.text.includes(firstName) && !/^(Mr|Mrs|Ms|Dr)\.?$/.test(firstName)) {
          warnings.push(`The email doesn't use the household's usual greeting ("${household.preferences.salutation}").`);
        }
      }
    }
    const changed = text !== input.text;
    return {
      revised_text: text,
      changed,
      compliance: report,
      warnings,
      verdict: report.fixes.length === 0 && report.warnings.length === 0 ? "ready_for_approval" : "needs_edits",
      requires_approval: true,
    };
  }

  /** Unknown client = error. Liaison down = degrade with a warning. */
  private async lookup(clientId: string, ctx: InvokeContext, warnings: string[]): Promise<HouseholdInfo | null> {
    const res = await this.households.getHousehold(clientId, ctx);
    if (res.ok) return res.household;
    if (res.notFound) throw new SkillError(res.reason);
    warnings.push(`CRM unavailable (${res.reason}). Draft is not personalized: check names and details before sending.`);
    return null;
  }

  private householdWarnings(h: HouseholdInfo): string[] {
    const out: string[] = [];
    if (h.preferences.contact_channel !== "email") {
      out.push(`${h.household} prefers ${h.preferences.contact_channel} contact. Consider calling, or keep the email short.`);
    }
    for (const alert of h.service_alerts) out.push(`Open service alert: ${alert}`);
    const overdue = h.open_tasks.filter((t) => t.overdue).length;
    if (overdue) out.push(`${overdue} open task(s) are overdue in the CRM.`);
    return out;
  }
}
