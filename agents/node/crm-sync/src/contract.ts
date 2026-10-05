/**
 * The agent contract and the skill inputs, as Zod schemas.
 *
 * LEARN: one Zod schema gives you THREE things:
 *   1. runtime validation   Schema.safeParse(json)
 *   2. a TypeScript type    z.infer<typeof Schema>   (no duplicate interface to keep in sync)
 *   3. a JSON Schema        z.toJSONSchema(Schema)   (used for Swagger and the agent card)
 * AgentRequest/AgentResponse are the SAME JSON shapes the Python agents use,
 * so the Python Conductor can call this TypeScript agent unchanged.
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
export type AgentRequest = z.infer<typeof AgentRequest>;

export interface AgentResponse<T = unknown> {
  agent: "liaison";
  status: "ok" | "error";
  output: T | Record<string, never>;
  error: string | null;
}

export const ok = <T>(output: T): AgentResponse<T> => ({ agent: "liaison", status: "ok", output, error: null });
export const fail = (error: string): AgentResponse => ({ agent: "liaison", status: "error", output: {}, error });

// ------------------------------------------------------------------ skill inputs
export const ClientId = z
  .string()
  .regex(/^[A-Za-z0-9_-]{1,64}$/, "must be 1-64 letters, digits, '-' or '_'")
  .describe("Client household id, e.g. patel-001");
const IsoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "must be YYYY-MM-DD");
const IdempotencyKey = z
  .string()
  .min(8)
  .max(128)
  .optional()
  .describe("Optional. Same key = same result, never a duplicate write");

export const GetHouseholdInput = z.object({ client_id: ClientId });

export const ListTasksInput = z.object({
  client_id: ClientId,
  status: z.enum(["open", "done", "all"]).default("open"),
});

export const AddTaskInput = z.object({
  client_id: ClientId,
  title: z.string().trim().min(3).max(200),
  owner: z.enum(["advisor", "client"]).default("advisor"),
  due: IsoDate.optional(),
  idempotency_key: IdempotencyKey,
});

export const CompleteTaskInput = z.object({
  client_id: ClientId,
  task_id: z.string().regex(/^T-\d{1,10}$/, "must look like T-1234"),
  idempotency_key: IdempotencyKey,
});

export const LogNoteInput = z.object({
  client_id: ClientId,
  note: z.string().trim().min(3),
  type: z.enum(["meeting", "call", "email", "ai_summary", "other"]).default("other"),
  idempotency_key: IdempotencyKey,
});

export type GetHouseholdInput = z.infer<typeof GetHouseholdInput>;
export type ListTasksInput = z.infer<typeof ListTasksInput>;
export type AddTaskInput = z.infer<typeof AddTaskInput>;
export type CompleteTaskInput = z.infer<typeof CompleteTaskInput>;
export type LogNoteInput = z.infer<typeof LogNoteInput>;

/** "invalid input: note Too small: expected string to have >=3 characters" */
export function describeZodError(error: z.ZodError): string {
  const issue = error.issues[0];
  if (!issue) return "invalid input";
  return `invalid input: ${issue.path.join(".") || "(root)"} ${issue.message}`;
}
