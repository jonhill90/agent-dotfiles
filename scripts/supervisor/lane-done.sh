#!/bin/bash
# Rename a lane back to free-N when its worker signals completion -- the
# second half of the dispatch/rename convention that agent-dotfiles#102
# found missing.
#
# WHY: dispatch.sh performs the first half automatically -- claim, worktree,
# rename to the task name, send. Nothing performed the second half, so every
# completed task permanently removed one lane from the pool until a human
# noticed `dispatch.sh` refusing "no free lane" and renamed by hand. That
# happened twice in one evening, 2026-08-11 (#102).
#
# WHY tied to the wait-for signal and nothing else: `lanes.sh` cannot tell
# "finished" from "idle between tool calls" or "blocked on an approval
# prompt holding an unposted verdict" -- all three read identically to
# `capture-pane`. Reclaiming on idle-alone was tried against a live lane the
# same night and nearly destroyed a verdict (#102). The worker's
# `tmux wait-for -S <channel>` is the one signal that cannot fire early: it
# is the brief's literal last instruction, sent only after everything else
# -- including posting a verdict -- is done (SPEC §14.1). Blocking on
# `wait-for -L` and renaming only when it returns needs no pane inspection
# at all, so it cannot mistake an approval prompt for completion.
#
# Usage: lane-done.sh <window-index> <expected-name> <channel> [session]
#
# <window-index>  the lane's tmux window index, e.g. what dispatch.sh sent
#                 the brief to.
# <expected-name> the task name dispatch.sh set on that window, e.g.
#                 `ad102-lane-rename-on-completion`. Renaming is refused if
#                 the window carries any other name when the signal arrives
#                 -- someone already handled it, or the lane was redispatched
#                 while this waiter was still up, and renaming now would
#                 steal the name out from under new work.
# <channel>       the wait-for channel named in the worker's brief.
#
# Run this BACKGROUNDED (Bash tool `run_in_background`, or `&` from a
# script) immediately after a successful dispatch, so the supervisor's tick
# stays free while it waits -- SPEC §14.3's fast path.
#
# Exit 0 only after a successful rename.
# Exit 1 if the channel was never signaled, or if the window no longer
#   carries <expected-name> when it was.
# `tmux wait-for -L` itself has no timeout (SPEC §14.2 L3): a worker that
# crashes or wedges before reaching its final action leaves this blocked
# forever, same as the underlying mechanism today. That is an accepted,
# already-documented limit of `wait-for`, not a new one introduced here.

set -uo pipefail

IDX="${1:-}"
EXPECTED_NAME="${2:-}"
CHANNEL="${3:-}"
SESSION="${4:-${LANES_SESSION:-agent-dotfiles}}"

if [ -z "$IDX" ] || [ -z "$EXPECTED_NAME" ] || [ -z "$CHANNEL" ]; then
  sed -n '/^# Usage:/,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
  exit 2
fi

if ! tmux wait-for -L "$CHANNEL" 2>/dev/null; then
  echo "lane-done: channel '$CHANNEL' was not signaled -- not renaming ${SESSION}:${IDX}" >&2
  exit 1
fi

CURRENT="$(tmux display-message -p -t "${SESSION}:${IDX}" '#{window_name}' 2>/dev/null)"
if [ "$CURRENT" != "$EXPECTED_NAME" ]; then
  echo "lane-done: ${SESSION}:${IDX} is now '$CURRENT', not '$EXPECTED_NAME' -- already handled, not renaming" >&2
  exit 1
fi

tmux rename-window -t "${SESSION}:${IDX}" "free-${IDX}"
