# 🧰 advisor-tools: MCP server

| Field | Value |
|---|---|
| What | An **MCP server**: portfolio data exposed as tools any AI agent can discover and call |
| Language | Python 3.11+ (official `mcp` SDK v2, `MCPServer`) |
| Port | 8500 |
| Endpoint | `http://127.0.0.1:8500/mcp` (Streamable HTTP transport) |
| Health | `http://127.0.0.1:8500/health` (public) |
| Auth | `Bearer SERVICE_TOKEN` |
| Used by | Analyst today; any MCP client tomorrow (Scribe, Claude Desktop, other teams) |

## What MCP is, in 30 seconds

**MCP (Model Context Protocol)** is an open standard for connecting AI applications to tools and data. Think "USB-C for AI": write a tool server once, and every MCP-capable client can use it.

```
   Analyst (MCP client) ──┐                        ┌── get_client_profile
   Claude Desktop ────────┼── tools/list ─────────▶│   get_holdings
   another team's agent ──┘   tools/call  ◀────────┤   get_recent_trades
                                                   │   get_security_info
                                                   └── list_clients
                                 advisor-tools (MCP server) ──▶ data\portfolios.json
                                                                (in real life: custodian / portfolio systems)
```

Three ideas:
1. **Discovery**: `tools/list` returns each tool's name, description and JSON input schema, generated from the Python type hints. An LLM reads these and picks tools itself.
2. **Standard calls**: `tools/call` with JSON arguments returns structured JSON.
3. **Decoupling**: agents never see where the data lives. Swap JSON files for a real database and no agent changes.

## The tools (all read-only)

| Tool | Arguments | Returns |
|---|---|---|
| `list_clients` | — | Households: id, name, risk profile |
| `get_client_profile` | `client_id` | Risk profile, **target allocation**, accounts (taxable/IRA) |
| `get_holdings` | `client_id` | Every position: asset class, value, cost basis, gain/loss, account type |
| `get_recent_trades` | `client_id`, `days` (1–365, default 30) | Buys/sells across all accounts (for wash-sale checks) |
| `get_security_info` | `symbol` | Name, type (stock/fund/cash), asset class, **replacement** funds |

## Sample data (`data\`)

| Client | Story | What the Analyst should find |
|---|---|---|
| `patel-001` | $2.35M, moderate | Equity +8 pts → rebalance · XYZ stock 14% → review · AIBF $12k loss → harvest |
| `chen-002` | $900k, conservative | Exactly on target → no action |
| `garcia-003` | $1.0M, aggressive | Cash +10 pts → rebalance · ABC stock 22% → escalate · EMKT $15k loss **blocked by wash sale** (bought in IRA 12 days earlier) |

All data is fictional and dated `as_of: 2026-10-01`.

## Folder map

```
advisor-tools/
├── src/
│   ├── main.py         ▶ ENTRY POINT: python src\main.py
│   ├── server.py       ★ the 5 tools (start here)
│   ├── data_store.py   reads data\*.json (stands in for real systems)
│   ├── auth.py         bearer-token middleware (/health stays public)
│   └── config.py       settings from aurelius\.env
├── data/               portfolios.json, securities.json
├── scripts/try_mcp.py  a tiny MCP client: discover + call a tool
└── tests/              10 tests (in-process MCP client, no network)
```

## Security principles

1. **Authenticated**: bearer token on `/mcp`; refuses to start with a weak token.
2. **Read-only by design**: no tool can change data, and each is annotated `read_only_hint=True`.
3. **Schema-validated input**: `client_id` pattern, `days` bounds, enforced by the SDK before your code runs.
4. **Safe errors**: expected problems raise `ToolError` with a clear message; unexpected crashes are hidden from callers.
5. **Audit**: every tool call is logged with its arguments and outcome.
6. **Bound to 127.0.0.1**: not reachable from other machines.

The MCP spec also defines OAuth 2.1 for MCP servers (supported by the SDK via `auth=`). A shared service token is the simple equivalent inside one system.
