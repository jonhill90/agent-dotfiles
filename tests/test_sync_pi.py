"""Tests for the pi harness projection and its skill denylist.

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


class PiProjectionTests(SyncTestCase):
    def test_initializes_pi_dir_when_binary_on_path(self) -> None:
        self.syncer.pi_available = lambda: True
        self.syncer.project_pi()
        out = self.home / ".pi" / "agent" / "AGENTS.md"
        self.assertTrue(out.is_file())

    def test_apply_creates_neutral_skills_dir(self) -> None:
        self.syncer.apply(no_apm=True)
        self.assertTrue((self.home / ".agents" / "skills").is_dir())

    def test_apply_mirrors_claude_skills_into_empty_neutral_path(self) -> None:
        src = self.home / ".claude" / "skills" / "github-cli"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("---\nname: github-cli\n---\nbody\n")
        self.syncer.apply(no_apm=True)
        mirrored = self.home / ".agents" / "skills" / "github-cli"
        self.assertTrue(mirrored.is_symlink() or mirrored.is_dir())
        self.assertTrue((mirrored / "SKILL.md").is_file())

    def test_projects_core_plus_overlay_when_pi_present(self) -> None:
        (self.home / ".pi" / "agent").mkdir(parents=True)
        self.syncer.project_pi()
        out = (self.home / ".pi" / "agent" / "AGENTS.md").read_text()
        self.assertIn(sync.SYNC_MARKER, out)
        self.assertIn("core rules", out)
        self.assertIn("pi rules", out)
        self.assertNotIn("description: test", out)  # frontmatter stripped

    def test_skipped_when_pi_absent(self) -> None:
        self.syncer.pi_available = lambda: False
        self.syncer.project_pi()
        self.assertFalse((self.home / ".pi" / "agent" / "AGENTS.md").exists())

    def test_refuses_to_overwrite_hand_authored_file(self) -> None:
        target = self.home / ".pi" / "agent" / "AGENTS.md"
        target.parent.mkdir(parents=True)
        target.write_text("my own pi instructions\n")
        self.syncer.project_pi()
        self.assertEqual(target.read_text(), "my own pi instructions\n")

class PiSkillDenylistTests(SyncTestCase):
    """Pi's Tier B lever is a `skills` denylist in ~/.pi/agent/settings.json,
    whose entries are paths: `-skills/<name>/SKILL.md`."""

    def test_excluded_skills_become_denylist_paths(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[codex]\nsanity-check\n", encoding="utf-8"
        )
        self.assertEqual(
            sync.pi_disabled_skills(self.repo), ["-skills/sanity-check/SKILL.md"]
        )

    def test_pi_scoped_skills_are_not_denied(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[pi]\nsanity-check\n", encoding="utf-8"
        )
        self.assertEqual(sync.pi_disabled_skills(self.repo), [])
