# Herald: Start & Test Runbook (TypeScript)

Same Node.js setup as the Liaison (v20.12+, no venv, TypeScript comes with `npm install`).

## 1. First-time setup

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\node\client-comms
npm install          # express, zod, swagger-ui-express, @anthropic-ai/sdk + typescript, tsx, @types/* (dev)
npm run typecheck    # no output = no type errors
npm test             # expect: tests 45, pass 45 (no Liaison, no API key needed: both are faked)
```

## 2. Settings (in `aurelius\.env`)

Already there from earlier agents: `SERVICE_TOKEN`, `ANTHROPIC_API_KEY`, `LLM_MOCK`. Add (optional):
```
ADVISOR_SIGNATURE=Sam Rivera\nAurelius Wealth
LIAISON_URL=http://127.0.0.1:8102
```
Start with `LLM_MOCK=true` (template drafts, free). Switch to `false` later to see Claude's rewrite.

## 3. Start (two terminals)

```powershell
# Terminal 1: the Liaison (the Herald asks it for household details)
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\node\crm-sync
npm start

# Terminal 2: the Herald
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\node\client-comms
npm start            # or: npm run dev  (restarts on save)
```
✅ You'll see:
```
Herald (client-comms) on http://127.0.0.1:8101
Swagger UI:            http://127.0.0.1:8101/docs
Drafting mode:         template   (Liaison at http://127.0.0.1:8102)
```

## 4. Swagger (browser)

1. Open **http://localhost:8101/docs**
2. **Authorize** → paste the SERVICE_TOKEN (`Select-String -Path ..\..\..\.env -Pattern '^SERVICE_TOKEN='`) → Authorize → Close
3. **POST /invoke** → **Try it out** → **Examples** dropdown → **Execute**

| Example | What to look for |
|---|---|
| `draft_email` | "Hi Raj and Anita,", tone `brief`, both points, review on Thursday October 8, `requires_approval: true` |
| `draft_email (formal household)` | "Dear Mr. and Mrs. Chen,", warning: prefers phone |
| `draft_email (compliance fixes)` | `[removed: non-compliant claim]`, `[ACCOUNT]`, risk disclosure at the end, Garcia service alert |
| `review_email` | `verdict: needs_edits`, 3 fixes |
| `review_email (clean)` | `verdict: ready_for_approval` |

Also **GET /v1/rules**. And look at **Terminal 1**: every draft shows a Liaison `get_household` line with the **same trace id**.

## 5. VS Code / PowerShell

**VS Code:** `api-tests.http` (20 requests) → paste the token → **Send Request**.

**PowerShell** (Terminal 3):
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\node\client-comms
$svc = ((Get-Content ..\..\..\.env | Where-Object { $_ -match '^SERVICE_TOKEN=' }) -split '=', 2)[1] -replace '\s+#.*$', ''
$h = @{ Authorization = "Bearer $svc" }

function Herald($skill, $inputObj, $trace = "ps-$(Get-Random)") {
    $body = @{ skill = $skill; input = $inputObj
               context = @{ trace_id = $trace; user_id = "dev-advisor" } } | ConvertTo-Json -Depth 6
    $r = Invoke-RestMethod http://localhost:8101/invoke -Method Post -Headers $h -ContentType "application/json" -Body $body
    if ($r.status -ne "ok") { "ERROR: $($r.error)" } else { $r.output }
}

$d = Herald draft_email @{ client_id = "patel-001"; purpose = "Follow up on today's review"
                           points = @("We agreed to increase the 529 contribution") } "ps-demo-1"
$d.subject; $d.body; $d.warnings

(Herald review_email @{ text = "This fund is risk-free. SSN 123-45-6789." }).compliance

Get-Content logs\drafts.jsonl -Tail 3     # trace, rules fired, body_sha256: no email text
```

## 6. Experiments

| Try | What you learn |
|---|---|
| Stop the Liaison (Ctrl+C in Terminal 1), run `draft_email` again | **Graceful degradation**: still `ok`, "Hello,", warning "CRM unavailable" |
| Set `LLM_MOCK=false` (real key), restart, compare a draft | Claude rewrites the template; `drafted_by` shows the model; compliance still runs after |
| Put "returns are guaranteed" in a point with the LLM on | Even if Claude keeps it, code removes it |
| Set `ADVISOR_SIGNATURE`, restart | The sign-off changes |
| Edit an `OPENINGS` sentence in `src\compose\templates.ts` with `npm run dev` running | Instant change, no restart |

## 7. With the Conductor

`aurelius\.env`:
```
REAL_AGENTS=herald,liaison          (plus any Python agents you have running)
HERALD_URL=http://127.0.0.1:8101
LIAISON_URL=http://127.0.0.1:8102
```
Start the Liaison, the Herald, then the Conductor. POST `/v1/chat` with
`{"message": "Draft a follow-up email to the Patels after our review meeting", "client_id": "patel-001"}`
→ the `herald` step is `ok`, and `drafts[0].content` has the Herald's subject and body. One trace id shows up in all three terminals.

## Troubleshooting

| You see | Fix |
|---|---|
| `SERVICE_TOKEN is missing or too short` | 24+ character token in `aurelius\.env` |
| `EADDRINUSE :8101` | Another Herald is running: close that terminal |
| Every draft says "CRM unavailable" | Liaison not running, or `LIAISON_URL` wrong. Use `127.0.0.1`, not `localhost` |
| "CRM unavailable (Liaison rejected our token (401))" | The two agents have different `SERVICE_TOKEN`s (an agent-level `.env` overriding the root one?) |
| `drafted_by: template (llm_fallback)` | Claude call failed (key, network, credit). Herald logs show `llm_failed reason=...` |
| `npm.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or `npm.cmd` |
