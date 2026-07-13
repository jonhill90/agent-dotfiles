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
| Sync backbone | microsoft/apm | Adopt (pinned) | Live-trial verified: user-scope install, global compile with marker safety, lockfile, drift audit, content scanning ([harness engineering](harness-engineering.md); evidence `8a222ce`, `dff03d0`) |
| Pi projection, settings merge, teardown | self | Author (`scripts/sync.py`) | Outside APM's primitive set; APM has no Pi target ([harness engineering](harness-engineering.md); evidence `065bc9d`) |
| Sync mirror mechanics, pointer instructions, terse skill style | steipete/agent-scripts | Adapt (patterns only) | Personal upstream content and no consumer versioning; adopted only the patterns (research archive `106e69c`) |
| Behavioral-layer selection rule | owner decision, 2026-07-12 grilling | Adopt (baseline-first) | Baseline = canonical instructions only; components added only when a failing eval justifies them, smallest candidate first; the eval matrix is the distiller (SPEC §4) |
| Enforcement chassis (bootstrap hook, skill-check contract, Pi/Codex shims) | obra/superpowers 6.1.1 | **Reject** (reversed 2026-07-12; was Adopt) | Superpowers dropped entirely — dependency, hook, and skills. Its skills remain parts-bin candidates in gap-fill auditions only. Enforcement hooks are auditioned solely on E14-class baseline failures |
| Intent/grilling stage | baseline instructions | Adopt baseline; reject extra component | E3/E5 passed across tested v1 pairs; no gap-fill justified ([baseline results](../evals/results/2026-07-12-baseline-day.md)) |
| TDD stage | baseline instructions | Adopt baseline; reject extra component | E6/E7 passed in authoritative interactive mode; no gap-fill justified ([baseline results](../evals/results/2026-07-12-baseline-day.md)) |
| Handoff/complete stage | baseline instructions | Adopt baseline; reject extra component | E13 passed and a cold session resumed successfully ([baseline results](../evals/results/2026-07-12-baseline-day.md)) |
| Process-owning SDD frameworks (spec-kit, OpenSpec, BMAD, kin) | — | Reject (family) | PRD non-goal: components stay small, composable, individually removable; reaffirmed 2026-07-12 |
| `ms-learn`, `ms-learn-cli` skills + `tools/mslearn` Go CLI | Jon (authored) | Reject (cut 2026-07-12, deleted M1.5) | Skill-noise reduction, owner-named; git history is the archive |
| `lint-agents` | Jon (authored) | Reject (cut 2026-07-12, deleted M1.5) | One-trick check; belongs in `scripts/validate_repository.py`, not an agent-facing skill |
| `validate-skill` | Jon (authored) | Reject (folded into `create-skill`, M1.5) | One owner for skill authoring+validation; `create-skill` already carried the validation workflow |
| `context7` skill | Jon (authored) | Reject (cut 2026-07-12, deleted M1.5) | Declared MCP server covers it on MCP-capable harnesses; accepted as unavailable on Pi |
| `youtube-transcript` | Jon (authored) | Reject (cut 2026-07-12, deleted M1.5) | Occasional-use utility, not workflow; restorable from history |
| `closing-the-loop`, `primer` | Jon (authored) | Reject from default; retain as public opt-in | Baseline E1/E4/E9/E10 passed without them. `settings/default-skills.txt` excludes both while `skills/` keeps them independently installable. |
| Kept tool-skill roster (`gh-cli`, `az-devops`, `linear`, `obsidian`, `using-tmux`, `create-skill`) | Jon (authored) | Adopt (roster cut 2026-07-12) | Daily drivers; each tool skill has acceptance checks in `evals/acceptance/`; displaceable only per the two-track rule |
| Obsidian access CLI | official Obsidian CLI (app ≥1.12) | Adopt official (owner override 2026-07-12) | Verified hands-on on 1.12.7 (create/read/append/search/property); optional for the skill and not a memory dependency ([memory](memory.md); evidence `b752300`) |
| `using-tmux` | Jon (authored) vs community candidates | Open (V7 acceptance checks) | Stays until a community skill passes the same acceptance checks with equal-or-fewer tokens |
| Skill-authoring skill | Jon's `create-skill` | Author (keep) | One owner per stage; superpowers `writing-skills` (6.6k t) and mattpocock `writing-great-skills` rejected as duplicates |
| Memory store | Personal Obsidian vault + direct files | Adopt | Plain markdown, zero infrastructure, portable to all harnesses; vault service owns cross-machine sync and the CLI is optional ([memory](memory.md)) |
| Memory conventions skill | self | Author (shipped M4) | Contract for index + one-fact-per-note schema (SPEC §3.6) |
| Fact-schema internals: one-file-per-fact, index hook-line format, `type: user\|feedback\|project\|reference` enum | Claude Code native auto-memory (Anthropic) | Adapt (provenance corrected 2026-07-12) | Carried over from the authoring harness's own memory design, not distilled from Jon's sources — an unexamined default at adoption time. Battle-tested and E12-verified, but the type enum has never been evaluated against alternatives; revisit if M5+ shows the categories misfit. **Named alternative for that revisit: INMPARA's typed observation categories** ([decision]/[requirement]/[insight]/[limitation]/…) — they classify facts by kind-of-claim rather than subject, which changes how an agent acts on a fact |
| Typed relations (`requires`, `enables`, `solves`, …) as semantic triples in markdown | INMPARA semantic markup (Jon, 2025) | Open (benched with Graphiti) | Zero-infra knowledge-graph middle ground between untyped wiki-links and a graph DB; auditioned only if evals show search-based retrieval failing — same trigger as Graphiti, much cheaper candidate, tried first |
| Memory lint criteria | INMPARA quality-indicators checklist + Karpathy lint op | Open (deferred) | Source documents for the lint check when memory rot is demonstrated; not built before then |
| `agent/` bundle root, `facts/` directory name | self | Author | Producer-chosen names; OKF prescribes none. `agent/` justified by Obsidian writing app files to the vault root |
| Memory instruction rules: write completion-gate + read-before-recall | authored, via E12 auditions | Adopt (eval-justified 2026-07-12) | First baseline-first adoptions; CC native memory shadowed the vault until gated ([E12 results](../evals/results/2026-07-12-e12-memory-writeback.md)) |
| Pi overlay deletion gate (list-first; contradiction ⇒ STOP) | authored, via E11 audition | Adopt (eval-justified 2026-07-12) | Pi×default deleted source from a mislabeled folder — baseline day's only failure; gate passes ×2 after adoption ([baseline results](../evals/results/2026-07-12-baseline-day.md)) |
| Graphiti (Zep) | Zep | Reject (benched) | Standing graph-DB infra + MCP-only access; revisit trigger = search retrieval demonstrably failing |
| basic-memory | incumbent | Reject | Dropped by intent decision; MCP server failure mid-session with no CLI fallback (2026-07-11) |
| Process-owning framework model | spec-kit | Reject (counterexample) | PRD non-goal: components stay small, composable, individually removable |
| Instructions projection | one canonical AGENTS.md, APM-compiled root files, marker-owned `~/.claude/CLAUDE.md` | Adopt (pattern) | Every target reads an AGENTS-family surface ([harness engineering](harness-engineering.md); evidence `c089a95`) |
| Committed compatibility symlink matrix (`.claude/skills` etc.) | this repo (gen 3/4) | Reject (retire) | Installer-owned projection replaces it; PRD non-goal |
| Neutral skills path `~/.agents/skills` | Codex/Copilot/Pi convergence | Adopt | Native on 3 of 4 harnesses; wrapper guarantees it after APM installation ([harness engineering](harness-engineering.md)) |

Prior migration decisions (vibes → skills, per-skill selection basis)
remain recorded in [migration-audit.md](migration-audit.md); they are not
re-litigated here.
