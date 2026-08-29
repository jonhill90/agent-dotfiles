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

    def test_evidence_quoting_a_live_ledger_path_is_allowed(self) -> None:
        result = run_hook(
            self.SCRIPT,
            f'gh issue comment 99 --body "sqlite3 {self.LIVE_LEDGER}"',
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
