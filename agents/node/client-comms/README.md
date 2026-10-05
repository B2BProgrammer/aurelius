# 📣 Herald: client-comms

| Field | Value |
|---|---|
| Codename | Herald |
| Code ID | `herald` |
| Language | **TypeScript** (strict) on Node.js 20.12+ · Express 5 · Zod 4 · Anthropic SDK |
| Port | 8101 |
| Swagger UI | **http://localhost:8101/docs** (OpenAPI 3.1 at `/openapi.json`) |
| Calls | **Liaison** (:8102) `get_household`, and Claude Haiku 4.5 (optional) |
| Called by | Conductor (`draft_email`), later the Atrium UI (`review_email`) |
| Auth | `Bearer SERVICE_TOKEN` |
| Writes data? | **No.** It never sends email and never changes the CRM. It only logs a fingerprint per draft. |

## What the Herald does

It writes client emails **for the advisor to approve**, and checks emails the advisor wrote.

| Skill | Input | Example |
|---|---|---|
| `draft_email` | `client_id`, `purpose`, `points?` (≤8), `tone?` (warm/formal/brief) | "Follow up on today's review" for the Patels → "Hi Raj and Anita," short and plain, their open tasks, the review date |
| `review_email` | `text`, `client_id?` | Removes "risk-free", masks an SSN, adds the risk disclosure, warns that the Chens prefer phone |

## The pipeline (`src/compose/composer.ts`)

```
draft_email
  1. Liaison get_household      ── HTTP, same token, same trace_id, 5 s timeout, 1 retry
       └─ down? -> generic "Hello," draft + warning   (graceful degradation)
       └─ unknown client? -> error                     (never a generic email to nobody)
  2. intent (from purpose) + tone (from the household's style note)
  3. TEMPLATE draft             ── code: names, dates and tasks are always right
  4. Claude rewrites it         ── forced tool call, Zod-validated, falls back to 3
  5. COMPLIANCE pass            ── code: promises removed, PII masked, disclosure added
  6. warnings + requires_approval: true
```

**Code computes, the LLM writes** (same idea as the Analyst): the facts come from the CRM through code; Claude only improves the wording, and code checks whatever Claude wrote.

## Security principles in this agent

| Principle | Where |
|---|---|
| **Human in the loop**: no send skill exists; every result has `requires_approval: true` | `skills/index.ts` |
| **Defense in depth**: the Sentinel's compliance rules ported to TS and run on every draft, even though the Conductor also guards output | `compose/compliance.ts` |
| **Minimum necessary**: Claude gets names, style, dates, task titles; no emails, phones, accounts. The whole prompt is PII-redacted | `compose/llm.ts` `buildPrompt` |
| **Untrusted text is data**: the advisor's text goes in `<advisor_request>` tags; the system prompt says to ignore instructions in it | `compose/llm.ts` |
| **Validate LLM output**: forced `write_email` tool + Zod schema; bad output → template | `compose/llm.ts` |
| **Fail closed on startup**: weak `SERVICE_TOKEN` → refuses to start | `config.ts` |
| **Constant-time token check** | `auth.ts` |
| **Input limits**: `client_id` regex, purpose ≤ 2000 chars, body ≤ 64 KB | `contract.ts`, `app.ts` |
| **Audit without data**: `logs\drafts.jsonl` stores trace, user, rules fired and a SHA-256 fingerprint, never the email text | `audit.ts` |
| **Warn on what code can't fix**: links, leftover `[placeholders]`, phone-preferring households, open service alerts | `compliance.ts`, `composer.ts` |

## Folder map

```
client-comms/
├─ src/
│  ├─ server.ts            ENTRY POINT: config -> Liaison client -> Claude writer -> composer -> app
│  ├─ app.ts               Express: /health, agent card, /invoke, /v1/rules, Swagger
│  ├─ openapi.ts           OpenAPI 3.1 doc built from the Zod schemas + skills table
│  ├─ config.ts            .env loading, settings, fail-closed check
│  ├─ contract.ts          Zod: agent contract, skill inputs, Claude's output schema
│  ├─ types.ts             HouseholdInfo (from the Liaison), DraftResult
│  ├─ auth.ts  logger.ts  audit.ts
│  ├─ clients/liaison.ts   agent-to-agent call (fetch + token + trace + timeout + retry)
│  ├─ compose/
│  │  ├─ composer.ts       THE PIPELINE (read this first)
│  │  ├─ templates.ts      intent, tone, template draft
│  │  ├─ llm.ts            Claude: forced tool call, redacted prompt
│  │  └─ compliance.ts     rules (ported from the Sentinel)
│  └─ skills/index.ts      draft_email, review_email (+ Swagger examples)
├─ tests/                  45 tests: fake Liaison (real HTTP) + fake Claude (no network)
├─ api-tests.http          20 requests for VS Code REST Client
├─ TESTING.md              start & test runbook
├─ tsconfig.json  tsconfig.build.json  package.json  .env.example
```

TypeScript setup is identical to the Liaison (see its README): strict mode, `"type": "module"` (imports end in `.js`), TypeScript 7 needs `"types": ["node"]`, `npm run dev` = tsx, `npm start` = tsc → `dist` → node.

## LLM or not?

| `aurelius\.env` | `/health` → `mode` | Drafts |
|---|---|---|
| `LLM_MOCK=true` or no `ANTHROPIC_API_KEY` | `template` | Template; `[Add your key points]` placeholder when you give no `points` |
| real key, `LLM_MOCK=false` | `llm (claude-haiku-4-5-20251001)` | Claude rewrites in the household's voice; ~1 call per draft (a fraction of a cent on Haiku) |

Set `ADVISOR_SIGNATURE=Sam Rivera\nAurelius Wealth` in `aurelius\.env` to replace the `[Your name]` sign-off.
