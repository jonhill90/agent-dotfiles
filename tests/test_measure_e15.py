"""Tests for live static-context measurement (scripts/measure_e15.py)."""

from __future__ import annotations

import json
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
        write_skill(self.home / ".claude" / "skills", "github-cli", "m" * 100)
        write_skill(self.home / ".agents" / "skills", "github-cli", "m" * 100)
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


class SuppressedSkillTests(unittest.TestCase):
    """A skill on disk is not necessarily in the model's context. Claude Code
    turns one off with `skillOverrides` and Copilot with `disabledSkills`, both
    of which the wrapper writes from the roster. Charging the whole directory
    reported Claude Code and Copilot ~81 tokens heavy on 2026-07-27."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_claude_skill_overrides_are_not_charged(self) -> None:
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "settings.json").write_text(
            json.dumps({"skillOverrides": {"sanity-check": "off", "tmux": "on"}}),
            encoding="utf-8",
        )
        self.assertEqual(
            measure_e15.suppressed_skills(self.home, "claude"), {"sanity-check"}
        )

    def test_copilot_disabled_skills_are_not_charged(self) -> None:
        (self.home / ".copilot").mkdir(parents=True)
        (self.home / ".copilot" / "settings.json").write_text(
            json.dumps({"disabledSkills": ["sanity-check"]}), encoding="utf-8"
        )
        self.assertEqual(
            measure_e15.suppressed_skills(self.home, "copilot"), {"sanity-check"}
        )

    def test_absent_settings_suppress_nothing(self) -> None:
        self.assertEqual(measure_e15.suppressed_skills(self.home, "claude"), set())
        self.assertEqual(measure_e15.suppressed_skills(self.home, "pi"), set())


class CodexSuppressionTests(unittest.TestCase):
    """Codex's disable lives in TOML, not JSON, and suppressed_skills had no
    branch for it — so a skill the wrapper had disabled for Codex was still
    charged to Codex (#92)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.home / ".codex").mkdir(parents=True)

    def _config(self, body: str) -> None:
        (self.home / ".codex" / "config.toml").write_text(body, encoding="utf-8")

    def test_disabled_entries_are_suppressed(self) -> None:
        self._config(
            '[[skills.config]]\nname = "sanity-check"\nenabled = false\n\n'
            '[[skills.config]]\nname = "tmux"\nenabled = true\n'
        )
        self.assertEqual(
            measure_e15.suppressed_skills(self.home, "codex"), {"sanity-check"}
        )

    def test_absent_config_suppresses_nothing(self) -> None:
        self.assertEqual(measure_e15.suppressed_skills(self.home, "codex"), set())

    def test_malformed_toml_does_not_crash(self) -> None:
        self._config("[[skills.config\nname = broken")
        self.assertEqual(measure_e15.suppressed_skills(self.home, "codex"), set())


class BlindSpotTests(unittest.TestCase):
    """The measurement reads deployed files, so populations that never touch
    disk are invisible to it. Claude Code's bundled skills are ~1,758 tokens
    and were reported as zero for weeks. Silence is the defect; the report
    must name what it cannot see."""

    def test_blind_spots_are_named_with_their_last_measured_cost(self) -> None:
        spots = measure_e15.blind_spots("claude")
        self.assertTrue(spots, "claude has known unmeasured populations")
        joined = " ".join(s["population"] for s in spots)
        self.assertIn("bundled", joined)
        self.assertTrue(all(s["measured"] for s in spots), "each needs a date")

    def test_pi_has_none(self) -> None:
        self.assertEqual(measure_e15.blind_spots("pi"), [])
