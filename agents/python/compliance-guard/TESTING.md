# Sentinel: Start & Test Runbook

## 1. First-time setup (once)

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\compliance-guard
py -m venv .venv
.\.venv\Scripts\Activate.ps1          # prompt now starts with (.venv)
pip install -r requirements.txt
python -m pytest -v                   # expect: 49 passed
```

Sentinel reads `SERVICE_TOKEN` from `aurelius\.env`, the **same** value the Conductor uses.

## 2. Start Sentinel alone

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\compliance-guard
.\.venv\Scripts\Activate.ps1
python src\main.py
```
✅ `Application startup complete` on **http://127.0.0.1:8004**
Swagger: **http://localhost:8004/docs** (Authorize with the SERVICE_TOKEN)

Requests: open **`api-tests.http`**, paste the service token, **Send Request**.
Get the token: `Select-String -Path ..\..\..\.env -Pattern '^SERVICE_TOKEN='`

Watch decisions live (another terminal):
```powershell
Get-Content logs\audit.jsonl -Wait -Tail 5
```

## 3. Run Sentinel + Conductor together

**a)** Add one line to `aurelius\.env`:
```
REAL_AGENTS=sentinel
```
(`MOCK_AGENTS=true` stays. The other 8 agents remain fake; only Sentinel is called for real.)

**b)** Terminal 1, Sentinel:
```powershell
cd ...\aurelius\agents\python\compliance-guard
.\.venv\Scripts\Activate.ps1
python src\main.py
```

**c)** Terminal 2, Conductor:
```powershell
cd ...\aurelius\agents\python\orchestrator
.\.venv\Scripts\Activate.ps1
python src\main.py
```

**d)** Use the Conductor's `api-tests.http` (or Swagger on port 8000) as before:

| Check | Expect |
|---|---|
| `GET /v1/agents` | `sentinel: "up"`, all others `"mock"` |
| 4.1 Patel meeting prep | 200, notes include `Added disclosure`, and Terminal 1 logs `guard skill=guard_input` |
| 5.1 SSN in message | `Masked SSN` (now done by the real Sentinel) |
| 5.2 Injection | 400, now with the **reason** listed |
| Stop Sentinel (Ctrl+C), send 4.1 again | **503** "Security service unavailable" → fail closed |

## Scorecard (`api-tests.http`, all verified)

| # | Test | Expect |
|---|---|---|
| 1.1 / 1.2 | health / agent card | 200 |
| 2.1 / 2.2 | no / wrong token | 401 |
| 2.3 | `/v1/rules` | 200 |
| 3.1 | clean request | allow |
| 3.2 | all PII types | sanitized: [SSN] [CARD_NUMBER] [ACCOUNT_NUMBER] [EMAIL] [PHONE] [DATE_OF_BIRTH] |
| 3.3 | $ amounts, dates, bad card | allow (no false alarms) |
| 3.4 | API key pasted | [SECRET] |
| 4.1–4.3 | override, role hijack, hidden chars | block |
| 4.4 / 4.5 | bulk export, skip compliance | allowed + "Flagged for review" (Claude decides when a key is set) |
| 4.6 | "Ignore the market noise…" | allow (score 0) |
| 5.1 | briefing | disclosure added |
| 5.2 | "guaranteed returns, risk-free…" | 3 claims removed |
| 5.3 | email with "projected returns" | risk disclosure added |
| 5.4 | plain email | unchanged |
| 5.5 | PII + key in answer | "Leak prevented" |
| 6.1–6.3 | bad skill / input / kind | status "error" |
| 6.4 | missing context | 422 |

## Troubleshooting

| You see | Fix |
|---|---|
| `SERVICE_TOKEN is missing or too short` | Put a 24+ character `SERVICE_TOKEN` in `aurelius\.env` (same one the Conductor uses) |
| Conductor shows `sentinel: "down"` | Sentinel isn't running on 8004, or `REAL_AGENTS` is misspelled |
| Conductor returns 503 | Sentinel stopped or crashed: check Terminal 1 |
| 401 from Sentinel in Conductor logs | The two agents read different `SERVICE_TOKEN`s: is there a stray `.env` inside one agent folder? |
| `Flagged for review` instead of a decision | No API key: the Claude classifier is off. Add `ANTHROPIC_API_KEY` to turn it on |
