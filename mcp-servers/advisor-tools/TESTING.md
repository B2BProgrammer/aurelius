# advisor-tools MCP server: Start & Test

## 1. First-time setup

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\mcp-servers\advisor-tools
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install fastapi                 # only for the HTTP tests
python -m pytest -v                 # expect: 10 passed
```

## 2. Start the server

```powershell
python src\main.py
```
✅ `advisor-tools MCP server on http://127.0.0.1:8500/mcp`
Leave it running. Every tool call prints a `tool_call tool=... args=...` line.

## 3. Try it (Terminal 2, same folder, venv active)

```powershell
Invoke-RestMethod http://127.0.0.1:8500/health                  # public: status ok, clients 3
Invoke-RestMethod http://127.0.0.1:8500/mcp -Method Post        # no token -> 401 (red error = correct)

python scripts\try_mcp.py                                        # discover tools + get_holdings patel-001
python scripts\try_mcp.py get_client_profile garcia-003
python scripts\try_mcp.py get_recent_trades garcia-003           # the EMKT buy in the IRA
python scripts\try_mcp.py get_security_info AIBF                 # replacements: GIBX
python scripts\try_mcp.py list_clients
python scripts\try_mcp.py get_holdings nobody-1                  # TOOL ERROR: No client with id ...
```

MCP isn't a plain REST API (it's JSON-RPC over HTTP with a session handshake), so Swagger and `.http` files don't fit it well. `try_mcp.py` is a real MCP client, and the Analyst's `GET /v1/tools` shows the same discovery over HTTP.

## Troubleshooting

| You see | Fix |
|---|---|
| `SERVICE_TOKEN is missing or too short` | 24+ character `SERVICE_TOKEN` in `aurelius\.env` |
| `try_mcp.py` connection error | Server not running in Terminal 1 |
| `ModuleNotFoundError: mcp.server.fastmcp` in other code you find online | That's MCP **v1** code. v2 uses `from mcp.server.mcpserver import MCPServer` |
