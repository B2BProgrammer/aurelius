# Notary: Start & Test Runbook (Java / Spring Boot)

## 0. Java and Maven (once)

```powershell
java -version      # need 21 or newer
mvn -v             # Maven 3.9+. "not recognized"? install it below
```

**Install Maven** (no admin rights needed: it goes into your user folder):
```powershell
$v = "3.9.11"
Invoke-WebRequest "https://archive.apache.org/dist/maven/maven-3/$v/binaries/apache-maven-$v-bin.zip" -OutFile "$env:TEMP\maven.zip"
Expand-Archive "$env:TEMP\maven.zip" -DestinationPath "$env:USERPROFILE\tools" -Force
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";$env:USERPROFILE\tools\apache-maven-$v\bin", "User")
```
Close PowerShell, open a **new** one, run `mvn -v`. It should show Maven 3.9.11 and your Java 21+.

> Maven is to Java what npm is to Node: `pom.xml` lists the libraries; the first build downloads them (~100 MB) into `%USERPROFILE%\.m2\repository`. Later builds are offline and fast.

## 1. First-time setup

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\java\onboarding-kyc
mvn test
```
✅ Expect, at the end:
```
[INFO] Tests run: 39, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
`ApiIntegrationTest` starts the real server on a random port (you'll see Spring's JSON logs scroll by); the other 4 classes are plain Java and take milliseconds.

## 2. Start (pick one)

```powershell
mvn spring-boot:run                    # compile + start (use this while learning)

mvn -DskipTests package                # OR: build target\notary.jar ...
java -jar target\notary.jar            # ... and run it (what production does)
```
Always start from the `onboarding-kyc` folder: the data paths (`data\...`) are relative to it.

✅ You'll see JSON log lines, then:
```
Notary (onboarding-kyc) on http://127.0.0.1:8201
Swagger UI:              http://127.0.0.1:8201/docs
```
On first start, `data\kyc.json` is created from `data\kyc.seed.json`. Stop with **Ctrl+C**.

## 3. Swagger (browser)

1. Open **http://localhost:8201/docs** (it redirects to `/swagger-ui/index.html`)
2. **Authorize** → paste the SERVICE_TOKEN (`Select-String -Path ..\..\..\.env -Pattern '^SERVICE_TOKEN='`) → Authorize → Close
3. **POST /invoke** → **Try it out** → **Examples** dropdown → **Execute**

| Example | What to look for |
|---|---|
| `check_kyc` | Patel `action_needed`: Raj's license expires in N days |
| `check_kyc (blocked)` | Garcia `blocked`: Luis has no ID, never screened. Diego (17) has no issues |
| `check_kyc (65+ clients)` | Chen: two `KYC_TRUSTED_CONTACT_MISSING` |
| `list_documents` | `"number": "****4417"`, `"state": "expiring"` |
| `screen_name (potential match)` | DEMO-0001, `requires_review: true` |
| `screen_name (record for Luis)` | `clear`, `used_dob: true`. Run `check_kyc (blocked)` again: one blocker left |
| `record_document (renewed license)` | `kyc_status_now: complete`. **Execute again**: same `doc_id`, `duplicate: true` |

Also try **GET /v1/clients** (all three households with status) and **GET /v1/rules**.

## 4. VS Code / PowerShell

**VS Code:** `api-tests.http` (30 requests) → paste the token → **Send Request** top to bottom (sections 4 and 5 tell a story: Garcia goes from *blocked* to *action_needed*).

**PowerShell** (Terminal 2):
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\java\onboarding-kyc
$svc = ((Get-Content ..\..\..\.env | Where-Object { $_ -match '^SERVICE_TOKEN=' }) -split '=', 2)[1] -replace '\s+#.*$', ''
$h = @{ Authorization = "Bearer $svc" }

function Notary($skill, $inputObj, $trace = "ps-$(Get-Random)") {
    $body = @{ skill = $skill; input = $inputObj
               context = @{ trace_id = $trace; user_id = "dev-advisor" } } | ConvertTo-Json -Depth 6
    $r = Invoke-RestMethod http://localhost:8201/invoke -Method Post -Headers $h -ContentType "application/json" -Body $body
    if ($r.status -ne "ok") { "ERROR: $($r.error)" } else { $r.output }
}

$k = Notary check_kyc @{ client_id = "garcia-003" }
$k.headline
$k.issues | Format-Table severity, rule, member, fix -Wrap

Notary screen_name @{ name = "Luis Garcia" }                                               # potential_match (no DOB)
Notary screen_name @{ name = "Luis Garcia"; client_id = "garcia-003"; member_id = "garcia-003-m2" }   # clear, recorded
(Notary check_kyc @{ client_id = "garcia-003" }).headline                                   # one blocker left

Get-Content logs\audit.jsonl -Tail 3          # name_sha256, never the name
Select-String -Path data\kyc.json -Pattern 'D123-4567'   # nothing: only "8901" is stored after record_document
```

## 5. Experiments

| Try | What you learn |
|---|---|
| In `application.yml` set `expiring-window-days: 30`, restart, `check_kyc` Patel | Raj's license (43 days) no longer flagged: rules are configuration-driven |
| `KYC_MATCH_THRESHOLD=0.95` in `aurelius\.env`, restart, screen "Luis Garcia" | Stricter threshold = fewer false positives, but risk of missing real ones |
| Open `KycRules.java`, change "65" to "70", `mvn test` | A test fails: the rules are pinned by tests |
| Stop the server, delete `data\kyc.json`, start | Back to the seed data |
| `mvn -DskipTests package`, look at `target\notary.jar` (~30 MB) | One "fat jar" with Tomcat inside: how Spring Boot apps ship |

## 6. With the Conductor

`aurelius\.env`: add `notary` to `REAL_AGENTS`, and set `NOTARY_URL=http://127.0.0.1:8201`.
Start the Notary, then the Conductor, and send the Patel meeting-prep request. The `notary.check_kyc` step returns the real result: Raj's expiring license.

## Troubleshooting

| You see | Fix |
|---|---|
| `'mvn' is not recognized` | Install Maven (step 0) and open a NEW terminal |
| `The JAVA_HOME environment variable is not defined correctly` | `[Environment]::SetEnvironmentVariable("JAVA_HOME", "C:\Program Files\Eclipse Adoptium\jdk-21...", "User")`: use your real JDK folder (`where.exe java` shows it, minus `\bin\java.exe`) |
| `release version 21 not supported` | Maven is using an older JDK: fix `JAVA_HOME` to point at 21+ |
| `ERROR: SERVICE_TOKEN is missing or too short` | 24+ character token in `aurelius\.env` |
| `NoSuchFileException: data\kyc.seed.json` | You started from another folder: `cd` into `onboarding-kyc` first |
| `Port 8201 was already in use` | Another Notary is running: close that terminal |
| Downloads fail on first build (company network) | Maven needs `repo.maven.apache.org`; a corporate proxy goes in `%USERPROFILE%\.m2\settings.xml` |
| Build error in a file you didn't touch | Copy the first `[ERROR]` lines and send them to me |
