/**
 * Liaison settings, read from aurelius\.env (shared) and crm-sync\.env (overrides).
 *
 * LEARN: Node 20.12+ reads .env files natively with process.loadEnvFile(), so
 * no "dotenv" package is needed. Secrets come from the environment, never code.
 */
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const VERSION = "0.2.0";

// src/config.ts (dev, via tsx) and dist/config.js (built) are both one level below the agent folder
const HERE = dirname(fileURLToPath(import.meta.url));
export const AGENT_DIR = resolve(HERE, "..");                    // ...\crm-sync
export const REPO_ROOT = resolve(AGENT_DIR, "..", "..", "..");    // ...\aurelius

const WEAK = new Set(["", "replace-me", "replace-with-long-random-string"]);

export interface Config {
  port: number;
  host: string;
  serviceToken: string;
  dataFile: string;
  seedFile: string;
  auditFile: string;
  maxNoteChars: number;
  /** Today's date as YYYY-MM-DD. A function so tests can freeze the clock. */
  today: () => string;
}

export function loadEnvFiles(): void {
  // the agent's own .env first, so it wins (loadEnvFile never overwrites a variable already set)
  for (const file of [join(AGENT_DIR, ".env"), join(REPO_ROOT, ".env")]) {
    if (existsSync(file)) process.loadEnvFile(file);
  }
}

export function getConfig(overrides: Partial<Config> = {}): Config {
  const env = process.env;
  return {
    port: Number(env["LIAISON_PORT"] ?? 8102),
    host: env["LIAISON_HOST"] ?? "127.0.0.1",
    serviceToken: env["SERVICE_TOKEN"] ?? "",
    dataFile: env["CRM_DATA_FILE"] ?? join(AGENT_DIR, "data", "crm.json"),
    seedFile: join(AGENT_DIR, "data", "crm.seed.json"),
    auditFile: env["CRM_AUDIT_FILE"] ?? join(AGENT_DIR, "logs", "audit.jsonl"),
    maxNoteChars: Number(env["MAX_NOTE_CHARS"] ?? 5000),
    today: () => new Date().toISOString().slice(0, 10),
    ...overrides,
  };
}

/** Fail closed: never start an agent that can WRITE client data with a guessable token. */
export function checkStartupSecurity(config: Config): void {
  if (WEAK.has(config.serviceToken) || config.serviceToken.length < 24) {
    throw new Error(
      "SERVICE_TOKEN is missing or too short (need 24+ chars) in aurelius\\.env. " +
        "Use the same value as the other agents.",
    );
  }
}
