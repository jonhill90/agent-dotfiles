#!/bin/bash
# PreToolUse guard (agent-dotfiles#276, table row 1).
#
# Rule: a destructive tmux verb (kill-server, kill-session, kill-window,
# respawn-*) must run against an isolated socket, never the operator's real
# one. A bare `tmux kill-server` from a single lane destroyed the whole live
# estate three times in one day, including sessions unrelated to that lane
# (agent-supervisor#247, closed by promoting exactly this scoping pattern).
#
# The scoped-safe form this guard requires, verbatim from agent-supervisor's
# own convention (AGENTS.md invariant 4):
#   TMUX_TMPDIR=$(mktemp -d) env -u TMUX tmux kill-server
# i.e. TMUX_TMPDIR pointed at a fresh directory (a real socket path, not the
# default), in the SAME command, with TMUX unset so tmux cannot fall back to
# an inherited server. Missing either half still reaches the operator's
# server, so both are required.
#
# This is pattern matching on a shell command, not judgement -- exactly the
# case RULE A says gets written as code, not re-argued by a model every turn.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

RULE="tmux-destructive-verb-guard (agent-dotfiles#276 / agent-supervisor#247)"
hook_require_parsed "$RULE"

# Only Bash commands that actually mention tmux are in scope.
case "$HOOK_COMMAND" in
  *tmux*) : ;;
  *) exit 0 ;;
esac

# Destructive verbs. respawn-pane / respawn-window both match respawn-*.
DESTRUCTIVE_RE='kill-server|kill-session|kill-window|respawn-pane|respawn-window'

echo "$HOOK_COMMAND" | grep -qE "$DESTRUCTIVE_RE" || exit 0

# From here on the command names a destructive verb. It is allowed ONLY if
# BOTH halves of the isolation idiom are present in the same command:
#   1. TMUX_TMPDIR=... (a real value, not empty/unset)
#   2. env -u TMUX (or an equivalent explicit unset of TMUX) ahead of tmux
# Fail closed: if we cannot confirm both, refuse. Guessing "probably fine"
# is exactly the class of error agent-dotfiles#228/#230/#235 recorded.

if ! echo "$HOOK_COMMAND" | grep -qE 'TMUX_TMPDIR='; then
  hook_block "$RULE" \
    "a destructive tmux verb (kill-server/kill-session/kill-window/respawn-*) with no TMUX_TMPDIR scoping. This targets the operator's real server. Required form: TMUX_TMPDIR=\$(mktemp -d) env -u TMUX tmux <verb> ... -- see agent-supervisor#247 (a bare 'tmux kill-server' destroyed the live estate three times, including sessions unrelated to the lane that ran it)."
fi

if ! echo "$HOOK_COMMAND" | grep -qE '(^|[;&|]|\s)env\s+-u\s+TMUX\b'; then
  hook_block "$RULE" \
    "TMUX_TMPDIR is set but TMUX is not unset in the same command (missing 'env -u TMUX'), so tmux can still resolve the operator's inherited server. Required form: TMUX_TMPDIR=\$(mktemp -d) env -u TMUX tmux <verb> ... -- see agent-supervisor#247."
fi

exit 0
