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
    TMUX_LOG="$D/tmux.log" TMUX_PANES="$D/panes" \
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
  || bad "pane 2 does not contain the reply" "$(cat "$D/panes/2" 2>/dev/null)"
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

# --- a message that IS a tmux key name is sent literally, not as a key -----
# agent-dotfiles#152. Without `-l`, `tmux send-keys` interprets an argument
# that matches a real key name as that key, not as text -- a reply of
# literally `C-c` fires SIGINT at the lane instead of typing "C-c", and
# `C-u` would silently wipe whatever the lane had already typed. The stub
# (tests/supervisor/stubs/tmux-dispatch) now models this: without `-l` a
# recognised key name never reaches the pane buffer at all, it is logged to
# <pane>.keys instead -- so this assertion can actually distinguish a
# literal-safe send from an unsafe one, which the old stub could not.
for key in "C-c" "Escape" "C-u"; do
  out=$(run "$D/one-blocked" "$key")
  rc=$?
  [ "$rc" -eq 0 ] && ok "key-name reply ($key): exits 0" || bad "exited $rc" "$out"
  pane="$D/panes/2"
  if [ "$key" = "C-u" ]; then
    # C-u's real action is "clear the buffer" -- sent literally it must
    # instead APPEAR in the buffer as the two characters C and u (well,
    # the text "C-u"), not clear it.
    grep -qF "$key" "$pane" 2>/dev/null && ok "C-u reply lands as literal text, not the clear action" \
      || bad "pane 2 does not contain the literal text \"$key\" -- got: $(cat "$pane" 2>/dev/null)"
  else
    grep -qF "$key" "$pane" 2>/dev/null && ok "$key reply lands as literal text in the pane" \
      || bad "pane 2 does not contain the literal text \"$key\" -- got: $(cat "$pane" 2>/dev/null)"
  fi
  [ -s "$pane.keys" ] && grep -q "^$key\$" "$pane.keys" 2>/dev/null \
    && bad "$key fired as a real key action instead of being typed literally" "$(cat "$pane.keys")" \
    || ok "$key was never interpreted as a key action"
done

# --- Enter is sent as its own key, not merely present in the buffer --------
# agent-dotfiles#152 finding 3: the old suite never checked Enter was
# actually sent -- deleting the Enter send-keys call still passed 9/9. The
# stub now logs every key it receives (Enter included, via `.keys` files
# for the literal case above and the same `.keys` log in general below)
# to <pane>.keys; assert on that rather than only on the buffer contents.
out=$(run "$D/one-blocked" "yes")
rc=$?
[ "$rc" -eq 0 ] && ok "plain reply: exits 0" || bad "exited $rc" "$out"
grep -q '^yes' "$D/panes/2" 2>/dev/null && ok "the plain reply lands in the blocked lane's pane" \
  || bad "pane 2 does not contain the reply" "$(cat "$D/panes/2" 2>/dev/null)"
grep -q 'send-keys -t t:2 Enter$' "$D/tmux.log" 2>/dev/null && ok "Enter was sent as its own key after the message" \
  || bad "no separate Enter send-keys call in the log" "$(cat "$D/tmux.log" 2>/dev/null)"

echo "  $pass passed, $fail failed"
[ "$fail" -eq 0 ]
