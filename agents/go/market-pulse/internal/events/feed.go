// Package events holds the market/news feed: the event model, the in-memory
// feed with ingest + dedupe, the ingest guard and the live-stream broker.
package events

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sort"
	"sync"
	"time"
)

// Event is one market or news item. External text (headline, summary) is
// UNTRUSTED: it came from outside the firm and may end up in an LLM prompt.
type Event struct {
	EventID        string   `json:"event_id"`
	Date           string   `json:"date"` // YYYY-MM-DD
	Type           string   `json:"type"`
	Severity       string   `json:"severity"` // low | medium | high
	Headline       string   `json:"headline"`
	Summary        string   `json:"summary,omitempty"`
	Source         string   `json:"source,omitempty"`
	Symbols        []string `json:"symbols,omitempty"`       // direct: these securities
	AssetClasses   []string `json:"asset_classes,omitempty"` // broad: equity | fixed_income | cash
	Regions        []string `json:"regions,omitempty"`       // broad: us | international | emerging
	Sectors        []string `json:"sectors,omitempty"`       // broad: technology, industrials, ...
	PriceChangePct *float64 `json:"price_change_pct,omitempty"`
}

func (e Event) Day() time.Time {
	t, _ := time.Parse(time.DateOnly, e.Date)
	return t
}

// ErrConflict: same event_id, different content (someone is rewriting history).
var ErrConflict = errors.New("an event with this event_id already exists with different content")

// Feed is the event store. Safe for many goroutines at once.
//
// LEARN: sync.RWMutex lets MANY readers in at the same time, but a writer
// waits until it's alone. Reads (every skill call) vastly outnumber writes
// (ingest), so this is faster than a plain Mutex.
type Feed struct {
	mu     sync.RWMutex
	events map[string]Event
	broker *Broker
}

func LoadFeed(path string, broker *Broker) (*Feed, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var file struct {
		Events []Event `json:"events"`
	}
	if err := json.Unmarshal(raw, &file); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	f := &Feed{events: map[string]Event{}, broker: broker}
	for _, e := range file.Events {
		if err := Validate(&e); err != nil {
			return nil, fmt.Errorf("%s: %s: %w", path, e.EventID, err)
		}
		f.events[e.EventID] = e
	}
	return f, nil
}

// Since returns events on or after `from`, newest first.
func (f *Feed) Since(from time.Time) []Event {
	f.mu.RLock()
	defer f.mu.RUnlock()
	out := []Event{}
	for _, e := range f.events {
		if !e.Day().Before(from) {
			out = append(out, e)
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Date != out[j].Date {
			return out[i].Date > out[j].Date
		}
		return out[i].EventID > out[j].EventID
	})
	return out
}

func (f *Feed) Get(id string) (Event, bool) {
	f.mu.RLock()
	defer f.mu.RUnlock()
	e, ok := f.events[id]
	return e, ok
}

func (f *Feed) Count() int {
	f.mu.RLock()
	defer f.mu.RUnlock()
	return len(f.events)
}

// Add stores a validated event and publishes it to live subscribers.
// Idempotent: the same event twice -> duplicate=true, nothing published again.
func (f *Feed) Add(e Event) (duplicate bool, err error) {
	if err := Validate(&e); err != nil {
		return false, err
	}
	f.mu.Lock()
	if old, ok := f.events[e.EventID]; ok {
		f.mu.Unlock()
		if same(old, e) {
			return true, nil
		}
		return false, ErrConflict
	}
	f.events[e.EventID] = e
	f.mu.Unlock() // never hold a lock while doing anything slow
	if f.broker != nil {
		f.broker.Publish(e)
	}
	return false, nil
}

func same(a, b Event) bool {
	ja, _ := json.Marshal(a)
	jb, _ := json.Marshal(b)
	return string(ja) == string(jb)
}
