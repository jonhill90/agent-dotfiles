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
# content into a literal string before gh ever sees it. `-F body=@file` is
# the typed form gh does read from a file, and is not blocked.
#
# What is matched, and what is not (agent-dotfiles#356, #358): the rule
# reads the parsed command -- lib/command_guard.py's `gh-body` -- so a flag
# that is only NAMED, inside a quoted -f body="..." string, a heredoc, or a
# shell comment, is an argument or nothing, never a use. Each -f/--raw-field
# spelling of body=@ blocks, including -fbody=@x, -f=body=@x, -if=body=@x
# and --raw-field=body=@x, and so does --body-file in either its spaced or
# its --body-file=x form.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

RULE="gh-body-guard (agent-dotfiles#276)"
hook_require_parsed "$RULE"

# Only in scope for gh api calls.
if hook_command_violates "$RULE" gh-body; then
  hook_block "$RULE" \
    "'gh api' has no --body-file flag (it belongs to 'gh issue comment'/'gh pr create'), and '-f body=@file' sends the literal text \"@file\" as the body -- -f never reads a file. Use -f body=\"\$(cat file)\" instead; -F body=@file, the typed field gh does read from a file, is also allowed."
fi

exit 0
