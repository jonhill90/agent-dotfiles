#!/bin/bash
# restore.sh must bring every lane back after a tmux server loss -- from the
# ledger, never from a window name -- and must REFUSE any lane it cannot
# positively identify rather than start a fresh agent in its place.
#
# agent-dotfiles#237. Everything here runs on a PRIVATE tmux socket
# (`tmux -L ad237-test-$$`) with its own $HOME, its own state dir and a stub
# harness. The live `agent-dotfiles` session is never touched: this suite
# kills a tmux server on purpose, which is the exact loss the issue was filed
# about, and doing that to the estate to demonstrate a recovery would cost
# more than the recovery saves.
#
# The stub harness is a real limit and is stated rather than papered over: the
# pane runs `$D/bin/claude`, which records its argv and execs `sleep`, so what
# this suite proves is that restore hands the RIGHT SESSION ID to the harness
# for the right lane under the right name. That the id then rehydrates a
# conversation is Claude Code's own contract (`--resume <session id>`), and it
# is exercised against the real binary in the PR's live demonstration, not
# here -- a test suite that launched nine real agents would be neither fast
# nor hermetic.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUP="$HERE/../../scripts/supervisor"
pass=0; fail=0
ok()   { echo "  ok   $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL $1"; shift; [ $# -gt 0 ] && sed 's/^/       /' <<<"$*"; fail=$((fail+1)); }
want() { # want <name> <regex> <output>
  if grep -qE "$2" <<<"$3"; then ok "$1"; else bad "$1 — no /$2/ in:" "$3"; fi
}
wantnot() {
  if grep -qE "$2" <<<"$3"; then bad "$1 — unexpected /$2/ in:" "$3"; else ok "$1"; fi
}

SOCKET="ad237-test-$$"
# The REAL tmux, resolved before this suite puts its own wrapper on PATH. The
# wrapper must exec this absolute path: `env tmux` would find the wrapper
# again and recurse forever.
REAL_TMUX=$(command -v tmux) || { echo "  SKIP no tmux on PATH"; exit 0; }
D=$(mktemp -d)
cleanup() { "$REAL_TMUX" -L "$SOCKET" kill-server 2>/dev/null; rm -rf "$D"; }
trap cleanup EXIT

mkdir -p "$D/bin" "$D/repo" "$D/home/.claude/projects/lanes"
# Every tmux call in this suite AND inside restore.sh goes to the private
# socket, because this wrapper is what `tmux` resolves to on PATH.
cat > "$D/bin/tmux" <<EOF
#!/bin/bash
exec "$REAL_TMUX" -L "$SOCKET" "\$@"
EOF
# The stub harness. `exec sleep` matters: tmux reports \`sleep\` as the pane's
# current command, which is not one of the shells restore.sh treats as
# wreckage -- so a restored lane reads as running an agent, exactly as a real
# one would, and restore.sh's "already live, leave it alone" branch is
# genuinely exercised rather than stubbed around.
cat > "$D/bin/claude" <<EOF
#!/bin/bash
echo "\$@" >> "$D/launched.log"
exec sleep 600
EOF
chmod +x "$D/bin/tmux" "$D/bin/claude"
export PATH="$D/bin:$PATH"
export HOME="$D/home"
export AGENT_SUPERVISOR_STATE_DIR="$D/state"

# Three fixture conversations on disk, each carrying its own marker -- these
# stand in for `~/.claude/projects/<slug>/<session-id>.jsonl`, the files that
# survived the real incident untouched while every pane died.
LANE2_ID="11111111-1111-4111-8111-111111111111"
LANE3_ID="22222222-2222-4222-8222-222222222222"
for pair in "$LANE2_ID:ad901-first" "$LANE3_ID:ad902-second"; do
  id="${pair%%:*}"; marker="${pair##*:}"
  printf '{"type":"mode","sessionId":"%s"}\n{"type":"user","sessionId":"%s","timestamp":"2026-08-12T00:00:00.000Z","message":"brief for %s"}\n' \
    "$id" "$id" "$marker" > "$HOME/.claude/projects/lanes/$id.jsonl"
done

record() { # record <lane> <task> <harness-session-id>
  python3 "$SUP/cli.py" record-dispatch \
    --lane "$1" --task "$2" --summary "worktree=$D/repo; brief=$D/brief.md" \
    --pane-id "%$RANDOM" --pane-path "$D/repo" --command claude --harness claude \
    --server-id "socket:1" --session-id "\$0" --harness-session-id "$3" \
    --issue 901 --github jonhill90/agent-dotfiles >/dev/null
}

start_estate() { # a live session with three lanes, two of them working
  "$REAL_TMUX" -L "$SOCKET" kill-server 2>/dev/null
  tmux new-session -d -s ad237test -c "$D/repo" -n supervisor
  for w in 2 3 4; do tmux new-window -d -t "=ad237test:$w" -c "$D/repo"; done
  tmux rename-window -t "=ad237test:2" ad901-first
  tmux rename-window -t "=ad237test:3" ad902-second
  tmux rename-window -t "=ad237test:4" free-4
  for w in 2 3 4; do tmux send-keys -t "=ad237test:$w" "claude" Enter; done
  sleep 1
}

echo "restore.sh (agent-dotfiles#237)"

# ---------------------------------------------------------------- RED -------
# The recording half is what makes the restore possible, so the red state is
# a ledger written the way EVERY dispatch before #237 wrote one: lanes, tasks,
# panes, tmux session ids -- and no harness session id anywhere. Kill the
# server with those lanes mid-task and nothing in this repository can bring
# the conversations back.
rm -rf "$D/state"; : > "$D/launched.log"
record ad237test:2 ad901-first ""
record ad237test:3 ad902-second ""
start_estate
before=$(tmux list-windows -t ad237test -F '#{window_index} #{window_name}' 2>&1)
want "setup: three lanes are live before the kill" "2 ad901-first" "$before"
"$REAL_TMUX" -L "$SOCKET" kill-server 2>/dev/null
sleep 0.5
gone=$(tmux has-session -t ad237test 2>&1; echo "rc=$?")
want "RED: the tmux server is gone and so is every pane" "rc=[^0]" "$gone"
red=$(bash "$SUP/restore.sh" 2>&1); redrc=$?
want "RED: a pre-#237 ledger cannot restore lane 2"  "ad237test:2 +UNRECOVERABLE.*no harness session id" "$red"
want "RED: a pre-#237 ledger cannot restore lane 3"  "ad237test:3 +UNRECOVERABLE.*no harness session id" "$red"
if [ "$redrc" = 2 ]; then ok "RED: restore exits 2 when a lane cannot be brought back"; else bad "RED: exit was $redrc, not 2" "$red"; fi
wantnot "RED: and it started NOTHING in their place" "." "$(cat "$D/launched.log")"

# -------------------------------------------------------------- GREEN -------
# The same loss, against a ledger that recorded what the harness held.
rm -rf "$D/state"; : > "$D/launched.log"
record ad237test:2 ad901-first "$LANE2_ID"
record ad237test:3 ad902-second "$LANE3_ID"
start_estate
"$REAL_TMUX" -L "$SOCKET" kill-server 2>/dev/null
sleep 0.5
green=$(bash "$SUP/restore.sh" 2>&1); greenrc=$?
sleep 1
want "GREEN: lane 2 is restored"                  "ad237test:2 +RESTORED" "$green"
want "GREEN: lane 3 is restored"                  "ad237test:3 +RESTORED" "$green"
if [ "$greenrc" = 0 ]; then ok "GREEN: restore exits 0"; else bad "GREEN: exit was $greenrc, not 0" "$green"; fi

launched=$(cat "$D/launched.log")
if grep -qF -- "--resume $LANE2_ID" <<<"$launched"; then ok "GREEN: lane 2 resumed its own conversation ($LANE2_ID)"; else bad "GREEN: lane 2 did not resume $LANE2_ID" "$launched"; fi
if grep -qF -- "--resume $LANE3_ID" <<<"$launched"; then ok "GREEN: lane 3 resumed its own conversation ($LANE3_ID)"; else bad "GREEN: lane 3 did not resume $LANE3_ID" "$launched"; fi
# The ids are not interchangeable: each transcript carries the marker of the
# lane that owns it, so resuming the wrong one would be a wrong conversation
# under a right-looking name -- the failure #237 exists to prevent.
want "GREEN: $LANE2_ID is the transcript naming ad901-first" \
  "brief for ad901-first" "$(cat "$HOME/.claude/projects/lanes/$LANE2_ID.jsonl")"

names=$(tmux list-windows -t ad237test -F '#{window_index} #{window_name} #{pane_current_command}' 2>&1)
want "GREEN: lane 2 came back under its ledger name"  "^2 ad901-first" "$names"
want "GREEN: lane 3 came back under its ledger name"  "^3 ad902-second" "$names"
want "GREEN: and it is running an agent, not a shell" "^2 ad901-first sleep" "$names"

# ------------------------------------------------------- IDEMPOTENCE --------
# The second run must be a no-op. This is the half of #237 that is not about
# recovery at all: the incident's SECOND loss came from re-running a recovery
# over lanes that were already back, killing them mid-task.
pid_before=$(tmux display-message -p -t "=ad237test:2" '#{pane_pid}')
again=$(bash "$SUP/restore.sh" 2>&1); againrc=$?
pid_after=$(tmux display-message -p -t "=ad237test:2" '#{pane_pid}')
want "IDEMPOTENT: a live lane is reported LIVE, not restored" "ad237test:2 +LIVE" "$again"
if [ "$pid_before" = "$pid_after" ]; then ok "IDEMPOTENT: the live pane was not replaced"; else bad "IDEMPOTENT: pane pid changed $pid_before -> $pid_after"; fi
if [ "$againrc" = 0 ]; then ok "IDEMPOTENT: second run exits 0"; else bad "IDEMPOTENT: exit was $againrc" "$again"; fi

# ----------------------------------------------------------- MUTATION -------
# Corrupt ONE session id and confirm restore reports that lane unrecoverable
# instead of silently starting a fresh agent wearing its name. The other lane
# must still come back, or this check would pass for the wrong reason.
rm -rf "$D/state"; : > "$D/launched.log"
record ad237test:2 ad901-first "deadbeef-dead-4bee-8bee-deadbeefdead"
record ad237test:3 ad902-second "$LANE3_ID"
start_estate
"$REAL_TMUX" -L "$SOCKET" kill-server 2>/dev/null
sleep 0.5
mut=$(bash "$SUP/restore.sh" 2>&1); mutrc=$?
sleep 1
want "MUTATION: the corrupted lane is UNRECOVERABLE" \
  "ad237test:2 +UNRECOVERABLE.*no transcript on disk" "$mut"
want "MUTATION: the intact lane still comes back"     "ad237test:3 +RESTORED" "$mut"
if [ "$mutrc" = 2 ]; then ok "MUTATION: restore exits 2"; else bad "MUTATION: exit was $mutrc, not 2" "$mut"; fi
mutlaunched=$(cat "$D/launched.log")
wantnot "MUTATION: no agent was started for the corrupted lane" "deadbeef" "$mutlaunched"
if [ "$(grep -c . <<<"$mutlaunched")" = 1 ]; then ok "MUTATION: exactly one agent started, and it is the intact lane"; else bad "MUTATION: wrong number of agents started" "$mutlaunched"; fi
mutnames=$(tmux list-windows -t ad237test -F '#{window_index} #{window_name} #{pane_current_command}' 2>&1)
wantnot "MUTATION: nothing wears the corrupted lane's name with a fresh agent" "^2 ad901-first sleep" "$mutnames"

# A missing id and a corrupt one must fail the same way -- refusing only on
# the empty string would let any garbage through.
rm -rf "$D/state"; : > "$D/launched.log"
record ad237test:2 ad901-first "not-a-uuid-at-all"
nomatch=$(bash "$SUP/restore.sh" --dry-run 2>&1)
want "MUTATION: a non-uuid id is refused too, not passed to the harness" \
  "UNRECOVERABLE.*not a well-formed" "$nomatch"

# agent-dotfiles#262. A GLOB METACHARACTER in the id is the sharpest case:
# `restore.sh` used to interpolate the ledger value straight into a glob and
# only ask whether anything matched, so a corrupted id of exactly `*` matched
# any transcript on disk and proceeded to resume `*` -- a bare glob typed into
# a live shell, where it can expand before the harness ever sees it. Real
# reproduction, not a synthetic case: this is the reviewer's exact ledger
# value from the PR #262 review comment.
rm -rf "$D/state"; : > "$D/launched.log"
record ad237test:2 ad901-first '*'
globcase=$(bash "$SUP/restore.sh" --dry-run 2>&1)
want "MUTATION: a glob-metacharacter id ('*') is refused, not expanded" \
  "UNRECOVERABLE.*not a well-formed" "$globcase"
wantnot "MUTATION: the resume command line for the glob id was never built" \
  "resume \*" "$globcase"

# ------------------------------------------------------------- CODEX --------
# agent-dotfiles#261. The claude fixtures above never exercised the codex
# path at all -- restore.sh's transcript-existence check used to be a
# claude-only literal (`~/.claude/projects/*/<id>.jsonl`), which refused
# EVERY codex lane regardless of whether its transcript was really on disk.
# This fixture is codex's own layout, measured live on remote.hill90.com
# against a real rollout file (v0.147.0):
# `$CODEX_HOME/sessions/<yyyy>/<mm>/<dd>/rollout-<ts>-<session-id>.jsonl`.
mkdir -p "$D/bin" "$D/home/.codex/sessions/2026/08/12"
cat > "$D/bin/codex" <<EOF
#!/bin/bash
echo "\$@" >> "$D/launched.log"
exec sleep 600
EOF
chmod +x "$D/bin/codex"
CODEX_ID="33333333-3333-4333-8333-333333333333"
: > "$D/home/.codex/sessions/2026/08/12/rollout-2026-08-12T00-00-00-$CODEX_ID.jsonl"

record_codex() { # record_codex <lane> <task> <harness-session-id>
  python3 "$SUP/cli.py" record-dispatch \
    --lane "$1" --task "$2" --summary "worktree=$D/repo; brief=$D/brief.md" \
    --pane-id "%$RANDOM" --pane-path "$D/repo" --command codex --harness codex \
    --server-id "socket:1" --session-id "\$0" --harness-session-id "$3" \
    --issue 901 --github jonhill90/agent-dotfiles >/dev/null
}

rm -rf "$D/state"; : > "$D/launched.log"
record_codex ad237test:2 ad903-codex "$CODEX_ID"
start_estate
"$REAL_TMUX" -L "$SOCKET" kill-server 2>/dev/null
sleep 0.5
codex_out=$(bash "$SUP/restore.sh" 2>&1); codex_rc=$?
sleep 1
want "CODEX: lane 2 is restored"     "ad237test:2 +RESTORED" "$codex_out"
if [ "$codex_rc" = 0 ]; then ok "CODEX: restore exits 0"; else bad "CODEX: exit was $codex_rc, not 0" "$codex_out"; fi
codex_launched=$(cat "$D/launched.log")
if grep -qF -- "resume $CODEX_ID" <<<"$codex_launched"; then
  ok "CODEX: lane 2 resumed its own codex session ($CODEX_ID)"
else
  bad "CODEX: lane 2 did not resume $CODEX_ID" "$codex_launched"
fi
if grep -qF -- "--dangerously-bypass-approvals-and-sandbox" <<<"$codex_launched"; then
  ok "CODEX: the resume command carries the unattended flag, not just the bare resume"
else
  bad "CODEX: resume command missing --dangerously-bypass-approvals-and-sandbox" "$codex_launched"
fi

# The mutation case, for codex specifically: a session id with no matching
# rollout file on disk must refuse, not resume a fabricated conversation --
# proves H_TRANSCRIPT_GLOB's codex entry is actually load-bearing here, not
# just present and unused.
rm -rf "$D/state"; : > "$D/launched.log"
record_codex ad237test:2 ad903-codex "44444444-4444-4444-8444-444444444444"
start_estate
"$REAL_TMUX" -L "$SOCKET" kill-server 2>/dev/null
sleep 0.5
codex_mut=$(bash "$SUP/restore.sh" 2>&1); codex_mut_rc=$?
want "CODEX MUTATION: a codex id with no rollout file is UNRECOVERABLE" \
  "ad237test:2 +UNRECOVERABLE.*no transcript on disk" "$codex_mut"
if [ "$codex_mut_rc" = 2 ]; then ok "CODEX MUTATION: restore exits 2"; else bad "CODEX MUTATION: exit was $codex_mut_rc, not 2" "$codex_mut"; fi
wantnot "CODEX MUTATION: no agent was started for the missing-transcript lane" "." "$(cat "$D/launched.log")"

echo "  $pass passed, $fail failed"
[ "$fail" = 0 ]
