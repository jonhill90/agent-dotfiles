# Phase 0: Memory Backend Shortlist

- **Date:** 2026-07-11
- **Question (from PRD):** basic-memory is being dropped. What supplies
  memory *tooling* on every machine? (Content is never synced by the
  dotfiles; the backend's own sync story carries it.)
- **Scope note:** memory here = long-term agent memory (facts, decisions,
  preferences). Session state stays harness-native.

## Requirements derived from PRD

1. Works from **all four harnesses** — implies the access path must be a
   portable skill wrapping a CLI, not a harness-specific MCP binding
   (observed failure mode: basic-memory's MCP server disconnecting
   mid-session leaves the agent memory-less with no fallback).
2. Cross-machine by its own mechanism (dotfiles configure, don't sync data).
3. Token-economical: retrieval returns small, targeted notes.
4. No standing infrastructure — the vibes-v1 lesson: self-hosted databases
   were the first thing every later generation deleted.

## Candidates

### 1. Obsidian vault + obsidian-cli (recommended default)

- **Evidence:** obsidian-cli v0.2.3 already installed (`~/bin`), an
  `obsidian` skill already exists in the repo, vault sync (Obsidian
  Sync/iCloud) already solves cross-machine.
- **Fit:** plain markdown = model-agnostic, human-auditable, greppable;
  zero infra; agent access via the existing skill (portable to all four
  harnesses by definition — it's a CLI). Memory conventions (folder
  layout, index note, frontmatter) become a small skill + instruction in
  the dotfiles.
- **Risks:** retrieval is search-based, not semantic; no temporal
  reasoning; agent-written notes need naming/curation conventions to stay
  useful. CLI is v0.x — pin the version in the dotfiles.

### 2. Karpathy-style flat files (fallback / complement)

- Plain per-fact files + an index file loaded at session start — the exact
  pattern Claude Code's native memory uses today (`MEMORY.md` + files).
- **Fit:** simplest possible, no dependencies at all; the *convention* can
  live in instructions so every harness reads/writes the same directory.
- **Risks:** without a vault it has no cross-machine sync of its own —
  would need a private git repo or the vault anyway. Best understood as
  the same answer as #1 minus Obsidian's UI/sync, not a separate system.

### 3. Graphiti (Zep) — deferred, revisit on demonstrated need

- Temporal knowledge graph with an MCP server; strongest retrieval
  semantics (relationships, time-aware facts).
- **Risks:** requires a graph database (Neo4j/FalkorDB) = standing infra
  on every machine or a hosted service; MCP-only access path fails
  requirement 1; heaviest token/complexity cost. Directly repeats the
  vibes-v1 pattern the project history warns against.
- **Revisit trigger:** evals show search-based retrieval genuinely failing
  (agent can't find facts it stored), not just "graph would be nicer."
- **Verify before any adoption:** current infra requirements and MCP
  maturity (knowledge here may be stale; not re-verified this pass).

### 4. basic-memory (incumbent) — dropping, per intent decision

Jon's call, reinforced by observed live failure: its MCP server
disconnected mid-session (2026-07-11), removing all memory tools with no
CLI fallback.

## Recommendation

**Obsidian vault as the store, obsidian-cli as the access path, a small
memory-conventions skill + instruction block in the dotfiles as the
contract.** Karpathy-style index+files is the shape *inside* the vault.
Graphiti stays on the bench with an explicit revisit trigger.

Spec must define: vault location/name per machine, memory folder schema,
index note format, what session-start loads (index only — token budget),
and write conventions (one fact per note, frontmatter, linking).
