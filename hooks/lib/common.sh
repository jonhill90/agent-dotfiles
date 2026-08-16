#!/bin/bash
# Shared plumbing for PreToolUse guard hooks (agent-dotfiles#276).
#
# Claude Code invokes a PreToolUse hook with one JSON object on stdin
# (session_id, cwd, tool_name, tool_input, ...) and reads its verdict from
# the exit code: 0 allows the call, 2 blocks it and feeds stderr back to the
# model as the reason. Every guard in this directory sources this file,
# reads the command being attempted into $HOOK_COMMAND, and either calls
# hook_block "<reason>" or falls through to allow (exit 0).
#
# Fail-closed rule (agent-dotfiles#276 requirement 2): if the JSON cannot be
# parsed, or tool_input.command is missing, that is NOT "nothing to check" —
# it is "cannot tell", and "cannot tell" must never resolve to "allowed".
# Callers that need this behaviour call hook_require_command after sourcing.

set -u

HOOK_STDIN="$(cat)"
HOOK_TOOL_NAME=""
HOOK_COMMAND=""
HOOK_PARSE_OK=0

# python3 is already a hard dependency of this repo (install.sh step 4/5,
# scripts/sync.py) -- reuse it instead of adding jq as a new one.
if command -v python3 >/dev/null 2>&1; then
  HOOK_PARSED="$(printf '%s' "$HOOK_STDIN" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("PARSE_FAILED")
    sys.exit(0)
name = data.get("tool_name", "")
cmd = ""
ti = data.get("tool_input")
if isinstance(ti, dict):
    cmd = ti.get("command", "") or ""
print("OK")
print(name)
print(cmd)
' 2>/dev/null)"
  HOOK_STATUS_LINE="$(printf '%s\n' "$HOOK_PARSED" | sed -n '1p')"
  if [ "$HOOK_STATUS_LINE" = "OK" ]; then
    HOOK_PARSE_OK=1
    HOOK_TOOL_NAME="$(printf '%s\n' "$HOOK_PARSED" | sed -n '2p')"
    HOOK_COMMAND="$(printf '%s\n' "$HOOK_PARSED" | sed -n '3,$p')"
  fi
fi

# hook_block RULE REASON
# Exit 2 with an explanatory message naming the rule and why (requirement 1).
# A silent block teaches nothing -- the message is the documentation.
hook_block() {
  local rule="$1"
  local reason="$2"
  printf 'BLOCKED by %s\n\n%s\n' "$rule" "$reason" >&2
  exit 2
}

# hook_require_parsed RULE
# Fail closed: a guard that cannot read tool_name/command well enough to
# decide must refuse, not allow (agent-dotfiles#228, #230, #235 are this
# same error). Call this first in every guard.
hook_require_parsed() {
  local rule="$1"
  if [ "$HOOK_PARSE_OK" -ne 1 ]; then
    hook_block "$rule" \
      "could not parse the tool call well enough to decide -- refusing rather than guessing (agent-dotfiles#276 requirement 2: ambiguity must never resolve to allowed)."
  fi
}
