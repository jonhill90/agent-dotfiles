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

## 4.1 Skill Roster Scoping (per-harness, added 2026-07-25)

§4 governs *which* fix is adopted. It says nothing about *who pays for
it*, and the P2-M3 adoptions exposed the gap: `safe-deletion` and
`failing-test-first` were authored to clear Copilot-only failures (E11,
E06), but `settings/default-skills.txt` is a single flat roster, so
Claude Code, Codex, and Pi — which passed both scenarios on the
canonical instructions alone — load them too. Unclosed, every rung-2
adoption charges all four harnesses, and a roster kept deliberately lean
by M1.5 grows one justified skill at a time.

**Rule.** A gap-fill skill is installed only on the harnesses whose
evals justify it. A skill enters a harness's roster only when either

- that harness failed a scenario the skill demonstrably fixes, with the
  deciding results file recorded in the provenance manifest (§4, step
  4); or
- it is a tool/workflow skill from the standing roster cut, which is
  harness-independent by intent.

Scoping is subtractive from a *passing* baseline only. A skill may never
be scoped out of a harness an eval showed needs it; narrowing a roster is
not a way to dodge a failing cell.

**Roster format.** `settings/default-skills.txt` gains optional
per-harness sections. Unscoped lines keep their current meaning — shared
by every harness — so the existing file stays valid and diffable:

```text
# shared roster (all harnesses)
gh-cli
create-skill
...

[copilot]
safe-deletion
failing-test-first
```

`load_default_skills(repo, harness=None)` returns the shared list when
called without a harness, and `shared + section` for a named one. APM
still installs the **union** across harnesses, so package deployment is
unchanged and APM keeps ownership of `~/.claude/skills`.

**Mechanism, by tier.** Achievable granularity is bounded by what each
harness exposes; §5 records that Pi, Codex, and Copilot all read the same
`~/.agents/skills` natively, so "per-harness" is not uniformly available.

*Tier A — shared-path scoping (implementable now, no new harness
surface).* `Sync.ensure_neutral_skills()` currently mirrors
`~/.claude/skills` wholesale. It instead mirrors only the union of the
Pi, Codex, and Copilot rosters, and removes wrapper-created symlinks that
have left that union — state-tracked and reversible, matching the
settings-merge discipline (§7). This cleanly separates Claude Code's set
from the neutral trio's in both directions.

*Tier B — harness-native disable (individual harnesses inside the neutral
trio).* Excluding one of Pi/Codex/Copilot alone requires that harness's
own disable surface:

- **Codex:** `[[skills.config]]` entries in `~/.codex/config.toml` —
  already proven and in production use for the `yeet` plugin-skill
  disable (E14 PASS ×2, 2026-07-18).
- **Copilot:** no persistent deny surface exists (verified 2026-07-18 via
  `copilot help config`). Copilot therefore always receives the neutral
  union, and a Copilot-only skill keeps costing Pi and Codex until V10
  resolves. This is the current `safe-deletion` case and it is a known,
  recorded cost — not a silent one.
- **Claude Code:** `skillOverrides` in settings — a per-skill state map
  (`on` / `name-only` / `user-invocable-only` / `off`). Verified
  hands-on 2026-07-26 on v2.1.220: `{"az-devops": "off"}` removed it
  from the model's skill list while the skill stayed on disk;
  `name-only` kept it listed. Plugin skills are **not** covered — those
  need `/plugin`.
- **Pi:** a `skills` denylist in `~/.pi/agent/settings.json`, the file
  the wrapper already merges (§3.5). Verified hands-on 2026-07-26 on
  0.80.6: `"skills": ["-skills/az-devops/SKILL.md"]` dropped it from
  Pi's loaded-skills banner, 9 → 8, with the skill still on disk.
  `pi config` writes it through a TUI, but the wrapper can write the key
  directly.

*Tier C — not built.* A dedicated skills directory per harness. V9 came
back affirmative for both Claude Code and Pi (2026-07-26), so Tier B now
covers three of four harnesses and Tier C is further from justified, not
closer. It remains reachable only if the measured neutral-union overhead
exceeds the §6 per-harness budget on Copilot, the one column with no
disable surface.

**Budget lever (§6).** Claude Code's `name-only` state lists a skill
without its description, so it cuts the description tokens a skill costs
while keeping it invocable. That is a cheaper instrument than exclusion
for a skill that is wanted but rarely triggered, and it applies to the
per-harness aggregate §4.1 introduced.

**Consequences.**

- §6's static budget is measured per harness against that harness's
  resolved roster, not against the union.
  `scripts/validate_repository.py` enforces the aggregate per harness.
- `sync status` reports each harness's resolved roster; `sync doctor`
  flags drift between the resolved roster and what is on disk.
- Every per-harness section entry carries a provenance-manifest row with
  its deciding results file, on the same terms as any other adoption.

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
| Enabled Claude Code plugin skills (live-only, see below) | counted in the description aggregate |
| **Total static, thickest harness** | **≤ 8,000** |

Everything procedural loads dynamically (progressive disclosure). The
validator fails the build if canonical files exceed their line/token
caps; the skill-description aggregate is checked against the declared
dependency set in `apm.yml`.

Once per-harness rosters land (§4.1, P2-M4), the skill-description
aggregate is measured against each harness's *resolved* roster rather
than the `apm.yml` union, and the total above is enforced per harness.
Until then the union is the enforced basis.

**Plugin skills are in the budget and cannot be measured repo-side.**
Enabled Claude Code plugins contribute description tokens but are not
vendored here, so `validate_repository.py` cannot see them — a plugin
can grow the static footprint with no repo-side check noticing. Live
E15 therefore runs `scripts/measure_e15.py`, which reads the deployed
tree. Three counting traps it encodes, each found on a live machine
2026-07-26: only `plugins/cache/` is installed content (`marketplaces/`
is the catalogue of everything *available* and double-counts anything
installed); a plugin may ship `commands/*.md` instead of
`skills/*/SKILL.md`, which Claude Code merges into skills and which
therefore cost tokens; and a cached-but-disabled plugin costs nothing.
Only Claude Code loads plugin skills — the neutral trio are not charged.

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

## 10.1 Evidence Bar and Counter-Scenarios (added 2026-07-25)

Two weaknesses in the v1 protocol above, both surfaced by the P2-M3
adoptions.

**A. `×2` is a thin sample for a stochastic system.** The bar for
adoption and for regression is the same two consecutive passes. But the
same milestone that adopted `safe-deletion` also pinned Copilot's model
*because* `Auto` routing flipped E03 between pass and fail inside a
single cell — an admission that run-to-run variance is large enough to
manufacture a result. Two passes is exactly the sample size that variance
defeats. The fix is not "more runs everywhere" — these are manual
sessions and uniform inflation would price the matrix out of existence.
It is to spend runs where the inference is actually load-bearing.

1. **Variance control precedes counting.** No cell may close an adoption
   while its model routing is unpinned or unrecorded. Every results row
   names the harness *and* the resolved model. A cell whose model is
   selected by a router (Copilot `Auto`, or any successor) is not
   evidence until pinned. Precedent: the `claude-sonnet-5` pin,
   2026-07-18.
2. **Regression checks stay at ×2.** Confirming that an
   already-passing scenario still passes is a low-stakes check against a
   high prior. Two runs remain sufficient, unchanged.
3. **Adoptions require ×3 consecutive, and must out-weigh the observed
   failure.** A gap-fill flips a cell whose prior is *failing*, so the
   post-fix evidence has to beat the pre-fix evidence rather than tie it.
   Record both counts explicitly — "failed ×2, passed ×3" — and require
   passes > failures. Ties (the current "failed ×2, passed ×2") do not
   close a row.
4. **Any disagreement inside the window resets it and flags the
   candidate.** One failure among the adoption runs means the sample
   restarts, and the candidate is recorded as *flapping*. A candidate
   that flaps twice is not adopted at that rung — escalate to the next
   §4 rung or investigate the variance source first. Flapping is a
   finding, not noise to be re-rolled away.

**B. Nothing tests whether an adopted fix fires when it shouldn't.**
Every audition asks "did the target scenario flip?" and "did any other
scenario regress?" Neither question catches overtriggering. A skill that
fires on *delete, remove, clean up, clear out, purge, empty* will fire
constantly, and a gate that stalls routine work fails no scenario in
E1–E15 — it just taxes every future session invisibly. Regression
coverage cannot find this, because the cost lands on tasks no scenario
describes.

Therefore: **every adopted behavioral skill carries a counter-scenario
before it enters a roster.** `tests/evals/counter/<skill>.md`, same shape
as the tool-skill acceptance checks below, containing at minimum:

- **A legitimate-path case.** The skill's triggers are present and the
  skill is genuinely relevant, but the correct outcome is to proceed.
  PASS = the task completes; FAIL = the agent refuses, stalls, or
  escalates to the user. For `safe-deletion`: clearing a `dist/` that
  contains exactly the build artifacts its name implies — the gate
  should list, match, delete, and report, not ask permission.
- **A null-trigger case.** The trigger vocabulary appears in a context
  the skill does not govern. PASS = the skill does not fire. For
  `safe-deletion`: "remove the retry loop from this function" is a code
  edit, not a file deletion.

Counter-scenarios run at the regression bar (×2) alongside the matrix. A
skill that fails one is over-scoped: narrow its `description` triggers or
its procedure, then re-audition.

**A counter-scenario FAIL is not believable until its transcript has been
read.** The runner is test code and carries the same burden of proof as
what it measures. A bad fixture or a bad matcher fails *consistently*, so
the ×2 bar gives no protection — it reproduces the same wrong answer
twice. The 2026-07-26 pass produced four runner defects, three of which
read as the skill misbehaving and would have narrowed `safe-deletion`
to fix bugs in the harness ([results](../tests/evals/results/2026-07-26-p2m5-counter-pass1.md)).
Four rules follow. Persist every transcript before its session is torn
down. Score agent behaviour only in the transcript region after the
prompt — a harness that prints its installed-skill roster at startup
otherwise matches the skill's own name and fails itself. Treat a
**missing transcript as `INVALID`, never as `FAIL`**: a session that
died mid-run is not evidence either way. And run **one orchestrator at
a time** — two concurrent runs share tmux session names and fixture
directories and silently overwrite each other's results
([pass 2](../tests/evals/results/2026-07-26-p2m5-counter-pass2.md)). Adoption rows in the provenance manifest
cite the counter file next to the deciding results file.

**Retroactive application.** `safe-deletion` and `failing-test-first`
were adopted 2026-07-18 under the prior bar (failed ×2, passed ×2, no
counter-scenario). They are not unwound — both cleared real, reproduced
failures. They are re-verified at the bar above on the next full matrix
run (P2-M5). Their manifest rows carry a **prior-bar** caveat naming the
evidence they were adopted on; P2-M5 clears the caveat once the
re-verification lands.

## 10.2 Scenario Intake (added 2026-07-25)

§4 and §4.1 govern how a *fix* earns adoption; both make a failing
scenario the only door into a roster. Neither says how a *scenario*
comes into existence, so the door has no described approach. This
section supplies it.

**Trigger.** A new scenario is written when a behavior the agent is
expected to have is exercised by no existing scenario. Absence of
coverage is the justification — not a component someone wants to
install.

**Numbering.** Next free `E<nn>`. E16 is permanently the live bootstrap
acceptance (§10, `docs/evals.md`) and never a `scenarios/` fixture, so
behavioral scenarios continue from E17.

**Shape.** `tests/evals/scenarios/E<nn>-<slug>/` with `prompt.md`
(setup plus the verbatim prompt) and `criteria.md` (one observable
PASS line), matching E1–E15. Fixture files only where the scenario
needs a rigged repository. Scoring stays transcript-and-filesystem
evidence, never self-report.

**Discrimination gate.** A scenario earns its place by discriminating.
It must fail on at least one v1 pair at baseline, or separate a
known-good run from a known-bad one on demand. A scenario that passes
everywhere at baseline is retained as regression coverage and justifies
no component — it has shown the behavior is already covered, which is
itself a result worth recording.

**Ordering gate.** The scenario is authored and baselined *before* any
candidate fix is auditioned against it, and its baseline result is
committed first. A scenario written after a candidate, to justify that
candidate, is void: the deciding results file must postdate the
baseline results file that established the failure. This is the rule
that keeps §4's ladder from being climbed backwards — authoring a
component and then reverse-engineering the scenario that admits it
would satisfy every other gate in this document.

**Retirement.** A scenario is removed only with a results file showing
it no longer discriminates, and the manifest records the removal.
Silent deletion of coverage is a regression.

**Plugin adoption gate.** `skillOverrides` does not reach plugin skills
(§4.1), so the unit of control is the plugin, not the skill: a plugin is
taken whole or not at all. Adding one therefore requires an E14 run
confirming it shadows no managed skill's trigger, recorded in the
provenance manifest. Precedent: Codex's curated `github` plugin shipped
a `yeet` skill that shadowed managed `gh-cli` on the PR workflow and had
to be disabled per-skill (2026-07-18). Claude Code has no per-skill
escape hatch for plugins, so on that harness the only remedies are
disabling the whole plugin or displacing the managed skill — which makes
the check before adoption the cheap moment.

**Tool-skill track (acceptance checks):** loop evals do not cover tool
skills. Each kept tool skill gets
`tests/evals/acceptance/<skill>.md` — 3–5 concrete tasks the skill must let
the agent complete (e.g. obsidian: create note, search, read from a
script — the memory backend's needs; tmux: start session, verified
send-keys, recover a stuck pane). A community candidate displaces a
personal skill only by passing the same checks with equal-or-fewer
tokens loaded. Swap decisions cite the check file in the manifest.

## 11. Verification Items (carry into implementation)

Open items are surfaced as GitHub issues labelled `verification`
(`docs/work-tracking.md`); the rows below stay canonical.

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
| V9 | Claude Code and Pi per-skill disable surfaces | **Resolved 2026-07-26, both affirmative** (hands-on; §4.1 Tier B): Claude Code `skillOverrides` on v2.1.220, Pi `skills` denylist on 0.80.6. Three of four harnesses now have a Tier B surface; only Copilot lacks one (V10) |
| V10 | Copilot per-skill disable surface — still absent at CLI **1.0.75** (rechecked 2026-07-26 at 1.0.71 and again at 1.0.75: full `copilot help config` key list contains nothing skills-related; `/skills` is an interactive session command, not persistent config; `permissions` offers `--deny-tool` for tools, not skills). Previously verified absent at 1.0.70 (2026-07-18); recheck on upgrades | No — until resolved Copilot receives the neutral union, and the overage is charged against its §6 budget |

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

Open milestones are surfaced as GitHub issues labelled `milestone`
(`docs/work-tracking.md`); the rows below stay canonical.

| M | Deliverable | Done when |
|---|---|---|
| P2-M1 | Mechanical layer: V5 verification, MCP projection to Codex + Copilot, status/doctor coverage | **Done 2026-07-18** (TDD, suite 59 tests; live on Jon's Mac) |
| P2-M2 | Behavioral columns: E1–E15 on Codex×default and Copilot×default, twice consecutively; gap-fills auditioned baseline-first (no hook surface — instruction/skill fixes only) | **Done 2026-07-18** ([baseline](../tests/evals/results/2026-07-18-p2m2-codex-copilot-baseline.md), [clearance](../tests/evals/results/2026-07-18-p2m3-blockers-cleared.md)): both columns fully green ×2. Adopted along the way: deletion-gate sentence, `safe-deletion` + `failing-test-first` skills, Copilot model pin, Codex `skills.config` plugin-skill disables |
| P2-M3 | First-class flip: SPEC/README list Codex + Copilot as release-blocking | **Done 2026-07-18**: all P2-M2 cells pass ×2; Codex and Copilot breakage now blocks release; harness-engineering matrix updated |
| P2-M4 | Per-harness skill rosters (§4.1): sectioned `default-skills.txt`, Tier A scoping in `ensure_neutral_skills()`, Tier B Codex disable wiring, per-harness §6 budget check, `status`/`doctor` roster reporting | **Done 2026-07-26** ([matrix](../tests/evals/results/2026-07-26-p2m4-e11-matrix.md)): sectioned roster parses with the flat file still valid (TDD); Tier A verified in tests and as a live no-op against the deployed tree; removal from a section removes the wrapper symlink reversibly; per-harness E15 measured live — 1,726 tokens on Claude Code/Codex/Copilot and 2,184 on Pi against an 8,000 cap; E11 PASS ×2 on all four columns with models and CLI versions pinned and recorded, no files deleted in any scored run. **Correction 2026-07-26:** this row previously required that "Claude Code no longer receives Copilot-scoped skills," which Tier A cannot deliver — §4.1 states APM installs the union and keeps ownership of `~/.claude/skills`, so excluding a skill from Claude Code needs a Tier B disable surface, which for Claude Code is V9 and unverified. The achievable Tier A guarantee is the reverse direction, stated above. The roster stays flat until the eval evidence lands; the mechanism is inert until a section is added |
| P2-M5 | Evidence bar + counter-scenarios (§10.1): `tests/evals/counter/` established, counter files for `safe-deletion` and `failing-test-first`, both re-verified at the ×3 adoption bar with models pinned and recorded | **Open.** Done when: both counter files exist and pass ×2 on all four columns; both skills pass their originating scenario (E11, E06) ×3 consecutive on Copilot with the model pinned and named in the results row; manifest rows updated to cite counter files and drop the prior-bar caveat; any skill failing a counter-scenario is narrowed and re-auditioned before the row closes |
| P2-M6 | Baseline E17 (§10.2): the delegation/verification scenario is authored but un-baselined, so it currently justifies nothing | **Three of four columns baselined 2026-07-26** ([results](../tests/evals/results/2026-07-26-e17-baseline.md)): PASS ×2 on Claude Code, Codex and Pi, every run reaching its conclusion on external evidence rather than the vote. On the evidence available E17 does not discriminate, so it is retained as regression coverage and justifies no component; `dispatching-subagents` stays public opt-in. Copilot is quota-blocked and unmeasured. **Open.** Done when: E17 has run on all four columns with models pinned and the matrix committed; the discrimination gate is settled either way — if it fails on at least one column it becomes admissible evidence and the §4 ladder runs from the sentence rung upward, and if it passes everywhere it is recorded as regression coverage and `dispatching-subagents` stays public opt-in with that result cited. No component is auditioned against E17 before its baseline results file is committed (§10.2 ordering gate) |

Phase 1 exit satisfies M6 (primary) and the required-pair M5 baseline. The
full four-pair consecutive-pass matrix remains incomplete secondary coverage,
and the results say so explicitly. The PRD's consolidation criterion (§9.3)
is satisfied on Jon's Mac as of 2026-07-17: stale project-scoped
basic-memory MCP configs and permission allows purged, Claude Code plugins
managed through the `enabledPlugins` fragment, and the declared MCP set
projected by the wrapper. Other machines consolidate on their next
`sync apply`.
