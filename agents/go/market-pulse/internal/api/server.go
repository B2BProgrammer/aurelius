// Package api is Pulse's HTTP layer: routes, middleware, the live event stream and Swagger.
//
// Endpoints
//
//	GET  /docs                     Swagger UI (embedded in the binary: works offline)
//	GET  /openapi.json             OpenAPI 3.1 document
//	GET  /health                   liveness + stream stats (no auth)
//	GET  /.well-known/agent.json   agent card (no auth)
//	POST /invoke                   the agent contract (service token)
//	GET  /v1/events                the feed (service token)
//	POST /v1/events                ingest one event (service token): validated, quarantined, deduped, streamed
//	GET  /v1/stream                live Server-Sent Events stream (service token), optional ?client_id=
package api

import (
	"crypto/rand"
	"crypto/subtle"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"log/slog"
	"net/http"
	"regexp"
	"runtime/debug"
	"strings"
	"time"

	"aurelius/pulse/internal/config"
	"aurelius/pulse/internal/contract"
	"aurelius/pulse/internal/events"
	"aurelius/pulse/internal/holdings"
	"aurelius/pulse/internal/impact"
	"aurelius/pulse/internal/skills"
)

//go:embed swaggerui
var swaggerFiles embed.FS

const maxBody = 64 << 10 // 64 KB

type ctxKey string

const traceKey ctxKey = "trace"

// API wires the HTTP layer to the service.
type API struct {
	Cfg     config.Config
	Service *skills.Service
	Broker  *events.Broker
	Log     *slog.Logger
	skills  map[string]skills.Skill
}

// Handler builds the router with all middleware.
//
// LEARN: Go 1.22+ ServeMux understands "METHOD /path" patterns, so a small
// service needs no web framework. Middleware is just a function that wraps a
// handler: func(http.Handler) http.Handler.
func (a *API) Handler() http.Handler {
	a.skills = a.Service.Table()
	mux := http.NewServeMux()
	quick := func(h http.HandlerFunc) http.Handler { // everything except the stream gets a 15 s limit
		return http.TimeoutHandler(h, 15*time.Second, `{"detail":"timeout"}`)
	}
	auth := a.requireToken

	docs, _ := fs.Sub(swaggerFiles, "swaggerui")
	mux.Handle("GET /docs/", withCSP(http.StripPrefix("/docs/", http.FileServerFS(docs))))
	mux.Handle("GET /docs", http.RedirectHandler("/docs/", http.StatusFound))
	mux.Handle("GET /openapi.json", quick(a.openapi))
	mux.Handle("GET /health", quick(a.health))
	mux.Handle("GET /.well-known/agent.json", quick(a.agentCard))
	mux.Handle("POST /invoke", auth(quick(a.invoke)))
	mux.Handle("GET /v1/events", auth(quick(a.listEvents)))
	mux.Handle("POST /v1/events", auth(quick(a.ingest)))
	mux.Handle("GET /v1/stream", auth(http.HandlerFunc(a.stream))) // long-lived: no timeout
	mux.HandleFunc("GET /favicon.ico", func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusNoContent) })
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) { writeJSON(w, 404, detail("Not found")) })

	return a.recoverPanics(a.traceAndHeaders(mux))
}

// ------------------------------------------------------------------ middleware

var safeTrace = regexp.MustCompile(`^[A-Za-z0-9_.:-]{1,128}$`)

// traceAndHeaders: reuse/create the trace id, set security headers, cap the body size.
func (a *API) traceAndHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		trace := r.Header.Get("X-Trace-Id")
		if !safeTrace.MatchString(trace) { // never echo unsafe text into headers or logs
			trace = newTraceID()
		}
		w.Header().Set("X-Trace-Id", trace)
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Cache-Control", "no-store")
		r.Body = http.MaxBytesReader(w, r.Body, maxBody)
		r.Header.Set("X-Trace-Id", trace)
		next.ServeHTTP(w, r)
	})
}

// recoverPanics: a bug in one request must not crash the server or leak a stack trace.
func (a *API) recoverPanics(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if v := recover(); v != nil {
				trace := r.Header.Get("X-Trace-Id")
				a.Log.Error("panic", "trace", trace, "error", fmt.Sprint(v), "stack", string(debug.Stack()))
				writeJSON(w, 500, map[string]any{"detail": "Internal error", "trace_id": trace})
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// requireToken: constant-time compare (crypto/subtle), like hmac.compare_digest in Python.
func (a *API) requireToken(next http.Handler) http.Handler {
	want := []byte(a.Cfg.ServiceToken)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
		if !ok {
			got, ok = strings.CutPrefix(r.Header.Get("Authorization"), "bearer ")
		}
		if !ok || len(want) == 0 || subtle.ConstantTimeCompare([]byte(got), want) != 1 {
			w.Header().Set("WWW-Authenticate", "Bearer")
			writeJSON(w, 401, detail("Invalid or missing service token"))
			return
		}
		next.ServeHTTP(w, r)
	})
}

// withCSP: the Swagger page may only load scripts and styles from this server.
func withCSP(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Security-Policy",
			"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
		next.ServeHTTP(w, r)
	})
}

// ------------------------------------------------------------------ public

func (a *API) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, 200, map[string]any{
		"status": "ok", "agent": contract.Agent, "version": config.Version,
		"events": a.Service.Feed.Count(), "live_subscribers": a.Broker.Subscribers(),
		"dropped_deliveries": a.Broker.Dropped(), "mcp_url": a.Cfg.McpURL,
	})
}

func (a *API) agentCard(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, 200, map[string]any{
		"name": contract.Agent, "codename": "Pulse", "folder": "market-pulse", "language": "Go (standard library only)",
		"version": config.Version, "description": "Market and news events, matched to each client's holdings; live stream.",
		"auth": "Bearer SERVICE_TOKEN", "depends_on": map[string]string{"advisor-tools MCP server": a.Cfg.McpURL},
		"endpoints": map[string]string{"invoke": "/invoke", "events": "/v1/events", "stream": "/v1/stream",
			"docs": "/docs", "openapi": "/openapi.json"},
		"skills": a.skills,
	})
}

// ------------------------------------------------------------------ /invoke

func (a *API) invoke(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	var req contract.Request
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		var tooBig *http.MaxBytesError
		if errors.As(err, &tooBig) {
			writeJSON(w, 413, detail("Body too large"))
			return
		}
		writeJSON(w, 422, detail("Body is not valid JSON"))
		return
	}
	if err := req.Validate(); err != nil {
		writeJSON(w, 422, detail("invalid request: "+err.Error()))
		return
	}
	if req.Input == nil {
		req.Input = map[string]json.RawMessage{}
	}
	skill, ok := a.skills[req.Skill]
	if !ok {
		writeJSON(w, 200, contract.Fail("unknown skill "+req.Skill))
		return
	}
	out, err := skill.Run(r.Context(), req.Input, *req.Context)
	ms := time.Since(start).Milliseconds()
	if err != nil {
		var inputErr *skills.InputError
		if errors.As(err, &inputErr) || errors.Is(err, holdings.ErrNotFound) {
			a.Log.Info("invoke_failed", "skill", req.Skill, "reason", err.Error(), "ms", ms, "trace", req.Context.TraceID)
			writeJSON(w, 200, contract.Fail(strings.TrimPrefix(err.Error(), "not found: ")))
			return
		}
		panic(err) // unexpected: recoverPanics answers 500 with the trace id
	}
	a.Log.Info("invoke", "skill", req.Skill, "ms", ms, "trace", req.Context.TraceID)
	writeJSON(w, 200, contract.OK(out))
}

// ------------------------------------------------------------------ /v1/events

func (a *API) listEvents(w http.ResponseWriter, r *http.Request) {
	input := map[string]json.RawMessage{}
	if d := r.URL.Query().Get("days"); d != "" {
		input["days"] = json.RawMessage(d)
	}
	if s := r.URL.Query().Get("symbol"); s != "" {
		input["symbol"], _ = json.Marshal(s)
	}
	out, err := a.skills["list_events"].Run(r.Context(), input, contract.Context{TraceID: r.Header.Get("X-Trace-Id")})
	if err != nil {
		writeJSON(w, 422, detail(err.Error()))
		return
	}
	writeJSON(w, 200, out)
}

// ingest: validate -> quarantine check -> dedupe -> store -> publish to live streams.
func (a *API) ingest(w http.ResponseWriter, r *http.Request) {
	var e events.Event
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields() // a feed we didn't design for is a feed we don't trust
	if err := dec.Decode(&e); err != nil {
		var tooBig *http.MaxBytesError
		if errors.As(err, &tooBig) {
			writeJSON(w, 413, detail("Body too large"))
			return
		}
		writeJSON(w, 422, detail("invalid event: "+err.Error()))
		return
	}
	trace := r.Header.Get("X-Trace-Id")
	dup, err := a.Service.Feed.Add(e)
	switch {
	case errors.Is(err, events.ErrQuarantined):
		a.Log.Warn("event_quarantined", "event_id", e.EventID, "trace", trace) // id only: never log the payload
		writeJSON(w, 422, detail(err.Error()))
	case errors.Is(err, events.ErrConflict):
		writeJSON(w, 409, detail(err.Error()))
	case err != nil:
		writeJSON(w, 422, detail("invalid event: "+err.Error()))
	case dup:
		writeJSON(w, 200, map[string]any{"event_id": e.EventID, "duplicate": true})
	default:
		a.Log.Info("event_ingested", "event_id", e.EventID, "severity", e.Severity, "subscribers", a.Broker.Subscribers(), "trace", trace)
		writeJSON(w, 201, map[string]any{"event_id": e.EventID, "duplicate": false, "delivered_to": a.Broker.Subscribers()})
	}
}

// ------------------------------------------------------------------ /v1/stream (SSE)

// stream keeps the connection open and pushes each new event as it's ingested.
//
// LEARN: Server-Sent Events = one long HTTP response, written a piece at a
// time ("event: ...\ndata: {...}\n\n"), flushed so the browser sees it at
// once. A `select` waits on three things at the same time: a new event, a
// heartbeat tick, or the client going away.
func (a *API) stream(w http.ResponseWriter, r *http.Request) {
	var book *holdings.Book
	if id := r.URL.Query().Get("client_id"); id != "" {
		if err := contract.ID("client_id", id); err != nil {
			writeJSON(w, 422, detail(err.Error()))
			return
		}
		b, err := a.Service.Holdings.Get(r.Context(), id, r.Header.Get("X-Trace-Id"))
		if err != nil {
			writeJSON(w, 404, detail(err.Error()))
			return
		}
		book = &b
	}
	sub, unsubscribe, err := a.Broker.Subscribe()
	if err != nil {
		writeJSON(w, 503, detail(err.Error()))
		return
	}
	defer unsubscribe()

	rc := http.NewResponseController(w)
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(200)
	hello := map[string]any{"agent": contract.Agent, "filter_client_id": nil, "note": skills.ExternalTextNote}
	if book != nil {
		hello["filter_client_id"] = book.ClientID
	}
	writeSSE(w, "hello", "", hello)
	_ = rc.Flush()

	heartbeat := time.NewTicker(15 * time.Second)
	defer heartbeat.Stop()
	for {
		select {
		case <-r.Context().Done(): // client left, or the server is shutting down
			return
		case <-heartbeat.C:
			if _, err := io.WriteString(w, ": ping\n\n"); err != nil {
				return
			}
			_ = rc.Flush()
		case e, ok := <-sub:
			if !ok {
				return
			}
			payload := any(e)
			if book != nil {
				hits := impact.Match(*book, []events.Event{e}, a.Service.Symbols)
				if len(hits) == 0 {
					continue // not about this client's holdings
				}
				payload = hits[0]
			}
			writeSSE(w, "market_event", e.EventID, payload)
			if err := rc.Flush(); err != nil {
				return
			}
		}
	}
}

func writeSSE(w io.Writer, event, id string, data any) {
	b, _ := json.Marshal(data)
	if id != "" {
		fmt.Fprintf(w, "id: %s\n", id)
	}
	fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event, b)
}

// ------------------------------------------------------------------ helpers

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func detail(msg string) map[string]string { return map[string]string{"detail": msg} }

func newTraceID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}
