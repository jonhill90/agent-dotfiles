"""Tests for teardown of marker-owned unused root files.

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


class TeardownTests(SyncTestCase):
    def test_removes_only_marker_owned_unused_root_files(self) -> None:
        cursor = self.home / ".cursor" / "AGENTS.md"
        cursor.parent.mkdir(parents=True)
        cursor.write_text(APM_MARKER + "\ngenerated\n")
        gemini = self.home / ".gemini" / "GEMINI.md"
        gemini.parent.mkdir(parents=True)
        gemini.write_text("hand authored\n")
        claude = self.home / ".claude" / "CLAUDE.md"
        claude.parent.mkdir(parents=True)
        claude.write_text(APM_MARKER + "\ngenerated\n")

        removed = self.syncer.teardown_unused_root_files()

        self.assertFalse(cursor.exists())
        self.assertTrue(gemini.exists())  # no marker -> untouched
        self.assertTrue(claude.exists())  # managed harness -> kept
        self.assertIn(cursor, removed)
