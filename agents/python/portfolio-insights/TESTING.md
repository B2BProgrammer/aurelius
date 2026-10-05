# Analyst: Start & Test Runbook

The Analyst needs the **advisor-tools MCP server** running first. Two terminals minimum.

## 1. First-time setup (once)

**MCP server** (see `mcp-servers\advisor-tools\TESTING.md` for details):
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\mcp-servers\advisor-tools
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install fastapi
python -m pytest -v            # 10 passed
deactivate
```

**Analyst:**
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\portfolio-insights
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -v            # 24 passed (uses a fake MCP server, no network)
```

**`aurelius\.env`**: if it has `MCP_ADVISOR_TOOLS_URL=http://localhost:8500/mcp` (from the original `.env.example`), change `localhost` to **`127.0.0.1`**. On Windows, `localhost` may try IPv6 first and fail or be slow.

## 2. Start (in this order)

**Terminal 1: MCP server**
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\mcp-servers\advisor-tools
.\.venv\Scripts\Activate.ps1
python src\main.py
```

**Terminal 2: Analyst**
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\portfolio-insights
.\.venv\Scripts\Activate.ps1
python src\main.py
```
Swagger: **http://localhost:8002/docs** (Authorize with the SERVICE_TOKEN)

## 3. Fire the requests

**Option A: VS Code.** `api-tests.http`, paste the token, **Send Request**.

**Option B: PowerShell** (Terminal 3):
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\portfolio-insights
$svc = ((Get-Content ..\..\..\.env | Where-Object { $_ -match '^SERVICE_TOKEN=' }) -split '=', 2)[1] -replace '\s+#.*$', ''
$h = @{ Authorization = "Bearer $svc" }

function Analyze($cid) {
    $body = @{ skill = "analyze_portfolio"; input = @{ client_id = $cid }
               context = @{ trace_id = "ps-test"; user_id = "dev-advisor" } } | ConvertTo-Json -Depth 5
    $r = Invoke-RestMethod http://localhost:8002/invoke -Method Post -Headers $h -ContentType "application/json" -Body $body
    if ($r.status -ne "ok") { return $r.error }
    $o = $r.output
    "`n== $($o.household)  `$$($o.total_value)"
    "Drift (pts): " + ($o.allocation.drift_pts | ConvertTo-Json -Compress)
    $o.concentration  | Format-Table symbol, weight_pct, level
    $o.tax_loss_ideas | Format-Table symbol, account_id, unrealized_loss, wash_sale_risk, replacements
    "Summary: $($o.summary)"
    "MCP tools used: $($o.mcp_tools_used -join ', ')"
}

Invoke-RestMethod http://localhost:8002/health | ConvertTo-Json      # mcp_server.status = up
(Invoke-RestMethod http://localhost:8002/v1/tools -Headers $h).tools | Format-Table name, read_only
Analyze patel-001
Analyze chen-002
Analyze garcia-003
Analyze nobody-1                                                     # error from the MCP server
```

Watch Terminal 1 (MCP server): each `Analyze` produces 3–4 `tool_call` lines. That's the Analyst using MCP.

## 4. Experiments

| Try | What you learn |
|---|---|
| Stop the MCP server, call `/health` and `Analyze patel-001` | Graceful degradation: clear error, no crash |
| Edit `mcp-servers\advisor-tools\data\portfolios.json` (e.g. raise XYZ quantity to 3000), restart the MCP server, `Analyze patel-001` | XYZ crosses 15% → `escalate`. No Analyst change needed |
| Set `CONCENTRATION_REVIEW_PCT=15` in `aurelius\.env`, restart the Analyst | Policy thresholds are configuration, not code |
| Add `ANTHROPIC_API_KEY`, restart, run requests 4.1 / 4.2 in `api-tests.http` | Claude chooses the MCP tools; scope pinning blocks the other-client trick |

## 5. With the Conductor

1. `aurelius\.env`: `REAL_AGENTS=sentinel,librarian,analyst` (needs the Conductor's `REAL_AGENTS` support from the Sentinel step)
2. Start: MCP server (8500) → Analyst (8002) → Sentinel (8004) → Librarian (8001) → Conductor (8000)
3. Conductor request 4.1 (Patel meeting prep) → the `analyst` step now shows the real numbers

## Scorecard (`api-tests.http`)

| # | Test | Expect |
|---|---|---|
| 1.1 / 1.2 | MCP health / no token | 200 / 401 |
| 1.3 / 1.4 | Analyst health / card | `mcp_server: up` |
| 2.1 / 2.2 | tools without / with token | 401 / 5 read-only tools |
| 3.1 | Patel | +8 equity, XYZ review, AIBF harvest |
| 3.2 | Chen | No action needed |
| 3.3 | Garcia | ABC escalate, EMKT wash-sale WAIT |
| 3.4 | client_id in context | 200 |
| 4.1 / 4.2 | ask (no key) | error: needs API key |
| 5.1–5.4 | bad input / unknown skill | status "error" |
| 5.5 | missing context | 422 |

## Troubleshooting

| You see | Fix |
|---|---|
| `mcp_server: down` / "Cannot reach the portfolio data service" | Start the MCP server first; check `MCP_ADVISOR_TOOLS_URL` uses `127.0.0.1:8500/mcp` |
| `...ConnectError...` only with `localhost` in the URL | Use `127.0.0.1` |
| `portfolio data: ... 401` style errors | Analyst and MCP server read different `SERVICE_TOKEN`s: is there a stray `.env` in one folder? |
| `ask_portfolio needs ANTHROPIC_API_KEY` | Expected without a key; `analyze_portfolio` works without one |
