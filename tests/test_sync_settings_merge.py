"""Tests for settings.json merge behaviour, including preservation of foreign/unmanaged entries.

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


class SettingsMergeTests(SyncTestCase):
    def test_merge_preserves_unmanaged_keys_and_records_previous(self) -> None:
        fragment = self.repo / "settings" / "claude" / "settings.json"
        fragment.write_text(json.dumps({"model": "opus", "env": {"FOO": "1"}}))
        live = self.home / ".claude" / "settings.json"
        live.parent.mkdir(parents=True)
        live.write_text(json.dumps({"model": "sonnet", "theme": "dark"}))

        self.syncer.merge_settings("claude", live)

        merged = json.loads(live.read_text())
        self.assertEqual(merged["model"], "opus")
        self.assertEqual(merged["theme"], "dark")  # unmanaged key preserved
        self.assertEqual(merged["env"], {"FOO": "1"})
        prev = self.syncer.state["settings"][str(live)]
        self.assertEqual(prev["model"], "sonnet")
        self.assertEqual(prev["env"], sync.ABSENT)

    def test_apply_merges_copilot_fragment_when_harness_present(self) -> None:
        (self.repo / "settings" / "copilot" / "settings.json").write_text(
            json.dumps({"model": "claude-sonnet-5"})
        )
        live = self.home / ".copilot" / "settings.json"
        live.parent.mkdir(parents=True)
        live.write_text(json.dumps({"model": "auto", "theme": "auto"}))
        self.syncer.apply(no_apm=True)
        merged = json.loads(live.read_text())
        self.assertEqual(merged["model"], "claude-sonnet-5")
        self.assertEqual(merged["theme"], "auto")

    def test_empty_fragment_is_noop(self) -> None:
        live = self.home / ".claude" / "settings.json"
        live.parent.mkdir(parents=True)
        live.write_text(json.dumps({"theme": "dark"}))
        self.syncer.merge_settings("claude", live)
        self.assertEqual(json.loads(live.read_text()), {"theme": "dark"})
        self.assertNotIn(str(live), self.syncer.state["settings"])

    def test_hook_commands_resolve_to_this_repos_absolute_path(self) -> None:
        # agent-dotfiles#276: the fragment is repo-relative and portable;
        # the live settings.json Claude Code actually invokes needs an
        # absolute path, since a hook fires from an arbitrary session cwd.
        fragment = self.repo / "settings" / "claude" / "settings.json"
        fragment.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [
                        {"type": "command", "command": "hooks/main-branch-guard.sh"},
                    ]},
                ],
            },
        }))
        live = self.home / ".claude" / "settings.json"
        live.parent.mkdir(parents=True)
        live.write_text("{}")

        self.syncer.merge_settings("claude", live)

        merged = json.loads(live.read_text())
        command = merged["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertEqual(command, str(self.repo / "hooks" / "main-branch-guard.sh"))

    def test_hook_merge_preserves_a_foreign_hook_and_withdraws_a_stale_one(
        self,
    ) -> None:
        # A hand-added hook the user (or another package) wrote must
        # survive `sync apply`, exactly like the top-level list-key
        # discipline this mirrors. And a hook this wrapper wrote in a
        # previous run, then stopped wanting, must be withdrawn rather than
        # accumulating forever (the same stale-`disabledSkills` defect this
        # file already exists to prevent, one level deeper).
        fragment = self.repo / "settings" / "claude" / "settings.json"
        theirs = {"type": "command", "command": "/opt/their-tool/check.sh"}
        ours_old = {"type": "command", "command": "hooks/old-guard.sh"}
        ours_new = {"type": "command", "command": "hooks/main-branch-guard.sh"}

        live = self.home / ".claude" / "settings.json"
        live.parent.mkdir(parents=True)

        # "theirs" is on disk already, never part of our fragment -- a hook
        # the user or another package wrote by hand.
        live.write_text(json.dumps({
            "hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [theirs]},
            ]},
        }))

        # First run: we ship old-guard.sh.
        fragment.write_text(json.dumps({
            "hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [ours_old]},
            ]},
        }))
        self.syncer.merge_settings("claude", live)
        after_first = json.loads(live.read_text())["hooks"]["PreToolUse"]
        self.assertIn({"matcher": "Bash", "hooks": [theirs]}, after_first)
        self.assertIn(
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": str(self.repo / "hooks" / "old-guard.sh")},
            ]},
            after_first,
        )

        # Second run: old-guard.sh is retired in favour of main-branch-guard.sh.
        fragment.write_text(json.dumps({
            "hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [ours_new]},
            ]},
        }))
        self.syncer.merge_settings("claude", live)
        after_second = json.loads(live.read_text())["hooks"]["PreToolUse"]

        self.assertIn({"matcher": "Bash", "hooks": [theirs]}, after_second)
        self.assertIn(
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": str(self.repo / "hooks" / "main-branch-guard.sh")},
            ]},
            after_second,
        )
        self.assertNotIn(
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": str(self.repo / "hooks" / "old-guard.sh")},
            ]},
            after_second,
        )

class ForeignSettingsEntryTests(SyncTestCase):
    """`deep_merge` recurses into dicts but replaces lists wholesale, so a
    list-valued managed key loses anything the wrapper did not write. Hit for
    real on 2026-07-29: removing a stale disable entry while its skill was
    still deployed made the skill load on four harnesses instead of two."""

    def _fragment(self, harness: str, body: dict) -> None:
        d = self.repo / "settings" / harness
        d.mkdir(parents=True, exist_ok=True)
        (d / "settings.json").write_text(json.dumps(body), encoding="utf-8")

    def test_apply_keeps_a_foreign_disabled_skill_entry(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[codex]\nsanity-check\n", encoding="utf-8"
        )
        live = self.home / ".copilot" / "settings.json"
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_text(
            json.dumps({"disabledSkills": ["vendor-thing"]}), encoding="utf-8"
        )
        self._fragment("copilot", {})
        sync.Sync(self.repo, self.home).merge_settings("copilot", live)
        entries = json.loads(live.read_text())["disabledSkills"]
        self.assertIn("vendor-thing", entries, "foreign entry was deleted")
        self.assertIn("sanity-check", entries, "derived entry missing")

    def test_remove_restores_foreign_entries_rather_than_dropping_the_key(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[codex]\nsanity-check\n", encoding="utf-8"
        )
        live = self.home / ".copilot" / "settings.json"
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_text(
            json.dumps({"disabledSkills": ["vendor-thing"]}), encoding="utf-8"
        )
        self._fragment("copilot", {})
        s = sync.Sync(self.repo, self.home)
        s.merge_settings("copilot", live)
        s.restore_settings(live)
        entries = json.loads(live.read_text()).get("disabledSkills", [])
        self.assertEqual(entries, ["vendor-thing"], "foreign entry not restored")
