#!/bin/bash
# lanes.sh must tell four kinds of "idle" apart. All four were hit in one
# night, 2026-08-11, and each was misread as "nothing to do":
#   free / busy / hung / dead, plus unknown for harnesses with no probe.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANES="$HERE/../../scripts/supervisor/lanes.sh"
pass=0; fail=0
want() { # want <name> <window-name> <expected-state> <output>
  if grep -qE "^[0-9]+ +$2 +[^ ]+ +$3$" <<<"$4"; then echo "  ok   $1"; pass=$((pass+1));
  else echo "  FAIL $1 — $2 not '$3' in:"; sed 's/^/       /' <<<"$4"; fail=$((fail+1)); fi
}

D=$(mktemp -d); mkdir -p "$D/bin"
cp "$HERE/stubs/tmux-lanes" "$D/bin/tmux"
cat > "$D/fixture" <<'FIX'
1|arch|claude.exe|❯ ready|❯ ready
2|w-busy|claude.exe|esc to interrupt 3s|esc to interrupt 9s
3|w-hung|claude.exe|esc to interrupt 40m|esc to interrupt 40m
4|w-dead|zsh|❯ |❯ 
5|w-copilot|node|esc to interrupt|esc to interrupt
FIX
out=$(PATH="$D/bin:$PATH" LANES_FIXTURE="$D/fixture" LANES_CALLS="$D/calls" LANES_SAMPLE_GAP=0 bash "$LANES" 2>&1)

echo "lanes.sh"
want "a turn whose output advances is busy"              w-busy    busy    "$out"
want "a turn frozen across samples is hung, not busy"    w-hung    hung    "$out"
want "a pane running a shell is dead, not idle"          w-dead    dead    "$out"
# A Claude-specific probe must not be applied to other harnesses: on
# 2026-08-11 a healthy idle Copilot pane was called `hung` because that
# string appeared in its scrollback.
want "a non-Claude harness is unknown, never guessed"    w-copilot unknown "$out"
want "an idle Claude lane is free"                       arch      free    "$out"

# --free must never offer a lane that would swallow the dispatch.
free=$(PATH="$D/bin:$PATH" LANES_FIXTURE="$D/fixture" LANES_CALLS="$D/calls2" LANES_SAMPLE_GAP=0 bash "$LANES" --free 2>&1)
for bad in w-dead w-hung w-busy w-copilot; do
  if grep -qx "$bad" <<<"$free"; then echo "  FAIL --free offered $bad"; fail=$((fail+1));
  else echo "  ok   --free withholds $bad"; pass=$((pass+1)); fi
done

echo "  $pass passed, $fail failed"
[ "$fail" -eq 0 ]
