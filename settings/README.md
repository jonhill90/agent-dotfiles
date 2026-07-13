# settings/

Wrapper-owned configuration fragments (SPEC §3.4–3.5). APM does not
manage these surfaces; `scripts/sync.py apply` merges them into each
harness's live config, tracking managed keys in
`~/.agent-dotfiles/state.json` so `sync remove` can undo them.

| File | Merged into | Contents |
|---|---|---|
| `claude/settings.json` | `~/.claude/settings.json` | Permission allowlists, hook wiring, model defaults |
| `pi/settings.json` | `~/.pi/agent/settings.json` | Skill paths, extension entries, trust defaults |
| `mcp/servers.json` | per-harness MCP config (APM-projected where supported) | Declared MCP servers |

Rules:

- Fragments are **merge patches**, not full files: only managed keys
  appear here; unmanaged keys in live configs are never touched.
- **No secrets.** Auth rides environment variables (`${VAR}` form) or
  the OS keychain; `sync doctor` reports missing variables.
- Machine-local values belong in untracked local overrides, never in
  this directory.

## Environment variables

Machine-local, set in the shell profile (secrets in an untracked
`~/.zshrc.local`, sourced from `~/.zshrc`):

| Variable | Used by | Purpose |
|---|---|---|
| `AGENT_MEMORY_VAULT` | memory conventions, `sync doctor` | Personal memory vault path (never employer storage) |
| `APM_COPILOT_COWORK_SKILLS_DIR` | `apm compile -g` | Pins the Cowork target when multiple OneDrive mounts exist |
| `CONTEXT7_API_KEY` | context7 MCP server | Library documentation API |
| `AZURE_DEVOPS_PAT` | az-devops skill | Azure DevOps personal access token |
