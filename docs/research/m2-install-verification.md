# M2 Verification: `apm install -g` End-to-End

- **Date:** 2026-07-12 — **M2 done-when met** (SPEC §12)
- **Method:** isolated trial first (`HOME=/tmp/apm-m2-trial`), then the
  real install on Jon's Mac. APM 0.24.1.

## Results

| Check | Result |
|---|---|
| `apm install -g <repo-path>` from the M1 layout | ✅ 8 skills + 2 agents + 1 global instruction resolved via the `.apm/` symlinks |
| Skills → `~/.agents/skills/` | ✅ all 8 |
| Skills → `~/.claude/skills/` | ✅ all 8 (real machine; trial fake-HOME skipped it — APM only targets harness dirs it detects) |
| Pre-existing npx-installed skills (find-skills, grill-me, grill-with-docs) | ✅ untouched |
| Agents → `~/.claude/agents/` | ✅ code-reviewer, researcher |
| Root context files marker-owned | ✅ `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.copilot/AGENTS.md` (+ cursor, kiro, hermes, opencode, windsurf) |
| Hand-authored files preserved | ✅ `~/.gemini/GEMINI.md` skipped ("hand-authored"); old 0-byte `~/.claude/CLAUDE.md` backed up to `CLAUDE.md.pre-dotfiles` before install (SPEC §3.2) |
| User-scope manifest | ✅ repo listed in `~/.apm/apm.yml` (local path, dev mode) |
| Claude Code live pickup | ✅ user-scope skills appeared in the running session |

## Findings for the wrapper (M3 job list, confirmed on this machine)

1. **`apm install -g` compiles root files itself** — a separate
   `compile --global` afterwards reports "no changes". The wrapper
   pipeline can treat compile as idempotent/optional after install.
2. **Wart 2 confirmed live:** compile hard-fails on this machine's five
   OneDrive mounts until `APM_COPILOT_COWORK_SKILLS_DIR` is set. Pinned
   to **OneDrive-Personal** (never an employer mount) in `~/.zshrc`;
   `install.sh`/doctor must own this permanently.
3. **Unused-harness root files created** (cursor, kiro, hermes,
   opencode, windsurf) — wart 3; wrapper teardown/target-filtering
   (V3) as specified.
4. **Duplicate skill identities while developing:** with the repo's
   project-scope symlinks still present, sessions in this repo see each
   skill twice (user + project scope). Resolves at M3 when the
   committed projections retire.
5. **Benched skills deploy anyway:** `closing-the-loop` and `primer`
   are in `skills/` so APM installs them. Baseline-stack benching
   (M1.5) needs enforcement at M5 baseline day — either temporary
   removal on the eval machine or manifest-level exclusion.
6. **Agent lint gap:** APM warns both agents use `tools:` as a YAML
   list, which OpenCode rejects (wants a name→bool mapping). Harmless
   for CC; fix or scope agents when OpenCode/Copilot become targets.
