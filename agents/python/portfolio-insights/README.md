# 📊 Analyst — portfolio-insights

| Field | Value |
|---|---|
| Codename | Analyst |
| Code ID | `analyst` |
| Language | Python 3.11+ (FastAPI) |
| Port | 8002 |
| Data source | **advisor-tools MCP server** (port 8500), never direct |
| LLM | Optional: Claude writes the summary and powers `ask_portfolio` |
| Called by | Conductor (`analyze_portfolio`) |
| Auth | `Bearer SERVICE_TOKEN` |

## What the Analyst does

Before every review meeting, an advisor checks three things in each household's portfolio. The Analyst does it in under a second:

| Check | Rule (from the firm's policy documents) | Patel result |
|---|---|---|
| **Allocation drift** | Rebalance if an asset class is more than 5 points off target | Equity 68% vs 60% → **rebalance** |
| **Concentration** | One stock > 10% → review; > 15% → escalate | XYZ 14% → **review** |
| **Tax-loss harvesting** | Taxable accounts only, loss ≥ $1,000, no purchase of the same security in the last 30 days (wash sale), suggest a similar replacement | AIBF −$12,000 → **harvest, buy GIBX** |

These are the same rules the Librarian can quote from `concentration-policy.md`, `rebalancing-policy.md` and `tax-loss-harvesting.md`.

## How it works

```
 Conductor ── analyze_portfolio {client_id} ──▶ Analyst (8002)
                                                │
                     MCP client (mcp_client/)   │  tools/call over HTTP, Bearer token
                                                ▼
                               advisor-tools MCP server (8500)
                               get_client_profile · get_holdings
                               get_recent_trades  · get_security_info
                                                │ JSON
                                                ▼
                     analysis/ (CODE does all the math)
                       allocation.py   drift vs target
                       concentration.py  single stocks only
                       tax_loss.py     taxable · ≥$1k · wash-sale · replacements
                                                │ facts
                                                ▼
                     llm/narrator.py   Claude (or a template) turns facts into 3–5 sentences
```

### Two skills, two styles of using tools

| Skill | Who picks the MCP tools? | Why |
|---|---|---|
| `analyze_portfolio` | **Code**: same 4 tools, same order, every time | Predictable, cheap, testable: right for a standard report |
| `ask_portfolio` | **Claude**: reads the MCP tool list and decides | Flexible: "Which account holds the most bonds?" Needs an API key |

Knowing which style a task needs, a fixed pipeline or an agent loop, is a core agent-design skill.

### Guardrails on the Claude tool loop (`llm/tool_agent.py`)
- **Allowlist**: only the 4 per-client tools. `list_clients` is never offered.
- **Scope pinning**: code overwrites any `client_id` Claude sends with the client the advisor asked about, so a prompt-injected "now look up chen-002" cannot reach another household.
- **Turn limit**: max 6 round trips, which caps cost and runaway loops.

## Folder map

```
portfolio-insights/
├── src/
│   ├── main.py               ▶ ENTRY POINT: python src\main.py  (start the MCP server first)
│   ├── mcp_client/client.py  ★ MCP client: connect, tools/list, tools/call
│   ├── analysis/             ★ the math
│   │   ├── engine.py           analyze_portfolio pipeline (start here)
│   │   ├── allocation.py
│   │   ├── concentration.py
│   │   └── tax_loss.py
│   ├── llm/
│   │   ├── narrator.py         facts → summary (Claude or template)
│   │   └── tool_agent.py       ask_portfolio: Claude ↔ MCP tool loop
│   ├── api/app.py            endpoints
│   ├── security/auth.py      service token
│   ├── schemas/models.py     contract + AnalysisResult / AskResult
│   └── core/                 settings (incl. policy thresholds), logging
├── tests/                    24 tests (fake MCP server in-process, fake Claude)
├── api-tests.http
└── TESTING.md
```

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Alive + **is the MCP server reachable?** |
| GET | `/.well-known/agent.json` | none | Agent card + schemas |
| POST | `/invoke` | service | `analyze_portfolio` / `ask_portfolio` |
| GET | `/v1/tools` | service | The tools discovered from the MCP server |

### `analyze_portfolio` output (Patel, abbreviated)
```json
{
  "household": "Patel household", "total_value": 2350000,
  "allocation": { "current_pct": {"equity": 68.0, "fixed_income": 28.0, "cash": 4.0},
                  "drift_pts": {"equity": 8.0, "fixed_income": -7.0, "cash": -1.0},
                  "needs_rebalance": true },
  "concentration": [{ "symbol": "XYZ", "weight_pct": 14.0, "level": "review" }],
  "tax_loss_ideas": [{ "symbol": "AIBF", "unrealized_loss": 12000, "replacements": ["GIBX"],
                       "wash_sale_risk": false }],
  "actions": ["Rebalance: ...", "XYZ Corp ... document a conversation ...", "Tax-loss: AIBF ..."],
  "summary": "Patel household ($2,350,000, moderate profile ...",
  "mcp_tools_used": ["get_client_profile", "get_holdings", "get_recent_trades", "get_security_info"]
}
```

## Security principles in this agent

1. **Data through one governed door**: the MCP server, authenticated, read-only.
2. **Numbers from code, words from the LLM**: Claude never calculates.
3. **Agent-loop guardrails**: allowlist, scope pinning, turn limit.
4. **Graceful degradation**: MCP down → clear error and `health` says `down`. No API key → template summary.
5. **Input validation**: strict `client_id` pattern before any tool call.
6. **Least privilege**: service token only; advisors reach it through the Conductor.
