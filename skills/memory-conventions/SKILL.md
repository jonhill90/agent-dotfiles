---
name: memory-conventions
description: Read and write durable agent memory in the personal Obsidian vault at $AGENT_MEMORY_VAULT. Use at session start to recall context, when the user states a lasting preference, decision, or fact, or when asked to remember, recall, or forget something.
---

# Memory Conventions

Durable, cross-harness agent memory lives in the vault at
`$AGENT_MEMORY_VAULT`. Access is **direct file operations** — no CLI or
app required, works headless on every harness.

## Layout

```text
$AGENT_MEMORY_VAULT/
  agent/
    index.md        # the only file loaded at session start
    facts/<slug>.md # one fact per note
```

## Session start

Read `agent/index.md` only (hard cap 200 lines / 25KB). Load individual
facts on demand when their hook matches the task.

## Writing a fact

When the user states something durable (preference, decision,
constraint, reference):

1. Create `agent/facts/<kebab-slug>.md`:

```markdown
---
type: user|feedback|project|reference
created: YYYY-MM-DD
source: <where this came from>
---

<the fact, one per note; absolute dates; [[wiki-links]] to related facts>
```

2. Add one index line: a markdown list item linking the fact — link
   text is the title, target is `facts/<slug>.md`, followed by
   ` — <one-line hook>`.

## Maintaining

- Update or delete stale facts; never duplicate them.
- Check the index for an existing fact before creating a new one.
- Session-scoped notes stay in the harness's native memory, not here.

## Guardrails

- The vault must be **personal** storage — never an employer-synced
  location (`sync doctor` enforces this).
- If `$AGENT_MEMORY_VAULT` is unset or missing, say so and skip memory
  operations; do not invent a location.
