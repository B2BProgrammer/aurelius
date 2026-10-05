# Conductor - orchestrator

| Field    | Value |
|----------|-------|
| Language | Python |
| Port     | 8000 |
| Role     | Supervisor. Plans the task, routes to agents, merges answers. |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)