"""Tests for hooks/*.sh -- the mechanical rules converted from prose to
blocking PreToolUse guards (agent-dotfiles#276).

Requirement 3 of that issue: a test per hook that breaks the guard and
watches it go red, AND attempts a legitimate near-miss and watches it be
allowed. Both are exercised here for every guard, plus the shared
fail-closed behaviour (an unparseable hook payload must never resolve to
"allowed").
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"
CLAUDE_SETTINGS_FRAGMENT = Path(__file__).resolve().parents[1] / "settings" / "claude" / "settings.json"


def run_hook(script: str, command: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = cwd
    return subprocess.run(
        ["bash", str(HOOKS_DIR / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def run_hook_raw(script: str, stdin_text: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HOOKS_DIR / script)],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


class FailClosedTests(unittest.TestCase):
    """Ambiguity must never resolve to allowed (agent-dotfiles#228, #230,
    #235 are all this same error, per the issue). Checked once against a
    representative guard rather than all six, since they share lib/common.sh."""

    def test_unparseable_payload_blocks(self) -> None:
        result = run_hook_raw("tmux-destructive-verb-guard.sh", "not json at all")
        self.assertEqual(result.returncode, 2)
        self.assertIn("could not parse", result.stderr)

    def test_empty_payload_blocks(self) -> None:
        result = run_hook_raw("gh-body-guard.sh", "")
        self.assertEqual(result.returncode, 2)


class TmuxDestructiveVerbGuardTests(unittest.TestCase):
    SCRIPT = "tmux-destructive-verb-guard.sh"

    def test_bare_kill_server_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "tmux kill-server")
        self.assertEqual(result.returncode, 2)
        self.assertIn("agent-supervisor#247", result.stderr)

    def test_bare_kill_session_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "tmux kill-session -t foo")
        self.assertEqual(result.returncode, 2)

    def test_tmux_tmpdir_without_unsetting_tmux_is_still_blocked(self) -> None:
        # Half the idiom is not the idiom -- TMUX would still resolve the
        # operator's inherited server.
        result = run_hook(self.SCRIPT, "TMUX_TMPDIR=$(mktemp -d) tmux kill-server")
        self.assertEqual(result.returncode, 2)

    def test_properly_scoped_kill_server_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            "TMUX_TMPDIR=$(mktemp -d) env -u TMUX tmux kill-server",
        )
        self.assertEqual(result.returncode, 0)

    def test_non_destructive_tmux_command_is_allowed(self) -> None:
        result = run_hook(self.SCRIPT, "tmux list-windows -a")
        self.assertEqual(result.returncode, 0)

    def test_unrelated_command_is_allowed(self) -> None:
        result = run_hook(self.SCRIPT, "ls -la")
        self.assertEqual(result.returncode, 0)

    def test_shell_comment_is_neither_a_use_nor_a_hiding_place(self) -> None:
        # lib/command_guard.py skips a word beginning with # to the end of
        # its line for every guard (agent-dotfiles#358). Both directions on
        # a second guard: a verb named in a comment is not a use, and a
        # comment after a real use does not hide it.
        allowed = run_hook(self.SCRIPT, "tmux list-windows -a # never tmux kill-server here")
        self.assertEqual(allowed.returncode, 0)
        blocked = run_hook(self.SCRIPT, "tmux kill-server # scoped by the caller")
        self.assertEqual(blocked.returncode, 2)

    def test_assignment_before_destructive_tmux_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, 'X="a" tmux kill-server')
        self.assertEqual(result.returncode, 2)

    def test_env_assignment_before_destructive_tmux_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "env VAR='x' tmux kill-server")
        self.assertEqual(result.returncode, 2)

    def test_backtick_substitution_before_destructive_tmux_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "echo `printf note`; tmux kill-server")
        self.assertEqual(result.returncode, 2)

    def test_quoted_heredoc_before_destructive_tmux_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT,
            "cat <<'EOF'\nproof: tmux kill-server\nEOF\ntmux kill-server",
        )
        self.assertEqual(result.returncode, 2)

    def test_and_separator_before_destructive_tmux_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "echo note && tmux kill-server")
        self.assertEqual(result.returncode, 2)

    def test_subshell_before_destructive_tmux_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "(tmux kill-server)")
        self.assertEqual(result.returncode, 2)

    def test_unquoted_heredoc_substitution_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "cat <<EOF\n$(tmux kill-server)\nEOF")
        self.assertEqual(result.returncode, 2)

    def test_double_quoted_substitution_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, 'echo "$(tmux kill-server)"')
        self.assertEqual(result.returncode, 2)

    def test_shell_wrapper_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, 'bash -c "tmux kill-server"')
        self.assertEqual(result.returncode, 2)

    def test_control_keyword_does_not_hide_destructive_tmux(self) -> None:
        result = run_hook(self.SCRIPT, "if true; then tmux kill-server; fi")
        self.assertEqual(result.returncode, 2)

    def test_misordered_isolation_tokens_are_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT,
            "tmux kill-server TMUX_TMPDIR=/tmp env -u TMUX",
        )
        self.assertEqual(result.returncode, 2)

    def test_evidence_quoting_a_destructive_verb_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'gh issue close 99 -c "the review found a tmux kill-server example"',
        )
        self.assertEqual(result.returncode, 0)


class TmuxProtectedTargetGuardTests(unittest.TestCase):
    SCRIPT = "tmux-protected-target-guard.sh"

    def test_targeting_the_supervisor_window_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "tmux send-keys -t agent-supervisor:1 'hi' Enter")
        self.assertEqual(result.returncode, 2)

    def test_targeting_the_hill90_session_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "tmux new-window -d -t =Hill90 -n qa-x")
        self.assertEqual(result.returncode, 2)

    def test_writing_the_real_tmux_conf_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "echo 'set -g mouse on' >> ~/.tmux.conf")
        self.assertEqual(result.returncode, 2)

    def test_reading_the_real_tmux_conf_is_allowed(self) -> None:
        # The danger is mutation, not inspection.
        result = run_hook(self.SCRIPT, "cat ~/.tmux.conf")
        self.assertEqual(result.returncode, 0)

    def test_targeting_a_lane_window_is_allowed(self) -> None:
        result = run_hook(self.SCRIPT, "tmux send-keys -t lane-42:1 'hi' Enter")
        self.assertEqual(result.returncode, 0)

    def test_quoted_prefix_does_not_hide_protected_target(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'echo "note"; tmux send-keys -t agent-supervisor:1 hi',
        )
        self.assertEqual(result.returncode, 2)

    def test_tmux_conf_in_quoted_issue_body_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'gh issue comment 99 --body "proof: echo x >> ~/.tmux.conf"',
        )
        self.assertEqual(result.returncode, 0)

    def test_variable_expanded_protected_target_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'target=Hill90; tmux kill-session -t "$target"',
        )
        self.assertEqual(result.returncode, 2)

    def test_evidence_naming_a_protected_target_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            "cat <<'EOF'\ntmux list-panes -t Hill90\nEOF\ngh issue create --body-file evidence.md",
        )
        self.assertEqual(result.returncode, 0)


class MainBranchGuardTests(unittest.TestCase):
    SCRIPT = "main-branch-guard.sh"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-q", "--allow-empty", "-m", "init"],
            check=True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_commit_on_main_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "git commit -m test", cwd=str(self.repo))
        self.assertEqual(result.returncode, 2)
        self.assertIn("main", result.stderr)

    def test_commit_on_a_feature_branch_is_allowed(self) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo), "checkout", "-q", "-b", "lane/1-test"],
            check=True,
        )
        result = run_hook(self.SCRIPT, "git commit -m test", cwd=str(self.repo))
        self.assertEqual(result.returncode, 0)

    def test_dry_run_on_main_is_allowed(self) -> None:
        result = run_hook(self.SCRIPT, "git commit --dry-run -m test", cwd=str(self.repo))
        self.assertEqual(result.returncode, 0)

    def test_unrelated_git_command_is_allowed(self) -> None:
        result = run_hook(self.SCRIPT, "git status", cwd=str(self.repo))
        self.assertEqual(result.returncode, 0)

    def test_quoted_prefix_does_not_hide_commit_on_main(self) -> None:
        result = run_hook(self.SCRIPT, 'echo "note"; git commit -m x', cwd=str(self.repo))
        self.assertEqual(result.returncode, 2)

    def test_shell_wrapper_does_not_hide_commit_on_main(self) -> None:
        result = run_hook(self.SCRIPT, 'bash -c "git commit -m bypass"', cwd=str(self.repo))
        self.assertEqual(result.returncode, 2)

    def test_evidence_quoting_a_commit_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            "cat <<'EOF'\ngit commit -m example\nEOF\ngh issue create --body-file evidence.md",
            cwd=str(self.repo),
        )
        self.assertEqual(result.returncode, 0)


class MainBranchGuardTargetTests(unittest.TestCase):
    """agent-dotfiles#353: the branch is resolved from where the write
    LANDS, not from where the session sits. Every test above keeps the
    payload cwd equal to the repository being committed to, which is
    exactly the shape that hid this. Here the session and the target are
    different directories: a checkout on main and a worktree of it on a
    feature branch -- the shape every lane in the estate works in, since
    protect-shared-checkout pushes each lane into a worktree."""

    SCRIPT = "main-branch-guard.sh"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.main_checkout = root / "checkout"
        self.worktree = root / "wt-feature"
        self.root = root
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.main_checkout)], check=True)
        subprocess.run(
            ["git", "-C", str(self.main_checkout), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-q", "--allow-empty", "-m", "init"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.main_checkout), "worktree", "add", "-q", "-b", "lane/353-test", str(self.worktree)],
            check=True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # Case B -- the event the guard exists to prevent: a write landing on
    # main, permitted because the session sits in a worktree.
    def test_case_b_commit_targeting_main_from_a_worktree_session_is_blocked(self) -> None:
        for command in (
            f"git -C {self.main_checkout} commit -m x",
            f"cd {self.main_checkout} && git commit -m x",
            f"cd {self.main_checkout}; git commit -m x",
        ):
            with self.subTest(command=command):
                result = run_hook(self.SCRIPT, command, cwd=str(self.worktree))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("main", result.stderr)

    # Case A -- the false block: a write landing on a feature worktree,
    # refused because the session sits on main. Must be allowed, and must
    # not be "fixed" by loosening Case B.
    def test_case_a_commit_targeting_a_feature_worktree_from_a_main_session_is_allowed(self) -> None:
        for command in (
            f"git -C {self.worktree} commit -m x",
            f"cd {self.worktree} && git commit -m x",
        ):
            with self.subTest(command=command):
                result = run_hook(self.SCRIPT, command, cwd=str(self.main_checkout))
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_target_in_a_compound_command_is_checked(self) -> None:
        command = f"git -C {self.worktree} commit -m a && git -C {self.main_checkout} commit -m b"
        result = run_hook(self.SCRIPT, command, cwd=str(self.worktree))
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_relative_paths_resolve_against_the_session_cwd(self) -> None:
        allowed = run_hook(self.SCRIPT, "cd wt-feature && git commit -m x", cwd=str(self.root))
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        blocked = run_hook(self.SCRIPT, "cd checkout && git commit -m x", cwd=str(self.root))
        self.assertEqual(blocked.returncode, 2, blocked.stderr)

    def test_cd_inside_a_subshell_does_not_move_the_target(self) -> None:
        # The subshell's cd is scoped to the subshell; the commit lands in
        # the session's cwd, which is main.
        command = f"(cd {self.worktree} && true) && git commit -m x"
        result = run_hook(self.SCRIPT, command, cwd=str(self.main_checkout))
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_cd_in_a_pipeline_does_not_move_the_target(self) -> None:
        command = f"cd {self.worktree} | cat; git commit -m x"
        result = run_hook(self.SCRIPT, command, cwd=str(self.main_checkout))
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_unresolvable_target_fails_closed(self) -> None:
        for command in (
            "cd $DIR && git commit -m x",
            "cd \"$(pwd)/elsewhere\" && git commit -m x",
            f"cd {self.worktree} || git commit -m x",
            "git -C $DIR commit -m x",
            f"pushd {self.worktree} && git commit -m x",
        ):
            with self.subTest(command=command):
                result = run_hook(self.SCRIPT, command, cwd=str(self.worktree))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("resolve", result.stderr)

    # Review on agent-dotfiles#354: `cd -` was NAMED as refused and was not --
    # `-` was stripped as a flag, so it resolved like bare `cd` (to $HOME). Its
    # real target is $OLDPWD, unknowable from the text. HOME is pointed at
    # the feature worktree so an accidental $HOME resolution would be allowed;
    # only a genuine refusal exits 2.
    def test_cd_dash_is_unresolvable_even_when_home_is_a_feature_branch(self) -> None:
        env = dict(os.environ)
        env["HOME"] = str(self.worktree)
        payload = {"tool_name": "Bash", "tool_input": {"command": "cd - && git commit -m x"}, "cwd": str(self.worktree)}
        result = subprocess.run(["bash", str(HOOKS_DIR / self.SCRIPT)], input=json.dumps(payload), capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("resolve", result.stderr)

    # `cd -- -` names a directory literally called "-"; it must be treated as
    # a path (here, a missing one, so refused for that reason), never as
    # bare `cd`.
    def test_cd_double_dash_dash_is_a_literal_path(self) -> None:
        env = dict(os.environ)
        env["HOME"] = str(self.worktree)
        payload = {"tool_name": "Bash", "tool_input": {"command": "cd -- - && git commit -m x"}, "cwd": str(self.worktree)}
        result = subprocess.run(["bash", str(HOOKS_DIR / self.SCRIPT)], input=json.dumps(payload), capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("does not exist", result.stderr)

    # Review on agent-dotfiles#354, audit of the other named limits:
    # --git-dir/--work-tree was refused only because the resolver returned no
    # target at all and the hook's fallback fired. Paired with a resolvable
    # commit in the same command, the fallback does not fire and the
    # --git-dir commit was silently dropped -- a false allow.
    def test_git_dir_commit_is_refused_by_name_even_beside_a_resolvable_commit(self) -> None:
        command = (
            f"git --git-dir={self.main_checkout}/.git --work-tree={self.main_checkout} commit -m x"
            f" && git -C {self.worktree} commit -m y"
        )
        result = run_hook(self.SCRIPT, command, cwd=str(self.worktree))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("git-dir", result.stderr)
        alone = run_hook(self.SCRIPT, f"git --work-tree {self.main_checkout} commit -m x", cwd=str(self.worktree))
        self.assertEqual(alone.returncode, 2, alone.stderr)
        self.assertIn("work-tree", alone.stderr)

    def test_cd_to_a_missing_directory_fails_closed(self) -> None:
        # `cd missing; git commit` would fail the cd and commit in the
        # session cwd; refusing is the only safe answer.
        result = run_hook(self.SCRIPT, "cd does-not-exist; git commit -m x", cwd=str(self.worktree))
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_dry_run_targeting_main_is_allowed(self) -> None:
        result = run_hook(self.SCRIPT, f"git -C {self.main_checkout} commit --dry-run -m x", cwd=str(self.worktree))
        self.assertEqual(result.returncode, 0, result.stderr)

    # Third defect: an UNQUOTED heredoc body quoting a commit is a mention,
    # not a use -- the quoted-delimiter case above already passes.
    def test_unquoted_heredoc_quoting_a_commit_is_a_mention(self) -> None:
        command = "gh issue create --title t --body-file - <<EOF\nReproduction:\ngit commit -m example\nBLOCKED by main-branch-guard\nEOF\n"
        result = run_hook(self.SCRIPT, command, cwd=str(self.main_checkout))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unquoted_heredoc_substitution_running_a_commit_is_still_caught(self) -> None:
        command = "cat <<EOF\nresult: $(git commit -m x)\nEOF\n"
        result = run_hook(self.SCRIPT, command, cwd=str(self.main_checkout))
        self.assertEqual(result.returncode, 2, result.stderr)


class GhBodyGuardTests(unittest.TestCase):
    SCRIPT = "gh-body-guard.sh"

    def test_body_file_flag_on_gh_api_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT, "gh api repos/o/r/issues/1/comments --body-file file.md"
        )
        self.assertEqual(result.returncode, 2)

    def test_at_file_on_dash_f_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT, "gh api repos/o/r/issues/1/comments -f body=@file.md"
        )
        self.assertEqual(result.returncode, 2)

    def test_the_safe_form_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'gh api repos/o/r/issues/1/comments -f body="$(cat file.md)"',
        )
        self.assertEqual(result.returncode, 0)

    def test_gh_pr_create_with_body_file_is_out_of_scope(self) -> None:
        # --body-file is a real, supported flag on gh pr create/gh issue
        # comment -- only gh api lacks it. Scoping the guard to `gh api`
        # keeps this legitimate call from being a false positive.
        result = run_hook(
            self.SCRIPT, "gh pr create --title x --body-file file.md"
        )
        self.assertEqual(result.returncode, 0)

    def test_evidence_quoting_a_bad_gh_api_flag_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'printf "%s" "echo evidence; gh api --body-file evidence.md"',
        )
        self.assertEqual(result.returncode, 0)

    # agent-dotfiles#356 measured the deployed regex guard against this
    # file's first command_guard.py version and found the rewrite traded one
    # real fix for two new defects; #358 is the use-versus-mention shape.
    # Each test below was run against origin/main before the fix (the PR
    # carries both runs) and holds in both directions: what the guard
    # exists to block still blocks.

    def test_body_file_equals_form_on_gh_api_is_blocked(self) -> None:
        # #356 defect 1: --body-file=x is one token, and an exact-token test
        # for "--body-file" let it through -- the deployed regex caught it.
        result = run_hook(
            self.SCRIPT, "gh api repos/o/r/issues/1/comments --body-file=file.md"
        )
        self.assertEqual(result.returncode, 2)

    def test_every_raw_field_spelling_of_at_file_is_blocked(self) -> None:
        # The -f body=@file footgun in the other spellings gh accepts for
        # the same flag. The quoted form is the one the deployed regex
        # missed (#356); the long and attached forms both versions missed.
        # -f=x and -if=x are pflag's shorthand spellings: it strips the =
        # and groups -i (boolean) before -f. Both reached gh as a raw
        # body=@file and were a false allow in this fix's first draft.
        for command in (
            "gh api repos/o/r/issues/1/comments --raw-field body=@file.md",
            "gh api repos/o/r/issues/1/comments --raw-field=body=@file.md",
            "gh api repos/o/r/issues/1/comments -fbody=@file.md",
            "gh api repos/o/r/issues/1/comments -f=body=@file.md",
            "gh api repos/o/r/issues/1/comments -if=body=@file.md",
            "gh api repos/o/r/issues/1/comments -if body=@file.md",
            'gh api repos/o/r/issues/1/comments -f "body=@file.md"',
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook(self.SCRIPT, command).returncode, 2)

    def test_typed_field_at_file_is_allowed(self) -> None:
        # #356 defect 2: -F/--field is the typed form gh DOES read from a
        # file -- the guard's own header names it as the one that works.
        # Flagging any body=@ token regardless of its flag blocked it.
        for command in (
            "gh api repos/o/r/issues/1/comments -F body=@file.md",
            "gh api repos/o/r/issues/1/comments -F=body=@file.md",
            "gh api repos/o/r/issues/1/comments -iF body=@file.md",
            "gh api repos/o/r/issues/1/comments --field body=@file.md",
            "gh api repos/o/r/issues/1/comments --field=body=@file.md",
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook(self.SCRIPT, command).returncode, 0)

    def test_typed_field_does_not_launder_a_raw_at_file_beside_it(self) -> None:
        # Mutation check on the -F fix: consuming -F's value must not hide a
        # real -f body=@file elsewhere in the same call, nor a bare body=@
        # token no flag owns (gh api could only ever reject that one).
        for command in (
            "gh api repos/o/r/issues/1/comments -F title=@t.md -f body=@file.md",
            "gh api repos/o/r/issues/1/comments -X POST body=@file.md",
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook(self.SCRIPT, command).returncode, 2)

    def test_flag_named_inside_a_quoted_body_is_allowed(self) -> None:
        # #358's shape: editing a comment whose body advises readers to
        # expand a file into -f body=. Every trigger is named, none used.
        result = run_hook(
            self.SCRIPT,
            'gh api -X PATCH repos/o/r/issues/comments/1 -f body="Expand the'
            " file into -f body= with cat; never --body-file, and never"
            ' -f body=@file, which sends the literal text."',
        )
        self.assertEqual(result.returncode, 0)

    def test_flag_named_in_a_trailing_comment_is_allowed(self) -> None:
        # #358, the shape origin/main still got wrong: a shell comment never
        # executes, but the tokenizer read its words as arguments of the
        # command before it, so a flag NAMED there was a flag USED.
        result = run_hook(
            self.SCRIPT,
            'gh api repos/o/r/issues/1/comments -f body="$(cat file.md)"'
            " # gh api has no --body-file flag, so the file is expanded",
        )
        self.assertEqual(result.returncode, 0)

    def test_a_comment_does_not_hide_a_real_use(self) -> None:
        # Mutation check on the comment fix, each way it could over-reach:
        # a real use earlier on the same line is still seen, and a # that
        # is not at a word start (mid-word, quoted) is not a comment.
        for command in (
            "gh api repos/o/r/issues/1/comments --body-file file.md # documented",
            "gh api repos/o/r/issues/1/comments -f body=@file#1.md",
            'gh api repos/o/r/issues/1/comments "#" -f body=@file.md',
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook(self.SCRIPT, command).returncode, 2)


class LaneSelfCloseGuardTests(unittest.TestCase):
    SCRIPT = "lane-self-close-guard.sh"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-q", "--allow-empty", "-m", "init"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "checkout", "-q", "-b", "lane/276-rules-to-hooks"],
            check=True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_closing_the_dispatching_issue_is_blocked(self) -> None:
        result = run_hook(self.SCRIPT, "gh issue close 276", cwd=str(self.repo))
        self.assertEqual(result.returncode, 2)

    def test_closing_the_dispatching_issue_via_rest_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT,
            "gh api repos/o/r/issues/276 -X PATCH -f state=closed",
            cwd=str(self.repo),
        )
        self.assertEqual(result.returncode, 2)

    def test_closing_an_unrelated_issue_is_allowed(self) -> None:
        result = run_hook(self.SCRIPT, "gh issue close 99", cwd=str(self.repo))
        self.assertEqual(result.returncode, 0)

    def test_branch_with_no_issue_number_is_out_of_scope(self) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo), "checkout", "-q", "-b", "chore/cleanup"],
            check=True,
        )
        result = run_hook(self.SCRIPT, "gh issue close 276", cwd=str(self.repo))
        self.assertEqual(result.returncode, 0)

    def test_quoted_prefix_does_not_hide_self_close(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'echo "note"; gh issue close 276',
            cwd=str(self.repo),
        )
        self.assertEqual(result.returncode, 2)

    def test_evidence_quoting_an_issue_close_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'printf "%s" "echo evidence; gh issue close 276"',
            cwd=str(self.repo),
        )
        self.assertEqual(result.returncode, 0)


class LedgerWriteGuardTests(unittest.TestCase):
    SCRIPT = "ledger-write-guard.sh"
    LIVE_LEDGER = "~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3"

    def test_ad_hoc_write_to_the_live_ledger_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT, f'sqlite3 {self.LIVE_LEDGER} "insert into tasks values (1)"'
        )
        self.assertEqual(result.returncode, 2)

    def test_readonly_open_of_the_live_ledger_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT, f'sqlite3 -readonly {self.LIVE_LEDGER} "select * from tasks"'
        )
        self.assertEqual(result.returncode, 0)

    def test_a_test_fixture_ledger_copy_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT, 'sqlite3 /tmp/test-fixture/ledger.sqlite3 "insert into tasks values (1)"'
        )
        self.assertEqual(result.returncode, 0)

    def test_writing_through_cli_py_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            f'python3 scripts/supervisor/cli.py claim --lane t:1 --ledger {self.LIVE_LEDGER}',
        )
        self.assertEqual(result.returncode, 0)

    def test_quoted_prefix_does_not_hide_live_ledger_write(self) -> None:
        result = run_hook(
            self.SCRIPT,
            f'echo "note"; sqlite3 {self.LIVE_LEDGER} "insert into tasks values (1)"',
        )
        self.assertEqual(result.returncode, 2)

    def test_variable_expanded_live_ledger_write_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT,
            f'db="{self.LIVE_LEDGER}"; sqlite3 "$db" "DELETE FROM tasks"',
        )
        self.assertEqual(result.returncode, 2)

    def test_evidence_quoting_a_live_ledger_path_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            f'gh issue comment 99 --body "sqlite3 {self.LIVE_LEDGER}"',
        )
        self.assertEqual(result.returncode, 0)

    # LIVE_CORPUS coverage (agent-estate#P6): a second, separate durable
    # record this same guard protects. Corpus protection had already
    # silently lapsed in this file's own #277 rewrite (never carried over
    # from the earlier, never-merged a3f6e09 revision) -- these are the
    # first tests to exist for it at all, covering both the real filename
    # and the compat symlink #P6 renamed the old one into.
    LIVE_CORPUS_REAL = "~/corpus/corpus.sqlite3"
    LIVE_CORPUS_SYMLINK = "~/corpus/ledger.sqlite3"

    def test_ad_hoc_write_to_the_live_corpus_real_name_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT, f'sqlite3 {self.LIVE_CORPUS_REAL} "insert into items values (1)"'
        )
        self.assertEqual(result.returncode, 2)

    def test_ad_hoc_write_to_the_live_corpus_symlink_name_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT, f'sqlite3 {self.LIVE_CORPUS_SYMLINK} "insert into items values (1)"'
        )
        self.assertEqual(result.returncode, 2)

    def test_readonly_open_of_the_live_corpus_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT, f'sqlite3 -readonly {self.LIVE_CORPUS_REAL} "select * from items"'
        )
        self.assertEqual(result.returncode, 0)

    def test_mode_ro_uri_open_of_the_live_corpus_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            f'sqlite3 "file:{self.LIVE_CORPUS_REAL}?mode=ro&immutable=1" "select * from items"',
        )
        self.assertEqual(result.returncode, 0)

    def test_a_test_fixture_corpus_copy_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT, 'sqlite3 /tmp/test-fixture/corpus.sqlite3 "insert into items values (1)"'
        )
        self.assertEqual(result.returncode, 0)


class ExecutableResolutionTests(unittest.TestCase):
    """agent-dotfiles#360: executable() compared the program token literally
    and unwrapped only env/command/exec/nohup bare, so `/usr/bin/git commit`
    and `sudo git commit` reached main through the live guard, and the same
    shape reached every rule. Each closed form below was run against
    origin/main's hooks first and failed there (the PR carries both runs);
    each guard's own block/allow split is re-checked through the same
    resolver so a fix for one hook cannot silently move another."""

    MAIN = "main-branch-guard.sh"
    KEYCHAIN = "keychain-write-guard.sh"
    TMUX = "tmux-destructive-verb-guard.sh"
    GH_BODY = "gh-body-guard.sh"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-q", "--allow-empty", "-m", "init"],
            check=True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def main_guard(self, command: str) -> int:
        return run_hook(self.MAIN, command, cwd=str(self.repo)).returncode

    def test_path_spellings_of_git_commit_on_main_are_blocked(self) -> None:
        # The program is its basename: a path only ever makes a rule apply,
        # never exempts it.
        for command in (
            "/usr/bin/git commit -m x",
            "./git commit -m x",
            "~/bin/git commit -m x",
            "/opt/homebrew/bin/git -C . commit -m x",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.main_guard(command), 2)

    def test_sudo_spellings_of_git_commit_on_main_are_blocked(self) -> None:
        # sudo's own option grammar is consumed: a value-taking option
        # (-u, --user) in its spaced, attached, grouped and = forms, a bare
        # --, VAR=value before the command, a path or a second prefix after.
        for command in (
            "sudo git commit -m x",
            "sudo -u root git commit -m x",
            "sudo -Eu root git commit -m x",
            "sudo -uroot git commit -m x",
            "sudo --user=root git commit -m x",
            "sudo --user root -E git commit -m x",
            "sudo -E -u root -- git commit -m x",
            "sudo -n -D /tmp git commit -m x",
            "sudo VAR=1 git commit -m x",
            "sudo /usr/bin/git commit -m x",
            "sudo sudo git commit -m x",
            "sudo -s git commit -m x",
            "sudo env -i git commit -m x",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.main_guard(command), 2)

    def test_other_prefix_programs_consume_their_own_options(self) -> None:
        # env -C takes a value; command -p and exec -a used to leave the
        # option itself as the program, so the rule never saw git.
        for command in (
            "env -C /tmp git commit -m x",
            "env -i -u HOME git commit -m x",
            "command -p git commit -m x",
            "exec -a x git commit -m x",
            "nohup git commit -m x",
            "/bin/bash -c 'git commit -m x'",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.main_guard(command), 2)

    def test_redirection_before_the_command_name_does_not_hide_it(self) -> None:
        # bash accepts a redirection anywhere in a simple command, including
        # before the name; the operator used to be read as the program.
        for command in (
            ">/tmp/log git commit -m x",
            "2>/dev/null git commit -m x",
            "</dev/null sudo -u root git commit -m x",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.main_guard(command), 2)

    def test_program_named_by_an_expansion_is_refused_with_its_own_reason(self) -> None:
        # Not resolved, refused: the text cannot say what $(which git) or
        # "$GIT" runs. The reason names the shape so the fix is obvious.
        for command in (
            "$(which git) commit -m x",
            '"$GIT" commit -m x',
            "$HOME/bin/git status",
            "`which git` status",
        ):
            with self.subTest(command=command):
                result = run_hook(self.MAIN, command, cwd=str(self.repo))
                self.assertEqual(result.returncode, 2)
                self.assertIn("named by an expansion", result.stderr)

    def test_one_unplaceable_clause_refuses_the_whole_line_on_every_guard(self) -> None:
        # The #362 review's own payload: a variable-named setup step chained
        # to a legitimate feature-branch commit. Refused by every guard,
        # including the ones whose subject is not in the line, and the
        # refusal names the token and says so -- this is the disclosed
        # blast radius, pinned rather than narrowed (agent-dotfiles#362).
        subprocess.run(["git", "-C", str(self.repo), "checkout", "-q", "-b", "feat/x"], check=True)
        command = "PYTHON=$(command -v python3); \"$PYTHON\" -c 'print(1)' && git commit --allow-empty -m x"
        for hook in (self.MAIN, self.GH_BODY, self.KEYCHAIN, self.TMUX):
            with self.subTest(hook=hook):
                result = run_hook(hook, command, cwd=str(self.repo))
                self.assertEqual(result.returncode, 2)
                self.assertIn("'$PYTHON'", result.stderr)
                self.assertIn("whole line on every guard", result.stderr)
        # Split into its own call, the same commit is allowed again.
        self.assertEqual(self.main_guard("git commit --allow-empty -m x"), 0)

    def test_sudo_h_host_is_refused_in_every_spelling(self) -> None:
        # sudo -h HOST (--host) takes its value attached OR as the next
        # non-dash argument, per sudo's own parse_args; #362 read -h as
        # plain, so the spaced form left the host as the program and the
        # guard never saw git. Under sudoers a remote host runs nothing,
        # so a value is refused rather than read past (#362 review).
        for command in (
            "sudo -h fakehost.example.com git commit -m x",
            "sudo -hfakehost.example.com git commit -m x",
            "sudo -l -h fakehost.example.com git commit -m x",
            "sudo -nh fakehost.example.com git commit -m x",
        ):
            with self.subTest(command=command):
                result = run_hook(self.MAIN, command, cwd=str(self.repo))
                self.assertEqual(result.returncode, 2)
                self.assertIn("remote host", result.stderr)

    def test_bare_sudo_h_is_help_and_runs_nothing(self) -> None:
        # No value follows -h: it is --help. Nothing runs, nothing to refuse.
        for command in ("sudo -h", "sudo --help", "sudo -h -- git status"):
            with self.subTest(command=command):
                self.assertEqual(self.main_guard(command), 0)

    def test_unmodelled_prefix_grammar_is_refused(self) -> None:
        # env -S re-splits its string into a command line; sudo has no -Z.
        # Neither is guessed at.
        for command in (
            "env -S 'git commit -m x'",
            "sudo -Z git commit -m x",
            "sudo --nonsense git commit -m x",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.main_guard(command), 2)

    def test_already_caught_alias_bypass_idioms_stay_caught(self) -> None:
        # Pins, not fixes: the tokenizer already dequoted these.
        for command in ("\\git commit -m x", '"git" commit -m x'):
            with self.subTest(command=command):
                self.assertEqual(self.main_guard(command), 2)

    def test_prefixed_commands_that_do_not_commit_stay_allowed(self) -> None:
        for command in (
            "sudo git status",
            "sudo -u root ls -la",
            "sudo -k",
            "sudo --version",
            "/usr/bin/git status",
            "/usr/bin/git commit --dry-run -m x",
            "env -C /tmp git status",
            "sudo -u root env FOO=1 git log -1",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.main_guard(command), 0)

    def test_commit_target_is_resolved_through_sudo_and_paths(self) -> None:
        # main-targets shares executable(): a prefixed commit still names
        # the directory it lands in, so a feature worktree stays allowed.
        subprocess.run(["git", "-C", str(self.repo), "checkout", "-q", "-b", "feat/x"], check=True)
        for command in ("sudo git commit -m x", "/usr/bin/git commit -m x", "sudo -u root git -C . commit -m x"):
            with self.subTest(command=command):
                self.assertEqual(self.main_guard(command), 0)

    def test_keychain_write_through_sudo_or_a_path_is_blocked(self) -> None:
        # Described, not exercised: only the guard script reads the payload.
        for command in (
            "sudo security add-generic-password -s service -a account -w secret",
            "sudo -u root security add-generic-password -s service -a account -w secret",
            "/usr/bin/security add-generic-password -s service -a account -w secret",
        ):
            with self.subTest(command=command):
                result = run_hook(self.KEYCHAIN, command)
                self.assertEqual(result.returncode, 2)
                self.assertIn("credential-store-read-only", result.stderr)

    def test_keychain_read_through_a_path_stays_allowed(self) -> None:
        result = run_hook(self.KEYCHAIN, "/usr/bin/security find-generic-password -s service -a account")
        self.assertEqual(result.returncode, 0)

    def test_tmux_destructive_verb_through_a_path_or_sudo_is_blocked(self) -> None:
        for command in ("/usr/bin/tmux kill-server", "sudo tmux kill-server"):
            with self.subTest(command=command):
                self.assertEqual(run_hook(self.TMUX, command).returncode, 2)

    def test_tmux_isolation_prefix_is_read_positionally(self) -> None:
        # The scoping check reads what precedes the program token, so a
        # path spelling keeps the isolation idiom intact rather than
        # crashing on a literal "tmux" lookup.
        allowed = run_hook(self.TMUX, "TMUX_TMPDIR=$(mktemp -d) env -u TMUX /usr/bin/tmux kill-server")
        self.assertEqual(allowed.returncode, 0)
        blocked = run_hook(self.TMUX, "/usr/bin/tmux kill-server TMUX_TMPDIR=/tmp env -u TMUX")
        self.assertEqual(blocked.returncode, 2)

    def test_gh_body_grammar_holds_through_a_path_or_sudo(self) -> None:
        blocked = run_hook(self.GH_BODY, "/usr/bin/gh api repos/o/r/issues/1/comments -f body=@file.md")
        self.assertEqual(blocked.returncode, 2)
        allowed = run_hook(self.GH_BODY, "sudo gh api repos/o/r/issues/1/comments -F body=@file.md")
        self.assertEqual(allowed.returncode, 0)


class KeychainWriteGuardTests(unittest.TestCase):
    SCRIPT = "keychain-write-guard.sh"

    def test_guard_is_declared_in_the_claude_settings_fragment(self) -> None:
        settings = json.loads(CLAUDE_SETTINGS_FRAGMENT.read_text())
        hooks = settings["hooks"]["PreToolUse"][0]["hooks"]
        self.assertIn(
            {"type": "command", "command": "hooks/keychain-write-guard.sh"},
            hooks,
        )

    def test_real_probe_shape_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT,
            "security add-generic-password -s estate-probe-write-1427 -a probe -w secret",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("credential-store-read-only", result.stderr)

    def test_executed_write_after_a_command_separator_is_blocked(self) -> None:
        result = run_hook(
            self.SCRIPT,
            "echo checking; security add-generic-password -s service -a account -w secret",
        )
        self.assertEqual(result.returncode, 2)

    def test_generic_password_write_verbs_are_blocked_with_any_flags(self) -> None:
        for command in (
            "security add-generic-password -a account -s service -A -U -w secret",
            "security delete-generic-password -a account -s service",
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook(self.SCRIPT, command).returncode, 2)

    def test_other_confirmed_keychain_mutators_are_blocked(self) -> None:
        for command in (
            "security set-keychain-settings -l login.keychain-db",
            "security add-internet-password -a account -s example.test -w secret",
            "security set-generic-password-partition-list -a account -s service -S apple:",
            "security delete-internet-password -a account -s example.test",
            "security set-key-partition-list -S apple:",
            "security default-keychain -s login.keychain-db",
            "security list-keychains -s login.keychain-db",
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook(self.SCRIPT, command).returncode, 2)

    def test_plain_text_mention_in_issue_comment_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'gh issue comment 665 --body "The keychain guard must refuse security add-generic-password -U -A, but this comment only describes the bug."',
        )
        self.assertEqual(result.returncode, 0)

    def test_plain_text_mention_in_commit_message_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            'git commit -m "Document why security delete-generic-password is forbidden"',
        )
        self.assertEqual(result.returncode, 0)

    def test_leading_global_flag_does_not_bypass_the_guard(self) -> None:
        # security's own man page is `security [-hilqv] [-p prompt] [command]
        # ...` -- a single leading global flag must not slip the subcommand
        # past position-0 detection (agent-dotfiles#344).
        for command in (
            "security -v add-generic-password -s estate-probe-write-1427 -a probe -w probevalue",
            "security -h add-generic-password -s estate-probe-write-1427 -a probe -w probevalue",
            "security -i add-generic-password -s estate-probe-write-1427 -a probe -w probevalue",
            "security -l add-generic-password -s estate-probe-write-1427 -a probe -w probevalue",
            "security -q add-generic-password -s estate-probe-write-1427 -a probe -w probevalue",
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook(self.SCRIPT, command).returncode, 2)

    def test_leading_dash_p_prompt_argument_does_not_bypass_the_guard(self) -> None:
        # `-p prompt` takes an argument -- a naive "skip anything starting
        # with -" would consume `prompt` and then misread the following
        # token as the subcommand instead of skipping both.
        result = run_hook(
            self.SCRIPT,
            "security -p prompt add-generic-password -s estate-probe-write-1427 -a probe -w probevalue",
        )
        self.assertEqual(result.returncode, 2)

    def test_read_only_keychain_commands_are_allowed(self) -> None:
        for command in (
            "security find-generic-password -w -s service -a account",
            "security show-keychain-info login.keychain-db",
            "security list-keychains",
            "security default-keychain",
        ):
            with self.subTest(command=command):
                self.assertEqual(run_hook(self.SCRIPT, command).returncode, 0)

    def test_read_only_keychain_command_with_leading_global_flag_is_allowed(self) -> None:
        # A leading global flag must not falsely trip the guard on a
        # legitimate read either -- the fix must skip the flag, not treat
        # its presence as evidence of a write.
        result = run_hook(self.SCRIPT, "security -v find-generic-password -s service -a account")
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
