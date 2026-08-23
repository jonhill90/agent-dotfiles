# Progressive-disclosure mechanism across the four-store boundary (#281)

Answers #281 within the boundary #281's own thread just settled (the
"Four-store boundary" comment, 2026-08-23): shared vault / per-agent
knowledge / corpus ledger / RAG. This document is the mechanism, not the
storage choice — no per-agent backend is picked here, no scope field is
added to any fact, nothing in the vault is migrated or restructured.

## What was already decided, read as input, not re-derived

`agent-dotfiles#281`'s own thread already settled more of this than a
fresh design pass would suggest starting from. In order:

1. **The council verdict** (same thread, three seats, corpus-grounded):
   *neither* a `scope:` frontmatter field *nor* a filename-prefix convention
   — precedent (`settings/default-skills.txt`'s rostered/`[benched]` split)
   puts scope **outside** the artifact, and `agent/facts/`'s own semantic-
   kebab filenames are concept identity, not a scope label. One vault, one
   index, not a file per project. **Build the detector, not the scheme** —
   and the detector (`scripts/memory_lint.py`'s `index-cap` check, citing
   this issue by number in its own output) already exists and already
   reports the review (80%) and decide (100%) thresholds this thread set.
2. **Jon's standing constraint on this thread**: the end state is the
   existing vault + OKF + a RAG, composed, not one store replacing another;
   RAG is explicitly not needed now and must not be built, scheduled, or
   allowed to block this thread; the per-agent storage backend is Jon's
   reserved call, not a lane's to pick on his behalf.
3. **The four-store boundary** (this thread, same day): shared vault stays
   OKF and is the spine; per-agent knowledge is agent/lane-scoped,
   not-yet-vetted, storage reserved to Jon, but *whatever gets picked needs
   some way for an agent to see what exists before searching* — named as
   real, uneven cost across candidates (cheap for OKF/graphify, an added
   build for pure vectors), evidence for Jon's choice, not something this
   document decides; the corpus ledger stays SQLite, a derivation source,
   explicitly **not a knowledge-consumption surface**; RAG is deferred,
   additive, sits behind a router that prefers a curated answer when one
   exists.

Re-measured, not assumed, before writing anything below:

```
$ python3 scripts/memory_lint.py --json
index-cap: index.md at 49.5% of its declared cap (82/200 lines, 12670/25600 bytes)
```

Still under the review trigger (80%). The council's Q4 conclusion — the
scoping *scheme* is not needed yet — still holds today; this document does
not reopen that question, it answers a different one the boundary comment's
own posting raised for the first time: per-agent knowledge is now a named,
real store, and the map-before-search property has to be specified as a
requirement before Jon picks a backend, not discovered as a gap after.

## The actual question this document answers

"Scope which agent sees what" resolves along the four-store boundary
itself, not by inventing a filtering mechanism the council already refuted.
Per store:

| Store | Who sees its map, and when | Mechanism |
|---|---|---|
| **Shared vault** | Every agent, every session, unconditionally. | `agent/index.md` — already built, already the one file read at session start (`docs/memory.md`'s own Behavior section), already mechanically verified complete and accurate (below). |
| **Per-agent knowledge** | The owning agent only, on its own schedule (not necessarily session-start — the boundary comment frames this as agent/lane-scoped, and a lane's own knowledge is naturally consulted when that lane is working, not by every other agent by default). | **Not built.** Backend reserved to Jon. What's specified here is the one property any backend must satisfy — see below. |
| **Corpus ledger** | No agent browses it directly for answers. It is a derivation source, not a consumption surface, by the boundary decision's own wording — judged items promote out of it into the vault or per-agent knowledge, which is where an agent actually reads from. | No map-before-search requirement applies here at all; there is nothing to disclose progressively because there is no direct consumption path to disclose it *to*. Naming this explicitly so "scope which agent sees what" is not misread as implying the ledger needs a consumption-facing index it was deliberately never given one. |
| **RAG** | Deferred. Not built, not scheduled. When it exists, it sits behind a router that tries a curated answer (vault or per-agent knowledge) first — its own map-analog (an embeddings index) is a different mechanism entirely and is explicitly out of scope for this document. | N/A yet. |

**This is why no new scoping mechanism needed to be invented**: the shared
vault is unscoped by design (one map, every agent, per the council's own
Q2), and per-agent knowledge is scoped *by construction* — it is defined as
belonging to one agent, so there is no cross-agent filtering question to
solve for it at all. The only genuinely open question is whether the owning
agent can see what its own store holds before searching it, which is a
property of the backend, not of a filtering scheme layered on top of one.

## The map-before-search contract — what any per-agent backend must satisfy

Stated as a requirement, not an implementation, so it constrains Jon's
choice without making it:

1. **A lightweight, enumerable inventory exists, separate from full
   content.** For every item in an agent's own knowledge store, at minimum
   an identifier and a one-line description must be retrievable without
   reading the full item — the same shape `agent/index.md` already has for
   the shared vault (one link, one description, per fact).
2. **The inventory is loadable before search, not only as a search
   result.** An agent must be able to ask "what do I already know" and get
   an answer cheap enough to consult routinely, the same way session start
   already reads `agent/index.md` in full before any fact file is opened.
   A backend that can only answer "what's relevant to this specific query"
   (pure similarity search with no enumeration path) does not satisfy this
   — it can only be searched, never browsed, which is exactly the
   asymmetry the four-store boundary comment flagged as a real, uneven
   cost across candidates.
3. **The inventory stays bounded and does not itself require search to
   consult.** `agent/index.md` enforces this today via a declared cap
   (200 lines / 25 KB, `docs/memory.md`) with review/decide thresholds
   already wired into `scripts/memory_lint.py`. A per-agent backend does
   not have to use the same numbers, but its own inventory needs some
   bound and some detection for approaching it — the identical shape,
   applied to a different store, not a new invention.

**What this does NOT do**: rank OKF vs. vectors vs. graphify against this
contract, or claim one candidate passes and another fails. The four-store
boundary comment already did the relevant comparison (cheap for
OKF/graphify, an added build for pure vectors) and named it evidence for
Jon's decision. This document exists so that comparison has a precisely
stated target to be measured against, not to pre-run the measurement.

## What's already mechanically verified today, cited rather than rebuilt

The shared vault's own map already satisfies every clause of the contract
above, and `scripts/memory_lint.py` already proves it on every run rather
than asserting it:

```
$ python3 scripts/memory_lint.py --json
index-cap: index.md at 49.5% of its declared cap (82/200 lines, 12670/25600 bytes)
index:     0/76 facts have no corresponding index.md link
index:     0 index.md links point at a fact that no longer exists
```

Clause 1 (enumerable, separate from full content): `index.md`'s own
one-link-one-description-per-fact shape, unchanged. Clause 2 (loadable
before search): `docs/memory.md`'s own Behavior section, unchanged — read
at session start, before any fact file is opened. Clause 3 (bounded, with
detection): the `index-cap` check above, citing this issue's own
review/decide thresholds by number. No new code was needed to establish
this — it is what `#280`'s linter and `#281`'s own prior council pass
already built, read together for the first time against the contract this
document states.

**Checked, not assumed clean**: `link-integrity` currently reports 9/125
broken internal links. Verified directly against `#310`'s own
`agent/pending-links.md` catalogue rather than treated as a new finding:
these are the identical 9 links that pass already recorded as deliberate
forward references (not fixable candidates, not new breakage) — nothing
has regressed since. Out of this document's own scope either way; named
here only so a reader of this document doesn't re-flag them.

## What this document does not settle — Jon's calls, not re-decided here

1. **Which backend** satisfies the map-before-search contract (OKF,
   vectors, or graphify) for per-agent knowledge. Reserved, per the
   four-store boundary comment's own text.
2. **When per-agent knowledge gets built at all.** Not scheduled by this
   document; RAG's own "not needed now, do not schedule it" constraint
   applies by the same reasoning Jon already gave for RAG — per-agent
   knowledge is the second of the two not-yet-built stores in the same
   boundary decision, and nothing in that decision distinguishes urgency
   between them.
3. **Whether the shared vault's own scoping scheme (per-fact tiers, a
   `scope:` field, per-project index files) is ever needed.** The council
   already answered this for today (no); this document does not reopen it,
   and the existing `index-cap` detector is what would surface it again if
   the vault's own growth ever crosses the review threshold — **could not
   measure** when that will happen; it is a function of future writes, not
   something derivable now.
4. **The request-path gap the original design comment named** (an agent
   that doesn't know to ask can't be pointed at a relevant fact by
   anything other than its own judgment) is unchanged by this document —
   still real, still unbuilt, still would reopen `#272`'s retrieval
   question if solved with anything resembling search. Not this
   document's problem to solve; named so it is not silently assumed
   covered by the map-before-search contract above, which only guarantees
   an agent CAN see what exists, not that it will think to look.
