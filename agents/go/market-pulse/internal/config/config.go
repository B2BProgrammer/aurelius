// Package config reads Pulse's settings from aurelius\.env (shared) and
// market-pulse\.env (overrides). Real environment variables win over both.
//
// LEARN: Go has no built-in .env reader and we use no third-party packages,
// so this is ~40 lines of our own: same rules as the other agents.
package config

import (
	"bufio"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const Version = "0.1.0"

var weakTokens = map[string]bool{"": true, "replace-me": true, "replace-with-long-random-string": true}

// Config is every setting Pulse uses. Built once at startup, then read-only.
type Config struct {
	Host           string
	Port           int
	ServiceToken   string
	McpURL         string
	McpTimeout     time.Duration
	EventsFile     string
	SnapshotFile   string
	SymbolsFile    string
	DefaultDays    int
	MaxSubscribers int
	SimulateEvery  time.Duration // 0 = off; >0 = publish a demo event every N seconds
	AsOf           string        // "" = today; "2026-10-03" freezes the demo date
}

// Load merges .env files under the real environment and returns the config.
func Load() Config {
	env := map[string]string{}
	if wd, err := os.Getwd(); err == nil {
		for dir, i := filepath.Dir(wd), 0; i < 5; dir, i = filepath.Dir(dir), i+1 {
			if vals, err := ReadDotEnv(filepath.Join(dir, ".env")); err == nil {
				for k, v := range vals {
					env[k] = v
				}
				break
			}
		}
		if vals, err := ReadDotEnv(filepath.Join(wd, ".env")); err == nil { // agent's own file wins
			for k, v := range vals {
				env[k] = v
			}
		}
	}
	get := func(key, def string) string {
		if v, ok := os.LookupEnv(key); ok { // real environment wins
			return v
		}
		if v, ok := env[key]; ok {
			return v
		}
		return def
	}
	return Config{
		Host:           get("PULSE_HOST", "127.0.0.1"),
		Port:           atoi(get("PULSE_PORT", "8301"), 8301),
		ServiceToken:   get("SERVICE_TOKEN", ""),
		McpURL:         get("MCP_ADVISOR_TOOLS_URL", "http://127.0.0.1:8500/mcp"),
		McpTimeout:     time.Duration(atoi(get("PULSE_MCP_TIMEOUT_MS", "5000"), 5000)) * time.Millisecond,
		EventsFile:     get("PULSE_EVENTS_FILE", filepath.Join("data", "events.json")),
		SnapshotFile:   get("PULSE_SNAPSHOT_FILE", filepath.Join("data", "holdings-snapshot.json")),
		SymbolsFile:    get("PULSE_SYMBOLS_FILE", filepath.Join("data", "symbols.json")),
		DefaultDays:    atoi(get("PULSE_DEFAULT_DAYS", "14"), 14),
		MaxSubscribers: atoi(get("PULSE_MAX_SUBSCRIBERS", "50"), 50),
		SimulateEvery:  time.Duration(atoi(get("PULSE_SIMULATE_SECONDS", "0"), 0)) * time.Second,
		AsOf:           get("PULSE_AS_OF", ""),
	}
}

// CheckSecurity fails closed: never start with a guessable token.
func (c Config) CheckSecurity() error {
	if weakTokens[c.ServiceToken] || len(c.ServiceToken) < 24 {
		return errors.New(`SERVICE_TOKEN is missing or too short (need 24+ chars) in aurelius\.env. Use the same value as the other agents`)
	}
	return nil
}

// ReadDotEnv parses KEY=VALUE lines: comments, blank lines, "export ", quotes, trailing "  # comment".
func ReadDotEnv(path string) (map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	out := map[string]string{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		line = strings.TrimSpace(strings.TrimPrefix(line, "export "))
		key, value, ok := strings.Cut(line, "=")
		if !ok || strings.TrimSpace(key) == "" {
			continue
		}
		value = strings.TrimSpace(value)
		if len(value) >= 2 && (value[0] == '"' && value[len(value)-1] == '"' || value[0] == '\'' && value[len(value)-1] == '\'') {
			value = value[1 : len(value)-1]
		} else if i := strings.Index(value, " #"); i >= 0 {
			value = strings.TrimSpace(value[:i])
		} else if i := strings.Index(value, "\t#"); i >= 0 {
			value = strings.TrimSpace(value[:i])
		}
		out[strings.TrimSpace(key)] = value
	}
	return out, sc.Err()
}

func atoi(s string, def int) int {
	n, err := strconv.Atoi(strings.TrimSpace(s))
	if err != nil {
		return def
	}
	return n
}
