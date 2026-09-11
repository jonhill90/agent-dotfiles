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
    # shellcheck disable=SC2034 # consumed by guard scripts after sourcing
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

# hook_command_violates RULE PARSER_RULE
# A parser error blocks: a security hook must never treat grammar it cannot
# identify as harmless prose.  The helper returns 10 only for a real match,
# 3 when a program is named by an expansion the text cannot resolve
# (agent-dotfiles#360), and 2 for any other grammar it cannot identify; on
# 2 and 3 it prints the reason, quoted back here so the refusal names the
# token. Either refusal is for the WHOLE payload, on EVERY guard that reads
# it: one clause the parser cannot place refuses the line for the guards
# whose subject is elsewhere in it too (agent-dotfiles#362 review). That
# is the fail-closed rule, not a side effect -- a clause that cannot be
# placed cannot be shown harmless to any rule.
hook_command_violates() {
  local rule="$1"
  local parser_rule="$2"
  local helper="${SCRIPT_DIR}/lib/command_guard.py"
  local reason
  reason="$(python3 "$helper" "$parser_rule" <<<"$HOOK_COMMAND" 2>/dev/null)"
  local status=$?
  case "$status" in
    0) return 1 ;;
    10) return 0 ;;
    3) hook_block "$rule" "a program in this Bash payload is named by an expansion -- ${reason:-see command_guard.py} -- so the text cannot say what would run. This refuses the whole line on every guard, not only the clause with the expansion (agent-dotfiles#360, #362). Name the program literally, or run that clause as its own Bash call." ;;
    *) hook_block "$rule" "could not identify executable commands in this Bash payload well enough to apply the guard -- ${reason:-grammar this guard does not model} -- refusing rather than guessing. This refuses the whole line on every guard." ;;
  esac
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
