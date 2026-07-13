# E16 Current-Tree Regression — 2026-07-13

- **Environment:** brand-new `agentprdtest` Linux user on
  `remote.hill90.com` (AlmaLinux 10.2), with Claude Code 2.1.207 and Pi
  0.80.6 installed before bootstrap.
- **Source:** the complete local working tree transferred with symlinks
  preserved. This avoids testing the older GitHub `main` revision.
- **Authentication:** intentionally absent (`claude auth status` reported
  `loggedIn: false`). No credential from the earlier session was reused.

## Results

| Check | Result |
|---|---|
| Fresh `./install.sh --non-interactive` | PASS, 12 seconds |
| Doctor | PASS 4/4 |
| Repository validation without site packages (`python3 -S`) | PASS, 9 skills, 0 errors/warnings |
| Unit suite on remote at capture time | PASS, 38 tests |
| Default skill roster | PASS, exactly 7; `primer` and `closing-the-loop` absent |
| Pi projection | PASS, fresh `~/.pi/agent/AGENTS.md` |
| Memory skeleton | PASS, index/log/facts created |
| Forced recompile after injecting a marker-owned stale sentinel | PASS, sentinel removed on re-apply |
| E15, Pi thickest total | PASS, ~1,793 tokens of 8,000 |

E15 components were measured as canonical instructions 895 tokens, Pi
overlay 462, seven deployed skill descriptions 428, and the fresh memory
index 9. Generated-file sizes were also checked (Claude root 3,533 bytes;
Pi root 5,365 bytes).

One additional local regression test was added afterward for preserving the
last-known-good root when a successful compile skips regeneration. The final
branch suite therefore contains 39 tests; Pi ran that complete suite during
the final release review. The production sync code exercised remotely did not
change after the remote run.

## Behavioral evidence boundary

E14 skill triggering and E12 agent-driven write/recall were not re-run because
the clean account had no model credentials. Their authenticated evidence is
the earlier attempt-2 result. The current-tree changes do not alter canonical
instructions, the `gh-cli` skill, or `memory-conventions`; this run verifies
that those same assets are present in the corrected seven-skill deployment.
Therefore v1 release acceptance uses the two records together: attempt 2 for
model behavior, this regression for the final bootstrap and deployment code.

This is not evidence for macOS-only Obsidian application integration or a
fully authenticated fresh Pi provider. Those remain separate platform/account
checks rather than claims made by this run.
