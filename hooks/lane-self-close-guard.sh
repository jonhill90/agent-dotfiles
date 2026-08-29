#!/bin/bash
# PreToolUse guard (agent-dotfiles#276, table row 5).
#
# Rule: a lane never closes its own issue -- the issue that dispatched it is
# not this lane's to certify done. Scope, stated rather than overclaimed:
# this only fires on the standard lane branch naming convention
# (<type>/<N>-<slug>, e.g. lane/276-rules-to-hooks), since that number is
# where "which issue is this branch FOR" is knowable at all. A branch that
# does not carry an issue number makes no claim this guard can check, so it
# is out of scope rather than blocked -- there is no "self" to detect.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

RULE="lane-self-close-guard (agent-dotfiles#276)"
hook_require_parsed "$RULE"

# A close can arrive two ways: the porcelain `gh issue close <N>` or the
# REST form `gh api .../issues/<N> -X PATCH -f state=closed` (also matches
# -f "state=closed" with a leading space).
CLOSE_NUM=""
if echo "$HOOK_COMMAND_PREFIX" | grep -qE '(^|[;&|]|\s)gh\s+issue\s+close\b'; then
  CLOSE_NUM="$(echo "$HOOK_COMMAND_PREFIX" | grep -oE 'gh\s+issue\s+close\s+[^ ]+' | grep -oE '[0-9]+' | head -1)"
elif echo "$HOOK_COMMAND_PREFIX" | grep -qE 'gh\s+api\b.*/issues/[0-9]+' && echo "$HOOK_COMMAND_PREFIX" | grep -qE 'state=closed'; then
  CLOSE_NUM="$(echo "$HOOK_COMMAND_PREFIX" | grep -oE '/issues/[0-9]+' | grep -oE '[0-9]+' | head -1)"
fi

[ -n "$CLOSE_NUM" ] || exit 0

# Which issue is this branch FOR? Convention across this estate:
# <type>/<N>-<slug> (lane/276-rules-to-hooks, fix/234-harness-argv, ...).
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
[ -n "$BRANCH" ] || exit 0  # not a git repo / no branch -- no "own issue" to check

OWN_ISSUE="$(echo "$BRANCH" | grep -oE '^[a-z]+/([0-9]+)-' | grep -oE '[0-9]+')"
[ -n "$OWN_ISSUE" ] || exit 0  # branch names no issue -- nothing this guard can verify

if [ "$OWN_ISSUE" = "$CLOSE_NUM" ]; then
  hook_block "$RULE" \
    "this closes issue #$CLOSE_NUM, and the current branch '$BRANCH' is dispatched against that same issue. A lane never closes its own issue -- that certification belongs to whoever reviews the PR, not the lane that wrote it."
fi

exit 0
