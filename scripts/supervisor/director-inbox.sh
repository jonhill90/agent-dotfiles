#!/bin/bash
# Out-of-band messages to the supervisor, without typing into its pane.
#
# WHY: a dynamic `/loop` stays alive by scheduling its own wakeup at the end
# of each turn. Any plain message sent to that pane REPLACES the loop prompt,
# so the next turn is an ordinary turn and nothing re-arms. The loop ends
# silently, and the watchdog cannot tell that from a crash — both look like
# "idle pane, agent alive, no pending wakeup".
#
# Measured 2026-08-11 (#85): 27 `/loop` messages since 09:00, zero
# ScheduleWakeup calls. The watchdog restarted three times, each restart did
# real work, each was ended by the Director sending a constraint, and the
# third tripped the escalation cap and paged Jon at 09:34:49Z — for a
# condition the Director itself kept re-creating.
#
# The pane is now single-writer. The Director appends here; the tick reads and
# drains. Nobody types into the supervisor.
#
# Usage:
#   director-inbox.sh post "message"   append a message for the next tick
#   director-inbox.sh read             print undrained messages (no drain)
#   director-inbox.sh drain            print undrained messages and mark them
#
# Drain marks rather than deletes: a message the supervisor read is still
# readable afterwards, because losing the record of an instruction is worse
# than re-reading one.

set -uo pipefail
STATE="${SUPERVISOR_STATE:-$HOME/.local/state/agent-dotfiles-supervisor}"
BOX="${DIRECTOR_INBOX:-$STATE/director-inbox.jsonl}"
mkdir -p "$(dirname "$BOX")" 2>/dev/null

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

case "${1:-read}" in
  post)
    [ -n "${2:-}" ] || { echo "director-inbox: post needs a message" >&2; exit 1; }
    python3 - "$BOX" "$(now)" "$2" <<'PY'
import json, sys
box, stamp, text = sys.argv[1], sys.argv[2], sys.argv[3]
with open(box, "a") as handle:
    handle.write(json.dumps({"at": stamp, "read": False, "text": text}) + "\n")
print(f"director-inbox: queued for the next tick ({stamp})")
PY
    ;;
  read|drain)
    [ -s "$BOX" ] || { echo "(no director messages)"; exit 0; }
    python3 - "$BOX" "${1}" <<'PY'
import json, sys
box, mode = sys.argv[1], sys.argv[2]
rows = []
for line in open(box):
    line = line.strip()
    if not line:
        continue
    try:
        rows.append(json.loads(line))
    except ValueError:
        continue
pending = [r for r in rows if not r.get("read")]
if not pending:
    print("(no new director messages)")
    sys.exit(0)
for r in pending:
    print(f"[director {r['at']}] {r['text']}")
if mode == "drain":
    for r in rows:
        r["read"] = True
    with open(box, "w") as handle:
        for r in rows:
            handle.write(json.dumps(r) + "\n")
PY
    ;;
  *) echo "usage: director-inbox.sh {post <msg>|read|drain}" >&2; exit 1 ;;
esac
