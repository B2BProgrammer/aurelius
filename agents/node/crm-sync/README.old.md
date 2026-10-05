# Liaison - crm-sync

| Field    | Value |
|----------|-------|
| Language | Node.js |
| Port     | 8102 |
| Role     | Reads/writes CRM (households, tasks, notes). |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)