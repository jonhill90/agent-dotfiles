# Memory Format Distillation: INMPARA × Second Brain × Karpathy × OKF

- **Date:** 2026-07-12
- **Question:** is the M4 memory schema right? Reconcile it with Jon's
  own knowledge lineage and the two strongest external references.
- **Sources reviewed:**
  - INMPARA (`~/source/repos/personal/inmpara`) — Jon's 2025 system:
    Inbox→Notes→MOCs→Projects→Areas→Resources→Archive; bottom-up
    emergence; AI-first frontmatter (title/type/tags/created/updated/
    status/stage/domain/permalink)
  - Second Brain vault (live, INMPARA's evolution) — synaptic tagging
    ("tag associatively, not categorically"), golden rule "search
    first", `YYYYMMDDHHmm` zettel IDs as filenames for atomic notes,
    typed templates, MOC hubs, strict folder rules
  - [Karpathy llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
    — three layers (immutable raw sources / LLM-owned wiki / schema
    doc); `index.md` read first; append-only `log.md`; operations
    ingest / query / lint; "maintenance cost is near zero" for LLMs
  - [Google OKF v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog)
    (`~/source/repos/personal/google-knowledge-catalog/okf/SPEC.md`) —
    markdown + YAML frontmatter bundles; ONE required field (`type`);
    recommended `title`/`description`/`resource`/`tags`/`timestamp`
    (ISO 8601); reserved `index.md` (progressive-disclosure listing) and
    `log.md` (`## YYYY-MM-DD` headings, newest first); permissive
    consumption; broken links = not-yet-written knowledge

## Finding 1: the four sources agree on the fundamentals

All four independently converge on: plain markdown + YAML frontmatter,
an index read first (progressive disclosure), semantic links as the
graph, structure emerging bottom-up, and tolerance for imperfection
(OKF's "broken links are not malformed" = INMPARA's forward
references). The M4 schema is directionally right; it needs alignment,
not redesign.

## Finding 2: two distinct systems, one format family

- **Second Brain** = Jon's *knowledge* system (human+agent curated,
  synaptic/INMPARA conventions, its own in-vault guide). Agents
  working in it follow *its* rules.
- **Agent Memory vault** = the agent's *memory* (facts about Jon,
  projects, preferences). Smaller, agent-owned, machine-write-heavy.

They stay separate (PRD: memory content ≠ knowledge content), but both
speak the same format family, and the memory vault should be
**OKF-conformant** so any consumption agent can traverse it without
bespoke rules. In Karpathy's terms: session transcripts are the raw
sources (harness-owned, immutable), the memory vault is the wiki (agent-
owned), and the memory-conventions skill is the schema document.

## Finding 3: fact filenames — semantic slugs, not timestamp IDs

Jon's question: `YYYYMMDDHHMM` vs `YYYYMMDDHHMMSS` for agent notes.
Answer: **neither, for memory facts.** Timestamp-ID filenames solve a
*human* problem (frictionless unique capture; the Second Brain keeps
them for atomic notes, correctly). Memory facts have a different
identity: the *concept* ("python-package-manager"), which must be
findable by name, updated in place, and never duplicated — the
one-owner rule. A timestamp filename would force duplicate facts
instead of updates and make index hooks meaningless.

Where timestamps DO matter for agents, they move into metadata with
**full seconds, ISO 8601, UTC** (`2026-07-12T18:42:07Z`): agents write
multiple times a minute, and minute-precision (`YYYYMMDDHHmm`) can
collide within one session. If a timestamp-ID file is ever needed
(e.g., Second Brain atomic notes written *by* an agent), use seconds
precision there too.

## Finding 4: adopt from each source

| Adopt | From | Into the memory schema |
|---|---|---|
| `type` as the only required field; permissive consumption | OKF | keep `type:`; never reject malformed facts, lint them |
| `title` + `description` recommended fields | OKF | add — `description` powers index generation and search snippets |
| `timestamp`/`created`/`updated` as ISO 8601 datetimes | OKF | replace date-only `created:` (answers the timestamp question) |
| `index.md` = link + one-line description per entry | OKF + Karpathy + current M4 | already aligned; keep 200-line/25KB cap |
| **`log.md`, append-only, `## YYYY-MM-DD` headings, newest first** | OKF + Karpathy | **new** — cheapest possible temporal reasoning; directly shrinks the gap that kept Graphiti on the bench (memory-backends risk: "no temporal reasoning") |
| Operations vocabulary: ingest / query / **lint** | Karpathy | lint = periodic health check (contradictions, stale facts, orphans, index drift); future `sync doctor` or skill duty at M5+ |
| Search-first golden rule; emergence; associative tags | INMPARA / Second Brain | already in conventions ("check index before creating"); tags stay optional per OKF |
| Wiki-links between facts | Second Brain / OKF §5 | keep; broken links = not-yet-written facts |

## Resulting schema (v2 — SPEC §3.6 is normative)

```text
$AGENT_MEMORY_VAULT/
  agent/                 # the OKF bundle root for agent memory
    index.md             # only file loaded at session start (≤200 lines/25KB)
    log.md               # append-only history: ## YYYY-MM-DD, newest first
    facts/<kebab-slug>.md
```

Fact frontmatter:

```yaml
---
type: user | feedback | project | reference   # required (OKF)
title: <display name>                          # recommended
description: <one line — becomes the index hook>
created: 2026-07-12T18:42:07Z                  # ISO 8601, seconds, UTC
updated: 2026-07-12T18:42:07Z
source: <where this came from>
tags: []                                       # optional, associative
---
```

Log entry convention (OKF format + operation verbs):

```markdown
## 2026-07-12
* **Create** [python-package-manager-uv](facts/python-package-manager-uv.md) — stated in session (18:42:07Z)
* **Update** [git-commit-style](facts/git-commit-style.md) — sharpened wording (19:03:11Z)
```

## Rejected / deferred

- Timestamp-ID filenames for facts (Finding 3).
- INMPARA's full frontmatter set (`status`/`stage`/`domain`/`permalink`)
  — knowledge-lifecycle fields; memory facts have no PARA lifecycle.
  `permalink` specifically was basic-memory residue.
- Automated lint tooling — convention first; build only if M5 evals
  show memory rot (same discipline as everything else).
- Migrating the Second Brain to OKF — its conventions are its own;
  out of scope for agent-dotfiles. (Noted: its in-vault Claude guide
  still documents the retired third-party obsidian-cli — Jon's vault
  content to refresh.)
