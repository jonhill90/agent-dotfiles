#!/bin/bash
# Report the real state of every worker lane in a tmux session.
#
# WHY: "idle" was doing four different jobs, and the supervisor could not tell
# them apart. All four were hit in one night, 2026-08-11:
#
#   free     an agent is running and waiting for work        -> dispatch to it
#   busy     an agent is mid-turn                            -> leave alone
#   hung     the pane looks busy but has stopped advancing   -> needs a human
#   dead     no agent at all, just a shell                   -> restart the agent
#   unknown  a non-Claude harness; no probe exists for it     -> ask a human
#
# `capture-pane` alone reports the last three identically. A dispatch sent to a
# dead lane lands in zsh, which answers "no such file or directory: /clear" and
# the work is silently lost. A dispatch sent to a hung lane is queued forever.
#
# Two signals, neither sufficient alone:
#   - `pane_current_command` separates dead from everything else.
#   - Sampling the pane twice separates hung from busy: a live turn's elapsed
#     timer advances between samples, a wedged one does not.
#
# Usage: lanes.sh [session]        human-readable table
#        lanes.sh --free [session] print only lane names safe to dispatch to
#        lanes.sh --json [session]
#
# Exit 0 always when the session exists; the states are the output, not the
# exit code. Exit 1 if the session does not exist -- which is NOT "no lanes".

set -uo pipefail

SESSION="${2:-${LANES_SESSION:-agent-dotfiles}}"
MODE="${1:-}"
case "$MODE" in
  --free|--json) ;;
  "") ;;
  *) SESSION="$MODE"; MODE="" ;;
esac

# Shells mean "the agent exited and left the pane behind".
SHELLS="bash|zsh|sh|fish|login"
# A lane is hung if it looks busy but tmux has seen no output from it for this
# long. Must exceed the slowest legitimate repaint interval -- Claude Code's
# footer drops to MINUTE granularity past 60s, so a live turn can go ~60s
# without changing a single byte.
HUNG_AFTER="${LANES_HUNG_AFTER:-180}"

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "lanes: session '$SESSION' does not exist" >&2
  exit 1
fi

windows=$(tmux list-windows -t "$SESSION" -F '#{window_index}' 2>/dev/null)

# First sample of every pane, taken together so the gap is shared rather than
# paid per lane.
declare -a IDX NAME CMD ACTIVITY
while read -r w; do
  [ -n "$w" ] || continue
  IDX+=("$w")
  NAME+=("$(tmux display-message -p -t "$SESSION:$w" '#{window_name}' 2>/dev/null)")
  CMD+=("$(tmux display-message -p -t "$SESSION:$w.1" '#{pane_current_command}' 2>/dev/null)")
  ACTIVITY+=("$(tmux display-message -p -t "$SESSION:$w" '#{window_activity}' 2>/dev/null)")
done <<<"$windows"

now_epoch=$(date +%s)

emit_rows() {
  local i
  for i in "${!IDX[@]}"; do
    local w="${IDX[$i]}" name="${NAME[$i]}" cmd="${CMD[$i]}" act="${ACTIVITY[$i]}"
    local pane state age
    pane=$(tmux capture-pane -p -t "$SESSION:$w" -S -6 2>/dev/null | tr -d '\n')

    if [[ "$cmd" =~ ^($SHELLS)$ ]]; then
      state=dead
    elif [[ ! "$cmd" =~ ^(claude|claude\.exe)$ ]]; then
      # The busy probe greps Claude Code's own status string. Other harnesses
      # paint different UIs, and guessing produces false alarms: a healthy idle
      # Copilot pane was classified `hung` because that string appeared in its
      # scrollback. Report what is known and refuse to invent the rest.
      state=unknown
    elif ! grep -q 'esc to interrupt' <<<"$pane"; then
      state=free
    else
      # Busy-looking. Hung iff tmux has seen no output for HUNG_AFTER.
      #
      # This deliberately does NOT diff pane text across a short gap. That was
      # the first version and it was wrong: Claude Code's elapsed footer shows
      # minute granularity past 60s, so a turn running 61-119s prints an
      # identical byte string for a whole minute and was reported hung while
      # fully alive. Found in review of #65. tmux's own activity timestamp is
      # independent of whatever the harness chooses to paint.
      age=$(( now_epoch - ${act:-now_epoch} ))
      if [ "$age" -ge "$HUNG_AFTER" ]; then state=hung; else state=busy; fi
    fi
    printf '%s\t%s\t%s\t%s\n' "$w" "$name" "$cmd" "$state"
  done
}

rows=$(emit_rows)

case "$MODE" in
  --free)
    awk -F'\t' '$4=="free"{print $2}' <<<"$rows" ;;
  --json)
    printf '['
    awk -F'\t' 'BEGIN{c=0}
      {if(c++)printf(",");printf("{\"window\":%s,\"name\":\"%s\",\"command\":\"%s\",\"state\":\"%s\"}",$1,$2,$3,$4)}
      END{}' <<<"$rows"
    printf ']\n' ;;
  *)
    printf '%-4s %-24s %-12s %s\n' WINDOW NAME COMMAND STATE
    awk -F'\t' '{printf("%-4s %-24s %-12s %s\n",$1,$2,$3,$4)}' <<<"$rows"
    dead=$(awk -F'\t' '$4=="dead"' <<<"$rows" | wc -l | tr -d ' ')
    hung=$(awk -F'\t' '$4=="hung"' <<<"$rows" | wc -l | tr -d ' ')
    [ "$dead" -gt 0 ] && echo "  ${dead} lane(s) have no agent — restart before dispatching"
    [ "$hung" -gt 0 ] && echo "  ${hung} lane(s) look wedged — a dispatch there would queue forever"
    : ;;
esac
