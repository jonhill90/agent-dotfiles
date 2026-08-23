# Memory done-condition: when is shared memory "good enough" to hang a harness-memory override on

**Scope.** This document answers one question: what does "good enough" mean
for `$AGENT_MEMORY_VAULT`, the shared cross-harness vault, such that it is
safe to force each harness off its own built-in store and onto this one
(`harness-memory-override-is-later`, vault fact, Jon, 2026-08-23)? It does
not decide a storage format, does not build anything, and does not cover the
**per-agent** memory tier or its knowledge-graph view — those are a
separate, explicitly-reserved decision (agent-tui#116, #61) and are called
out below only to keep them out of this gate.

Jon named three prerequisites for the override, in his own words recorded in
the vault fact: *"memory iterated to something solid, progressive disclosure
done properly, and the storage question settled."* This doc turns each into
checkable criteria, measures the vault against them as of 2026-08-23, and
states plainly what is not yet true.

## How this was measured

`agent-dotfiles`'s `scripts/memory_lint.py` (agent-dotfiles#280/#281, merged
to `origin/main` as of `448eca7`) is a read-only, deterministic linter built
for exactly this vault. Run against the live vault today:

```
$ python3 scripts/memory_lint.py --json
fact_count: 69
index_lines: 75 / 200 cap (37.5%)
index_bytes: 11475 / 25600 cap (44.8%)
title: 69/69, description: 67/69
generated/verified/status/stale_after/sources: 0/69 each
link-integrity: 10/112 internal [[wikilink]]s unresolved
near-duplicates: 0 groups
possible-contradictions: 0 pairs
unlinked facts (strict): 0/69
```

Local checkout note: `agent-dotfiles` (this shared checkout) was 7 commits
behind `origin/main`; the script and doc cited above were read from
`origin/main` directly (`git show origin/main:<path>`) rather than from a
stale local tree, per the repo's own "verify a mutation applied" and
"instrument that can't see a thing" guardrails.

## Prerequisite 1 — progressive disclosure done properly

| Criterion | Measured | Status |
|---|---|---|
| Session-start load (`index.md`) stays under its declared cap with margin, not just under it | 75/200 lines, 11,475/25,600 bytes — both under the 80% *review* threshold agent-dotfiles#281's council set as the reconsideration trigger | **TRUE** |
| Every fact is reachable from the index (no orphaned facts) | 0/69 facts unlinked from `index.md` (linter `--strict` check, agent-dotfiles#300) | **TRUE** |
| Cross-fact `[[wikilink]]` edges resolve to real facts | 10/112 internal links point at a fact that does not exist | **NOT TRUE** — 8.9% of the vault's only relationship mechanism is broken |

Two of three hold. The broken-link count is a small, mechanically fixable
defect, not a design gap — but it means "progressive disclosure done
properly" is not yet a clean pass.

## Prerequisite 2 — memory iterated to something solid

This is where `memory-needs-its-own-loop` (2026-08-15) and the OKF v0.2 gap
report (`docs/okf-adoption-280.md`) point at the same unclosed gap from two
directions.

| Criterion | Measured | Status |
|---|---|---|
| OKF v0.2 conformance floor (parseable frontmatter, non-empty `type`) | 69/69 | **TRUE** |
| Recommended fields (`title`, `description`) near-complete | title 69/69, description 67/69 | **TRUE (near)** |
| Trust/lifecycle fields exist so staleness and verification are checkable from frontmatter, not re-derived by rereading every fact | `generated`, `verified`, `status`, `stale_after`, `sources` — **0/69 on every field** | **NOT TRUE** |
| No duplicate or contradicting facts | 0 exact-duplicate groups, 0 similar-slug pairs flagged | **TRUE, as far as this detector reaches** — it only catches identical bodies or near-identical slugs; semantic contradiction between differently-worded facts is out of its reach (linter's own scope, `docs/okf-adoption-280.md` §3: "detect and report... judgement needs a model in the loop") |
| A recurring loop exists that sweeps transcripts for uncaptured intent, re-verifies facts against current reality, and surfaces contradictions/staleness for action | `mine-transcripts` and `memory_lint.py` both exist and work; **nothing schedules either, and nothing acts on their findings** | **NOT TRUE** |
| Cross-harness write-back and recall work | Demonstrated once: E12, 2026-07-12, `tests/evals/results/2026-07-12-e12-memory-writeback.md` (private `jonhill90/agent-evals`, not publicly re-checkable) | **Evidence exists, but is a single point-in-time proof, not a repeatable or continuous check** |

The two real blockers here are the same one Jon named directly:
`memory-needs-its-own-loop` records his own diagnosis — *"we need to
eventually setup a loop to build the perfect memory"* — and that fact is
explicit that this is *"recorded as an ask, not as work in progress."*
Nothing in this pass found that to have changed. The trust/lifecycle field
gap is the same problem from the linter's side: `docs/okf-adoption-280.md`'s
own migration design left backfilling those fields to "the AI side of the
boundary... reviewed and applied one fact at a time," which is loop work
that has not started.

## Prerequisite 3 — the storage question settled

Out of scope for *this* gate on purpose: the override this doc is about is
whether to point each harness at the **existing shared vault**, which
already has a settled format (OKF markdown, `docs/memory.md`). The open
storage question Jon reserved (agent-tui#116) is about a **different,
not-yet-built tier** — per-agent memory with a knowledge graph — and is not
a precondition for the shared-vault override. Listed here only so the two
are not conflated:

- agent-tui#116 (open): per-agent storage format — OKF, vectors, or
  "graphify" — explicitly reserved for Jon, not decided.
- agent-tui#120 (merged): evidence gathered for #116, no format picked.
- agent-tui#61 (open, backlog): the draggable graph view, explicitly
  sequenced *after* loop and memory, "at somepoint."

## What is NOT yet true — the actual gap the override is waiting on

1. **No recurring memory loop.** `memory_lint.py` and `mine-transcripts`
   exist as tools; nothing schedules them and nothing consumes their output.
   This is the headline gap — it's the literal content of
   `memory-needs-its-own-loop` and remains unclosed.
2. **Trust/lifecycle fields are at 0/69 across the board.** Staleness and
   verification cannot be checked from frontmatter today; every fact reads
   as equally current regardless of age, which is the drift failure mode
   the OKF v0.2 adoption work was started to fix and has not yet applied.
3. ~~**10/112 internal links are broken**~~ — addressed, see the 2026-08-23
   update below. 2/69 facts are still missing a `description`; unchanged by
   this pass, out of its scope.

Everything else asked for by "progressive disclosure done properly"
(session-start load, reachability, OKF conformance floor) already measures
as true today. The gate is not blocked on the storage question (out of
scope here) — it is blocked on prerequisite 2: no loop yet drives memory,
so nothing keeps it solid over time even where it is solid right now.

## Update 2026-08-23 — prerequisite 1's link-integrity gap addressed

The measurement above (10/112, taken earlier the same day) was re-derived,
not assumed, then acted on: `python3 scripts/memory_lint.py --json` against
the live vault now reports **9/111 internal links resolve to a missing
fact**.

Each of the original 10 was investigated individually — checked against
every existing fact slug in the vault (`ls agent/facts/`) for a typo or
rename before deciding — per `memory-conventions.md`'s own convention that a
`[[name]]` with no matching file is not automatically an error:

| # | Source → target | Category | Disposition |
|---|---|---|---|
| 1 | `a-conflicted-pr-branch-runs-no-ci-at-all` → `[[name]]` (literal, in `memory-needs-its-own-loop`) | **Neither** — linter false positive: example syntax inside backticks illustrating the `[[name]]` convention itself, not an intended link | Escaped (`` \[\[name\]\] ``) so the pattern no longer parses as a wikilink. Total link count drops 112→111 for this reason, not a deletion. |
| 2 | `hill90-app-public-cleanup-precondition` → `hill90-app-repo-visibility-history-finding` | Deliberate forward reference — no existing fact is a match | Left as-is; catalogued |
| 3 | `hill90-app-public-cleanup-precondition` → `hill90-app-is-a-tenant` | Deliberate forward reference — no existing fact is a match | Left as-is; catalogued |
| 4 | `hill90-one-keycloak` → `hill90-app-is-a-tenant` (same target as #3) | Deliberate forward reference | Left as-is; catalogued |
| 5 | `hill90-one-keycloak` → `hill90-silent-config-failures` | Deliberate forward reference — no existing fact is a match | Left as-is; catalogued |
| 6 | `intent-as-a-constraint-solve` → `decide-by-variant` | Deliberate forward reference — names a Claude Code skill and Jon's own standing instruction, neither yet written as a vault fact | Left as-is; catalogued |
| 7 | `intent-as-a-constraint-solve` → `memory-design` | Deliberate forward reference — the `weight`/`status`/`stale_after` field design isn't in `memory-conventions.md` yet | Left as-is; catalogued |
| 8 | `transcripts-are-a-lossy-record-of-intent` → `memory-failure-mode-is-staleness-not-retrieval` | Deliberate forward reference — no existing fact is a match | Left as-is; catalogued |
| 9 | `verify-against-parent-not-just-green` → `positive-control-fixture` | Deliberate forward reference — sibling concept to the existing `green-ci-is-not-evidence` fact, not yet written on its own | Left as-is; catalogued |

No fact was deleted to make a link resolve, and no fact was invented to fill
a forward reference — writing those nine facts is real judgement work,
explicitly out of this pass's scope. The nine are now recorded in a new
vault file, `agent/pending-links.md` (outside `agent/facts/`, same tier as
`index.md`/`log.md`), so a later run of `memory_lint.py`'s link-integrity
check does not re-discover and re-litigate the same nine gaps — each stays
correctly flagged until its target fact is actually written.

This does not touch the storage-backend question (agent-tui#116, still
reserved to Jon) and does not change prerequisite 2's blocking status —
`memory-needs-its-own-loop` remains the real gate.
