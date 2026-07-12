// Package output provides formatting for MCP tool results.
package output

import (
	"encoding/json"
	"fmt"
	"strings"
)

// ContentPart is a single content element from an MCP tool result.
type ContentPart struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

// Record is a formatted output record for a single tool invocation.
type Record struct {
	Tool      string         `json:"tool"`
	Arguments map[string]any `json:"arguments"`
	Content   []ContentPart  `json:"content"`
	CacheHit  bool           `json:"cache_hit,omitempty"`
	LatencyMS int64          `json:"latency_ms,omitempty"`
	Timestamp string         `json:"timestamp"`
}

// Format formats a record using the given format name.
// Supported: "compact", "json", "jsonl", "md".
func Format(r *Record, format string) (string, error) {
	switch format {
	case "compact":
		return formatCompact(r), nil
	case "json":
		return formatJSON(r)
	case "jsonl":
		return formatJSONL(r)
	case "md":
		return formatMarkdown(r), nil
	default:
		return "", fmt.Errorf("unknown format: %q", format)
	}
}

func formatCompact(r *Record) string {
	var sb strings.Builder
	for i, c := range r.Content {
		if i > 0 {
			sb.WriteByte('\n')
		}
		sb.WriteString(c.Text)
	}
	return sb.String()
}

func formatJSON(r *Record) (string, error) {
	b, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return "", err
	}
	return string(b), nil
}

func formatJSONL(r *Record) (string, error) {
	b, err := json.Marshal(r)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

func formatMarkdown(r *Record) string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("## %s\n\n", r.Tool))
	for _, c := range r.Content {
		sb.WriteString(c.Text)
		sb.WriteByte('\n')
	}
	return sb.String()
}
