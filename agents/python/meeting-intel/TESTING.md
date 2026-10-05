# Scribe: Start & Test Runbook

## 1. First-time setup (once)

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\meeting-intel
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -v            # expect: 24 passed (no API key needed)
```

## 2. Start

```powershell
python src\main.py
```
✅ `Application startup complete` on port 8003, plus a warning that extraction is RULE-BASED (no API key).
Swagger: **http://localhost:8003/docs** (Authorize with the SERVICE_TOKEN)

## 3. Fire the requests

**Option A: VS Code.** `api-tests.http`, paste the token, **Send Request**.

**Option B: PowerShell** (Terminal 2):
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\meeting-intel
$svc = ((Get-Content ..\..\..\.env | Where-Object { $_ -match '^SERVICE_TOKEN=' }) -split '=', 2)[1] -replace '\s+#.*$', ''
$h = @{ Authorization = "Bearer $svc" }

function Meetings($cid) {
    $body = @{ skill = "summarize_meetings"; input = @{ client_id = $cid }
               context = @{ trace_id = "ps-test"; user_id = "dev-advisor" } } | ConvertTo-Json -Depth 5
    $o = (Invoke-RestMethod http://localhost:8003/invoke -Method Post -Headers $h -ContentType "application/json" -Body $body).output
    "`n== $cid : $($o.meetings_found) meeting(s), last $($o.last_meeting)"
    "Summary: $($o.summary)"
    $o.open_action_items | Format-Table owner, due, task -Wrap
    "Concerns:";    $o.client_concerns | ForEach-Object { "  - $_" }
    "Life events:"; $o.life_events     | ForEach-Object { "  - $_" }
    $o.compliance_flags | Format-Table type, detail -Wrap
}

function Extract($notes, $date) {
    $body = @{ skill = "extract_meeting"; input = @{ notes = $notes; meeting_date = $date }
               context = @{ trace_id = "ps-test"; user_id = "dev-advisor" } } | ConvertTo-Json -Depth 5
    $o = (Invoke-RestMethod http://localhost:8003/invoke -Method Post -Headers $h -ContentType "application/json" -Body $body).output
    "Extracted by: $($o.extracted_by)   PII masked: $($o.pii_masked -join ', ')"
    $o.extract.action_items | Format-Table owner, due, task -Wrap
    $o.extract.compliance_flags | Format-Table type, detail -Wrap
}

Meetings patel-001
Meetings garcia-003
Meetings chen-002
Extract "Quick call with Lin Chen. Lin is worried about rising rates and asked me to sell the bond fund. I will send a bond ladder proposal by July 1. Lin will send the old plan statements." "2026-06-10"
```

## 4. Experiments

| Try | What you learn |
|---|---|
| Write your own notes in `Extract "..."` using different phrasings ("Remind me to...", "Action: ...") | Where rules stop working, and why LLMs are used for extraction |
| Add a file `data\meetings\patel-001\2026-09-28-call.md` (copy the front matter format) and run `Meetings patel-001` | New notes are picked up immediately |
| Add `ANTHROPIC_API_KEY`, restart, run `Meetings chen-002` | Claude also catches "Wei turns 73 and asked about RMDs" (rules miss it); `extracted_by` shows the model |
| Search the responses for `6789` | The SSN in the July Patel notes never appears; only `pii_in_notes` |

## 5. With the Conductor

`aurelius\.env`: `REAL_AGENTS=sentinel,librarian,analyst,scribe`. Start the Scribe along with the others, then send the Conductor's Patel meeting-prep request: the `scribe` step shows the real summary.

## Scorecard (`api-tests.http`)

| # | Test | Expect |
|---|---|---|
| 1.1 / 1.2 | health / card | 200 |
| 2.1 / 2.2 | meetings without / with token | 401 / 2 Patel meetings |
| 3.1 | Patel | retirement + wedding, Anita due 2026-08-15, `pii_in_notes`, no SSN in output |
| 3.2 | Garcia | complaint, client_trade_request, concentration_increase |
| 3.3 | Chen | 2 advisor actions, due 2027-01-15 |
| 3.4 / 3.5 / 3.6 | last_n, client in context, unknown client | 1 meeting / ok / 0 meetings |
| 4.1 | pasted notes | advisor + client actions, concern, trade request |
| 4.2 | PII + injection | SSN/EMAIL masked, `pii_in_notes` |
| 5.1–5.5 | bad input | status "error" |
| 5.6 | missing context | 422 |

## Troubleshooting

| You see | Fix |
|---|---|
| `clients_with_notes: 0` | `data\meetings` folder missing: re-extract the zip |
| A note's date shows `null` | Its front matter is missing or malformed (needs `---` lines and `date: YYYY-MM-DD`) |
| `SERVICE_TOKEN is missing or too short` | 24+ character token in `aurelius\.env` |
