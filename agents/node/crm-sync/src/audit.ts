/**
 * Audit log for every WRITE: who, when, which trace, what changed (ids only).
 * The note text itself is never logged; it lives only in the CRM.
 */
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

export interface AuditEntry {
  trace_id: string;
  user_id: string;
  skill: string;
  client_id: string;
  duplicate: boolean;
  ids: { note_id?: string | undefined; task_id?: string | undefined };
}

export class AuditLog {
  constructor(private readonly file: string) {
    mkdirSync(dirname(file), { recursive: true });
  }

  record(entry: AuditEntry): void {
    appendFileSync(this.file, JSON.stringify({ ts: new Date().toISOString(), ...entry }) + "\n");
  }
}
