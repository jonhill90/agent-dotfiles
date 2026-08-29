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

hook_command_violates "$RULE" destructive || exit 0

# From here on the command names a destructive verb. It is allowed ONLY if
# BOTH halves of the isolation idiom are present in the same command:
#   1. TMUX_TMPDIR=... (a real value, not empty/unset)
#   2. env -u TMUX (or an equivalent explicit unset of TMUX) ahead of tmux
# Fail closed: if we cannot confirm both, refuse. Guessing "probably fine"
# is exactly the class of error agent-dotfiles#228/#230/#235 recorded.

hook_block "$RULE" \
  "a destructive tmux verb (kill-server/kill-session/kill-window/respawn-*) is not isolated with both TMUX_TMPDIR and 'env -u TMUX' in the same command. This can target the operator's real server."
