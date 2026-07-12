package output

import (
	"encoding/json"
	"strings"
	"testing"
)

func testRecord() *Record {
	return &Record{
		Tool:      "microsoft_docs_search",
		Arguments: map[string]any{"query": "azure functions"},
		Content: []ContentPart{
			{Type: "text", Text: "Azure Functions overview"},
			{Type: "text", Text: "Serverless compute service"},
		},
		CacheHit:  true,
		LatencyMS: 42,
		Timestamp: "2025-01-01T00:00:00Z",
	}
}

func TestFormatCompact(t *testing.T) {
	got, err := Format(testRecord(), "compact")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(got, "Azure Functions overview") {
		t.Errorf("compact output missing content: %s", got)
	}
	if !strings.Contains(got, "Serverless compute service") {
		t.Errorf("compact output missing second part: %s", got)
	}
	// Should be just text, no JSON
	if strings.Contains(got, "{") {
		t.Errorf("compact output should not contain JSON: %s", got)
	}
}

func TestFormatJSON(t *testing.T) {
	got, err := Format(testRecord(), "json")
	if err != nil {
		t.Fatal(err)
	}
	var r Record
	if err := json.Unmarshal([]byte(got), &r); err != nil {
		t.Fatalf("invalid JSON: %v\n%s", err, got)
	}
	if r.Tool != "microsoft_docs_search" {
		t.Errorf("tool = %q", r.Tool)
	}
	if !r.CacheHit {
		t.Error("cache_hit should be true")
	}
}

func TestFormatJSONL(t *testing.T) {
	got, err := Format(testRecord(), "jsonl")
	if err != nil {
		t.Fatal(err)
	}
	// Should be a single line
	if strings.Count(got, "\n") > 0 {
		t.Errorf("jsonl should be single line: %s", got)
	}
	var r Record
	if err := json.Unmarshal([]byte(got), &r); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
}

func TestFormatMarkdown(t *testing.T) {
	got, err := Format(testRecord(), "md")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(got, "## microsoft_docs_search") {
		t.Errorf("markdown should start with heading: %s", got)
	}
	if !strings.Contains(got, "Azure Functions overview") {
		t.Errorf("markdown missing content: %s", got)
	}
}

func TestFormatUnknown(t *testing.T) {
	_, err := Format(testRecord(), "xml")
	if err == nil {
		t.Fatal("expected error for unknown format")
	}
}
