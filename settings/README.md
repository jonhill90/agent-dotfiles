# settings/

Wrapper-owned configuration fragments (SPEC §3.4–3.5). APM does not
manage these surfaces; `scripts/sync.py apply` merges them into each
harness's live config, tracking managed keys in
`~/.agent-dotfiles/state.json` so `sync remove` can undo them.

| File | Merged into | Contents |
|---|---|---|
| `claude/settings.json` | `~/.claude/settings.json` | Managed plugin roster, hook wiring, workflow preferences (`alwaysThinkingEnabled`, `effortLevel`) — permission allowlists and model selection stay machine-local, not in this fragment |
| `pi/settings.json` | `~/.pi/agent/settings.json` | Currently empty on disk; `sync.py` injects a `skills` denylist at merge time to enforce Pi's resolved skill roster |
| `mcp/servers.json` | per-harness MCP config (APM-projected where supported) | Declared MCP servers |
| `copilot/settings.json` | `~/.copilot/settings.json` (when `~/.copilot` exists) | `disabledSkills` roster enforcement |
| `default-skills.txt` | (not merged directly — parsed by `sync.py` to compute each harness's skill roster) | Shared + per-harness default skill lists, plus a `[benched]` section of authored-but-not-rostered skills |

**Corrected 2026-08-23:** the table above previously omitted `copilot/settings.json`
and `default-skills.txt`, and described `claude/settings.json` as holding
permission allowlists and model defaults it does not carry — see
`docs/SPEC.md` §3.5 ("Permission allowlists and model selection stay
machine-local ... until a portable set is curated — the fragment must never
invent permission grants").

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
