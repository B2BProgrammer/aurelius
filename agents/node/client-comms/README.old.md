# Herald - client-comms

| Field    | Value |
|----------|-------|
| Language | Node.js |
| Port     | 8101 |
| Role     | Drafts client emails / review letters in advisor's voice. |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)