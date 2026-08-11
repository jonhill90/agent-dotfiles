#!/bin/bash
# Answer "would merging this branch revert X" by actually merging it,
# instead of by reading a diff.
#
# WHY: agent-dotfiles#114. `loop-tick.md` already explains, at length, that
# `git diff main..branch` renders every commit the branch lacks as a
# deletion and that this is not a prediction about merging -- #107 wrote
# that section from scratch, with a reproduction. It held for about an
# hour: a lane read the two-dot diff on PR #111, reported a revert of
# #104, and held the PR. Refuted by merging into a scratch worktree --
# nothing was actually deleted. Two false holds in two hours, from the
# same reading, with the correction already merged and in the file the
# supervisor is told to follow.
#
# A rule written into a ~500-line document only works if the reader
# happens to read that section before they need it. A lane dispatched to
# review a PR is briefed on the PR, not on the tick file, and has no
# reason to consult a merge-mechanics section it does not know exists.
# This is the same move as `worktree.sh` and `claim.sh`: a paragraph a
# reader might skip becomes a command a reviewer can run.
#
# WHAT IT DOES: merges <branch-or-ref> into a scratch worktree at [base],
# built with `worktree.sh new` so cleanup follows the same contract every
# other lane worktree does, and reports three things distinctly --
#   DELETES    files the merge removes that [base] has -- the actual
#              question being asked.
#   CONFLICTS  files the merge cannot resolve on its own -- the other real
#              cause of "this looks like a revert" and NOT the same thing
#              as a deletion.
#   also touches   everything else the merge adds or modifies.
# The scratch worktree is removed on every exit path, including a failed
# merge or a conflict -- a conflicted merge leaves the tree dirty, and
# `worktree.sh done` refuses to remove anything dirty on purpose (the
# safe-deletion contract), so a conflict is aborted first. There is
# nothing in a scratch worktree worth keeping; it exists to answer one
# question.
#
# WHAT IT NEVER DOES: touch the working tree, index, or current branch of
# the repo it is run from. It never `git checkout`s, `git merge`s, or
# writes anywhere in that repo -- `worktree.sh new` only adds a linked
# worktree, which is metadata in `.git/worktrees`, not a change to any
# other checkout. A tool for checking a merge that mutates the caller's
# checkout would be worse than the diff it replaces.
#
# Usage:
#   would-revert.sh <branch-or-ref> [base]
#
# [base] defaults to origin/main. Run from the repo to check; set
# WOULD_REVERT_REPO to point at a different one.
#
# Exit 0  the merge deletes nothing (clean, usable as a check).
# Exit 1  the merge deletes files [base] has.
# Exit 2  the merge conflicts, or the merge/worktree could not be built.
set -uo pipefail

usage() { sed -n '/^# Usage:/,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REF="${1:-}"
[ -n "$REF" ] || usage
BASE="${2:-origin/main}"
REPO="${WOULD_REVERT_REPO:-$PWD}"

git -C "$REPO" rev-parse --verify --quiet "$REF" >/dev/null \
  || { echo "would-revert: '$REF' is not a ref in $REPO" >&2; exit 2; }
git -C "$REPO" rev-parse --verify --quiet "$BASE" >/dev/null \
  || { echo "would-revert: '$BASE' is not a ref in $REPO" >&2; exit 2; }

WORKTREE=""

cleanup() {
  [ -n "$WORKTREE" ] || return 0
  # A conflicted or half-finished merge leaves the scratch tree dirty;
  # `worktree.sh done` refuses to remove anything dirty, matching
  # safe-deletion. Abort first -- there is nothing here worth keeping.
  git -C "$WORKTREE" merge --abort >/dev/null 2>&1 || true
  "$HERE/worktree.sh" done "$WORKTREE" >/dev/null 2>&1 \
    || echo "would-revert: could not remove scratch worktree $WORKTREE -- remove it by hand" >&2
}
trap cleanup EXIT

WORKTREE_ERR=$(mktemp)
WORKTREE=$("$HERE/worktree.sh" new "would-revert-$$" "$REPO" "$BASE" 2>"$WORKTREE_ERR")
rc=$?
if [ "$rc" -ne 0 ] || [ -z "$WORKTREE" ] || [ ! -d "$WORKTREE" ]; then
  echo "would-revert: could not build a scratch worktree at $BASE" >&2
  sed 's/^/  /' "$WORKTREE_ERR" >&2
  rm -f "$WORKTREE_ERR"
  WORKTREE=""
  exit 2
fi
rm -f "$WORKTREE_ERR"

# Captured before the merge, not re-derived from $BASE afterwards: $BASE can
# be a moving ref like origin/main, and the diff must be against the exact
# commit this worktree started from.
START_SHA=$(git -C "$WORKTREE" rev-parse HEAD)

MERGE_OUT=$(git -C "$WORKTREE" \
  -c user.name="would-revert.sh" -c user.email="would-revert@localhost" \
  -c commit.gpgsign=false \
  merge --no-edit "$REF" 2>&1)
merge_rc=$?

if [ "$merge_rc" -ne 0 ]; then
  conflicts=$(git -C "$WORKTREE" diff --name-only --diff-filter=U)
  if [ -n "$conflicts" ]; then
    echo "would-revert: merging $REF into $BASE CONFLICTS -- not a clean merge, not a deletion either:"
    sed 's/^/  /' <<<"$conflicts"
    exit 2
  fi
  echo "would-revert: merge of $REF into $BASE failed:" >&2
  echo "$MERGE_OUT" >&2
  exit 2
fi

STATUS=$(git -C "$WORKTREE" diff --name-status "$START_SHA" HEAD)
DELETES=$(awk '$1=="D"{print $2}' <<<"$STATUS")
OTHERS=$(awk '$1!="D"{ $1=""; sub(/^ /,""); print }' <<<"$STATUS")

if [ -n "$DELETES" ]; then
  echo "would-revert: merging $REF into $BASE DELETES:"
  sed 's/^/  /' <<<"$DELETES"
  [ -z "$OTHERS" ] || { echo "would-revert: also adds/modifies:"; sed 's/^/  /' <<<"$OTHERS"; }
  exit 1
fi

echo "would-revert: merging $REF into $BASE deletes nothing"
[ -z "$OTHERS" ] || { echo "would-revert: adds/modifies:"; sed 's/^/  /' <<<"$OTHERS"; }
exit 0
