# Technical Spec: agent-dotfiles

- **Status:** Implemented v1.3 — 2026-07-18 (Phase 2 mechanical layer
  landed; Codex/Copilot behavioral columns pending, §13)
- **Owner:** Jon Hill
- **Inputs:** [PRD](PRD.md), [harness engineering](harness-engineering.md),
  [memory](memory.md), and [behavioral evals](evals.md). Dated research is
  preserved in git history (`106e69c`, `c089a95`, `8a222ce`, `065bc9d`,
  `a4de1ac`, `e33f08b`).
- **Companion artifact:** [provenance manifest](provenance-manifest.md) —
  every adopt/adapt/author/reject decision in this spec is recorded there.
- **Scope of this spec:** Phase 1 (v1) — Claude Code + Pi, all five layers
  plus memory tooling. The shared bootstrap core is accepted on isolated
  Linux; macOS-only integration is verified separately on Jon's existing Mac.
  Later phases are constrained but not designed here.

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
              memory tooling config (vault conventions, doctor checks)
              teardown of stale generated root files (by marker)
              preflight/doctor checks
```

Design rules, from the PRD and research:

1. **APM is the backbone** (verified live; see
   [harness-engineering.md](harness-engineering.md)): user-scope install,
   global compile
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
6. **Baseline-first, evals arbitrate** (PRD Selection Rubric, 2026-07-12
   rule): the starting behavioral stack is the canonical instructions and
   nothing else. Components are added only when a failing eval justifies
   them, smallest candidate first. There is no framework comparison to
   win — the eval matrix is the distiller.

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
  tests/                   # one verification tree (layout rev. 2026-07-18)
    test_*.py              # unittest suite (wrapper + validators)
    requirements-dev.txt   # dev/CI-only dependencies
    evals/
      scenarios/           # E1–E15 runnable fixtures; E16 is the live
                           # bootstrap acceptance (docs/evals.md)
      results/             # per-run matrices: <date>-<harness>-<model>.md
  docs/                    # living product, architecture, memory, eval docs
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
  **The v1 dependency set starts empty.** A third-party skill enters only
  with evidence: a failing eval it fixes (behavioral) or a passed
  acceptance check at equal-or-fewer tokens (tool skill) — see §4 and
  §10. Installed per-skill, never whole collections.
- **Public collection is not the default install.** `skills/` contains every
  independently installable public skill. The wrapper passes repeated APM
  `--skill` filters from `settings/default-skills.txt`, so benched `primer` and
  `closing-the-loop` remain public without deploying or consuming context.
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

- **No bootstrap/enforcement hooks in the v1 baseline.** A session-start
  injection is a *candidate fix*, auditioned like any other component and
  only if the baseline run shows the failure it treats: installed skills
  not firing (E14) or the loop being skipped on weaker pairs (E3/E9
  model-down). Audition order follows smallest-first: an instruction
  line → a ~100–200-token authored injection → anything heavier. If
  nothing fails, no hook exists in v1 on any harness.
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
- Projection (Claude Code implemented 2026-07-17; Codex/Copilot
  2026-07-18): the wrapper merges the declared set into Claude Code user
  scope (`~/.claude.json` `mcpServers`) and Copilot
  (`~/.copilot/mcp-config.json`, same schema), tracking previous values in
  `state.json` so `sync remove` restores them; unmanaged servers are
  preserved. Codex gets a marker-delimited block in `~/.codex/config.toml`
  (`url` + `bearer_token_env_var` form); servers the user defines outside
  the block are never touched. Codex/Copilot projection is gated on the
  harness directory existing. Pi gets none by design; every MCP-backed
  capability must already satisfy the CLI-first rule or be accepted as
  unavailable on Pi.
- v1 declared set: the servers Jon actually uses today (context7,
  deepwiki, microsoft-learn). Anything else is per-machine local config,
  not dotfiles.

### 3.5 Agents & Settings

- Agent definitions: `agents/<name>.md` (unchanged), deployed by APM's
  agents primitive to CC; other harnesses best-effort (Phase 2).
- Settings are **wrapper-owned** (outside APM's primitive set — residual
  unknown 1 in apm-verification):
  - `settings/claude/settings.json` is a merge *fragment*. Populated v1
    content (2026-07-17): the managed plugin roster (`enabledPlugins`) and
    portable workflow preferences (`alwaysThinkingEnabled`, `effortLevel`).
    Permission allowlists and model selection stay machine-local
    (`settings.local.json` / harness-owned keys) until a portable set is
    curated — the fragment must never invent permission grants. The wrapper
    deep-merges the fragment into `~/.claude/settings.json`, preserving
    unmanaged keys, and never touches `settings.local.json`.
  - `settings/pi/settings.json` merged into `~/.pi/agent/settings.json`
    the same way (skill paths, extension entries, `defaultProjectTrust`).
  - Merge is idempotent and reversible: managed keys are tracked in a
    wrapper state file (`~/.agent-dotfiles/state.json`) so `sync remove`
    can cleanly undo them.

### 3.6 Memory (tooling only)

Per [memory.md](memory.md): **Obsidian vault as
the store, direct file operations as the access path (V6 override —
official Obsidian CLI powers the `obsidian` skill separately), a
memory-conventions skill +
instruction block as the contract.** Content is never synced by this repo.

- **Vault location:** resolved per machine via `AGENT_MEMORY_VAULT` env
  var (set in shell profile by the installer prompt); no hardcoded path.
  Cross-machine sync is the vault's own job (Obsidian Sync/iCloud).
  **The memory vault must be personal:** `sync doctor` fails if the
  path resolves under a corporate mount (`OneDrive-<Org>` pattern) —
  the employer boundary applies to memory data, and the current default
  vault on this Mac is employer-hosted (V6 machine-state finding).
- **Schema inside the vault** (v2, 2026-07-12 — an OKF v0.1-conformant
  bundle; lineage and rationale in [memory.md](memory.md)):
  - `agent/index.md` — the only file loaded at session start; hard cap
    200 lines / 25KB (matches CC's native memory budget). One line per
    memory: `- [title](facts/<slug>.md) — hook` (the hook is the
    fact's `description`).
  - `agent/log.md` — append-only history, `## YYYY-MM-DD` headings
    newest first; entries `**Create|Update|Delete** [title](facts/…) —
    reason (HH:MM:SSZ)`. The temporal layer.
  - `agent/facts/<kebab-slug>.md` — one fact per note, **semantic slug
    filenames** (concept = identity; update in place, never
    duplicate). Frontmatter: `type: user|feedback|project|reference`
    (required), `title`, `description`, `created`/`updated` (ISO 8601
    with seconds, UTC), `source`, optional `tags`. Wiki-links between
    related facts; broken links = not-yet-written facts (OKF §5.3).
  - Consumption is permissive (OKF §9): malformed facts are linted,
    never rejected. Lint (contradictions, stale facts, orphans, index
    drift) stays convention-only unless M5 evals show memory rot.
- **Access path (V6 resolved, owner override 2026-07-12):** the memory
  contract itself uses **direct file operations** on the vault (read,
  write, grep) — zero dependencies, works on every harness and headless
  context by definition. The `obsidian` skill wraps the **official
  Obsidian CLI** (app ≥1.12, verified hands-on) for richer operations
  when the app is running; the CLI errors when the app is closed, so it
  is never a memory-path dependency
  (hands-on evidence: commit `b752300`). `install.sh` checks the
  installer version and CLI registration instead of installing a
  third-party binary. A new
  small `memory-conventions` skill (authored, ~300 tokens) owns the
  read/write contract. Works identically on all four harnesses because it
  is CLI + files.
- On Claude Code, native auto-memory continues for session-scoped recall;
  the vault is the cross-harness, cross-machine long-term layer. The
  conventions skill tells the agent which goes where (durable → vault).
- Graphiti stays benched; revisit trigger = evals show search-based
  retrieval failing (agent cannot find facts it stored), per research.
- basic-memory: removed by migration (§9).

## 4. Behavioral-Layer Composition (baseline-first, revised 2026-07-12)

Superpowers is dropped entirely — dependency, hook, and skills (PRD
decision log addendum). There is no chassis and no framework
head-to-head. The behavioral layer is *grown from a measured baseline*:

1. **Baseline = canonical instructions only.** The ~700-token
   `global.instructions.md` (plus the Pi overlay on Pi) already encodes
   the loop: orient → plan → implement → verify → complete. No
   behavioral skills installed, no hooks, no session injections.
2. **Baseline run:** execute E1–E15 on all v1 harness×model pairs with
   that stack. Whatever passes needs nothing — native harness behavior
   plus instructions already cover it.
3. **Gap-fill auditions:** for each failing scenario, audition the
   smallest candidate that plausibly fixes it, re-running only that
   scenario:
   - a sentence in the canonical instructions or a harness overlay;
   - a lean skill (community — e.g. mattpocock's 36–800-token process
     skills — or authored; superpowers' skills are parts-bin candidates
     here, nothing more);
   - a session-start injection (~100–200 tokens, authored) — only for
     E14-class triggering failures;
   - heavier machinery last, and only with a results file showing the
     lighter options failed.
4. **Adoption:** the winning fix is recorded in the provenance manifest
   with its deciding results file, pinned in `apm.yml` if third-party,
   and counted against the static budget (§6) if always-loaded.

Standing constraints: one owner per loop stage (rubric #3 — an adopted
fix displaces anything overlapping it); candidates are auditioned in
the eval sandbox, never installed speculatively on a live machine;
process-owning frameworks (spec-kit, OpenSpec, BMAD, and kin) are
rejected as a family and are not candidates (PRD non-goal).
agent-scripts remains a pattern donor only.

Jon's authored layer (identity instructions, skills surviving the
roster cut) is subject to the same rule in reverse: anything the
baseline proves redundant is thinned.

## 5. Per-Harness Projection Summary

| Layer | Claude Code | Pi | Codex | Copilot |
|---|---|---|---|---|
| Skills | APM → `~/.claude/skills/` | native `~/.agents/skills/` (APM-populated) | native `~/.agents/skills/` | native `~/.agents/skills/` |
| Instructions | APM → `~/.claude/CLAUDE.md` (marker-owned) | wrapper → `~/.pi/agent/AGENTS.md` (core + pi overlay) | APM → `~/.codex/AGENTS.md` | APM → `~/.copilot/AGENTS.md` **and** `copilot-instructions.md` (both marker-owned) |
| Hooks | none in v1 baseline; wrapper merges settings hooks only if a fix is adopted (§4) | none in v1 baseline; wrapper extension shim only if a fix is adopted | no hook surface — degraded mode, E14 tests it | no hook surface — degraded mode, E14 tests it |
| MCP | wrapper → `~/.claude.json` | none (by design; CLI-first rule) | wrapper → managed block in `~/.codex/config.toml` | wrapper → `~/.copilot/mcp-config.json` |
| Agents | APM agents primitive | n/a v1 | best effort | APM → `~/.copilot/agents/*.agent.md` |
| Settings | wrapper merge into `~/.claude/settings.json` | wrapper merge into `~/.pi/agent/settings.json` | not managed (personal `config.toml` keys) | not managed |
| Memory | conventions skill + vault (native auto-memory stays for session scope) | conventions skill + vault (only memory Pi has) | conventions skill + vault | conventions skill + vault |
| Static thickness | thinnest (native plan mode, verification, memory) | thickest (overlay carries the loop) | no overlay yet (baseline-first) | no overlay yet (baseline-first) |

Codex/Copilot mechanics verified hands-on 2026-07-18 (macOS; see
[harness-engineering.md](harness-engineering.md)). Their behavioral eval
columns are required before their breakage blocks release.

## 6. Static Context Token Budget

Budget answers PRD open question 2. **Measurement method:** bytes/4 of
every file loaded at session start (same method as the research);
enforced by `scripts/validate_repository.py`; verified live by E15.

| Component | Budget (tokens) |
|---|---|
| Canonical global instructions | ≤ 2,000 (≈200 lines) |
| Per-harness overlay (worst case: Pi) | ≤ 1,500 |
| Session-start injection (baseline: none; reserved for an eval-justified fix) | ≤ 500 (baseline measured 0) |
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
  settings merges → MCP merge (§3.4) → state file update.
- `sync status` — drift report: `apm audit` + wrapper-owned surfaces
  (settings keys, Pi files, root files vs marker) vs `state.json`.
- `sync doctor` — environment checks: required CLIs present (apm, node,
  official Obsidian CLI registered if the app is expected, pi if
  expected), env vars set (`AGENT_MEMORY_VAULT`,
  MCP auth vars, `APM_COPILOT_COWORK_SKILLS_DIR` pinned — live-trial
  wart 2), trust state.
- `sync remove` — reverse everything `state.json` recorded.

Wrapper-owned jobs (the APM live-trial "wart list" verbatim):

1. **Stale teardown** — after compile, remove marker-bearing root files
   for harnesses no longer targeted (wart 1) and for harnesses Jon
   doesn't use (kiro, hermes, windsurf…) (wart 3). **Verify item V3:**
   whether `targets:` in `~/.apm/apm.yml` scopes global compile; if yes,
   pin targets there instead of cleaning up after.
2. **Pi projection** — `~/.pi/agent/AGENTS.md` and settings merge. An
   extension shim is only added if an eval-justified hook is adopted
   (§4); **verify item V4** (local-extension install mechanics) is
   deferred until then.
3. **Settings merges** with state tracking (§3.5).
4. **MCP projection** into Claude Code user scope with state tracking
   (§3.4); doctor warns on env vars the declared servers reference but
   the environment lacks.
5. **First-run adoption** of hand-authored root files (§3.2).

**Self-application guardrail:** this repo is maintained under the harness
it defines (see PRD Vision). Instruction and overlay changes are never
`sync apply`'d in the same session that authored them — apply after
review, and evaluate behavior in a fresh session, so a bad edit cannot
steer the session that is supposed to catch it.

## 8. New-Machine Bootstrap (`install.sh`)

The PRD's primary success criterion. One command sequence, target ≤15
minutes (E16):

```bash
git clone https://github.com/jonhill90/agent-dotfiles ~/.agent-dotfiles-src
cd ~/.agent-dotfiles-src && ./install.sh
```

`install.sh` (macOS and Linux shared core; later phases generalize further):

1. Ensure `uv` (installs if missing) → `uv tool install apm` (pinned).
2. If Obsidian is installed: verify installer ≥1.12 and register the
   official CLI on PATH (`~/bin/obsidian` symlink; no third-party CLI).
   Memory works without it (direct file operations).
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
   `settings/`, `tests/evals/`; retire committed compatibility symlinks once
   `sync apply` replaces them.
3. On each existing machine, before first `sync apply`:
   - remove frozen `npx skills` copies in `~/.agents/skills` (wrapper
     preflight detects and lists them; removal is confirmed, not silent);
   - the superpowers plugin (5.1.0) stays installed until baseline day:
     uninstalling it is step 1 of the baseline protocol (§10), and
     nothing replaces it unless a failing eval does;
   - remove basic-memory configuration;
   - back up hand-authored `~/.claude/CLAUDE.md` (§3.2).
4. Secret scan runs in validation from the first commit of the new layout
   (public repo; PRD privacy model).

## 10. Eval Mechanics (v1)

Answers PRD open question 3. Manual by design — no automation before the
scenarios prove they discriminate (eval-scenarios doctrine).

- `tests/evals/scenarios/E<nn>-<slug>/` — one directory per scenario: `prompt.md`
  (verbatim prompt + setup steps), `criteria.md` (observable PASS/FAIL),
  fixture files where needed (E2, E6, E7, E9 need rigged repos).
- Runner protocol: fresh session in the target harness×model pair, run
  the prompt, score against criteria. A pair passes a stage when all its
  scenarios pass **twice consecutively**.
- Results: `tests/evals/results/<date>-<harness>-<model>.md` — one matrix per
  run, committed. Adoption decisions are closed only by results files
  referenced from the provenance manifest.
- v1 release-required pairs: Claude Code×Fable and Pi×default. Claude
  Code×Sonnet and Pi×Sonnet-class are the secondary model-variation matrix;
  record partial coverage honestly when provider accounts are unavailable.

**Baseline protocol (the §4 selection rule, operationalized):**

1. On the eval machine: uninstall the superpowers plugin — rip-out day
   is baseline day. Stack = canonical instructions (+ Pi overlay on Pi),
   surviving tool skills, nothing else.
2. Run E1–E15 on all v1 pairs; commit the matrix.
3. Per failing scenario: audition the smallest fix (§4 order), re-run
   that scenario twice, record winner + results file in the provenance
   manifest.
4. Re-run the full matrix with the adopted set before declaring M5 done
   (fixes must not regress previously passing scenarios).

**Tool-skill track (acceptance checks):** loop evals do not cover tool
skills. Each kept tool skill gets
`tests/evals/acceptance/<skill>.md` — 3–5 concrete tasks the skill must let
the agent complete (e.g. obsidian: create note, search, read from a
script — the memory backend's needs; tmux: start session, verified
send-keys, recover a stuck pane). A community candidate displaces a
personal skill only by passing the same checks with equal-or-fewer
tokens loaded. Swap decisions cite the check file in the manifest.

## 11. Verification Items (carry into implementation)

| # | Item | Blocking? |
|---|---|---|
| V1 | APM follows `.apm/` symlinks for local-path install/pack | **Verified 2026-07-12** (APM 0.24.1, evidence commit `dff03d0`): in-package symlinks whose targets stay inside the package root are dereferenced and deploy to user skill paths. APM's `--skill` filter was re-verified on the clean 2026-07-13 remote run. |
| V2 | APM hooks primitive at user scope | No — wrapper owns hook wiring until proven (§3.3) |
| V3 | `targets:` in `~/.apm/apm.yml` scopes global compile | No — cleanup fallback specified (§7) |
| V4 | Pi local-extension install mechanics | No — deferred; only needed if an eval-justified hook is adopted (§4) |
| V5 | (Phase 2) Copilot CLI MCP path, `~/.copilot/AGENTS.md`, `~/.agents/skills` symlink handling; Codex hook mechanism | **Resolved 2026-07-18** (hands-on, macOS, Codex CLI 0.144.1 / Copilot CLI 1.0.70): APM writes both `~/.copilot/AGENTS.md` and `copilot-instructions.md` marker-owned, mooting the per-platform filename question; Copilot MCP = `~/.copilot/mcp-config.json` (`mcpServers` schema); Codex MCP = `[mcp_servers.*]` tables in `~/.codex/config.toml` (wrapper owns a marker block); both read `~/.agents/skills` natively; neither has a hook surface — E14 degraded mode applies |
| V6 | Official Obsidian CLI vs third-party obsidian-cli | **Resolved 2026-07-12, owner override** (evidence commit `b752300`): official CLI adopted for the optional `obsidian` skill; memory uses direct files and has no CLI dependency. Verified hands-on on 1.12.7. The CLI does not auto-launch the app. `sync doctor` rejects vaults on corporate mounts. |
| V7 | Community tmux-skill candidates vs `using-tmux` acceptance checks | No — swap decision, not a blocker; `using-tmux` stays until displaced |
| V8 | APM serves stale root-file content after source edits ("files unchanged" while content differs) | **Resolved 2026-07-13:** apply detaches only marker-owned managed roots before compile, forcing regeneration; a failed compile restores the last-known-good roots. Covered by regression tests. |

## 12. Milestones (Phase 1)

| M | Deliverable | Done when |
|---|---|---|
| M1 | Repo rename + layout migration (§2, §9.1–2) | validation suite green on new layout; `npx skills add . --list` still resolves |
| M2 | APM package works | **Done 2026-07-12** (evidence commit `dff03d0`): skills deployed to both paths, marker-owned root files written, hand-authored files preserved |
| M3 | Wrapper v1 | **Done 2026-07-12**: `sync apply/status/doctor/remove` implemented TDD (11 tests); live apply on this Mac — 6 stale root files torn down, `~/.pi/agent/AGENTS.md` projected (core + overlay), status clean; committed symlink matrix retired, validator enforces absence |
| M1.5 | Skill roster cut | **Done 2026-07-13:** cut skills deleted; kept tool checks committed; the filtered APM install contains seven accepted skills while benched public skills remain individually installable. Validator enforces the split. |
| M4 | Memory tooling | **Done 2026-07-12**: "Agent Memory" vault created in iCloud + registered; `AGENT_MEMORY_VAULT` wired; memory-conventions skill shipped; doctor validates vault (personal + exists); basic-memory user-scope MCP removed; E12 passes 2× on CC×Fable and Pi×default incl. cross-harness recall ([results](../tests/evals/results/2026-07-12-e12-memory-writeback.md)) |
| M5 | Baseline run + gap-fill | **v1 behavioral baseline complete 2026-07-12** ([results](../tests/evals/results/2026-07-12-baseline-day.md)): all E1–E15 scenarios covered on required Claude Code×Fable and Pi×default surfaces; the only authoritative failure, Pi E11, passed twice after the smallest overlay fix. Sonnet-class sampling passed but its entire optional matrix and every second-run cell are not complete; that is recorded secondary coverage, not a claim of a full 4-pair matrix. No framework or hook was justified. |
| M6 | New-machine test | **Complete 2026-07-13.** Attempt 1 failed and produced bootstrap fixes. [Attempt 2](../tests/evals/results/2026-07-13-e16-attempt2-pass.md) supplied authenticated E14/E12 behavior. The [remote regression](../tests/evals/results/2026-07-13-e16-current-tree-regression.md) used a brand-new Linux user: bootstrap and doctor passed in 12 seconds, the then-38-test suite and no-PyYAML validation passed, stale-root regeneration passed, exactly seven default skills deployed, and corrected E15 measured ~1,793/8,000 tokens. A final last-known-good preservation test brought the branch suite to 39 and was run by Pi; production sync code was unchanged after the remote run. The remote account had no model credentials, so release acceptance explicitly combines its deployment evidence with attempt 2's unchanged behavioral assets. Research scaffolding was distilled into living topical docs and deleted; git history remains the archive. |

## 13. Milestones (Phase 2 — Codex + Copilot first-class)

| M | Deliverable | Done when |
|---|---|---|
| P2-M1 | Mechanical layer: V5 verification, MCP projection to Codex + Copilot, status/doctor coverage | **Done 2026-07-18** (TDD, suite 59 tests; live on Jon's Mac) |
| P2-M2 | Behavioral columns: E1–E15 on Codex×default and Copilot×default, twice consecutively; gap-fills auditioned baseline-first (no hook surface — instruction/skill fixes only) | results files committed |
| P2-M3 | First-class flip: SPEC/README list Codex + Copilot as release-blocking | P2-M2 passes; harness-engineering matrix updated |

Phase 1 exit satisfies M6 (primary) and the required-pair M5 baseline. The
full four-pair consecutive-pass matrix remains incomplete secondary coverage,
and the results say so explicitly. The PRD's consolidation criterion (§9.3)
is satisfied on Jon's Mac as of 2026-07-17: stale project-scoped
basic-memory MCP configs and permission allows purged, Claude Code plugins
managed through the `enabledPlugins` fragment, and the declared MCP set
projected by the wrapper. Other machines consolidate on their next
`sync apply`.
