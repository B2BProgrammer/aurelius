# Conductor: Start & Test Runbook

Everything you need to bring the Conductor back up and test it.
The requests themselves live in **`api-tests.http`** (same folder).

---

## 1. Start the server (Terminal 1)

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\orchestrator
.\.venv\Scripts\Activate.ps1          # prompt must now start with (.venv)
python src\main.py
```

✅ Look for `Application startup complete`.
Leave this terminal open. Every request writes JSON log lines here.

## 2. Get your tokens (Terminal 2)

Open a second terminal (`Ctrl+Shift+5` splits it in VS Code):

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\orchestrator
.\.venv\Scripts\Activate.ps1

python scripts\make_dev_token.py                                  # advisor login (JWT), lasts 60 min
Select-String -Path ..\..\..\.env -Pattern '^SERVICE_TOKEN='      # agent-to-agent token
```

## 3. Fire the requests

**Option A: VS Code (recommended)**
1. Install the extension **REST Client** (by Huachao Mao), once.
2. Open `api-tests.http`.
3. Paste the two tokens into `@token` and `@serviceToken` at the top.
4. Click **Send Request** above any request. Compare with its `EXPECT` line.

**Option B: Browser**
Open **http://localhost:8000/docs** → **Authorize** → paste the JWT → **Try it out** on any endpoint.
(For `/invoke`, Logout and Authorize again with the service token.)

**Option C: PowerShell**
```powershell
$token = python scripts\make_dev_token.py
$h = @{ Authorization = "Bearer $token" }
$body = '{"message":"Prep me for my review with the Patel household and draft a follow-up email","client_id":"patel-001"}'
$r = Invoke-RestMethod http://localhost:8000/v1/chat -Method Post -Headers $h -ContentType "application/json" -Body $body
$r.steps | Format-Table agent, skill, status, duration_ms
$r.drafts[0].content.body
$r.answer
```

## 4. Run the automated tests

```powershell
python -m pytest -v          # expect: 19 passed
```

---

## Scorecard (all verified passing)

| # | Request | Expect | Proves |
|---|---|---|---|
| 1.1 | GET /health | 200 | Server is alive |
| 1.2 | GET /.well-known/agent.json | 200 | Agent card |
| 1.3 | GET /health (headers) | nosniff, DENY, no-store | Browser hardening |
| 2.1 | chat, no token | 401 | Login required |
| 2.2 | chat, garbage token | 401 | Signature checked |
| 2.3 | chat, valid token | 200 | Login works |
| 3.1 | GET /v1/agents | 200, 9 agents | Registry |
| 4.1 | Patel meeting prep | 200, 2 stages, 1 draft | Planning + parallel + human approval |
| 4.2 | Retirement projection | 200, actuary only | Calls only what's needed |
| 4.3 | Portfolio drift | 200, analyst | Routing |
| 4.4 | Firm policy question | 200, librarian | Routing to RAG |
| 4.5 | Draft an email | 200, herald, 1 draft | Drafts need approval |
| 4.6 | "Hello" | 200, empty plan | No wasted agent calls |
| 4.7 | Custom X-Trace-Id | header echoed, in logs | Tracing |
| 5.1 | SSN + email in message | 200, Masked SSN/EMAIL | PII masking |
| 5.2 | "Ignore previous instructions…" | 400 | Prompt-injection block |
| 5.3 | "Developer mode…" | 400 | Prompt-injection block |
| 6.1 | client_id with SQL | 422 | Input validation |
| 6.2 | Empty message | 422 | Input validation |
| 6.3 | Missing message | 422 | Input validation |
| 6.4 | Not JSON | 422 | Input validation |
| 6.5 | 4,100-character message | 413 | Size limit |
| 7.1 | /invoke with advisor JWT | 401 | Humans ≠ services |
| 7.2 | /invoke with service token | 200 | Agent contract works |
| 7.3 | /invoke unknown skill | 200, status "error" | Errors in standard envelope |
| 7.4 | /invoke missing context | 422 | Contract enforced |

---

## 6. Endpoints for the web and mobile apps

Add to `aurelius\.env`:
```
DEV_LOGIN_PASSWORD=pick-a-demo-password
```
Restart the Conductor, then (Terminal 2):
```powershell
$login = Invoke-RestMethod http://localhost:8000/v1/auth/login -Method Post -ContentType "application/json" `
  -Body (@{ username = "sam.rivera"; password = "pick-a-demo-password" } | ConvertTo-Json)
$a = @{ Authorization = "Bearer $($login.access_token)" }

Invoke-RestMethod http://localhost:8000/v1/clients -Headers $a
$o = Invoke-RestMethod http://localhost:8000/v1/clients/patel-001/overview -Headers $a
$o.sections.PSObject.Properties | ForEach-Object { "{0,-10} {1,-8} {2,-6} {3,5} ms" -f $_.Name, $_.Value.agent, $_.Value.status, $_.Value.duration_ms }

# live events (relayed from Pulse; start Pulse and add it to REAL_AGENTS first)
curl.exe -N -H "Authorization: Bearer $($login.access_token)" "http://localhost:8000/v1/stream?client_id=garcia-003"
```
With `MOCK_AGENTS=true`, every agent not in `REAL_AGENTS` answers with **its real recorded output** (`src\agents\recorded_responses.json`), so the apps can be built and demoed with only the Conductor running.

| Endpoint | What to check |
|---|---|
| `POST /v1/auth/login` | 5 wrong passwords → `429` for 5 minutes |
| `GET /v1/clients/{id}/overview` | 6 sections, each with its own `status` and `duration_ms` (they run in parallel) |
| `POST /v1/skills/{agent}/{skill}` | Read-only allowlist: `actuary/project_retirement` works, `liaison/log_note` → `403` |
| `POST /v1/drafts/approve` | Sentinel checks the final text; a CRM note gets the subject + SHA-256 fingerprint, not the body |
| `GET /v1/stream` | `event: hello`, then `market_event`s; ends after 30 minutes (apps reconnect) |

## Troubleshooting (every error we've hit so far)

| You see | Why | Fix |
|---|---|---|
| `Python was not found; run without arguments to install from the Microsoft Store` | venv not active; `python` is the Store shortcut | `.\.venv\Scripts\Activate.ps1`, or use `py` outside the venv |
| `The term '\.venv\Scripts\Activate.ps1' is not recognized` | Missing the leading dot | `.\.venv\...` (type `.\.v` + Tab) |
| `cannot be loaded… not digitally signed` | Windows execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (once) |
| `JWT_SIGNING_KEY is missing or too short` | No real key in `aurelius\.env` | `py -c "import secrets; print(secrets.token_urlsafe(48))"` → paste into `.env` |
| `ModuleNotFoundError` | Running system Python, not the venv's | Activate the venv; check with `where.exe python` |
| `401 Token expired` | JWT lasts 60 minutes | `python scripts\make_dev_token.py` again |
| `401` on `/invoke` | Used the JWT instead of the service token | Use `SERVICE_TOKEN` from `.env` |
| `503 Security service unavailable` | `MOCK_AGENTS=false` but Sentinel isn't running | Set `MOCK_AGENTS=true`, or start Sentinel |
| Port 8000 already in use | An old server is still running | Close that terminal, or `Ctrl+C` in it |

---

## Modes (in `aurelius\.env`)

| Setting | Effect |
|---|---|
| `ANTHROPIC_API_KEY=replace-me` | Free. Keyword planner + plain summary (`LLM is in MOCK mode` in the log) |
| `ANTHROPIC_API_KEY=sk-ant-…` | Claude plans and writes the briefing. Log shows `est_cost_usd` per call |
| `MOCK_AGENTS=true` | Built-in fake agents (Patel household demo data) |
| `REAL_AGENTS=sentinel` | Only the listed agents are called for real; the rest stay fake. Add each agent here as you build it, e.g. `REAL_AGENTS=sentinel,librarian` |
| `MOCK_AGENTS=false` | Calls ALL agents over HTTP (use once every agent exists) |

## Build progress

- [x] Conductor (Python): orchestrator, port 8000
- [x] Sentinel (Python): security, port 8004
  (see agents\python\compliance-guard\TESTING.md)
- [ ] Librarian (Python): RAG, port 8001  ← next
- [ ] Analyst (Python): portfolio, port 8002
- [ ] Scribe (Python): meetings, port 8003
- [ ] Herald (Node): emails, port 8101
- [ ] Liaison (Node): CRM, port 8102
- [ ] Notary (Java): KYC, port 8201
- [ ] Actuary (Java): risk, port 8202
- [ ] Pulse (Go): market events, port 8301
- [ ] Atrium (React): frontend, port 5173
