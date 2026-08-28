"""Tests for skill source backup, restore, and rollback-on-failure exception safety.

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


class SkillSourceBackupTests(SyncTestCase):
    """scripts/sync.py's snapshot/restore around `apm install -g` (#9): a
    failed public or private skill-source fetch must not leave the
    previously deployed skill set partially overwritten.
    """

    def test_backup_skills_dirs_snapshots_existing_content(self) -> None:
        agents_skill = self.home / ".agents" / "skills" / "tmux" / "SKILL.md"
        agents_skill.parent.mkdir(parents=True)
        agents_skill.write_text("original agents tmux content\n")
        claude_skill = self.home / ".claude" / "skills" / "tmux" / "SKILL.md"
        claude_skill.parent.mkdir(parents=True)
        claude_skill.write_text("original claude tmux content\n")

        backups = self.syncer.backup_skills_dirs()

        self.assertEqual(
            set(backups), {self.home / ".agents" / "skills", self.home / ".claude" / "skills"}
        )
        for live, backup in backups.items():
            self.assertTrue(backup.is_dir())
            self.assertNotEqual(live, backup)
            self.assertFalse(live.exists())  # renamed aside, not copied

    def test_backup_skills_dirs_noop_when_nothing_deployed_yet(self) -> None:
        self.assertEqual(self.syncer.backup_skills_dirs(), {})

    def test_restore_skills_dirs_replaces_a_partial_write_with_the_backup(self) -> None:
        agents_dir = self.home / ".agents" / "skills"
        (agents_dir / "tmux").mkdir(parents=True)
        (agents_dir / "tmux" / "SKILL.md").write_text("last-good\n")

        backups = self.syncer.backup_skills_dirs()
        # simulate a partial/bad write left behind by a failed install
        agents_dir.mkdir(parents=True)
        (agents_dir / "partial-write.txt").write_text("garbage\n")

        self.syncer.restore_skills_dirs(backups)

        self.assertFalse((agents_dir / "partial-write.txt").exists())
        self.assertEqual(
            (agents_dir / "tmux" / "SKILL.md").read_text(), "last-good\n"
        )

    def test_discard_skills_backup_removes_the_snapshot(self) -> None:
        agents_dir = self.home / ".agents" / "skills"
        (agents_dir / "tmux").mkdir(parents=True)
        (agents_dir / "tmux" / "SKILL.md").write_text("content\n")
        backups = self.syncer.backup_skills_dirs()

        self.syncer.discard_skills_backup(backups)

        for backup in backups.values():
            self.assertFalse(backup.exists())

class SkillBackupConflictTests(SyncTestCase):
    """A `.bak` left by an interrupted prior apply is the only
    last-known-good copy that exists. backup_skills_dirs() must never
    overwrite or delete it -- it must fail closed instead (#9 review)."""

    def test_never_deletes_an_existing_bak(self) -> None:
        agents_dir = self.home / ".agents" / "skills"
        (agents_dir / "tmux").mkdir(parents=True)
        (agents_dir / "tmux" / "SKILL.md").write_text("current\n")
        stale_backup = self.home / ".agents" / "skills.bak"
        (stale_backup / "tmux").mkdir(parents=True)
        (stale_backup / "tmux" / "SKILL.md").write_text("last-known-good\n")

        with self.assertRaises(sync.SkillBackupConflict):
            self.syncer.backup_skills_dirs()

        # the only last-known-good copy must survive untouched
        self.assertEqual(
            (stale_backup / "tmux" / "SKILL.md").read_text(), "last-known-good\n"
        )
        # and the live dir must not have been renamed away either
        self.assertEqual(
            (agents_dir / "tmux" / "SKILL.md").read_text(), "current\n"
        )

    def test_undoes_a_partial_rename_before_raising(self) -> None:
        # .claude/skills has no stale backup and renames cleanly first;
        # .agents/skills DOES have one. The .claude rename must be undone
        # rather than left half-applied when the whole call fails.
        claude_dir = self.home / ".claude" / "skills"
        (claude_dir / "tmux").mkdir(parents=True)
        (claude_dir / "tmux" / "SKILL.md").write_text("claude-current\n")
        agents_dir = self.home / ".agents" / "skills"
        agents_dir.mkdir(parents=True)
        (self.home / ".agents" / "skills.bak").mkdir(parents=True)

        with self.assertRaises(sync.SkillBackupConflict):
            self.syncer.backup_skills_dirs()

        self.assertTrue(claude_dir.is_dir())
        self.assertEqual(
            (claude_dir / "tmux" / "SKILL.md").read_text(), "claude-current\n"
        )
        self.assertFalse((self.home / ".claude" / "skills.bak").exists())

    def test_apply_fails_closed_without_running_apm(self) -> None:
        agents_dir = self.home / ".agents" / "skills"
        (agents_dir / "tmux").mkdir(parents=True)
        (agents_dir / "tmux" / "SKILL.md").write_text("current\n")
        stale_backup = self.home / ".agents" / "skills.bak"
        (stale_backup / "tmux").mkdir(parents=True)
        (stale_backup / "tmux" / "SKILL.md").write_text("last-known-good\n")

        def runner(cmd, check=False):
            raise AssertionError("apm must not run while a backup is unresolved")

        self.syncer.runner = runner
        rc = self.syncer.apply()

        self.assertNotEqual(rc, 0)
        self.assertEqual(
            (agents_dir / "tmux" / "SKILL.md").read_text(), "current\n"
        )
        self.assertEqual(
            (stale_backup / "tmux" / "SKILL.md").read_text(), "last-known-good\n"
        )

    def test_recover_skills_backup_restores_last_known_good(self) -> None:
        agents_dir = self.home / ".agents" / "skills"
        (agents_dir / "tmux").mkdir(parents=True)
        (agents_dir / "tmux" / "SKILL.md").write_text("broken-partial\n")
        stale_backup = self.home / ".agents" / "skills.bak"
        (stale_backup / "tmux").mkdir(parents=True)
        (stale_backup / "tmux" / "SKILL.md").write_text("last-known-good\n")

        rc = self.syncer.recover_skills_backup()

        self.assertEqual(rc, 0)
        self.assertFalse(stale_backup.exists())
        self.assertEqual(
            (agents_dir / "tmux" / "SKILL.md").read_text(), "last-known-good\n"
        )

    def test_recover_skills_backup_is_a_noop_without_one(self) -> None:
        self.assertEqual(self.syncer.recover_skills_backup(), 0)

    def test_doctor_flags_an_unresolved_skill_backup(self) -> None:
        stale_backup = self.home / ".agents" / "skills.bak"
        stale_backup.mkdir(parents=True)
        checks = dict(self.syncer.doctor_checks(env={}))
        self.assertIn("skill-backup-conflict", checks)
        ok, message = checks["skill-backup-conflict"]
        self.assertFalse(ok)
        self.assertIn(str(stale_backup), message)

    def test_doctor_is_silent_without_a_stale_backup(self) -> None:
        checks = dict(self.syncer.doctor_checks(env={}))
        ok, _ = checks["skill-backup-conflict"]
        self.assertTrue(ok)

class ApplyInstallFailureRollbackTests(SyncTestCase):
    def test_apply_restores_prior_skills_on_install_failure(self) -> None:
        agents_dir = self.home / ".agents" / "skills"
        (agents_dir / "tmux").mkdir(parents=True)
        (agents_dir / "tmux" / "SKILL.md").write_text("last-good\n")

        def runner(cmd, check=False):
            if cmd[1] == "install":
                # simulate a partial write left by the source that failed
                agents_dir.mkdir(parents=True, exist_ok=True)
                (agents_dir / "partial-write.txt").write_text("garbage\n")

            class R:
                returncode = 9 if cmd[1] == "install" else 0

            return R()

        self.syncer.runner = runner
        self.assertEqual(self.syncer.apply(), 9)
        self.assertFalse((agents_dir / "partial-write.txt").exists())
        self.assertEqual(
            (agents_dir / "tmux" / "SKILL.md").read_text(), "last-good\n"
        )
        self.assertFalse(self.syncer.state_file.exists())

    def test_apply_discards_backup_after_successful_install(self) -> None:
        agents_dir = self.home / ".agents" / "skills"
        (agents_dir / "tmux").mkdir(parents=True)
        (agents_dir / "tmux" / "SKILL.md").write_text("last-good\n")

        def runner(cmd, check=False):
            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        self.assertEqual(self.syncer.apply(), 0)
        leftovers = [
            p for p in (self.home / ".agents").iterdir() if p.name != "skills"
        ]
        self.assertEqual(leftovers, [])

class ApplyExceptionSafetyTests(SyncTestCase):
    """launching apm can raise before returning any process result at all
    (binary missing, permissions, OS error) -- not just return nonzero.
    apply() must restore on every exception, not only a bad returncode
    (#9 review)."""

    def test_restores_skills_if_install_raises(self) -> None:
        agents_dir = self.home / ".agents" / "skills"
        (agents_dir / "tmux").mkdir(parents=True)
        (agents_dir / "tmux" / "SKILL.md").write_text("last-good\n")

        def runner(cmd, check=False):
            if cmd[1] == "install":
                raise FileNotFoundError("apm binary vanished mid-run")

            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        rc = self.syncer.apply()

        self.assertNotEqual(rc, 0)
        self.assertEqual(
            (agents_dir / "tmux" / "SKILL.md").read_text(), "last-good\n"
        )
        self.assertFalse((self.home / ".agents" / "skills.bak").exists())

    def test_restores_root_files_if_compile_raises(self) -> None:
        claude = self.home / ".claude" / "CLAUDE.md"
        claude.parent.mkdir(parents=True)
        original = APM_MARKER + "\nlast known good\n"
        claude.write_text(original)

        def runner(cmd, check=False):
            if cmd[1] == "compile":
                raise RuntimeError("compile crashed mid-run")

            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        rc = self.syncer.apply()

        self.assertNotEqual(rc, 0)
        self.assertEqual(claude.read_text(), original)

    def test_install_exception_does_not_reach_the_caller(self) -> None:
        # A raised exception must become a reported failure, not propagate
        # past apply() -- the caller (a cron job, a CLI invocation) needs a
        # return code, not a crash mid-deployment.
        def runner(cmd, check=False):
            if cmd[1] == "install":
                raise OSError("network unreachable")

            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        try:
            rc = self.syncer.apply()
        except Exception as exc:  # pragma: no cover - the assertion below fails first
            self.fail(f"apply() propagated {exc!r} instead of returning a code")
        self.assertIsInstance(rc, int)
        self.assertNotEqual(rc, 0)

    def test_compile_failure_return_code_still_restores_skills(self) -> None:
        # compile failing after a successful install must not re-touch the
        # already-committed skill set -- the skill backup was already
        # discarded by then, and compile failure is a root-file concern.
        agents_dir = self.home / ".agents" / "skills"
        (agents_dir / "tmux").mkdir(parents=True)
        (agents_dir / "tmux" / "SKILL.md").write_text("last-good\n")

        def runner(cmd, check=False):
            if cmd[1] == "install":
                # a real successful install repopulates the directory;
                # the fake must too, or the assertion below tests nothing
                agents_dir.mkdir(parents=True, exist_ok=True)
                (agents_dir / "tmux").mkdir(exist_ok=True)
                (agents_dir / "tmux" / "SKILL.md").write_text("last-good\n")

            class R:
                returncode = 5 if cmd[1] == "compile" else 0

            return R()

        self.syncer.runner = runner
        rc = self.syncer.apply()

        self.assertEqual(rc, 5)
        self.assertEqual(
            (agents_dir / "tmux" / "SKILL.md").read_text(), "last-good\n"
        )
        self.assertFalse((self.home / ".agents" / "skills.bak").exists())
