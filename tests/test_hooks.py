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
