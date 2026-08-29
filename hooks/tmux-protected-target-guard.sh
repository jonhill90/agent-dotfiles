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

if hook_command_violates "$RULE" protected; then
  hook_block "$RULE" \
    "this command addresses a protected tmux target or writes, replaces, or reloads ~/.tmux.conf. These are operator-owned resources, not lane-owned ones."
fi

exit 0
