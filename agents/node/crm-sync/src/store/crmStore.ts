/**
 * The CRM data store: a JSON file (data\crm.json), created from crm.seed.json on first start.
 *
 * LEARN: This agent WRITES, and three things make writes safe:
 *
 * 1. ATOMIC WRITES: write crm.json.tmp, then rename it over crm.json. A rename
 *    is all-or-nothing, so a crash mid-write can never corrupt the file.
 * 2. ONE WRITER AT A TIME: every change goes through a queue (a promise chain),
 *    so two simultaneous requests can't both read the old data and overwrite
 *    each other's changes (a "lost update").
 * 3. IDEMPOTENCY: each write has a key. If the same key arrives again (the
 *    Conductor retries after a network hiccup), the first result is returned
 *    instead of writing a duplicate.
 *
 * In a real firm this class would call Salesforce / Dynamics / Wealthbox.
 * Nothing outside this file would change.
 */
import { copyFileSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import type { CrmData, Household } from "../types.js";

const MAX_IDEMPOTENCY_KEYS = 1000;

export class NotFoundError extends Error {
  override name = "NotFoundError";
}

export interface WriteResult<T> {
  result: T;
  duplicate: boolean;
}

/**
 * On Windows, OneDrive or antivirus can lock a file for a moment while syncing
 * or scanning it, so rename fails with EPERM/EBUSY. Retry briefly before giving up.
 */
function renameWithRetry(from: string, to: string, attempts = 5): void {
  for (let i = 1; ; i++) {
    try {
      renameSync(from, to);
      return;
    } catch (err: unknown) {
      const code = (err as NodeJS.ErrnoException).code ?? "";
      if (i >= attempts || !["EPERM", "EBUSY", "EACCES"].includes(code)) throw err;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50 * i); // short pause
    }
  }
}

export class CrmStore {
  private data: CrmData;
  private queue: Promise<unknown> = Promise.resolve();

  constructor(private readonly opts: { dataFile: string; seedFile: string }) {
    if (!existsSync(opts.dataFile)) {
      mkdirSync(dirname(opts.dataFile), { recursive: true });
      copyFileSync(opts.seedFile, opts.dataFile);
    }
    this.data = JSON.parse(readFileSync(opts.dataFile, "utf-8")) as CrmData;
    this.data.idempotency ??= {};
  }

  // ---------------------------------------------------------------- reads
  household(clientId: string): Household {
    const h = this.data.households[clientId];
    if (!h) throw new NotFoundError(`No household with id '${clientId}'`);
    return h;
  }

  clientIds(): string[] {
    return Object.keys(this.data.households);
  }

  // ---------------------------------------------------------------- writes
  /** Run `change(draft)` as one serialized, persisted, idempotent write. */
  write<T>(idempotencyKey: string, change: (draft: CrmData) => T): Promise<WriteResult<T>> {
    const run = async (): Promise<WriteResult<T>> => {
      const previous = this.data.idempotency[idempotencyKey];
      if (previous !== undefined) return { result: previous as T, duplicate: true };

      const draft = structuredClone(this.data);          // change a copy...
      const result = change(draft);
      draft.idempotency[idempotencyKey] = result;
      const keys = Object.keys(draft.idempotency);
      for (const k of keys.slice(0, Math.max(0, keys.length - MAX_IDEMPOTENCY_KEYS))) {
        delete draft.idempotency[k];                      // keep the most recent 1000
      }

      const tmp = `${this.opts.dataFile}.tmp`;            // ...write it atomically...
      writeFileSync(tmp, JSON.stringify(draft, null, 2));
      renameWithRetry(tmp, this.opts.dataFile);
      this.data = draft;                                  // ...then switch over in memory
      return { result, duplicate: false };
    };
    const next = this.queue.then(run, run);
    this.queue = next.catch(() => undefined);             // one failure must not block the queue
    return next;
  }
}
