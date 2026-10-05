# Analyst - portfolio-insights

| Field    | Value |
|----------|-------|
| Language | Python |
| Port     | 8002 |
| Role     | Allocation drift, concentration, tax-loss ideas (via MCP tools). |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)