# AGENTS.md

## Project

`agent-dotfiles` is Jon's versioned personal harness for AI coding agents —
dotfiles for agents. Portable Agent Skills remain individually installable;
canonical instructions, hooks, agents, settings, and MCP declarations are the
other managed layers. Product requirements live in `docs/PRD.md`; the
technical design in `docs/SPEC.md`.

This file is the shared repository policy. `CLAUDE.md` and
`.github/copilot-instructions.md` are committed **symlinks** to it, so each
harness reads its own filename and there is one source. Edit this file; the
other two follow with no sync step.

## Product Boundaries

- Keep `skills/` portable and independently installable.
- Keep canonical content out of harness-owned directories.
- Treat `.claude/` and `.github/` as repo-development configuration or
  repository automation; other harness-owned directories must not
  accumulate content.
- Do not make installation of one skill inherit the complete personal workflow.
- Keep project-specific and employer-specific material out of this repository.

## Canonical Layout

```text
apm.yml                  # APM package manifest (deploys the repo at user scope)
.apm/                    # APM source tree — symlinks into the canonical dirs
skills/
  <skill-name>/
    SKILL.md
    scripts/
    references/
    assets/
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
tests/                   # unittest suite + evals/ (scenarios, harness, results)
```

Projection is installer-owned (`apm install -g` + `scripts/sync.py apply`).
The former committed symlink matrix (`.claude/skills`, `.codex/skills`, …)
is retired; validation errors if any reappear.

## Skill Authoring

Decide placement first — see "Where a Skill Belongs" in `README.md`. The
§10.1 evidence bar governs the **default roster**, not every skill written.
A project skill lives in that project, needs no eval, no scenario and no
manifest row. A skill from someone else is reached with `npx skills use`
or declared as a pinned dependency (SPEC §3.1); it is never vendored here.

- Use `skills/<name>/SKILL.md`.
- Match the directory name and frontmatter `name`.
- Use lowercase letters, digits, and hyphens; maximum 64 characters.
- Include what the skill does and when it should trigger in `description`.
- Keep portable frontmatter to `name` and `description` by default.
- Use imperative instructions.
- Keep `SKILL.md` under 500 lines.
- Move detailed material to `references/` and link it directly from `SKILL.md`.
- Put deterministic, repeated operations in tested scripts.
- Do not add a README inside a skill directory.
- Avoid harness-specific preprocessing syntax in portable skills.
- Classify each skill as *model-invoked* (a reusable discipline the agent
  should reach on its own) or *user-invoked* (a workflow reached
  deliberately). Express the classification in `description` trigger
  wording, not in frontmatter fields — the portable field set stays
  `name` and `description`.

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
npx skills add . --list
```

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
