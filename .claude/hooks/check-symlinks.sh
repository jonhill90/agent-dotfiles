#!/bin/bash
# PostToolUse (Bash) hook: checks for broken symlinks after move/rename commands.
# Discovers symlinks dynamically via find, verifies each target resolves.
# Non-blocking: exits 0 with systemMessage listing broken links.
# Soft-requires jq — degrades silently if missing.
#
# Limitation: command detection is best-effort string matching. It will
# false-positive on quoted/echoed move commands (e.g., echo "mv foo bar")
# and miss edge forms like aliased moves. This is an accepted tradeoff —
# the hook is non-blocking (exit 0 + systemMessage), so false triggers
# just add a cheap symlink check.

set -euo pipefail

# Guard: jq required
command -v jq >/dev/null 2>&1 || exit 0

# Read stdin JSON (hook input)
INPUT=$(cat)

# Guard: empty input
[ -z "$INPUT" ] && exit 0

# Extract command from tool_input
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Guard: missing command
[ -z "$COMMAND" ] && exit 0

# Check if command involves a move/rename operation (best-effort detection)
IS_MOVE=false
if echo "$COMMAND" | grep -qE '(^mv |[;&|] *mv | mv |git mv |^rename )'; then
    IS_MOVE=true
fi

# Exit silently for non-move commands
[ "$IS_MOVE" = false ] && exit 0

# Determine project dir
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# Discover all symlinks in the repo (maxdepth 4 covers all current depths)
BROKEN_LINKS=""
while IFS= read -r LINK; do
    # A symlink that exists as -type l but fails [ -e ] is broken
    if [ ! -e "$LINK" ]; then
        TARGET=$(readlink "$LINK" 2>/dev/null || echo "unknown")
        BROKEN_LINKS="${BROKEN_LINKS}  - ${LINK} -> ${TARGET}\n"
    fi
done < <(find "$PROJECT_DIR" -maxdepth 4 -type l \
    -not -path '*/.git/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/vendor/*' 2>/dev/null)

# Report broken links if any found
if [ -n "$BROKEN_LINKS" ]; then
    MESSAGE=$(printf "Broken symlinks detected after move command:\n%b\nFix these before committing." "$BROKEN_LINKS")
    echo "$MESSAGE" | jq -Rs '{ systemMessage: . }'
fi

exit 0
