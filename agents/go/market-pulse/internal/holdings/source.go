package holdings

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"sort"
)

// Position is one security in a client's book (same symbol in several accounts = one position).
type Position struct {
	Symbol       string  `json:"symbol"`
	Name         string  `json:"name"`
	AssetClass   string  `json:"asset_class"`
	SecurityType string  `json:"security_type"`
	MarketValue  float64 `json:"market_value"`
}

// Book is a client's whole portfolio as Pulse sees it.
type Book struct {
	ClientID         string     `json:"client_id"`
	Household        string     `json:"household,omitempty"`
	AsOf             string     `json:"as_of"`
	TotalMarketValue float64    `json:"total_market_value"`
	Positions        []Position `json:"positions"`
	Source           string     `json:"-"` // "mcp" or "snapshot (...)"
}

// ErrNotFound: unknown client (never a reason to fall back to the snapshot).
var ErrNotFound = errors.New("not found")

// Source tries MCP first, then the snapshot, and says which one answered.
type Source struct {
	MCP      *MCPClient // nil = snapshot only (tests)
	Snapshot map[string]Book
	Log      *slog.Logger
}

func LoadSnapshot(path string) (map[string]Book, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var file struct {
		Clients map[string]Book `json:"clients"`
	}
	if err := json.Unmarshal(raw, &file); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	for id, b := range file.Clients {
		b.ClientID, b.Source = id, "snapshot"
		file.Clients[id] = b
	}
	return file.Clients, nil
}

func (s *Source) Get(ctx context.Context, clientID, traceID string) (Book, error) {
	if s.MCP != nil {
		book, err := s.fromMCP(ctx, clientID, traceID)
		if err == nil {
			return book, nil
		}
		var toolErr *ToolError
		if errors.As(err, &toolErr) {
			return Book{}, fmt.Errorf("%w: %s", ErrNotFound, toolErr.Message)
		}
		if s.Log != nil {
			s.Log.Warn("mcp_unavailable", "reason", err.Error(), "trace", traceID)
		}
		book, snapErr := s.fromSnapshot(clientID)
		if snapErr != nil {
			return Book{}, snapErr
		}
		book.Source = "snapshot (MCP unavailable: " + err.Error() + ")"
		return book, nil
	}
	return s.fromSnapshot(clientID)
}

// ClientIDs: from MCP list_clients when possible, else the snapshot's keys.
func (s *Source) ClientIDs(ctx context.Context, traceID string) []string {
	if s.MCP != nil {
		if raw, err := s.MCP.CallTool(ctx, "list_clients", map[string]any{}, traceID); err == nil {
			var r struct {
				Clients []struct {
					ClientID string `json:"client_id"`
				} `json:"clients"`
			}
			if json.Unmarshal(raw, &r) == nil && len(r.Clients) > 0 {
				ids := make([]string, 0, len(r.Clients))
				for _, c := range r.Clients {
					ids = append(ids, c.ClientID)
				}
				sort.Strings(ids)
				return ids
			}
		}
	}
	ids := make([]string, 0, len(s.Snapshot))
	for id := range s.Snapshot {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

func (s *Source) fromSnapshot(clientID string) (Book, error) {
	b, ok := s.Snapshot[clientID]
	if !ok {
		return Book{}, fmt.Errorf("%w: no holdings for client '%s'", ErrNotFound, clientID)
	}
	return b, nil
}

// fromMCP calls get_holdings and merges positions by symbol.
func (s *Source) fromMCP(ctx context.Context, clientID, traceID string) (Book, error) {
	raw, err := s.MCP.CallTool(ctx, "get_holdings", map[string]any{"client_id": clientID}, traceID)
	if err != nil {
		return Book{}, err
	}
	var h struct {
		AsOf      string     `json:"as_of"`
		Total     float64    `json:"total_market_value"`
		Positions []Position `json:"positions"`
	}
	if err := json.Unmarshal(raw, &h); err != nil {
		return Book{}, fmt.Errorf("%w: holdings are not JSON", ErrUnavailable)
	}
	merged := map[string]*Position{}
	order := []string{}
	for _, p := range h.Positions {
		if m, ok := merged[p.Symbol]; ok {
			m.MarketValue += p.MarketValue
			continue
		}
		cp := p
		merged[p.Symbol] = &cp
		order = append(order, p.Symbol)
	}
	book := Book{ClientID: clientID, AsOf: h.AsOf, TotalMarketValue: h.Total, Source: "mcp"}
	for _, sym := range order {
		book.Positions = append(book.Positions, *merged[sym])
	}
	sort.Slice(book.Positions, func(i, j int) bool { return book.Positions[i].MarketValue > book.Positions[j].MarketValue })
	return book, nil
}
