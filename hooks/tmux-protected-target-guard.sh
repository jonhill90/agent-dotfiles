#!/bin/bash
# PreToolUse guard (agent-dotfiles#276, table row 2).
#
# Rule: never touch the supervisor's own window (agent-supervisor:1), the
# operator's real tmux config (~/.tmux.conf), or the Hill90 family of
# sessions (Hill90, hill90-app, hill90-docs) from an agent's tmux command.
# These names are a fixed denylist -- a string match on the target, not
# judgement.
#
# Known scope limit, stated rather than silently overclaimed: "never touch
# another lane" (the brief's third clause) needs to know which lane is
# running to tell "another" from "mine", and a stateless hook has no such
# identity by default. This guard enforces the denylist half, which is the
# fully mechanical part. If a harness starts exporting the current lane name
# (e.g. AGENT_LANE_TARGET), extend the check below -- do not silently widen
# the denylist to guess at it.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

RULE="tmux-protected-target-guard (agent-dotfiles#276)"
hook_require_parsed "$RULE"

# Session/window identifiers that must never appear as a tmux target or
# argument, regardless of verb -- reading a protected pane is also not the
# job of an agent's tmux command (use the supervisor's own read surface).
PROTECTED_RE='agent-supervisor:1|=Hill90|\bHill90\b|hill90-app|hill90-docs'

case "$HOOK_COMMAND_PREFIX" in
  *tmux*)
    if echo "$HOOK_COMMAND_PREFIX" | grep -qE "$PROTECTED_RE"; then
      hook_block "$RULE" \
        "this tmux command names a protected target (agent-supervisor:1, the Hill90 session, hill90-app or hill90-docs). These are the operator's own panes/sessions, not lane-owned ones -- an agent must never address them directly."
    fi
    ;;
esac

# This sub-rule cannot use HOOK_COMMAND_PREFIX: an ordinary direct write
# commonly has a quoted payload before its redirection (for example,
# `echo 'set -g mouse on' >> ~/.tmux.conf`). Matching that prefix would
# silently allow a real mutation. Keep its narrow, write-shaped raw match;
# protected tmux-target detection above uses the shared prefix.
if echo "$HOOK_COMMAND" | grep -qE '\.tmux\.conf'; then
  if echo "$HOOK_COMMAND" | grep -qE '(>>?[^&]*\.tmux\.conf|tee\b.*\.tmux\.conf|source-file\b.*\.tmux\.conf|sed\s+-i.*\.tmux\.conf|\bmv\b.*\.tmux\.conf|\bcp\b.*\.tmux\.conf)'; then
    hook_block "$RULE" \
      "this command writes to, replaces, or reloads ~/.tmux.conf, the operator's real tmux config. Experiment on the operator's disposable remote sandbox instead (NOTEBOOK-jon-directives.md standing rule 11: 'never touch his tmux config')."
  fi
fi

exit 0
