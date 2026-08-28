"""Tests for harness overlay projection into root instruction files.

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


class HarnessOverlayTests(SyncTestCase):
    """Per-harness instruction overlays existed only for Pi, so a sentence
    needed by one harness was billed to all four — E17's cost 48 tokens on
    every column when only Copilot failed the scenario (#85)."""

    def _overlay(self, name: str, body: str) -> None:
        d = self.repo / "instructions" / "overlays"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(body, encoding="utf-8")

    def _root(self, harness: str) -> Path:
        first = None
        for rel in sync.HARNESS_ROOT_FILES[harness]:
            path = self.home / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# canonical\n\ncore instructions\n", encoding="utf-8")
            first = first or path
        return first

    def test_overlay_is_appended_to_the_harness_root(self) -> None:
        root = self._root("copilot")
        self._overlay("copilot", "# Copilot Overlay\n\nagreement is not evidence.\n")
        sync.Sync(self.repo, self.home).apply_overlays()
        text = root.read_text(encoding="utf-8")
        self.assertIn("core instructions", text)
        self.assertIn("agreement is not evidence.", text)
        self.assertIn(sync.OVERLAY_BEGIN, text)

    def test_reapply_does_not_duplicate(self) -> None:
        root = self._root("copilot")
        self._overlay("copilot", "# Copilot Overlay\n\nonce.\n")
        for _ in range(3):
            sync.Sync(self.repo, self.home).apply_overlays()
        self.assertEqual(root.read_text(encoding="utf-8").count("once."), 1)

    def test_emptied_overlay_removes_the_block(self) -> None:
        root = self._root("copilot")
        self._overlay("copilot", "# Copilot Overlay\n\ntemporary.\n")
        sync.Sync(self.repo, self.home).apply_overlays()
        self._overlay("copilot", "# Copilot Overlay\n\nIntentionally empty.\n")
        sync.Sync(self.repo, self.home).apply_overlays()
        text = root.read_text(encoding="utf-8")
        self.assertNotIn("temporary.", text)
        self.assertNotIn(sync.OVERLAY_BEGIN, text)
        self.assertIn("core instructions", text)

    def test_placeholder_overlay_writes_nothing(self) -> None:
        """claude-code.md documents itself as intentionally empty; that must
        not produce a block."""
        root = self._root("claude")
        self._overlay("claude-code", "# Claude Code Overlay\n\nIntentionally empty. Native norms cover it.\n")
        sync.Sync(self.repo, self.home).apply_overlays()
        self.assertNotIn(sync.OVERLAY_BEGIN, root.read_text(encoding="utf-8"))

    def test_missing_harness_directory_is_skipped(self) -> None:
        self._overlay("copilot", "# Copilot Overlay\n\nsomething.\n")
        sync.Sync(self.repo, self.home).apply_overlays()  # must not raise

class OverlayBodyTests(SyncTestCase):
    """An overlay file documents why its rule exists; the harness should be
    charged only for the rule. The E17 overlay's rationale added ~45 tokens
    to Copilot's static context before comments were stripped (2026-07-27)."""

    def _write(self, body: str) -> None:
        d = self.repo / "instructions" / "overlays"
        d.mkdir(parents=True, exist_ok=True)
        (d / "copilot.md").write_text(body, encoding="utf-8")

    def test_html_comments_are_not_projected(self) -> None:
        self._write(
            "# Copilot Overlay\n\nThe rule.\n\n"
            "<!--\nWhy: measured on E17, Copilot only.\n-->\n"
        )
        body = sync.overlay_body(self.repo, "copilot")
        self.assertIn("The rule.", body)
        self.assertNotIn("Why:", body)
        self.assertNotIn("<!--", body)

    def test_an_overlay_that_is_only_a_comment_projects_nothing(self) -> None:
        self._write("# Copilot Overlay\n\n<!--\nNotes for maintainers.\n-->\n")
        self.assertEqual(sync.overlay_body(self.repo, "copilot"), "")

class CopilotBothInstructionFilesTests(SyncTestCase):
    """Copilot reads ~/.copilot/copilot-instructions.md, not AGENTS.md.

    The overlay was written to AGENTS.md alone on 2026-07-27 and was never in
    context: asked directly, a fresh Copilot answered "NO — my instructions
    don't contain a rule stating that agreement between dispatched agents
    isn't evidence", while quoting a rule that lives in the other file. Four
    eval runs referenced the policy zero times and nearly became a finding
    about delivery surfaces."""

    def test_overlay_reaches_every_file_the_harness_reads(self) -> None:
        d = self.repo / "instructions" / "overlays"
        d.mkdir(parents=True, exist_ok=True)
        (d / "copilot.md").write_text("# Copilot Overlay\n\nthe rule.\n", encoding="utf-8")
        copilot = self.home / ".copilot"
        copilot.mkdir(parents=True)
        for name in ("AGENTS.md", "copilot-instructions.md"):
            (copilot / name).write_text("core\n", encoding="utf-8")
        sync.Sync(self.repo, self.home).apply_overlays()
        for name in ("AGENTS.md", "copilot-instructions.md"):
            self.assertIn("the rule.", (copilot / name).read_text(encoding="utf-8"),
                          f"{name} missing the overlay")
