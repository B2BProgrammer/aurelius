# Actuary: Start & Test Runbook (Java / Spring Boot)

Same tools as the Notary: Java 21+ and the project-local Maven in `aurelius\tools`.

## 0. Activate Maven for this terminal (like a venv)

```powershell
$env:Path = "C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\tools\apache-maven-3.9.11\bin;" + $env:Path
mvn -v
```

## 1. Test

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\java\risk-engine
Get-Content .mvn\maven.config      # -Dmaven.repo.local=.m2/repository  (already in the zip)
mvn test
```
✅ Expect `Tests run: 36, Failures: 0, Errors: 0` and `BUILD SUCCESS`. The first run downloads libraries into `risk-engine\.m2\repository`.
- **No MCP server is needed for the tests:** `McpClientTest` starts a fake one, and `ApiIntegrationTest` checks the snapshot fallback.
- `WARNING: A Java agent has been loaded dynamically` comes from Mockito and is harmless.

## 2. Start

```powershell
# Terminal 1: the MCP server (portfolio data). Optional but recommended
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\mcp-servers\advisor-tools
.\.venv\Scripts\Activate.ps1
python src\main.py

# Terminal 2: the Actuary (activate Maven first, step 0)
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\java\risk-engine
mvn spring-boot:run
```
✅ You'll see:
```
Actuary (risk-engine) on http://127.0.0.1:8202
Swagger UI:            http://127.0.0.1:8202/docs
Portfolios from MCP:   http://127.0.0.1:8500/mcp   (snapshot file if it's down)
```

## 3. Swagger

1. Open **http://localhost:8202/docs**, click **Authorize**, paste the `SERVICE_TOKEN`, then **Authorize** and **Close**.
2. Open **POST /invoke**, click **Try it out**, pick from **Examples**, then **Execute**.

| Example | What to look for |
|---|---|
| `risk_score` | 60, Moderate growth, `portfolio_source: "mcp"` |
| `risk_score (portfolio too risky)` | Garcia: `portfolio_riskier_than_profile`, 3 notes |
| `project_retirement (62 vs 63)` | Two scenarios plus the comparison sentence. **Execute again**: identical numbers |
| `project_retirement (spend less)` | Higher probability than at $140k |
| `project_retirement (already retired)` | Chen: "over 99%" (never "100%") |
| `stress_test` | Worst case 2008: about $556,000 = 4.0 years of spending |
| `stress_test (one scenario)` | Garcia, 2022 only |

Then **stop the MCP server** (Ctrl+C in Terminal 1) and run `risk_score` again. You'll get the same answer, with `portfolio_source: "snapshot (MCP unavailable: ...)"`.

Also try **GET /v1/assumptions** to see every number the math assumes.

## 4. VS Code / PowerShell

**VS Code:** `api-tests.http` (26 requests) → paste the token → **Send Request**.

**PowerShell:**
```powershell
$svc = ((Get-Content ..\..\..\.env | Where-Object { $_ -match '^SERVICE_TOKEN=' }) -split '=', 2)[1] -replace '\s+#.*$', ''
$h = @{ Authorization = "Bearer $svc" }
function Actuary($skill, $inputObj) {
    $body = @{ skill = $skill; input = $inputObj; context = @{ trace_id = "ps-$(Get-Random)"; user_id = "dev-advisor" } } | ConvertTo-Json -Depth 6
    $r = Invoke-RestMethod http://localhost:8202/invoke -Method Post -Headers $h -ContentType "application/json" -Body $body
    if ($r.status -ne "ok") { "ERROR: $($r.error)" } else { $r.output }
}

$p = Actuary project_retirement @{ client_id = "patel-001"; retire_ages = @(62, 63) }
$p.headline
$p.scenarios | Format-Table retire_age, probability_of_success_pct, median_at_retirement, worst_case_age_money_lasts

(Actuary stress_test @{ client_id = "patel-001" }).scenarios | Format-Table name, loss, loss_pct, years_of_spending
```

## 5. Experiments

| Try | What you learn |
|---|---|
| In `data\profiles.json`, change Patel's `retirement_spending` to 120000, restart | The probability rises: spending is the strongest lever |
| `"simulations": 500`, then `20000` | Fewer simulations = noisier numbers; more = slower but steadier |
| In `Assumptions.DEFAULT`, lower `equityMean` from 0.050 to 0.040, `mvn test` | Projections fall. Assumptions drive everything, which is why they're published |
| Remove `.version(HttpClient.Version.HTTP_1_1)` in `McpClient.java`, `mvn test` | `McpClientTest` fails: the h2c bug, caught by a test |

## 6. With the Conductor

`aurelius\.env`: add `actuary` to `REAL_AGENTS`, and set `ACTUARY_URL=http://127.0.0.1:8202`. Ask the Conductor *"Should Raj retire at 62 or 63?"* with `client_id` patel-001: the `actuary.project_retirement` step returns the real projection.

## Troubleshooting

| You see | Fix |
|---|---|
| `'mvn' is not recognized` | Run step 0 in this terminal |
| `portfolio_source: "snapshot (MCP unavailable: ... not reachable ...)"` | The MCP server isn't running (Terminal 1), or `MCP_ADVISOR_TOOLS_URL` is wrong |
| `snapshot (MCP unavailable: MCP server rejected our token (401))` | The MCP server and the Actuary have different `SERVICE_TOKEN`s |
| `ERROR: SERVICE_TOKEN is missing or too short` | Check `aurelius\.env` |
| `NoSuchFileException: data\profiles.json` | Start from the `risk-engine` folder |
| `Port 8202 was already in use` | Close the other Actuary terminal |
