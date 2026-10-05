# 🤝 Liaison — crm-sync

| Field | Value |
|---|---|
| Codename | Liaison |
| Code ID | `liaison` |
| Language | **TypeScript** (strict) on Node.js 20.12+ · Express 5 · Zod 4 |
| Port | 8102 |
| Swagger UI | **http://localhost:8102/docs** (OpenAPI 3.1 at `/openapi.json`) |
| Data | `data\crm.json`, created from `data\crm.seed.json` on first start (stands in for Salesforce / Dynamics / Wealthbox) |
| Called by | Conductor (`get_household`, `log_note`), later the Herald |
| Auth | `Bearer SERVICE_TOKEN` |

## What the Liaison does

It's the swarm's single door into the CRM: who's in the household, how they like to be contacted, open and overdue tasks, recent notes. It also **writes back**: logging notes and creating and completing tasks.

| Skill | Reads/Writes | Example |
|---|---|---|
| `get_household` | read | Patel: Raj (58) & Anita (56), prefers short emails, **2 overdue tasks**, last 3 notes |
| `list_tasks` | read | Open / done / all tasks with `overdue` flags |
| `add_task` | **write** | "Send wedding savings options" due 2026-10-15 |
| `complete_task` | **write** | Mark T-1002 done |
| `log_note` | **write** | Save a call note; masks SSNs and account numbers first |

## TypeScript setup

| File | Purpose |
|---|---|
| `tsconfig.json` | Base config for the editor and `npm run typecheck`: covers `src`, `tests`, `scripts`; **no output** |
| `tsconfig.build.json` | Extends the base; compiles **only `src` → `dist`** for `npm start` |
| `package.json` → `"type": "module"` | Real ES modules; that's why imports end in `.js` even in `.ts` files (they point at the compiled file) |

Strictness turned on (all explained inline in `tsconfig.json`): `strict`, `noUncheckedIndexedAccess` (`obj[key]` might be `undefined`), `exactOptionalPropertyTypes`, `noImplicitReturns`, `noUnusedLocals/Parameters`, `useUnknownInCatchVariables`, `verbatimModuleSyntax` (`import type` for types).

**TypeScript 7 note:** it no longer auto-loads `@types/*` packages, so `"types": ["node"]` is listed explicitly. Leave it out and you get "Cannot find name 'process'".

**How code runs:**
- `npm run dev` runs the `.ts` files directly with **tsx** (fast, restarts on save, no build step)
- `npm start` runs **tsc** (`src/*.ts` → `dist/*.js`), then `node dist/server.js`: what production runs
- `npm test` runs the `.ts` tests with Node's built-in test runner via tsx

**Types vs. validation:** TypeScript types (`src/types.ts`) are checked at **compile time** and erased. JSON arriving over HTTP can't be trusted by types alone, so **Zod** (`src/contract.ts`) validates it at **runtime**. Each Zod schema also produces the TypeScript type (`z.infer`) and the Swagger schema (`z.toJSONSchema`), so one definition serves three purposes.

## Swagger

FastAPI generates Swagger automatically. Express doesn't, so `src/openapi.ts` builds an **OpenAPI 3.1** document from the **same Zod schemas and the same skills table** the code uses, and `swagger-ui-express` serves it at `/docs`. A test sends every Swagger example to the real API, so the docs can't drift from the code.

In the browser: **Authorize** (SERVICE_TOKEN) → **POST /invoke** → **Try it out** → choose from the **Examples** dropdown (all 5 skills) → **Execute**.

## New lesson: writing data safely

1. **Atomic writes**: write `crm.json.tmp`, then rename over `crm.json`. A crash can never leave a half-written file. (On Windows, a brief OneDrive/antivirus lock is retried automatically.)
2. **One writer at a time**: all writes go through a queue: ten simultaneous requests get ten unique IDs (a test proves it).
3. **Idempotency**: the Conductor **retries** failed calls. Each write gets a key (your `idempotency_key`, or one derived from `trace_id` + input). Same key, same result, `duplicate: true`, nothing written twice.
4. **Audit trail**: every write goes to `logs\audit.jsonl` (trace, user, skill, ids), never the note text.
5. **No deletes**: there is no delete skill. CRM history is a record.

## Same contract, different language

| Concept | Python agents | Liaison (TypeScript) |
|---|---|---|
| Web framework | FastAPI | Express 5 |
| Validation + types | Pydantic | Zod (`z.infer` for types) |
| Swagger | automatic | `openapi.ts` + swagger-ui-express |
| Settings / .env | pydantic-settings | `process.loadEnvFile()` (Node 20.12+) |
| Constant-time compare | `hmac.compare_digest` | `crypto.timingSafeEqual` |
| Packages | `pip`, `requirements.txt`, `.venv` | `npm`, `package.json`, `node_modules` |
| Tests | pytest | `node:test` + tsx |
| Run | `python src\main.py` | `npm start` / `npm run dev` |

## Folder map

```
crm-sync/
├── src/                      (all TypeScript)
│   ├── server.ts             ▶ ENTRY POINT
│   ├── app.ts                endpoints, Swagger mount, headers, errors
│   ├── openapi.ts            OpenAPI 3.1 document (from Zod + skills)
│   ├── contract.ts           Zod schemas: agent contract + skill inputs (+ inferred types)
│   ├── types.ts              domain model: Household, Task, Note...
│   ├── skills/
│   │   ├── index.ts          ★ the 5 skills (start here)
│   │   └── views.ts          what other agents may see (masked contacts)
│   ├── store/crmStore.ts     ★ atomic, serialized, idempotent writes
│   ├── audit.ts · auth.ts · config.ts · logger.ts
├── tests/                    api.test.ts, openapi.test.ts, helpers.ts (32 tests)
├── scripts/reset-data.ts     npm run reset-data
├── data/crm.seed.json        sample households
├── tsconfig.json · tsconfig.build.json · package.json
├── dist/                     compiled JavaScript (created by npm start / npm run build; git-ignored)
├── api-tests.http · TESTING.md
```

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/docs` | none to view | **Swagger UI** |
| GET | `/openapi.json` | none | OpenAPI 3.1 document |
| GET | `/health` | none | Alive + household count |
| GET | `/.well-known/agent.json` | none | Agent card with JSON schemas |
| POST | `/invoke` | service | The 5 skills |
| GET | `/v1/households` | service | List households |
| GET | `/v1/households/{clientId}` | service | One household |

## Security principles in this agent

1. **Minimum necessary**: emails and phones are masked in everything agents receive.
2. **No sensitive data in free text**: SSNs and account/card numbers in notes are masked before saving.
3. **Safe writes**: atomic, serialized, idempotent, audited; no delete operation.
4. **Validation**: Zod on every input; strict IDs and dates; 64 KB body limit; 5,000-character notes.
5. **Fail closed**: weak `SERVICE_TOKEN` and it won't start.
6. **Quiet errors**: no stack traces to callers, no `X-Powered-By` banner.
7. **Type safety**: strict TypeScript catches whole classes of bugs (undefined lookups, typos in field names) before the code runs.
