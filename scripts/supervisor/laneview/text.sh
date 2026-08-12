#!/bin/bash
# laneview implementation: plain stdout, no daemon, no tmux plugin.
#
# This is the "apart" implementation (agent-dotfiles#178): it has no
# dependency beyond python3 for json parsing, works over a bare SSH session,
# in cron, or with no tmux client attached at all. It is the control that
# proves the meta-harness half is not required for the estate to have a
# lane view.
#
# Usage: text.sh <session> <lanes.sh --json output>   (called by laneview.sh)

set -uo pipefail

SESSION="$1"
JSON="$2"

python3 - "$SESSION" "$JSON" <<'PY'
import json, sys

session, raw = sys.argv[1], sys.argv[2]
rows = json.loads(raw)

glyph = {
    "free": "-", "busy": "*", "hung": "!", "dead": "x",
    "menu-blocked": "?", "text-blocked": "?", "unsent": "~",
    "service": ".", "supervisor": ".", "unknown": "?",
}

print(f"laneview text -- {session}")
for r in rows:
    g = glyph.get(r["state"], "?")
    print(f"  {g} {r['name']:<24} {r['state']}")
PY
