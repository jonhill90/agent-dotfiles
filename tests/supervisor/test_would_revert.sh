#!/bin/bash
# would-revert.sh must answer "would merging this branch revert X" by
# actually merging it, and must never touch the caller's working tree,
# index, or current branch while doing so.
#
# This is the agent-dotfiles#114 scenario: a two-dot diff renders every
# commit a branch is merely behind on as a deletion, and a lane read that
# as a real revert twice in two hours even after the correction was
# written into loop-tick.md. The load-bearing cases are: a branch that is
# only behind reports no deletions, a branch that truly deletes a file
# reports it and fails, a conflict is reported as a conflict and not
# silently folded into either of those, and the caller's own checkout is
# untouched throughout.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WR="$HERE/../../scripts/supervisor/would-revert.sh"
pass=0; fail=0

ok()   { echo "  ok   $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL $1"; sed 's/^/       /' <<<"${2:-}"; fail=$((fail+1)); }
want_exit() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected exit $3, got $2: ${4:-}"; fi }

echo "would-revert.sh"

D=$(mktemp -d)
export WORKTREE_ROOT="$D/roots"
mkdir -p "$WORKTREE_ROOT"

git init -q --bare "$D/origin.git"
git clone -q "$D/origin.git" "$D/repo"
REPO="$D/repo"
git -C "$REPO" config user.email test@example.com
git -C "$REPO" config user.name "Test"
git -C "$REPO" checkout -q -b main
echo one > "$REPO/mainfile.txt"
git -C "$REPO" add mainfile.txt
git -C "$REPO" commit -q -m "initial"
git -C "$REPO" push -q -u origin main
git -C "$REPO" remote set-head origin main >/dev/null 2>&1 || true

export WOULD_REVERT_REPO="$REPO"

# --- false-positive case: a branch that is merely behind -------------------
# This is the exact shape that produced both false holds in #114: main gains
# a commit the branch never had, which a two-dot diff renders as the branch
# "deleting" it. A real merge reverts nothing.
git -C "$REPO" checkout -q -b behind-branch
echo feature > "$REPO/feature.txt"
git -C "$REPO" add feature.txt
git -C "$REPO" commit -q -m "branch work"

git -C "$REPO" checkout -q main
echo two >> "$REPO/mainfile.txt"
git -C "$REPO" commit -q -am "main moved on without the branch"
git -C "$REPO" push -q origin main

out=$(bash "$WR" behind-branch origin/main 2>&1); rc=$?
want_exit "behind branch: exits 0" "$rc" 0 "$out"
if grep -q "DELETES" <<<"$out"; then bad "behind branch: reports no deletions" "$out"; else ok "behind branch: reports no deletions"; fi

# --- true-positive case: a branch that genuinely deletes a base file -------
git -C "$REPO" checkout -q main
git -C "$REPO" checkout -q -b delete-branch
git -C "$REPO" rm -q mainfile.txt
git -C "$REPO" commit -q -m "branch actually removes mainfile.txt"

out=$(bash "$WR" delete-branch origin/main 2>&1); rc=$?
want_exit "deleting branch: exits non-zero" "$rc" 1 "$out"
if grep -q "DELETES" <<<"$out" && grep -q "mainfile.txt" <<<"$out"; then
  ok "deleting branch: reports the deletion"
else
  bad "deleting branch: reports the deletion" "$out"
fi

# --- conflict case -----------------------------------------------------------
git -C "$REPO" checkout -q main
git -C "$REPO" checkout -q -b conflict-branch
echo "branch version" > "$REPO/mainfile.txt"
git -C "$REPO" commit -q -am "branch edits the same line main also changed"

git -C "$REPO" checkout -q main
echo "main version" > "$REPO/mainfile.txt"
git -C "$REPO" commit -q -am "main edits the same line"
git -C "$REPO" push -q origin main

out=$(bash "$WR" conflict-branch origin/main 2>&1); rc=$?
want_exit "conflict: exits non-zero" "$rc" 2
if grep -qi "CONFLICT" <<<"$out"; then ok "conflict: reported as a conflict"; else bad "conflict: reported as a conflict" "$out"; fi
if grep -q "DELETES" <<<"$out"; then bad "conflict: not reported as a deletion" "$out"; else ok "conflict: not reported as a deletion"; fi

# --- caller's working tree, index, and branch are untouched ----------------
git -C "$REPO" checkout -q main
echo "uncommitted edit" >> "$REPO/feature-not-tracked.txt"
before_branch=$(git -C "$REPO" branch --show-current)
before_status=$(git -C "$REPO" status --porcelain)

bash "$WR" delete-branch origin/main >/dev/null 2>&1

after_branch=$(git -C "$REPO" branch --show-current)
after_status=$(git -C "$REPO" status --porcelain)

if [ "$before_branch" = "$after_branch" ]; then ok "caller branch is unchanged"; else bad "caller branch is unchanged" "was $before_branch, now $after_branch"; fi
if [ "$before_status" = "$after_status" ]; then ok "caller working tree/index is unchanged"; else bad "caller working tree/index is unchanged" "before:$before_status  after:$after_status"; fi

# --- no scratch worktree is left behind, on any of the paths above ---------
leftover=$(git -C "$REPO" worktree list | grep -c "would-revert-" || true)
if [ "$leftover" -eq 0 ]; then ok "no scratch worktree left behind"; else bad "no scratch worktree left behind" "$(git -C "$REPO" worktree list)"; fi

rm -rf "$D"

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
