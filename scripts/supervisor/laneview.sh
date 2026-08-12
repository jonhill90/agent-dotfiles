#!/bin/bash
# Drive one laneview/ implementation from lanes.sh's own json.
#
# WHY (agent-dotfiles#178): Jon wants a tmux plugin that can act as a
# meta-harness "working together and apart" with the headless supervisor.
# Neither half may become required by the other, so the human-facing render
# is defined once, as a contract, and every renderer -- a plain stdout feed
# or a tmux-plugin sidebar -- is a swappable implementation of it, never a
# second reader of tmux or the ledger. See laneview/README.md for the
# contract text and #173 for the measured cost of the tmux-sidebar path.
#
# Usage: laneview.sh <impl> [session]
#   impl:    the basename of a script under laneview/, e.g. text, opensessions
#   session: tmux session to report on (default: agent-dotfiles)
#
# Adding a renderer is a new file under laneview/. Removing one is
# `rm laneview/<impl>.sh` -- nothing here or in lanes.sh names it.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMPL="${1:?usage: laneview.sh <impl> [session]}"
SESSION="${2:-agent-dotfiles}"
IMPL_SCRIPT="$HERE/laneview/$IMPL.sh"

if [ ! -x "$IMPL_SCRIPT" ]; then
  echo "laneview.sh: no renderer at $IMPL_SCRIPT (implementations: $(ls "$HERE/laneview" 2>/dev/null | sed 's/\.sh$//' | tr '\n' ' '))" >&2
  exit 1
fi

# lanes.sh is the one reader of tmux measurements and the ledger (#178
# brief, "tmux is not a database"); every implementation gets state only
# through this json, never by polling tmux or the ledger itself.
json=$(bash "$HERE/lanes.sh" --json "$SESSION")

exec "$IMPL_SCRIPT" "$SESSION" "$json"
