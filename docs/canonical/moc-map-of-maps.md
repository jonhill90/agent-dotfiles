---
type: Document
knowledge_status: canonical
updated: 2026-09-06T23:27:40+00:00
---

# Map of maps — where the estate's stores live

A pointer list, nothing more. For each store: what it holds, in one line,
and where to look next. It does not unify or mirror any store's own
internal shape — a store's entry point stays whatever that store already
uses (an index, a SQL view, or "search directly" if no map exists yet).

**This is not an OKF mechanism.** [OKF](https://okf.dev/) has no
multi-bundle or federation spec — nothing in the format defines how one
bundle points at another. This file is an estate-owned convention invented
to fill that gap, not something OKF provides or endorses. Do not add OKF
frontmatter here; this file is deliberately outside that format.

Six stores, three navigable today:

| Store | Holds | Entry point |
|---|---|---|
| vault | Durable facts about Jon — preferences, decisions, project state | bundle-root `index.md` in the Obsidian vault at `$AGENT_MEMORY_VAULT` (`agent/` retired in full, agent-estate#1275) |
| corpus | Jon's own prompts (3,700+) and live hard constraints (900+), judged and queryable | `~/corpus/ledger.sqlite3` — 5 SQL views: `unacknowledged`, `live_parameters`, `conflicts`, `open_questions`, `possibility_count`; see `docs/corpus/index.md` for the full map. Not `~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3` — a different, far-behind database (2,180 prompts / 51 live parameters vs. this one's 10,371 / 1,308, measured 2026-09-07); agent-estate#942 |
| agent-tui | TUI product docs — PRD, spec — now inside `agent-estate` (`jonhill90/agent-tui` retired 2026-08-30; its README: "This repository is decommissioned") | [`docs/orientation/tui-arrival.md`](https://github.com/jonhill90/agent-estate/blob/main/docs/orientation/tui-arrival.md), routing to `docs/tui/PRD.md`, `docs/tui/SPEC.md`, and code at `src/tui/` |
| agent-supervisor | This repo's own docs and code layout | not yet mapped — an internal-map replication pilot is separately in flight (estate:2); until it lands, search `CLAUDE.md` and `scripts/supervisor/` directly |
| skills | Public skills collection | not yet mapped — search the repo directly; note `docs/` was deliberately removed here on 2026-08-09 (agent-dotfiles/docs/docs-layout-council-138.md, Q3) as harness machinery that didn't belong in a content-only repo, so a future map for this store should not default to a `docs/` layout |
| agent-dotfiles | The estate's own harness/docs home — PRD, spec, loop and memory engineering, this file | no `index.md` yet; `docs/` is flat (agent-dotfiles/docs/docs-layout-council-138.md) — search `docs/*.md` directly |

RAG does not exist yet as a store and is out of scope here entirely.

## What this deliberately does not do

- Does not add a common schema, frontmatter, or content shape across
  stores — each store's own map (or absence of one) is authoritative for
  itself.
- Does not touch or reference the per-agent memory storage-format decision
  (agent-tui#116) — unrelated question, not settled by this file.
- Does not wait on agent-supervisor's in-flight internal-map replication
  (estate:2) — that row above will be updated when that work lands, not
  before.
