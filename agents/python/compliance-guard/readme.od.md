# Sentinel - compliance-guard

| Field    | Value |
|----------|-------|
| Language | Python |
| Port     | 8004 |
| Role     | Guardrails: PII redaction, prompt-injection & suitability checks. |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)