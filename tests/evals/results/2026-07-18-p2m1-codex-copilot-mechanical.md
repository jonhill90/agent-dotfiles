# P2-M1 mechanical verification — Codex + Copilot (2026-07-18)

Scope: SPEC §13 P2-M1 (mechanical layer only; behavioral columns P2-M2
remain open). Platform: Jon's Mac, Codex CLI 0.144.1, Copilot CLI 1.0.70.

- **V5 resolved hands-on.** APM writes both `~/.copilot/AGENTS.md` and
  `~/.copilot/copilot-instructions.md` marker-owned; both harnesses read
  `~/.agents/skills` natively; APM projects `agents/*.md` to
  `~/.copilot/agents/*.agent.md`; neither harness has a hook surface.
- **Codex MCP projection: PASS.** `sync apply` wrote the marker block in
  `~/.codex/config.toml`; `tomllib` parses the result; Codex's own
  servers (`node_repl`, `computer-use`) untouched. Authoritative check:
  `codex mcp list` shows context7 (bearer env `CONTEXT7_API_KEY`),
  deepwiki, microsoft-learn all **enabled**.
- **Copilot MCP projection: PASS.** `sync apply` wrote
  `~/.copilot/mcp-config.json`; from a neutral cwd `copilot mcp list`
  reports all three as **User servers** (user scope confirmed, not the
  repo's workspace `.mcp.json`).
- **Headless boot smoke.** `codex exec` runs under the managed
  instructions (cited the projected global instructions). Note: in exec
  mode the model reported context7 unavailable while `codex mcp list`
  shows it enabled — registration is the authoritative surface; tool
  visibility in exec mode is a harness behavior to observe in P2-M2.
- **Status/doctor.** `sync status` reports nine `mcp:<surface>:<name>`
  rows, 0 issues; doctor passes root-file checks for claude, codex, and
  copilot. Suite: 59 tests OK; validation 0 errors both modes.

Boundary: no behavioral scenarios were scored in this run. Codex and
Copilot remain non-release-blocking until P2-M2's E1–E15 columns pass
twice consecutively.
