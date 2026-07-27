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
| MCP | wrapper → `~/.claude.json` | none shipped (0.80.6) | wrapper → `config.toml` block / `mcp-config.json` |
| Long-term memory | shared vault plus native session memory | shared vault | shared vault (conventions skill) |
| Per-skill disable | `skillOverrides` (v2.1.220) | `skills` denylist in `~/.pi/agent/settings.json` (0.80.6) | Codex `[[skills.config]]`; **Copilot: none** (V10) |
| Release status | v1 behavioral target | v1 behavioral target | **first-class since 2026-07-18** (P2-M3): breakage blocks release |

Pi ships no MCP support as of 0.80.6 — verified by grepping its distributed
`dist/` for `modelcontextprotocol`, `mcpServers`, and `MCP server`, which
returns nothing. That is **absent by default, not absent by design**: Pi
installs extensions (`pi install npm:…`), so a third-party bridge could add
it. The earlier wording here claimed the stronger fact.

The constraint that follows has two halves, and they are not equally
supported:

- **Degradation (evidence-backed, keep).** A capability must not be
  unusable when its transport fails. `basic-memory` was dropped for exactly
  this — an MCP server failure mid-session with no CLI fallback — and on
  2026-07-26 a misconfigured MCP connector resolved to the wrong workspace
  and returned success, which a CLI would have refused.
- **Primacy (over-fit, treat with care).** "CLI must be the canonical path"
  was generalised from one harness's missing feature. It excludes the web
  tier entirely, where a CLI-backed skill is inert and MCP is the only
  transport — so as a universal rule it inverts the portability goal that
  motivated it. It holds for the declared v1 harness set, all four of which
  are terminal; it is not a general law.

Prefer native CLIs, direct files, and harness-native APIs for the first-class
set; add MCP when those lack the needed semantics, and require a documented
degradation path either way.

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
- Codex/Copilot behavioral findings (P2-M2 baseline, 2026-07-18):
  - Codex spawns `zsh -l` shells: profile exports override per-session
    env vars (temp-vault redirection fails), and vault writes need
    `sandbox_workspace_write.writable_roots` to include the vault.
  - Codex's curated `github` plugin shadows the managed `github-cli` skill
    and survives `plugin remove` via cache re-sync (E14 unstable; open).
  - Copilot in print mode loads the global instructions but does not
    reliably bind guardrails (E11 fails with the gate provably in
    context); small focused skills bind where instructions do not
    (`safe-deletion`, `failing-test-first` — both eval-adopted).
  - **Confirmed across three harnesses 2026-07-26** by the E18 ladder: an
    instruction sentence bound on Claude Code (PASS ×2), flapped on Codex,
    and failed on Pi, which read the policy nine times in one run and edited
    on its own reasoning anyway. Instruction-binding is per-harness, not
    universal, and the per-harness roster (§4.1) is how the difference is
    paid for.
  - Copilot's `Auto` model routing changes the effective model per run
    and breaks behavioral consistency; the managed settings fragment
    pins the model.
  - Codex plugin-skill shadowing is durably fixed by `[[skills.config]]`
    per-skill disables in `config.toml`; `plugin remove` alone re-syncs.
  - Codex CLI auto-updates can interrupt interactive automation
    mid-session.
- The bootstrap is portable across macOS and Linux for its shared core.
  Obsidian application integration is macOS-only and optional; memory itself
  uses direct files.

The public repository contains architecture, contracts, test fixtures, and
results. Machine inventories, credentials, raw transcripts, and private vault
content do not belong here.
