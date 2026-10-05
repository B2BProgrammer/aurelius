package events

import (
	"errors"
	"sync"
	"sync/atomic"
)

// ErrTooManySubscribers protects the server: each live stream holds a connection open.
var ErrTooManySubscribers = errors.New("too many live subscribers")

// Broker fans new events out to every live subscriber (pub/sub).
//
// LEARN, Go concurrency in 30 lines:
//   - each subscriber gets its own CHANNEL (a typed queue between goroutines)
//   - Publish never blocks: if a subscriber's buffer is full (a slow reader),
//     the event is dropped FOR THAT SUBSCRIBER and counted. One slow browser
//     tab must not freeze ingest for everybody. That's "backpressure".
//   - Unsubscribe closes the channel, which ends the reader's `for range` loop.
type Broker struct {
	mu      sync.Mutex
	subs    map[int]chan Event
	nextID  int
	max     int
	dropped atomic.Int64
}

func NewBroker(maxSubscribers int) *Broker {
	return &Broker{subs: map[int]chan Event{}, max: maxSubscribers}
}

// Subscribe returns a channel of new events and a function to stop.
func (b *Broker) Subscribe() (<-chan Event, func(), error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if len(b.subs) >= b.max {
		return nil, nil, ErrTooManySubscribers
	}
	id := b.nextID
	b.nextID++
	ch := make(chan Event, 16)
	b.subs[id] = ch
	var once sync.Once
	return ch, func() {
		once.Do(func() {
			b.mu.Lock()
			delete(b.subs, id)
			close(ch)
			b.mu.Unlock()
		})
	}, nil
}

// Publish delivers e to every subscriber without ever blocking.
func (b *Broker) Publish(e Event) {
	b.mu.Lock()
	defer b.mu.Unlock()
	for _, ch := range b.subs {
		select {
		case ch <- e:
		default:
			b.dropped.Add(1) // that subscriber is too slow: skip it, keep going
		}
	}
}

func (b *Broker) Subscribers() int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return len(b.subs)
}

func (b *Broker) Dropped() int64 { return b.dropped.Load() }
