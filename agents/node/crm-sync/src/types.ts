/**
 * The CRM domain model: what's stored in data\crm.json.
 *
 * LEARN: These are TypeScript TYPES. They exist only at compile time; the
 * compiler checks every read and write against them, then erases them.
 * Runtime checks on incoming JSON are done separately by Zod (contract.ts),
 * because types can't validate data that arrives over the network.
 */

export type TaskStatus = "open" | "done";
export type TaskOwner = "advisor" | "client";
export type NoteType = "meeting" | "call" | "email" | "ai_summary" | "other";

export interface Member {
  name: string;
  role: "primary" | "spouse" | "dependent";
  age: number;
  email?: string;
  phone?: string;
}

export interface Preferences {
  contact_channel: "email" | "phone";
  communication_style: string;
  salutation: string;
}

export interface Account {
  account_id: string;
  type: "taxable" | "ira";
}

export interface Task {
  task_id: string;
  title: string;
  owner: TaskOwner;
  due?: string;
  status: TaskStatus;
  created: string;
  created_by?: string;
  completed?: string;
  completed_by?: string;
}

export interface Note {
  note_id: string;
  date: string;
  type: NoteType;
  author: string;
  text: string;
  trace_id?: string;
}

export interface Household {
  household: string;
  segment: string;
  advisor_id: string;
  members: Member[];
  preferences: Preferences;
  accounts: Account[];
  last_contact: string;
  next_review: string;
  service_alerts: string[];
  tasks: Task[];
  notes: Note[];
}

export interface CrmData {
  note?: string;
  next_ids: { task: number; note: number };
  households: Record<string, Household>;
  idempotency: Record<string, unknown>;
}

/** What other agents get back from get_household (contacts masked). */
export interface HouseholdView {
  client_id: string;
  household: string;
  segment: string;
  members: Array<{ name: string; role: Member["role"]; age: number; email: string | null; phone: string | null }>;
  preferences: Preferences;
  accounts: Account[];
  last_contact: string;
  next_review: string;
  service_alerts: string[];
  open_tasks: TaskView[];
  overdue_tasks: number;
  recent_notes: Note[];
}

export interface TaskView extends Task {
  overdue: boolean;
}
