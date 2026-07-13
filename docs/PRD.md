# PRD: agent-dotfiles

- **Status:** Draft v1 — decisions from intent interview, 2026-07-11
- **Owner:** Jon Hill
- **Successor to:** `skills` repository identity (rename in place, history preserved)
- **Next artifact:** Distillation research report, then technical spec

## Problem

Jon's agent workflow — loop discipline, skills, instructions, hooks, MCP
configuration, agents, settings — is scattered across unmanaged surfaces:
project symlinks, frozen `npx skills` copies in `~/.agents/skills`, drifted
plugin versions (superpowers 5.1.0 installed vs 6.1.1 upstream), and setup
knowledge that exists only in memory. Setting up a new machine or a new
harness is a manual, unrepeatable exercise. Behavior differs between
harnesses and models depending on what happens to be installed where.

Four prior generations (vibes v1 infra → PRP framework → symlink projection
layer → portable skills repo) each solved part of this and were outgrown.
The constant across all four was harness engineering and loop engineering;
the missing piece was treating the whole harness as versioned, installable
personal configuration — dotfiles.

## Vision

**Dotfiles for agents.** One versioned repo that makes any machine Jon sits
at, running any supported harness, behave like *his* agent.

Grounding principle (Google "New SDLC" paper, May 2026): **Agent = Model +
Harness**, and the harness dominates observed behavior (~90%). Therefore
the harness — not the model vendor — is where Jon's agent behavior is
defined. The repo is that harness, as code.

**Behavioral parity goal:** the same workflow everywhere. Pi should work
like Claude Code. Sonnet or Kimi under this harness should *run the same
loop* as Fable under Claude Code: orient → plan → implement → verify →
complete, with the same guardrails, memory habits, and communication norms.

**Honest boundary:** harness engineering equalizes *process and guardrails*,
not raw model capability. Weaker models degrade gracefully inside the same
loop — the harness's verification gates carry more weight, not less.

**Token economy:** the agent stays a lightweight generalist that flexes
into specialist roles on demand through progressive disclosure. Static
context (loaded every session) is a hard budget; everything else loads
dynamically via skills and references.

## Primary Customer

Jon. Me-first, public-friendly: when personal-workflow needs and public-product needs conflict, personal wins. Public installability of individual skills is a preserved constraint, not the driver.

## Success Criteria

**Primary — the new-machine test:** sit at a fresh machine (or fresh
harness install), run one command, and within minutes any first-class
harness behaves like Jon's agent — same discipline, same skills, same
tools. If this fails, the project failed.

**Secondary:**

- **Parity:** scenario evals pass on every first-class harness×model pair.
- **Consolidation:** nothing agent-related on Jon's machines is unmanaged —
  no orphaned copies, no drifted versions, no memory-only setup steps.

## Scope

### Managed layers (all five, plus memory tooling)

| Layer | What the dotfiles manage |
|---|---|
| Skills | Portable Agent Skills (own + declared third-party) |
| Instructions | One canonical global AGENTS.md projected per harness |
| Hooks & guardrails | Session bootstraps, validation, safety checks, per-harness shims |
| MCP configuration | Declared servers, env-var auth, projected per harness config format |
| Agents + settings | Subagent definitions, permission allowlists, model defaults |
| Memory (tooling only) | Memory infrastructure/config on every machine; backend TBD by research. Memory *content* is data, not dotfiles — never synced by this repo in v1 |

### First-class harnesses (end state)

Claude Code, Codex, GitHub Copilot, Pi. First-class = tested, configured by
sync, breakage blocks release. Other Agent Skills–compatible harnesses:
best effort via the portable format, no dedicated adapters.

### OS support (end state)

macOS, Windows/WSL, Linux.

### Phasing

The full matrix is 4 harnesses × 3 OSes × 5+ layers. It is delivered as a
vertical slice first; the architecture must not preclude later phases, but
v1 verifies only its own slice.

- **Phase 0 — Distillation research** (see Research Phase below).
- **Phase 1 (v1) — Vertical slice:** this Mac (macOS), Claude Code + Pi,
  ALL layers managed end-to-end. New-machine test passes for these two
  harnesses.
- **Phase 2:** Codex + Copilot first-class; still macOS.
- **Phase 3:** Windows/WSL and Linux support in the sync tooling.
- **Phase 4:** Curated public bundles/profiles, if demand exists.

## Selection Rubric

No behavioral-layer or tooling winner is chosen by opinion or by what is
currently installed.

**Baseline-first rule (added 2026-07-12):** the starting stack is the
canonical instructions and nothing else. No behavioral component —
skill, hook, or framework — is adopted unless a failing eval justifies
it, and the smallest candidate that fixes the failure wins. Tool skills
use per-skill acceptance checks instead of loop evals; a community
candidate displaces a personal skill only by passing the same checks
with equal or fewer tokens loaded. Process-owning frameworks (spec-kit,
OpenSpec, BMAD, and kin) remain rejected as a family per Non-Goals.

Every candidate is scored against:

1. **Token economy** — respects the static-context budget; specialist
   knowledge behind progressive disclosure. Budget number set in the spec.
2. **Portability** — works on all four first-class harnesses; degrades
   gracefully by model.
3. **Loop coverage** — each loop stage (orient, plan, implement, verify,
   complete) has exactly one owner; no duplicate or ambiguous triggers.
4. **Maintenance ownership** — upstream-maintained > vendored > self-
   authored, at equal quality. No forking/vendoring of maintained projects.
5. **Eval-passing** — the decisive criterion: candidates are kept or cut by
   scenario evals, not by reputation.

## Research Phase (Phase 0) — Deliverables

1. **Distillation matrix.** For each source × harness layer × loop stage:
   what it recommends, token cost, portability, conflicts. Sources:
   superpowers 6.x, mattpocock/skills, agent-scripts (steipete),
   microsoft/skills, azure-skills, spec-kit (as counterexample), Anthropic
   docs (Claude Code, Agent Skills spec, engineering posts), OpenAI Codex
   docs, GitHub Copilot docs, Pi docs, Google New-SDLC paper, prior
   RESEARCH.md.
2. **Provenance manifest.** Successor to `docs/migration-audit.md`: every
   adopt / adapt / author / reject decision recorded with source and
   rationale.
3. **APM verification.** APM is the lead candidate for the sync backbone
   (manifest + lockfile + multi-harness compile + drift detection + content
   security). Must verify before commitment: (a) Pi target support or a
   viable wrapper path; (b) machine/global scope (dotfiles are ~-scoped,
   APM's model is project-scoped). If verified, custom sync code shrinks to
   a thin wrapper; if not, fall back to a custom sync tool (agent-scripts
   pattern) with APM for publishing only.
4. **Memory backend selection.** basic-memory is expected to be replaced.
   Candidates to evaluate: Obsidian CLI, Graphiti, Karpathy-style
   file-based memory, others surfaced by research. Criteria: rubric above
   plus cross-machine story and data ownership.
5. **Eval scenario set.** Per loop stage, behavioral scenarios that define
   "works like Jon's agent" (e.g., interviews before building on vague
   requests; verifies before claiming done). These become the spec's
   acceptance tests for parity.

## Distribution & Boundaries

- **Repo:** renamed to `jonhill90/agent-dotfiles`, evolved in place;
  history and backup branches preserved; GitHub redirects old URLs.
- **Public floor:** individual skills remain installable by strangers via
  `npx skills add` and `apm install`. No APM bundle/profile publishing in
  v1.
- **Privacy:** public repo; secrets externalized (env vars, OS keychain,
  untracked local overrides merged by sync). Validation includes secret
  scanning.
- **Third-party content:** declared, pinned dependencies managed by sync —
  never vendored, never ad-hoc per machine.
- **Employer boundary:** unchanged from AGENTS.md — no employer-owned
  content; employer repos are research evidence only.

## Non-Goals

- Owning the development *process* end-to-end (spec-kit model). Components
  stay small, composable, individually removable.
- Model-capability parity. The harness equalizes workflow, not judgment.
- Syncing memory content, documents, or any user data in v1.
- Supporting every harness on earth. Portable format keeps exits open;
  first-class means four.
- Hand-maintained per-harness projection trees. Projections are generated
  or installer-owned; committed symlink matrices are retired.

## Open Questions (deferred to spec, informed by Phase 0)

1. Sync tool implementation (APM wrapper vs custom; language if custom).
2. Static context token budget (number and measurement method).
3. Eval harness mechanics (how scenarios run per harness×model pair).
4. Behavioral-layer composition (superpowers vs alternatives vs authored —
   decided by rubric + evals, per Research Phase).
5. Memory backend (per Research Phase).
6. Repo layout for the renamed repository (spec proposes; must serve both
   `apm`/`npx skills` resolution and sync).

## Decision Log

### Intent interview (2026-07-11)

| Decision | Choice |
|---|---|
| Primary customer | Me-first, public-friendly |
| First-class harnesses (end state) | Claude Code, Codex, Copilot, Pi |
| Managed layers | All five + memory tooling |
| OS support (end state) | macOS, Windows/WSL, Linux |
| V1 slice | This Mac, Claude Code + Pi, all layers |
| Repo identity | Rename in place to `agent-dotfiles` |
| Privacy model | Public repo, secrets externalized |
| Process | Rubric in PRD; research decides; evals arbitrate |
| Success test | New-machine test (primary) |
| APM role | Lead candidate for sync backbone; research verifies Pi + global scope |
| Memory | Tooling in scope, backend researched; content never synced in v1 |

### Spec revision interview (2026-07-12)

| Decision | Choice |
|---|---|
| Superpowers | Dropped entirely (dependency, hook, skills); parts-bin candidate in gap-fill auditions only |
| Behavioral-layer selection | Baseline-first rule (see Selection Rubric); the eval matrix is the distiller, not framework comparison |
| Enforcement hooks | Not researched separately; auditioned only if the baseline shows E14-class failures |
| Tool-skill swaps | Per-skill acceptance checks in `evals/`; community wins on equal coverage + fewer tokens |
| Skill cuts | Propose/veto; cut = delete (git history is the archive). Named: ms-learn, ms-learn-cli, tools/mslearn |
| Obsidian access path | Official Obsidian CLI researched against memory-backend needs before any swap |
| using-tmux | Community search + acceptance checks before keep/swap decision |
| Machine migration | Superpowers 5.1.0 stays installed until baseline day (its removal is step 1 of the baseline protocol) |

### Memory format distillation (2026-07-12)

Design inputs: Karpathy's llm-wiki gist and Google OKF v0.1. INMPARA
and the Second Brain were reviewed for boundary-setting only — owner
decision: they are personal note-taking systems, not harness inputs,
and contribute nothing to the memory schema. Full analysis:
`docs/research/memory-format-distillation.md`.

| Decision | Choice |
|---|---|
| Memory vault format | OKF v0.1-conformant bundle (markdown + frontmatter; `type` required; permissive consumption) — interoperable with any OKF consumer |
| Two systems, hard boundary | Second Brain = Jon's personal notes, kept for himself, not a harness component; Agent Memory vault = agent memory. Never merged; no Second Brain/INMPARA taxonomy (stages, note typologies, MOCs) may enter the memory schema |
| Fact filenames | Semantic kebab slugs (concept = identity; update in place, never duplicate). Timestamp-ID filenames rejected for facts — they are the Second Brain's human-capture pattern |
| Timestamps | ISO 8601 with seconds, UTC, in frontmatter (`created`/`updated`) and log entries — minute precision collides for agent writers; answers YYYYMMDDHHMM-vs-HHMMSS: neither in filenames, seconds in metadata |
| Temporal layer | Append-only `log.md` (OKF/Karpathy format) — cheapest temporal reasoning; shrinks the Graphiti gap |
| Operations model | Karpathy ingest/query/lint; lint stays convention-only until evals show memory rot |
