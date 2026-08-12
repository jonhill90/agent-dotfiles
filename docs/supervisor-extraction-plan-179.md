# Supervisor Extraction Plan — #179

This is a plan and a measurement, not an extraction. Per Jon's own framing
in #179 and the brief that produced this document, the extraction does not
happen now — lanes are running on this code as this is written. What
follows is (1) a fresh, enumerated coupling inventory, superseding the one
already in the #179 issue body, and (2) a sequencing plan for whenever the
work is picked up.

All figures below are **measured** in this worktree on 2026-08-12 against
the tree at `39c7389` (whose parent is `main` at `d4ae64d`), by running the
command shown, unless marked **inferred**.

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
| 7,258 lines, `scripts/supervisor/` | **11,508** | `cat $(find scripts/supervisor -type f) \| wc -l` |
| 30 files, `tests/supervisor/` | **41** | `find tests/supervisor -type f \| wc -l` |
| "every default is env-overridable" | **False** — see §3 | `grep -rn 'agent-dotfiles-supervisor' scripts/supervisor/` |

This is not a criticism of whoever wrote the issue body — it is the exact
failure mode `AGENTS.md`'s "Recording Figures" section names: a number that
reads as measured but wasn't re-verified against current `main`. The
inventory below replaces it.

## 1. Size, enumerated

`scripts/supervisor/` — **36 files, 11,508 lines**, enumerated by
`find scripts/supervisor -type f`:

- **20 shell**: `advance-live.sh`, `bootstrap-session.sh`, `claim.sh`,
  `digest.sh`, `director-inbox.sh`, `director-route.sh`, `dispatch.sh`,
  `inbox-poll.sh`, `inbox-route.sh`, `inbox.sh`, `input-box.sh`,
  `lane-done.sh`, `lanes.sh`, `notify.sh`, `watchdog.sh`, `worktree.sh`,
  `would-revert.sh`, plus `harness/claude.sh`, `harness/codex.sh`,
  `harness/copilot.sh` — 5,025 lines.
- **14 Python**: `acp_transport.py`, `adapter.py`, `cli.py`, `core.py`,
  `github_source.py`, `mcp_server.py`, `recycle.py`,
  `refresh_brief_resume.py`, `sensor.py`, `sleepcheck.py`,
  `supervisor_view.py`, `transport.py`, `verdict.py`, `watchdog_notify.py`
  — 5,309 lines.
- **2 Markdown**: `README.md`, `loop-tick.md` — 1,174 lines.

`tests/supervisor/` — **41 files, 13,507 lines**:

- **18 shell suites** (`test_advance_live.sh` … `test_would_revert.sh`).
- **15 Python test modules** plus `__init__.py` — 16 `.py` files total.
- **7 executable stub fixtures** under `stubs/` with no extension: `gh`,
  `gh-claim`, `ps-lanes`, `tmux`, `tmux-dispatch`, `tmux-lane-done`,
  `tmux-lanes`.

An earlier draft of this document reported "23 shell, 9 Python" for
`scripts/supervisor/` and "20 shell test suites, 14 Python test modules"
for `tests/supervisor/`. Both were wrong — the first pair does not even sum
to the correct total of 36. The lists above were produced by enumerating
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
| Shell supervisor | `watchdog.sh`, `lanes.sh`, `dispatch.sh`, `claim.sh`, `notify.sh`, `inbox.sh`, `worktree.sh`, `director-inbox.sh`, `sleepcheck.py`, `watchdog_notify.py` | **3,298** | 1,727 |
| Ledger | `cli.py`, `core.py`, `adapter.py`, `sensor.py`, `github_source.py`, `transport.py`, `acp_transport.py` | **3,335** | 2,137 |

The remaining **4,875** lines — arithmetic on the two measured subtotals
against the 11,508 total, not a third measurement — are the other shell
scripts, the other Python modules, `README.md`, and `loop-tick.md`.

That the ledger has never run (no `ledger.sqlite3`, no lock file, no
results directory under its default state path) is **inferred current**
from `supervisor-disposition.md`, not re-measured this session.

This is a real scope question for #179 that "measure the coupling" doesn't
answer by itself: **extraction of "the supervisor" could mean the 3,298
running lines, the full 6,633, or a decision to leave the never-called
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
`input-box.sh` from the same directory via `$HERE`. No `../..` traversal
exists anywhere under the tree (`grep -rn '\.\./\.\.' scripts/supervisor/`
— zero hits).

## 3. Hardcoded paths, and three competing env-var names

The issue body names two hardcodes. There are **three**, and the
"every default is env-overridable" claim fails on a fourth axis as well.

**Hardcoded absolute paths:**

1. **`cli.py`** — `DEFAULT_REPOSITORIES`, four absolute
   `/Users/jon/source/repos/Personal/...` paths. The only `/Users/jon` in
   `scripts/` outside `README.md`'s Hill90 examples.
2. **`sleepcheck.py`** — `DEFAULT_PROJECT_DIR`, hardcoding
   `~/.claude/projects/-Users-jon-source-repos-Personal-agent-dotfiles`.
3. **`notify.sh`** — assigns `STATE="$HOME/.local/state/agent-dotfiles-supervisor"`
   as a bare literal with **no env override at all**, unlike every other
   shell caller.

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
env-overridable everywhere it is read (`advance-live.sh`,
`bootstrap-session.sh`, `claim.sh`, `digest.sh`, `director-route.sh`,
`dispatch.sh`, `inbox-poll.sh`, `inbox-route.sh`, `lane-done.sh`,
`lanes.sh`) — it is a *default value*, not a hardcode. But the default
string is this repo's own name, which is itself a coupling if the tool
moves and inherits a session named after the repo it left.

## 4. References from outside `scripts/supervisor/` and `tests/supervisor/`

`grep -rln 'scripts/supervisor\|scripts\.supervisor'`, excluding the two
trees themselves and this document, returns exactly **six** files.

**Code and config — the real couplings (three):**

- **`scripts/validate_repository.py`** — its `validate_lane_state_docs`
  function reads `scripts/supervisor/lanes.sh` directly to extract the
  state machine and cross-check it against the `supervised-lane-loop`
  skill's `SKILL.md`, resolved from `apm_modules` (in this repo or
  `~/.apm`). This is the **one** structural coupling in the repo's own
  validation, and it already reaches across a repo boundary (into
  `jonhill90/skills`). It emits a `warning`, not an `error` — deliberately,
  per its own docstring, so a skills-repo PR is never required to land
  before an agent-dotfiles PR can merge (#196).
- **`tests/test_validate_repository.py`** — builds a fake
  `scripts/supervisor/lanes.sh` fixture to exercise that drift check.
- **`settings/mcp/servers.json`** — the `"supervisor"` MCP server entry
  (from #198, implemented in #233) hardcodes
  `/Users/jon/source/repos/Personal/agent-dotfiles/scripts/supervisor/mcp_server.py`
  in its `args`. **This coupling landed after #179's issue-body inventory
  was written and is absent from it.** It was flagged non-blocking in
  #233's own review and is still present.

**Docs that cite the path (three):** `docs/hierarchy-naming-57.md`,
`docs/loop-signals.md`, `docs/supervisor-disposition.md`,
`docs/work-tracking.md`. These are prose references — design rationale,
workflow instructions — not code dependencies. They would need editing
after a move (dead relative paths), not re-architecture.

**Not couplings, corrected from an earlier draft:** that draft also listed
`docs/loop-engineering.md`, `docs/PRD.md`, `docs/SPEC.md`,
`docs/provenance-manifest.md`, `AGENTS.md`, and fixture transcripts under
`docs/research/docs-layout-council-138/` as references. None of them
contains the string `scripts/supervisor` (verified with `grep -c` per
file); they mention the supervisor by *name* only, and `docs/research/`
does not mention the path at all. Naming a file that does not reference
the thing is the same defect class as missing one that does.

**Roster:** `settings/default-skills.txt` lists `supervised-lane-loop`, the
skill that operates the tool, but its content lives in `jonhill90/skills`
per this repo's "roster here, author elsewhere" model — so this is a name
in a list, not a dependency on the tree.

**`apm.yml`: zero references.** The supervisor is not declared as an APM
package or dependency; it is committed content, synced by nothing but git.
This matters for §7 below.

## 5. What the repo's own validation and CI actually know about it

- `scripts/validate_repository.py` — **one** supervisor-aware check
  (`validate_lane_state_docs`, §4). Nothing else in that file names
  `scripts/supervisor/` or `tests/supervisor/`.
- `tests/test_instruction_globs.py` — **zero** references. It validates
  `.github/instructions/*.instructions.md` glob coverage; the supervisor
  ships no instructions file, so this test is silent on it either way.
- `.github/workflows/validate.yml` — the only CI workflow in the repo. It
  runs `scripts/validate_repository.py`, then
  `python -m unittest discover -s tests -v`. `unittest discover` walks
  every package under `tests/`, so **all 41 files in `tests/supervisor/`
  run in CI today**, with no separate job, no separate trigger, and no way
  to skip them independently. Extracting the tree removes this coverage
  from `agent-dotfiles`' CI entirely unless the new repo stands up its own
  workflow first.

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
| `scripts/supervisor/` Python, shell, and `harness/` | **Moves** | Zero imports out (§2); self-contained ledger/transport/dispatch logic — this is the product #179 describes |
| `tests/supervisor/` | **Moves with it** | Tests only exercise the moving code; leaving them behind strands coverage against nothing |
| `scripts/supervisor/README.md` | **Moves with it** | Documents the moving code, including the Hill90 precedent this plan extends |
| `scripts/supervisor/loop-tick.md` | **Moves to `jonhill90/skills`, or is packaged as a skill** | Jon's framing: *"the loop or skill that uses the tool might go in skills or agent-dotfiles."* It instructs an operator how to run the tool; it is not the tool |
| `supervised-lane-loop` (rostered in `settings/default-skills.txt`, authored in `jonhill90/skills`) | **Stays rostered here; content stays in `skills`** | Already follows this repo's "roster here, author elsewhere" model; no change needed |
| State directory location, `DEFAULT_REPOSITORIES`, the MCP server's absolute path, any LaunchAgent/cron entry | **Stays in `agent-dotfiles`, or in a new adapter layer** | Exactly the class of thing that stayed in `Hill90` under the existing precedent (§6) — machine wiring, not portable product |
| `validate_lane_state_docs` in `scripts/validate_repository.py` | **Deleted, or rewritten to check the new repo**, decided at extraction time | It is the one check that already reaches across the boundary; after extraction it checks a directory that no longer exists here |
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
- **#198** (MCP server proposal) and **#233** (its implementation) —
  **closed / merged** as `d4ae64d`. Done, but #233 is what introduced the
  fresh hardcoded-path coupling in §4 and §7. Worth fixing — resolve the
  path relative to the MCP config file, or from an env var — before or
  during extraction, since extraction is the natural moment to stop
  hardcoding a same-repo-relative path across a repo boundary.
- **#212 / #225** (dispatch.sh authorship guard) — **still open**, and
  touching `dispatch.sh` inside the tree that would move. Land it before
  extraction starts, or the extraction PR inherits an in-flight review
  burden on top of the move.

A search for open issues naming the supervisor
(`gh issue list --search "supervisor in:body" --state open`) found **nine
more** beyond #179 and #212/#225: #215 (watchdog busy check), #227
(`test_inbox_poll.sh` CI hang), #139 (Linux/Windows portability, explicitly
deferred), #178 (tmux plugin, §11), #52 (notification architecture), #192
(`digest.sh` test gap), #16 (the ledger-versus-shell decision
`docs/supervisor-disposition.md` was written for), #92 (watchdog re-arm
reliability), and #226 (verdict-SHA rebase detection). None sits on the
extraction boundary itself, but #227 is a currently red CI test in the tree
that would move, and #16 is a live architectural question about which of
the two implementations in this tree is even the right one to extract.
Both extend "after we get it working" rather than blocking this plan: a bug
list this long is itself evidence the tool is not done, which is the
condition Jon already attached to the timing.

## 10. What must be true before extraction starts

1. **The loop keeps running.** The move must be a repo split with a pinned
   dependency added afterward (§8), not a flag day — the cron/LaunchAgent
   loop cannot go dark while `apm.yml` is edited and re-resolved.
2. **#212/#225 lands first** (§9) — the one open PR touching the moving tree.
3. **#16 has an answer, or the ledger's fate is stated explicitly** (§1.1)
   — extraction scope (3,298 running lines versus 6,633) is undefined until
   then.
4. **The three hardcodes and the three env-var names in §3 are resolved**,
   in the new repo or before the move — otherwise the new repo ships
   `/Users/jon` in its own `cli.py` and `sleepcheck.py` on day one, and
   `notify.sh`'s state directory remains the one non-overridable default.
5. **`validate_lane_state_docs` has a stated fate** — deleted, or rewritten
   to fetch `lanes.sh` from the new repo — before the PR that removes
   `scripts/supervisor/lanes.sh` from `main` merges, or CI silently stops
   checking a state-drift class of bug this repo already paid to catch
   once (#196).
6. **CI parity** — the new repo needs its own `unittest discover` (or
   equivalent) wired before `tests/supervisor/`'s 41 files stop running
   here (§5), or 13,507 lines of test coverage go dark mid-move.

## 11. Open questions this plan does not resolve

Named, not answered:

- **Repo name** — the tool has been called "the supervisor," "the tool,"
  "the meta-harness," and "OpenClaw/Hermes" in a single session.
- **Public or private** — a docs and config-bar question, not a coupling
  question, and out of scope for this measurement.
- **Whether the tmux plugin (#178) ships with the extracted repo or
  separately** — it is the human-facing half of the same product, but no
  code under `scripts/supervisor/` references any tmux-plugin artifact
  today, so this measurement has nothing to add.
