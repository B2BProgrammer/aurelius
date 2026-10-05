/**
 * Compliance pass for every email, whoever wrote it (template, Claude, or the advisor).
 *
 * LEARN: These are the SAME rules the Sentinel enforces (compliance.py),
 * ported to TypeScript. Why check here too, if the Conductor already sends
 * output through the Sentinel? DEFENSE IN DEPTH: the Herald can also be
 * called directly (Swagger, another agent), and a client email is the riskiest
 * thing the swarm produces. Code decides; it doesn't ask the LLM "is this ok?".
 */
import type { ComplianceReport } from "../types.js";

interface Rule { id: string; pattern: RegExp; description: string }

// 1. Promissory claims: removed.
export const PROMISSORY_RULES: Rule[] = [
  { id: "CMP_GUARANTEE", description: "Guaranteed returns/income",
    pattern: /\bguarantee(?:d|s)?\b(?:\s+\w+){0,3}\s+(?:returns?|income|profits?|gains?|growth|performance)\b|\b(?:returns?|income|profits?|gains?)\s+(?:are|is)\s+guaranteed\b/gi },
  { id: "CMP_NO_RISK", description: "Claims an investment has no risk",
    pattern: /\b(?:risk[- ]free|no risk|zero risk|without any risk|can(?:no|')t lose|cannot lose|safe bet)\b/gi },
  { id: "CMP_CERTAINTY", description: "Predicts market moves with certainty",
    pattern: /\b(?:will definitely|certain to|sure to|bound to)\s+(?:go up|rise|increase|outperform|double|grow)\b/gi },
];
export const REPLACEMENT = "[removed: non-compliant claim]";

// 2. Sensitive identifiers: masked. Email is not a secure channel.
export const PII_RULES: Rule[] = [
  { id: "PII_SSN", description: "Social Security number", pattern: /\b\d{3}-\d{2}-\d{4}\b/g },
  { id: "PII_CARD", description: "Card number", pattern: /\b(?:\d[ -]?){15}\d\b/g },
  { id: "PII_ACCOUNT", description: "Full account number (8-17 digits)", pattern: /(?<![\d$,.])\d{8,17}(?!\d|,\d|\.\d)/g },
];

// 3. Disclosure: required when the email talks about performance.
export const EMAIL_DISCLOSURE =
  "Investments involve risk, including possible loss of principal. " +
  "Past performance and projections do not guarantee future results.";
const PERFORMANCE_WORDS = /\b(?:returns?|performance|projections?|projected|probability|yield|outperform\w*|gains?|growth rate)\b/i;

// 4. Things code can't fix: the advisor must look.
const LINK = /\bhttps?:\/\/\S+|\bwww\.\S+/i;
const PLACEHOLDER = /\[(?!removed: |SSN|CARD|ACCOUNT)[A-Za-z ]{2,30}\]/;   // e.g. "[client name]" left in

export interface ComplianceResult { text: string; report: ComplianceReport }

export function checkEmail(input: string, opts: { signature?: string } = {}): ComplianceResult {
  const fixes: string[] = [];
  const warnings: string[] = [];
  let text = input;

  for (const rule of PROMISSORY_RULES) {
    text = text.replace(rule.pattern, () => { fixes.push(rule.id); return REPLACEMENT; });
  }
  for (const rule of PII_RULES) {
    const label = rule.id.replace("PII_", "");
    text = text.replace(rule.pattern, () => { fixes.push(rule.id); return `[${label}]`; });
  }

  let disclosureAdded = false;
  // Check the ORIGINAL too: removing "guaranteed returns" must not also remove the disclosure.
  if ((PERFORMANCE_WORDS.test(input) || PERFORMANCE_WORDS.test(text)) && !text.includes("possible loss of principal")) {
    text = `${text.trimEnd()}\n\n${EMAIL_DISCLOSURE}`;
    disclosureAdded = true;
  }

  if (fixes.some((f) => f.startsWith("CMP_"))) {
    warnings.push("A promise about returns or risk was removed. Rewrite that sentence before sending.");
  }
  if (fixes.some((f) => f.startsWith("PII_"))) {
    warnings.push("Sensitive numbers were masked. Never send SSNs or full account numbers by email.");
  }
  if (LINK.test(text)) warnings.push("The email contains a link. Check it points where you expect.");
  const signatureLines = (opts.signature ?? "").split("\n");
  const withoutSignature = signatureLines.reduce((t, line) => (line ? t.replaceAll(line, "") : t), text);
  if (PLACEHOLDER.test(withoutSignature)) warnings.push("The email still has a [placeholder]. Fill it in.");

  return { text, report: { fixes: [...new Set(fixes)], disclosure_added: disclosureAdded, warnings } };
}

/** Mask PII in text BEFORE it goes to the LLM (minimum necessary). */
export function redactForLlm(text: string): string {
  return PII_RULES.reduce((t, r) => t.replace(r.pattern, `[${r.id.replace("PII_", "")}]`), text);
}

export function listRules(): Array<{ id: string; action: string; description: string }> {
  return [
    ...PROMISSORY_RULES.map((r) => ({ id: r.id, action: "remove", description: r.description })),
    ...PII_RULES.map((r) => ({ id: r.id, action: "mask", description: r.description })),
    { id: "CMP_DISCLOSURE_EMAIL", action: "append", description: "Risk disclosure when the email mentions performance" },
    { id: "WARN_LINK", action: "warn", description: "Email contains a link" },
    { id: "WARN_PLACEHOLDER", action: "warn", description: "Unfilled [placeholder] left in the text" },
  ];
}
