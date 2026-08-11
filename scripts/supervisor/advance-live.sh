#!/bin/bash
# Advance the LIVE worktree the watchdog LaunchAgent runs from, to
# origin/main -- the half of #99 that nothing did. #100 built the report
# (`code: ... behind origin/main`); this is the deploy step that acts on it.
#
# WHO CALLS THIS: loop-tick.md's first step, once per supervisor tick --
# invoked, not merely documented (the `acp_transport.py`/`worktree.sh`/
# `lane-done.sh` shape: a tool nothing calls is a documentation rule with a
# binary attached). Rejected designs, from #99's own comments:
#   - the watchdog advancing itself: a broken watchdog would then reinstall
#     itself every 180s and nothing would be left to notice.
#   - a merge webhook / CI step: puts the deploy decision in the same system
#     that produced the change, which is what makes "merged does not mean
#     running" a safety property here.
#   - a plain timer: same failure shape as the first, with extra steps.
# A supervisor tick is gated on real activity (dispatch, review, merge), not
# a clock, so this is neither.
#
# THE GATE: CI green is a property of the merge commit, not proof this
# machine's copy runs. Before switching LIVE's pin, check out the candidate
# commit into a throwaway worktree and run ITS OWN watchdog.sh once, pointed
# at scratch state, and confirm it writes a well-formed status file. That
# exercises the real entry point without ever touching the live loop: the
# smoke run's SUPERVISOR_PANE targets a pane that cannot exist, so the
# candidate takes the pane_unreadable/no_session branch and returns before
# any tmux send-keys is possible.
#
# THE RACE: the LaunchAgent runs watchdog.sh from LIVE on a fixed cadence.
# Swapping LIVE's working tree mid-tick can hand that tick a half-rewritten
# file. There is no lock -- watchdog.sh is not touched here, and adding one
# would change code #100 already shipped. Instead this reads watchdog.status's
# own `checked:` timestamp (the same file the watchdog writes every tick) and
# only advances in the window right after a tick, never blind and never in
# the stretch just before the next one is due.
#
# ROLLBACK: the pre-advance sha is written to disk before anything is
# mutated, because it is only knowable then -- after `checkout --detach` you
# are guessing from reflog.
#
# FAILURE IS LOUD: a failed smoke test, an unreadable origin/main, or a
# checkout that lands somewhere other than the target all exit non-zero with
# the live worktree left exactly where it was. No silent revert, no
# half-state.
#
# Usage:
#   advance-live.sh [live-worktree-path]
#
# Env overrides (mirroring watchdog.sh's, for testing and for a second
# machine layout):
#   SUPERVISOR_STATE     state dir; default ~/.local/state/agent-dotfiles-supervisor
#   SUPERVISOR_LIVE       live worktree path; default $SUPERVISOR_STATE/live
#   SUPERVISOR_STATUS     the LIVE watchdog's own status file (read, not written)
#   ADVANCE_LOG           default $SUPERVISOR_STATE/advance-live.log
#   ADVANCE_ROLLBACK      default $SUPERVISOR_STATE/.live-rollback-sha
#   ADVANCE_TICK_INTERVAL watchdog cadence in seconds; default 180
#   ADVANCE_SAFETY_BUFFER seconds before the next tick to stay clear of; default 30
set -uo pipefail

STATE="${SUPERVISOR_STATE:-$HOME/.local/state/agent-dotfiles-supervisor}"
LIVE="${1:-${SUPERVISOR_LIVE:-$STATE/live}}"
WATCHDOG_STATUS="${SUPERVISOR_STATUS:-$STATE/watchdog.status}"
LOG="${ADVANCE_LOG:-$STATE/advance-live.log}"
ROLLBACK="${ADVANCE_ROLLBACK:-$STATE/.live-rollback-sha}"
TICK_INTERVAL="${ADVANCE_TICK_INTERVAL:-180}"
SAFETY_BUFFER="${ADVANCE_SAFETY_BUFFER:-30}"

log() { mkdir -p "$(dirname "$LOG")" 2>/dev/null; printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >>"$LOG"; }
fail() { log "FAIL: $*"; echo "advance-live: $*" >&2; exit 1; }
skip() { log "SKIP: $*"; echo "advance-live: $*"; exit 0; }

git -C "$LIVE" rev-parse --git-dir >/dev/null 2>&1 || fail "not a git worktree: $LIVE"

cur=$(git -C "$LIVE" rev-parse HEAD 2>/dev/null) || fail "cannot read HEAD in $LIVE"
target=$(git -C "$LIVE" rev-parse origin/main 2>/dev/null) || fail "origin/main unreadable in $LIVE -- not advancing"

behind=$(git -C "$LIVE" rev-list --count HEAD..origin/main 2>/dev/null)
case "$behind" in
  ''|*[!0-9]*) fail "behind-count unreadable in $LIVE -- not advancing" ;;
esac

if [ "$cur" = "$target" ] || [ "$behind" -eq 0 ]; then
  log "current: $cur already matches origin/main, nothing to advance"
  exit 0
fi

# --- race gate: only advance in the window right after a tick -----------
if [ ! -f "$WATCHDOG_STATUS" ]; then
  skip "no watchdog status at $WATCHDOG_STATUS -- watchdog has not ticked from $LIVE yet, not advancing this pass"
fi
checked_line=$(grep -m1 '^checked:' "$WATCHDOG_STATUS" 2>/dev/null | sed 's/^checked:  *//')
[ -n "$checked_line" ] || skip "no checked: line in $WATCHDOG_STATUS -- not advancing this pass"
checked_epoch=$(date -u -j -f '%Y-%m-%dT%H:%M:%SZ' "$checked_line" +%s 2>/dev/null \
              || date -u -d "$checked_line" +%s 2>/dev/null)
[ -n "$checked_epoch" ] || skip "cannot parse watchdog checked: timestamp '$checked_line' -- not advancing this pass"
now=$(date -u +%s)
age=$((now - checked_epoch))
safe_until=$((TICK_INTERVAL - SAFETY_BUFFER))
if [ "$age" -lt 0 ] || [ "$age" -gt "$safe_until" ]; then
  skip "watchdog last ticked ${age}s ago, outside the 0-${safe_until}s post-tick window -- not advancing this pass"
fi

# --- gate: the candidate must demonstrably run, not just have CI-green --
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/ad99-advance-smoke.XXXXXX")"
cleanup() {
  git -C "$LIVE" worktree remove --force "$SCRATCH" >/dev/null 2>&1
  rm -rf "$SCRATCH" 2>/dev/null
  git -C "$LIVE" worktree prune >/dev/null 2>&1
}
trap cleanup EXIT

if ! git -C "$LIVE" worktree add --detach "$SCRATCH" "$target" >>"$LOG" 2>&1; then
  fail "could not create a scratch worktree at $target for the smoke test -- not advancing"
fi

SMOKE="$SCRATCH/.smoke"
mkdir -p "$SMOKE"
SUPERVISOR_STATE="$SMOKE" SUPERVISOR_STATUS="$SMOKE/watchdog.status" \
SUPERVISOR_LOG="$SMOKE/watchdog.log" SUPERVISOR_STAMP="$SMOKE/.last-restart" \
SUPERVISOR_HISTORY="$SMOKE/.restart-history" NOTIFY_ENV="$SMOKE/none.env" \
SUPERVISOR_PANE="advance-live-smoke-test:999.1" \
  bash "$SCRATCH/scripts/supervisor/watchdog.sh" >"$SMOKE/stdout" 2>"$SMOKE/stderr"
smoke_rc=$?

if [ "$smoke_rc" -ne 0 ] || [ ! -s "$SMOKE/watchdog.status" ] \
   || ! grep -q '^checked:' "$SMOKE/watchdog.status" \
   || ! grep -q '^state:' "$SMOKE/watchdog.status"; then
  log "smoke test at $target: rc=$smoke_rc status=$(cat "$SMOKE/watchdog.status" 2>/dev/null | tr '\n' ' ')"
  fail "candidate watchdog.sh at $target did not write a well-formed status -- not advancing, live worktree unchanged"
fi
log "smoke test at $target passed: $(grep '^state:' "$SMOKE/watchdog.status")"

# --- capture the rollback target before any mutation ---------------------
mkdir -p "$(dirname "$ROLLBACK")" 2>/dev/null
tmp="$ROLLBACK.$$"
if ! { printf '%s\n' "$cur" >"$tmp" && mv -f "$tmp" "$ROLLBACK"; }; then
  fail "could not record rollback target $cur to $ROLLBACK -- not advancing"
fi

# --- advance --------------------------------------------------------------
if ! git -C "$LIVE" checkout --detach "$target" >>"$LOG" 2>&1; then
  fail "checkout to $target failed in $LIVE -- live worktree left at $cur, rollback recorded at $ROLLBACK"
fi

newsha=$(git -C "$LIVE" rev-parse HEAD 2>/dev/null)
if [ "$newsha" != "$target" ]; then
  fail "post-checkout HEAD ($newsha) does not match target ($target) in $LIVE -- inconsistent, check by hand; rollback target $cur recorded at $ROLLBACK"
fi

log "ADVANCED $LIVE from $cur to $target ($behind commit(s))"
echo "advance-live: advanced $LIVE from ${cur:0:12} to ${target:0:12} ($behind commit(s))"
