#!/bin/bash
# inbox-route.sh must deliver Jon's Telegram reply to the one lane that is
# actually waiting on it, and must never guess when that is ambiguous.
#
# agent-dotfiles#142. Routing is built on lanes.sh's real `blocked` state
# (#123/#124), not a separate table, so this drives the REAL lanes.sh and
# notify.sh through the same tmux/curl stubs the rest of the suite uses --
# nothing about routing itself is reimplemented or mocked away here.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROUTE="$HERE/../../scripts/supervisor/inbox-route.sh"
pass=0; fail=0
ok()  { echo "  ok   $1"; pass=$((pass+1)); }
bad() { echo "  FAIL $1"; sed 's/^/       /' <<<"${2:-}"; fail=$((fail+1)); }

echo "inbox-route.sh"

D=$(mktemp -d); mkdir -p "$D/bin" "$D/state/.local/state/agent-dotfiles-supervisor"
cp "$HERE/stubs/tmux-dispatch" "$D/bin/tmux"

# notify.sh's real caller gate + Telegram send, with curl stubbed so no test
# touches the network -- same technique as test_notify.sh.
cat > "$D/bin/curl" <<'EOF'
#!/bin/bash
echo "curl $*" >> "${CURL_LOG:-/dev/null}"
exit 0
EOF
chmod +x "$D/bin/curl"
cat > "$D/notify.env" <<'EOF'
AGENT_NOTIFY_TELEGRAM_TOKEN=fake-token
AGENT_NOTIFY_TELEGRAM_CHAT_ID=fake-chat
EOF

run() {  # run <lanes-fixture-file> <message...>
  local fixture="$1"; shift
  : > "$D/tmux.log"; rm -rf "$D/panes"; mkdir -p "$D/panes"
  : > "$D/curl.log"
  PATH="$D/bin:$PATH" LANES_FIXTURE="$fixture" LANES_SESSION=t \
    TMUX_LOG="$D/tmux.log" TMUX_PANES="$D/panes" TMUX_PROBE_LOG="$D/probe.log" \
    HOME="$D/state" NOTIFY_ENV="$D/notify.env" CURL_LOG="$D/curl.log" \
    bash "$ROUTE" "$@" t
}

# --- exactly one blocked lane: unambiguous, deliver there -------------------
cat > "$D/one-blocked" <<'FIX'
1|arch|claude.exe|❯ ready|1|0
2|ad99-thing|claude.exe|Do you want to proceed?\n❯ 1. Yes\n  2. No\n Esc to cancel · Tab to amend|1|0
3|free-3|claude.exe|❯ ready|1|0
FIX
out=$(run "$D/one-blocked" "yes")
rc=$?
[ "$rc" -eq 0 ] && ok "exactly one blocked lane: exits 0" || bad "exited $rc" "$out"
grep -q '^yes' "$D/panes/2" 2>/dev/null && ok "the reply lands in the blocked lane's pane" \
  || bad "pane 2 does not contain the reply" "$(
       echo "--- route stdout/stderr ---"; echo "$out"
       echo "--- ls -la \$D/panes ---"; ls -la "$D/panes" 2>&1
       echo "--- \$D/tmux.log ---"; cat "$D/tmux.log" 2>&1
       echo "--- probe.log ---"; cat "$D/probe.log" 2>&1
       echo "--- od of panes/2 ---"; od -c "$D/panes/2" 2>&1 | head -5
       echo "--- lanes.sh --blocked ---"
       PATH="$D/bin:$PATH" LANES_FIXTURE="$D/one-blocked" LANES_SESSION=t \
         TMUX_LOG=/dev/null TMUX_PANES="$D/probe-panes" HOME="$D/state" \
         bash "$HERE/../../scripts/supervisor/lanes.sh" --blocked t 2>&1
       echo "--- lanes.sh --json ---"
       PATH="$D/bin:$PATH" LANES_FIXTURE="$D/one-blocked" LANES_SESSION=t \
         TMUX_LOG=/dev/null TMUX_PANES="$D/probe-panes" HOME="$D/state" \
         bash "$HERE/../../scripts/supervisor/lanes.sh" --json t 2>&1
       echo "--- which tmux (test PATH) ---"
       PATH="$D/bin:$PATH" command -v tmux 2>&1
       PATH="$D/bin:$PATH" bash -c 'type -a tmux' 2>&1
       echo "--- stub perms ---"; ls -la "$D/bin" 2>&1
       echo "--- real tmux on box ---"; command -v tmux 2>&1; tmux -V 2>&1
       echo "--- locale/bash ---"; echo "LANG=$LANG LC_ALL=${LC_ALL:-} TMPDIR=${TMPDIR:-}"; bash --version | head -1
       echo "--- leaked env (TMUX/LANES/DISPATCH/SUPERVISOR) ---"
       env | grep -E '^(TMUX|LANES|DISPATCH|SUPERVISOR|NOTIFY|CURL)' 2>&1
       echo "--- default panes dir ---"; ls -la "${TMPDIR:-/tmp}/tmux-dispatch-panes" 2>&1
     )"
[ -s "$D/curl.log" ] && bad "notify.sh was called even though delivery succeeded" "$(cat "$D/curl.log")" \
  || ok "no Telegram notification sent when delivery succeeds"

# --- zero blocked lanes: ask Jon rather than dropping it -------------------
cat > "$D/zero-blocked" <<'FIX'
1|arch|claude.exe|❯ ready|1|0
2|free-2|claude.exe|❯ ready|1|0
3|ad50-review|claude.exe|esc to interrupt 3s|1|0
FIX
out=$(run "$D/zero-blocked" "yes")
rc=$?
[ "$rc" -eq 0 ] && ok "zero blocked lanes: still exits 0 (Jon was told)" || bad "exited $rc" "$out"
[ -s "$D/curl.log" ] && ok "zero blocked lanes notifies Jon through notify.sh" \
  || bad "no notify.sh call for zero blocked lanes"
[ -z "$(ls "$D/panes" 2>/dev/null)" ] && ok "nothing was sent to any pane" \
  || bad "a pane received the message despite zero blocked lanes" "$(ls "$D/panes")"

# --- several blocked lanes: ask which, rather than guess --------------------
cat > "$D/two-blocked" <<'FIX'
1|arch|claude.exe|❯ ready|1|0
2|ad10-a|claude.exe|Do you want to proceed?\n❯ 1. Yes\n  2. No\n Esc to cancel|1|0
3|ad20-b|claude.exe|Enter to select · Esc to cancel|1|0
FIX
out=$(run "$D/two-blocked" "yes")
rc=$?
[ "$rc" -eq 0 ] && ok "several blocked lanes: exits 0 (Jon was asked)" || bad "exited $rc" "$out"
[ -s "$D/curl.log" ] && ok "several blocked lanes notifies Jon to disambiguate" \
  || bad "no notify.sh call for several blocked lanes"
[ -z "$(ls "$D/panes" 2>/dev/null)" ] && ok "nothing was guessed into any pane" \
  || bad "a pane received the message despite ambiguity" "$(ls "$D/panes")"

echo "  $pass passed, $fail failed"
[ "$fail" -eq 0 ]
