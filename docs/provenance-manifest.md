# Provenance Manifest

Successor to [migration-audit.md](migration-audit.md). Every
adopt / adapt / author / reject decision for agent-dotfiles content and
tooling, with source and rationale. Open rows are closed only by eval
results files under `evals/results/`, per [SPEC.md](SPEC.md) §10.

Decision types: **adopt** (pinned dependency, unmodified) · **adapt**
(pattern taken, content reauthored) · **author** (Jon's own) · **reject**
(evaluated and declined) · **open** (awaiting evals).

| Subject | Source | Decision | Rationale / evidence |
|---|---|---|---|
| Sync backbone | microsoft/apm | Adopt (pinned) | Live-trial verified: user-scope install, global compile w/ marker safety, lockfile, drift audit, content scanning ([apm-verification](research/apm-verification.md)) |
| Pi projection, settings merge, teardown | self | Author (`scripts/sync.py`) | Outside APM's primitive set; APM has no Pi target ([apm-verification](research/apm-verification.md) Finding 2) |
| Sync mirror mechanics, pointer instructions, tools.md, terse skill style | steipete/agent-scripts | Adapt (patterns only) | Personal-to-Peter content, no consumer versioning; patterns proven ([distillation-matrix](research/distillation-matrix.md)) |
| Enforcement chassis (bootstrap hook, skill-check contract, Pi/Codex shims) | obra/superpowers 6.1.1 | Adopt (pinned) | Only cross-harness enforcement mechanism that exists, incl. Pi ([distillation-matrix](research/distillation-matrix.md)) |
| Intent/grilling skill | superpowers `brainstorming` vs mattpocock `grill-me`/`grilling` | Open | Decided by E3, E5 model-down; 70x token difference favors lean if it holds |
| TDD skill | superpowers `test-driven-development` vs mattpocock `tdd` | Open | Decided by E6, E7 |
| Handoff/complete skill | superpowers `finishing-a-development-branch` vs mattpocock `handoff` | Open | Decided by E13 |
| Skill-authoring skill | Jon's `create-skill` | Author (keep) | One owner per stage; superpowers `writing-skills` (6.6k t) and mattpocock `writing-great-skills` rejected as duplicates |
| Memory store | Obsidian vault + obsidian-cli | Adopt (pinned CLI) | Plain markdown, zero infra, vault sync solves cross-machine; CLI path portable to all four harnesses ([memory-backends](research/memory-backends.md)) |
| Memory conventions skill | self | Author | Contract for index + one-fact-per-note schema (SPEC §3.6) |
| Graphiti (Zep) | Zep | Reject (benched) | Standing graph-DB infra + MCP-only access; revisit trigger = search retrieval demonstrably failing |
| basic-memory | incumbent | Reject | Dropped by intent decision; MCP server failure mid-session with no CLI fallback (2026-07-11) |
| Process-owning framework model | spec-kit | Reject (counterexample) | PRD non-goal: components stay small, composable, individually removable |
| Instructions projection | one canonical AGENTS.md, APM-compiled root files, marker-owned `~/.claude/CLAUDE.md` | Adopt (pattern) | Every harness reads AGENTS.md-family content somewhere ([harness-baselines](research/harness-baselines.md) Finding 5) |
| Committed compatibility symlink matrix (`.claude/skills` etc.) | this repo (gen 3/4) | Reject (retire) | Installer-owned projection replaces it; PRD non-goal |
| Neutral skills path `~/.agents/skills` | Codex/Copilot/Pi convergence | Adopt | Native on 3 of 4 harnesses; APM populates it ([harness-baselines](research/harness-baselines.md) Finding 1) |

Prior migration decisions (vibes → skills, per-skill selection basis)
remain recorded in [migration-audit.md](migration-audit.md); they are not
re-litigated here.
