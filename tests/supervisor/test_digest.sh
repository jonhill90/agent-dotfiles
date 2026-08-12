#!/bin/bash
# digest.sh replaces ~26 subprocess round-trips the Director made every tick.
# Because a reader trusts it INSTEAD of looking, its failure modes matter more
# than its happy path: a section it could not read must say so, and an
# unreachable GitHub must never look like "no open PRs".
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIGEST="$HERE/../../scripts/supervisor/digest.sh"
pass=0; fail=0
ok()  { echo "  ok   $1"; pass=$((pass+1)); }
bad() { echo "  FAIL $1 — $2"; fail=$((fail+1)); }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want '$2', got '$3'"; fi; }

command -v jq >/dev/null 2>&1 || { echo "  SKIP no jq"; exit 0; }

D=$(mktemp -d); mkdir -p "$D/bin" "$D/state"
trap 'rm -rf "$D"' EXIT INT TERM

# A gh that always fails, to prove an unreachable GitHub is not silence.
printf '#!/bin/bash\nexit 1\n' > "$D/bin/gh"; chmod +x "$D/bin/gh"
cat > "$D/state/watchdog.status" <<'S'
checked:  2026-08-12T00:00:00Z
state:    asleep
restarts: 0 in the last 3600s
S
cat > "$D/state/inbox-poll.status" <<'S'
checked: 2026-08-12T00:00:00Z
state:   ok
S

run() { PATH="$D/bin:$PATH" SUPERVISOR_STATE="$D/state" LANES_SESSION=nosuch bash "$DIGEST" "$@" 2>/dev/null; }

# 1. THE ONE THAT MATTERS: gh unreachable must not read as "no PRs".
out=$(run)
grep -q "this digest is INCOMPLETE" <<<"$out" && ok "gh failure is announced, not silent" \
  || bad "gh failure is announced" "$out"
grep -q "gh pr list failed" <<<"$out" && ok "the failing repo is named" || bad "failing repo named" "$out"

# 2. Exit code distinguishes complete from partial.
run >/dev/null 2>&1; chk "partial digest exits 1" "1" "$?"

# 3. --json stays valid JSON under failure, and says so in-band.
j=$(run --json)
jq -e . >/dev/null 2>&1 <<<"$j" && ok "--json is valid JSON when things fail" || bad "--json valid under failure" "$j"
chk "ok=false under failure" "false" "$(jq -r '.ok' <<<"$j")"
[ "$(jq -r '.errors|length' <<<"$j")" -gt 0 ] && ok "errors[] is populated" || bad "errors populated" "$j"

# 4. An unreadable watchdog.status is named, not defaulted.
out=$(PATH="$D/bin:$PATH" SUPERVISOR_STATE="$D/none" LANES_SESSION=nosuch bash "$DIGEST" 2>/dev/null)
grep -q "watchdog.status unreadable" <<<"$out" && ok "unreadable watchdog.status is named" \
  || bad "unreadable watchdog named" "$out"
grep -q "UNREADABLE" <<<"$out" && ok "watchdog state reads UNREADABLE, not a guess" \
  || bad "watchdog UNREADABLE" "$out"

# 5. A missing lanes session is reported rather than rendering as "no lanes".
grep -q "lanes.sh returned nothing" <<<"$(run)" && ok "empty lanes.sh is reported" \
  || bad "empty lanes reported" "$(run)"

echo "  $pass passed, $fail failed"
[ "$fail" -eq 0 ]
