/**
 * The agent contract and the Herald's skill inputs/outputs, as Zod schemas.
 * Same JSON shapes as every other agent; one schema = validation + TS type + Swagger schema.
 */
import { z } from "zod";

// ------------------------------------------------------------------ contract
export const InvokeContext = z.object({
  trace_id: z.string().min(1).max(128).describe("Follows one request across every agent's logs"),
  user_id: z.string().min(1).max(128).describe("The advisor the request is for"),
  client_id: z.string().nullish().describe("Optional default client_id for the skill"),
});
export type InvokeContext = z.infer<typeof InvokeContext>;

export const AgentRequest = z.object({
  skill: z.string().min(1).max(64),
  input: z.record(z.string(), z.unknown()).default({}),
  context: InvokeContext,
});

export interface AgentResponse<T = unknown> {
  agent: "herald";
  status: "ok" | "error";
  output: T | Record<string, never>;
  error: string | null;
}

export const ok = <T>(output: T): AgentResponse<T> => ({ agent: "herald", status: "ok", output, error: null });
export const fail = (error: string): AgentResponse => ({ agent: "herald", status: "error", output: {}, error });

// ------------------------------------------------------------------ skill inputs
export const ClientId = z
  .string()
  .regex(/^[A-Za-z0-9_-]{1,64}$/, "must be 1-64 letters, digits, '-' or '_'")
  .describe("Client household id, e.g. patel-001");

export const Tone = z.enum(["warm", "formal", "brief"]).describe("Overrides the household's usual style");

export const DraftEmailInput = z.object({
  client_id: ClientId,
  purpose: z.string().trim().min(3).describe("What the email is for, in the advisor's words"),
  points: z.array(z.string().trim().min(2).max(300)).max(8).default([])
    .describe("Optional bullet points the email must cover"),
  tone: Tone.optional(),
});
export type DraftEmailInput = z.infer<typeof DraftEmailInput>;

export const ReviewEmailInput = z.object({
  text: z.string().trim().min(3).describe("An email the advisor wrote, to check before sending"),
  client_id: ClientId.optional(),
});
export type ReviewEmailInput = z.infer<typeof ReviewEmailInput>;

// ------------------------------------------------------------------ LLM output schema
/** The shape Claude must return (forced tool call). Validated before use. */
export const EmailDraftSchema = z.object({
  subject: z.string().min(3).max(120),
  body: z.string().min(20).max(4000),
});
export type EmailDraft = z.infer<typeof EmailDraftSchema>;

/** "invalid input: purpose Too small: expected string to have >=3 characters" */
export function describeZodError(error: z.ZodError): string {
  const issue = error.issues[0];
  if (!issue) return "invalid input";
  return `invalid input: ${issue.path.join(".") || "(root)"} ${issue.message}`;
}
