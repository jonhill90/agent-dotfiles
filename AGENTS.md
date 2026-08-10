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
  can carry stale local-package registrations from any machine's history,
  not just this repo's. `apply()` fails closed on them; `status`/`doctor`
  name them; recovery is `apm uninstall -g <path> --dry-run` then
  `apm uninstall -g <path>` — never manual deletion. See README.md's
  "Stale Global Registrations and Recovery" (#14).
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

## Required Verification

Run before considering repository changes complete:

```bash
python3 scripts/validate_repository.py
python3 -m unittest discover -s tests -v
apm lock -v          # resolves both pinned skill-source refs without deploying
```

`npx skills add . --list` no longer applies here — this repository has no
local `skills/` to enumerate (#9); it correctly reports "No skills found."
Run language-specific tests when changing bundled scripts or tools.

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
  four harnesses and bills for it.
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
