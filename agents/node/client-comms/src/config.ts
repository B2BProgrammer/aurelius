/**
 * Herald settings, read from aurelius\.env (shared) and client-comms\.env (overrides).
 */
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const VERSION = "0.1.0";

const HERE = dirname(fileURLToPath(import.meta.url));
export const AGENT_DIR = resolve(HERE, "..");                    // ...\client-comms
export const REPO_ROOT = resolve(AGENT_DIR, "..", "..", "..");    // ...\aurelius

const WEAK = new Set(["", "replace-me", "replace-with-long-random-string"]);

export interface Config {
  port: number;
  host: string;
  serviceToken: string;
  /** Where the Liaison (CRM agent) lives. The Herald calls it for household details. */
  liaisonUrl: string;
  liaisonTimeoutMs: number;
  anthropicApiKey: string;
  llmModel: string;
  llmMock: boolean;
  /** Sign-off placed at the end of every draft; the advisor edits it before sending. */
  signature: string;
  maxPurposeChars: number;
  maxEmailChars: number;
  /** Draft log: one line per draft (ids, rule hits, SHA-256 of the body; never the text). */
  auditFile: string;
  /** Injected clock so tests get predictable dates. */
  today: () => string;
}

export function loadEnvFiles(): void {
  for (const file of [join(AGENT_DIR, ".env"), join(REPO_ROOT, ".env")]) {
    if (existsSync(file)) process.loadEnvFile(file);
  }
}

export function getConfig(overrides: Partial<Config> = {}): Config {
  const env = process.env;
  return {
    port: Number(env["HERALD_PORT"] ?? 8101),
    host: env["HERALD_HOST"] ?? "127.0.0.1",
    serviceToken: env["SERVICE_TOKEN"] ?? "",
    liaisonUrl: env["LIAISON_URL"] ?? "http://127.0.0.1:8102",
    liaisonTimeoutMs: Number(env["LIAISON_TIMEOUT_MS"] ?? 5000),
    anthropicApiKey: env["ANTHROPIC_API_KEY"] ?? "",
    llmModel: env["LLM_MODEL"] ?? "claude-haiku-4-5-20251001",
    llmMock: (env["LLM_MOCK"] ?? "").toLowerCase() === "true",
    signature: (env["ADVISOR_SIGNATURE"] ?? "[Your name]\\nAurelius Wealth").replaceAll("\\n", "\n"),
    maxPurposeChars: Number(env["MAX_PURPOSE_CHARS"] ?? 2000),
    maxEmailChars: Number(env["MAX_EMAIL_CHARS"] ?? 10000),
    auditFile: env["HERALD_AUDIT_FILE"] ?? join(AGENT_DIR, "logs", "drafts.jsonl"),
    today: () => new Date().toISOString().slice(0, 10),
    ...overrides,
  };
}

export function useLlm(config: Config): boolean {
  return !config.llmMock && !WEAK.has(config.anthropicApiKey) && config.anthropicApiKey.length > 0;
}

/** Fail closed: never start with a guessable token. */
export function checkStartupSecurity(config: Config): void {
  if (WEAK.has(config.serviceToken) || config.serviceToken.length < 24) {
    throw new Error(
      "SERVICE_TOKEN is missing or too short (need 24+ chars) in aurelius\\.env. " +
        "Use the same value as the other agents.",
    );
  }
}
