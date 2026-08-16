# Adopting OKF v0.2 for the memory vault

Companion to `docs/memory.md`, which stays the contract summary; this
document carries the gap report, the additive migration design, and the
loop proposal for #280. Read against the v0.2 SPEC at
`GoogleCloudPlatform/knowledge-catalog` (`okf/SPEC.md`, main branch),
fetched directly for this work rather than recalled from v0.1 — per
`determine-signals`, a stored read of a spec that has since moved version
is exactly the kind of signal this skill exists to recheck. Measured
2026-08-16: 8,648 stars, `Apache-2.0`, repo `pushed_at` 2026-08-15,
`updated_at` 2026-08-16 (`gh api repos/GoogleCloudPlatform/knowledge-catalog`).

## `determine-intent` / `determine-signals`, used and reported on

**`determine-intent`.** Literal ask: research OKF v0.2, design an additive
migration, ship a read-only linter, report what it finds, then propose a
loop — in that order, with a hard separation between the read-only tool
and any mutating one. Underlying goal, read from the brief's own framing
of Jon's quote: memory has drifted (stale facts served as current,
reopened decisions, provenance that exists only as an unattributed quote)
and the fix must not be able to make that class of failure *worse* by
handing an LLM edit access to the store its own trust arguably depends on.
Both readings agree; nothing to surface as a conflict. Stated here per the
skill's step 4, correctable before the work below is read as final.

**`determine-signals`, and what it caught.** The brief's measured baseline
(facts: 45, index lines: 50, title/description present on 35/45) is a
*stored* signal — a snapshot taken before this task started. Re-measuring
live against the same vault paths during this task found **facts: 53,
index lines: 58** (grew during the session; re-measured three times across
the work, values were 52 → 53 → 53, consistent with the vault being
actively written to by other concurrent work, not with a bug in either
count). The two disagree, and the live one is what the linter below runs
against, per the skill's rule to prefer live state and say when it
differs. One structural finding held constant across every measurement
regardless of total count: **exactly 10 facts are missing both `title`
and `description`**, confirmed independently by grep and by the linter
below. `determine-signals` is also why the linter itself treats "0
occurrences of `stale_after`" as "cannot assess staleness" rather than
silently reporting "0 stale facts" — a zero from a field nobody writes yet
is not the same finding as a zero from a field that was checked and came
back clean, and conflating them is the exact `verify-the-instrument`
failure mode `determine-signals` hands off to.

**Did they help?** Yes, concretely: `determine-signals` is the reason this
report states the count discrepancy instead of quietly picking one number,
and is the reason the linter's own report format (below) separates
"field absent" from "field present and checked" everywhere a naive tool
would collapse both into a bare count. `determine-intent` mostly confirmed
a literal reading that was already unambiguous — its value here was
lower than `determine-signals`', because the brief left little goal
ambiguity to resolve. That asymmetry is itself worth recording: a skill
built for "before acting" moments earns its keep in proportion to how
much the request actually needed disambiguating, and this request mostly
didn't.

## 1. Gap report

OKF v0.2 (§3) describes the format as "a directory of markdown files with
YAML frontmatter" with no required tooling — which the vault already is
(`docs/memory.md`'s contract: `agent/index.md`, `agent/log.md`,
`agent/facts/<slug>.md`, YAML frontmatter, `type` required by this repo's
own convention already). Gap, measured live (53 facts) rather than against
the brief's 45-fact snapshot:

| Field / family | OKF v0.2 role | Live coverage |
|---|---|---|
| `type` | required (§4.1, §11) | 51/53 parse; 2/53 have unparseable frontmatter (below) |
| `title`, `description` | recommended (§4.1) | 41/51 parseable facts carry both; 10/51 carry neither |
| `source`, `created` | not OKF fields; this repo's own convention, additive extension keys under §4.1 "Extensions" | carried forward unchanged, no OKF conflict |
| `updated` | not an OKF field; overlaps in intent with `generated.at` (§5.2) but isn't it | 11 facts carry it today; candidate to fold into `generated.at` during migration, not before |
| `generated` (`{by, at}`) | additive, trust family (§5.2) | 0/51 |
| `verified[]` (`{by, at}`) | additive, trust family (§5.2, §5.3) | 0/51 |
| `status` | additive, lifecycle (§5.4) | 0/51 |
| `stale_after` | additive, lifecycle (§5.5) | 0/51 |
| `sources` + credibility signals | additive, provenance (§5.1) | 0/51 |
| legacy `timestamp` | v0.1 field, superseded by `generated.at` (§13.1, breaking) | 0/51 — not present, so the fallback consumers need for it is moot here |
| body `# Citations` | v0.1 convention, superseded by `sources` (§13.1, breaking) | 0/53 — same |
| `okf_version` | optional, root `index.md` frontmatter only (§12) | **present**: `agent/index.md` already declares `okf_version: "0.1"` |

Confirms the brief's structural finding (the 10-fact gap) and narrows one
thing further: this vault has *no* v0.1-breaking-change exposure to manage
(`timestamp` and `# Citations` are both at 0), so §13.1's two breaking
changes are not migration work here — they're a compatibility note for
any *other* OKF bundle this tooling might later point at. The
`okf_version: "0.1"` declaration is the one piece of the vault that
already speaks OKF's own versioning vocabulary (§12) and is the literal
line a version bump would touch first.

## 2. Migration design — additive, and what happens to the 10 notes

Every rule below follows directly from OKF's own conformance floor (§11):
a bundle is conformant with only a non-empty `type`; nothing else is ever
required, and a consumer "MUST NOT reject a concept for missing any
optional family." That is not a convenience reading for this repo — it's
the spec's own designed permissiveness, and the additive plan below rests
on it rather than inventing a local leniency policy.

- **No file changes in this PR.** Per the brief's constraint, work stays
  read-only until this report is reviewed. Nothing below has been applied
  to the vault.
- **New optional keys only.** `generated`, `verified`, `status`,
  `stale_after`, `sources` get added where a fact has enough information
  to populate them honestly. A fact that doesn't gets left alone — OKF
  §11 makes that conformant, not degraded.
- **`title`/`description` on the 10 missing notes.** These are
  *recommended*, not required (§4.1) — the vault stays fully conformant
  without them today, so there is no forcing function to backfill them
  *before* anything else. The linter's job is to keep surfacing the count
  (it does, see below) so the gap doesn't silently persist forever. Per
  the tool boundary, the linter does not write a `title`/`description` for
  those 10 — inferring a human-readable title and one-sentence summary
  from a fact's body is exactly the judgement call reserved for the AI
  side of the boundary (§3 below), reviewed and applied one fact at a
  time, not batch-generated by a script.
- **`timestamp` → `generated.at`, `# Citations` → `sources`.** Both are
  moot for *this* vault today (0 occurrences of either), so there is no
  live breaking-change migration to design. Documented here so a future
  contributor doesn't have to re-derive it: if either ever appears (e.g.
  content copied in from a v0.1 bundle elsewhere), the linter's
  `legacy-v0.1-fields` check already reports counts for both, and OKF's
  own fallback (§13.1: consumers MAY read the legacy field when the new
  one is absent) is sufficient — no forced rewrite is required even then.
- **`okf_version` bump.** `agent/index.md` already declares
  `okf_version: "0.1"`. Bumping it to `"0.2"` is a one-line, purely
  declarative change with no schema consequence (§12: consumers that
  don't understand a declared version fall back to best-effort
  consumption) — but it is still a vault write, so it stays out of this
  PR and is the first concrete action once this report is reviewed.
- **`source`/`created`/`updated` stay as they are.** They are not OKF
  fields; OKF's "Extensions" clause (§4.1) explicitly allows arbitrary
  producer-defined keys and requires consumers to preserve them. No
  rename is needed for OKF conformance. `updated` and `generated.at`
  overlap in intent (both answer "when did the content last change"); folding
  one into the other is a judgement call for the AI side of the boundary
  once there's a concrete fact to test it against, not a blanket rule to
  apply script-side.

Net: adoption changes nothing about what makes a vault note readable
today. Every consumer that reads `type`/`title`/`description`/`source`
now keeps working unchanged; new frontmatter is additive and ignorable by
anything that doesn't yet look for it.

## 3. The read-only linter — built first, run against the live vault

`scripts/memory_lint.py`. Deterministic: YAML parsing (PyYAML with the
same flat-key fallback `scripts/validate_repository.py` already uses for
PyYAML-less machines), string/regex link resolution, SHA-256 hashing, and
plain date comparison. No model call anywhere in it, and no write call
anywhere in it — verified by a test (`test_never_writes_to_the_vault`)
that snapshots every file's mtime before and after a run and asserts they
match.

**TOOLS DETECT AND REPORT. THEY NEVER REWRITE MEANING.** This is the
explicit design boundary the brief asked to have stated, not left
implicit: the tool's entire output surface is a `Finding` list
(`level, check, message`) rendered to text or JSON. There is no code path
in `memory_lint.py` that opens a vault file for writing. Deciding whether
a flagged fact is still true, resolving a possible contradiction, or
writing a correction to `title`/`description`/`generated`/`verified` is
explicitly out of scope for this script and is not built in this PR — a
second, mutating tool is a separate, later PR by design, reviewed against
this one's report rather than folded into it. A tool that can only report
cannot corrupt a memory, however buggy it turns out to be; a tool that can
write can, and that is the entire reason the two are not the same
program.

**Checks implemented**, each mapped to the brief's list:

1. Frontmatter conformance against OKF §11 (parseable YAML, non-empty
   `type`) — the only check that affects exit status, matching OKF's own
   floor.
2. Recommended-field coverage (`title`, `description`, §4.1) — advisory.
3. OKF v0.2 additive-family presence (`generated`, `verified`, `status`,
   `stale_after`, `sources`, §5) — advisory, reports counts so the gap
   above stays measured, not asserted, as adoption proceeds.
4. Legacy v0.1 field detection (`timestamp`, body `# Citations`, §13.1).
5. `stale_after` freshness — flags facts where `today >= stale_after`
   (§5.5). Reports "cannot be assessed" rather than "0 stale" when no fact
   carries the field, so an empty result isn't misread as a clean one.
6. `verified[]` coverage and recency — reports facts with no `verified[]`
   entry at all (OKF's *unverified* trust tier, §5.3) separately from
   facts whose latest `verified[].at` is older than a configurable
   threshold (default 90 days).
7. `[[wikilink]]` and markdown-link integrity — resolves link targets
   against known fact slugs; OKF (§6.1) requires consumers to *tolerate*
   broken links (they may be not-yet-written knowledge), so this is a
   report, not a failure.
8. Near-duplicate detection — SHA-256 of normalized (whitespace-collapsed,
   lowercased) body text; flags exact-match groups.
9. Possible-contradiction heuristic — facts with high token overlap in
   their slugs (Jaccard ≥ 0.6) but differing body hashes are flagged as
   **candidates for AI review**, explicitly not as confirmed
   contradictions; this is a deterministic proxy for "these two might be
   about the same subject," and the tool says so in its own output rather
   than implying a verdict.
10. Index reconciliation — computes which facts have no corresponding
    `index.md` link and which `index.md` links point at a fact that no
    longer exists, and reports both as counts. This is "rebuild the
    index" done as a **read-only diff report**, not a write — the brief
    asks for the check, not for the file to change, and the tool boundary
    above means it doesn't.

**Run against the live vault (2026-08-16), 53 facts, 58 index lines
— counts only, no fact content, per the brief's constraint:**

- Conformance: 51/53 facts parse with a non-empty `type`. **2 facts have
  unparseable frontmatter** — both from an unquoted colon inside a scalar
  value (`title: <text>: <text>`), which breaks YAML mapping parsing. This
  is a real, previously-undetected defect: a naive reader that doesn't
  validate would either crash or silently drop the whole frontmatter
  block for those two files. Not previously flagged by anything in this
  repo, because nothing here parsed vault frontmatter as YAML before now.
- Recommended fields: 10/51 parseable facts missing both `title` and
  `description` — the same defect and the same count the brief measured,
  confirmed against the live, larger vault.
- OKF v0.2 families: 0/51 for all five (`generated`, `verified`, `status`,
  `stale_after`, `sources`) — confirms the brief's baseline exactly.
- Legacy v0.1 fields: 0/51 `timestamp`, 0/53 `# Citations` — no
  breaking-change exposure, as above.
- Freshness: 0 facts carry `stale_after`, so 0 is reported as "cannot be
  assessed," not "0 stale."
- Trust: 51/51 facts carry no `verified[]` entry (unverified tier by
  OKF's own default, §5.3 — not itself a defect).
- Link integrity: 8/87 internal links do not resolve to an existing fact.
  Manually spot-checked (link targets only, not surrounding fact content):
  seven are genuine forward references to facts that don't exist yet,
  which OKF §6.1 explicitly permits and calls "not-yet-written knowledge."
  One is a false positive — a fact's body quotes documentation prose that
  contains a literal `[[name]]` placeholder, not an intended link. Noted
  as a linter limitation: it cannot distinguish a quoted example from a
  real link, and OKF's own permissiveness on broken links means this
  doesn't need fixing to stay conformant.
- Near-duplicates: 0 exact-duplicate body groups.
- Possible contradictions: 0 candidate pairs at the current similarity
  threshold.
- Index: `agent/index.md` already declares `okf_version: "0.1"` (§12). 1/53
  facts has no corresponding index link; 0 index links point at a deleted
  fact.

**Every number above is measured** by running `scripts/memory_lint.py`
against `$AGENT_MEMORY_VAULT` during this task (2026-08-16); none is
inferred. The fact-count drift (45 → 52 → 53 across the brief's snapshot
and three re-measurements here) is also measured, not estimated — each
value came from a separate live run.

## 4. Proposing the memory loop — after the tool, not before

This section is a proposal, not a build; nothing here is implemented.
Read against `docs/loop-engineering.md`'s twelve-field contract and ring
model, which govern any loop design in this repository, and against the
supervisor loop (now `jonhill90/agent-supervisor`) as the sibling this one
sits beside rather than duplicates.

**Objective (end state, not an activity).** Every fact in the vault has
been checked by the read-only linter since its last content change, and
every WARN the linter raises has either been resolved by an AI-assisted
pass (title/description backfilled, a contradiction adjudicated, a stale
fact re-verified or retired) or explicitly deferred with a reason. Not
"the linter ran" — the linter running and nothing downstream reading its
output is the exact "444 completion events, 0 acknowledgements" failure
`determine-signals` names as a shape to avoid.

**Trigger.** Goal-based within a session (run the linter before/after any
memory-writing turn) plus a low-frequency time-based sweep (weekly is a
reasonable starting cadence; not yet measured against real drift rate) —
Ring 1 for the former, Ring 3/5 for the latter per the ring table. Cron
driving a *mutating* pass directly is exactly what §14 already prohibits
for the supervisor loop, and the same prohibition applies here for the
same reason: a scheduled process should never be the thing deciding a
memory fact's meaning unattended.

**Discover / Intake watermark.** The linter's own report is the intake
list — WARN and ERROR findings, keyed by fact slug and check name. The
watermark is "findings already actioned or explicitly deferred," tracked
so a re-run doesn't re-surface the same accepted deferral every time
(the corpus's most common silent defect, per `loop-engineering.md`).
Where that watermark lives is an open question this proposal doesn't
resolve — a `status`/`verified[]` entry on the fact itself is the OKF-native
answer and avoids a second, parallel ledger, but needs testing against a
real backlog before being decided.

**Delegation.** Exactly the boundary already established: the linter
(Ring 0, no model) produces findings; a model-driven step, invoked
per-finding rather than batch, is the only thing that writes — and it
writes one fact at a time, with the finding that justified the change
recorded in that fact's own `generated`/`verified` frontmatter, not
silently.

**Verification.** The linter itself, re-run after any write, is the
loop's own verification step — a corrected fact should produce zero new
WARNs of the kind that triggered the fix, and the exit-status contract
(§11 conformance only) means a write that breaks frontmatter parsing is
caught immediately, not on the next unrelated read.

**Budget / Escalation / Exit.** Not sized yet — this is the one field the
corpus calls out as most-often-skipped, and guessing a number here without
a real run to measure against would be exactly the kind of inferred
figure `AGENTS.md`'s "Recording Figures" section warns against. Escalation
path: any AI-side judgement call the loop can't resolve deterministically
(a genuine contradiction between two facts, not the heuristic's
candidate list) surfaces to Jon rather than picking a side, per the tool
boundary.

**Why this is a peer, not a merge.** The supervisor loop watches lane
health and PR mergeability; a "skills loop" (mine-transcripts,
`determine-signals`' own hand-off target, and the §10.1 evidence-bar
cadence) watches whether transcript vocabulary should become a rostered
skill. Both are goal-based loops reading a different corpus and gating a
different kind of write. A memory loop reading vault frontmatter and
gating vault writes is the same shape applied to a third corpus — sharing
the ring model and the twelve-field contract, not sharing state or a
process with either.

## What this PR does and does not do

**Does:** fetches and reads the v0.2 SPEC from source; measures the live
vault gap; documents an additive migration with no vault writes; ships
`scripts/memory_lint.py` (read-only) and its test suite; runs the linter
against the live vault and reports findings by count; proposes, without
building, how a memory loop would use the linter.

**Does not:** write anything to `$AGENT_MEMORY_VAULT`; bump
`okf_version`; add `generated`/`verified`/`status`/`stale_after`/`sources`
to any fact; backfill any of the 10 missing `title`/`description` pairs;
build any mutating tool. Those are next steps, gated on this report being
reviewed, per the brief's constraint.
