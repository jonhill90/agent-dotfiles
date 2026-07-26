"""Tests for live static-context measurement (scripts/measure_e15.py)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import measure_e15  # noqa: E402


def write_skill(directory: Path, name: str, description: str) -> None:
    skill = directory / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


class MeasureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "CLAUDE.md").write_text("x" * 400, encoding="utf-8")
        write_skill(self.home / ".claude" / "skills", "gh-cli", "m" * 100)
        write_skill(self.home / ".agents" / "skills", "gh-cli", "m" * 100)
        # plugin tree mirrors the real layout:
        # plugins/cache/<marketplace>/<plugin>/<version>/skills/<name>/SKILL.md
        self.plugins = self.home / ".claude" / "plugins" / "cache" / "market"
        write_skill(self.plugins / "frontend-design" / "v1" / "skills",
                    "frontend-design", "p" * 200)
        write_skill(self.plugins / "superpowers" / "v5" / "skills",
                    "brainstorming", "s" * 800)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_plugin_skill_bytes_counts_only_enabled_plugins(self) -> None:
        total, names = measure_e15.plugin_skill_bytes(
            self.home / ".claude" / "plugins", {"frontend-design"}
        )
        self.assertEqual(names, ["frontend-design"])
        self.assertEqual(total, 200)

    def test_disabled_plugin_costs_nothing(self) -> None:
        total, names = measure_e15.plugin_skill_bytes(
            self.home / ".claude" / "plugins", set()
        )
        self.assertEqual((total, names), (0, []))

    def test_cached_but_unenabled_plugin_is_excluded(self) -> None:
        total, _ = measure_e15.plugin_skill_bytes(
            self.home / ".claude" / "plugins", {"frontend-design"}
        )
        self.assertNotIn(800, [total], "superpowers is cached but not enabled")

    def test_enabled_plugins_parses_the_settings_fragment(self) -> None:
        self.assertEqual(
            measure_e15.enabled_plugins(
                {"enabledPlugins": {"a@market": True, "b@market": False}}
            ),
            {"a"},
        )

    def test_claude_total_includes_enabled_plugin_skills(self) -> None:
        report = measure_e15.measure(
            self.home, enabled={"frontend-design"}, memory_index=None
        )
        claude = report["claude"]
        self.assertEqual(claude["plugin_skills"], 200 / 4)
        self.assertAlmostEqual(
            claude["total"],
            claude["instructions"] + claude["skills"] + claude["plugin_skills"],
        )

    def test_neutral_harnesses_are_not_charged_for_claude_plugins(self) -> None:
        report = measure_e15.measure(
            self.home, enabled={"frontend-design"}, memory_index=None
        )
        self.assertEqual(report["pi"]["plugin_skills"], 0)


class PluginSourceTests(unittest.TestCase):
    """Two ways the plugin scan under-counts or double-counts."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "plugins"
        # installed copy
        write_skill(self.root / "cache" / "market" / "fd" / "v1" / "skills",
                    "fd-skill", "i" * 100)
        # marketplace catalog copy of the SAME plugin — must not be counted
        write_skill(self.root / "marketplaces" / "market" / "plugins" / "fd" / "skills",
                    "fd-skill", "i" * 100)
        # a plugin that ships commands rather than skills
        cmds = self.root / "cache" / "market" / "rl" / "v1" / "commands"
        cmds.mkdir(parents=True)
        (cmds / "go.md").write_text(
            '---\ndescription: "' + "c" * 60 + '"\n---\n\nbody\n', encoding="utf-8"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_marketplace_catalog_is_not_counted(self) -> None:
        total, names = measure_e15.plugin_skill_bytes(self.root, {"fd"})
        self.assertEqual(names, ["fd"])
        self.assertEqual(total, 100, "catalog copy must not double-count")

    def test_plugin_commands_count_as_skills(self) -> None:
        total, names = measure_e15.plugin_skill_bytes(self.root, {"rl"})
        self.assertEqual(names, ["rl"])
        self.assertEqual(total, 60, "commands are merged into skills by Claude Code")
