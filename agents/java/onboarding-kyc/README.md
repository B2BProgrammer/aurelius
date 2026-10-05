# 🖋️ Notary: onboarding-kyc

| Field | Value |
|---|---|
| Codename | Notary |
| Code ID | `notary` |
| Language | **Java 21** · Spring Boot 3.5 · Jackson · springdoc (Swagger) |
| Port | 8201 |
| Swagger UI | **http://localhost:8201/docs** (OpenAPI at `/openapi.json`) |
| Data | `data\kyc.json`, created from `data\kyc.seed.json` on first start (stands in for the firm's onboarding system) |
| Watchlist | `data\watchlist.json`: **fictional** demo entries (real firms use OFAC and similar lists through a vendor) |
| Called by | Conductor (`check_kyc` in every meeting prep) |
| Auth | `Bearer SERVICE_TOKEN` |
| LLM | **None, on purpose**: a KYC decision must be identical every time and explainable rule by rule |

## Skills

| Skill | Reads/Writes | Example |
|---|---|---|
| `check_kyc` | read | Patel: *"1 action item. Raj Patel's driver's license expires on 2026-11-15 (in 43 days)."* Garcia: **BLOCKED** (Luis has no ID, never screened) |
| `list_documents` | read | Documents with masked numbers (`****4417`) and state: valid / expiring / expired |
| `screen_name` | read, or **write** with `member_id` | Fuzzy watchlist match: "Victor Morozenko" → potential match. "Luis Garcia" + his birth date → clear, recorded on his file |
| `record_document` | **write**, idempotent | Raj's renewed license → Patel becomes `complete`. Same request again → `duplicate: true` |

## The rule book (`kyc/KycRules.java`)

| Severity | Rules |
|---|---|
| **BLOCKER** | `KYC_ID_MISSING`, `KYC_ID_EXPIRED`, `AML_NOT_SCREENED`, `AML_POTENTIAL_MATCH` |
| **ACTION** | `KYC_ID_EXPIRING` (≤ 60 days), `AML_SCREENING_STALE` (> 1 yr), `KYC_ADDRESS_STALE` (> 3 yrs), `KYC_W9_MISSING`, `KYC_RISK_PROFILE_STALE` (> 1 yr), `KYC_SOURCE_OF_FUNDS_MISSING`, `KYC_TRUSTED_CONTACT_MISSING` (65+, FINRA 4512), `KYC_BENEFICIARY_MISSING` (IRAs) |
| **INFO** | `KYC_TRUSTED_CONTACT_SUGGESTED` (under 65), `KYC_BENEFICIARY_REVIEW` (> 10 yrs) |

Status = `blocked` if any blocker, else `action_needed` if any action, else `complete`. Minors (Diego, 17) get no ID or screening issues of their own. Every issue comes with a `fix`.

## Fuzzy screening (`screening/NameScreener.java`)

1. Normalize: lowercase, strip accents (`José` → `jose`) and punctuation.
2. **Jaro-Winkler** similarity, on the name and on the name with its words sorted (word-order proof), against every name and alias.
3. Date of birth: same birth date → +0.05; different birth year → ×0.85. This is how real systems cut **false positives**.
4. Score ≥ 0.88 = `potential_match` → `requires_review: true`. A human compliance officer decides; code never accuses a client. The reply reminds the advisor not to tip off the client.

## Security principles in this agent

| Principle | Where |
|---|---|
| **Deterministic decisions**: rules in code, no LLM | `kyc/KycRules.java` |
| **Fail closed**: weak `SERVICE_TOKEN` → won't start | `NotaryApplication.main` → `Checks.serviceToken` |
| **Constant-time token check** (`MessageDigest.isEqual`) | `web/ServiceTokenFilter.java` |
| **Validate at the edge**: each input record validates itself in its constructor; ids are `^[A-Za-z0-9_-]{1,64}$`; names letters-only; dates must make sense | `skills/SkillInputs.java`, `contract/*` |
| **Minimum necessary**: only the last 4 of a document number are ever stored; outputs mask them; no birth dates in outputs (ages only) | `SkillInputs.numberLast4`, `KycService` |
| **Idempotent writes**: explicit `idempotency_key`, or SHA-256 of trace + content (with only the last 4 of the number in it) | `KycService.recordDocument`, `KycStore` |
| **Atomic, serialized writes**: `synchronized` + temp file + atomic rename (retry for Windows/OneDrive locks) | `store/KycStore.java` |
| **Audit trail for AML**: every write and screening logged with trace, user, ids; names only as SHA-256 fingerprints | `store/AuditLog.java` → `logs\audit.jsonl` |
| **Safe headers**: unsafe `X-Trace-Id` values are replaced (no header/log injection); `nosniff`, `no-store`; bodies > 64 KB refused | `web/TraceFilter.java` |
| **No internals in errors**: no stack traces, no Java class names; 500s carry only a trace id | `web/ApiErrorHandler.java`, `SkillRegistry.readable` |

## Folder map

```
onboarding-kyc/
├─ pom.xml                         Maven: Spring Boot parent, web + springdoc + test
├─ src/main/java/com/aurelius/notary/
│  ├─ NotaryApplication.java       ENTRY POINT: .env -> token check -> Spring Boot
│  ├─ config/  AppConfig           wiring (beans, filters)       NotaryProperties  typed settings
│  │           OpenApiConfig       Swagger: bearer auth + examples from SkillRegistry
│  ├─ web/     PublicController    /health, agent card
│  │           AgentController     POST /invoke
│  │           BrowseController    /v1/clients, /v1/clients/{id}/kyc, /v1/rules
│  │           TraceFilter  ServiceTokenFilter  ApiErrorHandler
│  ├─ skills/  SkillRegistry       ONE table: skills -> /invoke, agent card, Swagger examples
│  │           SkillInputs         validated input records
│  ├─ kyc/     KycRules            THE RULE BOOK (start reading here)
│  │           KycService          use cases     Model  records
│  ├─ screening/NameScreener       Jaro-Winkler watchlist screening
│  ├─ store/   KycStore  AuditLog  JSON file + audit trail
│  └─ support/ Json  DotEnv  Checks
├─ src/main/resources/application.yml
├─ src/test/java/...               5 test classes (4 plain Java + 1 full Spring Boot over HTTP)
├─ data/  kyc.seed.json  watchlist.json
├─ api-tests.http  TESTING.md  .env.example
```

## Java concepts you'll meet here

| Concept | Where | In one line |
|---|---|---|
| `record` | `Model.java`, `SkillInputs.java` | Immutable data class; the compact constructor validates |
| Dependency injection | `AppConfig`, controller constructors | Spring builds objects once and passes them in |
| Servlet `Filter` | `TraceFilter`, `ServiceTokenFilter` | Middleware that runs before the controllers |
| `@RestControllerAdvice` | `ApiErrorHandler` | One place that turns exceptions into JSON errors |
| `@ConfigurationProperties` | `NotaryProperties` | `application.yml` → typed record |
| `synchronized` | `KycStore` | One thread at a time in that method |
| `Clock` injection | `KycService` | Tests pin "today" to 2026-10-03 |
