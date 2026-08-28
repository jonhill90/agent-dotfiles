"""Tests for status/doctor reporting and apply ordering.

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


class StatusTests(SyncTestCase):
    def test_status_skips_uninstalled_harnesses(self) -> None:
        # no harness dirs exist in the fresh fake home
        self.assertEqual(self.syncer.status(), 0)

    def test_status_flags_missing_file_when_harness_present(self) -> None:
        (self.home / ".claude").mkdir()
        self.assertEqual(self.syncer.status(), 1)

class ApplyOrderTests(SyncTestCase):
    def test_apply_pins_the_default_skill_roster(self) -> None:
        calls = []

        def runner(cmd, check=False):
            calls.append(cmd)

            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        self.assertEqual(self.syncer.apply(), 0)
        self.assertEqual(
            calls[0],
            [
                "apm",
                "install",
                "-g",
                str(self.repo),
                "--skill",
                "github-cli",
                "--skill",
                "memory-conventions",
            ],
        )

    def test_apply_forces_marker_owned_roots_to_recompile(self) -> None:
        claude = self.home / ".claude" / "CLAUDE.md"
        claude.parent.mkdir(parents=True)
        claude.write_text(APM_MARKER + "\nstale rules\n")
        saw_missing_before_compile = False

        def runner(cmd, check=False):
            nonlocal saw_missing_before_compile
            if cmd[1] == "compile":
                saw_missing_before_compile = not claude.exists()
                claude.write_text(APM_MARKER + "\ncurrent rules\n")

            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        self.assertEqual(self.syncer.apply(), 0)
        self.assertTrue(saw_missing_before_compile)
        self.assertIn("current rules", claude.read_text())

    def test_apply_preserves_last_good_root_when_compile_skips_it(self) -> None:
        claude = self.home / ".claude" / "CLAUDE.md"
        claude.parent.mkdir(parents=True)
        original = APM_MARKER + "\nlast known good\n"
        claude.write_text(original)

        def runner(cmd, check=False):
            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        self.assertEqual(self.syncer.apply(), 0)
        self.assertEqual(claude.read_text(), original)

    def test_apply_runs_install_then_compile_then_teardown(self) -> None:
        calls = []
        home = self.home

        def runner(cmd, check=False):
            calls.append(cmd[1])
            if cmd[1] == "compile":
                stale = home / ".cursor" / "AGENTS.md"
                stale.parent.mkdir(parents=True, exist_ok=True)
                stale.write_text(APM_MARKER + "\ngenerated\n")

            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        self.assertEqual(self.syncer.apply(), 0)
        self.assertEqual(calls[:2], ["install", "compile"])
        # teardown must run AFTER compile: the stale root compile wrote is gone
        self.assertFalse((home / ".cursor" / "AGENTS.md").exists())

    def test_apply_aborts_when_compile_fails(self) -> None:
        calls = []
        claude = self.home / ".claude" / "CLAUDE.md"
        claude.parent.mkdir(parents=True)
        original = APM_MARKER + "\nlast known good\n"
        claude.write_text(original)

        def runner(cmd, check=False):
            calls.append(cmd[1])

            class R:
                returncode = 7 if cmd[1] == "compile" else 0

            return R()

        self.syncer.runner = runner
        self.assertEqual(self.syncer.apply(), 7)
        self.assertEqual(calls, ["install", "compile"])
        self.assertEqual(claude.read_text(), original)
        self.assertFalse(self.syncer.state_file.exists())

class DoctorTests(SyncTestCase):
    def test_flags_corporate_memory_vault(self) -> None:
        env = {
            "AGENT_MEMORY_VAULT": str(
                self.home / "Library/CloudStorage/OneDrive-Gentiva/vault"
            )
        }
        checks = dict(self.syncer.doctor_checks(env=env))
        self.assertFalse(checks["memory-vault-personal"][0])

    def test_accepts_personal_vault(self) -> None:
        vault = self.home / "Library/CloudStorage/OneDrive-Personal/vault"
        vault.mkdir(parents=True)
        env = {"AGENT_MEMORY_VAULT": str(vault)}
        checks = dict(self.syncer.doctor_checks(env=env))
        self.assertTrue(checks["memory-vault-personal"][0])

    def test_vault_set_but_missing_path_fails(self) -> None:
        env = {"AGENT_MEMORY_VAULT": str(self.home / "no-such-vault")}
        checks = dict(self.syncer.doctor_checks(env=env))
        ok, detail = checks["memory-vault-personal"]
        self.assertFalse(ok)
        self.assertIn("does not exist", detail)

    def test_accepts_existing_personal_vault_with_agent_dir(self) -> None:
        vault = self.home / "icloud" / "Agent Memory"
        (vault / "agent" / "facts").mkdir(parents=True)
        (vault / "agent" / "index.md").write_text("# idx\n")
        env = {"AGENT_MEMORY_VAULT": str(vault)}
        checks = dict(self.syncer.doctor_checks(env=env))
        self.assertTrue(checks["memory-vault-personal"][0])

    def test_missing_claude_harness_is_warning_not_failure(self) -> None:
        checks = dict(self.syncer.doctor_checks(env={}))
        ok, detail = checks["claude-root-file"]
        self.assertIsNone(ok)
        self.assertIn("not installed", detail)

    def test_codex_and_copilot_root_files_checked_when_installed(self) -> None:
        for harness in (".codex", ".copilot"):
            (self.home / harness).mkdir()
        checks = dict(self.syncer.doctor_checks(env={}))
        self.assertFalse(checks["codex-root-file"][0])  # dir, no root file
        self.assertFalse(checks["copilot-root-file"][0])
        (self.home / ".codex" / "AGENTS.md").write_text(APM_MARKER + "\nx\n")
        (self.home / ".copilot" / "AGENTS.md").write_text(APM_MARKER + "\nx\n")
        checks = dict(self.syncer.doctor_checks(env={}))
        self.assertTrue(checks["codex-root-file"][0])
        self.assertTrue(checks["copilot-root-file"][0])

    def test_codex_copilot_absent_is_warning(self) -> None:
        checks = dict(self.syncer.doctor_checks(env={}))
        self.assertIsNone(checks["codex-root-file"][0])
        self.assertIsNone(checks["copilot-root-file"][0])

    def test_unset_vault_is_warning_not_failure(self) -> None:
        checks = dict(self.syncer.doctor_checks(env={}))
        ok, detail = checks["memory-vault-personal"]
        self.assertIsNone(ok)  # None = warning
        self.assertIn("not set", detail)
