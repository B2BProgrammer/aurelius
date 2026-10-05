# Actuary - risk-engine

| Field    | Value |
|----------|-------|
| Language | Java |
| Port     | 8202 |
| Role     | Risk scores, Monte-Carlo retirement projections. |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)