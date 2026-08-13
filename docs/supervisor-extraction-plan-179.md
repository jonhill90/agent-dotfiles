# Supervisor Extraction Plan — #179

> **Superseded.** The extraction this document planned landed in the
> Phase 1.5 split PR: `scripts/supervisor/` and `tests/supervisor/` were
> removed from this repository and now live in `jonhill90/agent-supervisor`
> (private). File paths and line counts below describe the tree as it stood
> before that removal — kept as the measured record the split PR relied on,
> not as a description of this repository's current state.

This is a plan and a measurement, not an extraction. Per Jon's own framing
in #179 and the brief that produced this document, the extraction does not
happen now — lanes are running on this code as this is written. What
follows is (1) a fresh, enumerated coupling inventory, superseding the one
already in the #179 issue body, and (2) a sequencing plan for whenever the
work is picked up.

All figures below are **measured** in this worktree on 2026-08-12 against
the tree at `main` = `b51cf71` (the merge of #232, this document's base),
by running the command shown, unless marked **inferred**.

This document has now been re-measured twice for the same reason, which is
itself the finding. Its first revision measured `d4ae64d` and was committed
sixteen minutes after #228 merged, so it narrated a `main` that had already
moved (36 files / 11,508 lines against a real 37 / 11,698). Its second
measured `32e8eab` and four more supervisor PRs landed before it could be
reviewed — #225 (`0b9f39d`), #229 (`2c4db5d`), #231 (`08b0d00`) and #232
(`b51cf71`), which between them added 2,340 lines and a whole
`laneview/` subtree. Every figure below has been re-run against `b51cf71`
and every one that moved is named as changed rather than silently replaced
(see "Corrections" at the end).

**The tree moves faster than a document about it can be reviewed.** That is
a measurement, not an excuse: all three revisions were written on
2026-08-12, and within that single day `scripts/supervisor/` grew from
11,508 to 12,414 lines — 7.9%. Any consumer should
re-run §1's and §4's commands rather than quoting these numbers — which is
why §4 now *derives* its total from its own list instead of stating one.

**Citations name files, functions, and variables — never line numbers.**
#223 shipped a comment citing its own callers at line numbers that were
already wrong in the diff that introduced them. Line numbers in a document
that outlives one merge are a defect, not a convenience.

## 0. The #179 issue body already contains a coupling inventory. It is stale.

The issue body states: *"7,258 lines across `scripts/supervisor/`, plus 30
files in `tests/supervisor/`"* and *"every default is env-overridable."*
Both are wrong against the code on `main` right now:

| Claim in issue body | Re-measured here | Command |
|---|---|---|
| 7,258 lines, `scripts/supervisor/` | **12,414** | `cat $(find scripts/supervisor -type f) \| wc -l` |
| 30 files, `tests/supervisor/` | **43** | `find tests/supervisor -type f \| wc -l` |
| "every default is env-overridable" | **False** — see §3 | `grep -rn 'agent-dotfiles-supervisor' scripts/supervisor/` |

This is not a criticism of whoever wrote the issue body — it is the exact
failure mode `AGENTS.md`'s "Recording Figures" section names: a number that
reads as measured but wasn't re-verified against current `main`. The
inventory below replaces it.

## 1. Size, enumerated

`scripts/supervisor/` — **41 files, 12,414 lines**, enumerated by
`find scripts/supervisor -type f`:

- **24 shell**: `advance-live.sh`, `bootstrap-session.sh`, `claim.sh`,
  `digest.sh`, `director-inbox.sh`, `director-route.sh`, `dispatch.sh`,
  `harness-registry.sh`, `inbox-poll.sh`, `inbox-route.sh`, `inbox.sh`,
  `input-box.sh`, `lane-done.sh`, `lanes.sh`, `laneview.sh`, `notify.sh`,
  `watchdog.sh`, `worktree.sh`, `would-revert.sh`, plus `harness/claude.sh`,
  `harness/codex.sh`, `harness/copilot.sh`, `laneview/opensessions.sh`,
  `laneview/text.sh` — 5,608 lines.
- **14 Python**: `acp_transport.py`, `adapter.py`, `cli.py`, `core.py`,
  `github_source.py`, `mcp_server.py`, `recycle.py`,
  `refresh_brief_resume.py`, `sensor.py`, `sleepcheck.py`,
  `supervisor_view.py`, `transport.py`, `verdict.py`, `watchdog_notify.py`
  — 5,529 lines.
- **3 Markdown**: `README.md`, `loop-tick.md`, `laneview/README.md` — 1,277
  lines.

Two of these arrived after this document's previous revision and were
checked for outward coupling along every axis §2 and §3 use:

- `harness-registry.sh` (#228) lifted the harness-adapter loader out of
  `lanes.sh` so `watchdog.sh` could ask the same adapters whether a pane is
  busy. No `/Users/jon`, no `../..`, no cross-tree source.
- The `laneview/` subtree (#231, closing #178) — `laneview.sh` plus
  `laneview/opensessions.sh`, `laneview/text.sh` and `laneview/README.md`,
  **350 lines** — is a renderer layer that takes state only through
  `lanes.sh --json`. It reaches outward exactly once, to
  `http://127.0.0.1:${OS_PORT:-39104}`: a localhost daemon, not a path into
  this repository. It is the one addition since the last revision that
  changed anything outside the tree, and what it changed is
  `scripts/validate_repository.py` — see §4 and §5.

Both add volume to the moving tree. Neither adds a path dependency on
`agent-dotfiles`.

`tests/supervisor/` — **43 files, 15,013 lines**:

- **19 shell suites** (`test_advance_live.sh` … `test_would_revert.sh`),
  `test_laneview.sh` being the newest.
- **15 Python test modules** (`test*.py`, the pattern `unittest discover`
  collects) plus `__init__.py` — 16 `.py` files total. §5 and §10 below say
  *fifteen* where an earlier revision said sixteen: `__init__.py` is not a
  test module and `discover` does not collect it.
- **8 executable stub fixtures** under `stubs/` with no extension:
  `curl-opensessions`, `gh`, `gh-claim`, `ps-lanes`, `tmux`,
  `tmux-dispatch`, `tmux-lane-done`, `tmux-lanes`.

An earlier draft of this document reported "23 shell, 9 Python" for
`scripts/supervisor/` and "20 shell test suites, 14 Python test modules"
for `tests/supervisor/`. Both were wrong — "23 shell, 9 Python" sums to 32,
which was not the tree's total at that commit (36) and is not its total now
(41). The lists above were produced by enumerating
the tree, which is what `AGENTS.md` requires and what the earlier draft
skipped.

## 1.1 "The supervisor" is two systems sharing a directory, and only one of them runs

`docs/supervisor-disposition.md` (written for #16) measured this and the
shape still holds: `scripts/supervisor/` contains a **shell supervisor**
that actually runs and a **ledger** that has never been run on this
machine. Its *line figures*, however, were measured at an older commit and
do not hold; re-measured here with `wc -l` over each named set:

| Set | Files | Lines (measured here) | `supervisor-disposition.md`'s figure |
|---|---|---|---|
| Shell supervisor | `watchdog.sh`, `lanes.sh`, `dispatch.sh`, `claim.sh`, `notify.sh`, `inbox.sh`, `worktree.sh`, `director-inbox.sh`, `sleepcheck.py`, `watchdog_notify.py` | **3,523** | 1,727 |
| Ledger | `cli.py`, `core.py`, `adapter.py`, `sensor.py`, `github_source.py`, `transport.py`, `acp_transport.py` | **3,359** | 2,137 |

The remaining **5,532** lines — arithmetic on the two measured subtotals
against the 12,414 total, not a third measurement — are the other shell
scripts (including `harness-registry.sh` and the `laneview/` subtree), the
other Python modules, `README.md`, and `loop-tick.md`.

That the ledger has never run (no `ledger.sqlite3`, no lock file, no
results directory under its default state path) is **inferred current**
from `supervisor-disposition.md`, not re-measured this session.

This is a real scope question for #179 that "measure the coupling" doesn't
answer by itself: **extraction of "the supervisor" could mean the 3,523
running lines, the full 6,882, or a decision to leave the never-called
ledger behind (or delete it) rather than pay to port dead code.**
`docs/SPEC.md` §14.3 frames these as layers of one design rather than
alternatives, and `docs/supervisor-disposition.md` poses the composition
question directly — #16 is still open. This plan does not resolve #16; it
names the dependency: **extraction scope should wait on whatever #16
decides**, or explicitly carry the ledger along as inert code with that
caveat stated in the new repo's own README, the way `recycle.py`'s orphan
status is already stated in this one.

## 2. Imports from outside the tree: zero, confirmed by reading every import statement

`grep -nE '^(import|from) ' scripts/supervisor/*.py` was read in full (not
sampled). Every non-stdlib import resolves to a sibling module in the same
directory: `cli.py` imports `acp_transport`, `adapter`, `core`,
`github_source`, `sensor`, `transport`; `mcp_server.py` imports
`supervisor_view`; `verdict.py` imports `core`. No file imports from
`scripts/` above it, from `tests/`, or from anywhere else in the repo.
Shell scripts that `source` another file (`dispatch.sh`,
`director-route.sh`, `inbox-route.sh`, `lanes.sh`) all source
`input-box.sh` from the same directory via `$HERE`, and `laneview.sh`
resolves both its renderer and `lanes.sh` the same way. No `../..`
traversal exists anywhere under the tree
(`grep -rn '\.\./\.\.' scripts/supervisor/` — zero hits).

Re-run against `b51cf71` after #225, #229, #231 and #232: unchanged. The
`laneview/` subtree added no import and no traversal; its only outward
reach is an HTTP call to a localhost port (§1).

## 3. Hardcoded paths, and three competing env-var names

The issue body names two hardcodes. There are **three**, and the
"every default is env-overridable" claim fails on a fourth axis as well.

**Hardcoded absolute paths:**

1. **`cli.py`** — `DEFAULT_REPOSITORIES`, four absolute
   `/Users/jon/source/repos/Personal/...` paths. The only `/Users/jon` in
   `scripts/` outside `README.md`'s Hill90 examples.
2. **`sleepcheck.py`** — `DEFAULT_PROJECT_DIR`, hardcoding
   `~/.claude/projects/-Users-jon-source-repos-Personal-agent-dotfiles`.
   Unlike #1 and #3 this one **is** overridable: the caller reads
   `SLEEPCHECK_DIR` first and falls back to the literal only when that is
   unset. It is on this list because the fallback bakes in both this
   machine's home directory and this repository's path, which is what a
   new repo would inherit — not because there is no escape hatch.
3. **`notify.sh`** — assigns `STATE="$HOME/.local/state/agent-dotfiles-supervisor"`
   as a bare literal with **no env override at all**. It is the only one
   of the three with no escape hatch, and unlike every other shell caller
   it ignores `SUPERVISOR_STATE`.

**Three different environment variables name the same state directory** —
a portability hazard in its own right, since setting one does not move the
others:

| Variable | Read by |
|---|---|
| `SUPERVISOR_STATE` | `advance-live.sh`, `digest.sh`, `director-inbox.sh`, `inbox-poll.sh`, `inbox.sh`, `watchdog.sh` |
| `AGENT_SUPERVISOR_STATE_DIR` | `cli.py`, `supervisor_view.py` |
| `SUPERVISOR_STATE_DIR` | `watchdog_notify.py` |
| *(none)* | `notify.sh` (bare literal, above); `refresh_brief_resume.py`'s `--brief` default, which is flag-overridable but not env-overridable; two operator-facing message strings in `watchdog_notify.py` that embed the literal path for a human to paste |

An earlier draft of this document listed `cli.py` and `watchdog_notify.py`
among the callers reading `${SUPERVISOR_STATE:-...}`. They do not — they
read the two other variable names above. Consolidating these to one name is
cheap now and is work the extraction should not inherit.

**Session naming** (`LANES_SESSION`, default `"agent-dotfiles"`) is
env-overridable in the ten scripts that read the variable
(`advance-live.sh`, `bootstrap-session.sh`, `claim.sh`, `digest.sh`,
`director-route.sh`, `dispatch.sh`, `inbox-poll.sh`, `inbox-route.sh`,
`lane-done.sh`, `lanes.sh`) — there it is a *default value*, not a
hardcode. But the default string is this repo's own name, which is itself a
coupling if the tool moves and inherits a session named after the repo it
left.

`laneview.sh` (#231) is the **eleventh** writer of that default string and
the one exception: it takes the session as a positional argument,
`SESSION="${2:-agent-dotfiles}"`, and never consults `LANES_SESSION`.
Exporting `LANES_SESSION` moves ten scripts and leaves the viewer pointed
at a session named after this repository. This is the same defect class as
the three env-var names above — one concept, more than one name for it —
arriving in code that landed after the previous revision of this document
was written.

## 4. References from outside `scripts/supervisor/` and `tests/supervisor/`

**This section has been wrong three times, always the same way: the list
and the number were produced separately, so they could disagree.** One
revision printed "six files" over a list of seven. The next printed seven
over a list that omitted `AGENTS.md`. Neither author was careless — the
structure permitted it, because a human typed the total.

So the total is no longer typed. **The command below emits the list
numbered, and the last line number *is* the count.** A wrong total now
requires the list itself to be wrong, which is a defect a reader can see
rather than one they must recompute.

### 4.1 The derivation

Three instruments, run over the union, because a coupling can be written
three different ways and no one grep sees all three.

- **Instrument 1 — the path.** `scripts/supervisor`, `scripts.supervisor`,
  `tests/supervisor`, `tests.supervisor`. Finds anything that spells a
  directory out. Both trees are swept, not just `scripts/`: half the
  moving code is tests, and an earlier revision's version of this
  instrument searched only `scripts/supervisor`. That is one of the two
  reasons `AGENTS.md` was missed: its only literal path is
  `tests/supervisor/`, and no revision before this one ran a systematic
  basename grep that would have caught it the other way.
- **Instrument 2 — any filename in the moving tree.** Some couplings never
  write a path. `scripts/validate_repository.py` builds it as a `Path`
  join of the segments `"scripts"`, `"supervisor"` and `"lanes.sh"`, so no
  grep for the joined string can ever match it, and `AGENTS.md` cites
  `dispatch.sh`, `cli.py`, `lane-done.sh`, `claim.sh`, `loop-tick.md` and
  `test_lane_done.sh` by filename alone. The name set is generated from
  the two trees, not hand-listed.
- **Instrument 3 — the word `supervisor`, case-insensitive, anywhere.**
  The backstop. It catches prose that names neither a path nor a file, and
  it is the only instrument that finds `scripts/sync.py`. Its job is to
  make the adjudication list *complete*: everything it returns is either a
  coupling or is excluded below by name, so nothing is left unexamined.

Run in this worktree against `main` = `b51cf71`:

```sh
OUT="':!scripts/supervisor' ':!tests/supervisor' ':!docs/supervisor-extraction-plan-179.md'"
NAMES=$(git ls-files scripts/supervisor tests/supervisor | xargs -n1 basename \
        | grep '\.' | grep -vx -e README.md -e __init__.py | sort -u \
        | sed 's/^/-e /' | tr '\n' ' ')
{ eval "git grep -l -e 'scripts/supervisor' -e 'scripts\.supervisor' \
                    -e 'tests/supervisor'   -e 'tests\.supervisor'   -- $OUT"   # 1: the path
  eval "git grep -lF $NAMES -- $OUT"                                            # 2: any filename in the tree
  eval "git grep -il supervisor -- $OUT"                                        # 3: the word, anywhere
} | sort -u | grep -vE \
  '^(apm\.yml|scripts/sync\.py|tests/test_sync\.py|docs/research/|docs/(PRD|SPEC|loop-engineering|provenance-manifest|docs-layout-council-138)\.md$)' \
  | cat -n
```

Output, pasted:

```
     1	AGENTS.md
     2	docs/hierarchy-naming-57.md
     3	docs/loop-signals.md
     4	docs/supervisor-disposition.md
     5	docs/work-tracking.md
     6	scripts/validate_repository.py
     7	settings/mcp/servers.json
     8	tests/test_validate_repository.py
```

**Eight coupled files.** The number is the last line of the list because
`cat -n` put it there.

Notes on the command, so it can be audited rather than trusted:

- The name set comes from `git ls-files`, not `find`, so it is the index
  and not whatever the working tree happens to hold — `find` sweeps in
  untracked `__pycache__/*.pyc` basenames, which match nothing but make
  the "generated from the tree" claim depend on a clean checkout.
- Three basenames are dropped from the set as too generic to carry signal:
  `README.md`, `__init__.py`, and the eight extensionless stub fixtures
  under `tests/supervisor/stubs/` (`gh`, `tmux`, `ps-lanes`, …), which the
  `grep '\.'` removes. Grepping the repository for `gh` or `tmux` returns
  prose, not couplings. All are inside the moving tree and travel with it
  under §7 regardless.
- `git grep` searches tracked files only. `CLAUDE.md` and
  `.github/copilot-instructions.md` are committed **symlinks** to
  `AGENTS.md` (`ls -l`), so the one file is listed once, not three times.
  All three names break together when `AGENTS.md`'s citations go stale.
- Everything in the `grep -vE` is a match this section adjudicates as
  **not** a coupling. They are excluded *inside the command* so the
  exclusion is part of the derivation and cannot be silently forgotten.
  The criterion is uniform: **would this file need editing, or break, if
  `scripts/supervisor/` and `tests/supervisor/` moved to another
  repository?**

| Excluded | Found by | Why it is not a coupling |
|---|---|---|
| `apm.yml` | 2 (`lanes.sh`) | A dated pin-bump comment (2026-08-12, #220) explaining why the `jonhill90/skills` ref moved: the old pin predated the `SKILL.md` that documents `lanes.sh`'s states. It **documents** the coupling in `validate_lane_state_docs` rather than being one. Listed rather than dropped, because an earlier revision's flat claim "`apm.yml`: zero references" came from the path grep alone and is false under instrument 2. |
| `scripts/sync.py` | 3 only | One comment, *"A stdio server (agent-dotfiles#198's supervisor server is the…"*, justifying the codex stdio-rendering branch. It names no path and no filename, so instruments 1 and 2 both miss it — which is why instrument 3 exists. It reads `settings/mcp/servers.json` generically and would behave identically if that entry pointed anywhere else. |
| `tests/test_sync.py` | 2 (`mcp_server.py`), 3 | A synthetic fixture path, `/x/mcp_server.py`, and a fixture server named `"supervisor"`, in a test of MCP-fragment merging. It models `servers.json`'s *shape*; it does not reference this tree. |
| `docs/SPEC.md` | 2, 3 | The instrument-2 hit is a substring false positive — `eval_score.py` contains `core.py`. The instrument-3 hits are real and substantial: §14, *"Supervisor/Worker Loop Mechanism (settled 2026-08-10)"*, is the governing design section for the thing being extracted. It is excluded because it describes the supervisor as a *design*, naming no file and no path, so a move leaves every sentence in it true. **That it is not a coupling does not make it irrelevant** — §11 now carries the question of where the design spec lives after a split, which this measurement cannot settle. |
| `docs/loop-engineering.md` | 2, 3 | Same shape: `core.py` inside `eval_score.py` is a false positive, and nine real prose mentions (*"§14's supervisor/worker loop, which is this repo's own"*) reference SPEC §14's design, not the tree. |
| `docs/provenance-manifest.md` | 2 (`dispatch.sh`), 3 | A dated 2026-08-11 ledger row citing *"`dispatch.sh`'s six code instances"* as an analogy for a past defect class. `AGENTS.md` makes the manifest a decision ledger; a move does not edit history. |
| `docs/PRD.md`, `docs/docs-layout-council-138.md`, and the nine transcripts under `docs/research/docs-layout-council-138/` | 3 only | Concept-level mentions. The transcripts are frozen eval fixtures — rewriting them would destroy the evidence they exist to preserve. |

An earlier draft of this document listed `docs/PRD.md` and the research
transcripts as *references*, which instruments 1 and 2 refute: neither
returns them. They are adjudicated here rather than dropped so that the
count above is the residue of a complete list, not of a convenient one.

### 4.2 What the eight are

**Code and config — the real couplings (three):**

- **`scripts/validate_repository.py`** *(instruments 2 and 3; never 1 — it
  writes no path)* — **two** supervisor-aware checks now, where the
  previous revision of this document measured one. Both read
  `scripts/supervisor/lanes.sh` directly:
  - `validate_lane_state_docs` (#196) extracts the state machine and
    cross-checks it against the `supervised-lane-loop` skill's `SKILL.md`,
    resolved from `apm_modules` (in this repo or `~/.apm`). It reaches
    across a repo boundary into `jonhill90/skills`, and emits a `warning`
    not an `error` — deliberately, per its own docstring, so a skills-repo
    PR is never required to land before an agent-dotfiles PR can merge.
  - `validate_laneview_state_maps` (#231) checks that every renderer under
    `scripts/supervisor/laneview/` names every state `lanes.sh` ships.
    Unlike the first, a renderer missing a shipped state is an **`error`**
    — both sides are files in this repository, so its docstring argues the
    fix belongs in the same change. (It also emits a `warning` for a
    renderer whose state map it cannot parse at all.) This is the first
    supervisor coupling in this repo's validation that can fail CI.
- **`tests/test_validate_repository.py`** — builds fake
  `scripts/supervisor/lanes.sh` and `laneview/*.sh` fixtures to exercise
  both checks.
- **`settings/mcp/servers.json`** — the `"supervisor"` MCP server entry
  (from #198, implemented in #233) hardcodes
  `/Users/jon/source/repos/Personal/agent-dotfiles/scripts/supervisor/mcp_server.py`
  in its `args`. **This coupling landed after #179's issue-body inventory
  was written and is absent from it.** It was flagged non-blocking in
  #233's own review and is still present.

**Repository policy (one) — `AGENTS.md`, the entry this section kept
missing.** It couples in two distinct ways, and neither is prose that can
be left to rot:

- Its **Canonical Layout** block lists `scripts/` with a `supervisor/`
  child annotated *"portable tmux-lane supervisor core, moved from
  jonhill90/Hill90; the launchd adapter stays there"*, and a `tests/` line
  reading *"unittest suite for `scripts/`, incl. `tests/supervisor/`"*.
  The layout block is drawn as an indented tree, so the string
  `scripts/supervisor` never appears on one line — an earlier revision's
  path grep, which searched only for that string, could not see this file
  at all. Widening instrument 1 to `tests/supervisor` is what makes
  `AGENTS.md` visible to it now.
- Its **"tmux is not a database"** section carries a three-row table
  tracking migration status per call site, citing `dispatch.sh:176` →
  `cli.py:194`, `lane-done.sh:90-93`/`:115-118`/`:140`, and `claim.sh:141`,
  plus `loop-tick.md` at L490/L494. (Those line numbers are quoted from
  `AGENTS.md`, not asserted by this document — they are the coupling.)
  That table is a **live policy
  instrument** — `AGENTS.md` states it "updates as each call site actually
  migrates in merged code," one row is still unmigrated, and #205 exists
  because the table once lied about merged code. After extraction it cites
  files in another repository, at line numbers, which is the exact failure
  it was written to prevent.

`AGENTS.md` is also the highest-leverage file in the repository: `CLAUDE.md`
and `.github/copilot-instructions.md` are symlinks to it, so it is the
policy three harnesses read. **A coupling inventory that misses it is
missing the one whose staleness every agent reads on every task** — which
is why #245 called this out as wrong in the one way that matters.

**Docs that cite the path (four):** `docs/hierarchy-naming-57.md`,
`docs/loop-signals.md`, `docs/supervisor-disposition.md`,
`docs/work-tracking.md`. These are prose references — design rationale,
workflow instructions — not code dependencies. They would need editing
after a move (dead relative paths), not re-architecture.
`docs/work-tracking.md` is the sharpest of the four: it gives operators
literal `scripts/supervisor/claim.sh` command lines to run.

### 4.3 Checked and empty, recorded so the absence is not mistaken for an oversight

- **Roster:** `settings/default-skills.txt` lists `supervised-lane-loop`,
  the skill that operates the tool, but its content lives in
  `jonhill90/skills` per this repo's "roster here, author elsewhere" model
  — a name in a list, not a dependency on the tree.
- **`hooks/`: zero references.** `AGENTS.md` lists `hooks/` among this
  repo's canonical assets and a reader will look for it here.
  `git ls-files hooks/` returns one path — `hooks/.gitkeep` — and
  `grep -rn supervisor hooks/` returns nothing. No hook wires the
  supervisor into any harness today, so nothing under `hooks/` moves,
  breaks, or needs editing at extraction time.
- **`apm.yml`: no dependency declaration.** The supervisor is not declared
  as an APM package or dependency; it is committed content, synced by
  nothing but git. This matters for §8. (Its one `lanes.sh` mention is a
  comment, adjudicated in §4.1.)

### 4.4 What the four newest merges changed

`#225`, `#229`, `#231` and `#232` — everything merged since the previous
revision's base — added 2,340 lines across 20 files
(`git diff --stat 32e8eab origin/main`, whose base `32e8eab` *is* #228).
Only one moved this section's list:

- **#231 (laneview) added a coupling** — `validate_laneview_state_maps` in
  `scripts/validate_repository.py`, and its fixtures in
  `tests/test_validate_repository.py`. Both files were already on the list,
  so the count did not change; what changed is that one of them now fails
  CI as an `error` rather than warning.
- **#225, #229 and #232 added none**, nor did #228 before them.
  `harness-registry.sh` is sourced only from inside the tree; #225's
  `dispatch.sh` authorship guard, #229's `verdict.py` rebase detection and
  #232's test-timeout bounding are all in-tree changes.

## 5. What the repo's own validation and CI actually know about it

- `scripts/validate_repository.py` — **two** supervisor-aware checks
  (`validate_lane_state_docs` and `validate_laneview_state_maps`, §4.2).
  The previous revision of this document said one, correctly at `32e8eab`;
  #231 added the second, and it is an `error`-level check, so from that
  merge onward the supervisor tree can fail this repository's validation
  outright rather than only warn. Nothing else in that file names
  `scripts/supervisor/` or `tests/supervisor/`.
- `tests/test_instruction_globs.py` — **zero** references. It validates
  `.github/instructions/*.instructions.md` glob coverage; the supervisor
  ships no instructions file, so this test is silent on it either way.
- `.github/workflows/validate.yml` — the only CI workflow in the repo. It
  runs `scripts/validate_repository.py`, then
  `python -m unittest discover -s tests -v`. **Both halves of
  `tests/supervisor/` run in CI today**, but by two different mechanisms,
  and an earlier revision of this section credited one for both:
  - `unittest discover` collects `test*.py` only, so it picks up the **15**
    Python test modules directly. (`tests/supervisor/` holds 16 `.py`
    files; the sixteenth is `__init__.py`, which is not a test module and
    is not collected. An earlier revision said sixteen here and in §10 —
    an off-by-one against this document's own §1, which enumerated the
    fifteen correctly.)
  - The **19 shell suites run through a Python shim**,
    `tests/supervisor/test_shell_suites.py`, which globs `test_*.sh` beside
    itself and shells out to each. Its own docstring records why it exists:
    before it, *"Nothing ran them"* — `unittest discover` picked up only the
    Python ones, and *"a regression in `lanes.sh` would have reached `main`
    green."*
  - The 8 stub fixtures under `stubs/` and `__init__.py` do not "run" at
    all; the stubs are invoked *by* the shell suites as fake `gh`, `tmux`,
    `ps` and — since #231 — `curl`.

  There is no separate job, no separate trigger, and no way to skip the
  supervisor tests independently. Extracting the tree removes this coverage
  from `agent-dotfiles`' CI entirely unless the new repo stands up its own
  workflow first — and, per the shim above, a bare `unittest discover`
  there would cover only the Python half.

## 6. The precedent already drawn once, in this exact domain — and it runs the other direction

`scripts/supervisor/README.md` records that this code was itself moved, not
born here: commit `a39ae9d`, *"Move portable supervisor core from Hill90
into agent-dotfiles"*.

At that move a boundary was drawn and has held since: the **portable core**
(ledger, transport adapters, dispatch/claim/notify scripts) came here; the
**launchd host adapter** for the machine that runs it
(`com.hill90.supervisor.plist`, `service.sh`, `install.sh`, and the
`hill90-supervisor` entry-point shim) *stayed behind* in `jonhill90/Hill90`
and is documented in that same `README.md` as deliberately not ported.
`docs/SPEC.md` §15.1 states the general version of the same line: *"the
portable core owns the ledger, ownership-safe transitions, assignment
gating, and attention; a transport adapter owns only 'deliver this prompt
to this lane and report what came back.'"*

**#179 proposes running that line a second time, in the opposite
direction:** the portable core — currently living in `agent-dotfiles`,
having already been extracted once from `Hill90` — moves again, to its own
repository, and `agent-dotfiles` becomes the thing that plugs an adapter
*into* it, symmetrical to how `Hill90` already relates to it today. This
plan extends that existing line rather than inventing a new one: **the
portable core moves; the machine-specific adapter (state directory
location, LaunchAgent/cron wiring, `DEFAULT_REPOSITORIES`, the MCP server's
absolute path) stays**, whether in `agent-dotfiles` or in a sibling
adapter repo akin to what `Hill90` already has.

## 7. What stays, what moves, and why

| Artifact | Disposition | Why |
|---|---|---|
| `scripts/supervisor/` Python, shell, `harness/`, and `laneview/` | **Moves** | Zero imports out (§2); self-contained ledger/transport/dispatch/render logic — this is the product #179 describes |
| `tests/supervisor/` | **Moves with it** | Tests only exercise the moving code; leaving them behind strands coverage against nothing |
| `scripts/supervisor/README.md` | **Moves with it** | Documents the moving code, including the Hill90 precedent this plan extends |
| `scripts/supervisor/loop-tick.md` | **Moves to `jonhill90/skills`, or is packaged as a skill** | Jon's framing: *"the loop or skill that uses the tool might go in skills or agent-dotfiles."* It instructs an operator how to run the tool; it is not the tool |
| `supervised-lane-loop` (rostered in `settings/default-skills.txt`, authored in `jonhill90/skills`) | **Stays rostered here; content stays in `skills`** | Already follows this repo's "roster here, author elsewhere" model; no change needed |
| State directory location, `DEFAULT_REPOSITORIES`, the MCP server's absolute path, any LaunchAgent/cron entry | **Stays in `agent-dotfiles`, or in a new adapter layer** | Exactly the class of thing that stayed in `Hill90` under the existing precedent (§6) — machine wiring, not portable product |
| `hooks/` | **Stays, and is a no-op either way** | Empty but for `.gitkeep`, and nothing under it references the supervisor (§4). Listed so the absence is recorded as checked, not overlooked |
| `AGENTS.md`'s Canonical Layout block and "tmux is not a database" table | **Stays, and must be edited in the extraction PR itself** | It is the policy three harnesses read (`CLAUDE.md` and `.github/copilot-instructions.md` are symlinks to it). Its table cites five moving files at line numbers and is explicitly maintained as merged code changes (§4.2) — leaving it stale reproduces #205 across a repo boundary |
| `validate_lane_state_docs` in `scripts/validate_repository.py` | **Deleted, or rewritten to check the new repo**, decided at extraction time | It already reaches across a repo boundary; after extraction it checks a directory that no longer exists here |
| `validate_laneview_state_maps` in `scripts/validate_repository.py` | **Same decision, but it fails louder and sooner** | Added by #231, after the previous revision of this plan. It is an `error`, and it returns `[]` when `lanes.sh` is absent — so on the day the tree moves it stops checking anything **silently**, exactly the failure mode its own docstring was written against |
| The `"supervisor"` entry in `settings/mcp/servers.json` | **Path updated to the new repo's checkout** — still hardcoded unless #233's flagged issue is fixed first | The "everyone must check out both repos in matching places" problem exists today; extraction relocates it rather than creating it |

## 8. The reverse-dependency question

After extraction: **`agent-dotfiles` depends on the supervisor repo; the
supervisor repo depends on nothing in `agent-dotfiles`.**

Evidence for the second half: §2 and §4 show no code under
`scripts/supervisor/` reaches outside itself, and `apm.yml` declares no
supervisor package today, so there is no existing reverse dependency to
invert. The forward dependency would need to be created — most naturally
the same way this repo already depends on skill content: an `apm.yml`
pinned-ref dependency resolved into `apm_modules`, which is the same
mechanism `validate_lane_state_docs` already uses to resolve
`supervised-lane-loop`. That keeps this repo's existing pattern rather than
inventing a second one for this case.

**"Both" is the wrong answer, and nothing measured here points toward it:**
no file under `scripts/supervisor/` names `agent-dotfiles` except as a
default string value (§3), never as an import or an execution path.

## 9. Sequencing with what's in flight

Re-checked against issue and PR state, not against the brief's framing —
some of this landed after the brief was written:

- **#216** (harness identity) — **closed**, merged as `7db46f2`. No blocker.
- **#215** (watchdog busy check) and **#228** (its fix) — **closed /
  merged** as `32e8eab`, the previous revision's base. It added
  `harness-registry.sh` to the moving tree and changed `watchdog.sh`,
  `lanes.sh`, `adapter.py`, and the test stubs — all inside it. No new
  coupling (§4).
- **#198** (MCP server proposal) and **#233** (its implementation) —
  **closed / merged** as `d4ae64d`. Done, but #233 is what introduced the
  fresh hardcoded-path coupling in §4 and §7. Worth fixing — resolve the
  path relative to the MCP config file, or from an env var — before or
  during extraction, since extraction is the natural moment to stop
  hardcoding a same-repo-relative path across a repo boundary.
- **#212 / #225** (dispatch.sh authorship guard) — **closed / merged** as
  `0b9f39d`. This was the previous revision's one "land it first"
  sequencing item and it has landed; gate 2 in §10 is now satisfied.
- **#226 / #229** (verdict-SHA rebase detection) — **closed / merged** as
  `2c4db5d`. In-tree, no new coupling.
- **#178 / #231** (tmux-plugin exploration, shipped as the `laneview`
  adapter) — **closed / merged** as `08b0d00`. This one *did* change the
  boundary: it added `validate_laneview_state_maps`, the first
  `error`-level supervisor check in this repo's validation (§4.2, §5, §7).
- **#227 / #232** (`test_inbox_poll.sh` CI hang) — **closed / merged** as
  `b51cf71`, this document's base. `main` is no longer red on the moving
  tree's tests, which removes the previous revision's caveat that the tree
  carried a currently-failing suite.

A search for open issues naming the supervisor
(`gh issue list --search "supervisor in:body" --state open`) returned **17**
issues when run against `b51cf71`, which is **sixteen** beyond #179 itself:
#16 (the ledger-versus-shell decision `docs/supervisor-disposition.md` was
written for), #52 (notification architecture), #57 (hierarchy naming), #92
(watchdog re-arm reliability), #139 (Linux/Windows portability, explicitly
deferred), #192 (`digest.sh` test gap), #235 (`advance-live.sh` never
fetches), #237 (restore after tmux server loss), #238 (two supervisor
instances can dispatch concurrently), #239 (`lanes.sh` protects by window
index), #240 (ledger task and window name identify a different brief than
the pane received), #241 (window indices as dispatch targets under
`renumber-windows`), #244 (a conflicting PR gets no check suite and a
waiting lane cannot tell), #245 (this document's own issue), #246
(`laneview` follow-ups from #231's re-review), and #247 (a lane's bare
`tmux kill-server` destroyed the live estate).

Counting #245 is deliberate: this document is one of the sixteen, and
excluding it to make the number look cleaner would be the same class of
self-flattering edit `AGENTS.md`'s "Recording Figures" names.

This is a count of a set that was enumerated, at a named commit, and it
**will drift**. It already has, twice: an earlier revision said "nine more"
and included #215, which had closed before that sentence was committed; the
next said fifteen and listed #178, #226 and #227, all three of which have
since closed, while #244, #246 and #247 opened. Re-run the command rather
than trusting the number; what matters is its shape, not its value.

None of the sixteen sits on the extraction boundary itself, but #16 is a
live architectural question about which of the two implementations in this
tree is even the right one to extract. #239, #240 and #241 are one family —
state inferred from tmux window names and indices rather than recorded —
which is the `AGENTS.md` "tmux is not a database" rule still being paid
down inside the moving tree, and #247 is that family's most expensive
instance so far.

All of it extends "after we get it working" rather than blocking this plan:
a bug list this long, and growing this fast, is itself evidence the tool is
not done — which is the condition Jon already attached to the timing.

## 10. What must be true before extraction starts

1. **The loop keeps running.** The move must be a repo split with a pinned
   dependency added afterward (§8), not a flag day — the cron/LaunchAgent
   loop cannot go dark while `apm.yml` is edited and re-resolved.
2. ~~**#212/#225 lands first**~~ — **satisfied.** Merged as `0b9f39d`
   (§9). It was the one open PR touching the moving tree when the previous
   revision was written; nothing open touches it today.
3. **#16 has an answer, or the ledger's fate is stated explicitly** (§1.1)
   — extraction scope (3,523 running lines versus 6,882) is undefined until
   then.
4. **The three hardcodes and the three env-var names in §3 are resolved**,
   in the new repo or before the move — otherwise the new repo ships
   `/Users/jon` in its own `cli.py` and `sleepcheck.py` on day one, and
   `notify.sh`'s state directory remains the one non-overridable default.
5. **Both `lanes.sh`-reading checks have a stated fate** — deleted, or
   rewritten to fetch `lanes.sh` from the new repo — before the PR that
   removes `scripts/supervisor/lanes.sh` from `main` merges. That is
   `validate_lane_state_docs` (#196) *and*, since #231,
   `validate_laneview_state_maps`. Both return `[]` when `lanes.sh` is
   absent, so on move day both stop checking without saying so: CI goes
   green having verified nothing, for a state-drift class of bug this repo
   has already paid to catch twice.
6. **CI parity, and it needs more than `unittest discover`** — the new repo
   needs its own runner wired before `tests/supervisor/`'s 43 files stop
   running here (§5), or 15,013 lines of test coverage go dark mid-move.
   A bare `unittest discover` buys only the 15 Python test modules: the 19
   shell suites run through `tests/supervisor/test_shell_suites.py`, so
   that shim must travel with them. Under §7's "tests move wholesale" it
   does — the point is that the gate is satisfied by the shim moving, not
   by the command being run.
7. **`AGENTS.md` is edited in the extraction PR, not after it** (§4.2,
   §7) — its Canonical Layout block and its "tmux is not a database" table
   are the policy every harness reads, and the table's rows cite five
   moving files at line numbers. #205 exists because that table once
   described merged code inaccurately; a move that leaves it pointing at a
   directory this repository no longer contains repeats that in the one
   file every harness reads, under all three of its names.

## 11. Open questions this plan does not resolve

Named, not answered:

- **Repo name** — the tool has been called "the supervisor," "the tool,"
  "the meta-harness," and "OpenClaw/Hermes" in a single session.
- **Public or private** — a docs and config-bar question, not a coupling
  question, and out of scope for this measurement.
- **Where the design spec lives after the split.** `docs/SPEC.md` §14,
  *"Supervisor/Worker Loop Mechanism (settled 2026-08-10)"*, and §15.1's
  core/adapter line are the governing design for the thing being
  extracted, and `docs/loop-engineering.md` reasons from them. §4.1
  adjudicates both as **not couplings** — they name no file and no path,
  so a move leaves every sentence true and breaks nothing. That is a
  measurement result, not a recommendation to leave them here: a
  repository whose design spec lives in a different repository is a
  governance question, and this document deliberately does not answer it.
  The same applies to `docs/supervisor-disposition.md`, which *is* a
  coupling (it cites paths) and whose #16 question §1.1 already flags.
- **Whether the viewer layer ships with the extracted repo or separately.**
  #178 closed while this document was in review: it shipped as #231's
  `laneview/` adapter — two renderers behind `lanes.sh --json`, neither
  required by the other — rather than as a tmux plugin. That answers *what
  the viewer is* and leaves *where it lives* open. It sits inside
  `scripts/supervisor/` and so moves by default under §7, but it is the
  human-facing half of the product and the only part with an outward
  network dependency (a localhost daemon, §1). #246 tracks its open
  follow-ups.

## Corrections in this revision

`AGENTS.md` requires that a corrected figure say what it was and why it was
wrong. Every change from the revision measured at `32e8eab`:

| Figure | Was | Now | Why it was wrong |
|---|---|---|---|
| §4 coupled files | 7 | **8** | `AGENTS.md` was absent. It is a coupling twice over (§4.2) and the path grep cannot see either instance. The deeper cause was structural — the total was typed by hand beside a separately-produced list — and §4.1 now derives it with `cat -n` so the two cannot disagree. |
| §4 `apm.yml` | "zero references" | one comment, adjudicated **not** a coupling | The claim was produced by the path grep alone. Instrument 2 finds a `lanes.sh` mention in a pin-bump comment. The conclusion stands; the evidence for it did not. |
| §4 instruments | 1 path grep over `scripts/supervisor` only, plus one file checked by hand | **3 instruments** over both trees, with every hit either counted or excluded by name | An adversarial review of the first draft of this revision broke the completeness argument, not the count: `scripts/sync.py` names the supervisor in a comment that neither the path grep nor the basename grep can see. Instrument 3 (the bare word, case-insensitive) was added as the backstop, instrument 1 was widened to `tests/supervisor`, and the name set now comes from `git ls-files` rather than `find` so it does not depend on a clean working tree. The list is unchanged at eight. |
| §4 exclusion reasons for `docs/SPEC.md` and `docs/loop-engineering.md` | "No supervisor reference" | both reference it extensively; excluded because they name no file and no path | Written against the substring false positive (`eval_score.py` contains `core.py`) without checking the rest of the file. `docs/SPEC.md:1000` is a section headed *"Supervisor/Worker Loop Mechanism"*. The exclusions survive; the stated reasons did not, and a false reason in this section is the defect class that closed #236. |
| §5 supervisor-aware checks in `validate_repository.py` | 1 | **2** | Correct at `32e8eab`. #231 added `validate_laneview_state_maps` after it, and that one is an `error`, not a warning. |
| §5 / §10 Python modules `discover` collects | 16 | **15** | Off-by-one against this document's own §1: `tests/supervisor/` holds 16 `.py` files, one of which is `__init__.py` and is not collected. |
| §1 `scripts/supervisor/` | 37 files / 11,698 lines | **41 / 12,414** | Four merges landed after that measurement (#225, #229, #231, #232); #231 added the four-file `laneview/` subtree. |
| §1 `tests/supervisor/` | 41 files / 13,652 lines | **43 / 15,013** | Same four merges; #231 added `test_laneview.sh` and the `curl-opensessions` stub. |
| §1 shell suites / stubs | 18 / 7 | **19 / 8** | Same. |
| §1.1 subsets | 3,378 / 3,346, remainder 4,974 | **3,523 / 3,359, remainder 5,532** | Re-measured over the same named file sets at the new base. |
| §9 open supervisor issues beyond #179 | 15 | **16** | #178, #226 and #227 closed; #244, #245, #246 and #247 opened. The count was accurate when taken and is quoted with its commit for that reason. |
| §10 gate 2 (#212/#225 lands first) | open blocker | **satisfied** | Merged as `0b9f39d`. |
| §11 tmux plugin (#178) | open question | **answered as the `laneview` adapter** (#231); *where it lives* still open | It shipped while this document was in review. |
| §11 open questions | 3 | **4** | Added: where `docs/SPEC.md` §14, the governing design for the extracted tool, lives after the split. Not a coupling (§4.1) and therefore not a blocker, but excluding it from §11 as well would have let "measured as harmless" read as "considered and settled." |

Unchanged and re-verified at `b51cf71`: §2 (zero outward imports, zero
`../..`), §3's three hardcoded paths and three env-var names, §4's docs
group of four, `hooks/` empty, and every conclusion in §6, §7 and §8. One
item is **added** rather than corrected: §3's finding that `laneview.sh` is
an eleventh writer of the `"agent-dotfiles"` session default and the only
one that does not read `LANES_SESSION`.
