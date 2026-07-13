# E16 Attempt 2 — 2026-07-13 — PASS (Linux, owner-approved deviation)

- **Environment:** fresh Linux users on remote.hill90.com (AlmaLinux
  10.2). Owner decision: macOS GUI login declined; E16's criterion
  ("fresh machine, one command, behaves like Jon's agent") satisfied on
  Linux. Not covered: macOS-only surface (Obsidian app link, Darwin
  profile bits) — partially verified by macOS attempt 1's bootstrap.
- **Harness auth:** `claude setup-token` (no GUI anywhere). Pi
  installed (0.80.6); behavioral Pi runs skipped (provider OAuth not
  staged) — Pi covered by the M5 matrix.

## The definitive run (user e16b, uninterrupted, then-current main)

`git clone --depth 1` + `./install.sh --non-interactive` + verification:

| Check | Result |
|---|---|
| Bootstrap | rc=0; doctor 4/4 pass; compile+teardown ran (fixed pipeline) |
| E14 skill triggering | ✓ loop recited from deployed CLAUDE.md; named gh-cli |
| E12 write-back | ✓ fact + index + log entry in the fresh vault |
| E12 recall (new dir, new session) | ✓ recalled from vault |
| E15 budget | ✓ CC root 3,533B (~883t); Pi 5,365B (~1,341t); vs 8,000t cap |
| **Elapsed, clone→all checks green** | **53 seconds** (budget: 15 min) |

## Fixes shipped during E16 (each found live, TDD'd, merged)

1. PR #26: wrong PyPI package (`apm` → `apm-cli==0.24.1`).
2. PR #27: apply lacked `apm compile -g`; install.sh ignored doctor rc.
3. PR #28: `~/.pi/agent` init when pi installed-but-never-run; neutral
   skills dir pre-created.
4. PR #29: APM's neutral-path targeting proved unreliable (populated on
   re-install, not fresh install) — wrapper now mirrors claude-scope
   skills into an empty `~/.agents/skills` (verified: neutral=9,
   status clean). Landed after the 53s run; verified by re-apply on
   the same user.

## Notes

- Attempt 1 (macOS) remains FAILED on record; its two blockers are
  PRs #26/#27 above.
- Benched skills (closing-the-loop, primer) deploy on fresh machines —
  known gap (manifest-level exclusion), tracked since M2, not
  E16-blocking.
- The recall prompt "when do I take notes?" was misread as a question
  about the agent's own note-taking; unambiguous phrasing recalls
  correctly. Scenario prompts should name the user explicitly.
- Cleanup: e16test and e16b deleted with homes; setup token to be
  revoked by Jon.

**PRD primary success criterion: MET.**
