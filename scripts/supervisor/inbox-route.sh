#!/bin/bash
# Deliver one inbound Telegram message to the lane it answers.
#
# agent-dotfiles#142. The common case this exists for: a lane is mid-turn and
# hit an interactive prompt -- a permission approval, a disambiguating
# question -- and stalled. `lanes.sh` already detects exactly that shape as
# `blocked` (#123/#124). Jon replies on his phone; this is what gets that
# reply into the pane that is actually waiting on it, instead of it sitting
# in the offset file until the next Director tick reads `inbox.sh`.
#
# This deliberately does NOT keep a separate routing table mapping messages
# to lanes. `blocked` is the routing table -- it is recomputed fresh from
# tmux on every call, so it can never point at a lane that has since finished,
# been redispatched, or renamed. A stale table would misroute; asking tmux
# again cannot.
#
# Three cases, and only the first is unambiguous:
#
#   exactly one lane blocked  -> that lane is presumed to be who asked.
#                                 Send the reply there.
#   zero lanes blocked        -> nobody is waiting. Sending nowhere would be
#                                 silent; guessing a target would be worse.
#                                 Tell Jon so, through notify.sh, so he knows
#                                 the message arrived and was not silently
#                                 dropped -- just that nothing was listening.
#   more than one blocked     -> routing would be a guess, and a reply
#                                 delivered to the wrong lane is worse than
#                                 one that pauses to ask. List the candidates
#                                 and ask Jon which one, through notify.sh.
#
# Usage: inbox-route.sh "<message text>" [session]
#
# Exit 0 once the message has been either delivered to a lane or reported to
# Jon via notify.sh. Exit 1 if neither happened -- the message text is
# printed to stderr in that case so it is not lost from the caller's log.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="${2:-${LANES_SESSION:-agent-dotfiles}}"
MESSAGE="${1:-}"

if [ -z "$MESSAGE" ]; then
  echo "inbox-route: usage: inbox-route.sh \"<message text>\" [session]" >&2
  exit 2
fi

notify_jon() {  # notify_jon <subject> <body>
  if ! AGENT_NOTIFY_CALLER=supervisor "$HERE/notify.sh" "$1" "$2"; then
    echo "inbox-route: could not reach Jon either -- message was: $MESSAGE" >&2
    return 1
  fi
}

BLOCKED=()
while read -r candidate; do
  [ -n "$candidate" ] || continue
  BLOCKED+=("$candidate")
done < <("$HERE/lanes.sh" --blocked "$SESSION" 2>/dev/null)

case "${#BLOCKED[@]}" in
  1)
    LANE="${BLOCKED[0]}"
    # No `-l`: dispatch.sh's own brief send (loop-tick.md's documented path)
    # relies on the same behaviour -- a single quoted argument that is not
    # itself a recognised key name is typed literally. Matching it keeps one
    # convention for "type text into a lane's pane" instead of two.
    if tmux send-keys -t "$LANE" "$MESSAGE" 2>/dev/null \
       && tmux send-keys -t "$LANE" Enter 2>/dev/null; then
      echo "inbox-route: delivered to $LANE"
      exit 0
    fi
    echo "inbox-route: send-keys to $LANE failed" >&2
    notify_jon "Telegram reply could not be delivered" \
      "$LANE was blocked and waiting but the send failed -- reply was: $MESSAGE"
    exit 1
    ;;
  0)
    notify_jon "Telegram message received, no lane is waiting" \
      "No blocked lane to route to -- got: $MESSAGE"
    exit $?
    ;;
  *)
    LIST="$(IFS=', '; echo "${BLOCKED[*]}")"
    notify_jon "Telegram reply -- which lane?" \
      "${#BLOCKED[@]} lanes are blocked ($LIST) -- got: $MESSAGE -- reply naming the lane"
    exit $?
    ;;
esac
