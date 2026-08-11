#!/bin/bash
# director-inbox.sh's own stated goal (director-inbox.sh:24-26) is "losing the
# record of an instruction is worse than re-reading one." Two paths broke that
# goal, both found by independent review of PR #86 and filed as #88:
#
#   1. drain silently and permanently deleted a line it could not json.loads
#      -- exactly the shape of a torn/partial write, the case most worth
#      keeping for hand inspection.
#   2. drain's read-modify-write over the whole file had no lock, so a `post`
#      landing between drain's read and its truncate-and-rewrite was
#      overwritten out of existence with no trace.
#
# The two `want_exit ... 1` assertions below (malformed-line preservation,
# post-racing-drain survival) are the load-bearing regression tests -- they
# fail against the pre-#88 script and pass after the fix.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INBOX="$HERE/../../scripts/supervisor/director-inbox.sh"
pass=0; fail=0

ok()   { echo "  ok   $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL $1"; sed 's/^/       /' <<<"${2:-}"; fail=$((fail+1)); }
want_contains()    { if grep -q -- "$2" <<<"$3"; then ok "$1"; else bad "$1" "$3"; fi }
want_not_contains() { if grep -q -- "$2" <<<"$3"; then bad "$1" "$3"; else ok "$1"; fi }
want_exit() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected exit $3, got $2: ${4:-}"; fi }

echo "director-inbox.sh"

D=$(mktemp -d)
run() { DIRECTOR_INBOX="$D/box.jsonl" bash "$INBOX" "$@"; }

# --- post then read: message appears, read does not mutate the file --------
run post "first message" >/dev/null
before=$(cat "$D/box.jsonl")
out=$(run read)
after=$(cat "$D/box.jsonl")
want_contains "read shows a posted message" "first message" "$out"
[ "$before" = "$after" ] && ok "read does not mutate the file" \
  || bad "read does not mutate the file" "before:$before"$'\n'"after:$after"

# --- post then drain then drain: pin idempotency ----------------------------
out=$(run drain)
want_contains "first drain prints the message" "first message" "$out"
snapshot=$(cat "$D/box.jsonl")
out2=$(run drain)
want_contains "second drain reports nothing new" "no new director messages" "$out2"
[ "$snapshot" = "$(cat "$D/box.jsonl")" ] && ok "second drain leaves the file unchanged" \
  || bad "second drain leaves the file unchanged" "$(cat "$D/box.jsonl")"

# --- missing/empty box: read and drain already handled, pin it -------------
rm -f "$D/box.jsonl"
out=$(run read); rc=$?
want_exit "read against a missing box exits 0" "$rc" 0
want_contains "read against a missing box says so" "no director messages" "$out"
out=$(run drain); rc=$?
want_exit "drain against a missing box exits 0" "$rc" 0

: > "$D/box.jsonl"
out=$(run drain); rc=$?
want_exit "drain against an empty box exits 0" "$rc" 0
want_contains "drain against an empty box says so" "no director messages" "$out"

# --- malformed line: preserved verbatim across drain, with a warning -------
rm -f "$D/box.jsonl"
run post "good message" >/dev/null
printf '{"at": "bad", "read": false, "tex\n' >> "$D/box.jsonl"
out=$(run drain 2>"$D/stderr.txt")
want_contains "drain still surfaces the well-formed message" "good message" "$out"
want_contains "drain warns about the malformed line" "malformed" "$(cat "$D/stderr.txt")"
want_contains "the malformed line survives the drain verbatim" \
  '{"at": "bad", "read": false, "tex' "$(cat "$D/box.jsonl")"

# --- two concurrent posts: both survive -------------------------------------
rm -f "$D/box.jsonl"
run post "concurrent-a" >/dev/null &
p1=$!
run post "concurrent-b" >/dev/null &
p2=$!
wait "$p1" "$p2"
final=$(cat "$D/box.jsonl")
want_contains "concurrent post a survives" "concurrent-a" "$final"
want_contains "concurrent post b survives" "concurrent-b" "$final"
lines=$(grep -c . "$D/box.jsonl")
[ "$lines" = 2 ] && ok "both concurrent posts landed as two lines" \
  || bad "both concurrent posts landed as two lines" "$final"

# --- post racing drain: the post survives -----------------------------------
# Patch a copy of the script to sleep after taking the lock, inside drain's
# read-modify-write, so a concurrent post has a real window to land in.
rm -f "$D/box.jsonl"
run post "msg-1" >/dev/null
SLOW="$D/slow-drain.sh"
python3 - "$INBOX" "$SLOW" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
marker = 'fcntl.flock(lockfile, fcntl.LOCK_EX)\n\n    # Each entry'
replacement = 'fcntl.flock(lockfile, fcntl.LOCK_EX)\n    import time; time.sleep(1)\n\n    # Each entry'
assert marker in text, "drain locking marker not found -- script shape changed"
open(dst, "w").write(text.replace(marker, replacement, 1))
PY
DIRECTOR_INBOX="$D/box.jsonl" bash "$SLOW" drain > "$D/drain_out.txt" 2>&1 &
drain_pid=$!
sleep 0.3
run post "msg-2 racing the drain" > "$D/post_out.txt" 2>&1
wait "$drain_pid"
final=$(cat "$D/box.jsonl")
want_contains "the racing drain still reports msg-1" "msg-1" "$(cat "$D/drain_out.txt")"
want_contains "the post racing drain survives in the file" "msg-2 racing the drain" "$final"

rm -rf "$D"

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
