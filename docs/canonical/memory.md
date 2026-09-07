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
resolve under employer-managed storage. The shared bundle is:

```text
$AGENT_MEMORY_VAULT/
  agent/
    index.md
    log.md
    facts/<semantic-kebab-slug>.md
```

- `index.md` is the only memory file read at session start. It contains one
  link and description per fact and is capped at 200 lines / 25 KB.
- `log.md` is append-only history grouped under `## YYYY-MM-DD`, newest first.
- Each fact owns one concept and is updated in place rather than duplicated.
- Frontmatter requires `type: user|feedback|project|reference`; title,
  description, UTC `created`/`updated`, source, and tags are recommended.
- Consumption is permissive. Malformed or stale facts are lint findings, not
  reasons to make the rest of the vault unreadable — `scripts/memory_lint.py`
  is that linter: read-only, no model call, detect-and-report only (#280).

The format follows the progressive-disclosure operating model of Karpathy's
LLM wiki and the permissive bundle conventions of Google OKF. The vault's
`agent/index.md` declares `okf_version: "0.1"` today; `docs/okf-adoption-280.md`
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

At session start, read `Start Here.md`, then the capped `agent/index.md`. Before answering from durable
history, actually read the index in that session. A durable user preference,
decision, or fact is not saved until its fact file exists and the index is
updated. Session-only state stays in the harness's native memory.

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
