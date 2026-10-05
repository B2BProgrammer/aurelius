# 📡 Pulse: market-pulse

| Field | Value |
|---|---|
| Codename | Pulse |
| Code ID | `pulse` |
| Language | **Go 1.24+**, **standard library only** (no third-party packages: nothing to download, nothing to audit) |
| Port | 8301 |
| Swagger UI | **http://localhost:8301/docs**, embedded in the program, works offline |
| Holdings | Live from the **advisor-tools MCP server** (:8500), with a Go MCP client on plain `net/http`. If it's down: `data\holdings-snapshot.json`, labelled in every answer |
| Events | `data\events.json`: 8 **fictional** market/news items. New ones arrive with `POST /v1/events` |
| Called by | Conductor (`get_events`) |
| Auth | `Bearer SERVICE_TOKEN` |
| LLM | None. It matches and ranks; the LLM agents explain |

## What Pulse does

| Skill / endpoint | What it answers | Example |
|---|---|---|
| `get_events` | Which recent events touch **this** client's holdings, and how much? | Patel: **"XYZ misses Q3 estimates"**, 14% of the portfolio, ≈ **-$29,610** |
| `scan_clients` | Morning brief: which households are hit most? (all checked **in parallel**) | Patel 5 events, Garcia 4 (ABC plant closures, 22% of the portfolio), Chen 2 |
| `list_events` | The raw feed, optionally per symbol | XYZ: EV-1002, EV-1001 |
| `POST /v1/events` | Ingest a new event: validated, **quarantined** if it looks like a prompt injection, deduped, streamed | `201`, then `200 duplicate`, `409` on a rewrite, `422` when poisoned |
| `GET /v1/stream` | **Live** Server-Sent Events: new events pushed the moment they arrive; `?client_id=` streams only what matters to that client | The ABC event reaches the Garcia stream in milliseconds; an XYZ event is skipped |

## How matching works (`internal/impact`)

- **Direct:** the event names a security the client holds ("XYZ misses").
- **Indirect:** the event is about a slice of the market the client is in: asset class, region or sector ("emerging markets slide" → their EMKT fund). Cash never matches.
- **Relevance** = severity (low 1, medium 2, high 3) × share of the portfolio × (direct 1.0 / indirect 0.5). Broad news reaches a client through diversified funds, diluted, so "XYZ misses earnings" outranks "US stocks hit a record".
- **Dollar impact** = exposure × the event's price move.

## Go concepts you'll meet here

| Concept | Where | In one line |
|---|---|---|
| goroutine + `sync.WaitGroup` + semaphore channel | `skills.scanClients` | Check every household at once, at most 4 at a time |
| channels + `select` | `events.Broker`, `api.stream` | Pub/sub; wait on "new event / heartbeat / client left" together |
| backpressure | `Broker.Publish` | A slow subscriber loses events (counted), it never blocks the others |
| `sync.RWMutex` | `events.Feed` | Many readers at once, one writer alone |
| `context` + graceful shutdown | `cmd/pulse/main.go` | Ctrl+C cancels one context; every live stream sees it and closes |
| `//go:embed` | `internal/api/server.go` | Swagger UI files compiled into the binary |
| method-aware routing | `api.Handler` | `mux.Handle("POST /invoke", ...)`, Go 1.22+, no framework |
| table-driven tests, `httptest` | `*_test.go` | Real HTTP server in tests, plus a fake MCP server |

## Security principles in this agent

| Principle | Where |
|---|---|
| **Fail closed**: weak `SERVICE_TOKEN` → won't start | `config.CheckSecurity` |
| **Constant-time token check** (`crypto/subtle`) | `api.requireToken` |
| **Prompt-injection quarantine at ingest**: news is *external* text that later reaches an LLM, so "ignore previous instructions…" is refused at the door; every answer carries an "external text = data" note | `events/guard.go` |
| **Strict ingest**: unknown fields rejected; ids, symbols, enums, lengths, dates checked; no control characters (no log/header injection) | `events/guard.go`, `contract` |
| **Idempotent, tamper-evident feed**: same event = duplicate; same id with a different story = `409` | `events.Feed.Add` |
| **Resource limits**: 64 KB bodies, 15 s per request, header-read timeout (Slowloris), max 50 live streams, bounded buffers | `api`, `main.go` |
| **No secrets in URLs**: the stream takes the token in the `Authorization` header, never `?token=` (URLs end up in logs) | `api.stream` |
| **Strict Content-Security-Policy on Swagger**: scripts only from this server (that's why `init.js` is a separate file) | `api.withCSP` |
| **No third-party packages**: zero supply-chain risk | `go.mod` |
| **Panics never leak**: 500 with a trace id; the stack goes to the log only | `api.recoverPanics` |
| **Graceful degradation**: MCP down → snapshot, labelled; unknown client → error, never a guess | `holdings.Source` |

## Folder map

```
market-pulse/
├─ go.mod                      module aurelius/pulse (no dependencies)
├─ cmd/pulse/main.go           ENTRY POINT: config -> feed -> holdings -> skills -> HTTP server
├─ internal/                   "internal" = importable only by this module
│  ├─ config/    config.go     settings + .env reader            (+ config_test.go)
│  ├─ contract/  contract.go   the agent contract (JSON envelope, id/text checks)
│  ├─ events/    feed.go       the feed: load, list, ingest, dedupe
│  │             guard.go      validation + prompt-injection quarantine
│  │             broker.go     live pub/sub with channels      (+ events_test.go)
│  ├─ holdings/  mcp.go        Go MCP client
│  │             source.go     MCP first, snapshot fallback     (+ holdings_test.go: fake MCP)
│  ├─ impact/    impact.go     event -> holdings matching + ranking (+ impact_test.go)
│  ├─ skills/    skills.go     get_events, scan_clients, list_events
│  └─ api/       server.go     routes, middleware, SSE stream, ingest
│                openapi.go    OpenAPI 3.1 from the skills table (+ api_test.go: end to end)
│                swaggerui/    embedded Swagger UI (v5.33.1, Apache-2.0)
├─ data/  events.json  holdings-snapshot.json  symbols.json
├─ api-tests.http  TESTING.md  .env.example
```
