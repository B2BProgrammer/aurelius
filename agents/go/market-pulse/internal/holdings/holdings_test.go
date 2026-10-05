package holdings

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"
)

const token = "test-service-token-abcdefghijklmnop"

var lineBreaks = regexp.MustCompile(`\s*\n\s*`)

// fakeMCP answers like the real Python server: SSE replies, a session header, 401 on a bad token.
func fakeMCP(t *testing.T) (*httptest.Server, *[]string) {
	t.Helper()
	var mu sync.Mutex
	seen := []string{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		mu.Lock()
		seen = append(seen, fmt.Sprintf("%s %s session=%s trace=%s", r.Method, body, r.Header.Get("mcp-session-id"), r.Header.Get("X-Trace-Id")))
		mu.Unlock()
		if r.Header.Get("Authorization") != "Bearer "+token {
			w.WriteHeader(401)
			return
		}
		var msg struct {
			ID     int    `json:"id"`
			Method string `json:"method"`
			Params struct {
				Name      string         `json:"name"`
				Arguments map[string]any `json:"arguments"`
			} `json:"params"`
		}
		_ = json.Unmarshal(body, &msg)
		if r.Method == http.MethodDelete || msg.Method == "notifications/initialized" {
			w.WriteHeader(202)
			return
		}
		var result string
		switch {
		case msg.Method == "initialize":
			w.Header().Set("mcp-session-id", "sess-1")
			result = `{"protocolVersion":"2025-06-18"}`
		case msg.Params.Arguments["client_id"] == "nobody-1":
			result = `{"content":[{"type":"text","text":"Error executing tool get_holdings: No client with id 'nobody-1'"}],"isError":true}`
		case msg.Params.Name == "list_clients":
			result = `{"isError":false,"structuredContent":{"clients":[{"client_id":"b-2"},{"client_id":"a-1"}]}}`
		default:
			result = `{"isError":false,"structuredContent":{"as_of":"2026-10-01","total_market_value":1000,"positions":[
				{"symbol":"XYZ","asset_class":"equity","security_type":"stock","market_value":300},
				{"symbol":"AGGB","asset_class":"fixed_income","security_type":"fund","market_value":600},
				{"symbol":"XYZ","asset_class":"equity","security_type":"stock","market_value":100}]}}`
		}
		result = lineBreaks.ReplaceAllString(result, "") // one line per data:, like a real server
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprintf(w, "event: message\r\ndata: {\"jsonrpc\":\"2.0\",\"id\":%d,\"result\":%s}\r\n\r\n", msg.ID, result)
	}))
	t.Cleanup(srv.Close)
	return srv, &seen
}

func TestHandshakeToolCallClose(t *testing.T) {
	srv, seen := fakeMCP(t)
	c := NewMCPClient(srv.URL, token, 2*time.Second)
	raw, err := c.CallTool(context.Background(), "get_holdings", map[string]any{"client_id": "patel-001"}, "trace-42")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(raw), `"total_market_value":1000`) {
		t.Errorf("raw = %s", raw)
	}
	s := *seen
	if len(s) != 4 || !strings.Contains(s[0], `"initialize"`) || !strings.Contains(s[1], "session=sess-1") ||
		!strings.Contains(s[2], "trace=trace-42") || !strings.HasPrefix(s[3], "DELETE") {
		t.Errorf("protocol steps: %v", s)
	}
}

func TestSourceMergesPositionsAndReportsMCP(t *testing.T) {
	srv, _ := fakeMCP(t)
	src := &Source{MCP: NewMCPClient(srv.URL, token, 2*time.Second)}
	b, err := src.Get(context.Background(), "patel-001", "t")
	if err != nil {
		t.Fatal(err)
	}
	if b.Source != "mcp" || len(b.Positions) != 2 || b.Positions[0].Symbol != "AGGB" || b.Positions[1].MarketValue != 400 {
		t.Errorf("book = %+v", b)
	}
	if ids := src.ClientIDs(context.Background(), "t"); strings.Join(ids, ",") != "a-1,b-2" {
		t.Errorf("ids = %v", ids)
	}
}

func TestUnknownClientIsNotFoundNotFallback(t *testing.T) {
	srv, _ := fakeMCP(t)
	snap, _ := LoadSnapshot(filepath.Join("..", "..", "data", "holdings-snapshot.json"))
	src := &Source{MCP: NewMCPClient(srv.URL, token, 2*time.Second), Snapshot: snap}
	_, err := src.Get(context.Background(), "nobody-1", "t")
	if !errors.Is(err, ErrNotFound) || !strings.Contains(err.Error(), "No client with id 'nobody-1'") {
		t.Errorf("err = %v", err)
	}
}

func TestFallsBackWhenMCPIsDownOrRejectsUs(t *testing.T) {
	snap, err := LoadSnapshot(filepath.Join("..", "..", "data", "holdings-snapshot.json"))
	if err != nil {
		t.Fatal(err)
	}
	srv, _ := fakeMCP(t)
	for name, client := range map[string]*MCPClient{
		"down":        NewMCPClient("http://127.0.0.1:1/mcp", token, 500*time.Millisecond),
		"wrong token": NewMCPClient(srv.URL, "wrong-token", time.Second),
	} {
		b, err := (&Source{MCP: client, Snapshot: snap}).Get(context.Background(), "chen-002", "t")
		if err != nil || !strings.HasPrefix(b.Source, "snapshot (MCP unavailable") || b.TotalMarketValue != 900000.25 {
			t.Errorf("%s: source=%q total=%v err=%v", name, b.Source, b.TotalMarketValue, err)
		}
	}
}

func TestSSEData(t *testing.T) {
	if got := string(SSEData([]byte("event: message\r\ndata: {\"a\":1}\r\n\r\n"))); got != `{"a":1}` {
		t.Errorf("got %q", got)
	}
}
