#!/bin/bash
# advance-live.sh must advance the LIVE worktree only when the candidate
# demonstrably runs and the watchdog is not about to tick mid-checkout, and
# it must never leave the live worktree in a half-state on any refusal.
#
# WHY: #99's advancement half. Nothing advanced ~/.local/state/agent-dotfiles-
# supervisor/live; it was hand-advanced five times in one day, each time
# prompted only by a human noticing the `code:` line #100 added. The design
# constraints recorded on the issue (candidate must run before the pin
# moves, rollback target captured before mutation, advance only in the
# window right after a watchdog tick, never a silent half-state) are exactly
# what this suite pins down.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADVANCE="$HERE/../../scripts/supervisor/advance-live.sh"
pass=0; fail=0

ok()   { echo "  ok   $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL $1"; sed 's/^/       /' <<<"${2:-}"; fail=$((fail+1)); }
want_exit() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected exit $3, got $2: ${4:-}"; fi }

echo "advance-live.sh"

D=$(mktemp -d)

# --- a minimal bare origin + clone, standing in for the shared repo -------
git init -q --bare "$D/origin.git"
git clone -q "$D/origin.git" "$D/src"
SRC="$D/src"
git -C "$SRC" config user.email test@example.com
git -C "$SRC" config user.name "Test"
git -C "$SRC" checkout -q -b main
mkdir -p "$SRC/scripts/supervisor"
# A stand-in watchdog.sh that writes a well-formed status file, matching the
# real one's contract, without needing tmux/gh -- advance-live.sh's smoke
# gate only cares that the candidate runs and writes checked:/state: lines.
cat >"$SRC/scripts/supervisor/watchdog.sh" <<'EOF'
#!/bin/bash
set -uo pipefail
STATUS="${SUPERVISOR_STATUS:?}"
mkdir -p "$(dirname "$STATUS")"
{
  printf 'checked:  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'state:    pane_unreadable\n'
} >"$STATUS"
exit 0
EOF
chmod +x "$SRC/scripts/supervisor/watchdog.sh"
git -C "$SRC" add -A
git -C "$SRC" commit -q -m "good watchdog.sh"
git -C "$SRC" push -q -u origin main

# A worktree standing in for the live copy, pinned at this first commit.
LIVE="$D/live"
git -C "$SRC" worktree add -q --detach "$LIVE" origin/main

fresh_status() { # fresh_status <state-dir>
  mkdir -p "$1"
  printf 'checked:  %s\nstate:    working\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$1/watchdog.status"
}
stale_status() { # stale_status <state-dir> <seconds-ago>
  mkdir -p "$1"
  local ts
  ts=$(date -u -v-"$2"S +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "$2 seconds ago" +%Y-%m-%dT%H:%M:%SZ)
  printf 'checked:  %s\nstate:    working\n' "$ts" >"$1/watchdog.status"
}
run() { # run <state-dir>
  SUPERVISOR_STATE="$1" bash "$ADVANCE" "$LIVE"
}

# --- already current: nothing to do, no watchdog.status even needed -------
S=$(mktemp -d)
out=$(run "$S" 2>&1); rc=$?
want_exit "already-current exits 0" "$rc" 0 "$out"
if grep -qi "advanc" <<<"$out"; then bad "already-current does not claim to advance" "$out"; else ok "already-current does not claim to advance"; fi

# --- put a second commit on origin/main so LIVE is genuinely behind -------
echo two >"$SRC/file.txt"
git -C "$SRC" add file.txt
git -C "$SRC" commit -q -m "second commit"
git -C "$SRC" push -q origin main
git -C "$LIVE" fetch -q origin main
target_sha=$(git -C "$LIVE" rev-parse origin/main)
before_sha=$(git -C "$LIVE" rev-parse HEAD)

# --- no watchdog.status yet: skip, live untouched --------------------------
S=$(mktemp -d)
out=$(run "$S" 2>&1); rc=$?
want_exit "no status file skips (exit 0)" "$rc" 0 "$out"
after=$(git -C "$LIVE" rev-parse HEAD)
if [ "$after" = "$before_sha" ]; then ok "no status file leaves live untouched"; else bad "no status file leaves live untouched" "moved to $after"; fi

# --- watchdog tick was too long ago: skip, live untouched ------------------
S=$(mktemp -d); stale_status "$S" 179
out=$(run "$S" 2>&1); rc=$?
want_exit "stale tick skips (exit 0)" "$rc" 0 "$out"
if grep -q "outside the" <<<"$out"; then ok "stale tick names the safe window"; else bad "stale tick names the safe window" "$out"; fi
after=$(git -C "$LIVE" rev-parse HEAD)
if [ "$after" = "$before_sha" ]; then ok "stale tick leaves live untouched"; else bad "stale tick leaves live untouched" "moved to $after"; fi

# --- fresh tick, but the candidate at origin/main is broken: gate refuses -
BROKEN=$(mktemp -d)
git -C "$SRC" worktree add -q --detach "$BROKEN" origin/main
printf '#!/bin/bash\nexit 1\n' >"$BROKEN/scripts/supervisor/watchdog.sh"
git -C "$BROKEN" -c user.email=t@t -c user.name=t commit -aq -m "break watchdog.sh"
broken_sha=$(git -C "$BROKEN" rev-parse HEAD)
# Point LIVE's view of origin/main at the broken commit without touching the
# real branch on origin -- update-ref on the shared object store, same trick
# advance-live.sh itself only ever reads via `rev-parse origin/main`.
git -C "$LIVE" update-ref refs/remotes/origin/main "$broken_sha"

S=$(mktemp -d); fresh_status "$S"
out=$(run "$S" 2>&1); rc=$?
want_exit "broken candidate refuses to advance (nonzero exit)" "$rc" 1 "$out"
after=$(git -C "$LIVE" rev-parse HEAD)
if [ "$after" = "$before_sha" ]; then ok "broken candidate leaves live untouched"; else bad "broken candidate leaves live untouched" "moved to $after"; fi
if [ -f "$S/.live-rollback-sha" ]; then bad "broken candidate did not write a rollback file" "$(cat "$S/.live-rollback-sha")"; else ok "broken candidate did not write a rollback file"; fi

# restore origin/main to the good target for the success case
git -C "$LIVE" update-ref refs/remotes/origin/main "$target_sha"
git -C "$SRC" worktree remove --force "$BROKEN" >/dev/null 2>&1
git -C "$SRC" worktree prune >/dev/null 2>&1

# --- fresh tick, good candidate: advances, records rollback ---------------
S=$(mktemp -d); fresh_status "$S"
out=$(run "$S" 2>&1); rc=$?
want_exit "good candidate advances (exit 0)" "$rc" 0 "$out"
after=$(git -C "$LIVE" rev-parse HEAD)
if [ "$after" = "$target_sha" ]; then ok "good candidate advances live to origin/main"; else bad "good candidate advances live to origin/main" "at $after, wanted $target_sha"; fi
if [ -f "$S/.live-rollback-sha" ] && [ "$(cat "$S/.live-rollback-sha")" = "$before_sha" ]; then
  ok "rollback file records the pre-advance sha"
else
  bad "rollback file records the pre-advance sha" "$(cat "$S/.live-rollback-sha" 2>/dev/null)"
fi
if grep -q "ADVANCED" "$S/advance-live.log" 2>/dev/null; then ok "advance is logged"; else bad "advance is logged" "$(cat "$S/advance-live.log" 2>/dev/null)"; fi

# --- origin/main unreadable: refuses loudly, live untouched ----------------
S=$(mktemp -d); fresh_status "$S"
git -C "$LIVE" update-ref -d refs/remotes/origin/main
before2=$(git -C "$LIVE" rev-parse HEAD)
out=$(run "$S" 2>&1); rc=$?
want_exit "unreadable origin/main refuses (nonzero exit)" "$rc" 1 "$out"
after2=$(git -C "$LIVE" rev-parse HEAD)
if [ "$after2" = "$before2" ]; then ok "unreadable origin/main leaves live untouched"; else bad "unreadable origin/main leaves live untouched" "moved to $after2"; fi

# advance-live.sh must clean up its own scratch smoke-test worktrees
leftover=$(git -C "$SRC" worktree list --porcelain | grep -c '^worktree.*ad99-advance-smoke' || true)
if [ "$leftover" -eq 0 ]; then ok "no leftover smoke-test worktrees"; else bad "no leftover smoke-test worktrees" "$leftover still registered"; fi

rm -rf "$D"

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
