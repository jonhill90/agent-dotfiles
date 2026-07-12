# Technical Spec: agent-dotfiles

- **Status:** Draft v1 — 2026-07-12
- **Owner:** Jon Hill
- **Inputs:** [PRD](PRD.md), Phase 0 research
  ([APM verification](research/apm-verification.md),
  [distillation matrix](research/distillation-matrix.md),
  [memory backends](research/memory-backends.md),
  [eval scenarios](research/eval-scenarios.md),
  [Pi harness survey](research/pi-harness.md),
  [harness baselines](research/harness-baselines.md))
- **Companion artifact:** [provenance manifest](provenance-manifest.md) —
  every adopt/adapt/author/reject decision in this spec is recorded there.
- **Scope of this spec:** Phase 1 (v1) — this Mac, Claude Code + Pi, all
  five layers plus memory tooling. Later phases are constrained (the
  architecture must not preclude them) but not designed here.

## 1. Architecture Overview

One repository, `jonhill90/agent-dotfiles` (renamed in place from
`skills`), is the canonical source for all managed layers. Two mechanisms
deploy it to a machine:

```
agent-dotfiles repo
  canonical: skills/, instructions/, hooks/, agents/, mcp, settings/
  manifest:  apm.yml (self + pinned third-party deps) + apm.lock.yaml
        │
        ├── apm install -g && apm compile --global      ← backbone
        │     skills → ~/.agents/skills + ~/.claude/skills
        │     root instructions → ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md, …
        │     MCP config, agents, drift audit, lockfile, content scanning
        │
        └── sync wrapper (scripts/sync.py)              ← everything APM won't own
              Pi projection (~/.pi/agent/AGENTS.md, extensions, settings)
              Claude Code settings.json merge (permissions, hooks, model defaults)
              memory tooling config (obsidian-cli, vault conventions)
              teardown of stale generated root files (by marker)
              preflight/doctor checks
```

Design rules, from the PRD and research:

1. **APM is the backbone** (verified live,
   [apm-verification.md](research/apm-verification.md)): user-scope
   install, global compile
   with marker safety, lockfile + drift detection + content scanning come
   free. The wrapper is additive, not a fork — if APM gains a Pi target,
   the wrapper shrinks.
2. **`~/.agents/skills` is the neutral installed-skills path.** Pi, Codex,
   and Copilot read it natively; APM already copies into it and into
   `~/.claude/skills` for Claude Code. No committed symlink matrices;
   projections are installer-owned (PRD non-goal upheld).
3. **One canonical global AGENTS.md**, projected per harness (harness
   baselines Finding 5). No hand-maintained per-harness instruction trees.
4. **CLI-first capability rule** (Pi survey Finding 4): every first-class
   capability must work through a CLI-backed skill. MCP is a per-harness
   enhancement, never the only access path.
5. **Per-harness thinning is a requirement** (harness baselines Finding
   3): Claude Code gets the thinnest static layer, Pi the thickest.
6. **Evals arbitrate** (PRD rubric #5): behavioral-layer conflicts are
   settled by the E1–E16 scenarios, not by this spec's opinions. Where a
   conflict is still open, this spec names the incumbent and the deciding
   scenarios.

## 2. Repository Layout

```text
agent-dotfiles/
  apm.yml                  # manifest: self-package + pinned dependencies
  apm.lock.yaml            # generated, committed
  .apm/                    # APM source tree — symlinks into canonical dirs (V1 verify)
    skills -> ../skills
    instructions -> ../instructions
    agents -> ../agents
    hooks -> ../hooks
  skills/                  # canonical portable skills (unchanged; npx skills floor)
    <skill-name>/SKILL.md ...
  instructions/
    global.instructions.md # canonical global AGENTS.md content (≤200 lines)
    overlays/
      pi.md                # Pi-only overlay (thickest harness)
      claude-code.md       # CC-only overlay (thinnest; may stay empty)
  agents/                  # reusable agent definitions (unchanged)
  hooks/                   # canonical hook logic (scripts), harness-agnostic
  settings/
    claude/settings.json   # merge fragment: permissions, hooks wiring, model defaults
    pi/settings.json       # merge fragment
    mcp/servers.json       # declared MCP servers (env-var auth, no secrets)
  scripts/
    sync.py                # the wrapper (Python 3 stdlib only)
    validate_repository.py # extended with token-budget + secret checks
  evals/
    scenarios/             # E1–E16 runnable fixtures (prompt + pass criteria)
    results/               # per-run matrices: <date>-<harness>-<model>.md
  tests/                   # unittest suite (wrapper + validators)
  docs/                    # PRD, this spec, provenance manifest, research
  install.sh               # new-machine bootstrap (see §8)
```

Notes:

- `skills/` stays the public floor: individually installable via
  `npx skills add` and `apm install` (PRD distribution boundary).
- `.apm/` symlinking into canonical dirs keeps one source of truth while
  satisfying APM's package anatomy. **Verify item V1:** APM follows these
  symlinks for local-path install/pack. Fallback: `scripts/sync.py build`
  materializes `.apm/` as a copy step before `apm` runs (generated,
  gitignored, marked with canonical-source header per repo policy).
- The compatibility symlinks currently committed (`.claude/skills`,
  `.codex/skills`, …) are **retired** once the installer owns projection
  (PRD non-goal: no committed projection matrices). The repo-local
  `.claude/` remains only for repo-development settings, not content.

## 3. Layer Specs

### 3.1 Skills

- Canonical authoring unchanged (AGENTS.md policy: portable frontmatter,
  <500 lines, references/, scripts/).
- **Deployment:** `apm install -g` from the repo (local path during
  development, `jonhill90/agent-dotfiles#<tag>` on other machines) copies
  skills to `~/.agents/skills/` and `~/.claude/skills/`. Pi reads
  `~/.agents/skills/` natively — zero Pi projection for skills.
- **Third-party skills are declared, pinned dependencies** in `apm.yml`
  (`#tag` or `#sha` from day one — live-trial wart 4). Never vendored.
  v1 dependency set:
  - `obra/superpowers#v6.1.1` — behavioral chassis (see §4).
  - Individual mattpocock skills only after evals decide the duplicate
    conflicts (§4); installed per-skill, never the whole collection.
- Frozen `npx skills` copies in `~/.agents/skills` and drifted plugin
  installs on Jon's machines are replaced by managed installs during
  migration (§9) — the PRD's consolidation criterion.

### 3.2 Instructions

- **Canonical file:** `instructions/global.instructions.md` — identity,
  communication norms, memory conventions pointer, CLI-first rule.
  Universal content only; nothing harness-specific, nothing that
  duplicates a harness's native behavior. Hard limit ≤200 lines (harness
  baselines Finding 4).
- **Projection:**
  - Claude Code / Codex / Copilot: `apm compile --global` writes
    `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.copilot/AGENTS.md`
    with the APM generated-marker.
  - Pi: the wrapper writes `~/.pi/agent/AGENTS.md` = canonical content +
    `overlays/pi.md` (APM has no Pi target).
- **Overlays implement thinning.** The canonical core assumes a capable
  harness; overlays add what a harness lacks (Pi: plan-mode discipline,
  verification norms, memory bootstrapping — everything CC does natively).
  Overlay content counts against that harness's static budget (§6).
- **Hand-authored root-file conflict** (live-trial finding 2): APM skips
  files without its marker. On first install the wrapper detects a
  hand-authored `~/.claude/CLAUDE.md`, backs it up to
  `~/.claude/CLAUDE.md.pre-dotfiles`, and lets APM own the file.
  Machine-local additions go in `~/.claude/CLAUDE.local.md` (untracked),
  referenced via `@CLAUDE.local.md` import appended by the wrapper.
- Decision: APM owns the generated file directly (not the `@AGENTS.md`
  import pattern) — one fewer indirection, and marker safety plus the
  wrapper's teardown handle lifecycle. Recorded in the provenance manifest.

### 3.3 Hooks & Guardrails

- **Bootstrap/enforcement hooks:** adopted from superpowers as a pinned
  dependency — its SessionStart injection (~765 tokens) is the parity
  engine, with shipped projections for Claude Code (plugin hooks) and Pi
  (`.pi/extensions`). Not reimplemented.
- **Jon's own hooks** (validation, safety checks) live in `hooks/` as
  plain scripts; per-harness wiring is installer-owned:
  - Claude Code: wrapper merges hook entries into `~/.claude/settings.json`.
  - Pi: wrapper installs a thin extension (TS module) that shells out to
    the same `hooks/` scripts on `session_start` / `agent_end`.
  - Codex/Copilot: no hook surface (harness baselines Finding 2) —
    enforcement rides instructions + skill descriptions; E14 tests this
    degraded mode in Phase 2.
- **Verify item V2:** APM's hooks primitive at user scope (sample
  package's hooks did not reach `~/.claude/settings.json` in the live
  trial). Until verified, the wrapper owns all hook wiring.

### 3.4 MCP Configuration

- Declared in `settings/mcp/servers.json`: server name, transport,
  command/URL, required env vars. **No secrets in the repo** — env vars
  and OS keychain only; the wrapper's doctor command reports missing ones.
- Projection: APM handles Claude Code (`.mcp.json`/settings scopes) and,
  in Phase 2, Codex (`config.toml`) and Copilot. Pi gets none by design;
  every MCP-backed capability must already satisfy the CLI-first rule
  (e.g. `ms-learn-cli` covers Microsoft Learn where MCP is absent).
- v1 declared set: the servers Jon actually uses today (context7,
  deepwiki, microsoft-learn). Anything else is per-machine local config,
  not dotfiles.

### 3.5 Agents & Settings

- Agent definitions: `agents/<name>.md` (unchanged), deployed by APM's
  agents primitive to CC; other harnesses best-effort (Phase 2).
- Settings are **wrapper-owned** (outside APM's primitive set — residual
  unknown 1 in apm-verification):
  - `settings/claude/settings.json` is a merge *fragment*: permission
    allowlists, model defaults, hook wiring. The wrapper deep-merges it
    into `~/.claude/settings.json`, preserving unmanaged keys, and never
    touches `settings.local.json`.
  - `settings/pi/settings.json` merged into `~/.pi/agent/settings.json`
    the same way (skill paths, extension entries, `defaultProjectTrust`).
  - Merge is idempotent and reversible: managed keys are tracked in a
    wrapper state file (`~/.agent-dotfiles/state.json`) so `sync remove`
    can cleanly undo them.

### 3.6 Memory (tooling only)

Per [memory-backends.md](research/memory-backends.md): **Obsidian vault as
the store, obsidian-cli as the access path, a memory-conventions skill +
instruction block as the contract.** Content is never synced by this repo.

- **Vault location:** resolved per machine via `AGENT_MEMORY_VAULT` env
  var (set in shell profile by the installer prompt); no hardcoded path.
  Cross-machine sync is the vault's own job (Obsidian Sync/iCloud).
- **Schema inside the vault** (Karpathy-style index + files):
  - `agent/index.md` — the only file loaded at session start; hard cap
    200 lines / 25KB (matches CC's native memory budget). One line per
    memory: `- [title](facts/<slug>.md) — hook`.
  - `agent/facts/<slug>.md` — one fact per note; frontmatter `type:
    user|feedback|project|reference`, `created:` (absolute date),
    `source:`; wiki-links between related notes.
- **Tooling:** obsidian-cli pinned (v0.x — pin exact version); installed
  by `install.sh`; the existing `obsidian` skill is the access path; a new
  small `memory-conventions` skill (authored, ~300 tokens) owns the
  read/write contract. Works identically on all four harnesses because it
  is CLI + files.
- On Claude Code, native auto-memory continues for session-scoped recall;
  the vault is the cross-harness, cross-machine long-term layer. The
  conventions skill tells the agent which goes where (durable → vault).
- Graphiti stays benched; revisit trigger = evals show search-based
  retrieval failing (agent cannot find facts it stored), per research.
- basic-memory: removed by migration (§9).

## 4. Behavioral-Layer Composition

Per the distillation matrix — hybrid, superpowers as enforcement chassis:

| Role | Source | Status |
|---|---|---|
| Bootstrap/enforcement (skill-check contract, session hooks, Pi/Codex shims) | superpowers, pinned `#v6.1.1` | Adopt (decided — only cross-harness enforcement that exists) |
| Loop skills where no conflict (writing-plans, executing-plans, systematic-debugging, verification-before-completion, worktrees, subagent dispatch) | superpowers | Adopt via chassis |
| Intent/grilling | superpowers `brainstorming` (2.6k t) vs matt `grill-me`/`grilling` (36–205 t) | **Open — decided by E3, E5** run model-down; lean wins on rubric #1 if it passes |
| TDD | superpowers `test-driven-development` (2.5k t) vs matt `tdd` (803 t) | **Open — decided by E6, E7** |
| Skill authoring | Jon's `create-skill` | Keep one owner; superpowers `writing-skills` and matt `writing-great-skills` rejected as duplicates |
| Handoff/complete | superpowers `finishing-a-development-branch` vs matt `handoff` | **Open — decided by E13** |
| Sync mechanics, pointer instructions, tools.md, terse style | agent-scripts | Patterns only; no content dependency |
| Everything nothing upstream owns (closing-the-loop, primer, tool skills, identity) | Jon's layer | Author/keep |

Conflict-resolution procedure: install both candidates in the eval
sandbox only (never both on a live machine — rubric #3, one owner per
loop stage), run the deciding scenarios on all v1 pairs, record
winner/loser in the provenance manifest, pin the winner in `apm.yml`.

## 5. Per-Harness Projection Summary (v1)

| Layer | Claude Code | Pi |
|---|---|---|
| Skills | APM → `~/.claude/skills/` | native `~/.agents/skills/` (APM-populated) |
| Instructions | APM → `~/.claude/CLAUDE.md` (marker-owned) | wrapper → `~/.pi/agent/AGENTS.md` (core + pi overlay) |
| Hooks | superpowers plugin + wrapper-merged settings hooks | superpowers `.pi/extensions` + wrapper extension shim |
| MCP | APM → settings scopes | none (by design; CLI-first rule) |
| Agents | APM agents primitive | n/a v1 |
| Settings | wrapper merge into `~/.claude/settings.json` | wrapper merge into `~/.pi/agent/settings.json` |
| Memory | conventions skill + vault (native auto-memory stays for session scope) | conventions skill + vault (only memory Pi has) |
| Static thickness | thinnest (native plan mode, verification, memory) | thickest (overlay carries the loop) |

Phase 2 adds the Codex/Copilot columns; their four hands-on verify items
from harness-baselines carry forward unchanged.

## 6. Static Context Token Budget

Budget answers PRD open question 2. **Measurement method:** bytes/4 of
every file loaded at session start (same method as the research);
enforced by `scripts/validate_repository.py`; verified live by E15.

| Component | Budget (tokens) |
|---|---|
| Canonical global instructions | ≤ 2,000 (≈200 lines) |
| Per-harness overlay (worst case: Pi) | ≤ 1,500 |
| Bootstrap hook injection (superpowers) | ≤ 1,000 (measured 765) |
| Memory index (vault `agent/index.md`) | ≤ 1,500 |
| Installed-skill descriptions (aggregate frontmatter in system prompt) | ≤ 2,000 |
| **Total static, thickest harness** | **≤ 8,000** |

Everything procedural loads dynamically (progressive disclosure). The
validator fails the build if canonical files exceed their line/token
caps; the skill-description aggregate is checked against the declared
dependency set in `apm.yml`.

## 7. Sync Wrapper (`scripts/sync.py`)

Python 3, stdlib only (the repo already standardizes on Python for
scripts/tests; stdlib-only keeps the new-machine bootstrap dependency-free
beyond `uv`). Idempotent throughout — modeled on the agent-scripts
`sync-skills` pattern (pattern adoption, no content).

Commands:

- `sync apply` — full pipeline: preflight → `apm install -g` →
  `apm compile --global` → post-compile cleanup → Pi projection →
  settings merges → state file update.
- `sync status` — drift report: `apm audit` + wrapper-owned surfaces
  (settings keys, Pi files, root files vs marker) vs `state.json`.
- `sync doctor` — environment checks: required CLIs present (apm, node,
  obsidian-cli, pi if expected), env vars set (`AGENT_MEMORY_VAULT`,
  MCP auth vars, `APM_COPILOT_COWORK_SKILLS_DIR` pinned — live-trial
  wart 2), trust state.
- `sync remove` — reverse everything `state.json` recorded.

Wrapper-owned jobs (the APM live-trial "wart list" verbatim):

1. **Stale teardown** — after compile, remove marker-bearing root files
   for harnesses no longer targeted (wart 1) and for harnesses Jon
   doesn't use (kiro, hermes, windsurf…) (wart 3). **Verify item V3:**
   whether `targets:` in `~/.apm/apm.yml` scopes global compile; if yes,
   pin targets there instead of cleaning up after.
2. **Pi projection** — `~/.pi/agent/AGENTS.md`, extension shim install,
   settings merge. **Verify item V4:** local-extension install mechanics
   (`pi install <path>` vs settings `extensions` entry) and that
   superpowers' package installs on Pi 0.80.x.
3. **Settings merges** with state tracking (§3.5).
4. **First-run adoption** of hand-authored root files (§3.2).

## 8. New-Machine Bootstrap (`install.sh`)

The PRD's primary success criterion. One command sequence, target ≤15
minutes (E16):

```bash
git clone https://github.com/jonhill90/agent-dotfiles ~/.agent-dotfiles-src
cd ~/.agent-dotfiles-src && ./install.sh
```

`install.sh` (macOS v1; Phase 3 generalizes):

1. Ensure `uv` (installs if missing) → `uv tool install apm` (pinned).
2. Ensure obsidian-cli (pinned) on PATH.
3. Prompt once for machine-local values (`AGENT_MEMORY_VAULT`, MCP env
   vars) → write shell-profile block + untracked local override file.
4. `python3 scripts/sync.py apply`.
5. `python3 scripts/sync.py doctor` — print pass/fail summary.

Acceptance = E16: after install, E14 (skill triggering), E12 (memory
write-back), E15 (token budget) all pass on the fresh machine.

## 9. Migration Plan (existing machines / this repo)

1. Rename repo to `jonhill90/agent-dotfiles` (GitHub rename; history and
   backup branches preserved; old URLs redirect).
2. Restructure per §2: add `apm.yml` + `.apm/` symlinks, `instructions/`,
   `settings/`, `evals/`; retire committed compatibility symlinks once
   `sync apply` replaces them.
3. On each existing machine, before first `sync apply`:
   - remove frozen `npx skills` copies in `~/.agents/skills` (wrapper
     preflight detects and lists them; removal is confirmed, not silent);
   - uninstall drifted superpowers plugin install (5.1.0) — replaced by
     the pinned dependency;
   - remove basic-memory configuration;
   - back up hand-authored `~/.claude/CLAUDE.md` (§3.2).
4. Secret scan runs in validation from the first commit of the new layout
   (public repo; PRD privacy model).

## 10. Eval Mechanics (v1)

Answers PRD open question 3. Manual by design — no automation before the
scenarios prove they discriminate (eval-scenarios doctrine).

- `evals/scenarios/E<nn>-<slug>/` — one directory per scenario: `prompt.md`
  (verbatim prompt + setup steps), `criteria.md` (observable PASS/FAIL),
  fixture files where needed (E2, E6, E7, E9 need rigged repos).
- Runner protocol: fresh session in the target harness×model pair, run
  the prompt, score against criteria. A pair passes a stage when all its
  scenarios pass **twice consecutively**.
- Results: `evals/results/<date>-<harness>-<model>.md` — one matrix per
  run, committed. The distillation-matrix conflicts are closed only by
  results files referenced from the provenance manifest.
- v1 pairs: Claude Code×Fable (baseline), Claude Code×Sonnet, Pi×default,
  Pi×Sonnet-class.
- Thinning check: E3/E9 on Claude Code×Fable with the behavioral layer
  OFF — if native behavior passes, the corresponding overlay/static
  content stays out of the CC projection.

## 11. Verification Items (carry into implementation)

| # | Item | Blocking? |
|---|---|---|
| V1 | APM follows `.apm/` symlinks for local-path install/pack | **Verified 2026-07-12** (APM 0.24.1 live test): in-package symlinks (`.apm/skills -> ../skills`, target inside the package root) are dereferenced and the skill deploys to both `~/.agents/skills` and `~/.claude/skills`; symlinks escaping the package root are rejected with "Local install aborted". The §2 layout works as specified; no build-step fallback needed |
| V2 | APM hooks primitive at user scope | No — wrapper owns hook wiring until proven (§3.3) |
| V3 | `targets:` in `~/.apm/apm.yml` scopes global compile | No — cleanup fallback specified (§7) |
| V4 | Pi local-extension install mechanics; superpowers on Pi 0.80.x | Yes for Pi hooks — resolve before M3 (§12) |
| V5 | (Phase 2) Copilot CLI MCP path, `~/.copilot/AGENTS.md`, `~/.agents/skills` symlink handling; Codex hook mechanism | No — Phase 2 |

## 12. Milestones (Phase 1)

| M | Deliverable | Done when |
|---|---|---|
| M1 | Repo rename + layout migration (§2, §9.1–2) | validation suite green on new layout; `npx skills add . --list` still resolves |
| M2 | APM package works | `apm install -g <repo-path>` deploys skills to both paths; `compile --global` writes marker-owned root files |
| M3 | Wrapper v1 | `sync apply/status/doctor/remove` pass unit tests; Pi surface fully projected (V4 resolved) |
| M4 | Memory tooling | vault conventions live; E12 passes on this Mac in CC and Pi |
| M5 | Evals run | E1–E15 scored for all four v1 pairs; open conflicts (§4) closed in provenance manifest |
| M6 | New-machine test | E16 passes on a clean macOS user account/VM for CC + Pi |

Phase 1 exit = PRD success criteria: M6 (primary), M5 parity matrix
(secondary), §9.3 consolidation complete on Jon's machines (secondary).
