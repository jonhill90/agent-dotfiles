# Harness Engineering

This document records the current deployment model and the verified harness
boundaries. The dated investigation that produced these decisions remains in
git history, principally commits `106e69c`, `c089a95`, `8a222ce`, `065bc9d`,
and `dff03d0`.

## Deployment model

APM CLI 0.24.1 is the user-scope backbone. `apm install -g` deploys the
package and `apm compile -g` generates marker-owned root instructions. The
wrapper in `scripts/sync.py` performs the work APM does not own:

- aborting when install or compile fails;
- projecting Pi's global instructions and settings;
- ensuring the neutral `~/.agents/skills` surface exists;
- merging wrapper-owned settings without replacing unmanaged keys;
- removing generated roots for unused harnesses; and
- checking machine-local requirements without storing secrets.

APM's generated marker is the ownership boundary. Hand-authored files are not
silently overwritten or deleted. Canonical content stays in top-level source
directories; `.apm/` is only the package view.

## Harness matrix

| Surface | Claude Code | Pi | Codex / Copilot |
|---|---|---|---|
| User skills | `~/.claude/skills` | `~/.agents/skills` | `~/.agents/skills` |
| Global instructions | APM-generated `CLAUDE.md` | wrapper-generated `AGENTS.md` | APM-generated AGENTS-family file |
| Hooks | rich native lifecycle | extension events | no v1 dependency |
| MCP | wrapper → `~/.claude.json` | deliberately absent | wrapper → `config.toml` block / `mcp-config.json` |
| Long-term memory | shared vault plus native session memory | shared vault | shared vault (conventions skill) |
| Release status | v1 behavioral target | v1 behavioral target | Phase 2: sync-managed; eval columns pending |

Pi's lack of MCP is a useful portability constraint: a first-class capability
must have a CLI or direct-file path. MCP can improve a capable harness, but it
cannot be the only way to use a capability. This is also the standing answer
to alternatives-to-MCP research: prefer native CLIs, direct files, and
harness-native APIs; add MCP only when those do not provide the needed
semantics and a non-MCP degradation path exists.

## Verified facts and boundaries

- APM follows in-package symlinks whose targets remain inside the package.
- APM user-scope targeting can vary with detected harness state, so the
  wrapper guarantees the neutral skills directory after installation.
- APM global compile may create files for detected but unused harnesses; the
  wrapper removes only marker-owned unused files.
- APM has no Pi target. Pi natively reads `~/.agents/skills` and uses
  `~/.pi/agent/AGENTS.md`, so its adapter remains small.
- Claude Code is the thinnest v1 surface; Pi's overlay supplies the extra
  safety gates that its minimal harness lacks.
- Codex and Copilot Phase 2 mechanics, verified hands-on 2026-07-18 on
  macOS (Codex CLI 0.144.1, Copilot CLI 1.0.70):
  - APM writes **both** `~/.copilot/AGENTS.md` and
    `~/.copilot/copilot-instructions.md` as marker-owned files, so the
    per-platform filename question (V5) is moot — content lands on
    whichever surface the CLI reads.
  - Copilot reads MCP servers from `~/.copilot/mcp-config.json`
    (standard `mcpServers` schema); the wrapper merges the declared set
    there with state-tracked reversal.
  - Codex has no user-scope JSON MCP surface; its `~/.codex/config.toml`
    carries `[mcp_servers.<name>]` tables (`url` +
    `bearer_token_env_var`). The wrapper owns a marker-delimited block
    and never touches servers defined outside it.
  - APM's agents primitive already projects `agents/*.md` to
    `~/.copilot/agents/*.agent.md`.
  - Both harnesses read `~/.agents/skills` natively; no extra skill
    projection is needed.
  - Behavioral eval columns (E14-class degraded mode — no hook surface)
    are still required before Codex/Copilot breakage blocks release.
- The bootstrap is portable across macOS and Linux for its shared core.
  Obsidian application integration is macOS-only and optional; memory itself
  uses direct files.

The public repository contains architecture, contracts, test fixtures, and
results. Machine inventories, credentials, raw transcripts, and private vault
content do not belong here.
