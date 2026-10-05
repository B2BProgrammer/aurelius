# 📐 Actuary: risk-engine

| Field | Value |
|---|---|
| Codename | Actuary |
| Code ID | `actuary` |
| Language | **Java 21** · Spring Boot 3.5 · Jackson · springdoc (Swagger) |
| Port | 8202 |
| Swagger UI | **http://localhost:8202/docs** (OpenAPI at `/openapi.json`) |
| Portfolios | **Live from the advisor-tools MCP server** (:8500), with a Java MCP client written on plain `java.net.http`. If it's down: `data\portfolio-snapshot.json`, and every answer says so (`portfolio_source`) |
| Planning data | `data\profiles.json`: ages, retirement plans, savings, spending, Social Security, one-time costs, questionnaire (fictional) |
| Called by | Conductor (`project_retirement`, `risk_score`) |
| Auth | `Bearer SERVICE_TOKEN`, used both to call the Actuary and by the Actuary to call the MCP server |
| LLM | **None**: it computes; the LLM agents explain |

## Skills

| Skill | What it answers | Example (seed data) |
|---|---|---|
| `risk_score` | How much risk *should* they take? | Patel **60, Moderate growth**, aligned. Garcia **55, Moderate**, but 70% equity with an 80% target on file → "portfolio riskier than profile" |
| `project_retirement` | Will the money last? (Monte Carlo) | Patel: retire at **62 → ~87%**, at **63 → ~91%**. That's Raj's question from the July meeting. Chen (retired): **over 99%** |
| `stress_test` | How bad could a crisis be? | Patel: a 2008 repeat costs **~$556,000 (23.7%) = 4.0 years of spending**. "XYZ falls 50%" costs $165,000 |

## How the math works

**Risk score** (`risk/RiskScorer.java`): the **lower** of
- *willingness*: questionnaire answers 1-5 → 0-100;
- *capacity*: the average of horizon (30 + 5 per year to retirement), coverage (portfolio ÷ 25× the yearly spending gap after Social Security), and income stability.

The score maps to a band and a suggested equity %, which is compared with the real portfolio and with the target on file.

**Monte Carlo** (`planning/MonteCarlo.java`): every simulated year is
`balance × (1 + random return) + savings (before retirement) − (spending − Social Security) − one-time costs`.
- Returns are drawn from a normal distribution with the portfolio's expected return and volatility (`planning/Assumptions.java`).
- Success means the money lasts until the youngest adult reaches 95.
- 5,000 futures take about 0.1 s.
- **Seeded from the inputs**, so the same question always gets the same answer. An advisor can't re-roll until it looks nicer, and an auditor can reproduce it.

**Stress test** (`risk/StressTester.java`): approximate historical asset-class moves (2008, 2000-02, 2020, 2022) applied to today's mix, plus a 50% drop in the largest single stock. Each loss is also shown in **years of retirement spending**, which clients understand better than percentages.

## MCP in Java (`mcp/McpClient.java`)

One tool call takes three POSTs and a DELETE to `/mcp`: `initialize` (the reply header `mcp-session-id` names the session), then `notifications/initialized`, then `tools/call`, then `DELETE` to end the session. Replies are Server-Sent Events (`data: {...}`) or plain JSON; the client accepts both.
- **Two tools are used:** `get_client_profile` (risk label, target mix) and `get_holdings` (positions → value per asset class, largest single stock).
- **HTTP/1.1 is forced on purpose.** Java's `HttpClient` otherwise sends `Upgrade: h2c`, and Python's uvicorn then loses the request body (`-32700 Parse error`). This was found during live testing and is pinned by a test.

## Security principles in this agent

| Principle | Where |
|---|---|
| **Fail closed**: weak `SERVICE_TOKEN` → won't start | `ActuaryApplication.main` |
| **Constant-time token check** | `web/ServiceTokenFilter.java` |
| **Authenticated agent-to-MCP calls**: Bearer token, trace id passed through, timeouts | `mcp/McpClient.java` |
| **Graceful, labelled degradation**: MCP down → snapshot, `portfolio_source` says so; unknown client → error, never a guess | `mcp/PortfolioSource.java` |
| **Resource limits**: at most 20,000 simulations, 3 scenarios, plan-to-age 80-105 (one request can't eat the CPU) | `SkillInputs`, `ActuaryService` |
| **Reproducible, explainable numbers**: seeded simulation; inputs, assumptions and disclosure returned with every projection | `ActuaryService.projectRetirement` |
| **Never sounds certain**: "over 99%", never "100%"; every projection says *not a guarantee* | `MonteCarlo.pctText`, `DISCLOSURE` |
| **Read-only**: no write skills, nothing to trade; `buy_stock` → unknown skill | `SkillRegistry` |
| Plus the Notary's: safe trace ids, 64 KB body limit, no stack traces or class names in errors | `web/*` |

## Folder map

```
risk-engine/
├─ pom.xml   .mvn/maven.config (libraries go to .\.m2, inside this folder)
├─ src/main/java/com/aurelius/actuary/
│  ├─ ActuaryApplication.java   ENTRY POINT
│  ├─ config/   AppConfig  ActuaryProperties  OpenApiConfig
│  ├─ web/      PublicController  AgentController  BrowseController  filters  ApiErrorHandler
│  ├─ skills/   SkillRegistry  SkillInputs
│  ├─ planning/ MonteCarlo  ActuaryService  Profiles  Portfolio  Assumptions
│  ├─ risk/     RiskScorer  StressTester
│  ├─ mcp/      McpClient  PortfolioSource
│  └─ support/  Json  DotEnv  Checks  NotFoundException
├─ src/test/java/...   MathTest  McpClientTest (fake MCP server)  SkillsTest  SupportTest  ApiIntegrationTest
├─ data/  profiles.json  portfolio-snapshot.json
├─ api-tests.http  TESTING.md  .env.example
```
