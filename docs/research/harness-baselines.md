# Phase 0: Harness Baselines (Official Docs Sweep)

- **Date:** 2026-07-11
- **Question:** What does each first-class harness natively provide per
  layer? This determines what the dotfiles must supply vs. merely
  configure, and where the behavioral layer earns its tokens.
- **Sources:** code.claude.com/docs (skills, hooks, memory),
  developers.openai.com/codex → learn.chatgpt.com (skills),
  docs.github.com Copilot customization + agent-skills pages,
  github.blog changelog 2025-12-18 (Copilot Agent Skills GA).
  Pi: see `pi-harness.md` (partial).

## Layer × harness matrix

| Layer | Claude Code | Codex | Copilot (CLI/cloud) | Pi (partial) |
|---|---|---|---|---|
| Skills: user scope | `~/.claude/skills/` (symlinks followed; enterprise>personal>project precedence) | `~/.agents/skills/` (symlinks followed) | `~/.copilot/skills/` **or `~/.agents/skills/`** | extension `skillPaths` |
| Skills: project scope | `.claude/skills/` + nested dirs + parent walk | `.agents/skills/` walking up to repo root | `.github/skills`, `.claude/skills`, or `.agents/skills` | verify |
| Skill triggering | description match + `/name`; invocation control, subagent execution, dynamic context injection (CC extensions) | description match + `$skill` mention; progressive disclosure | description match; `/skills reload`, `/skills info` | description match (Agent Skills native) |
| Instructions | CLAUDE.md hierarchy (managed → `~/.claude/CLAUDE.md` → project → local) + `@imports` (4-hop) + `~/.claude/rules/` + `.claude/rules/` w/ `paths` scoping; symlinks supported; reads AGENTS.md only via import/symlink | `~/.codex/AGENTS.md` + repo AGENTS.md | `.github/copilot-instructions.md`, AGENTS.md (nearest wins), `.instructions.md` w/ `applyTo` globs; reads CLAUDE.md/GEMINI.md as fallback | verify |
| Hooks | 31 lifecycle events, 5 types (command/http/mcp_tool/prompt/agent), 5 config scopes incl. plugins and skill/agent frontmatter | none documented (verify: superpowers 6.1.1 notes mention "Codex SessionStart hook re-registration") | none documented | extension events: session_start, session_compact, agent_end, context (message injection) |
| MCP | `.mcp.json`, settings scopes | `~/.codex/config.toml` | VS Code `mcp.json`; CLI config (verify path) | verify |
| Memory (native) | CLAUDE.md + auto memory (`~/.claude/projects/<project>/memory/`, MEMORY.md index, 200-line/25KB session load) | none documented | none documented | verify |
| Config/permissions | settings.json (user/project/local/managed), permission rules, sandbox | config.toml incl. `[[skills.config]]` per-skill enable | limited documented | verify |

## Finding 1: `~/.agents/skills` is becoming the neutral user-scope path

Codex documents it as its user scope; Copilot accepts it as an
alternative to `~/.copilot/skills`. Claude Code does NOT read it (uses
`~/.claude/skills`, but entries may be symlinks — officially supported).

**Consequence:** the dotfiles' canonical installed-skill location can be
`~/.agents/skills` (or APM's `~/.apm/apm_modules` feeding it), with
Claude Code served by per-skill symlinks and Pi by `skillPaths`. Two of
four harnesses then need zero projection for skills.

## Finding 2: Hooks are the differentiating layer, and only Claude Code has real ones

- Claude Code: full lifecycle (SessionStart/PreToolUse/Stop/PreCompact…),
  five hook types, hooks shippable in plugins AND in skill/agent
  frontmatter.
- Pi: equivalent-enough via extension events (context injection covers
  the bootstrap pattern).
- Codex/Copilot: no documented hook surface. **Consequence:** on those
  two, behavioral enforcement must ride instructions (AGENTS.md) +
  skill descriptions alone — the eval scenarios (E14) must test exactly
  this degraded mode. This also means the "superpowers chassis"
  conclusion in distillation-matrix.md applies fully only to CC+Pi;
  verify what superpowers' Codex package actually does (release notes
  imply some Codex hook mechanism exists — resolve during hands-on).

## Finding 3: Claude Code native features overlap the behavioral layer (thinning confirmed as real question)

CC natively provides: auto memory w/ index budget (the exact
Karpathy-style pattern recommended in memory-backends.md), plan mode,
path-scoped rules, instruction hierarchy, live skill reload,
skills-dir-as-plugin packaging. The behavioral layer's static portion
should be near-zero on CC and carried by instructions on Codex/Copilot.
Per-harness thinning moves from "spec question" to "spec requirement."

## Finding 4: Official guidance aligns with the PRD's token rubric

- CC docs: CLAUDE.md target under 200 lines; auto-memory index capped at
  200 lines/25KB; "if it's a procedure, make it a skill; if it's a fact,
  memory/instructions."
- Codex: progressive disclosure is the documented loading model.
- These give the spec concrete static-budget anchors: global
  instructions ≤200 lines, memory index ≤200 lines, everything
  procedural in skills.

## Finding 5: Instructions projection is simpler than feared

Every harness reads AGENTS.md-family content *somewhere*:
- Codex/Copilot: natively (AGENTS.md; Copilot even falls back to CLAUDE.md).
- Claude Code: one-line `@AGENTS.md` import in CLAUDE.md (officially
  recommended pattern) or symlink.
- APM's `compile --global` writes exactly these per-harness root files.

**Consequence:** one canonical AGENTS.md in the dotfiles + trivial
per-harness pointers. The agent-scripts pointer pattern is officially
sanctioned now.

## Verify hands-on (spec phase)

1. Copilot CLI: MCP config path + user-scope instructions location
   (`~/.copilot/AGENTS.md` per APM's code — confirm against CLI docs).
2. Codex: whether any hook/notify mechanism exists (superpowers evidence
   vs docs silence).
3. Pi: full docs pass after install (instructions, MCP, settings).
4. Whether Copilot CLI honors `~/.agents/skills` symlinked entries the
   way Codex does.
