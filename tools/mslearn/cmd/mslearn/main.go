// Command mslearn is a CLI for querying Microsoft Learn via the MCP protocol.
package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"mslearn/internal/cache"
	"mslearn/internal/mcp"
	"mslearn/internal/output"
	"mslearn/internal/validate"
)

const defaultEndpoint = "https://learn.microsoft.com/api/mcp"

// Global flags
var (
	flagTrace    bool
	flagVerbose  bool
	flagNoCache  bool
	flagEndpoint string
	flagTTL      time.Duration
)

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	// Parse global flags before subcommand
	global := flag.NewFlagSet("mslearn", flag.ContinueOnError)
	global.BoolVar(&flagTrace, "trace", false, "Enable trace output to stderr")
	global.BoolVar(&flagVerbose, "verbose", false, "Enable verbose output")
	global.BoolVar(&flagNoCache, "no-cache", false, "Bypass disk cache")
	global.StringVar(&flagEndpoint, "endpoint", defaultEndpoint, "MCP endpoint URL")
	global.DurationVar(&flagTTL, "ttl", 15*time.Minute, "Cache TTL")
	global.Usage = usage

	if err := global.Parse(args); err != nil {
		return 2
	}

	remaining := global.Args()
	if len(remaining) == 0 {
		usage()
		return 2
	}

	cmd := remaining[0]
	cmdArgs := remaining[1:]

	switch cmd {
	case "search":
		return cmdSearch(cmdArgs)
	case "fetch":
		return cmdFetch(cmdArgs)
	case "samples":
		return cmdSamples(cmdArgs)
	case "batch":
		return cmdBatch(cmdArgs)
	case "session":
		return cmdSession(cmdArgs)
	case "cache":
		return cmdCache(cmdArgs)
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n", cmd)
		usage()
		return 2
	}
}

func usage() {
	fmt.Fprint(os.Stderr, `Usage: mslearn [global flags] <command> [flags]

Commands:
  search    Search Microsoft Learn documentation
  fetch     Fetch a specific documentation page
  samples   Search for code samples
  batch     Process queries from a JSONL file
  session   Manage MCP sessions (start|end|status)
  cache     Manage disk cache (stats|clear)

Global flags:
  --trace       Enable trace output to stderr
  --verbose     Enable verbose output
  --no-cache    Bypass disk cache
  --endpoint    MCP endpoint URL
  --ttl         Cache TTL (default 15m)
`)
}

func trace(format string, args ...any) {
	if flagTrace {
		fmt.Fprintf(os.Stderr, "[trace] "+format+"\n", args...)
	}
}

func getCache() *cache.Cache {
	if flagNoCache {
		return nil
	}
	dir, err := os.UserCacheDir()
	if err != nil {
		return nil
	}
	return cache.New(filepath.Join(dir, "mslearn", "cache"), flagTTL)
}

func callTool(client *mcp.Client, c *cache.Cache, tool string, args map[string]any) (*output.Record, error) {
	start := time.Now()

	// Check cache
	if c != nil {
		if cached := c.Get(tool, args); cached != nil {
			trace("cache hit for %s", tool)
			var parts []output.ContentPart
			json.Unmarshal(cached, &parts)
			return &output.Record{
				Tool:      tool,
				Arguments: args,
				Content:   parts,
				CacheHit:  true,
				LatencyMS: time.Since(start).Milliseconds(),
				Timestamp: start.UTC().Format(time.RFC3339),
			}, nil
		}
	}

	trace("calling %s", tool)
	result, err := client.CallTool(tool, args)
	if err != nil {
		return nil, err
	}

	// Convert content parts
	parts := make([]output.ContentPart, len(result.Content))
	for i, p := range result.Content {
		parts[i] = output.ContentPart{Type: p.Type, Text: p.Text}
	}

	// Store in cache
	if c != nil {
		if b, err := json.Marshal(parts); err == nil {
			c.Put(tool, args, b)
		}
	}

	return &output.Record{
		Tool:      tool,
		Arguments: args,
		Content:   parts,
		LatencyMS: time.Since(start).Milliseconds(),
		Timestamp: start.UTC().Format(time.RFC3339),
	}, nil
}

func initClient() (*mcp.Client, error) {
	client := mcp.NewClient(flagEndpoint)
	if flagTrace {
		client.Trace = func(format string, args ...any) {
			trace(format, args...)
		}
	}

	// Try to restore persisted session
	sid, endpoint, _ := mcp.LoadSession()
	if sid != "" && endpoint == flagEndpoint {
		client.SetSessionID(sid)
		trace("restored session %s", sid)
		return client, nil
	}

	trace("initializing new session")
	if err := client.Initialize(); err != nil {
		return nil, err
	}
	return client, nil
}

func printRecord(rec *output.Record, format string) error {
	out, err := output.Format(rec, format)
	if err != nil {
		return err
	}
	fmt.Println(out)
	return nil
}

// --- Subcommands ---

func cmdSearch(args []string) int {
	fs := flag.NewFlagSet("search", flag.ContinueOnError)
	query := fs.String("query", "", "Search query (required)")
	maxResults := fs.Int("max-results", 0, "Maximum results")
	format := fs.String("format", "compact", "Output format: compact|json|jsonl|md")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *query == "" {
		fmt.Fprintln(os.Stderr, "error: --query is required")
		return 2
	}

	client, err := initClient()
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	defer client.Terminate()

	toolArgs := map[string]any{"query": *query}
	if *maxResults > 0 {
		toolArgs["maxResults"] = *maxResults
	}

	rec, err := callTool(client, getCache(), "microsoft_docs_search", toolArgs)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	if err := printRecord(rec, *format); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	return 0
}

func cmdFetch(args []string) int {
	fs := flag.NewFlagSet("fetch", flag.ContinueOnError)
	url := fs.String("url", "", "URL to fetch (required)")
	format := fs.String("format", "compact", "Output format: compact|json|jsonl|md")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *url == "" {
		fmt.Fprintln(os.Stderr, "error: --url is required")
		return 2
	}

	// Validate URL before making any network calls
	if errMsg := validate.URL(*url); errMsg != "" {
		fmt.Fprintf(os.Stderr, "error: URL validation failed: %s\n", errMsg)
		return 2
	}

	client, err := initClient()
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	defer client.Terminate()

	rec, err := callTool(client, getCache(), "microsoft_docs_fetch", map[string]any{"url": *url})
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	if err := printRecord(rec, *format); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	return 0
}

func cmdSamples(args []string) int {
	fs := flag.NewFlagSet("samples", flag.ContinueOnError)
	query := fs.String("query", "", "Search query (required)")
	language := fs.String("language", "", "Filter by language")
	maxResults := fs.Int("max-results", 0, "Maximum results")
	format := fs.String("format", "compact", "Output format: compact|json|jsonl|md")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *query == "" {
		fmt.Fprintln(os.Stderr, "error: --query is required")
		return 2
	}

	client, err := initClient()
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	defer client.Terminate()

	toolArgs := map[string]any{"query": *query}
	if *language != "" {
		toolArgs["language"] = *language
	}
	if *maxResults > 0 {
		toolArgs["maxResults"] = *maxResults
	}

	rec, err := callTool(client, getCache(), "microsoft_code_sample_search", toolArgs)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	if err := printRecord(rec, *format); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	return 0
}

// batchQuery is a single entry in a JSONL batch file.
type batchQuery struct {
	Tool      string         `json:"tool"`
	Arguments map[string]any `json:"arguments"`
}

func cmdBatch(args []string) int {
	fs := flag.NewFlagSet("batch", flag.ContinueOnError)
	file := fs.String("file", "", "JSONL file with queries (required)")
	format := fs.String("format", "jsonl", "Output format: compact|json|jsonl|md")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *file == "" {
		fmt.Fprintln(os.Stderr, "error: --file is required")
		return 2
	}

	f, err := os.Open(*file)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	defer f.Close()

	var queries []batchQuery
	scanner := bufio.NewScanner(f)
	lineNum := 0
	for scanner.Scan() {
		lineNum++
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "//") {
			continue
		}
		var q batchQuery
		if err := json.Unmarshal([]byte(line), &q); err != nil {
			fmt.Fprintf(os.Stderr, "error: line %d: %v\n", lineNum, err)
			return 1
		}
		queries = append(queries, q)
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "error reading file: %v\n", err)
		return 1
	}

	if len(queries) == 0 {
		fmt.Fprintln(os.Stderr, "error: no queries found in file")
		return 2
	}

	// Single session for all queries
	client, err := initClient()
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	defer client.Terminate()

	c := getCache()
	exitCode := 0
	for i, q := range queries {
		trace("batch query %d/%d: %s", i+1, len(queries), q.Tool)

		// Validate fetch URLs
		if q.Tool == "microsoft_docs_fetch" {
			if urlStr, ok := q.Arguments["url"].(string); ok {
				if errMsg := validate.URL(urlStr); errMsg != "" {
					fmt.Fprintf(os.Stderr, "error: query %d: URL validation failed: %s\n", i+1, errMsg)
					exitCode = 1
					continue
				}
			}
		}

		rec, err := callTool(client, c, q.Tool, q.Arguments)
		if err != nil {
			fmt.Fprintf(os.Stderr, "error: query %d: %v\n", i+1, err)
			exitCode = 1
			continue
		}
		if err := printRecord(rec, *format); err != nil {
			fmt.Fprintf(os.Stderr, "error: query %d: %v\n", i+1, err)
			exitCode = 1
		}
	}
	return exitCode
}

func cmdSession(args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "usage: mslearn session start|end|status")
		return 2
	}

	switch args[0] {
	case "start":
		client := mcp.NewClient(flagEndpoint)
		if flagTrace {
			client.Trace = func(format string, a ...any) { trace(format, a...) }
		}
		if err := client.Initialize(); err != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", err)
			return 1
		}
		if err := mcp.SaveSession(client.SessionID(), flagEndpoint); err != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", err)
			return 1
		}
		fmt.Printf("session started: %s\n", client.SessionID())
		return 0

	case "end":
		sid, endpoint, err := mcp.LoadSession()
		if err != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", err)
			return 1
		}
		if sid == "" {
			fmt.Fprintln(os.Stderr, "no active session")
			return 0
		}
		client := mcp.NewClient(endpoint)
		client.SetSessionID(sid)
		client.Terminate()
		if err := mcp.ClearSession(); err != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", err)
			return 1
		}
		fmt.Println("session ended")
		return 0

	case "status":
		status, err := mcp.SessionStatus()
		if err != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", err)
			return 1
		}
		fmt.Println(status)
		return 0

	default:
		fmt.Fprintf(os.Stderr, "unknown session command: %s\n", args[0])
		return 2
	}
}

func cmdCache(args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "usage: mslearn cache stats|clear")
		return 2
	}

	c := getCache()
	if c == nil {
		fmt.Fprintln(os.Stderr, "cache is disabled (--no-cache)")
		return 1
	}

	switch args[0] {
	case "stats":
		entries, size := c.Stats()
		fmt.Printf("entries: %d\nsize: %d bytes\n", entries, size)
		return 0

	case "clear":
		if err := c.Clear(); err != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", err)
			return 1
		}
		fmt.Println("cache cleared")
		return 0

	default:
		fmt.Fprintf(os.Stderr, "unknown cache command: %s\n", args[0])
		return 2
	}
}
