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
| Behavioral-layer selection rule | owner decision, 2026-07-12 grilling | Adopt (baseline-first) | Baseline = canonical instructions only; components added only when a failing eval justifies them, smallest candidate first; the eval matrix is the distiller (SPEC §4) |
| Enforcement chassis (bootstrap hook, skill-check contract, Pi/Codex shims) | obra/superpowers 6.1.1 | **Reject** (reversed 2026-07-12; was Adopt) | Superpowers dropped entirely — dependency, hook, and skills. Its skills remain parts-bin candidates in gap-fill auditions only. Enforcement hooks are auditioned solely on E14-class baseline failures |
| Intent/grilling stage | baseline instructions; lean skills as gap-fill candidates | Open (baseline-gated) | Auditioned only if E3/E5 fail at baseline; smallest fix wins |
| TDD stage | baseline instructions; lean skills as gap-fill candidates | Open (baseline-gated) | Auditioned only if E6/E7 fail at baseline |
| Handoff/complete stage | baseline instructions; lean skills as gap-fill candidates | Open (baseline-gated) | Auditioned only if E13 fails at baseline |
| Process-owning SDD frameworks (spec-kit, OpenSpec, BMAD, kin) | — | Reject (family) | PRD non-goal: components stay small, composable, individually removable; reaffirmed 2026-07-12 |
| `ms-learn`, `ms-learn-cli` skills + `tools/mslearn` Go CLI | Jon (authored) | Reject (cut 2026-07-12, deleted M1.5) | Skill-noise reduction, owner-named; git history is the archive |
| `lint-agents` | Jon (authored) | Reject (cut 2026-07-12, deleted M1.5) | One-trick check; belongs in `scripts/validate_repository.py`, not an agent-facing skill |
| `validate-skill` | Jon (authored) | Reject (folded into `create-skill`, M1.5) | One owner for skill authoring+validation; `create-skill` already carried the validation workflow |
| `context7` skill | Jon (authored) | Reject (cut 2026-07-12, deleted M1.5) | Declared MCP server covers it on MCP-capable harnesses; accepted as unavailable on Pi |
| `youtube-transcript` | Jon (authored) | Reject (cut 2026-07-12, deleted M1.5) | Occasional-use utility, not workflow; restorable from history |
| `closing-the-loop`, `primer` | Jon (authored) | Open (baseline-gated, benched M1.5) | Kept in repo, removed from the default/baseline stack; earn installation via E1 (primer) and E4/E9/E10 A/B (closing-the-loop) like any candidate |
| Kept tool-skill roster (`gh-cli`, `az-devops`, `linear`, `obsidian`, `using-tmux`, `create-skill`) | Jon (authored) | Adopt (roster cut 2026-07-12) | Daily drivers; each tool skill has acceptance checks in `evals/acceptance/`; displaceable only per the two-track rule |
| Obsidian access CLI | official Obsidian CLI (app ≥1.12) | Adopt official (owner override 2026-07-12; reversed same-day research verdict) | Jon's call; verified hands-on on 1.12.7 (create/read/append/search/property). Does NOT auto-launch the app — errors when closed. Memory backend consequently drops all CLI dependency: direct file operations. Third-party (Yakitrak) removed from machine ([obsidian-cli-v6 addendum](research/obsidian-cli-v6.md)) |
| `using-tmux` | Jon (authored) vs community candidates | Open (V7 acceptance checks) | Stays until a community skill passes the same acceptance checks with equal-or-fewer tokens |
| Skill-authoring skill | Jon's `create-skill` | Author (keep) | One owner per stage; superpowers `writing-skills` (6.6k t) and mattpocock `writing-great-skills` rejected as duplicates |
| Memory store | Obsidian vault + obsidian-cli | Adopt (pinned CLI) | Plain markdown, zero infra, vault sync solves cross-machine; CLI path portable to all four harnesses ([memory-backends](research/memory-backends.md)) |
| Memory conventions skill | self | Author (shipped M4) | Contract for index + one-fact-per-note schema (SPEC §3.6) |
| Memory instruction rules: write completion-gate + read-before-recall | authored, via E12 auditions | Adopt (eval-justified 2026-07-12) | First baseline-first adoptions; CC native memory shadowed the vault until gated ([E12 results](../evals/results/2026-07-12-e12-memory-writeback.md)) |
| Graphiti (Zep) | Zep | Reject (benched) | Standing graph-DB infra + MCP-only access; revisit trigger = search retrieval demonstrably failing |
| basic-memory | incumbent | Reject | Dropped by intent decision; MCP server failure mid-session with no CLI fallback (2026-07-11) |
| Process-owning framework model | spec-kit | Reject (counterexample) | PRD non-goal: components stay small, composable, individually removable |
| Instructions projection | one canonical AGENTS.md, APM-compiled root files, marker-owned `~/.claude/CLAUDE.md` | Adopt (pattern) | Every harness reads AGENTS.md-family content somewhere ([harness-baselines](research/harness-baselines.md) Finding 5) |
| Committed compatibility symlink matrix (`.claude/skills` etc.) | this repo (gen 3/4) | Reject (retire) | Installer-owned projection replaces it; PRD non-goal |
| Neutral skills path `~/.agents/skills` | Codex/Copilot/Pi convergence | Adopt | Native on 3 of 4 harnesses; APM populates it ([harness-baselines](research/harness-baselines.md) Finding 1) |

Prior migration decisions (vibes → skills, per-skill selection basis)
remain recorded in [migration-audit.md](migration-audit.md); they are not
re-litigated here.
