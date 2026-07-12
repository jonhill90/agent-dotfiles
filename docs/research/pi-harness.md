# Phase 0: Pi Harness Survey

- **Date:** 2026-07-11 — **complete** (installed 0.80.6 on Jon's Mac via
  `npm install -g @earendil-works/pi-coding-agent`; docs ship inside the
  npm package under `docs/`).
- **What Pi is:** Mario Zechner's minimal coding agent CLI. Deliberate
  philosophy: small core, no built-in MCP, sub-agents, permission
  popups, plan mode, or to-dos — all of that is meant to come from
  extensions, skills, and packages. That makes Pi the *maximum-need*
  target for the behavioral layer, and the honest test bed for "same
  loop on any model" (model/provider switching is first-class:
  `--provider/--model`, Ctrl+P cycling).

## Layer support

| Layer | Pi surface |
|---|---|
| Skills (user) | `~/.pi/agent/skills/` AND **`~/.agents/skills/`** (native, recursive, symlinks per Agent Skills standard; lenient validation) |
| Skills (project) | `.pi/skills/`, `.agents/skills/` in cwd + ancestors (requires project trust) |
| Skills (extra) | settings `skills` array — can point at `~/.claude/skills`, `~/.codex/skills`; `--skill <path>` CLI |
| Skill triggering | descriptions in system prompt (spec-standard XML), progressive disclosure; `/skill:name` forces load |
| Instructions | `~/.pi/agent/AGENTS.md` global; project `AGENTS.md` **or `CLAUDE.md`** from parents + cwd |
| Hooks-equivalent | extensions (TS modules): `session_start`, `session_compact`, `agent_end`, `context` (message injection) — bootstrap pattern proven by superpowers' `.pi/extensions` |
| MCP | **none built-in by design** — available only via extensions/packages |
| Settings | `~/.pi/agent/settings.json` (global), `.pi/settings.json` (project) |
| Packages | `pi install <source>` manages extension packages; `package.json` `pi.skills` entries |
| Trust model | project-local settings/skills/extensions require explicit trust (`~/.pi/agent/trust.json`, `/trust`); non-interactive modes follow `defaultProjectTrust` |

## Findings

1. **The neutral-path convergence is now 3 of 4.** Pi reads
   `~/.agents/skills/` natively, alongside Codex and Copilot. Claude
   Code remains the only harness needing projection (per-skill symlinks
   — officially supported). The dotfiles' skill layer is nearly
   projection-free.
2. **Instructions:** `~/.pi/agent/AGENTS.md` is just another root file —
   the wrapper writes it from the same canonical AGENTS.md that APM
   compiles for the others (APM has no Pi target, so the wrapper owns
   this one file).
3. **Behavioral layer earns maximum value here.** No native plan mode,
   verification norms, or memory: everything Fable-era Claude Code does
   natively must come from the dotfiles on Pi. Per-harness thinning
   (harness-baselines Finding 3) has its two poles: CC = thinnest,
   Pi = thickest.
4. **MCP absence validates the CLI-first rule.** Tool skills that wrap
   CLIs (gh, az, obsidian-cli, mslearn) work on Pi unchanged; MCP-only
   capabilities don't. The dotfiles should prefer CLI-backed skills and
   treat MCP as a per-harness enhancement — consistent with the
   memory-backends decision.
5. **Trust model affects sync design:** global (`~/.pi/agent/`) content
   loads without prompts; project-level `.pi/`/`.agents/` needs a trust
   decision. Dotfiles install at global scope → frictionless.
6. **Memory:** none native. The memory conventions skill + vault (see
   memory-backends.md) is the only memory Pi gets — parity depends on it.

## Remaining verify (spec phase, low risk)

- Extension install/run mechanics for a *local* extension (the wrapper's
  bootstrap injector): `pi install <local path>` vs settings `extensions`
  entry.
- Whether superpowers' published package installs cleanly on Pi 0.80.x
  (`pi install` from its repo) — decides chassis packaging for Pi.
