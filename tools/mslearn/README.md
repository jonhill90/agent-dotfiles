# mslearn

A CLI for querying Microsoft Learn documentation via the MCP (Model Context Protocol) endpoint.

Single compiled Go binary. Zero runtime dependencies. Stdlib only.

## Install

```bash
cd tools/mslearn
make build
```

Produces a `mslearn` binary in the current directory.

## Commands

### search

Search Microsoft Learn documentation.

```bash
mslearn search --query "Azure Functions"
mslearn search --query "Cosmos DB" --max-results 5 --format json
```

### fetch

Fetch a specific documentation page by URL (must be `*.microsoft.com`).

```bash
mslearn fetch --url "https://learn.microsoft.com/en-us/azure/azure-functions/functions-overview"
mslearn fetch --url "https://learn.microsoft.com/en-us/dotnet/core/introduction" --format md
```

### samples

Search for code samples.

```bash
mslearn samples --query "Azure Functions HTTP trigger"
mslearn samples --query "Cosmos DB" --language python --format json
```

### batch

Process multiple queries from a JSONL file.

```bash
mslearn batch --file queries.jsonl
mslearn batch --file queries.jsonl --format json
```

Each line in the JSONL file is `{"tool":"<tool_name>","arguments":{...}}`.

### session

Manage MCP sessions for connection reuse across commands.

```bash
mslearn session start    # Initialize and persist session
mslearn search --query "test"   # Reuses persisted session
mslearn session status   # Show session info
mslearn session end      # Terminate and clear session
```

### cache

Manage the disk cache.

```bash
mslearn cache stats   # Show entry count and size
mslearn cache clear   # Remove all cached entries
```

## Global Flags

Place these **before** the subcommand:

| Flag | Default | Description |
|------|---------|-------------|
| `--trace` | false | Trace output to stderr |
| `--verbose` | false | Verbose output |
| `--no-cache` | false | Bypass disk cache |
| `--endpoint` | `https://learn.microsoft.com/api/mcp` | MCP endpoint URL |
| `--ttl` | 15m | Cache TTL |

## Per-Command Flags

| Flag | Commands | Description |
|------|----------|-------------|
| `--format` | all | Output format: `compact` (default), `json`, `jsonl`, `md` |
| `--query` | search, samples | Search query |
| `--url` | fetch | Documentation URL |
| `--language` | samples | Filter by language |
| `--max-results` | search, samples | Maximum results |
| `--file` | batch | JSONL input file |

## Output Formats

- **compact** — Plain text content (default). Good for piping.
- **json** — Pretty-printed JSON with metadata (tool, args, latency, cache hit).
- **jsonl** — Single-line JSON per result. Good for batch processing.
- **md** — Markdown with heading per tool.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Operational error (network, protocol, cache) |
| 2 | Usage error (missing flag, unknown command) |

## Cache

Results are cached to `$HOME/Library/Caches/mslearn/cache/` (macOS) or `$XDG_CACHE_HOME/mslearn/cache/` (Linux). Cache keys are SHA256 hashes of tool name + arguments. Directory layout uses git object store convention (`{key[:2]}/{key}.json`).

Default TTL is 15 minutes. Override with `--ttl`.

## Migration from Python

This binary replaces `tools/mslearn_cli.py` and `.github/skills/ms-learn-py/scripts/_mcp_client.py`. The command interface maps as follows:

| Python | Go |
|--------|-----|
| `mslearn_cli.py mcp search --query "..."` | `mslearn search --query "..."` |
| `mslearn_cli.py mcp fetch --url "..."` | `mslearn fetch --url "..."` |
| `mslearn_cli.py mcp code --query "..."` | `mslearn samples --query "..."` |

The Go version adds: disk caching, batch mode, session management, multiple output formats, retry with backoff, and trace logging.

## Development

```bash
make test    # Run all tests with race detector
make lint    # Run go vet
make bench   # Run benchmarks
make clean   # Remove binary
```
