// Package contract is the agent contract, the same JSON every Aurelius agent speaks:
//
//	POST /invoke  {"skill": "...", "input": {...}, "context": {"trace_id": "...", "user_id": "..."}}
//	reply         {"agent": "pulse", "status": "ok"|"error", "output": {...}, "error": null|"..."}
package contract

import (
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strings"
)

const Agent = "pulse"

type Context struct {
	TraceID  string  `json:"trace_id"`
	UserID   string  `json:"user_id"`
	ClientID *string `json:"client_id,omitempty"`
}

type Request struct {
	Skill   string                     `json:"skill"`
	Input   map[string]json.RawMessage `json:"input"`
	Context *Context                   `json:"context"`
}

// Response: Output is "any" so each skill returns its own struct. Error is a pointer so it's null when OK.
type Response struct {
	Agent  string  `json:"agent"`
	Status string  `json:"status"`
	Output any     `json:"output"`
	Error  *string `json:"error"`
}

func OK(output any) Response { return Response{Agent: Agent, Status: "ok", Output: output} }

func Fail(msg string) Response {
	return Response{Agent: Agent, Status: "error", Output: map[string]any{}, Error: &msg}
}

var safeID = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

// Validate checks the envelope (not the skill input). A failure here is HTTP 422.
func (r *Request) Validate() error {
	if r.Skill == "" || len(r.Skill) > 64 {
		return errors.New("skill is required (max 64 characters)")
	}
	if r.Context == nil {
		return errors.New("context is required")
	}
	if err := Text("context.trace_id", r.Context.TraceID, 1, 128); err != nil {
		return err
	}
	return Text("context.user_id", r.Context.UserID, 1, 128)
}

// ID accepts only safe ids (no "../", no spaces): they end up in lookups and logs.
func ID(field, value string) error {
	if value == "" {
		return fmt.Errorf("%s is required", field)
	}
	if !safeID.MatchString(value) {
		return fmt.Errorf("%s must be 1-64 letters, digits, '-' or '_'", field)
	}
	return nil
}

// Text checks length and rejects ALL control characters, newlines included (no log injection).
func Text(field, value string, min, max int) error {
	return text(field, value, min, max, false)
}

// MultiLine is Text but allows line breaks (for summaries).
func MultiLine(field, value string, min, max int) error {
	return text(field, value, min, max, true)
}

func text(field, value string, min, max int, allowNewline bool) error {
	n := len([]rune(strings.TrimSpace(value)))
	if n < min || n > max {
		return fmt.Errorf("%s must be %d-%d characters", field, min, max)
	}
	for _, ch := range value {
		if ch < 0x20 && !(allowNewline && ch == '\n') {
			return fmt.Errorf("%s has control characters", field)
		}
	}
	return nil
}
