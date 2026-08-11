# Loop Engineering

This document records the current position on designing and running repeating
or unattended agent work with this harness set. It is a sibling to
`docs/harness-engineering.md`: a working document future loop work reads and
edits, not a summary of a research project.

Distilled from the 23-file research corpus at
`~/source/repos/Personal/Loops-Research` (dated 2026-07-27 through
2026-08-02), which stays external and read-only — it is not vendored here.
Files read for this distillation: `01-contract.md`, `02-loop-types.md`,
`03-triggers.md`, `08-budget.md`, `RECOMMENDATIONS.md`,
`specs/loop-contract.md`, `specs/loop-memory.md`. Not read: the remaining 16
files (`00-landscape`, `04-verifiers` through `07-isolation`,
`09-memory`/`10-hooks`/`11-daily-loops`/`12-ops`,
`13-repo-review-loop-engineering`, `14-more-loops`, `CHEATSHEET`, `SOURCES`,
`specs/deferred`) — the seven above already carry everything this repo needed
to decide, and `RECOMMENDATIONS.md` quotes the load-bearing parts of
`13-repo-review-loop-engineering.md` and `14-more-loops.md` directly, so their
citations below are inherited rather than independently verified against the
source files.

## This repository's mechanism already, before any loop vocabulary

`docs/SPEC.md` §14 and §15 are canonical and are cited, not restated, here.
Read them before designing any loop that spans more than one Claude Code
session:

- **§14** settles the supervisor/worker handoff: cooperative `tmux wait-for`
  is the only mechanism in active use, its four measured limits (serializes
  lanes, is not crash-safe, has no timeout at the tmux layer, carries no
  payload), and the layered fix — a backgrounded fast path, a Stop-hook or
  `herdr agent wait` failure path, a durable ledger for payload and restart
  survival, and cron restricted to dead-man stall detection only. **Cron
  driving the loop directly is prohibited, not discouraged — that was the v1
  bug.**
- **§15** settles the transport boundary: the ledger, ownership-safe
  transitions, and attention live in a portable core; a transport adapter
  (tmux, ACP, `herdr`) owns only delivering a prompt and reporting what came
  back.

Any loop-contract or loop-memory work in this repository has to compose with
§14's layering and §15's boundary, not invent a competing one.

## The twelve-field contract

The corpus's most reusable artifact (`01-contract.md`) is a **twelve-field
contract**, checked before a loop is given a trigger, in three groups:

**Setup** — Objective (an end state, not an activity) · Trigger · Discover /
Intake (with a dedupe watermark) · Workspace.
**Execution** — Context · Delegation · Verification · State.
**Governance** — Budget · Escalation · Exit · Next action.

Two fields are the ones most often left blank and cause the most damage when
they are:

- **Intake watermark.** Without one, every run reprocesses the whole
  backlog — the single most common silent defect in scheduled loops.
- **Escalation.** A loop with no path back to a human is not
  production-grade; name the conditions and how a human is notified.

### Stop conditions — the field's number-one failure mode

Every source in the corpus independently names a missing or weak stop
condition as the top cause of runaway loops (`01-contract.md`). Always define
**two, never one**:

1. **Goal-based**, demonstrable from the transcript: one measurable end
   state, a stated check (`npm test` exits 0, `git status` is clean), and the
   constraints that must hold along the way. A condition the evaluator cannot
   see is not a condition.
2. **Safety fallback**, all four caps, because they fail differently:
   iterations (start ~50, raise only with real cost data), tokens, wall
   clock, and spend — plus idle detection (no commit in N iterations) and
   repetition detection (same tool, near-identical inputs, 2–3 times running).

Name terminal states, not a boolean:
`verified-complete | no-work-found | blocked-needs-human | budget-exhausted | failed-unrecoverable`.

A green run exit is not a success claim — Anthropic's own Routines docs warn
that green means only "the session started and exited without an
infrastructure error." Treating it as more is the second-most-common failure
in the corpus.

### Skill first, then loop

Every loop in Boris Cherny's own attested Claude Code set invokes a named
skill, never an ad-hoc prompt (`RECOMMENDATIONS.md`, attributed to
`14-more-loops.md` §2 in the corpus, not independently re-read here). The
rule this repository should hold a loop to: **if the work is not yet a
named, tested procedure, it is not ready to be looped.** A loop multiplies
whatever an ad-hoc prompt gets wrong by the iteration count.

### Untrusted trigger payloads

Issue bodies, alert text, PR descriptions, and webhook payloads are
attacker-controlled input, not instructions. Anthropic wraps fired Routine
payloads in an explicit untrusted-data block for this reason; any
home-grown loop that ingests such text needs the same discipline, with the
prompt explicitly opting in to acting on the payload.

## Choosing a mechanism — the ring model, mapped onto §14

`02-loop-types.md` sorts loop mechanisms by **who holds the restart
button** — Anthropic's public four-type vocabulary (turn-based, goal-based,
time-based, proactive) is the naming layer; the rings below are the
mechanism underneath it:

| Ring | Mechanism | Restart held by | Survives session close? |
|---|---|---|---|
| 0 | Inner agentic loop | The model | No |
| 1 | `/goal` | A separate small evaluator model | No (restored on resume) |
| 2 | Stop hooks | The hook script's exit code | No |
| 3 | `/loop` | A timer | No — 7-day expiry |
| 4 | Headless / Ralph | The shell | Yes, no session at all |
| 5 | Cron / Routines | The OS or Anthropic's infra | Yes |

Decision table (`02-loop-types.md`, `specs/loop-contract.md` §7):

| If | Then |
|---|---|
| Must survive the machine being off | Ring 5 — managed/cloud scheduling |
| Needs local files and the machine is on | Local scheduled task |
| Long unattended grind | Ring 4 — headless, fresh context per pass, sandboxed |
| Condition is deterministic and repo-wide | Ring 2 — a code-enforced stop gate |
| Condition is judgeable from the transcript | Ring 1 — a model-evaluated goal |
| Watching something during a live session | Ring 3, or better, a push/event channel |

The general principle: **prefer push over poll, and prefer the weakest
mechanism that satisfies the contract.** Durability nobody asked for is
blast radius nobody asked for either.

**This repository's own instance of ring 5 is already layered, per §14**:
cron is not itself ring 5's mechanism here, it is that layer's stall
backstop — the supervisor/worker fast path (backgrounded `wait-for`) plus a
Stop-hook or `herdr agent wait` failure path plus the v5 ledger *is* this
repo's ring-5-equivalent durability story. A loop design that reaches for
"use cron" where §14 already gives a fast path is reinventing a mechanism
this repo rejected on evidence.

### Where the corpus and this repo's decided mechanism diverge

No direct contradiction was found. The corpus's ring 5 (Routines / OS cron)
describes a different substrate — externally hosted or single-shot scheduled
prompts — from §14's supervisor/worker loop, which is this repo's own
multi-lane orchestration mechanism. They do not compete for the same slot.
The one place they touch is cron's role: the corpus treats cron as one
option among several durable-restart mechanisms (`02-loop-types.md`); §14 is
stricter, permitting cron **only** as a dead-man stall detector and
prohibiting it as the mechanism outright, because that was the measured v1
defect (a lane's true state — working vs. wedged — is not recoverable from a
blind cron re-entry). Any future loop-contract skill in this repository must
carry §14's stricter rule, not the corpus's softer "ring 5" framing, whenever
the loop in question is this repo's own supervisor/worker pattern rather than
an externally-triggered Routine.

### Stage the autonomy: L1 → L2 → L3

Every loop starts at **L1 report-only**, and earns L2 (assisted fixes) or L3
(unattended) on evidence — never widen scope and autonomy in the same step,
or a regression cannot be attributed to either change
(`RECOMMENDATIONS.md`, `specs/loop-contract.md` §8). A loop's real autonomy
equals the highest verification level (deterministic assertion → schema/
policy linter → field truth → LLM-as-judge → human checkpoint) it passes
without a human; if the only real check is LLM-as-judge, the loop is a fast
draft generator with a rubber stamp and belongs at L1.

Most runs should be a cheap no-op with early exit — thousands of tokens, not
tens of thousands. If the common case is expensive, the cadence or the
intake filter is wrong. Report one line even when idle; a silent loop is
indistinguishable from a dead one.

**No loop in this repository auto-commits or auto-merges.** Every corpus
source that discusses it lands on human review before merge; this repo's own
global instructions already require verification evidence before a success
claim, and `01-contract.md`'s stop-condition anti-patterns list treating a
green run as success as a named failure mode.

## Two load-bearing findings — measured, not corpus opinion

The supervisor's brief for this document names two findings from this
repository's own operating history as load-bearing, distinct from the
corpus's design reasoning:

1. **Throughput comes from lanes, not tick cadence.** The 4-day Hill90 loop's
   output came from worker parallelism and a named work seam, not from the
   ~3-minute polling tick — the tick only bounded stall latency, at high
   cost. Design point: dispatch on completion (§14's fast path), and treat a
   long interval purely as a stall ceiling, not a throughput lever.
2. **Budget explicitly for a "verify the instrument" pass.** Tuning a loop
   for throughput without one quietly trades correctness for volume — one
   run propagated a wrong Loki finding two hops and built a wrong Keycloak
   diagnosis on top of it. This is the concrete, in-repo instance of
   `08-budget.md`'s warning against cheapening the verifier: the asymmetry
   is that a cheap verifier is how a loop starts passing bad work, and that
   costs more than the tokens it saved.

These are recorded here as attributed facts from this repository's own
operating history (via the supervisor brief), not measured freshly by this
distillation — no command was run to reproduce them.

## Budget — the second safety mechanism

`08-budget.md`: a loop multiplies a single task's cost (order-of-magnitude
figures the corpus cites: a chat turn ~2,000–4,000 tokens, one agent task
50,000–500,000, agent teams roughly 7× a standard session, an uncapped goal
loop up to $500/hour) by iterations by days. Set all four caps — they fail
differently:

| Cap | Catches |
|---|---|
| Iterations | Endless retry |
| Tokens | A few unexpectedly enormous turns |
| Wall clock | Hung tools, slow external systems |
| Spend | Everything else, the true backstop |

**Model routing** is the single biggest cost lever: frontier for
orchestration and non-trivial implementation, cheap for mechanical edits,
classification, and stop-condition evaluation — except the verifier, which
stays frontier when a false pass is expensive. **Context economy** is the
other budget, the one that degrades quality rather than the bill: fresh
context per iteration for long grinds, compaction, tool-output offloading,
and a **60%-of-window rule of thumb** for when to start preparing a handoff
rather than carrying bloated history.

The two numbers worth tracking per loop, corpus-sourced and inferred rather
than measured for this repo (no loop here currently emits them):
**cost per verified outcome** (dollars per merged PR / closed issue / fixed
flake — the metric that also prices the failures) and **escalation rate**
(fraction of runs ending `blocked-needs-human`; a rising rate signals scope
drift past the loop's verification).

## Run memory — what a loop leaves behind

`specs/loop-memory.md` draws a tier boundary this repository should keep:
durable *user* facts live in the memory vault
(`memory-conventions`/`agent/facts/`, per `CLAUDE.md`'s Memory section) —
*run* state does not belong there, and putting it there would swamp an index
the global rules require reading every session. Run memory instead lives in
the repo or a run directory beside it, and grows every run, unlike the vault.

Five files, each with one job — resist inventing more:

| File | Holds | Written |
|---|---|---|
| Progress / plan | Work queue and current status | Every iteration |
| Decisions | Choices made **and why** | On any non-obvious choice |
| Known failures | What has failed before, and its recognizable symptom | On every failure |
| Run receipts | Cost, terminal state, evidence, artifacts | Every run, including crashed ones |
| Handoff note | State, known issues, next action | Before compaction, model switch, or a long pause |

Two mechanics carry the actual weight: **re-inject the plan every turn** (a
plan read once at the start is gone by iteration three), and **carry an
intake watermark** so a scheduled loop does not reprocess its whole backlog
on every run — the same failure the contract's Intake field exists to catch,
recorded here as *state* rather than *design*.

Receipts are written **by the wrapper, not the agent**, so they exist even
when a run crashes or a cap fires mid-turn — this is the operational form of
this repo's own "leave a handoff a cold session could resume from"
instruction, and the corpus explicitly says so. A known-failures file that
grows to 20–50 real cases is an eval substrate in a different coat; this
repository already has one (`scripts/eval_arm.py`, `scripts/eval_score.py`,
`tests/evals/`) that a loop's known-failures file should feed rather than
duplicate.

The circuit-breaker rule belongs to run memory even though the cap itself is
a contract field: before each retry, check the ledger, and if the same
failure has repeated or the attempt cap is hit, stop and escalate rather
than retrying blind.

**Hazards**, all corpus-named and worth restating because they are easy to
skip past: staleness (a memory file records what was true when written —
verify against the repo before acting on it, matching this repo's own memory
guardrail); concurrent writes (two agents writing one file is last-write-wins
corruption — partition by owner or make writes append-only with
attribution); growth (name a prune rule per file or nobody reads it); and
secrets (state files are often committed — redact CI logs and alert payloads
before writing).

## What this repository has not adopted from the corpus, and why

The corpus's own recommendations file (`RECOMMENDATIONS.md`) argues against
several things worth naming here so this document doesn't quietly re-open
them:

- **A `/loop`-wrapper skill.** First-party mechanisms move fast across four
  harnesses that mostly don't share them; teach *choosing* between
  mechanisms (the ring table above), not wrapping one.
- **A graph-shapes skill.** The vocabulary was unsettled as of the corpus's
  writing (2026-07-27); treat it as a reference detail inside dispatch
  guidance, not a standalone concept here.
- **A Ralph skill.** Ralph's guardrails are environmental (container/VM,
  disposable branch, permission bypass), not instructional — a document
  cannot make it safe, only name when the headless ring is appropriate.
- **Auto-committing or auto-merging loops.** Already covered above; every
  corpus source and this repo's own global instructions land on human
  review before merge.

No skill implementing `loop-contract` or `loop-memory` exists in this
repository yet — the corpus's specs for both are implementation-ready but
unimplemented, and this document does not implement them; it records the
decision surface a future skill or loop design has to answer.

## Quick reference — designing a new loop here

1. Is the next action fixed regardless of state? Write a script, not a loop
   (`specs/loop-contract.md` §2).
2. Is the work already a named, tested skill? If not, name and pilot it
   manually first.
3. Answer all twelve contract fields, watermark and escalation included.
4. Write two stop conditions — goal-based and the four-cap safety
   fallback — and name the terminal states.
5. Pick the weakest mechanism from the ring table; if it is this repo's own
   supervisor/worker pattern, it must follow §14's layering, not
   reinvent one.
6. Start at L1 report-only; state the highest verification level the loop
   passes without a human, and budget a pass that verifies the instrument
   itself, not just the throughput.
7. Decide where run memory lives (the five-file set) before the first
   scheduled run, not after the first repeat failure.
