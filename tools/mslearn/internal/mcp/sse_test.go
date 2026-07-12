package mcp

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestParseSSE_BasicPayload(t *testing.T) {
	input := "data: {\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{}}\n\n"
	results := ParseSSE(strings.NewReader(input))
	if len(results) != 1 {
		t.Fatalf("got %d results, want 1", len(results))
	}
	var msg struct {
		ID int `json:"id"`
	}
	if err := json.Unmarshal(results[0], &msg); err != nil {
		t.Fatal(err)
	}
	if msg.ID != 1 {
		t.Errorf("id = %d, want 1", msg.ID)
	}
}

func TestParseSSE_MultipleEvents(t *testing.T) {
	input := "data: {\"id\":1}\n\ndata: {\"id\":2}\n\n"
	results := ParseSSE(strings.NewReader(input))
	if len(results) != 2 {
		t.Fatalf("got %d results, want 2", len(results))
	}
}

func TestParseSSE_CommentsIgnored(t *testing.T) {
	input := ": keepalive\ndata: {\"id\":1}\n\n"
	results := ParseSSE(strings.NewReader(input))
	if len(results) != 1 {
		t.Fatalf("got %d results, want 1", len(results))
	}
}

func TestParseSSE_MultiLineData(t *testing.T) {
	// Multi-line data fields get joined with newline
	input := "data: {\"text\":\n" +
		"data: \"hello\"}\n\n"
	results := ParseSSE(strings.NewReader(input))
	if len(results) != 1 {
		t.Fatalf("got %d results, want 1", len(results))
	}
	var msg map[string]string
	if err := json.Unmarshal(results[0], &msg); err != nil {
		t.Fatal(err)
	}
	if msg["text"] != "hello" {
		t.Errorf("text = %q, want %q", msg["text"], "hello")
	}
}

func TestParseSSE_EOFFlush(t *testing.T) {
	// No trailing blank line — should still flush
	input := "data: {\"id\":1}"
	results := ParseSSE(strings.NewReader(input))
	if len(results) != 1 {
		t.Fatalf("got %d results, want 1", len(results))
	}
}

func TestParseSSE_InvalidJSON(t *testing.T) {
	input := "data: not-json\n\n"
	results := ParseSSE(strings.NewReader(input))
	if len(results) != 0 {
		t.Fatalf("got %d results, want 0 (invalid JSON should be skipped)", len(results))
	}
}

func TestParseSSE_MixedValidInvalid(t *testing.T) {
	input := "data: {\"id\":1}\n\ndata: broken\n\ndata: {\"id\":3}\n\n"
	results := ParseSSE(strings.NewReader(input))
	if len(results) != 2 {
		t.Fatalf("got %d results, want 2", len(results))
	}
}

func TestParseSSE_EventAndRetryIgnored(t *testing.T) {
	input := "event: message\nretry: 3000\ndata: {\"id\":1}\n\n"
	results := ParseSSE(strings.NewReader(input))
	if len(results) != 1 {
		t.Fatalf("got %d results, want 1", len(results))
	}
}

func BenchmarkParseSSE(b *testing.B) {
	// Build a realistic SSE stream with 100 events
	var sb strings.Builder
	for i := range 100 {
		sb.WriteString("data: {\"jsonrpc\":\"2.0\",\"id\":")
		sb.WriteString(strings.Repeat("0", 0)) // placeholder
		_ = i
		sb.WriteString("1,\"result\":{\"content\":[{\"type\":\"text\",\"text\":\"some result text here\"}]}}\n\n")
	}
	input := sb.String()
	b.ResetTimer()
	for range b.N {
		ParseSSE(strings.NewReader(input))
	}
}
