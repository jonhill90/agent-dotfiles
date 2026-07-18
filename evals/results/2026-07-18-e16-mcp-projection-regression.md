# E16 mechanical regression — MCP projection change (2026-07-18)

Trigger: PR #33 changed projection code (`sync.py` MCP merge), which per
[docs/evals.md](../../docs/evals.md) requires another clean mechanical run.

- Platform: `remote.hill90.com` (AlmaLinux 10.2, Python 3.12.13), brand-new
  Linux user `e16-mcp-regress`, no model credentials.
- Bootstrap: clone + `./install.sh --non-interactive` → **19 seconds**,
  doctor all pass; the new `mcp-env-CONTEXT7_API_KEY` check correctly
  **warns** (not fails) when the env var is unset.
- Skills: exactly the seven default skills in `~/.agents/skills`.
  `~/.claude/skills` absent because Claude Code is not installed there —
  same condition as the 2026-07-13 regression; unchanged behavior.
- **New surface under test — MCP projection: PASS.** `~/.claude.json`
  `mcpServers` = context7, deepwiki, microsoft-learn; `sync status`
  reports all three `[ok]` with 0 issues.
- Settings fragment merge: PASS — `enabledPlugins` (3), 
  `alwaysThinkingEnabled`, `effortLevel` present in
  `~/.claude/settings.json`.
- Suite: 48 tests OK on the fresh machine; validation 0 errors/0 warnings
  in both normal and `python3 -S` (no-PyYAML) modes.
- E15 static estimate on the fresh box: instructions 883t + skill
  frontmatter 481t + index reserve 1,500t ≈ **2,864/8,000** (conservative:
  full frontmatter counted, not descriptions only).

Boundary: as before, this run supplies deployment evidence only (no model
credentials on the remote account); behavioral assets are byte-unchanged
since the 2026-07-13 attempt-2 pass except the additive MCP/settings
surfaces verified above. Temp user removed after the run.
