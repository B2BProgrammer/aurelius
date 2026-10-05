package impact

import (
	"path/filepath"
	"testing"

	"aurelius/pulse/internal/events"
	"aurelius/pulse/internal/holdings"
)

func pct(v float64) *float64 { return &v }

func setup(t *testing.T) (map[string]holdings.Book, map[string]SymbolInfo) {
	t.Helper()
	snap, err := holdings.LoadSnapshot(filepath.Join("..", "..", "data", "holdings-snapshot.json"))
	if err != nil {
		t.Fatal(err)
	}
	syms, err := LoadSymbols(filepath.Join("..", "..", "data", "symbols.json"))
	if err != nil {
		t.Fatal(err)
	}
	return snap, syms
}

func TestDirectHitWithDollarImpact(t *testing.T) {
	snap, syms := setup(t)
	e := events.Event{EventID: "EV-1", Date: "2026-10-01", Severity: "high", Headline: "XYZ misses",
		Symbols: []string{"XYZ"}, PriceChangePct: pct(-9)}
	hits := Match(snap["patel-001"], []events.Event{e}, syms)
	if len(hits) != 1 {
		t.Fatalf("hits = %d", len(hits))
	}
	h := hits[0]
	// 329,000 x -9% = -29,610
	if h.Match != "direct" || h.Exposure != 329000 || h.ExposurePct != 14 || *h.EstimatedImpact != -29610 {
		t.Errorf("got %+v", h)
	}
	if h.Why != "XYZ: $329,000 (14.0% of the portfolio), direct exposure; a -9.0% move is about -$29,610." {
		t.Errorf("why = %q", h.Why)
	}
}

func TestIndirectMatchesByRegionAndClassButNeverCash(t *testing.T) {
	snap, syms := setup(t)
	em := events.Event{EventID: "EV-2", Severity: "medium", Headline: "EM slide", AssetClasses: []string{"equity"}, Regions: []string{"emerging"}}
	if hits := Match(snap["garcia-003"], []events.Event{em}, syms); len(hits) != 1 || hits[0].HoldingsHit[0] != "EMKT" {
		t.Errorf("Garcia holds EMKT: %+v", hits)
	}
	if hits := Match(snap["patel-001"], []events.Event{em}, syms); len(hits) != 0 {
		t.Errorf("Patel holds no emerging markets: %+v", hits)
	}
	rates := events.Event{EventID: "EV-3", Severity: "medium", Headline: "Rates", AssetClasses: []string{"fixed_income"}, Regions: []string{"us"}}
	hits := Match(snap["patel-001"], []events.Event{rates}, syms)
	if len(hits) != 1 || len(hits[0].HoldingsHit) != 1 || hits[0].HoldingsHit[0] != "AGGB" {
		t.Errorf("US bonds only (AGGB, not international AIBF, not cash MMKT): %+v", hits)
	}
}

func TestDirectNewsOutranksBroadNews(t *testing.T) {
	snap, syms := setup(t)
	evs := []events.Event{
		{EventID: "EV-10", Date: "2026-09-22", Severity: "low", Headline: "US record", AssetClasses: []string{"equity"}, Regions: []string{"us"}},
		{EventID: "EV-11", Date: "2026-09-30", Severity: "high", Headline: "XYZ misses", Symbols: []string{"XYZ"}},
	}
	hits := Match(snap["patel-001"], evs, syms)
	if hits[0].EventID != "EV-11" {
		t.Errorf("XYZ earnings miss should rank first, got %s (%.3f vs %.3f)", hits[0].EventID, hits[0].Relevance, hits[1].Relevance)
	}
}

func TestEventsForOtherHoldingsAreIgnored(t *testing.T) {
	snap, syms := setup(t)
	abc := events.Event{EventID: "EV-4", Severity: "high", Headline: "ABC news", Symbols: []string{"ABC"}}
	if hits := Match(snap["chen-002"], []events.Event{abc}, syms); len(hits) != 0 {
		t.Errorf("Chen holds no ABC: %+v", hits)
	}
}
