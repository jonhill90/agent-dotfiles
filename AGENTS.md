# AGENTS.md

## Project

`agent-dotfiles` is Jon's versioned personal harness for AI coding agents —
dotfiles for agents. It owns canonical instructions, hooks, agents,
settings, MCP declarations, install/sync behavior, and the skill *roster*
(`settings/default-skills.txt`). Skill content is not vendored here: it is
declared as two pinned `apm.yml` dependencies on `jonhill90/skills`
(public) and `jonhill90/skills-private` (private, authenticated) — see
"Skill Sources" in `README.md` (#9). Product requirements live in
`docs/PRD.md`; the technical design in `docs/SPEC.md`.

This file is the shared repository policy. `CLAUDE.md` and
`.github/copilot-instructions.md` are committed **symlinks** to it, so each
harness reads its own filename and there is one source. Edit this file; the
other two follow with no sync step.

## Product Boundaries

- Skill content lives in `jonhill90/skills` (public) or
  `jonhill90/skills-private` (private) — this repository declares them as
  pinned dependencies and rosters names, it does not vendor a `skills/`
  directory (#9).
- The *global* `~/.apm/apm.yml` (distinct from this repo's own `apm.yml`)
  can carry stale local-package registrations, and basename collisions
  between them, from any machine's history — not just this repo's.
  `apply()` fails closed on both; `status`/`doctor` name every stale path
  and every colliding group. **Manifest identity is full-path; the local
  cache and compiled `apm:source` markers are basename-only** — a single
  `apm uninstall -g <path>` is never isolated recovery when a basename
  collision is reported. See README.md's "Stale Global Registrations and
  Recovery" (#14, #15) for the group-level recovery workflow.
- Keep canonical content out of harness-owned directories.
- Treat `.claude/` and `.github/` as repo-development configuration or
  repository automation; other harness-owned directories must not
  accumulate content.
- Do not make installation of one skill inherit the complete personal workflow.
- Keep project-specific and employer-specific material out of this repository.
- Behavioral scenarios, counter-scenarios, harness runners, results and
  transcripts, scoring and arming tools, and eval methodology belong to the
  private jonhill90/agent-evals (evidence unavailable publicly)
  repository, not here (#10). This repository retains only the narrow
  release/compatibility checks it needs for its own deployed static-context
  budget: `scripts/measure_e15.py`, `scripts/measure_context.py`, and their
  tests.
- `docs/provenance-manifest.md` stays here even though 17 of its 61 rows
  (per the #18 census) cite evidence that lives only in agent-evals: it is
  a decision ledger, not an evidence store, and `validate_roster_credit`
  in `scripts/validate_repository.py` is a live, executable consumer of
  this exact path that enforces SPEC §10.1 rule 5. The roster it guards
  (`settings/default-skills.txt`) is owned here and cannot move, so the
  check that guards it needs the manifest here too. No split (#18).

## Canonical Layout

```text
apm.yml                  # APM package manifest — also declares the two pinned
                         # skill-source dependencies (jonhill90/skills,
                         # jonhill90/skills-private), each ref pinned to a SHA
apm.lock.yaml            # resolved commit + content hash per dependency
.apm/                    # APM source tree — symlinks into the canonical dirs
instructions/
  global.instructions.md # canonical global agent instructions (≤200 lines)
  overlays/              # per-harness additions, wrapper-projected
agents/
hooks/                   # canonical hook scripts, harness-agnostic
settings/                # wrapper-owned config fragments (claude, copilot, pi, mcp)
  default-skills.txt     # skill roster, flat today; sync can scope it per
                         # harness and enforces that on all four (SPEC §4.1)
docs/
scripts/
tests/                   # unittest suite for scripts/
```

The tmux-lane supervisor core previously lived at `scripts/supervisor/` and
`tests/supervisor/` here; it moved to `jonhill90/agent-supervisor` (private)
in the Phase 1.5 split (#179).

Projection is installer-owned (`apm install -g` + `scripts/sync.py apply`).
The former committed symlink matrix (`.claude/skills`, `.codex/skills`, …)
is retired; validation errors if any reappear.

## Skill Authoring and Sourcing

Decide placement first — see "Where a Skill Belongs" in `README.md`. The
§10.1 evidence bar governs the **default roster**, not every skill
written. A project skill lives in that project, needs no eval, no
scenario and no manifest row. A skill from someone else is reached with
`npx skills use` or declared as a pinned dependency (SPEC §3.1); it is
never vendored here.

**Authoring a skill's content happens in `jonhill90/skills` (public) or
`jonhill90/skills-private` (private) — never in this repository (#9).**
Each has its own `SKILL.md` authoring contract (name/directory match,
portable frontmatter, 500-line cap, references/ for detail, deterministic
scripts, imperative instructions, model-invoked vs. user-invoked framed in
`description`) and its own validator/CI. Follow that repository's
`AGENTS.md`, not this section, when writing skill content.

For the same reason this repository carries no path-scoped skill-authoring
instruction file. It had one — `.github/instructions/skill-authoring.instructions.md`,
`applyTo: 'skills/**/*.md'` — which bound to nothing from the moment #9
removed the `skills/` directory, and stated a second, divergent copy of a
contract the paragraph above sends you elsewhere to read (#28). Every
`.github/instructions/*.instructions.md` must match at least one tracked
file; `tests/test_instruction_globs.py` enforces it.

**Rostering an existing skill happens here:**

1. Add its name to `settings/default-skills.txt`.
2. If it was just added upstream, bump that dependency's `ref:` in
   `apm.yml` to the new commit — pinned refs never move on their own
   (§9 reproducibility requirement; enforced by
   `validate_skill_source_pins` in `scripts/validate_repository.py`).
3. Run `python3 scripts/validate_repository.py` and
   `python3 -m unittest discover -s tests -v`.

Harness-specific extensions require an explicit compatibility note and must not
replace the portable workflow.

## Agent Authoring

- Store reusable agent definitions in `agents/<name>.md`.
- Use kebab-case filenames.
- Keep harness-specific projections or schemas in adapter directories.
- Validate tool lists as YAML arrays where the target format requires arrays.

## Workflow

1. Orient in the repository and inspect current changes.
2. Define observable success criteria.
3. For behavioral code, use red-green-refactor.
4. Make the smallest coherent change.
5. Run repository validation and relevant script tests.
6. Review the diff for generated files, broken links, and source duplication.

## Work Tracking

- GitHub Issues on this repository is the tracking surface for open work —
  `gh issue list`. Conventions and the label taxonomy:
  `docs/work-tracking.md`. This repo does not track work in Linear or any
  other tracker.
- `docs/SPEC.md` §11–§13 and `docs/provenance-manifest.md` stay canonical.
  An issue cites its section rather than restating it; when an issue and
  the SPEC disagree, the SPEC wins and the issue is corrected.
- Parked decisions get an issue naming the revisit trigger. Finished work
  does not get one — history lives in git and the provenance manifest.
- Close with `Fixes #N` in the PR body. Branch with a type prefix
  (`docs/`, `feat/`, `chore/`); CI gates on `pull_request`.

## Merging PRs you did not author

When more than one agent lane works this repository at once, every lane
pushes through the same shared GitHub login — `gh pr review --approve`
is refused as self-review regardless of who is actually asking, so a
real cross-lane review has to be recorded another way: a reviewing lane
posts a plain PR comment, not a GitHub review object, carrying

```
Verdict: APPROVE            (or REQUEST CHANGES, with specifics)
Review-Lane: <reviewing lane's own name>
Reviewed-SHA: <the exact head commit SHA reviewed>
```

and the PR's own body states which lane opened it:

```
Author-Lane: <authoring lane's own name>
```

Before merging a PR you did not author, run

```bash
python3 scripts/pr_verdict.py --repo <owner/name> --number <N>
```

and merge only on exit code `0` (`approved`) — every other exit code
(`1` rejected, `2` no verdict on record, `3` unknown/unresolved: same
lane, stale SHA, a missing trailer) means do not merge, full stop, same
as CI being red. See `scripts/pr_verdict.py`'s own doc comment for
exactly what this checks and why: it is a port of
`jonhill90/agent-supervisor`'s `verdict.py`/`verdict-independence.sh`,
following the shape `jonhill90/skills#255` already adapted (this
repository, like `skills`, is Python with a stdlib `tests/` suite —
`jonhill90/agent-tui#107`'s Go port does not transfer), because this
repository has no lane ledger to resolve authorship from independently
— `Author-Lane:`/`Review-Lane:` are both self-declared, the same trust
model either side already has.

**Not wired into CI, deliberately.** This repository's own CI
(`.github/workflows/validate.yml`) never merges a PR — every job here
validates content and exits; merging is always a separate `gh pr merge`
invocation an operator or an agent lane runs directly, outside any
workflow. There is no merge-time CI job to attach this gate to without
inventing one that does not otherwise exist; `scripts/pr_verdict.py` is
the check that invocation must run first, by convention stated here —
the same shape `skills#255` itself documented, and the same posture
`agent-tui#107` stated plainly for its own repository rather than
implying an enforcement that did not exist.

## Required Verification

Run before considering repository changes complete:

```bash
python3 scripts/validate_repository.py
python3 -m unittest discover -s tests -v
apm lock -v          # resolves both pinned skill-source refs without deploying
```

`npx skills add . --list` no longer applies here — this repository has no
*tracked* `skills/` to enumerate (#9); it correctly reports "No skills
found" in a checkout that has never resolved dependencies. That changes
once `apm lock -v` or `apm install -g` has run: both materialize a local,
gitignored `apm_modules/` at the repo root (per `apm.yml`'s `skills: ["*"]`
pin on each dependency, currently 24 skills from `jonhill90/skills` plus 1
fixture from `jonhill90/skills-private`), and `npx skills add .` walks
into it and enumerates those — the full upstream set, not
`settings/default-skills.txt`'s 13-name active roster. Read the roster
file for what actually ships; treat `npx skills add . --list` output as
"what's resolved on disk right now," not as this repository's roster
(#264 step 5).
Run language-specific tests when changing bundled scripts or tools.

Citing a newly-opened issue by bare number (`#N`) in a tracked `.md` fails
`tests/test_cross_repo_references.py` until the manifest it checks against
is refreshed in the same change:

```bash
python3 scripts/refresh_known_references.py
```

`tests/fixtures/reference_guard_allowlist.json` is for genuinely
unresolvable historical references only — a stale manifest is not that;
refresh it instead of adding the number there (#34).

## Recording Figures

Every number written into `docs/` is either **measured** — a command was
run and its output read — or **inferred** from a setting, a prediction, or
arithmetic. Write which. An inferred figure that reads as measured is the
most common defect in this repository's record, and it is always
self-flattering: it makes a result look stronger than the evidence
supports.

Four instances, all corrected after the fact:

- `~352 tokens saved` by disabling two plugins — inferred from
  `enabledPlugins: false`. The plugin's skills load anyway; only
  uninstalling removes them.
- `7 FAIL / 1 INVALID` as the E20 baseline — a re-score that a later guard
  *would have* produced. The measurement is 8 FAIL.
- `six candidates fetched and read` — five were read; the sixth failed to
  install and is unmeasured.
- `~40 stale figures remaining` — arithmetic on a round number. No list
  existed until one was built, and the real count was two.

Rules:

- State the instrument beside the number. `measure_e15.py` reads deployed
  files under `$HOME` and reports declared state; `/context` reports what
  the model was actually sent, free, on Claude Code only; `claude plugin
  details <name>` prices one plugin, free; `measure_context.py` asks all
  four harnesses and bills for it. Read its codex column with care (#44):
  codex's `turn.completed.input_tokens` is the turn's *cumulative* input
  across every model request it took, so a probe turn where the agent
  called a tool first reports a billing sum, not a context size. Measured
  2026-08-11 over three runs: the per-request context was identical
  (19,787) every time while the reported total was 62,674 / 41,816 /
  41,872. The original 19,501 -> 40,981 swing is consistent with that
  mechanism — 19,501 is within 1.4% of the measured context — but those
  payloads predate #103 and are gone, so applying it to them is inference,
  not a reading. The script now blanks that column for a multi-request
  turn rather than printing the sum, so a codex figure that prints is a
  real one-request reading. That makes the column honest, not yet usable:
  the deployed session-start memory rule makes the probe use tools on most
  runs, so expect it to be blank, and read the real number from the first
  `token_count` event's `last_token_usage` in that thread's rollout log
  under `$CODEX_HOME/sessions`. Until the script reads that field itself
  (#44), a codex figure is a per-run reading, not a column you can diff.
- A prediction, a counterfactual, and a re-score are not results. Record
  them where they belong — as a note on the results file, not as the
  result.
- Do not quote a count for a set you have not enumerated. Build the list.
- When correcting a figure, say what it was and why it was wrong. A
  silently improved number teaches nothing and cannot be audited.

## Distribution

- Use `npx skills` for individual skill discovery and installation.
- Use APM as the sync backbone: the repo is an APM package installed at
  user scope (`apm install -g`), with a thin wrapper for what APM does
  not own (SPEC §7).
- Do not hand-maintain a growing matrix of harness skill copies.
- Generated package or harness output must identify its canonical source.

## tmux is not a database

Jon, twice and emphatically: **"TMUX IS NOT A DATABASE."**

tmux is for persistent terminals, multiplexing, and plugins. Those are the
reasons it was chosen and they are not in question.

**The test is authorship.** Did *this system* write the value, or did tmux or the
OS produce it as a byproduct?

- **We wrote it** → it is a **record**, and records belong in the ledger.
  Whether a lane is available, who owns a task, that work completed.
- **tmux or the kernel produced it** → it is a **measurement**, and measurements
  may be read freely. `#{window_activity}`, `#{pane_in_mode}`, `#{pane_pid}`,
  and the pane's own process via `ps`.

Authorship is the test rather than "decided versus observed" because that
phrasing does not resolve `#{window_activity}`: tmux persists it, it describes
the past, and reading it is nonetheless correct — it is tmux's value, not ours.

A window name may be a *projection* of a record. It may not be the record.

**This principle, and the case study that motivated it, now live with the
code they describe.** The call-site migration table (#174), the `#102`
incident (dispatch capacity silently falling to zero while lanes sat idle,
repaired by editing the "database" with `tmux rename-window`), and
`loop-tick.md`'s renaming instructions were all about `scripts/supervisor/`
and `tests/supervisor/`, which moved to `jonhill90/agent-supervisor`
(private) in the Phase 1.5 split (#179). The detailed evidence belongs
there now; this section keeps only the rule itself, for any future tmux
usage written directly in this repository (installer, hooks, sync).

Do not read this rule as licence to stop renaming windows in the code that
still does so — that code just isn't in this repository anymore.

It is also why "no tmux on Windows" costs a state store as well as a terminal.

## Guardrails

Do:

- use current primary documentation for changing formats and tools;
- install skills selectively;
- preserve progressive disclosure;
- keep generic improvements upstream here;
- document compatibility assumptions.

Do not:

- copy employer-owned content into this repository;
- add duplicate skill identities;
- encode one harness as the portable source model;
- load every skill into every workflow by default;
- claim validation without running the commands above;
- write an inferred figure as if it were measured (see Recording Figures).
