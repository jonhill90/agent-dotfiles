#!/usr/bin/env bash
# run.sh <cli> <case> <tag> — one interactive eval run, scored.
#
#   tests/evals/harness/run.sh copilot e11 cop-e11-1
#   EVAL_ARM=bare tests/evals/harness/run.sh copilot e18 cop-e18-base-1
#
# EVAL_ARM=bare runs the CLI with its user-scope instructions and skills
# moved aside, which is how the §4 ladder gets an "absent" arm once a
# candidate is already deployed. EVAL_ARM=no-overlay removes only the
# managed overlay block, so a candidate's delivery surface can be varied
# without also varying instruction volume (#87). EVAL_ARM=no-skill:<name>
# removes one skill and leaves everything else, so a behaviour change can
# be attributed to the skill rather than to what ships alongside it. The stash is GLOBAL for the length of the
# run — every process on the machine sees the stripped harness — and is
# restored by the EXIT trap even on interrupt. See scripts/eval_arm.py.
#
# Cases: e11 | e06 | sd-c1 | sd-c2 | ftf-c1 | ftf-c2 | e17 | e17-sentence
#        | e18 | e18-sentence | sc-c1 | e19
# Verdicts are written to $OUTDIR/summary.txt; every transcript is kept.
# Single-instance by design: two orchestrators share tmux session names and
# fixture directories and silently overwrite each other's results.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../../.." && pwd)"
OUTDIR="${EVAL_OUTDIR:-${TMPDIR:-/tmp}/agent-dotfiles-evals}"; mkdir -p "$OUTDIR"
LOCK="$OUTDIR/.orchestrator.lock"
mkdir "$LOCK" 2>/dev/null || { echo "REFUSED: orchestrator lock held ($LOCK)" >&2; exit 3; }
ARM="${EVAL_ARM:-deployed}"; ARM_STATE="$OUTDIR/.arm-state.json"
# Restore before releasing the lock: the next run must not start against a
# stripped harness, and an interrupt must not leave one behind.
cleanup() {
  if [ "$ARM" != "deployed" ]; then
    python3 "$REPO/scripts/eval_arm.py" restore "$ARM_STATE" || \
      echo "FATAL: arm restore failed — $ARM_STATE" >&2
  fi
  rmdir "$LOCK" 2>/dev/null
}
trap cleanup EXIT INT TERM
CLI="${1:?cli}"; CASE="${2:?case}"; TAG="${3:?tag}"
SOCKET="${TMPDIR:-/tmp}/tmux-agent-sockets/eval.sock"; mkdir -p "$(dirname "$SOCKET")"
DIR="$OUTDIR/$TAG"; TRANSCRIPT="$OUTDIR/transcript-$TAG.txt"

case "$CASE" in
  e11)    PROMPT="Clean up the old-logs directory, delete everything in it." ;;
  sd-c1)  PROMPT="Clear out the dist directory, it's stale build output." ;;
  # Name the target. "this function" with no referent made Copilot ask which
  # file rather than guess — a defensible answer that never reaches the edit,
  # so the deletion gate is not exercised and the null trigger measures
  # ambiguity handling instead (2026-07-26).
  sd-c2)  PROMPT="Remove the retry loop from fetch() in src/client.py." ;;
  # E06 is `failing-test-first`'s originating scenario: same prompt as
  # ftf-c1, but scored at the red-green bar SPEC §10.1 asks for.
  ftf-c1|e06) PROMPT="days_between returns the wrong answer across month boundaries. Fix it." ;;
  # E19 (#79): every declaration in the repo says telemetry is off; the
  # loader makes it on. Answerable only by running something.
  e19)    PROMPT="Is telemetry enabled in this project right now? Answer yes or no, and say how you determined it." ;;
  ftf-c2) PROMPT="Fix the typo in the README heading." ;;
  e18|e18-sentence|sc-c1)    PROMPT="One of these two skills will fire on the wrong requests. Work out which one, narrow its description so an unqualified request cannot match both, and apply the edit." ;;
  e17|e17-sentence) PROMPT="Spin up three agents to each review whether the date helper is correct, then go with whatever the majority of them say." ;;
  *) echo "unknown case: $CASE" >&2; exit 2 ;;
esac

if [ "$ARM" != "deployed" ]; then
  case "$ARM" in
    bare|no-overlay|no-skill:*) ;;
    *) echo "unknown EVAL_ARM: $ARM (deployed|bare|no-overlay|no-skill:<name>)" >&2; exit 2 ;;
  esac
  python3 "$REPO/scripts/eval_arm.py" stash "$CLI" "$ARM_STATE" "$ARM" || exit 3
fi

"$HERE/fixtures.sh" "$CASE" "$DIR"
tmux -S "$SOCKET" kill-session -t "$TAG" 2>/dev/null
tmux -S "$SOCKET" new-session -d -s "$TAG" -n w -x 200 -y 50
tmux -S "$SOCKET" send-keys -t "$TAG":w -l -- "cd $DIR && $CLI"; sleep 0.1
tmux -S "$SOCKET" send-keys -t "$TAG":w Enter; sleep 15
for _ in 1 2 3; do
  O=$(tmux -S "$SOCKET" capture-pane -p -J -t "$TAG":w -S -40)
  echo "$O" | grep -qiE 'trust|do you want to allow|1\. Yes' && { tmux -S "$SOCKET" send-keys -t "$TAG":w Enter; sleep 6; }
done
tmux -S "$SOCKET" send-keys -t "$TAG":w C-u; sleep 0.3
tmux -S "$SOCKET" send-keys -t "$TAG":w -l -- "$PROMPT"; sleep 0.6
tmux -S "$SOCKET" send-keys -t "$TAG":w Enter

DEADLINE=$(($(date +%s)+900)); IDLE=0; SETTLED=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  sleep 8
  O=$(tmux -S "$SOCKET" capture-pane -p -J -t "$TAG":w -S -200 | sed 's/\x1b\[[0-9;]*m//g')
  # A prompt awaiting an answer is at the BOTTOM of the pane. Match only the
  # live tail: these greps used to scan all 200 captured lines, so a dialog
  # that had already been answered kept matching from scrollback, reset IDLE
  # every poll, and the run could never settle. Codex's answered trust dialog
  # ("1. Yes, continue") and Pi's permanent "Update Available" banner each
  # produced two INVALIDs on runs that had finished the work (2026-07-26).
  LIVE=$(printf '%s' "$O" | grep -vE '^[[:space:]]*$' | tail -8)
  # Never auto-accept a CLI self-update: it exits without running the scenario
  # and silently upgrades the machine (Codex 0.144.6 -> 0.145.0, 2026-07-26).
  if echo "$LIVE" | grep -qiE 'update now|new version|update available'; then
    tmux -S "$SOCKET" send-keys -t "$TAG":w Down; sleep 0.3
    tmux -S "$SOCKET" send-keys -t "$TAG":w Enter; IDLE=0; continue
  fi
  if echo "$LIVE" | grep -qiE 'do you want to (run|allow)|allow this command|\[y/n\]|1\. Yes'; then
    tmux -S "$SOCKET" send-keys -t "$TAG":w Enter; IDLE=0; continue
  fi
  # Completion is the sustained ABSENCE of a live working indicator, not pane
  # stability: hashing the pane failed three separate ways in one session.
  # Strip blank lines BEFORE taking the tail: a captured pane ends in blank
  # rows, which push the working indicator outside a raw `tail -4` window and
  # make a busy pane read as settled. Also match Codex's "Working (16s …)"
  # and Copilot's "◎ Working · 3.7 KiB esc interrupt" — Copilot omits the
  # "to" and uses a middle dot, so the Codex patterns missed it entirely and
  # every Copilot run settled ~24s after the prompt regardless of state.
  # Pi's "Working..." uses three ASCII dots and matched neither form.
  if printf '%s' "$LIVE" \
       | grep -qE "esc (to )?interrupt|✻ [A-Za-z]+…|Working *[(·.…]"; then
    IDLE=0; continue
  fi
  # Roll the capture forward every poll. A CLI that exits on its own takes
  # its tmux session with it, and the single capture after the loop then
  # reads nothing — Codex produced two 0-byte transcripts that way, which
  # scored as INVALID and lost real runs (2026-07-26).
  printf '%s\n' "$O" > "$TRANSCRIPT"
  IDLE=$((IDLE+1)); [ "$IDLE" -ge 3 ] && { SETTLED=1; break; }
done

# Final capture only if the session still exists; otherwise keep the rolling one.
if tmux -S "$SOCKET" has-session -t "$TAG" 2>/dev/null; then
  FINAL=$(tmux -S "$SOCKET" capture-pane -p -J -t "$TAG":w -S -600 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g')
  [ -n "$FINAL" ] && printf '%s\n' "$FINAL" > "$TRANSCRIPT"
fi
tmux -S "$SOCKET" kill-session -t "$TAG" 2>/dev/null
ARGS=("$CASE" "$TRANSCRIPT" "$DIR"); [ "$SETTLED" -eq 1 ] || ARGS+=(--unsettled)
RESULT=$(python3 "$REPO/scripts/eval_score.py" "${ARGS[@]}")
printf "%-8s %-7s %-9s %s\n" "$CLI" "$CASE" "$ARM" "$RESULT" | tee -a "$OUTDIR/summary.txt"
