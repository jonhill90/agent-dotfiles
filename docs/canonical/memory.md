---
type: Document
knowledge_status: canonical
updated: 2026-09-06T23:27:40+00:00
---

# Memory

Agent memory is a personal, cross-harness Obsidian vault accessed through
read-only file operations; ordinary writes use the reviewed estate candidates tool. The dotfiles install conventions and validate the
path; they never sync memory content. **Corrected 2026-08-23:** this
previously cited detailed design history as living in commits `106e69c`,
`a4de1ac`, `e33f08b`, and `b752300` — none of these four SHAs resolves in
this repository's current history (checked against a full fetch from
`origin`, all refs). The underlying research is not recoverable from this
repo as cited.

## Contract

`AGENT_MEMORY_VAULT` points to a personal vault on each machine. It must not
resolve under employer-managed storage. `agent/` — the pre-INMAPS bundle
shape this section used to describe — no longer exists (retired in full,
agent-estate#1275); the current shared bundle is:

```text
$AGENT_MEMORY_VAULT/
  index.md       # bundle-root okf_version carrier, capped, read at session start
  Start Here.md  # human entry point / routing
  00 - Inbox/    # drafts awaiting review
  01 - Notes/    # accepted atomic notes, permanent 12-digit IDs, under
                 # earned letter subdirs (registry: 99 - Meta/note-subdirs.md)
  02 - MOCs/     # generated hubs
  05 - Sources/  # source records
  99 - Meta/     # tag vocabulary, the append-only log, tooling
```

- The bundle-root `index.md` is the only memory file read at session start —
  and, per OKF section 12, the sole legal `okf_version` carrier; it is not a
  browsing index. It contains one link and description per note and is
  capped (see the vault's own `99 - Meta/index-contract.md` for the current
  limit).
- `99 - Meta/log.md` is append-only history grouped under `## YYYY-MM-DD`,
  newest first.
- Each note owns one concept and is superseded (deprecated with a
  replacement pointer) rather than duplicated in place.
- Frontmatter requires `type: user|feedback|project|reference`; title,
  description, UTC `created`/`updated`, source, and tags are recommended.
- Consumption is permissive. Malformed or stale notes are lint findings, not
  reasons to make the rest of the vault unreadable — `scripts/memory_lint.py`
  is that linter: read-only, no model call, detect-and-report only (#280).

The format follows the progressive-disclosure operating model of Karpathy's
LLM wiki and the permissive bundle conventions of Google OKF. The vault's
bundle-root `index.md` declares `okf_version: "0.1"` today; `docs/okf-adoption-280.md`
carries the OKF v0.2 gap report, the additive migration design (no vault
writes in that pass), and `scripts/memory_lint.py`, the read-only linter
built for it (#280). `docs/memory-per-agent-map-contract.md` generalizes
`index.md`'s own map-before-search shape into a backend-agnostic
requirement for per-agent knowledge (#281's four-store boundary) — it
picks no backend and touches nothing here. Personal note-taxonomy systems are intentionally
excluded: agent memory and Jon's knowledge vault are separate systems.

## INMAPS — current write contract

The 2026-09-06 approved layout supersedes the earlier slug/write-in-place
conventions: drafts enter `00 - Inbox`; accepted atomic notes use permanent
12-digit IDs in `01 - Notes`; supersession keeps old notes deprecated with
replacement pointers. New links use Markdown paths. Aliases are discovery
metadata, not proof that existing bare wikilinks resolve.

Writes validate the governed `99 - Meta/tags.md` vocabulary and required
frontmatter: type, title, description, tags, id, created/updated with UTC offset,
status and known provenance. Never invent human review. INMAPS writer support
is pending in the estate push-2 PR; do not use legacy slug publication as a
fallback. The migration was an explicit backed-up mechanical exception.

See the [canonical workflow](https://github.com/jonhill90/agent-estate/blob/main/docs/knowledge-workflow.md)
for commands. This repository installs conventions; it never syncs vault content.

## Behavior

At session start, read `Start Here.md` for routing, then the capped
bundle-root `index.md`. Before answering from durable history, actually
read the index in that session. A durable user preference, decision, or
fact is not saved until its note exists in `01 - Notes` and, if it earns
index space, the index is updated. Session-only state stays in the
harness's native memory.

The `memory-conventions` skill is the normative operating procedure. E12
demonstrates write-back and cross-harness recall in
`tests/evals/results/2026-07-12-e12-memory-writeback.md` in the private
jonhill90/agent-evals (evidence unavailable publicly) repository.

## Tooling choices

Direct file operations are the required path because they work on every
harness and on headless systems. The official Obsidian CLI is an optional
app-present enhancement used by the `obsidian` skill; it is not required for
memory. Graph databases remain deferred until eval evidence shows that indexed
file search cannot retrieve stored facts. Basic Memory is retired because its
MCP-only failure mode removed access with no fallback.
