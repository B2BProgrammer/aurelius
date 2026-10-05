# Liaison: Start & Test Runbook (TypeScript)

## 0. Node.js (once)

```powershell
node --version     # need v20.12 or newer (v22 LTS recommended)
npm --version
```
Not installed or too old? Install the **LTS** version from https://nodejs.org, then **open a new terminal**.

> There's no virtual environment in Node: each project's packages live in its own `node_modules` folder (`npm install` creates it). TypeScript itself is one of those packages, so you **don't** install it globally.

## 1. First-time setup

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\node\crm-sync
npm install          # express, zod, swagger-ui-express + typescript, tsx, @types/* (dev)
npm run typecheck    # tsc --noEmit: no output = no type errors
npm test             # expect: tests 32, pass 32
```

If PowerShell says `npm.ps1 cannot be loaded`: run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `npm.cmd ...`.

## 2. Start (pick one)

```powershell
npm start            # compiles TypeScript to dist\, then runs node dist\server.js
npm run dev          # runs the .ts directly with tsx and restarts on every save (best while learning)
```
✅ You'll see:
```
Liaison (crm-sync) on http://127.0.0.1:8102
Swagger UI:          http://127.0.0.1:8102/docs
```
On first start, `data\crm.json` is created from `data\crm.seed.json`.

## 3. Swagger (browser)

1. Open **http://localhost:8102/docs**
2. **Authorize** → paste the SERVICE_TOKEN (get it with `Select-String -Path ..\..\..\.env -Pattern '^SERVICE_TOKEN='`) → Authorize → Close
3. **POST /invoke** → **Try it out** → **Examples** dropdown → pick a skill → **Execute**

| Example | What to look for |
|---|---|
| `get_household` | masked emails/phones, `overdue_tasks: 2` |
| `list_tasks` | 3 tasks, T-1003 `done` |
| `log_note (writes)` | `pii_masked: ["SSN"]`. **Execute again**: same `note_id`, `duplicate: true` |
| `add_task (writes)` | new `T-11xx`. Execute again: same id (idempotency_key) |
| `complete_task (writes)` | T-1002 → `done`. Execute again: `already_done: true` |

Also try **GET /v1/households/{clientId}** with `garcia-003`.

## 4. VS Code / PowerShell

**VS Code:** `api-tests.http` (20 requests) → paste the token → **Send Request**.

**PowerShell** (Terminal 2):
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\node\crm-sync
$svc = ((Get-Content ..\..\..\.env | Where-Object { $_ -match '^SERVICE_TOKEN=' }) -split '=', 2)[1] -replace '\s+#.*$', ''
$h = @{ Authorization = "Bearer $svc" }

function Crm($skill, $inputObj, $trace = "ps-$(Get-Random)") {
    $body = @{ skill = $skill; input = $inputObj
               context = @{ trace_id = $trace; user_id = "dev-advisor" } } | ConvertTo-Json -Depth 6
    $r = Invoke-RestMethod http://localhost:8102/invoke -Method Post -Headers $h -ContentType "application/json" -Body $body
    if ($r.status -ne "ok") { "ERROR: $($r.error)" } else { $r.output }
}

$p = Crm get_household @{ client_id = "patel-001" }
$p.members    | Format-Table name, age, email, phone
$p.open_tasks | Format-Table task_id, title, due, overdue

Crm log_note @{ client_id = "patel-001"; type = "call"; note = "Anita confirmed budget. Raj SSN 123-45-6789." } "retry-demo"
Crm log_note @{ client_id = "patel-001"; type = "call"; note = "Anita confirmed budget. Raj SSN 123-45-6789." } "retry-demo"
#   ^ same trace twice -> same note_id, duplicate = True

Get-Content logs\audit.jsonl -Tail 5
Select-String -Path data\crm.json -Pattern '123-45-6789'    # nothing: never stored
```

## 5. Experiments

| Try | What you learn |
|---|---|
| In `src\skills\index.ts`, change `client_id` to `clientId` in one `run`, then `npm run typecheck` | The compiler catches the typo before anything runs |
| `npm run dev`, edit a skill's `description`, refresh `/docs` | Swagger is generated from code: it updates itself |
| `npm run build`, open `dist\skills\index.js` | What TypeScript compiles to (types erased) |
| Stop the server, `npm run reset-data` | Back to the sample data |

## 6. With the Conductor

`aurelius\.env`: include `liaison` in `REAL_AGENTS`. Start the Liaison, then send the Conductor's Patel meeting-prep request: the `liaison` step returns the real CRM data.

## Troubleshooting

| You see | Fix |
|---|---|
| `'node' is not recognized` | Install Node LTS, open a NEW terminal |
| `npm.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or `npm.cmd` |
| `process.loadEnvFile is not a function` | Node too old: v20.12+ |
| `Cannot find name 'process'` in the editor | Run `npm install` (it brings `@types/node`); reopen VS Code |
| `SERVICE_TOKEN is missing or too short` | 24+ character token in `aurelius\.env` |
| `EADDRINUSE :8102` | Another Liaison is running: close that terminal |
| Swagger "Failed to fetch" | Server stopped, or you opened `/docs` on a different port |
