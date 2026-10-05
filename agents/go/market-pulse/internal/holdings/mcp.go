// Package holdings gets each client's positions: live from the advisor-tools
// MCP server, or (only when it's down) from a snapshot file.
package holdings

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync/atomic"
	"time"
)

// ErrUnavailable: the server is down, slow, or refused us. Callers may fall back.
var ErrUnavailable = errors.New("mcp unavailable")

// ToolError: the tool ran and said no (e.g. "No client with id 'x'"). Not a connectivity problem.
type ToolError struct{ Message string }

func (e *ToolError) Error() string { return e.Message }

const protocolVersion = "2025-06-18"

// MCPClient speaks MCP's "streamable HTTP" transport with net/http only.
//
// LEARN: three POSTs per tool call, the same as the Java Actuary:
// initialize (reply header mcp-session-id) -> notifications/initialized ->
// tools/call; then DELETE ends the session. Replies can be SSE ("data: {...}").
// Go's http.Client doesn't try HTTP/2 upgrades on http://, so the bug the
// Java client hit can't happen here.
type MCPClient struct {
	URL    string
	Token  string
	HTTP   *http.Client
	nextID atomic.Int64
}

func NewMCPClient(url, token string, timeout time.Duration) *MCPClient {
	return &MCPClient{URL: url, Token: token, HTTP: &http.Client{Timeout: timeout}}
}

// CallTool opens a session, calls one tool, closes the session; returns structuredContent.
func (c *MCPClient) CallTool(ctx context.Context, tool string, args map[string]any, traceID string) (json.RawMessage, error) {
	initBody, session, err := c.post(ctx, "", traceID, c.request("initialize", map[string]any{
		"protocolVersion": protocolVersion,
		"capabilities":    map[string]any{},
		"clientInfo":      map[string]any{"name": "aurelius-pulse", "version": "0.1.0"},
	}))
	if err != nil {
		return nil, err
	}
	_ = initBody
	defer c.close(session)
	if _, _, err := c.post(ctx, session, traceID, map[string]any{"jsonrpc": "2.0", "method": "notifications/initialized"}); err != nil {
		return nil, err
	}
	body, _, err := c.post(ctx, session, traceID, c.request("tools/call", map[string]any{"name": tool, "arguments": args}))
	if err != nil {
		return nil, err
	}
	var reply struct {
		Result struct {
			IsError           bool            `json:"isError"`
			StructuredContent json.RawMessage `json:"structuredContent"`
			Content           []struct {
				Text string `json:"text"`
			} `json:"content"`
		} `json:"result"`
	}
	if err := json.Unmarshal(body, &reply); err != nil {
		return nil, fmt.Errorf("%w: reply is not JSON", ErrUnavailable)
	}
	r := reply.Result
	if r.IsError {
		msg := "tool error"
		if len(r.Content) > 0 {
			msg = r.Content[0].Text
		}
		if _, after, ok := strings.Cut(msg, ": "); ok && strings.HasPrefix(msg, "Error executing tool") {
			msg = after
		}
		return nil, &ToolError{Message: msg}
	}
	if len(r.StructuredContent) > 0 && string(r.StructuredContent) != "null" {
		return r.StructuredContent, nil
	}
	if len(r.Content) > 0 {
		return json.RawMessage(r.Content[0].Text), nil
	}
	return nil, fmt.Errorf("%w: empty tool result", ErrUnavailable)
}

func (c *MCPClient) request(method string, params map[string]any) map[string]any {
	return map[string]any{"jsonrpc": "2.0", "id": c.nextID.Add(1), "method": method, "params": params}
}

// post sends one JSON-RPC message; returns the JSON body (SSE unwrapped) and the session id.
func (c *MCPClient) post(ctx context.Context, session, traceID string, msg map[string]any) (json.RawMessage, string, error) {
	payload, _ := json.Marshal(msg)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.URL, bytes.NewReader(payload))
	if err != nil {
		return nil, "", fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json, text/event-stream")
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("X-Trace-Id", traceID)
	if session != "" {
		req.Header.Set("mcp-session-id", session)
		req.Header.Set("mcp-protocol-version", protocolVersion)
	}
	res, err := c.HTTP.Do(req)
	if err != nil {
		return nil, "", fmt.Errorf("%w: not reachable at %s", ErrUnavailable, c.URL)
	}
	defer res.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(res.Body, 2<<20)) // 2 MB cap: never trust a peer's size
	if session == "" {
		session = res.Header.Get("mcp-session-id")
	}
	switch {
	case res.StatusCode == http.StatusUnauthorized:
		return nil, "", fmt.Errorf("%w: rejected our token (401)", ErrUnavailable)
	case res.StatusCode == http.StatusAccepted || len(bytes.TrimSpace(raw)) == 0:
		return nil, session, nil
	case res.StatusCode >= 400:
		return nil, "", fmt.Errorf("%w: HTTP %d", ErrUnavailable, res.StatusCode)
	}
	if strings.Contains(res.Header.Get("Content-Type"), "text/event-stream") {
		raw = SSEData(raw)
	}
	var rpcErr struct {
		Error *struct{ Message string } `json:"error"`
	}
	if json.Unmarshal(raw, &rpcErr) == nil && rpcErr.Error != nil {
		return nil, "", fmt.Errorf("%w: %s", ErrUnavailable, rpcErr.Error.Message)
	}
	return raw, session, nil
}

// SSEData joins the "data:" lines of a Server-Sent Events body (several lines join with \n).
func SSEData(body []byte) []byte {
	var out []string
	for _, line := range strings.Split(strings.ReplaceAll(string(body), "\r\n", "\n"), "\n") {
		if rest, ok := strings.CutPrefix(line, "data:"); ok {
			out = append(out, strings.TrimSpace(rest))
		}
	}
	return []byte(strings.Join(out, "\n"))
}

func (c *MCPClient) close(session string) {
	if session == "" {
		return
	}
	req, err := http.NewRequest(http.MethodDelete, c.URL, nil)
	if err != nil {
		return
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("mcp-session-id", session)
	if res, err := c.HTTP.Do(req); err == nil {
		res.Body.Close()
	}
}
