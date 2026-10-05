# 🛡️ Sentinel — compliance-guard

| Field    | Value |
|----------|-------|
| Codename | Sentinel |
| Code ID  | `sentinel` |
| Language | Python 3.11+ (FastAPI) |
| Port     | 8004 |
| Called by | Conductor, on every request and every answer |
| Auth     | `Bearer SERVICE_TOKEN` (agents only, never people) |

## What Sentinel does

Sentinel is the security checkpoint. Nothing reaches the LLM, and nothing reaches the advisor, without passing through it.

```
 Advisor's request ──▶ guard_input ──▶ (LLM, agents...) ──▶ guard_output ──▶ Advisor
                        │                                    │
                        ├ mask secrets (API keys, tokens)    ├ mask secrets (leak prevention)
                        ├ mask PII (SSN, card, account...)   ├ mask PII
                        └ score prompt injection             ├ remove non-compliant claims
                            ≥ 0.8  → BLOCK                   └ add required disclosures
                            0.4–0.8 → ask Claude Haiku
                            < 0.4  → allow
                                     every decision ──▶ logs\audit.jsonl
```

**Inputs can be blocked; outputs are fixed.** A blocked request costs nothing. Blocking an answer after all the work is done helps no one, so Sentinel cleans it and explains what it changed.

## Folder map

```
compliance-guard/
├── src/
│   ├── main.py               ▶ ENTRY POINT: python src\main.py
│   ├── guards/               ★ the brain
│   │   ├── engine.py           guard_input / guard_output (start here)
│   │   ├── pii.py              PII + secret detectors (regex + Luhn check)
│   │   ├── injection.py        prompt-injection rules and scoring
│   │   └── compliance.py       promissory-claim rules, disclosures
│   ├── llm/classifier.py     Claude Haiku second opinion (borderline cases only)
│   ├── audit/audit_log.py    one JSON line per decision, no raw text
│   ├── api/app.py            endpoints
│   ├── security/auth.py      service-token check
│   ├── schemas/models.py     agent contract + GuardInput / GuardResult
│   └── core/                 settings, logging
├── tests/                    49 tests
├── logs/audit.jsonl          created at runtime (git-ignore it)
├── api-tests.http            every request to try
└── TESTING.md                start & test runbook
```

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Liveness |
| GET | `/.well-known/agent.json` | none | Agent card + JSON schemas of each skill |
| POST | `/invoke` | service token | `guard_input` / `guard_output` |
| GET | `/v1/rules` | service token | Every active rule and threshold |

### `/invoke` input
```json
{
  "skill": "guard_input",
  "input": { "text": "SSN 123-45-6789, prep me", "kind": "request" },
  "context": { "trace_id": "abc", "user_id": "dev-advisor" }
}
```
`kind`: `request` (advisor's message), `answer` (briefing for the advisor), `email` (may go to a client).

### `/invoke` output
```json
{
  "agent": "sentinel", "status": "ok",
  "output": {
    "allowed": true, "decision": "sanitized",
    "text": "SSN [SSN], prep me",
    "notes": ["Masked SSN"],
    "findings": [{ "rule": "PII_SSN", "category": "pii", "count": 1 }],
    "injection_score": 0.0, "llm_checked": false
  }
}
```

## Rules

| Family | Rule IDs | Action |
|---|---|---|
| PII | `PII_SSN`, `PII_CARD` (Luhn), `PII_ACCOUNT`, `PII_EMAIL`, `PII_PHONE`, `PII_DOB` | Mask as `[LABEL]` |
| Secrets | `SECRET_API_KEY`, `SECRET_JWT` | Mask as `[SECRET]` |
| Injection | `INJ_OVERRIDE` 0.9, `INJ_PROMPT_LEAK` 0.9, `INJ_ROLE_HIJACK` 0.8, `INJ_COMPLIANCE_BYPASS` 0.7, `INJ_DEV_MODE` 0.6, `INJ_EXFIL` 0.6, `INJ_ROLE_SPOOF` 0.5, `INJ_ENCODED` 0.3 | Combined score → block / review / allow |
| Compliance | `CMP_GUARANTEE`, `CMP_NO_RISK`, `CMP_CERTAINTY` | Replace with `[removed: non-compliant claim]` |
| Disclosures | `CMP_DISCLOSURE_ANSWER`, `CMP_DISCLOSURE_EMAIL` | Append (once) |

Scores combine like probabilities: `1 − (1−a)(1−b)…`. Two weak signals together can cross the block line.

## Security principles in this agent

1. **Defense in depth**: rules, then an LLM classifier, then the Conductor's `<request>` tags.
2. **Least data to the LLM**: PII is masked before any model sees it.
3. **Normalize before matching**: invisible characters and odd spacing are removed first.
4. **Fail closed**: weak `SERVICE_TOKEN` → won't start. Sentinel down → Conductor refuses requests.
5. **Untrusted text stays data**: the classifier sees text in `<text>` tags and must answer through a forced tool call.
6. **Auditability without a second copy of PII**: the audit log stores a SHA-256 fingerprint, never the text.
7. **Cost control**: the LLM is only called for borderline cases.
8. **Transparency**: `/v1/rules` shows exactly what is enforced.
