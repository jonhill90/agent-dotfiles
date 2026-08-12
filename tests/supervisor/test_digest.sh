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

# 6. A status-file value containing its own colon is not truncated. Reproduced
# live against watchdog.status before the fix: `checked:  2026-08-12T03:10:31Z`
# read back as `2026-08-12T03`.
chk "colon-bearing status value is not truncated" \
  "2026-08-12T00:00:00Z" "$(jq -r '.watchdog.checked' <<<"$(run --json)")"

# 7. lanes.sh exiting 0 with only its header row (a real, narrow tmux hiccup
# shape, not a fully empty result) is reported, not read as a clean idle estate.
cat > "$D/bin/lanes-header-only.sh" <<'S'
#!/bin/bash
printf 'WINDOW\tNAME\tCOMMAND\tSTATE\n'
S
chmod +x "$D/bin/lanes-header-only.sh"
out=$(PATH="$D/bin:$PATH" SUPERVISOR_STATE="$D/state" LANES_SESSION=nosuch \
  DIGEST_LANES_BIN="$D/bin/lanes-header-only.sh" bash "$DIGEST" 2>/dev/null)
grep -q "no lane rows" <<<"$out" && ok "header-only lanes.sh is reported, not read as idle" \
  || bad "header-only lanes.sh reported" "$out"

# 8. jq missing is named, not silently empty. Reproduced before the fix:
# `--json` with jq removed from PATH printed nothing at all to stdout.
NOJQ_PATH=""
while IFS= read -r d; do
  [ -n "$d" ] || continue
  [ -x "$d/jq" ] && continue
  NOJQ_PATH="${NOJQ_PATH:+$NOJQ_PATH:}$d"
done <<<"$(tr ':' '\n' <<<"$PATH")"
out=$(PATH="$D/bin:$NOJQ_PATH" SUPERVISOR_STATE="$D/state" LANES_SESSION=nosuch bash "$DIGEST" 2>/dev/null)
rc=$?
grep -q "jq is required" <<<"$out" && ok "missing jq is named, not silent" \
  || bad "missing jq named" "$out"
chk "missing jq exits 1" "1" "$rc"
jout=$(PATH="$D/bin:$NOJQ_PATH" SUPERVISOR_STATE="$D/state" LANES_SESSION=nosuch bash "$DIGEST" --json 2>/dev/null)
[ -n "$jout" ] && ok "missing jq --json is not a zero-byte payload" || bad "missing jq --json non-empty" "$jout"

# 9-12. THE BLOCKING FINDING (agent-dotfiles#192): the per-PR jq assembly
# (repo, number, title, head, run_sha, run_conclusion, ci_is_current,
# merge_state, verdict) never executed under test, because the stub gh in
# every test above fails unconditionally and `gh pr list` always takes the
# `continue` branch. A gh with a SUCCESS mode, so that block actually runs --
# and assertions on ci_is_current/merge_state across states that DISAGREE
# with each other, so hardcoding either field (the exact mutations the
# review applied) cannot pass all of them at once.
OK=$(mktemp -d); mkdir -p "$OK/bin" "$OK/fixtures"
cat > "$OK/bin/gh" <<'S'
#!/bin/bash
# Success-mode gh stub: serves canned PR/run JSON from $GH_STUB_FIXTURES so
# the per-PR assembly block actually executes under test.
FIX="${GH_STUB_FIXTURES:?}"
case "$1 $2" in
  "pr list")
    cat "$FIX/pr_list.json" ;;
  "run list")
    branch=""; prev=""
    for a in "$@"; do
      [ "$prev" = "--branch" ] && branch="$a"
      prev="$a"
    done
    f="$FIX/run_${branch}.json"
    [ -f "$f" ] && cat "$f" || echo "[]"
    ;;
  *) exit 1 ;;
esac
S
chmod +x "$OK/bin/gh"

cat > "$OK/fixtures/pr_list.json" <<'S'
[
  {"number":1,"title":"current head, clean merge","headRefOid":"aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111","headRefName":"b1","mergeStateStatus":"CLEAN","comments":[]},
  {"number":2,"title":"stale pass, dirty merge","headRefOid":"bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222","headRefName":"b2","mergeStateStatus":"DIRTY","comments":[]},
  {"number":3,"title":"no CI run at all, behind","headRefOid":"cccc3333cccc3333cccc3333cccc3333cccc3333","headRefName":"b3","mergeStateStatus":"BEHIND","comments":[]},
  {"number":4,"title":"current head, CI failed","headRefOid":"dddd4444dddd4444dddd4444dddd4444dddd4444","headRefName":"b4","mergeStateStatus":"CLEAN","comments":[{"body":"REQUEST CHANGES: fix x"}]}
]
S
cat > "$OK/fixtures/run_b1.json" <<'S'
[{"headSha":"aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111","conclusion":"success"}]
S
cat > "$OK/fixtures/run_b2.json" <<'S'
[{"headSha":"oldoldoldoldoldoldoldoldoldoldoldoldoldo","conclusion":"success"}]
S
cat > "$OK/fixtures/run_b4.json" <<'S'
[{"headSha":"dddd4444dddd4444dddd4444dddd4444dddd4444","conclusion":"failure"}]
S
# b3 deliberately has no run_b3.json -- stub falls back to "[]", i.e. no run.

run_ok() {
  PATH="$OK/bin:$PATH" SUPERVISOR_STATE="$D/state" LANES_SESSION=nosuch \
    DIGEST_REPOS=test-repo DIGEST_OWNER=ownerx GH_STUB_FIXTURES="$OK/fixtures" \
    bash "$DIGEST" --json 2>/dev/null
}
J=$(run_ok)
pr() { jq -c --argjson n "$1" '.prs[] | select(.number==$n)' <<<"$J"; }

# 9. current head + a matching run -> ci_is_current true, run_conclusion success.
p1=$(pr 1)
chk "PR1 ci_is_current true on a matching head" "true" "$(jq -r '.ci_is_current' <<<"$p1")"
chk "PR1 run_conclusion success" "success" "$(jq -r '.run_conclusion' <<<"$p1")"
chk "PR1 merge_state passes through CLEAN" "CLEAN" "$(jq -r '.merge_state' <<<"$p1")"

# 10. a run exists but for an OLDER head -> ci_is_current false even though
# the run itself succeeded. This is what distinguishes "CI passed on this
# head" from "CI passed on an older head" (#137). Hardcoding
# ci_is_current:true or merge_state:"CLEAN" both break this row.
p2=$(pr 2)
chk "PR2 ci_is_current false on a stale head" "false" "$(jq -r '.ci_is_current' <<<"$p2")"
chk "PR2 run_conclusion success (the stale run itself passed)" "success" "$(jq -r '.run_conclusion' <<<"$p2")"
chk "PR2 merge_state passes through DIRTY" "DIRTY" "$(jq -r '.merge_state' <<<"$p2")"

# 11. no run at all -- must read distinctly from both "CI failed" and "CI
# passed on an older head" (#149/#161: a conflicted branch with no run at
# all read exactly like a pending one).
p3=$(pr 3)
chk "PR3 run_conclusion is NO RUN, not a guessed pass/fail" "NO RUN" "$(jq -r '.run_conclusion' <<<"$p3")"
chk "PR3 ci_is_current false with no run" "false" "$(jq -r '.ci_is_current' <<<"$p3")"
chk "PR3 merge_state passes through BEHIND" "BEHIND" "$(jq -r '.merge_state' <<<"$p3")"

# 12. current head + a run that failed -- distinct again from both above.
p4=$(pr 4)
chk "PR4 run_conclusion failure" "failure" "$(jq -r '.run_conclusion' <<<"$p4")"
chk "PR4 ci_is_current true (the failing run IS for this head)" "true" "$(jq -r '.ci_is_current' <<<"$p4")"
chk "PR4 verdict reads REQUEST CHANGES from the comment" "REQUEST CHANGES" "$(jq -r '.verdict' <<<"$p4")"

rm -rf "$OK"

echo "  $pass passed, $fail failed"
[ "$fail" -eq 0 ]
