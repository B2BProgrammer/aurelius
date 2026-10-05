# Scribe - meeting-intel

| Field    | Value |
|----------|-------|
| Language | Python |
| Port     | 8003 |
| Role     | Summarises meeting notes, extracts action items & follow-ups. |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)