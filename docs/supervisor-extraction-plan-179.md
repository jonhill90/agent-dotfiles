# Supervisor Extraction Plan — #179

This is a plan and a measurement, not an extraction. Per Jon's own framing
in #179 and the brief that produced this document, the extraction does not
happen now — eight lanes are running on this code as this is written. What
follows is (1) a fresh, enumerated coupling inventory, superseding the one
already in the #179 issue body, and (2) a sequencing plan for whenever the
work is picked up.

All figures below are **measured** in this worktree at `d4ae64d` on
2026-08-12, by running the command shown, unless marked **inferred**.

## 0. The #179 issue body already contains a coupling inventory. It is stale.

The issue body (added between its creation at 00:59 and last edit at
13:24 on 2026-08-12) states: *"7,258 lines across `scripts/supervisor/`,
plus 30 files in `tests/supervisor/`"* and *"every default is
env-overridable."* Both are wrong against the code on `main` right now:

| Claim in issue body | Re-measured here | Command |
|---|---|---|
| 7,258 lines, `scripts/supervisor/` | **11,508** (5,309 Python + 5,025 shell + 1,174 Markdown) | `wc -l $(find scripts/supervisor -type f)` |
| 30 files, `tests/supervisor/` | **41** | `find tests/supervisor -type f \| wc -l` |
| "every default is env-overridable" | **False for one file**: `notify.sh:31` hardcodes `STATE="$HOME/.local/state/agent-dotfiles-supervisor"` with no env override (every other state-dir default reads `${SUPERVISOR_STATE:-...}`) | `grep -rn 'agent-dotfiles-supervisor' scripts/supervisor/*.sh` |

This is not a criticism of whoever wrote the issue body — it is the exact
failure mode `AGENTS.md`'s "Recording Figures" section names: a number that
reads as measured but wasn't re-verified against current `main`. The
inventory below replaces it.

## 1. Size, enumerated

`scripts/supervisor/`: 36 files (23 shell, 9 Python, `README.md`,
`loop-tick.md`), 11,508 lines.
`tests/supervisor/`: 41 files (7 stub fixtures, 20 shell test suites, 14
Python test modules), 13,507 lines.

## 1.1 "The supervisor" is two systems sharing a directory, and only one of them runs

`docs/supervisor-disposition.md` (written for #16, re-checked there at
`34f0cc3`) already measured this and it still holds: `scripts/supervisor/`
contains a **shell supervisor** that actually runs (`watchdog.sh`,
`lanes.sh`, `dispatch.sh`, `claim.sh`, `notify.sh`, `inbox.sh`,
`worktree.sh`, `director-inbox.sh`, plus `sleepcheck.py` and
`watchdog_notify.py` that it shells out to — 1,727 lines) and a **ledger**
(`cli.py`, `core.py`, `adapter.py`, `sensor.py`, `github_source.py`,
`transport.py`, `acp_transport.py` — 2,137 lines) that has never been run
on this machine: no `ledger.sqlite3`, no lock file, no results directory
exists under its own default state path, and nothing outside
`tests/supervisor/` calls into it except `cli.py` importing itself and two
lines of `README.md` (`supervisor-disposition.md` §1.1-1.2, re-verified
here by rereading those cited greps rather than re-running them —
**inferred current**, not re-measured this session).

This is a real scope question for #179 that "measure the coupling" doesn't
answer by itself: **extraction of "the supervisor" could mean the 1,727
running lines, the full 3,864 (1,727 + 2,137), or a decision to leave the
never-called ledger behind (or delete it) rather than pay to port dead
code.** `docs/SPEC.md` §14.3 already frames these as layers of one design
rather than alternatives, and `docs/supervisor-disposition.md` §6-7 poses
the composition question directly — #16 is still open (§9). This plan
does not resolve #16; it names the dependency: **extraction scope should
wait on whatever #16 decides**, or explicitly carry the ledger along as
inert code with that caveat stated in the new repo's own README, the way
`recycle.py`'s orphan status is already stated in this one.

## 2. Imports from outside the tree: zero, confirmed by reading every import statement

`grep -nE '^(import|from) ' scripts/supervisor/*.py` was read in full (not
sampled). Every non-stdlib import resolves to a sibling module in the same
directory: `cli.py` imports `acp_transport`, `adapter`, `core`,
`github_source`, `sensor`, `transport`; `mcp_server.py` imports
`supervisor_view`; `verdict.py` imports `core`. No file imports from
`scripts/` above it, `tests/`, or anywhere else in the repo. Shell scripts
that `source`/`.` another file (`dispatch.sh`, `director-route.sh`,
`inbox-route.sh`, `lanes.sh`) all source `input-box.sh` from the same
directory via `$HERE`. No `../..` traversal exists anywhere under the tree
(`grep -rn '\.\./\.\.' scripts/supervisor/` — zero hits).

## 3. Hardcoded paths: three, not two

The issue body names two (`cli.py:34-37`, `sleepcheck.py:34`). A third
exists and was missed:

1. **`cli.py:35-38`** — `DEFAULT_REPOSITORIES`, four absolute
   `/Users/jon/source/repos/Personal/...` paths.
2. **`sleepcheck.py:34`** — `DEFAULT_PROJECT_DIR`, hardcodes
   `~/.claude/projects/-Users-jon-source-repos-Personal-agent-dotfiles`.
3. **`notify.sh:31`** — `STATE="$HOME/.local/state/agent-dotfiles-supervisor"`
   as a bare literal, the one state-dir default in the tree with no
   `${SUPERVISOR_STATE:-...}` override, unlike every other caller
   (`digest.sh:38`, `inbox-poll.sh:134`, `director-inbox.sh:49`,
   `inbox.sh:52`, `watchdog.sh:48`, `watchdog_notify.py:440`,
   `cli.py:22`, `supervisor_view.py:67`).

`README.md:73,76` also embeds `/Users/jon/.../Hill90` paths, but those are
doc examples for the *Hill90 adapter*, not code — see §6.

Session/lane naming (`LANES_SESSION`, default `"agent-dotfiles"`) is
env-overridable everywhere it's read (`claim.sh:49`, `bootstrap-session.sh:55`,
`digest.sh:39`, `dispatch.sh:65`, `inbox-poll.sh:133`, `director-route.sh:114,118`,
`advance-live.sh:184`, `lane-done.sh:77`, `inbox-route.sh:99`, `lanes.sh:112`)
— it is a *default value*, not a hardcode, but the default string is this
repo's own name, which is itself a coupling if the tool moves and inherits
a session named after the repo it left.

## 4. References from outside `scripts/supervisor/` and `tests/supervisor/`

`grep -rln 'scripts/supervisor\|scripts\.supervisor'` across the repo,
outside the two trees themselves:

- **Code that gates on it:** `scripts/validate_repository.py:729` —
  `validate_lane_state_docs()` reads `lanes.sh` directly to extract its
  state machine and cross-checks it against the `supervised-lane-loop`
  skill's `SKILL.md`, resolved from `apm_modules` (in this repo or
  `~/.apm`). This is the **one** structural coupling in the repo's own
  validation: it already reaches across a repo boundary (into
  `jonhill90/skills`) to check a claim about `scripts/supervisor/`. It is a
  `warning`, not an `error` — deliberately, per the docstring, so a skills-repo
  PR is never required to land before an agent-dotfiles PR can merge.
- **Tests exercising that check:** `tests/test_validate_repository.py` —
  builds a fake `scripts/supervisor/lanes.sh` fixture to test the drift
  check above (lines 985-1096).
- **Config with a hardcoded path:** `settings/mcp/servers.json` — the
  `"supervisor"` MCP server entry (`#198`/`#233`) hardcodes
  `"/Users/jon/source/repos/Personal/agent-dotfiles/scripts/supervisor/mcp_server.py"`
  as its `args`. Flagged non-blocking in #233's review; still present.
- **Roster:** `settings/default-skills.txt:12` — `supervised-lane-loop`, the
  skill that operates the tool, is rostered here but its content lives in
  `jonhill90/skills` (per this repo's own skill-sourcing model — skill
  *content* is never vendored, only rostered).
- **Docs that reference the path or the tool by name, not by dependency:**
  `docs/hierarchy-naming-57.md`, `docs/loop-signals.md`,
  `docs/supervisor-disposition.md`, `docs/work-tracking.md`,
  `docs/loop-engineering.md`, `docs/PRD.md`, `docs/SPEC.md`,
  `docs/provenance-manifest.md`, `AGENTS.md`, plus fixture transcripts under
  `docs/research/docs-layout-council-138/`. These are prose references
  (design rationale, workflow instructions, provenance rows), not code
  dependencies — none of them `import` or execute anything under
  `scripts/supervisor/`. They would need editing after a move (dead
  relative paths), not re-architecture.
- **`apm.yml`: zero references.** The supervisor is not declared as an APM
  package or dependency; it is committed content, synced by nothing but
  git. This matters for §7 below.

## 5. What the repo's own validation and CI actually know about it

- `scripts/validate_repository.py` — **one** supervisor-aware check
  (`validate_lane_state_docs`, §4 above). Nothing else in that file names
  `scripts/supervisor/` or `tests/supervisor/`.
- `tests/test_instruction_globs.py` — **zero** references. It validates
  `.github/instructions/*.instructions.md` glob coverage; the supervisor
  ships no instructions file, so this test is silent on it either way.
- `.github/workflows/validate.yml` — the only CI workflow in the repo. It
  runs `python scripts/validate_repository.py` then
  `python -m unittest discover -s tests -v`. `unittest discover` walks
  every package under `tests/`, so **all 41 files in `tests/supervisor/`
  run in CI today**, with no separate job, no separate trigger, and no way
  to skip them independently. Extracting the tree removes this coverage
  from `agent-dotfiles`' CI entirely unless the new repo stands up its own
  workflow first.

## 6. The precedent already drawn once, in this exact domain — and it runs the other direction

`scripts/supervisor/README.md:1-13` records that this code was itself
moved, not born here:

> commit `a39ae9d` — "Move portable supervisor core from Hill90 into
> agent-dotfiles"

At that move, a boundary was drawn and has held since: the **portable
core** (ledger, transport adapters, dispatch/claim/notify scripts) came
here; the **launchd host adapter** for the machine that runs it
(`com.hill90.supervisor.plist`, `service.sh`, `install.sh`, the
`hill90-supervisor` entry-point shim) *stayed behind* in `jonhill90/Hill90`
and is explicitly documented as not being ported (`README.md:11-13,
605-622`). `docs/SPEC.md` §15.1 states the general version of this same
line: *"the portable core owns the ledger, ownership-safe transitions,
assignment gating, and attention; a transport adapter owns only 'deliver
this prompt to this lane and report what came back.'"*

**#179 proposes running that same line a second time, in the opposite
direction**: the portable core (currently living in `agent-dotfiles`,
having already been extracted once from `Hill90`) would move again, to its
own repository, and `agent-dotfiles` would become the thing that plugs an
adapter *into* it — symmetrical to how `Hill90` already relates to it
today. This plan extends that existing line rather than inventing a new
one, per the brief's instruction: **the portable core moves; the
machine-specific adapter (state directory location, LaunchAgent/cron
wiring, the repo list in `DEFAULT_REPOSITORIES`, the MCP server's absolute
path) stays, whether that's in `agent-dotfiles` or a sibling
"agent-dotfiles adapter" akin to what `Hill90` already has for it.**

## 7. What stays, what moves, and why

| Artifact | Disposition | Why |
|---|---|---|
| `scripts/supervisor/*.py`, `*.sh`, `harness/*.sh` | **Moves** | Zero imports out (§2), self-contained ledger/transport/dispatch logic — this is the product #179 describes |
| `tests/supervisor/*` | **Moves with it** | Tests only exercise the moving code; leaving them behind would strand coverage against nothing |
| `scripts/supervisor/README.md` | **Moves with it** | Documents the moving code; already documents the Hill90 precedent this plan extends |
| `scripts/supervisor/loop-tick.md` | **Moves to `jonhill90/skills` (or stays, packaged as a skill)** | Jon's own framing: *"the loop or skill that uses the tool might go in skills or agent-dotfiles."* It is markdown instructing an operator how to run the tool, not the tool — the same shape as every other skill this repo rosters but does not vendor |
| `supervised-lane-loop` skill (lives in `jonhill90/skills`, rostered at `settings/default-skills.txt:12`) | **Stays rostered here, content stays in `skills`** | Already follows this repo's existing "roster here, author elsewhere" model (`AGENTS.md` "Skill Authoring and Sourcing"); no change needed |
| State directory location, `DEFAULT_REPOSITORIES`, the MCP server's absolute path, any future LaunchAgent/cron entry | **Stays in `agent-dotfiles`, or a new adapter layer** | This is exactly the class of thing that stayed in `Hill90` under the existing precedent (§6) — machine-specific wiring, not portable product |
| `validate_lane_state_docs` in `scripts/validate_repository.py` | **Deleted or rewritten to check the new repo instead**, decided at extraction time | It is the one check that reaches across the boundary already; after extraction it would be checking a directory that no longer exists here |
| `settings/mcp/servers.json`'s `"supervisor"` entry | **Path updated to point at the new repo's checkout**, still hardcoded unless #233's flagged non-blocking issue is fixed first | Already broken by the "everyone has to check out both repos in matching places" problem the hardcoded path creates today — extraction doesn't create this problem, it just relocates it |

## 8. The reverse-dependency question

After extraction: **`agent-dotfiles` depends on the supervisor repo; the
supervisor repo depends on nothing in `agent-dotfiles`.**

Evidence for the second half: §2 and §4 show zero code in
`scripts/supervisor/` reaches outside itself, and `apm.yml` declares no
supervisor package today, so there is no existing reverse-dependency
mechanism to invert. The forward dependency (`agent-dotfiles` → supervisor)
would need to be created, most naturally the same way this repo already
depends on skill content: an `apm.yml` pinned-ref dependency, resolved into
`apm_modules`, the same mechanism `validate_lane_state_docs` (§4, §7)
already resolves `supervised-lane-loop` through. That keeps this repo's
existing pattern — "declare a pinned dependency on content authored
elsewhere" — rather than inventing a second one for this specific case.

**"Both" is the wrong answer and nothing measured here points toward it**:
no file under `scripts/supervisor/` names `agent-dotfiles` except as a
default string value (§3), never as an import or an execution path.

## 9. Sequencing with what's in flight

Re-checked against issue/PR state, not the brief's framing (some of this
has already landed since the brief was written):

- **#216** (harness identity) — **closed**, merged as `7db46f2`. Done; no blocker.
- **#198** (MCP server proposal) / **#233** (its implementation) — **closed
  / merged** as `d4ae64d`. Done, but it's the one that introduced the fresh
  hardcoded-path coupling in §4 and §7 — worth fixing (make the path
  configurable, e.g. resolve relative to the MCP config file or an env var)
  before or during extraction, since extraction is the natural point to
  stop hardcoding a same-repo-relative path across a repo boundary.
- **#212 / #225** (dispatch.sh authorship guard) — **still open**. This
  touches `dispatch.sh` inside the tree that would move. Land it before
  extraction starts, or the extraction PR inherits an in-flight review
  burden on top of the move itself.

The brief names four items; a fresh search (`gh issue list --search
"supervisor in:body" --state open`) found **nine more open issues** that
name the supervisor, beyond #179 itself and #212/#225: #215 (watchdog busy
check), #227 (`test_inbox_poll.sh` CI hang), #139 (Linux/Windows
portability, explicitly deferred), #178 (tmux plugin, §11), #52
(notification architecture), #192 (`digest.sh` test gap), #16 (the
ledger-vs-shell decision `docs/supervisor-disposition.md` was written for),
#92 (watchdog re-arm reliability), #226 (verdict-SHA rebase detection).
None of these are "mid-migration" in the sense #212/#225 is — none touch
the extraction boundary itself — but #227 is a **currently red CI test**
in the tree that would move, and #16 is a live, unresolved architectural
question about which of two supervisor implementations in this same tree
is even the right one to extract. Both are reasons to extend "after we get
it working" rather than reasons to block this plan: a bug list this long
is itself evidence the tool isn't done yet, which is the condition Jon
already attached to the timing.

## 10. What must be true before extraction starts (acceptance criteria, restated as gates)

1. **The loop keeps running.** The move must be a repo split with a pinned
   dependency added afterward (§8), not a flag day — `agent-dotfiles`'s
   cron/LaunchAgent-driven loop cannot go dark while `apm.yml` is edited
   and re-resolved.
2. **#212/#225 lands first** (§9) — the one open PR touching the moving tree.
3. **#16 has an answer, or the ledger's fate is stated explicitly** (§1.1)
   — extraction scope (1,727 running lines vs. 3,864 total) is undefined
   until then.
4. **The three hardcodes in §3 get fixed, in the new repo or before the
   move** — otherwise the new repo ships `/Users/jon` in its own `cli.py`
   and `sleepcheck.py` on day one, and `notify.sh`'s state dir remains the
   one non-overridable default in the tree.
5. **`validate_lane_state_docs` (§4, §7) has a stated fate** — deleted,
   or rewritten to fetch `lanes.sh` from the new repo — before the PR that
   removes `scripts/supervisor/lanes.sh` from `main` merges, or CI silently
   stops checking a state-drift class of bug this repo already paid to catch once (#196).
6. **CI parity** — the new repo needs its own `unittest discover` (or
   equivalent) wired before `tests/supervisor/`'s 41 files stop running
   here (§5), or 13,507 lines of test coverage goes dark mid-move.

## 11. Open questions this plan does not resolve

Per the brief, these are named, not answered:

- Repo name — the issue body notes the tool has already been called "the
  supervisor," "the tool," "the meta-harness," and "OpenClaw/Hermes" in one
  session.
- Public or private — `docs/PRD.md` and `#16`-adjacent material raise this;
  it's a docs/config bar question, not a coupling question, and out of
  scope for this measurement.
- Whether the tmux plugin (#178) ships with the extracted repo or
  separately — it's the human-facing half of the same product per the
  brief, but no code under `scripts/supervisor/` references `#178` or any
  tmux-plugin artifact today, so this measurement has nothing to add.
