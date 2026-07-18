# Memory

Agent memory is a personal, cross-harness Obsidian vault accessed through
ordinary file operations. The dotfiles install conventions and validate the
path; they never sync memory content. Detailed design history remains in
commits `106e69c`, `a4de1ac`, `e33f08b`, and `b752300`.

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
  reasons to make the rest of the vault unreadable.

The format follows the progressive-disclosure operating model of Karpathy's
LLM wiki and the permissive bundle conventions of Google OKF v0.1. Personal
note-taxonomy systems are intentionally excluded: agent memory and Jon's
knowledge vault are separate systems.

## Behavior

At session start, read `agent/index.md` only. Before answering from durable
history, actually read the index in that session. A durable user preference,
decision, or fact is not saved until its fact file exists and the index is
updated. Session-only state stays in the harness's native memory.

The `memory-conventions` skill is the normative operating procedure. E12
demonstrates write-back and cross-harness recall in
`tests/evals/results/2026-07-12-e12-memory-writeback.md`.

## Tooling choices

Direct file operations are the required path because they work on every
harness and on headless systems. The official Obsidian CLI is an optional
app-present enhancement used by the `obsidian` skill; it is not required for
memory. Graph databases remain deferred until eval evidence shows that indexed
file search cannot retrieve stored facts. Basic Memory is retired because its
MCP-only failure mode removed access with no fallback.
