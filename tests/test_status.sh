#!/bin/bash
# Tests for scripts/status.sh -- the estate tick's status tool.
#
# Style matches agent-supervisor's own bash suites (tests/supervisor/test_*.sh
# there): ok()/bad() counters, a final "$pass passed, $fail failed" line, and
# the suite's own exit code is the pass/fail signal `tests/test_status.py`
# (this repo's unittest bridge, see that file) checks.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS_SH="$HERE/../scripts/status.sh"

pass=0
fail=0
ok()  { echo "  ok   $1"; pass=$((pass+1)); }
bad() { echo "  FAIL $1"; [ -n "${2:-}" ] && sed 's/^/       /' <<<"$2"; fail=$((fail+1)); }

cleanup_pids=()
cleanup() {
  for p in "${cleanup_pids[@]:-}"; do
    kill -9 "$p" 2>/dev/null
  done
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# host_guard_tripped -- both thresholds, both boundaries, mutation-checked
# in both directions per the brief: a test that can't be shown failing
# against a broken version isn't proof of anything.
# ---------------------------------------------------------------------------

source "$STATUS_SH"

# load/core threshold: >= 3.0 trips, below does not.
if host_guard_tripped 3.0 0; then ok "percore 3.0 (== threshold) trips guard"
else bad "percore 3.0 (== threshold) trips guard" "expected tripped, got not-tripped"; fi

if host_guard_tripped 2.99 0; then bad "percore 2.99 (< threshold) does not trip guard" "expected not-tripped, got tripped"
else ok "percore 2.99 (< threshold) does not trip guard"; fi

# proc-count threshold: >= 20 trips, below does not.
if host_guard_tripped 0 20; then ok "procs=20 (== threshold) trips guard"
else bad "procs=20 (== threshold) trips guard" "expected tripped, got not-tripped"; fi

if host_guard_tripped 0 19; then bad "procs=19 (< threshold) does not trip guard" "expected not-tripped, got tripped"
else ok "procs=19 (< threshold) does not trip guard"; fi

# Neither threshold met -> not tripped.
if host_guard_tripped 1.0 5; then bad "neither threshold met does not trip guard" "expected not-tripped, got tripped"
else ok "neither threshold met does not trip guard"; fi

# --- mutation checks: prove the tests above would actually catch a broken
# guard, by running the same assertions against deliberately-mutated copies
# of host_guard_tripped and confirming THEY fail. Each mutated copy is
# sourced in its own subshell so it never contaminates the real function
# used by the rest of this suite.

mutation_check() {
  local desc="$1" mutated_src="$2" args="$3" expect_tripped="$4"
  local result
  result=$(bash -c "
    $mutated_src
    if host_guard_tripped $args; then echo tripped; else echo not-tripped; fi
  ")
  if [ "$result" = "$expect_tripped" ]; then
    bad "mutation ($desc) went undetected" "mutated guard still returned the correct verdict ($result) -- the real tests above would NOT have caught this mutant"
  else
    ok "mutation ($desc) is caught (mutated guard returned '$result', real behavior is '$expect_tripped')"
  fi
}

# Load-average comparison inverted (>= became <): percore=3.0 should now
# read as NOT tripped under the mutant, i.e. the mutant disagrees with the
# real "tripped" verdict our tests above assert for percore=3.0.
inverted_percore='host_guard_tripped() { local percore="$1" procs="$2"; awk -v p="$percore" "BEGIN{exit !(p<3.0)}" && return 0; [ "$procs" -ge 20 ] && return 0; return 1; }'
mutation_check "load comparison inverted" "$inverted_percore" "3.0 0" "tripped"

# Load-average constant changed (3.0 -> 30.0): percore=3.0 should now read
# as NOT tripped.
changed_const='host_guard_tripped() { local percore="$1" procs="$2"; awk -v p="$percore" "BEGIN{exit !(p>=30.0)}" && return 0; [ "$procs" -ge 20 ] && return 0; return 1; }'
mutation_check "load constant changed (3.0 -> 30.0)" "$changed_const" "3.0 0" "tripped"

# proc-count comparison inverted (-ge became -lt): procs=20 should now read
# as NOT tripped.
inverted_procs='host_guard_tripped() { local percore="$1" procs="$2"; awk -v p="$percore" "BEGIN{exit !(p>=3.0)}" && return 0; [ "$procs" -lt 20 ] && return 0; return 1; }'
mutation_check "proc-count comparison inverted" "$inverted_procs" "0 20" "tripped"

# proc-count constant changed (20 -> 200): procs=20 should now read as NOT
# tripped.
changed_procs_const='host_guard_tripped() { local percore="$1" procs="$2"; awk -v p="$percore" "BEGIN{exit !(p>=3.0)}" && return 0; [ "$procs" -ge 200 ] && return 0; return 1; }'
mutation_check "proc-count constant changed (20 -> 200)" "$changed_procs_const" "0 20" "tripped"

# ---------------------------------------------------------------------------
# reap_orphans -- real orphan, real kill, real safety property.
#
# A real PPID-1 orphan is made by running `yes` in a background job inside a
# throwaway `bash -c` subprocess that then exits immediately without
# `wait`ing: once that subprocess is gone, its child `yes` has no parent
# left, and the kernel reparents it to PID 1 (launchd, on macOS). This is
# NOT a synthetic ps stand-in -- it is a genuinely orphaned process, and its
# PPID is checked with a real `ps` call below before anything is asserted
# against it, per the brief's own requirement.
# ---------------------------------------------------------------------------

bash -c 'yes >/dev/null 2>&1 & echo $!' > /tmp/status_test_orphan_pid.$$
orphan_pid=$(cat /tmp/status_test_orphan_pid.$$)
rm -f /tmp/status_test_orphan_pid.$$
cleanup_pids+=("$orphan_pid")

# Give the kernel a moment to complete the reparent.
sleep 0.5
orphan_ppid=$(ps -o ppid= -p "$orphan_pid" 2>/dev/null | tr -d ' ')

if [ "$orphan_ppid" = "1" ]; then
  ok "constructed a real orphan (pid $orphan_pid, confirmed ppid=1 via ps)"

  before_count=$(ps -Ao pid,ppid,comm | awk '$3=="yes" && $2==1' | wc -l | tr -d ' ')
  reap_output=$(reap_orphans)
  sleep 0.2
  still_alive=$(kill -0 "$orphan_pid" 2>/dev/null && echo yes || echo no)

  if [ "$still_alive" = "no" ]; then
    ok "reap_orphans killed the real orphan (pid $orphan_pid)"
  else
    bad "reap_orphans killed the real orphan" "pid $orphan_pid is still alive after reap_orphans ran"
  fi

  reported_n=$(sed -n 's/^reaped: \([0-9]*\) orphaned.*/\1/p' <<<"$reap_output")
  if [ "$reported_n" = "$before_count" ] && [ -n "$reported_n" ]; then
    ok "reap_orphans reported count ($reported_n) matches what was actually there ($before_count)"
  else
    bad "reap_orphans reported count matches reality" "reported '$reported_n', but $before_count real PPID-1 yes process(es) existed before the reap; output was:
$reap_output"
  fi
else
  bad "constructed a real PPID-1 orphan" "COULD NOT MEASURE: this environment reaped/reparented pid $orphan_pid before it could be observed with ppid=1 (observed ppid='$orphan_ppid'). The kill-path assertions above are skipped rather than faked -- see PR body."
fi

# --- Safety property (matters more than the kill, per the brief): a `yes`
# whose parent is ALIVE must survive reap_orphans untouched. The parent here
# is this very test script -- it does not exit until the suite is done, so
# the child's PPID is this script's own real, live PID, not 1.
yes >/dev/null 2>&1 &
live_child_pid=$!
cleanup_pids+=("$live_child_pid")
sleep 0.3
live_child_ppid=$(ps -o ppid= -p "$live_child_pid" 2>/dev/null | tr -d ' ')

if [ "$live_child_ppid" = "$$" ]; then
  reap_orphans >/dev/null
  sleep 0.2
  if kill -0 "$live_child_pid" 2>/dev/null; then
    ok "reap_orphans left a live-parented yes (pid $live_child_pid) untouched"
  else
    bad "reap_orphans left a live-parented yes untouched" "pid $live_child_pid was killed even though its parent ($$, this test script) was alive -- this would corrupt a real running test's load generator"
  fi
else
  bad "set up a live-parented yes to test the safety property" "expected ppid=$$, observed ppid='$live_child_ppid'"
fi
kill "$live_child_pid" 2>/dev/null

# --- No-orphan path stays silent: no side effect, no output.
# Confirm no stray PPID-1 `yes` remains from the sections above before
# asserting silence.
sleep 0.3
remaining=$(ps -Ao pid,ppid,comm | awk '$3=="yes" && $2==1' | wc -l | tr -d ' ')
if [ "$remaining" = "0" ]; then
  silent_output=$(reap_orphans)
  if [ -z "$silent_output" ]; then
    ok "reap_orphans is silent (no output, no side effect) when there are no orphans"
  else
    bad "reap_orphans is silent when there are no orphans" "expected no output, got: $silent_output"
  fi
else
  bad "no-orphan silent-path precondition" "COULD NOT MEASURE: $remaining stray PPID-1 yes process(es) remained from earlier in this suite, so the silent path was not actually exercised on an empty set"
fi

# ---------------------------------------------------------------------------
# Exit codes -- asserted by running the real script end-to-end against a
# faked environment on PATH, not assumed from reading the source.
# ---------------------------------------------------------------------------

FAKE_BIN="$(mktemp -d)"
cleanup_pids+=()  # fake bin dir cleaned up separately below
trap 'cleanup; rm -rf "$FAKE_BIN"' EXIT

write_fake() {
  local name="$1" body="$2"
  cat > "$FAKE_BIN/$name" <<EOF
#!/bin/bash
$body
EOF
  chmod +x "$FAKE_BIN/$name"
}

# Common fakes: quiet host (low load, few procs), no PRs, no tmux estate.
write_fake uptime 'echo "10:00  up 1 day,  load averages: 0.50 0.40 0.30"'
write_fake sysctl 'case "$2" in hw.ncpu) echo 8;; vm.swapusage) echo "used = 0.00M";; *) echo 0;; esac'
write_fake gh 'exit 1'   # no PRs reachable -> "(none open)"
write_fake tmux 'exit 1' # no estate session -> every pane "GONE" (action=1)
write_fake ps '/bin/ps "$@"' # real ps, just proxied so PATH-first fakes don't shadow real process listing needed by reap_orphans/procs count

run_status() {
  # STATUS_SH_TEST_PATH_PREFIX beats status.sh's own hardcoded
  # /usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin ordering, which otherwise
  # gives the real tmux/gh/sysctl priority over these fakes even with
  # FAKE_BIN prepended to PATH here.
  STATUS_SH_TEST_PATH_PREFIX="$FAKE_BIN" PATH="$FAKE_BIN:$PATH" bash "$STATUS_SH" >/tmp/status_test_out.$$ 2>&1
  echo $?
}

# Exit 0: quiet host, no PRs, but tmux fails -> every agent reads GONE ->
# action=1, so this fake setup alone cannot produce exit 0. To exercise a
# genuine "nothing to do" (0) as well as "action available" (1) and "guard
# tripped" (3), each gets its own tailored fake tmux.

write_fake tmux 'echo "esc to interrupt"'  # every pane looks busy -> action stays 0 from agents
rc=$(run_status)
out=$(cat /tmp/status_test_out.$$)
if [ "$rc" = "0" ]; then ok "exit 0 (nothing to do) asserted against a quiet, all-busy, PR-free host"
else bad "exit 0 (nothing to do)" "expected rc=0, got rc=$rc; output:
$out"; fi

write_fake tmux 'exit 1'  # panes GONE -> action=1
rc=$(run_status)
out=$(cat /tmp/status_test_out.$$)
if [ "$rc" = "1" ]; then ok "exit 1 (action available) asserted when an agent pane is unreachable"
else bad "exit 1 (action available)" "expected rc=1, got rc=$rc; output:
$out"; fi

write_fake uptime 'echo "10:00  up 1 day,  load averages: 50.00 40.00 30.00"'
rc=$(run_status)
out=$(cat /tmp/status_test_out.$$)
if [ "$rc" = "3" ]; then ok "exit 3 (HOST GUARD TRIPPED) asserted against a saturated host"
else bad "exit 3 (HOST GUARD TRIPPED)" "expected rc=3, got rc=$rc; output:
$out"; fi

rm -f /tmp/status_test_out.$$

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
