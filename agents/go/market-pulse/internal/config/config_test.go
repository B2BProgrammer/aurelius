package config

import (
	"os"
	"path/filepath"
	"testing"
)

// LEARN: Go tests are plain functions named TestXxx(t *testing.T) in *_test.go
// files next to the code. `go test ./...` finds and runs them all.

func TestReadDotEnvFollowsTheSameRulesAsTheOtherAgents(t *testing.T) {
	path := filepath.Join(t.TempDir(), ".env")
	content := "# comment\n\nSERVICE_TOKEN=abc123     # same token everywhere\nexport LLM_MOCK=true\nQUOTED=\"has # hash\"\nEMPTY=\nURL=http://127.0.0.1:8102\n"
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	got, err := ReadDotEnv(path)
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]string{"SERVICE_TOKEN": "abc123", "LLM_MOCK": "true", "QUOTED": "has # hash", "EMPTY": "", "URL": "http://127.0.0.1:8102"}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("%s = %q, want %q", k, got[k], v)
		}
	}
}

func TestWeakTokensAreRejected(t *testing.T) {
	for _, tok := range []string{"", "replace-me", "replace-with-long-random-string", "short-token"} {
		if (Config{ServiceToken: tok}).CheckSecurity() == nil {
			t.Errorf("token %q should be rejected", tok)
		}
	}
	if err := (Config{ServiceToken: "a-long-enough-service-token-123"}).CheckSecurity(); err != nil {
		t.Errorf("good token rejected: %v", err)
	}
}
