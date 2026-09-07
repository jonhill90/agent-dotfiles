---
type: Document
knowledge_status: canonical
updated: 2026-09-06T23:27:40+00:00
---

# Technical Spec: agent-dotfiles

- **Status:** Implemented v1.4 — 2026-07-26; status line refreshed
  2026-07-29. Codex and Copilot are first-class (P2-M3); per-harness
  roster scoping landed (P2-M4, §4.1); V9 and V10 resolved
  affirmatively: all four first-class harnesses have a Tier B disable
  surface and the roster is enforced on each. P2-M5, P2-M6 and P2-M7
  all closed 2026-07-27 (§13). `sanity-check` moved to public opt-in
  2026-07-29 (§4.1), so per-harness scoping currently has no user.
  Open: E20's unbound columns (Codex FAIL ×3, Pi 1 of 3, Copilot
  unmeasured — could not re-measure from this repo, evidence lives in the
  private jonhill90/agent-evals repository). jonhill90/skills#96
  (`name-only`) closed 2026-08-03. **Corrected 2026-08-23:** #5 (§6 budget
  blind spot), previously listed open here, closed 2026-08-11.
- **Owner:** Jon Hill
- **Inputs:** [PRD](PRD.md), [harness engineering](harness-engineering.md),
  and [memory](memory.md). Behavioral evals' methodology now lives in
  `docs/evals.md` in the private repository jonhill90/agent-evals, evidence
  unavailable publicly. **Corrected 2026-08-23:** this previously cited
  dated research as preserved in git history at `106e69c`, `c089a95`,
  `8a222ce`, `065bc9d`, `a4de1ac`, `e33f08b` — none of these six SHAs
  resolves in this repository's current history (checked against a full
  fetch from `origin`, all refs). The underlying research is not
  recoverable from this repo as cited.
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
    validate_repository.py # token-budget checks + a private-term scan
                           # (.privacy-denylist). NOT a secret scanner:
                           # no credential detection exists, here or in CI.
                           # A missing denylist is a hard CI failure, not a
                           # silent pass (#325) — CI materializes it from
                           # the PRIVACY_DENYLIST repository secret
  tests/                   # one verification tree (layout rev. 2026-07-18)
    test_*.py              # unittest suite (wrapper + validators)
    requirements-dev.txt   # dev/CI-only dependencies
    evals/
      scenarios/           # E1–E18 fixture dirs; E16 is excluded — it is
                           # the live bootstrap acceptance (§10.2). E19/E20
                           # fixtures are built by harness/fixtures.sh
      counter/             # counter-scenarios (§10.1)
      acceptance/          # concrete checks for tool skills
      harness/             # run.sh — one scored interactive run
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

**Ownership (2026-08-10, #9):** skill content moved out of this
repository entirely, into the public `jonhill90/skills` and the private
`jonhill90/skills-private`, each pinned in `apm.yml` as an object-form git
dependency (`ref:` a commit SHA, `skills: ["*"]`). This repository no
longer contains a `skills/` directory; `docs/AGENTS.md` and this section's
mentions of `skills/` below describe the pre-#9 v1 design and are
historical except where superseded by the ownership line above. Roster
membership (`settings/default-skills.txt`) and the roster-enforcement
mechanism (§4.1) are unchanged and still live here.

- Canonical authoring unchanged (AGENTS.md policy: portable frontmatter,
  <500 lines, references/, scripts/) — but now enforced in
  `jonhill90/skills`/`jonhill90/skills-private`'s own validators, not
  `scripts/validate_repository.py` here.
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
  `--skill` filters from `settings/default-skills.txt`, so benched `primer`,
  `close-the-loop`, `dispatching-subagents`, and (since 2026-07-29)
  `sanity-check` remain public without deploying or consuming context.
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
    **Implemented 2026-08-19 (agent-dotfiles#276), extended 2026-08-30
    (agent-estate#665):** seven `PreToolUse`
    guards — destructive tmux verbs, protected tmux targets, commits to
    `main`, `gh api` body-posting footguns, a lane closing its own issue,
    and ad hoc writes to the live ledger, and macOS Keychain writes — each
    blocking with exit 2 and a named reason. `scripts/sync.py`'s
    `resolve_hook_commands()` rewrites the
    fragment's repo-relative `hooks/*.sh` commands to this install's
    absolute path before merging into the live file. See `hooks/README.md`
    for the full enumeration this issue produced, including what stayed
    prose and why.
  - Pi: wrapper installs a thin extension (TS module) that shells out to
    the same `hooks/` scripts on `session_start` / `agent_end`. **Not yet
    built** — agent-dotfiles#276 scoped to Claude Code only.
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

[Memory](memory.md) owns the canonical INMAPS contract. The vault path is
`AGENT_MEMORY_VAULT`; content is personal, separate from Second Brain, and never
synced by dotfiles. Read progressively from Start Here and the capped index.
Ordinary writes use the reviewed tool: Inbox draft → ID-named stable note;
supersession preserves deprecated notes. This replaces direct file writes and
semantic filenames. The [previous contract](../historical/memory-contract-before-inmaps.md)
is preserved as historical evidence, not active instruction.

### 14.1 Today's mechanism, and it is the only one

Supervisor-to-worker handoff is **cooperative tmux `wait-for`**: the
supervisor blocks on a shell call, and the worker's final action is
`tmux wait-for -S <channel>`. That is the entire mechanism in active use
today (#22 — used to review and merge `jonhill90/Hill90#871`).

### 14.2 Four measured limits

| # | Limit | Instrument |
|---|---|---|
| L1 | It blocks the supervisor, so lanes run serially rather than concurrently | Observed in the jonhill90/Hill90#871 review (#22) |
| L2 | It is cooperative: a worker that crashes, wedges, or hits a usage limit never runs its final action, so the signal never arrives and the supervisor blocks forever. **This is the v4 defect class** — a usage-blocked pane that echoed the prompt marker got marked delivered without consuming the turn | #22, citing the v4 incident |
| L3 | No timeout exists at the tmux layer: `man tmux` gives `wait-for [-L \| -S \| -U] channel` with no timeout option at all. Claude Code's Bash tool caps its own `timeout` at 600000 ms (10 minutes), so any worker task longer than that cannot be waited on in the foreground at all | `man tmux` (#22); Claude Code Bash tool `timeout` cap (#22) |
| L4 | The signal carries no payload: `wait-for -S` transmits one bit. The verdict, test counts, and PR URL must be scraped from pane scrollback, which is lossy and racy — the signal has been observed arriving before the final message finished rendering, during the jonhill90/Hill90#871 review | Observed in the jonhill90/Hill90#871 review (#22) |

### 14.3 Layered design, by failure mode

The mechanism is layered by failure mode rather than replaced by a single
alternative:

| Layer | Mechanism | Addresses |
|---|---|---|
| Fast path | Cooperative `wait-for`, run under Bash `run_in_background` so the supervisor stays live and lanes can run concurrently | L1 |
| Failure path | Harness-fired Claude Code Stop hooks, or `herdr agent wait` | L2 — this is what closes the v4 defect class |
| Durability and payload | The v5 ledger: a signal is ephemeral, a ledger row survives a supervisor restart and can carry the payload | L2, L4 |
| Backstop only | Cron as a dead-man stall detector: it notices a lane has been in the same state too long and escalates | Stall detection only — not a signal source |

**Cron must never be the mechanism — that was the v1 bug.** Cron re-enters
blind, re-derives context, and cannot distinguish "still working" from
"wedged." Its role is limited to the backstop stall detector above; using
it to drive the loop directly is prohibited, not merely discouraged.

## 15. Transport Adapter Boundary (settled 2026-08-10)

Design context and the measured figures below are recorded in full in
`jonhill90/agent-dotfiles#23`; this section is the canonical citation
point for future issues and should be cited rather than restated.

**Moved (Phase 1.5 split, #179, 2026-08-12):** the portable core and the
tmux/ACP adapters this section describes moved to `jonhill90/agent-supervisor`
(private) along with `scripts/supervisor/` and `tests/supervisor/` (commit
`2925720`; see §14's note). The boundary decision below is still accurate and
stays canonical, but "the core" is now that repository's code, not this one's.
The core/adapter split described in §15.1 is unchanged by the move; only the
core's location changed, and where this spec itself should live is the same
open question noted in §14 (`docs/supervisor-extraction-plan-179.md` §11).

### 15.1 What the core owns vs. what an adapter owns

The portable core owns the ledger, ownership-safe transitions, assignment
gating, and attention. A transport adapter owns only "deliver this prompt
to this lane and report what came back." tmux and ACP (Agent Client
Protocol) are the two worked examples; `herdr` is a candidate third,
pending the open build-vs-adopt decision in #24.

If protocol knowledge leaks into the core, durable state becomes coupled
to one protocol's lifetime, and the next harness costs a rewrite instead
of an adapter.

### 15.2 Harness capability, measured on this machine 2026-08-10

| Harness | Evidence |
|---|---|
| Copilot CLI | `copilot --help` → `--acp  Start as Agent Client Protocol server` (#23) |
| Codex | `codex --help` → `exec`, `app-server`, `exec-server`, `remote-control` (#23) |
| Claude Code | Streaming JSON IO, resumable sessions, background agents, hooks, remote control (#23) |

All three first-class harnesses already expose a structured drive surface
beyond typing into a terminal; #23 is the source for these figures.
