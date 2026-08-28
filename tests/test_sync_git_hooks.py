"""Tests for git hook installation, doctor checks, and the real no-coauthor-trailer hook script.

Split out of the former tests/test_sync.py (2969 lines, agent-dotfiles#331).
Pure reorganisation -- no behaviour change.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sync  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_helpers import APM_MARKER, SyncTestCase, make_repo  # noqa: E402


class GitHooksInstallTests(SyncTestCase):
    """#275: the Co-Authored-By guard must be installed machine-global via
    core.hooksPath, not left as a per-repo hook that only this checkout
    sees -- otherwise a guard exists on one checkout out of however many
    the estate has."""

    def _hooks_path(self) -> str:
        env = {**os.environ, "HOME": str(self.home)}
        return subprocess.run(
            ["git", "config", "--global", "--get", "core.hooksPath"],
            env=env,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def test_install_copies_hook_and_sets_global_hookspath(self) -> None:
        ok, detail = self.syncer.install_git_hooks()

        self.assertTrue(ok, detail)
        target = self.home / ".git-hooks" / "commit-msg"
        self.assertTrue(target.is_file())
        self.assertTrue(target.stat().st_mode & 0o111, "hook must be executable")
        self.assertEqual(self._hooks_path(), str(self.home / ".git-hooks"))

    def test_install_is_idempotent(self) -> None:
        self.syncer.install_git_hooks()
        ok, detail = self.syncer.install_git_hooks()

        self.assertTrue(ok, detail)
        self.assertEqual(self._hooks_path(), str(self.home / ".git-hooks"))

    def test_install_does_not_clobber_existing_hookspath(self) -> None:
        env = {**os.environ, "HOME": str(self.home)}
        custom = self.home / "my-own-hooks"
        custom.mkdir()
        subprocess.run(
            ["git", "config", "--global", "core.hooksPath", str(custom)],
            env=env,
            check=True,
        )

        ok, detail = self.syncer.install_git_hooks()

        self.assertFalse(ok)
        self.assertIn(str(custom), detail)
        self.assertEqual(self._hooks_path(), str(custom))

    def test_apply_installs_hook(self) -> None:
        def runner(cmd, check=False):
            if cmd[0] == "apm":
                class R:
                    returncode = 0

                return R()
            return subprocess.run(
                cmd, check=check, env={**os.environ, "HOME": str(self.home)}
            )

        self.syncer.runner = runner
        code = self.syncer.apply()

        self.assertEqual(code, 0)
        self.assertTrue((self.home / ".git-hooks" / "commit-msg").is_file())
        self.assertEqual(self._hooks_path(), str(self.home / ".git-hooks"))

class GitHooksDoctorTests(SyncTestCase):
    def test_doctor_fails_when_hook_not_installed(self) -> None:
        checks = dict(self.syncer.doctor_checks(env={}))

        ok, detail = checks["no-coauthor-trailer-hook"]
        self.assertFalse(ok, detail)

    def test_doctor_passes_after_install(self) -> None:
        self.syncer.install_git_hooks()

        checks = dict(self.syncer.doctor_checks(env={}))

        ok, detail = checks["no-coauthor-trailer-hook"]
        self.assertTrue(ok, detail)

class CoAuthorTrailerHookRefusesCommitTests(unittest.TestCase):
    """Proves the actual production hook script (hooks/no-coauthor-trailer)
    refuses a real `git commit` carrying a Co-Authored-By trailer, and
    allows one without it -- run against the real script content, not a
    test double."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self._tmp.name) / "target-repo"
        self.repo_dir.mkdir()
        subprocess.run(
            ["git", "init", "-q"], cwd=self.repo_dir, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo_dir,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.repo_dir,
            check=True,
        )
        hook_source = (
            Path(__file__).resolve().parents[1] / "hooks" / "no-coauthor-trailer"
        )
        hooks_dir = self.repo_dir / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        target = hooks_dir / "commit-msg"
        target.write_bytes(hook_source.read_bytes())
        target.chmod(0o755)
        (self.repo_dir / "a.txt").write_text("hello\n")
        subprocess.run(["git", "add", "a.txt"], cwd=self.repo_dir, check=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_refuses_commit_with_coauthor_trailer(self) -> None:
        result = subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "feat: add file\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Co-Authored-By", result.stderr)
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(log.stdout.strip(), "")  # no commit was created

    def test_allows_commit_without_coauthor_trailer(self) -> None:
        result = subprocess.run(
            ["git", "commit", "-m", "feat: add file"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        self.assertIn("feat: add file", log.stdout)

    def test_case_insensitive_trailer_is_also_refused(self) -> None:
        result = subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "feat: add file\n\nco-authored-by: Claude <noreply@anthropic.com>\n",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
