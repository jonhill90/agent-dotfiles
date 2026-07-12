# Phase 0: APM Verification

- **Date:** 2026-07-11
- **Question (from PRD):** Can APM be the sync backbone? Verify (a) Pi
  support, (b) machine/global scope.
- **Evidence:** local snapshot `~/source/repos/skills-research/apm`
  (post-v0.20, commit `26d8cee8`), source + docs inspection.

## Verdict

**Conditionally passes — use as backbone with a thin wrapper for Pi.**

Global scope is real and first-class. Pi is absent and needs either a
wrapper or an upstream contribution. Claude Code, Codex, and Copilot (all
three of the non-Pi first-class targets) are fully covered.

## Finding 1: Global/user scope is supported (concern resolved)

- `apm install -g <package>` installs to user scope (`~/.apm/apm_modules`)
  — documented in `docs/.../consumer/install-packages.md`.
- `apm compile --global` compiles user-scope root context files per target
  (`src/apm_cli/compilation/user_root_context.py`):
  - claude → `~/.claude/CLAUDE.md` (honors `$CLAUDE_CONFIG_DIR`)
  - codex → `~/.codex/AGENTS.md`
  - copilot/vscode → `~/.copilot/AGENTS.md`
  - cursor → `~/.cursor/AGENTS.md`; gemini → `~/.gemini/GEMINI.md`;
    opencode → `~/.config/opencode/AGENTS.md`
- Safety behavior matters for dotfiles: generated files carry a marker;
  **hand-authored files without the marker are never overwritten.**
- Adapters take a `user_scope` flag throughout (`ClientFactory`,
  approvals stored in `~/.apm/config.json`).

## Finding 2: Pi is not a target (gap confirmed)

The MCP client registry (`src/apm_cli/factory.py`) has 12 targets:
antigravity, copilot, vscode, codex, cursor, gemini, intellij, kiro,
opencode, windsurf, claude, hermes. **No Pi.** Same for compile families
(claude/agents/vscode/gemini) — no Pi root-file mapping.

Mitigations, in order of preference:

1. **Wrapper projection:** APM owns the canonical installed tree
   (`~/.apm/apm_modules`); a small personal sync step projects that tree
   into Pi's config surface (skills dir + instructions). Pi support in
   superpowers (`.pi/extensions`) documents the target format.
2. **Upstream contribution:** the code is explicitly structured for new
   targets ("adding a new MCP-capable target means a single dict entry"
   plus a `TargetProfile`). Microsoft repo, active development, plausible
   PR. Long-term better; not a v1 dependency.

## Finding 3: Primitive coverage matches the PRD's five layers

`TargetProfile` registry (`src/apm_cli/integration/targets.py`) maps
primitives per target: instructions, skills, prompts, agents, **hooks**
(e.g. claude `hooks_config_display: .claude/settings.json`), plus MCP
server integration with trust prompts. Drift detection (`apm audit`),
lockfile with content hashes, and unicode-hijack scanning come free —
three things the spec would otherwise have to build.

## Residual unknowns (verify hands-on during spec)

1. Whether `apm install -g` deploys *skills* into each harness's
   user-scope skills dir (e.g. `~/.claude/skills`) or only into
   `~/.apm/apm_modules` pending compile — needs a live trial
   (`install.sh` → `apm install -g` a test package on this Mac).
2. Claude Code note from live inspection (2026-07-11): home-level
   `~/.claude/skills` requires per-skill entries (one-level scan);
   project-level whole-dir symlink works. Verify APM's deploy shape
   matches the harness's actual scan behavior.
3. Settings/permissions layer (Claude `settings.json` beyond hooks,
   model defaults, allowlists) — likely outside APM's primitive set;
   expect the wrapper to own it.

## Consequence for the architecture

```
agent-dotfiles repo (canonical: skills/, instructions/, hooks/, agents/, mcp)
        │  apm.yml (deps: own package + superpowers/etc, pinned) + apm.lock.yaml
        ▼
  apm install -g && apm compile --global     ← backbone (CC, Codex, Copilot)
        │
        ▼
  sync wrapper (small script)                ← Pi projection, settings layer,
                                               anything APM won't own
```

The wrapper is additive, not a fork: if APM gains Pi support, the wrapper
shrinks.
