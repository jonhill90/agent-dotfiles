#!/bin/bash
# Deterministic estate status. One call replaces the four the tick was making
# by hand every 3 minutes, identically, for hours.
#
# WHY THIS IS A TOOL AND NOT AN AGENT STEP: the output is a pure FUNCTION of
# the input -- load, proc count, swap, PR list, pane busy-flags. No judgement
# is involved in gathering it; judgement starts only once the numbers are on
# the table. Jon's own rule: a tool beats an agent every time.
#
# Exit codes carry the verdict so a caller can branch without re-reading:
#   0  nothing to do        (board empty, all agents busy, host fine)
#   1  action available     (a mergeable PR, or an idle agent)
#   3  HOST GUARD TRIPPED   -- do one cleanup and stop
#
# Moved here from the untracked `~/.local/state/estate-loop/status.sh` --
# load-bearing (called every 3 minutes), edited under pressure, and had no
# history, no tests, no review. `~/.local/state/estate-loop/status.sh` is now
# a symlink to this file, so the absolute path every caller already uses
# keeps working unchanged; the content is what moved.
#
# Split into functions so tests/test_status.sh can `source` this file and
# call each piece directly -- host_guard_tripped and reap_orphans take no
# implicit global state beyond what's passed in or what they read from the
# real host, so a test can drive them without running the whole script (and
# without waiting on a real `gh pr list` or a real tmux server for a check
# that has nothing to do with either).
set -uo pipefail
# STATUS_SH_TEST_PATH_PREFIX is an opt-in test seam only -- unset in every
# real invocation, so production PATH ordering is byte-identical to before
# this file had tests. tests/test_status.sh sets it so its fake tmux/gh/
# uptime/sysctl binaries win over the real ones this line otherwise
# guarantees precedence to.
export PATH="${STATUS_SH_TEST_PATH_PREFIX:+$STATUS_SH_TEST_PATH_PREFIX:}/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

# host_guard_tripped percore procs -- returns 0 (tripped) if either
# threshold is at or past its limit, 1 (not tripped) otherwise. A pure
# function of its two arguments, on purpose: the two thresholds this
# estate has actually needed (load/core, live claude-process count) are
# the only inputs, so a test can drive every boundary directly without
# faking `uptime`/`ps` output for a whole-script run.
host_guard_tripped() {
  local percore="$1" procs="$2"
  awk -v p="$percore" 'BEGIN{exit !(p>=3.0)}' && return 0
  [ "$procs" -ge 20 ] && return 0
  return 1
}

# reap_orphans -- kills every `yes` process whose PPID is genuinely 1 (a
# real orphan: its own parent already exited and nothing reparented it
# except the kernel's own init), and prints one line naming how many it
# reaped and how many are still alive afterward. Prints NOTHING when there
# are no orphans -- silence is the no-op path, not a "checked, found none"
# line, so a caller scraping this output for real reaps never has to filter
# out a false positive.
#
# ONLY PPID 1 is killed. A `yes` whose parent is alive belongs to a test
# still running and is not ours to touch -- reaping that would corrupt a
# live measurement, which is the more expensive of the two mistakes
# (agent-supervisor's own "never a fabricated success" shape, inverted:
# here the expensive failure is destroying real evidence, not inventing it).
reap_orphans() {
  local orphans n left
  orphans=$(ps -Ao pid,ppid,comm | awk '$3=="yes" && $2==1 {print $1}')
  if [ -n "$orphans" ]; then
    n=$(printf '%s\n' "$orphans" | wc -l | tr -d ' ')
    echo "$orphans" | xargs kill 2>/dev/null
    sleep 1
    left=$(ps -Ao pid,ppid,comm | awk '$3=="yes" && $2==1' | wc -l | tr -d ' ')
    echo "reaped: $n orphaned load generator(s), $left still alive"
  fi
}

list_prs() {
  local action=0 tmp
  tmp=$(mktemp)
  echo "prs:"
  for r in agent-tui agent-supervisor skills agent-dotfiles agent-evals; do
    gh pr list --repo "jonhill90/$r" --state open \
       --json number,mergeable,title \
       --jq ".[]|\"  $r #\(.number) [\(.mergeable)] \(.title[0:44])\"" 2>/dev/null
  done > "$tmp"
  if [ -s "$tmp" ]; then cat "$tmp"; grep -q 'MERGEABLE' "$tmp" && action=1; else echo "  (none open)"; fi
  rm -f "$tmp"
  return "$action"
}

check_agents() {
  local action=0 w n pane
  echo "agents:"
  # Window ids are stable across renumbering; names are not. Keyed on id.
  for pair in "@58:director" "@38:build-2" "@39:build-3" "@51:build-4" "@52:build-5"; do
    w=${pair%%:*}; n=${pair##*:}
    pane=$(tmux capture-pane -p -t "=estate:$w" 2>/dev/null) || { echo "  $n GONE"; action=1; continue; }
    # BUSY is more than "esc to interrupt". An agent that finished its turn
    # but left background shells running, or that is parked on a PR, is
    # mid-task -- dispatching onto it collides with work in flight. Measured
    # live: build-2 showed no interrupt marker while running 2 shells and
    # waiting on #91's CI.
    #
    # This is the agent-supervisor#414 shape inverted: there, a lane was
    # recorded complete having delivered nothing; here, a lane doing real
    # work reads as free. Both come from trusting one screen marker as the
    # whole truth.
    if grep -qE 'esc to interrupt|[0-9]+ shells? (still )?running|. to manage' <<<"$pane"; then
      echo "  $n busy"
    else
      echo "  $n IDLE"; action=1
    fi
  done
  return "$action"
}

main() {
  local load cores procs swap percore action=0

  load=$(uptime | sed 's/.*averages: //' | awk '{print $1}' | tr -d ,)
  cores=$(sysctl -n hw.ncpu)
  procs=$(ps -eo comm | grep -c '[c]laude')
  swap=$(sysctl -n vm.swapusage | awk '{print $6}')
  percore=$(awk -v l="$load" -v c="$cores" 'BEGIN{printf "%.2f", l/c}')
  echo "host: load=$load/${cores}c (${percore}/core) procs=$procs swap=$swap"

  reap_orphans

  if host_guard_tripped "$percore" "$procs"; then
    echo "HOST GUARD TRIPPED"
    exit 3
  fi

  list_prs || action=1
  check_agents || action=1

  if [ "$action" = "1" ]; then echo "verdict: ACTION AVAILABLE"; exit 1; fi
  echo "verdict: nothing to do"
  exit 0
}

# Run only when executed, not when sourced -- tests/test_status.sh sources
# this file to call host_guard_tripped/reap_orphans directly, and must not
# trigger a real host check (a real `gh pr list`, a real tmux server) just
# by loading the function definitions.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
