/**
 * The Liaison's skills: 2 reads + 3 writes.
 *
 * Each skill = { description, input (Zod schema), writes, example, run }.
 * /invoke looks the skill up, validates input with the schema, then calls run().
 * The same table also feeds the agent card and the Swagger page (openapi.ts),
 * so documentation can never drift away from the code.
 */
import { createHash } from "node:crypto";

import type { z } from "zod";

import type { Config } from "../config.js";
import {
  AddTaskInput, CompleteTaskInput, GetHouseholdInput, ListTasksInput, LogNoteInput,
  type InvokeContext,
} from "../contract.js";
import { type CrmStore, NotFoundError } from "../store/crmStore.js";
import type { Note, Task } from "../types.js";
import { householdView, taskView } from "./views.js";

export interface Deps {
  store: CrmStore;
  config: Config;
}

export interface Skill<S extends z.ZodType = z.ZodType> {
  description: string;
  input: S;
  writes: boolean;
  /** Example input shown in Swagger. */
  example: Record<string, unknown>;
  run: (input: z.infer<S>, ctx: InvokeContext, deps: Deps) => unknown;
}

/** Helper so each skill keeps its own precise input type. */
const skill = <S extends z.ZodType>(def: Skill<S>): Skill => def as unknown as Skill;

// Free-text notes must not hold sensitive identifiers (same rule as the Scribe's pii_in_notes flag).
const PII_IN_NOTES: Array<[string, RegExp]> = [
  ["SSN", /\b\d{3}-\d{2}-\d{4}\b/g],
  ["ACCOUNT_NUMBER", /(?<![\d$,.])\d{8,17}(?!\d|,\d|\.\d)/g],
  ["CARD_NUMBER", /\b(?:\d[ -]?){15}\d\b/g],
];

function maskNote(text: string): { text: string; masked: string[] } {
  const masked: string[] = [];
  // eslint-disable-next-line no-control-regex
  let out = text.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");
  for (const [label, pattern] of PII_IN_NOTES) {
    out = out.replace(pattern, () => {
      if (!masked.includes(label)) masked.push(label);
      return `[${label}]`;
    });
  }
  return { text: out, masked };
}

/** Explicit key if given; otherwise derived from trace + skill + input, so a RETRY is safe. */
function idempotencyKey(name: string, input: { idempotency_key?: string | undefined }, ctx: InvokeContext): string {
  if (input.idempotency_key) return `${name}:${input.idempotency_key}`;
  const { idempotency_key: _ignored, ...rest } = input;
  return `${name}:` + createHash("sha256").update(`${ctx.trace_id}|${JSON.stringify(rest)}`).digest("hex").slice(0, 32);
}

export const SKILLS: Record<string, Skill> = {
  get_household: skill({
    description: "Household profile: members (contacts masked), preferences, accounts, open tasks (with overdue flags), last 3 notes.",
    input: GetHouseholdInput,
    writes: false,
    example: { client_id: "patel-001" },
    run: ({ client_id }, _ctx, { store, config }) =>
      householdView(client_id, store.household(client_id), config.today()),
  }),

  list_tasks: skill({
    description: "Tasks for a household, filtered by status (open | done | all).",
    input: ListTasksInput,
    writes: false,
    example: { client_id: "patel-001", status: "all" },
    run: ({ client_id, status }, _ctx, { store, config }) => {
      const today = config.today();
      const tasks = store.household(client_id).tasks
        .filter((t) => status === "all" || t.status === status)
        .map((t) => taskView(t, today));
      return { client_id, status, count: tasks.length, tasks };
    },
  }),

  add_task: skill({
    description: "Create a task for the advisor or the client. Idempotent.",
    input: AddTaskInput,
    writes: true,
    example: { client_id: "patel-001", title: "Send wedding savings options", due: "2026-10-15",
               idempotency_key: "patel-wedding-options-001" },
    run: async (input, ctx, { store, config }) => {
      store.household(input.client_id); // not found -> error before any write
      const { result, duplicate } = await store.write(idempotencyKey("add_task", input, ctx), (data) => {
        const task: Task = {
          task_id: `T-${data.next_ids.task++}`, title: input.title, owner: input.owner,
          status: "open", created: config.today(), created_by: ctx.user_id,
          ...(input.due ? { due: input.due } : {}),
        };
        data.households[input.client_id]!.tasks.push(task);
        return { saved: true, task };
      });
      return { ...result, duplicate };
    },
  }),

  complete_task: skill({
    description: "Mark a task done. Idempotent: completing it twice is harmless.",
    input: CompleteTaskInput,
    writes: true,
    example: { client_id: "patel-001", task_id: "T-1002" },
    run: async (input, ctx, { store, config }) => {
      const h = store.household(input.client_id);
      if (!h.tasks.some((t) => t.task_id === input.task_id)) {
        throw new NotFoundError(`No task '${input.task_id}' for '${input.client_id}'`);
      }
      const { result, duplicate } = await store.write(idempotencyKey("complete_task", input, ctx), (data) => {
        const task = data.households[input.client_id]!.tasks.find((t) => t.task_id === input.task_id)!;
        const already = task.status === "done";
        if (!already) Object.assign(task, { status: "done", completed: config.today(), completed_by: ctx.user_id });
        return { saved: !already, already_done: already, task };
      });
      return { ...result, duplicate };
    },
  }),

  log_note: skill({
    description: "Save a note to the household's CRM record. SSNs/account numbers are masked. Idempotent.",
    input: LogNoteInput,
    writes: true,
    example: { client_id: "patel-001", type: "call",
               note: "Anita confirmed the wedding budget. Raj read out his SSN 123-45-6789." },
    run: async (input, ctx, { store, config }) => {
      if (input.note.length > config.maxNoteChars) {
        throw new RangeError(`note longer than ${config.maxNoteChars} characters`);
      }
      store.household(input.client_id);
      const { text, masked } = maskNote(input.note);
      const { result, duplicate } = await store.write(idempotencyKey("log_note", input, ctx), (data) => {
        const note: Note = {
          note_id: `N-${data.next_ids.note++}`, date: config.today(), type: input.type,
          author: ctx.user_id, text, trace_id: ctx.trace_id,
        };
        const h = data.households[input.client_id]!;
        h.notes.push(note);
        h.last_contact = note.date;
        return { saved: true, note_id: note.note_id, date: note.date, pii_masked: masked };
      });
      return { ...result, duplicate };
    },
  }),
};
