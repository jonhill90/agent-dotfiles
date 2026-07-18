# Acceptance: gh-cli

Tasks the skill must let the agent complete (SPEC §10 tool-skill track).
A community candidate displaces this skill only by passing all checks
with equal-or-fewer tokens loaded.

1. Open a PR from the current branch with title and multi-line body;
   verify it exists with `gh pr view`.
2. Check a PR's merge readiness (checks, mergeability) via JSON output
   and report it accurately.
3. List failing workflow runs for the repo and fetch the log of one
   failing job.
4. Create an issue with labels, then close it with a comment.
5. Add an inline review comment to a PR diff.

PASS: all five completed without fabricated flags (no invented `gh`
syntax; commands verified against `--help` when unsure).
