#!/bin/bash
# lane-done.sh must rename a lane back to free-N ONLY when its worker has
# actually signaled completion -- never on idle pane state alone.
#
# WHY: agent-dotfiles#102. dispatch.sh renames a lane to its task name on
# dispatch; nothing renamed it back on completion, so every finished lane
# permanently left the pool until a human noticed and renamed by hand
# (twice, one evening: ad94/ad93/ad97/ad96, then ad101/ad44). The obvious
# fix -- "rename any idle lane" -- is wrong: `lanes.sh` calls a lane idle
# whether it finished, is between tool calls, or is blocked on an approval
# prompt holding an unposted verdict, and reclaiming on idle alone nearly
# destroyed a live verdict the same night. lane-done.sh instead blocks on
# the worker's own `tmux wait-for -S <channel>` -- the brief's literal last
# action -- and renames only when that returns.
#
# The load-bearing case is the first one below: a channel that has not been
# signaled must produce NO rename-window call, full stop. Everything else is
# secondary.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANE_DONE="$HERE/../../scripts/supervisor/lane-done.sh"
pass=0; fail=0

ok()   { echo "  ok   $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL $1"; sed 's/^/       /' <<<"${2:-}"; fail=$((fail+1)); }
want_exit()     { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected exit $3, got $2: ${4:-}"; fi }
want_contains() { if grep -qF -- "$2" <<<"$3"; then ok "$1"; else bad "$1" "want '$2' in: $3"; fi }
want_missing()  { if grep -qF -- "$2" <<<"$3"; then bad "$1" "unwanted '$2' in: $3"; else ok "$1"; fi }

echo "lane-done.sh"

D=$(mktemp -d)
cp "$HERE/stubs/tmux-lane-done" "$D/tmux"
chmod +x "$D/tmux"

cat > "$D/lanes" <<'FIX'
5|ad102-lane-rename-on-completion
6|ad103-something-else
FIX

mkdir -p "$D/wait"
run() {
  : > "$D/tmux.log"
  PATH="$D:$PATH" LANES_FIXTURE="$D/lanes" TMUX_LOG="$D/tmux.log" \
    WAIT_DIR="$D/wait" bash "$LANE_DONE" "$@" 2>&1
}
signal() { mkdir -p "$D/wait"; : > "$D/wait/$1.signaled"; }
tmuxlog() { cat "$D/tmux.log"; }

# --- THE safety property: not signaled -> no rename, ever ------------------
rm -rf "$D/wait"; mkdir -p "$D/wait"
out=$(run 5 ad102-lane-rename-on-completion ad102-done t); rc=$?
want_exit "an unsignaled channel exits non-zero" "$rc" 1 "$out"
want_missing "an unsignaled channel is never renamed" "rename-window" "$(tmuxlog)"

# --- signaled, name still matches -> renamed to free-N ----------------------
signal ad102-done
out=$(run 5 ad102-lane-rename-on-completion ad102-done t); rc=$?
want_exit "a signaled channel exits zero" "$rc" 0 "$out"
want_contains "a finished lane is renamed back to free-N" \
  "rename-window -t t:5 free-5" "$(tmuxlog)"

# --- signaled, but the window no longer carries the expected name ----------
# Someone already handled it (or the lane was redispatched into that slot
# while this waiter was still up) -- renaming now would steal the new name.
signal ad102-done
out=$(run 6 ad102-lane-rename-on-completion ad102-done t); rc=$?
want_exit "a name mismatch exits non-zero" "$rc" 1 "$out"
want_missing "a name mismatch is never renamed" "rename-window" "$(tmuxlog)"

# --- prove the safety assertion is load-bearing -----------------------------
# Patch a copy of lane-done.sh to drop the wait-for guard entirely -- the
# exact regression #102's "rename any idle lane" temptation would produce --
# and confirm the FIRST assertion above (no rename on an unsignaled channel)
# now fails against it. If this sub-test cannot turn the assertion red, the
# assertion was not testing the guard.
BROKEN="$D/lane-done-broken.sh"
patch_rc=0
python3 - "$LANE_DONE" "$BROKEN" <<'PY' || patch_rc=$?
import sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
marker = 'if ! tmux wait-for -L "$CHANNEL" 2>/dev/null; then\n  echo "lane-done: channel \'$CHANNEL\' was not signaled -- not renaming ${SESSION}:${IDX}" >&2\n  exit 1\nfi\n\n'
assert marker in text, "wait-for guard block not found -- script shape changed"
assert text.count(marker) == 1, "wait-for guard block not unique -- script shape changed"
open(dst, "w").write(text.replace(marker, "", 1))
PY
if [ "$patch_rc" -ne 0 ]; then
  bad "setup: patched a guard-free copy of lane-done.sh" \
    "could not patch $LANE_DONE (exit $patch_rc) -- treating as a failure, not a skip"
else
  ok "setup: patched a guard-free copy of lane-done.sh"
  chmod +x "$BROKEN"
  : > "$D/tmux.log"; rm -rf "$D/wait"; mkdir -p "$D/wait"
  out=$(PATH="$D:$PATH" LANES_FIXTURE="$D/lanes" TMUX_LOG="$D/tmux.log" \
        WAIT_DIR="$D/wait" bash "$BROKEN" 5 ad102-lane-rename-on-completion ad102-done t 2>&1)
  log="$(tmuxlog)"
  if grep -qF "rename-window" <<<"$log"; then
    ok "mutation confirmed: removing the guard renames an unfinished lane (the assertion above would now be red)"
  else
    bad "mutation confirmed: removing the guard renames an unfinished lane" \
      "expected the broken copy to rename with no signal present, it did not -- the guard-removal patch missed the real guard: $log"
  fi
fi

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
