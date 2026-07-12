# Phase 0: Behavioral-Layer Distillation Matrix

- **Date:** 2026-07-11
- **Question:** Which source(s) supply the loop-discipline layer that makes
  every harness×model pair run Jon's workflow?
- **Contenders this chunk:** superpowers 6.1.1, mattpocock/skills,
  steipete/agent-scripts. (Official vendor docs sweep = later chunk.)
- **Method:** local snapshots in `~/source/repos/skills-research/`;
  token sizes ≈ bytes/4 of SKILL.md, measured 2026-07-11.
- **Status:** preliminary scoring. Final keep/cut decisions require the
  eval scenarios (see `eval-scenarios.md`) run per harness×model pair.

## Contender profiles

### superpowers 6.1.1 (obra)

14 skills, pure process — no domain content. The only contender with a
**bootstrap mechanism**: a SessionStart hook injects `using-superpowers`
(~765 tokens) into every session, which enforces skill-checking before any
response. This is the parity engine — it works regardless of model.

| Loop stage | Skill (tokens) |
|---|---|
| Orient/intent | brainstorming (2,608) |
| Plan | writing-plans (1,773), executing-plans (647) |
| Implement | test-driven-development (2,473), subagent-driven-development (5,411), using-git-worktrees (1,868), dispatching-parallel-agents (1,661) |
| Debug | systematic-debugging (2,471) |
| Verify | verification-before-completion (1,050), requesting/receiving-code-review (706/1,595) |
| Complete | finishing-a-development-branch (1,708) |
| Meta | writing-skills (6,607), using-superpowers (765) |

- **Static cost:** ~765t/session (hook injection). Everything else on demand.
- **Portability:** best in class — shipped projections for Claude Code
  (plugin+hooks), Codex (portal package), Gemini (extension), OpenCode
  (plugin), Cursor (hooks-cursor.json), **Pi** (.pi/extensions), Windows shim
  (run-hook.cmd). Covers all four first-class targets today.
- **Ownership:** actively released (6.1.1), versioned, release notes.
- **Weaknesses:** verbose skills (2-6k tokens where Matt does the same in
  200-800); rigid tone ("NOT NEGOTIABLE") burns tokens re-asserting
  authority; overlaps Fable-era Claude Code native features (plan mode,
  verification norms) — redundant static cost on the best harness, most
  valuable on the weakest.

### mattpocock/skills

~40 skills in curated categories (engineering, productivity, in-progress,
deprecated — active lifecycle management via changesets). Philosophy
matches the PRD's non-goals: small, composable, anti-framework
(explicitly positioned against spec-kit-style process ownership).

| Loop stage | Skill (tokens) |
|---|---|
| Orient/intent | grill-me (36!), grilling (205), grill-with-docs (61), research (199) |
| Plan/spec | to-spec (768), to-tickets (1,450), triage (1,643), codebase-design (1,622), domain-modeling (856) |
| Implement | implement (108), tdd (803), prototype (699) |
| Debug | diagnosing-bugs (2,134) |
| Verify | code-review (1,685) |
| Complete | handoff (219), claude-handoff (321) |
| Meta | writing-great-skills (2,353), setup wizard (1,732) |

- **Static cost:** zero — no hook/bootstrap; relies on harness-native skill
  triggering (description matching) or explicit invocation.
- **Token economy:** best in class. grill-me at 36 tokens vs brainstorming
  at 2,608 for the same loop stage is a 70x difference.
- **Portability:** distributed via skills.sh to 70+ targets, but **no
  enforcement mechanism** — on harnesses with weak skill-triggering, the
  discipline silently doesn't fire. Setup-wizard pattern (interview →
  configure) is harness-agnostic and worth adopting regardless.
- **Ownership:** very active, versioned (changesets), large user base.
- **Weaknesses:** no hooks = no guarantee; some TS-flavored content;
  no verify-before-completion equivalent as strong as superpowers'.

### agent-scripts (steipete)

~50 skills but predominantly domain/tool skills (macOS apps, GitHub ops,
SwiftUI, releases) — **not a behavioral layer**. Its loop discipline lives
in AGENTS.MD (~2,692 tokens, always loaded), not in skills.

- **Static cost:** heavy — 2,692t of hard rules in every session.
- **Value to this project:** *patterns, not content.*
  - `sync-skills`: idempotent machine mirror w/ verified harness quirks
    (feeds the sync-wrapper spec, already cited in apm-verification.md)
  - pointer-AGENTS.md convention for downstream repos
  - `tools.md`: machine environment contract as documentation
  - terse, imperative skill style (median skill ~1k tokens)
- **Weaknesses as a dependency:** personal-to-Peter content throughout;
  no release/versioning discipline aimed at consumers; CC+Codex focus.

## Rubric scoring (1-5, preliminary)

| Criterion | superpowers | mattpocock | agent-scripts |
|---|---|---|---|
| Token economy | 3 (lean hook, fat skills) | **5** | 2 (fat static) |
| Portability w/ enforcement | **5** (hooks on 6 harnesses incl. Pi) | 3 (format-portable, no enforcement) | 2 |
| Loop coverage | **5** (every stage owned) | 4 (verify/complete thinner) | 1 (n/a — instructions, not skills) |
| Maintenance ownership | 5 | 5 | 3 |
| Eval-passing | TBD | TBD | TBD |

## Conflicts requiring a single owner (rubric rule 3)

| Loop stage | Duplicate triggers today | Resolution to test in evals |
|---|---|---|
| Intent | superpowers:brainstorming vs grill-me/grilling | Matt's grilling flow at ~1/10 the tokens; test whether it holds up model-down |
| TDD | superpowers:tdd (2,473) vs matt tdd (803) | Same discipline; test lean version for equivalent compliance |
| Skill authoring | writing-skills (6,607) vs writing-great-skills (2,353) vs Jon's create-skill | One owner; others rejected in provenance manifest |
| Handoff/complete | finishing-a-development-branch vs handoff | Different philosophies (ceremony vs terse); pick per eval |

## Preliminary synthesis (validate with evals before spec lock)

**Hybrid, with superpowers as the enforcement chassis:**

1. **Adopt superpowers' bootstrap mechanism** (session hook → skill-check
   contract) as the parity engine — it is the only proven cross-harness
   enforcement, and its Pi/Codex/Cursor/Windows shims are exactly the
   projections the PRD needs. Declared, pinned dependency.
2. **Prefer Matt-style lean skills inside the loop** where duplicates
   exist (intent/grilling, possibly TDD) — subject to eval parity when
   run on weaker models. Install individually as pinned deps, not the
   whole collection.
3. **Adopt agent-scripts *patterns*** (sync mirror mechanics, pointer
   instructions, tools.md, terse authoring style) into Jon's own layer;
   take no content as a dependency.
4. **Jon's own layer** keeps what nothing upstream owns: closing-the-loop,
   primer, tool skills (gh-cli, az-devops, linear, obsidian, ms-learn,
   context7, using-tmux), identity instructions.
5. **Per-harness conditional loading is a spec question:** Fable-era
   Claude Code natively covers part of the loop (plan mode, verification
   norms); the behavioral layer earns most of its tokens on Pi/Codex/
   Copilot and weaker models. The spec should decide whether the static
   layer thins on harnesses that provide native equivalents.

## Not yet surveyed (pending chunks)

Anthropic docs (Claude Code best practices, Agent Skills spec, context
engineering posts), OpenAI Codex docs, GitHub Copilot customization docs,
Pi docs, microsoft/skills eval patterns. These inform the *official
baseline* each harness provides, which determines how much behavioral
layer each one actually needs.
