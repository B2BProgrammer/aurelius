# Librarian - knowledge-rag

| Field    | Value |
|----------|-------|
| Language | Python |
| Port     | 8001 |
| Role     | RAG over research, product docs & policies (ChromaDB). |

## Standard agent contract (every agent implements these)
- `GET  /health`                  -> liveness check
- `GET  /.well-known/agent.json`  -> "agent card": name, skills, input schema
- `POST /invoke`                  -> do the work (payload = contracts/agent-message.schema.json)