# Supervisor Disposition — Two Supervisors, One Decision

This repository contains two supervisors. One of them runs. This document is
the decide-ready material for `agent-dotfiles#16`: what each one actually is,
what each has that the other does not, whether the reasons the ledger was
rejected still hold, and what each path costs. **It does not pick a winner.**

It does reach one conclusion the framing did not anticipate, recorded in §6:
`docs/SPEC.md` §14.3 already settles these two as *layers of one design*, not
as alternatives. The decision in front of Jon is therefore narrower than
"which one", and §7 states it as three questions.

## How the figures here were produced

Every number below was produced by running a command in a disposable worktree
at `34f0cc3` (`feat(watchdog): say when the live copy is behind main (#100)`)
on 2026-08-11, or by reading a file, and is labelled **measured**. Anything
labelled **inferred** is arithmetic, a reading of code that was not executed,
or a prediction. Per `AGENTS.md`, no figure here is quoted for a set that was
not enumerated.

Read-only on behaviour, as the brief required: `cli.py tick`, `sensor`,
`assign`, `notify` and `reconstruct` were never run. `--help` and `status`
were run against a temporary `--state-dir`. The running supervisor and its
panes were not touched; its state directory and logs were read, never written.

## 1. What each one actually is, today

### 1.1 The inventory in #16 is close, and two of its rows are wrong

**Measured** (`wc -l`, this worktree):

| Group | Files | Lines |
|---|---|---:|
| Ledger, as #16 lists it | `cli.py` `core.py` `adapter.py` `sensor.py` `github_source.py` `transport.py` `acp_transport.py` `recycle.py` | 2,376 |
| Shell supervisor, as #16 lists it | `watchdog.sh` `lanes.sh` `dispatch.sh` `claim.sh` `notify.sh` `inbox.sh` `worktree.sh` `director-inbox.sh` | 1,260 |

Two corrections, both material to a decision framed as "Python versus shell":

- **`recycle.py` (239 lines) is not part of the ledger.** It imports `re`,
  `time`, `dataclasses` and `pathlib` and nothing else — no `core`, no
  `Ledger` (**measured**, `grep '^import\|^from' recycle.py`). What it parses
  is the *shell* supervisor's `brief.md` and its `## Live lanes and armed
  channels` table. It belongs to neither column cleanly, and it has no caller
  either. The ledger proper is **2,137 lines** (**inferred**: 2,376 − 239).
- **The running supervisor is not all shell.** `watchdog.sh` shells out to
  `sleepcheck.py` (152) and `watchdog_notify.py` (315) on its hot path
  (**measured**, `watchdog.sh:169,225`). The system that runs is **1,727
  lines** (**inferred**: 1,260 + 467), about a quarter of it Python.

So the axis is not language. It is *reachability*, and there are three
categories, not two.

### 1.2 Reachability, measured

**Measured** — `grep -rn "cli\.py\|from core import\|import core\|Ledger("`
across `*.sh *.md *.py *.plist *.yml *.json`, excluding `.git/`: every hit
outside `tests/supervisor/` is either `cli.py` importing its own module or two
lines of `scripts/supervisor/README.md`. Nothing dispatches through it.

**Measured** — `launchctl list | grep -Ei 'supervisor|hill90'` returns exactly
one loaded job, `com.jonhill.supervisor-watchdog`. Its plist runs
`~/.local/state/agent-dotfiles-supervisor/live/scripts/supervisor/watchdog.sh`
every `StartInterval` 180s. The two `com.hill90.codex-supervisor*` plists are
present on disk and **not loaded**.

**Measured** — the ledger's own default state directory
(`cli.py:20`, `~/.local/state/agent-dotfiles-supervisor`) contains no
`ledger.sqlite3`, `ledger.lock`, `results/`, `snapshots/`, `event-payloads/`
or `incoming/`. The ledger has never been run on this machine, not once, by
anyone.

**Measured** — `python3 scripts/supervisor/cli.py --help` now prints usage and
exits 0, listing 13 subcommands; `cli.py --state-dir <tmp> status` returns
`{"events":[],"lanes":[],"source_tasks":[],"tasks":[]}` and creates the state
tree. It is runnable, as #94 made it. It is still called by nothing.

Uncalled code is not a ledger-only phenomenon. **Measured**: `inbox.sh` (the
Telegram *inbound* half) is referenced only by its own file and its test —
`loop-tick.md`'s two hits are `director-inbox.sh`, a different tool. `recycle.py`
is referenced only by `README.md` and two docstrings. The estate's named
defect family — *a tool that fails closed when called, and nothing calls it*,
stated three times in `dispatch.sh`'s own header — has instances on both
sides of this comparison.

### 1.3 Does each one do what it says? Both drift, and one drifts further

The brief asked for this specifically, because both halves have been caught
documenting properties they lacked. Findings, all **measured** by reading the
code against its own prose:

**Ledger:**

- `scripts/supervisor/README.md:19` says state lives under
  `~/.local/state/hill90-supervisor`. `cli.py:20` uses
  `~/.local/state/agent-dotfiles-supervisor` — **the running supervisor's own
  state directory**. `Ledger.__init__` (`core.py:38-39`) unconditionally
  `chmod`s its root to `0700`; that directory is currently `0755`. Any ledger
  subcommand run without `--state-dir` writes a database into the live
  supervisor's state directory and changes its permissions. Not destructive;
  entirely unadvertised.
- The prompt the ledger sends a worker (`adapter.py:118-121`) instructs it to
  run `hill90-supervisor accept --task …` and `hill90-supervisor complete …`;
  `notify_architecture` (`adapter.py:161`) instructs `hill90-supervisor ack`.
  **Measured**: `command -v hill90-supervisor` → not on PATH. Only
  `hill90-codex-supervisor`, the retired v4 control script, exists. Every
  assignment this system could make would hand its worker an uninvokable
  command.
- `README.md:52-54` says architecture notifications are bounded to event IDs
  and result paths. They are — but there is **no cap on how many**.
  `notify_architecture` (`adapter.py:146-162`) joins every row of
  `events_due()` into one prompt with no count or byte limit. The disposition
  comment's PR 6 never landed.
- `core.py:105` still hard-codes `harness IN ('codex','claude','copilot-acp')`.
  Three values instead of two is progress; it is not the pluggable registry
  PR 7 called for.
- `core.py:1` still describes itself as "the Hill90 supervisor". It moved.

**Shell supervisor:**

- `lanes.sh`'s own header documents five states (`free busy hung dead
  unknown`). `emit_rows` produces **seven** — `supervisor` and `scrolled` are
  real, load-bearing, and undocumented in the header and in `loop-tick.md`.
- `README.md:276` names five bash suites wired into `unittest`.
  `test_shell_suites.py` globs `test_*.sh` and runs **seven** (`notify` and
  `director-inbox` are also covered). The doc undercounts what the code does —
  the harmless direction, but drift.
- `NOTIFY_SCRIPT` in the live `notify.env` points at
  `~/source/repos/Personal/agent-dotfiles/scripts/supervisor/notify.sh` — the
  *shared checkout* — while the watchdog itself runs from the pinned `live/`
  worktree. The escalation path and the watchdog can be at different commits.
  That is #99's deploy-drift with a second instance nobody has recorded.

Neither is clean. The ledger's drift is the kind that would fail on first
contact with a real task; the shell supervisor's is the kind that misleads a
reader without breaking a run.

## 2. What the ledger gives that the shell version does not

#16 names four properties. Each is audited against `34f0cc3`, together with
what the running system does instead.

| Property | Does the ledger deliver it? | What the shell supervisor does instead |
|---|---|---|
| **Durable state** | **Yes, in code.** SQLite with `journal_mode=WAL`, `synchronous=FULL`, `BEGIN IMMEDIATE` transactions, an `flock` around every mutation, a partial unique index enforcing one open task per lane (`core.py:53-134`), immutable hashed results and in-transaction completion events (`core.py:695-736`). This is genuinely better engineered than anything on the other side. | Durable state is **GitHub plus the filesystem**: the claim is the issue assignee (`claim.sh`, survives total local loss), the lane's identity is the tmux window name, the work lives in a git worktree, and the supervisor's context lives in `brief.md`. In-flight dispatch state is **not** durable — a supervisor restart mid-dispatch leaves a claim and a worktree with nothing tracking them. `claim.sh stale` exists to find exactly that wreckage, and reports rather than repairs. |
| **Event-driven dispatch** | **No.** There is no `wait-for` anywhere in the ledger (**measured**, `grep -rn "wait-for" scripts/supervisor/*.py` — no hits). `tick` polls: it captures 25 lines of pane and classifies them (`adapter.py:133-138`). That is a poll on a timer, the same shape as the mechanism `docs/SPEC.md` §14 warns about. | The loop's fast path is a **backgrounded `tmux wait-for`** (`loop-tick.md:45`), which is genuinely event-driven for the *signal*. SPEC §14.2 L4 already records that the payload still has to be scraped from scrollback. `lanes.sh:88` also polls a pane's last line before every dispatch. Neither system is event-driven end to end; the shell one is closer. |
| **Unambiguous delivery** | **Yes, and this is its strongest single contribution.** `delivery_pending` is written *before* the physical send (`adapter.py:129-131`), a task in that state cannot be auto-resent (`adapter.py:98-102`), and the only ways out are a confirmed `mark_delivered` or a human `reconcile` authenticated by the task's own recorded `pane_nonce` rather than the lane's current one (`core.py:594-639`). Nothing infers delivery from echoed text. | `dispatch.sh:191-214` types the brief, **reads the pane back**, and only sends `Enter` when both the head of the message and the worktree path are visible; one retype, then abort and roll back. That is a different guarantee — it verifies the *content* landed, which the ledger never does — but it has no persistent record, so a crash between send and verification leaves nothing behind at all. |
| **Multi-harness support** | **Partly.** Three harnesses in a hardcoded CHECK constraint, and a real ACP adapter (`acp_transport.py`) that returns a structured `stopReason` and token usage — the one place in the estate where completion is not scraped from a terminal. But `classify_capture` raises on any harness that is not `codex` or `claude` (`adapter.py:35-36`), and the ACP path has never been run against a live agent from this repository. | `lanes.sh` refuses to guess: a non-Claude pane is reported `unknown` and withheld, with the reasoning that a wrong probe produced a false `hung` on a healthy Copilot lane. Honest, and narrower — one harness supported, the rest named as unsupported. |

Two of the four are real and the ledger genuinely owns them. One is claimed
and absent. One is half-built.

### 2.1 The gate that makes all of it unreachable

`Ledger.assign()` refuses any task without a reconstructed, open
`source_tasks` row (`core.py:532-538`). That row can only come from
`GithubTaskSource.reconstruct`, which requires the issue body to contain
**exactly one** `<!-- hill90-supervisor:v1 {…} -->` task marker whose
`source_url`, `source_ref` and `task_id` all match, with `source_ref` a full
commit SHA that GitHub resolves (`github_source.py:132-152`).

**Measured**, across all four repos, `--state all --limit 300`:

| Repo | Issues carrying a `hill90-supervisor:v1` marker |
|---|---:|
| `agent-dotfiles` | 0 |
| `skills` | 0 |
| `skills-private` | 0 |
| `agent-evals` | 0 |

**Zero.** As the code stands, there is no issue in the estate the ledger could
be asked to dispatch. Fixing rejection reason 1 so thoroughly is what made the
system unusable without a hand-authored marker in every issue body. This is
the single most decision-relevant fact in this document, and it is not
mentioned anywhere in #16.

## 3. What the shell version has that the ledger does not

**Operating evidence.** The shell supervisor has been hit by real failures and
carries the fix for each in tested code. The ledger has never run, so it has
never been hit by anything.

Merged into `main` in the last day (**measured**, `git log` and `gh`):

| PR | What it fixed |
|---|---|
| #93 | An escalation was marked notified when the *send* had failed — the loop could be down with nobody told. |
| #96 | A dispatch with no `[repo]` argument shifted the lane name into the repo slot, so `claim.sh` ran `gh issue view 95 -R claim-refuses-closed` and every dispatch aborted, indistinguishably from a legitimate refusal. |
| #97 | `claim.sh take` accepted a closed issue. |
| #100 | The watchdog's status line reported a sha without saying how far behind `main` the pinned live copy was. |

Each is a defect that only exists once something runs. Behind them sit #73
(shared-checkout corruption: one lane's four files discarded, another's commit
silently carrying a deletion), #28-dispatched-twice (about an hour of lane work
spent twice), #65 (a capture window six lines too wide reported live lanes
`hung`), #85/#88 (a plain message into the supervisor's pane silently ends the
loop), and #89 (`DISPATCH_LANE=t:1` put a worker brief into the supervisor's
own pane at exit 0).

**Measured, from the live state directory:** `watchdog.log` spans
`04:15:00Z` to now in 44 lines, containing 12 `RESTARTED` and 13 `ESCALATE`
records. `watchdog.status` currently reads `state: asleep`, `code: main @
34f0cc3`. That file is the loop's own account of itself and it is accurate.

**What that is worth, plainly.** Every one of those defects was invisible to
review and to tests, and became visible only under load. The ledger's 81 tests
(**measured**, per file: core 28, adapter 14, cli 11, github_source 9, sensor 4,
transport 1, acp_transport 14) are good tests of a design nothing has stressed.
The shell path's 180 stub-driven bash assertions (**measured**: claim 29,
director-inbox 26, dispatch 61, lanes 15, notify 7, watchdog 26, worktree 16,
all passing) mostly encode incidents that actually happened. Those are not the
same kind of evidence and should not be traded at par.

The concrete instance, **measured this session** by calling the pure function
`adapter.classify_capture` directly (no tmux involved):

| Pane content (last lines) | `classify_capture("claude", …)` |
|---|---|
| `❯ ` after ordinary output | `idle` |
| a lane quoting `Should I proceed?` while reading `loop-tick.md`, then `❯ ` | **`approval`** |
| a lane quoting *"the run hit your weekly limit"* from a PR body, then `❯ ` | **`blocked`** |
| `✻ Thinking… (12s · esc to interrupt)` | `active` |

Rows two and three are wrong, and they are wrong in the exact way `lanes.sh`
was wrong in #65 — matching on a phrase anywhere in a wide capture window
rather than on the live status line. `lanes.sh:80-88` paid for that lesson and
now reads only the last non-empty line. `adapter.py` never did, because nothing
ever ran it. The consequences if it were run: `assign_task` refuses to dispatch
to a perfectly healthy lane (`adapter.py:104-105`), and `observe_lane` writes a
durable `attention:<task>:approval` event which `Ledger.ack` then refuses to
acknowledge until the task reaches a terminal status (`core.py:825-828`).

The shell supervisor also owns four concepts the ledger has no equivalent for
at all: **lane health beyond busy/idle** (`dead`, `hung`, `scrolled`, `unknown`),
**worktree isolation** per dispatch, **claim-before-dispatch**, and the
**`free-N` naming rule** that separates "idle" from "unowned". Each exists
because its absence cost something.

## 4. The eight rejection reasons, re-checked at `34f0cc3`

The #16 body's reasons are why the ledger was rejected. All eight were checked
against the code as it stands. Statuses are **measured by reading the cited
lines**; nothing in this section was executed.

| # | Reason | Status | Evidence |
|---|---|---|---|
| 1 | SQLite as task authority | **Fixed — and now over-tight** | `core.py:532-538` refuses assignment without an open, reconstructed `source_tasks` row. See §2.1: zero issues in the estate can satisfy it. |
| 2 | Ambiguous delivery / resend | **Fixed** | `mark_delivery_pending` before the send (`adapter.py:129-131`, `core.py:579-592`); resend guard (`adapter.py:98-102`); human `reconcile` keyed on the task's own nonce (`core.py:594-639`), exposed at `cli.py:149-160`. |
| 3 | Unsafe re-registration / completion ownership | **Fixed** | `register_lane` refuses a changed identity while a non-`delivery_pending` task is outstanding (`core.py:359-394`); `complete` requires the task's recorded `pane_nonce`, checked twice (`core.py:702, 711`); `_transition` checks it for every other move (`core.py:566-567`). |
| 4 | Attention states not durable | **Fixed in mechanism, undermined by its input** | `observe_attention` writes `attention:<task>` / `attention:<task>:<reason>` (`core.py:738-772`), and `adapter.observe_lane` calls it for every non-active state (`adapter.py:133-138`). But the reason it records comes from the classifier audited in §3, which invents `approval` and `blocked` from quoted text — and such an event cannot be acked until the task is terminal (`core.py:825-828`). |
| 5 | Sensor recovery absorbing changes | **Fixed** | `record_component` retains the prior `snapshot_sha256` across an unhealthy collection (`core.py:842`); the on-disk baseline is only replaced after a successful diff (`core.py:927`); `collect_all` reports `recoveries` separately (`sensor.py:78-79`). |
| 6 | Service timeouts and drain incomplete | **Timeouts fixed; drain has no owner** | Bounded: git/gh 30s (`sensor.py:14`), tmux 10s (`transport.py:9`), ACP 30s (`acp_transport.py:27`). Drain belonged to Hill90's `service.sh`, which did not move here (`README.md:282-291`). The ledger has no service, no start/stop, and nothing to drain — the finding is not closed, it is unowned. |
| 7 | Rollback without reconciliation | **Not applicable here; the property exists elsewhere** | There is no v4/v5 cutover in this repository, so the original finding has no target. Note where the property *does* live: `dispatch.sh:138-215` releases the claim and removes the worktree on every failure path, so a failed dispatch leaves the estate as it found it — 61 passing assertions in `test_dispatch.sh`. The shell path has the rollback discipline; the ledger never needed it because it never acts. |
| 8 | Runtime hardening and the GitHub spool | **Spool fixed; hardening split and partly landed** | `reconstruct` exists and gates assignment (`github_source.py:195-198`, `core.py:532`). CI hardening landed: `test_shell_suites.py` runs all seven bash suites under the repo-wide `unittest discover`. `publish_status` (`github_source.py:200`) has **no caller outside its own test** (**measured**) — the receipt half of "GitHub is the record" is implemented and never written *to*. |

**Net: none of the eight is still true as originally stated.** Six are fixed,
one is unowned, one does not apply. That is a real answer to the question #16
has been carrying, and it is not the answer the issue's framing expects.

Three findings that are *not* in the original eight, all still open, all
**measured** in §1.3: the unbounded architecture prompt, the still-hardcoded
harness enum, and the worker prompt that names a binary which does not exist.
Plus the two that matter more than any of them: **the classifier is wrong in a
way already paid for on the other side (§3), and no issue in the estate can
pass the assignment gate (§2.1).**

## 5. What each path costs

### A. Keep the shell supervisor; delete the ledger

- **Loses:** 2,137 lines and 81 passing tests, including the two properties
  the ledger genuinely owns — non-resendable ambiguous delivery, and
  ownership-safe completion — plus the only ACP transport in the estate.
- **Requires:** amending every canonical citation of "the ledger" as the
  durability layer, not just one. That is at least four locations: `docs/SPEC.md`
  §14.3, which names "the v5 ledger" as the layer that addresses L2 and L4;
  `docs/SPEC.md` §15, which independently and canonically asserts "the
  portable core owns the ledger, ownership-safe transitions, assignment
  gating, and attention"; `docs/PRD.md`'s ACP boundary row, which cites §15
  while restating that same claim; and `docs/loop-engineering.md`, which
  cites both §14 and §15 and additionally names "the v5 ledger" directly as
  part of the estate's durability story (lines 37-39, 43, 137). Deleting the
  ledger without amending all four leaves canonical docs describing a
  component that does not exist. **This is the hidden cost of the delete
  path** and it is not optional — closer to a small doc-consistency pass
  across two SPEC sections and two downstream documents than to amending one
  section.
- **Gains:** the estate's largest instance of its own named defect family
  disappears, and `scripts/supervisor/` starts describing only what runs.
- **Guardrail:** `AGENTS.md` and `safe-deletion` both require looking before
  deleting. §4 is that look, and it says the code is better than its
  reputation — so this path is a decision to discard *working* code, not
  cleanup. It should be recorded as such.

### B. Adopt the ledger; retire the shell path

Everything below is **inferred** from reading the code; none of it was
attempted.

- **Documentation-amendment cost, checked for the same defect as path A:
  none found.** `docs/SPEC.md`, `docs/PRD.md` and `docs/loop-engineering.md`
  never name any of the eight shell-supervisor files (`watchdog.sh`
  `lanes.sh` `dispatch.sh` `claim.sh` `notify.sh` `inbox.sh` `worktree.sh`
  `director-inbox.sh`) or the phrase "shell supervisor" (**measured**,
  `grep -n -i "watchdog\|dispatch.sh\|lanes.sh\|claim.sh\|shell supervisor"
  docs/SPEC.md docs/PRD.md docs/loop-engineering.md` — no hits). The
  cooperative `tmux wait-for` mechanism SPEC §14.1 and §14.3's fast-path row
  describe lives in `scripts/supervisor/lane-done.sh`, which is neither one
  of the eight nor the ledger's (**measured**, `grep -rln "wait-for"
  scripts/supervisor/*.sh` → only `lane-done.sh`; §2 already establishes the
  ledger has none). Retiring the shell path therefore does not leave any
  canonical doc describing a component that no longer exists, unlike
  deleting the ledger.
- A `hill90-supervisor`-equivalent entry point has to exist, be installed, and
  be named something this repository owns.
- Every dispatchable issue needs a hand-authored marker in its body, or the
  gate has to be relaxed to accept the assignee-as-claim that already works.
  Today: 0 of the estate's issues qualify (**measured**).
- `classify_capture` has to be rebuilt to `lanes.sh`'s standard, or the system
  will refuse healthy lanes and raise unackable attention events.
- The four concepts the ledger has no equivalent for — lane health beyond
  busy/idle, worktree isolation, claim-before-dispatch, `free-N` ownership —
  would have to be reimplemented inside it, each one re-earning an incident
  that has already been paid for once.
- A scheduler has to drive it, and SPEC §14.3 prohibits cron as the mechanism.
- **This is not a port. It is rewriting the shell supervisor inside the
  ledger, and starting over on the operating evidence.**

### C. Compose them, per SPEC §14.3

- The seam already exists in shape: `dispatch.sh` knows the issue, the lane,
  the worktree and the brief at the moment it sends. Wrapping its send in
  `mark_delivery_pending` / `mark_delivered`, and having the lane call
  `complete`, is the "durability and payload" layer §14.3 names.
- **Requires giving something up:** the ledger currently wants to own
  assignment, pane binding and the send itself (`adapter.assign_task`). As a
  durability layer it must own none of those. That is a real refactor of
  `adapter.py`, and the marker requirement in §2.1 has to go or be replaced.
- **Risk, stated plainly:** this is how a third half-built thing gets made.
  It should not start without a named end state and a failing test.

### D. Keep both — the status quo, which is not free

- **Not the cost:** CI time. The ledger's seven test files run 81 tests in
  **1.11s** (**measured**, run directly) inside a 39.2s, 399-test suite
  (**measured**, `python3 -m unittest discover -s tests` → `Ran 399 tests`,
  `OK`).
- **The actual costs:** every reviewer and every future agent reads
  `scripts/supervisor/` and finds a documented, tested, plausible supervisor
  that has never run — the README's Contract section reads as an operating
  description of this estate and is a description of nothing. The default
  state directory collides with the live supervisor's (§1.3). And the estate's
  own most-cited defect — *"a tool that fails closed when called, and nothing
  calls it"* — sits at its largest scale inside the very directory whose
  `dispatch.sh` header names it three times.
- Status quo is the only option with no end state. It is the one that has been
  chosen by default for a month.

## 6. The question in #16 is half malformed, and the SPEC already says so

#16's latest comment frames this as *"we have two, which one do we keep."*
That framing treats them as substitutes. `docs/SPEC.md` §14.3 — settled
2026-08-10, and canonical over any issue per `AGENTS.md` — already treats them
as **layers of one mechanism**:

| §14.3 layer | Mechanism | Where it lives today |
|---|---|---|
| Fast path | backgrounded cooperative `wait-for` | `loop-tick.md:45` — shell path |
| Failure path | Stop hooks / `herdr agent wait` | nowhere; `herdr` is #24, still gated on Jon |
| Durability and payload | **the v5 ledger** | `scripts/supervisor/core.py` — unreachable |
| Backstop only | cron as a dead-man stall detector | `watchdog.sh` + the LaunchAgent — shell path |

Read that way, the shell supervisor is the fast path and the backstop; the
ledger is the durability layer; and the estate is missing the failure path and
the seam between the layers. They are not competing for a slot. **Nothing in
either codebase connects them, and that missing seam is the actual defect.**

Where the framing *is* sound: the ledger as written does not behave like a
durability layer. It wants to own assignment gating, pane identity and the
physical send — that overlap with `dispatch.sh` is genuine duplication and a
genuine choice. So the honest form of the question is not "which one do we
keep" but "does the ledger become the durability layer §14.3 already promises,
or does §14.3 get amended to say this estate will not have one?"

Either answer is legitimate. Answering neither is what the status quo does.

## 7. What a decision has to say

Three questions. The first is the decision; the other two follow from it and
are cheap to get wrong silently.

1. **Does `docs/SPEC.md` §14.3's "durability and payload" layer survive?**
   If yes, path C, and the ledger's assignment/pane/send ownership has to be
   given up. If no, path A, and §14.3 is amended in the same change — a delete
   that leaves the SPEC describing a missing component is worse than either
   outcome.
2. **If anything survives, what replaces the marker gate (§2.1)?** The
   assignee-as-claim in `claim.sh` already works, survives total local loss,
   and satisfies the same contract clause. The v1 marker satisfies it too and
   requires hand-editing every issue body. These are alternatives; only one
   should stay.
3. **Whatever survives gets a caller in the same change.** The estate has now
   produced this defect four times (`acp_transport.py`, `claim.sh`,
   `worktree.sh`, and the ledger). Merging a durability layer with no caller
   would be the fifth, and the largest.

Not in scope for the decision, but should not be lost: the classifier defect
(§3) and the non-existent `hill90-supervisor` binary (§1.3) are bugs in code
that is on `main` today, whichever path is chosen. If the ledger is deleted
they go with it. If it is kept in any form, they are the first two things to
fix, before anything is wired to anything.
