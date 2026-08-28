"""Tests for the remove/apply-remove cycle.

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


class RemoveTests(SyncTestCase):
    def test_remove_restores_settings_and_deletes_projection(self) -> None:
        (self.home / ".pi" / "agent").mkdir(parents=True)
        fragment = self.repo / "settings" / "claude" / "settings.json"
        fragment.write_text(json.dumps({"model": "opus"}))
        live = self.home / ".claude" / "settings.json"
        live.parent.mkdir(parents=True)
        live.write_text(json.dumps({"model": "sonnet", "theme": "dark"}))

        self.syncer.apply(no_apm=True)
        self.syncer.remove(no_apm=True)

        self.assertFalse((self.home / ".pi" / "agent" / "AGENTS.md").exists())
        restored = json.loads(live.read_text())
        self.assertEqual(restored, {"model": "sonnet", "theme": "dark"})

    def test_apply_twice_then_remove_is_clean(self) -> None:
        (self.home / ".pi" / "agent").mkdir(parents=True)
        self.syncer.apply(no_apm=True)
        first = (self.home / ".pi" / "agent" / "AGENTS.md").read_text()
        self.syncer.apply(no_apm=True)
        self.assertEqual(
            (self.home / ".pi" / "agent" / "AGENTS.md").read_text(), first
        )
        self.syncer.remove(no_apm=True)
        self.assertFalse((self.home / ".pi" / "agent" / "AGENTS.md").exists())
