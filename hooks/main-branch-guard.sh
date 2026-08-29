#!/bin/bash
# PreToolUse guard (agent-dotfiles#276, table row 3).
#
# Rule: never commit to main (agent-supervisor/AGENTS.md, "Conventions":
# "Branch with a type prefix; never commit to main."). A branch check before
# a commit is a fact, not a judgement call.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

RULE="main-branch-guard (agent-dotfiles#276)"
hook_require_parsed "$RULE"

# Only in scope for an actual commit invocation.
hook_command_violates "$RULE" main || exit 0

# --dry-run never writes a commit; nothing to guard.
# Determine the branch this commit would land on. Prefer the working
# directory tool_input may have run in (cwd from the hook payload) so a
# `git -C <path> commit` or `cd x && git commit` targeting a different repo
# is checked correctly; fall back to the process's own cwd.
TARGET_DIR="$(printf '%s' "$HOOK_STDIN" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
print(data.get("cwd", "") or "")
' 2>/dev/null)"
[ -n "$TARGET_DIR" ] || TARGET_DIR="$PWD"

BRANCH="$(git -C "$TARGET_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null)"

if [ -z "$BRANCH" ]; then
  # Not a git repo, or HEAD unreadable -- cannot establish the branch this
  # commit would land on. Fail closed rather than assume it is safe.
  hook_block "$RULE" \
    "could not determine the current branch in '$TARGET_DIR' to confirm this commit is not landing on main -- refusing rather than guessing."
fi

# "HEAD" (detached) is not main -- rebases and tag checkouts detach
# legitimately and are out of scope for this rule; only the named branch
# main is blocked.
if [ "$BRANCH" = "main" ]; then
  hook_block "$RULE" \
    "this would commit directly to 'main'. Branch with a type prefix (docs/, feat/, chore/, fix/, lane/NNN-...) and open a PR instead -- agent-supervisor/AGENTS.md, 'Conventions': 'never commit to main'."
fi

exit 0
