# Pulse: Setup, Start & Test Runbook (Go)

## 0. Laptop setup: install Go (once)

Go is like Java: one toolchain for the whole computer. Pulse has **no third-party packages**, so beyond Go itself **nothing is downloaded**.

```powershell
go version          # need go1.24 or newer. "not recognized"? install it:
winget install --id GoLang.Go -e
```
No winget? Download the Windows **.msi** from https://go.dev/dl (the installer adds Go to your PATH).

**Close and reopen** VS Code / PowerShell, then check: `go version`.

Optional, in VS Code: install the **Go** extension (by the Go Team at Google) for autocomplete and "run test" buttons. When it offers to install its tools (gopls etc.), say yes.

## 1. Put the project in place

Unzip `pulse_go.zip` into `aurelius\agents\go\`, so you get:
```
aurelius\agents\go\market-pulse\go.mod
aurelius\agents\go\market-pulse\cmd\pulse\main.go
aurelius\agents\go\market-pulse\internal\...
aurelius\agents\go\market-pulse\data\...
```
If the skeleton from step 1 left an empty `market-pulse` folder there (README only), replace it.

Pulse uses the same `SERVICE_TOKEN` from `aurelius\.env` as every agent. Nothing to add.

## 2. Test

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\go\market-pulse
go vet ./...        # Go's built-in bug checker: no output = fine
go test ./...       # all packages
```
✅ Expect:
```
ok   aurelius/pulse/internal/api
ok   aurelius/pulse/internal/config
ok   aurelius/pulse/internal/events
ok   aurelius/pulse/internal/holdings
ok   aurelius/pulse/internal/impact
```
- `go test -v ./...` shows all 23 tests by name. `go test ./... -run Stream -v` runs one.
- `./...` means "this folder and everything below it".
- No MCP server needed: the tests start a fake one.

## 3. Start

```powershell
# Terminal 1: the MCP server (optional but recommended)
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\mcp-servers\advisor-tools
.\.venv\Scripts\Activate.ps1
python src\main.py

# Terminal 2: Pulse
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\go\market-pulse
go run ./cmd/pulse
```
✅ You'll see:
```
Pulse (market-pulse) on http://127.0.0.1:8301
Swagger UI:           http://127.0.0.1:8301/docs
Live stream:          http://127.0.0.1:8301/v1/stream
```
**Always start from the `market-pulse` folder.** From anywhere else you get `ERROR: loading events: open data\events.json`.

**Or build a real .exe** (one file, Swagger inside):
```powershell
go build -o pulse.exe ./cmd/pulse
.\pulse.exe
```
Windows Defender may ask the first time a new .exe listens on the network: allow **Private networks**.

Stop with **Ctrl+C**: you'll see `shutting_down` (graceful shutdown).

## 4. Swagger (browser)

1. Open **http://localhost:8301/docs**, click **Authorize**, paste the `SERVICE_TOKEN`, then **Authorize** and **Close**.
2. Open **POST /invoke**, click **Try it out**, pick from **Examples**, then **Execute**.

| Example | What to look for |
|---|---|
| `get_events` | Patel: 5 events, first "XYZ Corp misses Q3 estimates" ≈ -$29,610, `holdings_source: "mcp"` |
| `get_events (high only)` | Garcia: ABC plant closures, 22% of the portfolio |
| `scan_clients` | All 3 households, most affected first |
| `list_events (one symbol)` | XYZ only |

Then **POST /v1/events** → **Try it out**:
- `New event`: 201. Execute again: 200 `duplicate: true`.
- `Prompt-injection attempt`: 422 **quarantined**.

## 5. The live stream (the fun part)

Swagger can't show a stream, so use **curl.exe** (built into Windows 10/11).

**Terminal 3: open a stream for Garcia:**
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\go\market-pulse
$svc = ((Get-Content ..\..\..\.env | Where-Object { $_ -match '^SERVICE_TOKEN=' }) -split '=', 2)[1] -replace '\s+#.*$', ''
curl.exe -N -H "Authorization: Bearer $svc" "http://localhost:8301/v1/stream?client_id=garcia-003"
```
You'll see `event: hello`, then it waits (a `: ping` every 15 s).

**Terminal 4 (or Swagger): publish two events:**
```powershell
$svc = ((Get-Content ..\..\..\.env | Where-Object { $_ -match '^SERVICE_TOKEN=' }) -split '=', 2)[1] -replace '\s+#.*$', ''
$h = @{ Authorization = "Bearer $svc" }
$today = Get-Date -Format "yyyy-MM-dd"

# 1) About XYZ: Garcia doesn't hold it -> NOT shown in Garcia's stream
Invoke-RestMethod http://localhost:8301/v1/events -Method Post -Headers $h -ContentType "application/json" -Body (@{
  event_id = "EV-3001"; date = $today; type = "company_news"; severity = "low"
  headline = "XYZ opens a new office"; symbols = @("XYZ") } | ConvertTo-Json)

# 2) About ABC: Garcia holds $220,000 -> appears in Terminal 3 instantly, with dollar impact
Invoke-RestMethod http://localhost:8301/v1/events -Method Post -Headers $h -ContentType "application/json" -Body (@{
  event_id = "EV-3002"; date = $today; type = "company_news"; severity = "high"
  headline = "ABC Industries CEO resigns"; symbols = @("ABC"); price_change_pct = -7 } | ConvertTo-Json)
```
✅ Terminal 3 shows only `id: EV-3002`, `event: market_event` and `"estimated_impact":-15400`.

**Self-running demo:** start Pulse with a simulator that publishes an event every 10 seconds:
```powershell
$env:PULSE_SIMULATE_SECONDS = "10"; go run ./cmd/pulse
```
Open a stream without `?client_id=` to see everything.

## 6. VS Code / PowerShell for the rest

**VS Code:** `api-tests.http` (22 requests) → paste the token → **Send Request**.

**PowerShell:**
```powershell
function Pulse($skill, $inputObj) {
    $body = @{ skill = $skill; input = $inputObj; context = @{ trace_id = "ps-$(Get-Random)"; user_id = "dev-advisor" } } | ConvertTo-Json -Depth 6
    $r = Invoke-RestMethod http://localhost:8301/invoke -Method Post -Headers $h -ContentType "application/json" -Body $body
    if ($r.status -ne "ok") { "ERROR: $($r.error)" } else { $r.output }
}
(Pulse get_events @{ client_id = "patel-001" }).events | Format-Table event_id, severity, match, exposure_pct, estimated_impact, headline
(Pulse scan_clients @{}).clients | Format-Table client_id, events, high_severity, estimated_impact, top_event
```

## 7. Experiments

| Try | What you learn |
|---|---|
| In `impact.go`, set `matchWeight["indirect"]` to 1.0, `go test ./...` | `TestDirectNewsOutranksBroadNews` fails: the ranking rule is pinned by a test |
| Open 3 streams, then publish | `/health` shows `live_subscribers: 3`; every stream gets it at once (fan-out) |
| `$env:PULSE_MAX_SUBSCRIBERS = "1"`, open 2 streams | The second gets `503 too many live subscribers` |
| Stop the MCP server, run `get_events` | `holdings_source: "snapshot (MCP unavailable: ...)"` |
| `go build` and look at `pulse.exe` (~12 MB) | One file, no runtime to install: why Go is popular for services |
| `$env:PULSE_AS_OF = "2026-10-03"` | Freezes "today", so the demo events stay in the 14-day window in later weeks |

## 8. With the Conductor

`aurelius\.env`: add `pulse` to `REAL_AGENTS`, and set `PULSE_URL=http://127.0.0.1:8301`. Ask the Conductor to prepare for the Patel meeting: the `pulse.get_events` step returns "XYZ misses Q3 estimates…".

## Troubleshooting

| You see | Fix |
|---|---|
| `'go' is not recognized` | Install Go (step 0), open a NEW terminal |
| `go.mod requires go >= 1.24` / tries to download a toolchain | Your Go is older: install the current version |
| `ERROR: SERVICE_TOKEN is missing or too short` | Check `aurelius\.env` |
| `ERROR: loading events: open data\events.json` | Start from the `market-pulse` folder |
| `can't listen on 127.0.0.1:8301` | Another Pulse is running: close it |
| `get_events` returns 0 events | The demo events are from late Sept 2026. If today is much later, set `PULSE_AS_OF=2026-10-03` or use `"days": 90` |
| The stream shows nothing in PowerShell's `Invoke-WebRequest` | It buffers. Use `curl.exe -N` |
