/**
 * Draft log: one JSON line per draft or review.
 *
 * LEARN: For client communications, regulators expect a record of what was
 * prepared. We log WHO / WHEN / WHICH trace / which rules fired, plus a SHA-256
 * fingerprint of the body. The fingerprint proves later which exact text was
 * produced, without storing client details in a log file.
 */
import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

export interface DraftAuditEntry {
  trace_id: string;
  user_id: string;
  skill: string;
  client_id: string;
  intent?: string;
  drafted_by?: string;
  fixes: string[];
  warnings: number;
  body: string;   // hashed, never written
}

export const fingerprint = (text: string): string => createHash("sha256").update(text).digest("hex").slice(0, 16);

export class AuditLog {
  constructor(private readonly file: string) {
    mkdirSync(dirname(file), { recursive: true });
  }

  record({ body, ...rest }: DraftAuditEntry): void {
    const line = { ts: new Date().toISOString(), ...rest, body_sha256: fingerprint(body), body_chars: body.length };
    appendFileSync(this.file, JSON.stringify(line) + "\n");
  }
}
