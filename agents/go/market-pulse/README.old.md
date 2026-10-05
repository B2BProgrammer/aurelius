# Pulse - market-pulse

| Field    | Value |
|----------|-------|
| Language | Go |
| Port     | 8301 |
| Role     | Streams market/news events, flags ones affecting client books. |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)