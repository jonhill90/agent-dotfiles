#!/bin/bash
# PreToolUse guard (agent-dotfiles#276, table row 3).
#
# Rule: never commit to main (agent-supervisor/AGENTS.md, "Conventions":
# "Branch with a type prefix; never commit to main."). A branch check before
# a commit is a fact, not a judgement call.
#
# agent-dotfiles#353: the branch is resolved from where the commit LANDS,
# never from where the session sits. The first version read the payload's
# cwd, so a session in a worktree could commit to a checkout on main (the
# event this guard exists to prevent) and a session on main could not
# commit to its own feature worktree. lib/command_guard.py's `main-targets`
# rule resolves every `git commit` in the payload to a directory from the
# command text -- git's own -C options, a preceding `cd` in the same shell
# scope, else the session cwd -- and reports UNRESOLVED, with the reason,
# for anything it cannot resolve without guessing (an expanded path, a
# `cd -`, pushd/popd, a `||` after a cd, git --git-dir/--work-tree). Every
# target is checked; one on main, one unreadable, or one unresolved refuses
# the whole call. Fail closed is the only safe answer for a write.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

RULE="main-branch-guard (agent-dotfiles#276)"
hook_require_parsed "$RULE"

# Only in scope for an actual commit invocation. Quoted text, heredoc
# bodies and evidence are arguments, not commands (command_guard.py).
hook_command_violates "$RULE" main || exit 0

SESSION_CWD="$(printf '%s' "$HOOK_STDIN" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
print(data.get("cwd", "") or "")
' 2>/dev/null)"
[ -n "$SESSION_CWD" ] || SESSION_CWD="$PWD"

TARGETS="$(python3 "$SCRIPT_DIR/lib/command_guard.py" main-targets <<<"$HOOK_COMMAND" 2>/dev/null)"
STATUS=$?
if [ "$STATUS" -ne 10 ]; then
  # The scope check found a commit but the resolver could not name a
  # target for it (a parse error, or a `commit` in a position the resolver
  # does not read): refuse rather than guess where it lands.
  hook_block "$RULE" \
    "could not resolve where this commit would land from the command text -- refusing rather than guessing (agent-dotfiles#353)."
fi

while IFS=$'\t' read -r kind value; do
  [ -n "$kind" ] || continue
  if [ "$kind" = "UNRESOLVED" ]; then
    hook_block "$RULE" \
      "could not resolve where this commit would land: $value -- refusing rather than guessing (agent-dotfiles#353). Name the directory literally (git -C <path> commit, or cd <path> && git commit)."
  fi
  target="$value"
  # The resolver emits a literal leading tilde for `cd ~` / `cd ~/x`; it is
  # expanded here, deliberately, not by the shell.
  # shellcheck disable=SC2088
  case "$target" in
    ".") target="$SESSION_CWD" ;;
    "~") target="$HOME" ;;
    "~/"*) target="$HOME/${target#\~/}" ;;
    /*) ;;
    *) target="$SESSION_CWD/$target" ;;
  esac
  if [ ! -d "$target" ]; then
    hook_block "$RULE" \
      "the directory this commit would land in does not exist ('$target'); a cd there would fail and the commit would land somewhere else -- refusing rather than guessing (agent-dotfiles#353)."
  fi
  BRANCH="$(git -C "$target" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  if [ -z "$BRANCH" ]; then
    # Not a git repo, or HEAD unreadable -- cannot establish the branch this
    # commit would land on. Fail closed rather than assume it is safe.
    hook_block "$RULE" \
      "could not determine the current branch in '$target' to confirm this commit is not landing on main -- refusing rather than guessing."
  fi
  # "HEAD" (detached) is not main -- rebases and tag checkouts detach
  # legitimately and are out of scope for this rule; only the named branch
  # main is blocked.
  if [ "$BRANCH" = "main" ]; then
    hook_block "$RULE" \
      "this would commit directly to 'main' (in '$target'). Branch with a type prefix (docs/, feat/, chore/, fix/, lane/NNN-...) and open a PR instead -- agent-supervisor/AGENTS.md, 'Conventions': 'never commit to main'."
  fi
done <<<"$TARGETS"

exit 0
