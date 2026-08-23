---
type: Map
description: What the prompt corpus is, what each of its five views answers, and the exact query to run for each -- an entry point, not a report.
---

# The corpus, mapped

Not a report — a map. `docs/corpus/*.md` (the other files in this
directory) are dated pass reports from specific sweeps; each documents
what one triage or refresh pass found and did, and none of them is
where a fresh agent should start. This file is that start: what the
corpus is, what it can answer without reading it end to end, and the
exact query for each answer, so consulting it costs one short read plus
one command, never a full scan.

## What the corpus is

Every prompt Jon has typed, mined from harness transcripts
(`mine_prompts.py`) and judged into structured `items` — parameters,
questions, directives, thoughts, corrections
(`itemize_prompts.py`) — by a model, once, at write time. Everything
downstream of that judging step is plain SQL; nothing reads a
transcript or calls a model again to answer a query against it. Tooling
and schema: `jonhill90/agent-supervisor`
(`scripts/supervisor/{mine_prompts.py,itemize_prompts.py,cli.py,core.py}`).

**Where it lives:** `~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3`
— not tracked in any git repo, not this repository's own state. The
same file also holds this estate's *operational* tables (`lanes`,
`tasks`, `sessions`, `pr_verdicts`, `events`, and others) — those are a
different concern (lane/task supervision, not what Jon has said) and
are out of scope for this map entirely; querying them is a different
question with a different entry point, not covered here.

## The five views, one line each, and the exact query

Every view below is queryable two ways: `cli.py prompts <view>` (a
human-readable table, run from an `agent-supervisor` checkout) or raw
`sqlite3` against the ledger path above directly (works with no
checkout, only `sqlite3` installed). Both given per view so this map
doesn't assume which one is on hand. **Counts are never given here** —
a number written down goes stale the moment the next prompt lands; the
query is the map, run it for the current number.

### `unacknowledged` — things said that nobody has recorded acting on

Every `items` row still `status = 'open'`, of ANY kind — a parameter,
a question, a directive, a thought, a correction Jon raised that has
not been marked acknowledged, acted, resolved, or dropped. The
broadest of the five; `open_questions` below is a strict subset of
this one (its `question`-kind rows).

```
python3 scripts/supervisor/cli.py prompts unacknowledged
sqlite3 ~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3 "select * from unacknowledged;"
```

Reach for this when: triaging backlog, or checking whether something
Jon said has already been recorded as handled before asking him again.

### `open_questions` — questions raised, never answered

`items` rows where `kind = 'question'` and `status = 'open'` — things
Jon asked, not things he decided. Answering one and marking it
resolved is a different action than acting on a parameter or directive;
this view exists so a question doesn't sit silently inside the broader
`unacknowledged` set indistinguishable from a directive nobody got to.

```
python3 scripts/supervisor/cli.py prompts open_questions
sqlite3 ~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3 "select * from open_questions;"
```

Reach for this when: about to ask Jon something — check here first
in case he already asked it of himself, or check whether an answer is
overdue before raising a new one.

### `live_parameters` — durable constraints and preferences, not retracted

`items` rows where `kind = 'parameter'` and `weight != 'retracted'` —
both `hard` (binding) and `preference` (softer) parameters together.
Use `possibility_count` below when only the `hard` subset matters.

```
python3 scripts/supervisor/cli.py prompts live_parameters
sqlite3 ~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3 "select * from live_parameters;"
```

Reach for this when: checking whether a design choice already has a
stated constraint or preference on record before treating it as open.
This is the closest thing the corpus has to the vault's `live_parameters`
view of hard-weight facts — see "corpus vs. vault" below for why they
are not the same list.

### `conflicts` — two items explicitly linked as contradicting each other

Joined pairs of `items` where a `links` row records `relation =
'conflicts_with'` between them. **Never inferred** — `agent-supervisor#303`'s
own brief is explicit that this view reports recorded links only; a
plausible-looking contradiction with no `links` row between the two
items does not appear here, and finding one is a human or a deliberate
pass's job, not a query's.

```
python3 scripts/supervisor/cli.py prompts conflicts
sqlite3 ~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3 "select * from conflicts;"
```

Reach for this when: two stated positions seem to disagree and there's
reason to think it was already noticed and recorded, not to discover a
contradiction fresh — this view cannot do that part.

### `possibility_count` — how many parameters are binding right now

A single aggregate row: `COUNT(*)` over `live_parameters` filtered to
`weight = 'hard'`. Structurally different from the other four — it
always returns exactly one row, never a list to page through.

```
python3 scripts/supervisor/cli.py prompts possibility_count
sqlite3 ~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3 "select count from possibility_count;"
```

Reach for this when: a single number is genuinely what's needed (e.g.
citing "how many hard constraints exist" in a report) — cite the query
above, not a number copied from a prior run.

## Corpus vs. the vault vs. repo docs — when to reach for which

Three different stores, three different questions, per the four-store
boundary `docs/memory-per-agent-map-contract.md` names (shared vault /
per-agent knowledge / corpus ledger / RAG) — this corpus is that
document's third store, and its own text is explicit that the corpus
"has no consumption-facing map at all... judged items promote out of
it into the vault or per-agent knowledge, which is where an agent
actually reads from." This map does not reopen that boundary; it
supplies the map-before-search property that boundary's own contract
requires (see "Contract" below) without changing what the corpus is
for.

- **The corpus** answers "what did Jon actually say, and is it still
  open." It is a derivation source and a search target for a *specific
  prompt or decision*, not somewhere an agent reads standing context
  from at session start.
- **The vault** (`$AGENT_MEMORY_VAULT/agent/index.md`, 82 lines over 76
  facts as of this write) is the *distilled, durable* record — a fact
  promoted out of the corpus once it's been judged worth keeping
  standing. Read this at session start; do not read the corpus at
  session start.
- **A repo's own `docs/`** (this repository's `docs/`, or
  `jonhill90/agent-tui`'s, mapped the same way by `docs/index.md`
  there — `agent-tui#136`) answers "what does this specific codebase's
  own design/status say," scoped to that repository, not to what Jon
  said across all of them.

Concretely: "did Jon ever say X" → corpus (`unacknowledged` or grep the
right view). "What do we currently believe about X, standing" → vault.
"How does this repo's own architecture handle X" → that repo's
`docs/index.md`.

## What the corpus is NOT for

- **Not a standing-context source.** Nothing here is read at session
  start; only the vault's `index.md` is. Querying the corpus is a
  deliberate, targeted act, not ambient context.
- **Not a substitute for the vault.** A fact worth carrying forward
  gets promoted into a vault note; the corpus keeps the raw judged
  record of every prompt regardless of whether it was ever promoted,
  including ones that were retracted, dropped, or superseded. Reading
  the corpus instead of the vault risks surfacing a stale or since-
  retracted position as if it were current.
- **Not a place to write new facts.** This map does not add, and no
  query above mutates, anything. Writing happens through
  `mine_prompts.py --store` / `itemize_prompts.py --load` only — a
  separate, deliberate pipeline this map does not cover.
- **Not the operational ledger.** `lanes`, `tasks`, `sessions`,
  `pr_verdicts`, and the rest of this same SQLite file are a different
  system (lane/task supervision) with a different entry point; this map
  does not attempt to be theirs too.
- **Not a contradiction detector.** `conflicts` reports links a pass
  already recorded, never infers one — see that view's own section
  above.

## Contract — the same one `agent-dotfiles#315`/`agent-tui#136` require

- **Enumerable, separate from full content:** exactly five views, named
  and one-lined above, without reading a single row of corpus content
  to know they exist.
- **Loadable before search, not only as a search result:** this file
  is the thing to read before querying, not something a search for a
  specific fact happens to surface.
- **Bounded:** five views is the whole surface — `Ledger.PROMPT_VIEWS`
  in `scripts/supervisor/core.py` is the single source of truth for
  the set, and this map's own set matches it exactly as of this write;
  a sixth view added there without a matching section here is this
  file going stale, the same failure mode `agent-tui#136`'s own
  `devils-advocate` pass named and did not close for its map either.
- **Cheap enough to consult routinely:** one short read (this file) and
  one command per question — no full-corpus scan required to find out
  what's askable.

## What this pass could not measure

Whether `Ledger.PROMPT_VIEWS`' five names will still match this file's
five sections at some future read — no mechanical guard checks that
today (the same gap `agent-tui#136`'s `devils-advocate` answer found
and left open for its own index). Not built here; flagged rather than
silently assumed solid.
