# Notary - onboarding-kyc

| Field    | Value |
|----------|-------|
| Language | Java |
| Port     | 8201 |
| Role     | Account opening checklist, KYC/AML document validation. |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)