#!/bin/bash
# PreToolUse guard (agent-dotfiles#276, table row 4).
#
# Rule: post gh api bodies with -f body="$(cat file)", never --body-file or
# an @file value on -f. Two distinct, well-known gh footguns this catches:
#
#   1. `gh api` has no --body-file flag at all (that flag belongs to
#      `gh issue comment` / `gh pr create`, not `gh api`) -- passing it to
#      `gh api` is a silent no-op or an error, not the post it looks like.
#   2. `gh api ... -f body=@file` sends the LITERAL STRING "@file" as the
#      body. `-f` never reads a file; only `-F` (typed fields) treats a
#      leading @ as "read this file". Swapping -f for -F is one character
#      and behaves completely differently, which is exactly the class of
#      bug notify.sh's own test guards against for a different tool
#      (test_notify.sh: a literal "--body-file" string became the message
#      body because the script had no such flag).
#
# The safe, required form: -f body="$(cat file)" -- shell-expand the file's
# content into a literal string before gh ever sees it.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

RULE="gh-body-guard (agent-dotfiles#276)"
hook_require_parsed "$RULE"

# Only in scope for gh api calls.
echo "$HOOK_COMMAND" | grep -qE '(^|[;&|]|\s)gh\s+api\b' || exit 0

if echo "$HOOK_COMMAND" | grep -qE '\-\-body-file\b'; then
  hook_block "$RULE" \
    "'gh api' has no --body-file flag -- it belongs to 'gh issue comment'/'gh pr create', not 'gh api'. Use -f body=\"\$(cat file)\" instead."
fi

# -f body=@... or -F body=@... where the field name is body specifically
# (other -F fields legitimately read files, e.g. uploading an asset).
if echo "$HOOK_COMMAND" | grep -qE '\-f\s+body=@'; then
  hook_block "$RULE" \
    "'-f body=@file' sends the literal string \"@file\" as the body -- -f never reads a file, only -F does. Use -f body=\"\$(cat file)\" instead."
fi

exit 0
