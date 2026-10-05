/**
 * The Herald's skills. Neither one SENDS anything: the Herald drafts and
 * checks; the advisor approves and sends from their own mailbox.
 *
 * Each skill = { description, input (Zod), example, run }. The same table
 * feeds /invoke, the agent card and the Swagger page.
 */
import type { z } from "zod";

import type { Composer } from "../compose/composer.js";
import { DraftEmailInput, type InvokeContext, ReviewEmailInput } from "../contract.js";

export interface Deps {
  composer: Composer;
}

export interface Skill<S extends z.ZodType = z.ZodType> {
  description: string;
  input: S;
  /** Example inputs shown in the Swagger dropdown (first one = the skill's main example). */
  examples: Record<string, Record<string, unknown>>;
  run: (input: z.infer<S>, ctx: InvokeContext, deps: Deps) => Promise<unknown>;
}

const skill = <S extends z.ZodType>(def: Skill<S>): Skill => def as unknown as Skill;

export const SKILLS: Record<string, Skill> = {
  draft_email: skill({
    description:
      "Draft a client email personalized from the CRM (via the Liaison), compliance-checked. " +
      "Returns a draft for the advisor to approve; nothing is sent.",
    input: DraftEmailInput,
    examples: {
      draft_email: {
        client_id: "patel-001",
        purpose: "Follow up on today's review meeting",
        points: ["We agreed to increase the 529 contribution", "I'll send the updated plan by Friday"],
      },
      "draft_email (formal household)": {
        client_id: "chen-002",
        purpose: "Prepare for our upcoming review",
      },
      "draft_email (compliance fixes)": {
        client_id: "garcia-003",
        purpose: "Check in about the new bond fund",
        points: ["It offers guaranteed returns of 6%", "Your account 123456789 is set up"],
        tone: "warm",
      },
    },
    run: (input, ctx, { composer }) => composer.draft(input, ctx),
  }),

  review_email: skill({
    description:
      "Check an email the advisor wrote: removes promises, masks SSNs/account numbers, adds the " +
      "risk disclosure when needed, and flags household preferences.",
    input: ReviewEmailInput,
    examples: {
      review_email: {
        client_id: "chen-002",
        text: "Hi Wei,\n\nThis fund is risk-free and will definitely go up. Your SSN 123-45-6789 is on file.\n\nBest,\nSam",
      },
      "review_email (clean)": {
        text: "Hi Maria and Luis,\n\nThanks for your time today. I'll send the paperwork tomorrow.\n\nBest,\nSam",
      },
    },
    run: (input, ctx, { composer }) => composer.review(input, ctx),
  }),
};
