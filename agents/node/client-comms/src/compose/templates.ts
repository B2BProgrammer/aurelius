/**
 * Template drafting: no LLM, fully predictable.
 *
 * LEARN: The template is not just a fallback for when Claude is down. It's
 * also the STARTING POINT we give Claude, so the facts (names, dates, open
 * tasks) come from the CRM via code, and Claude only improves the wording.
 * Same idea as the Analyst: code computes, the LLM writes.
 */
import type { HouseholdInfo, Intent } from "../types.js";

export type Tone = "warm" | "formal" | "brief";

const INTENT_RULES: Array<[Intent, RegExp]> = [
  ["meeting_follow_up", /\b(follow[- ]?up|recap|after (?:our|the|today'?s) (?:meeting|call|review)|summary of (?:our|the))\b/i],
  ["scheduling", /\b(schedul\w*|reschedul\w*|book\w*|availability|set up a (?:call|meeting)|find a time)\b/i],
  ["thank_you", /\b(thank\w*|referr\w*|appreciat\w*)\b/i],
  ["meeting_prep", /\b(review|upcoming|prepar\w*|agenda|before (?:our|the) (?:meeting|call))\b/i],
];

export function detectIntent(purpose: string): Intent {
  for (const [intent, pattern] of INTENT_RULES) if (pattern.test(purpose)) return intent;
  return "check_in";
}

/** The household's style note decides the default tone; the advisor can override it. */
export function toneFromStyle(style: string | undefined): Tone {
  if (!style) return "warm";
  if (/\bformal\b/i.test(style)) return "formal";
  if (/\b(short|brief|concise|plain)\b/i.test(style)) return "brief";
  return "warm";
}

export function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { timeZone: "UTC", weekday: "long", month: "long", day: "numeric" });
}

const SUBJECTS: Record<Intent, (h: HouseholdInfo | null) => string> = {
  meeting_follow_up: () => "Following up on our conversation",
  meeting_prep: (h) => (h?.next_review ? `Your upcoming review on ${formatDate(h.next_review)}` : "Your upcoming review"),
  scheduling: () => "Finding a time to talk",
  thank_you: () => "Thank you",
  check_in: () => "Checking in",
};

const OPENINGS: Record<Intent, Record<Tone, string>> = {
  meeting_follow_up: {
    warm: "Thank you for taking the time to meet with me. Here is a short recap of what we discussed.",
    formal: "Thank you for meeting with me. Please find below a brief summary of our discussion.",
    brief: "Thanks for meeting. Quick recap:",
  },
  meeting_prep: {
    warm: "I'm looking forward to our upcoming review and wanted to share what I'd like us to cover.",
    formal: "In preparation for our upcoming review, I would like to share the topics I propose we cover.",
    brief: "Ahead of our review, here's what I'd like to cover:",
  },
  scheduling: {
    warm: "I'd love to find a time for us to catch up.",
    formal: "I would like to arrange a time for us to speak.",
    brief: "Can we find a time to talk?",
  },
  thank_you: {
    warm: "I wanted to say a sincere thank you.",
    formal: "I would like to extend my sincere thanks.",
    brief: "A quick thank you.",
  },
  check_in: {
    warm: "I hope all is well. I wanted to check in.",
    formal: "I hope this message finds you well. I am writing to check in.",
    brief: "Quick check-in.",
  },
};

export const KEY_POINTS_PLACEHOLDER = "[Add your key points]";

const CLOSINGS: Record<Tone, string> = { warm: "Warm regards,", formal: "Kind regards,", brief: "Thanks," };

export interface TemplateInput {
  purpose: string;
  points: string[];
  intent: Intent;
  tone: Tone;
  household: HouseholdInfo | null;
  signature: string;
}

export function greeting(h: HouseholdInfo | null, tone: Tone): string {
  const name = h?.preferences.salutation;
  if (!name) return tone === "formal" ? "Dear Client," : "Hello,";
  return tone === "formal" ? `Dear ${name},` : `Hi ${name},`;
}

export function templateDraft(t: TemplateInput): { subject: string; body: string } {
  const h = t.household;
  const parts: string[] = [greeting(h, t.tone), OPENINGS[t.intent][t.tone]];

  // The purpose is an INSTRUCTION ("draft a follow-up to the Patels"), not email text,
  // so the template never pastes it in. Points are content; without them, leave a
  // placeholder (Claude fills it from the purpose; otherwise the advisor gets a warning).
  if (t.points.length === 0) parts.push(KEY_POINTS_PLACEHOLDER);
  else parts.push(t.points.map((p) => `- ${sentence(p)}`).join("\n"));

  if (h && (t.intent === "meeting_follow_up" || t.intent === "meeting_prep")) {
    const clientTasks = h.open_tasks.filter((x) => x.owner === "client");
    const advisorTasks = h.open_tasks.filter((x) => x.owner === "advisor");
    if (clientTasks.length) {
      parts.push(`A friendly reminder of the items on your side:\n${clientTasks.map((x) => `- ${sentence(x.title)}`).join("\n")}`);
    }
    if (advisorTasks.length) {
      parts.push(`On my side, I'm working on:\n${advisorTasks.map((x) => `- ${sentence(x.title)}`).join("\n")}`);
    }
  }
  if (h?.next_review && t.intent !== "thank_you") {
    parts.push(t.intent === "scheduling"
      ? `Our next review is currently set for ${formatDate(h.next_review)}. Let me know if another time works better.`
      : `Our next review is on ${formatDate(h.next_review)}.`);
  }
  parts.push(t.tone === "brief" ? "Let me know if you have any questions."
    : "Please don't hesitate to reach out if you have any questions.");
  parts.push(`${CLOSINGS[t.tone]}\n${t.signature}`);

  return { subject: SUBJECTS[t.intent](h), body: parts.join("\n\n") };
}

/** "send the trust paperwork" -> "Send the trust paperwork." */
function sentence(text: string): string {
  const s = text.trim();
  const capped = s.charAt(0).toUpperCase() + s.slice(1);
  return /[.!?]$/.test(capped) ? capped : `${capped}.`;
}
