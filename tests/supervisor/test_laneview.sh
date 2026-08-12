#!/bin/bash
# laneview.sh must stay a pure viewer over lanes.sh --json: same fixture
# mechanism as test_lanes.sh (agent-dotfiles#178), reused here so a renderer
# bug can't be confused with a classification bug -- lanes.sh's own tests
# already cover that.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANEVIEW="$HERE/../../scripts/supervisor/laneview.sh"
TEXT_IMPL="$HERE/../../scripts/supervisor/laneview/text.sh"
pass=0; fail=0
ok()   { echo "  ok   $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL $1 — $2"; fail=$((fail+1)); }

echo "laneview.sh"

# An unknown implementation name must fail loudly and name what IS available,
# never silently fall back to one.
out=$(bash "$LANEVIEW" no-such-impl fixture 2>&1); rc=$?
if [ "$rc" -ne 0 ] && grep -q 'no renderer' <<<"$out"; then
  ok "an unknown renderer name fails, not falls back"
else
  bad "an unknown renderer name fails, not falls back" "rc=$rc out=$out"
fi

# End-to-end against the same stub tmux and fixture mechanism test_lanes.sh
# uses, so this exercises the real lanes.sh --json -> laneview.sh -> text.sh
# path, not a hand-built json blob.
D=$(mktemp -d); mkdir -p "$D/bin"
cp "$HERE/stubs/tmux-lanes" "$D/bin/tmux"
cp "$HERE/stubs/ps-lanes" "$D/bin/ps"
cat > "$D/fixture" <<'FIX'
1|arch|claude.exe|❯ ready|1|0
15|w-real-free|claude.exe|⏵⏵ bypass permissions on (shift+tab to cycle) · ← 1 agent|1|0
2|w-busy|claude.exe|esc to interrupt 3s|1|0
FIX

out=$(PATH="$D/bin:$PATH" LANES_FIXTURE="$D/fixture" bash "$LANEVIEW" text fixture 2>&1)
if grep -qE 'w-real-free +free' <<<"$out"; then
  ok "a free lane renders as free through the full laneview.sh path"
else
  bad "a free lane renders as free through the full laneview.sh path" "$out"
fi
if grep -qE 'w-busy +busy' <<<"$out"; then
  ok "a busy lane renders as busy through the full laneview.sh path"
else
  bad "a busy lane renders as busy through the full laneview.sh path" "$out"
fi
if grep -qE 'arch +supervisor' <<<"$out"; then
  ok "the supervisor window is never rendered as a lane"
else
  bad "the supervisor window is never rendered as a lane" "$out"
fi

# text.sh itself must never touch tmux or the network -- it is the "apart"
# implementation (#178), so calling it directly with canned json and no PATH
# to a real tmux, no daemon, must still work.
out=$(PATH=/usr/bin:/bin bash "$TEXT_IMPL" demo-session \
  '[{"window":1,"name":"free-2","command":"claude.exe","state":"free"}]' 2>&1)
if grep -qE '^\s*- free-2\s+free$' <<<"$out"; then
  ok "text.sh renders with no tmux and no daemon reachable"
else
  bad "text.sh renders with no tmux and no daemon reachable" "$out"
fi

echo "  $pass passed, $fail failed"
[ "$fail" -eq 0 ]
