// Package impact answers "which of these events matter to THIS client, and how much?"
//
// LEARN: An event can hit a portfolio two ways:
//
//	DIRECT    the event names a security the client holds ("XYZ misses earnings")
//	INDIRECT  the event is about a whole slice of the market the client is in
//	          ("emerging-market stocks slide" -> the client's EMKT fund)
//
// Relevance = severity weight x share of the portfolio exposed x match weight.
// A direct hit counts fully; an indirect one counts half, because broad news
// reaches the client through diversified funds, diluted. So "XYZ misses
// earnings" outranks "US stocks hit a record" even though index funds are bigger.
package impact

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"slices"
	"sort"
	"strings"

	"aurelius/pulse/internal/events"
	"aurelius/pulse/internal/holdings"
)

// SymbolInfo says where a security sits (for indirect matches).
type SymbolInfo struct {
	Region string `json:"region"`
	Sector string `json:"sector"`
}

func LoadSymbols(path string) (map[string]SymbolInfo, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var file struct {
		Symbols map[string]SymbolInfo `json:"symbols"`
	}
	if err := json.Unmarshal(raw, &file); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return file.Symbols, nil
}

var (
	severityWeight = map[string]float64{"low": 1, "medium": 2, "high": 3}
	matchWeight    = map[string]float64{"direct": 1.0, "indirect": 0.5}
)

// Hit is one event that affects one client.
type Hit struct {
	EventID         string   `json:"event_id"`
	Date            string   `json:"date"`
	Type            string   `json:"type"`
	Severity        string   `json:"severity"`
	Headline        string   `json:"headline"`
	Summary         string   `json:"summary,omitempty"`
	Source          string   `json:"source,omitempty"`
	Match           string   `json:"match"` // direct | indirect
	HoldingsHit     []string `json:"holdings_hit"`
	Exposure        int64    `json:"exposure"`
	ExposurePct     float64  `json:"exposure_pct"`
	EstimatedImpact *int64   `json:"estimated_impact,omitempty"` // dollars, when the event has a price move
	Relevance       float64  `json:"relevance"`
	Why             string   `json:"why"`
}

// Match finds the events in `evs` that touch `book`, most relevant first.
func Match(book holdings.Book, evs []events.Event, symbols map[string]SymbolInfo) []Hit {
	hits := []Hit{}
	for _, e := range evs {
		var hitSyms []string
		var exposure float64
		match := "indirect"
		for _, p := range book.Positions {
			if slices.Contains(e.Symbols, p.Symbol) {
				match = "direct"
				hitSyms = append(hitSyms, p.Symbol)
				exposure += p.MarketValue
			}
		}
		if match != "direct" && len(e.Symbols) == 0 { // broad event: check every position
			for _, p := range book.Positions {
				if touches(e, p, symbols[p.Symbol]) {
					hitSyms = append(hitSyms, p.Symbol)
					exposure += p.MarketValue
				}
			}
		}
		if len(hitSyms) == 0 || book.TotalMarketValue <= 0 {
			continue
		}
		share := exposure / book.TotalMarketValue
		h := Hit{
			EventID: e.EventID, Date: e.Date, Type: e.Type, Severity: e.Severity,
			Headline: e.Headline, Summary: e.Summary, Source: e.Source, Match: match,
			HoldingsHit: hitSyms, Exposure: round(exposure, 1), ExposurePct: math.Round(share*1000) / 10,
			Relevance: math.Round(severityWeight[e.Severity]*share*matchWeight[match]*1000) / 1000,
		}
		why := fmt.Sprintf("%s: %s (%.1f%% of the portfolio), %s exposure",
			strings.Join(hitSyms, ", "), usd(exposure), h.ExposurePct, match)
		if e.PriceChangePct != nil && *e.PriceChangePct != 0 {
			est := round(exposure**e.PriceChangePct/100, 10)
			h.EstimatedImpact = &est
			why += fmt.Sprintf("; a %+.1f%% move is about %s", *e.PriceChangePct, signedUSD(est))
		}
		h.Why = why + "."
		hits = append(hits, h)
	}
	sort.SliceStable(hits, func(i, j int) bool {
		if hits[i].Relevance != hits[j].Relevance {
			return hits[i].Relevance > hits[j].Relevance
		}
		return hits[i].Date > hits[j].Date
	})
	return hits
}

// touches: does a broad event (asset class / region / sector) cover this position?
// Every dimension the event names must match; unnamed dimensions match anything.
func touches(e events.Event, p holdings.Position, info SymbolInfo) bool {
	if p.AssetClass == "cash" {
		return false // a money-market fund doesn't move with market news
	}
	if len(e.AssetClasses) > 0 && !slices.Contains(e.AssetClasses, p.AssetClass) {
		return false
	}
	if len(e.Regions) > 0 && !slices.Contains(e.Regions, info.Region) {
		return false
	}
	if len(e.Sectors) > 0 && !slices.Contains(e.Sectors, info.Sector) {
		return false
	}
	return true
}

func round(v, to float64) int64 { return int64(math.Round(v/to) * to) }

func usd(v float64) string {
	n := int64(math.Round(v))
	s := fmt.Sprintf("%d", n)
	for i := len(s) - 3; i > 0; i -= 3 {
		s = s[:i] + "," + s[i:]
	}
	return "$" + s
}

func signedUSD(v int64) string {
	if v < 0 {
		return "-" + usd(float64(-v))
	}
	return "+" + usd(float64(v))
}
