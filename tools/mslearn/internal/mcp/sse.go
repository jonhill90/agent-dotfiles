package mcp

import (
	"bufio"
	"encoding/json"
	"io"
	"strings"
)

// maxSSEBuffer is the maximum line length for SSE scanning (1MB).
const maxSSEBuffer = 1 << 20

// ParseSSE reads an SSE stream per WHATWG spec and yields parsed JSON-RPC payloads.
// - "data: " lines accumulate into a buffer
// - ":" lines (comments/keepalives) are ignored
// - Blank lines dispatch the accumulated buffer
// - EOF flushes any remaining buffer
func ParseSSE(r io.Reader) []json.RawMessage {
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 0, maxSSEBuffer), maxSSEBuffer)

	var results []json.RawMessage
	var dataBuf []string

	for scanner.Scan() {
		line := scanner.Text()
		switch {
		case strings.HasPrefix(line, "data: "):
			dataBuf = append(dataBuf, line[6:])
		case strings.HasPrefix(line, ":"):
			// comment / keepalive — ignore
		case line == "":
			if len(dataBuf) > 0 {
				payload := strings.Join(dataBuf, "\n")
				dataBuf = dataBuf[:0]
				if json.Valid([]byte(payload)) {
					results = append(results, json.RawMessage(payload))
				}
			}
		// other fields (event:, id:, retry:) ignored per spec
		}
	}

	// Flush remaining data on EOF
	if len(dataBuf) > 0 {
		payload := strings.Join(dataBuf, "\n")
		if json.Valid([]byte(payload)) {
			results = append(results, json.RawMessage(payload))
		}
	}

	return results
}
