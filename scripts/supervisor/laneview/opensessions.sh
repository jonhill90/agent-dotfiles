#!/bin/bash
# laneview implementation: push lane state into an OpenSessions tmux
# sidebar (github.com/Ataraxy-Labs/opensessions), via its documented
# HTTP API.
#
# This is the "together" implementation (agent-dotfiles#178) -- the
# tmux-plugin path. It is a productionized version of the bridge script
# #173 wrote and measured live on remote.hill90.com
# (`~/exp173/lanebridge.sh`); the mapping and mechanism are unchanged, only
# cleaned up to fit the laneview.sh contract (README.md in this
# directory): read-only, exits nonzero rather than showing stale state if
# the daemon is unreachable, and never invoked from a headless supervisor
# path.
#
# Requires: OpenSessions installed and its server already running (TPM
# manages this; this script does not start or stop the daemon -- starting
# a daemon is a decision this viewer does not get to make).
#
# Usage: opensessions.sh <session> <lanes.sh --json output>
#   OS_PORT   OpenSessions server port (default 39104, its documented
#             default derivation for a single-socket tmux server)

set -uo pipefail

SESSION="$1"
JSON="$2"
URL="http://127.0.0.1:${OS_PORT:-39104}"

post() {
  local path="$1" body="$2" code
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 \
    -X POST "$URL$path" -H 'content-type: application/json' -d "$body") || {
    echo "laneview/opensessions.sh: cannot reach $URL -- is the OpenSessions daemon running? not rendering stale state." >&2
    exit 1
  }
  if [ "$code" != "204" ] && [ "$code" != "200" ]; then
    echo "laneview/opensessions.sh: $path -> HTTP $code" >&2
    exit 1
  fi
}

# lanes.sh's states -> OpenSessions' fixed AgentStatus vocabulary. This
# mapping is lossy (#173): menu-blocked and text-blocked both collapse to
# waiting, and unknown/service both read as idle. That loss is
# OpenSessions', not this script's -- see laneview/README.md.
map_status() {
  case "$1" in
    free) echo idle ;;
    busy) echo running ;;
    hung) echo stale ;;
    menu-blocked|text-blocked|unsent) echo waiting ;;
    dead) echo error ;;
    *) echo idle ;;
  esac
}

events=$(python3 - "$SESSION" "$JSON" <<'PY'
import json, sys
session, raw = sys.argv[1], sys.argv[2]
rows = json.loads(raw)
out = []
for r in rows:
    if r["state"] == "supervisor":
        continue
    out.append({
        "agent": "lanes", "tmuxSession": session,
        "status": None,  # filled in by the shell mapping below
        "threadId": r["name"],
        "threadName": f"{r['name']} — {r['state']}",
        "lastUserPrompt": f"lanes.sh says {r['state']}",
        "_state": r["state"],
    })
print(json.dumps(out))
PY
)

summary=$(python3 - "$JSON" <<'PY'
import json, sys, collections
rows = json.loads(sys.argv[1])
c = collections.Counter(r["state"] for r in rows if r["state"] != "supervisor")
print(" · ".join(f"{n} {s}" for s, n in sorted(c.items())))
PY
)

python3 -c '
import json, sys
for e in json.loads(sys.argv[1]):
    print(json.dumps(e))
' "$events" | while IFS= read -r ev; do
  state=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["_state"])' "$ev")
  status=$(map_status "$state")
  ev_out=$(python3 -c '
import json, sys
e = json.loads(sys.argv[1]); e.pop("_state"); e["status"] = sys.argv[2]
print(json.dumps(e))
' "$ev" "$status")
  post /api/agent-event "$ev_out"
done

post /set-status "$(python3 -c '
import json, sys
print(json.dumps({"session": sys.argv[1], "text": sys.argv[2]}))
' "$SESSION" "$summary")"

echo "laneview opensessions -- pushed $(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1])))' "$events") lane(s) for $SESSION to $URL"
