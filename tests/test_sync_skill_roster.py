"""Tests for per-harness skill roster scoping, overrides, and modifiers.

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


class SkillRosterScopingTests(SyncTestCase):
    """SPEC §4.1 — per-harness roster sections, Tier A neutral scoping."""

    SECTIONED = (
        "# shared roster (all harnesses)\n"
        "github-cli\n"
        "memory-conventions\n"
        "\n"
        "[copilot]\n"
        "safe-deletion\n"
        "\n"
        "[codex]\n"
        "tmux\n"
    )

    def write_roster(self, text: str) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            text, encoding="utf-8"
        )

    def test_flat_roster_stays_valid_and_is_shared_by_every_harness(self) -> None:
        self.write_roster("github-cli\nmemory-conventions\n")
        shared = sync.load_default_skills(self.repo)
        self.assertEqual(shared, ["github-cli", "memory-conventions"])
        for harness in ("claude", "pi", "codex", "copilot"):
            self.assertEqual(
                sync.load_default_skills(self.repo, harness), shared
            )

    def test_named_harness_gets_shared_plus_its_section(self) -> None:
        self.write_roster(self.SECTIONED)
        self.assertEqual(
            sync.load_default_skills(self.repo),
            ["github-cli", "memory-conventions"],
        )
        self.assertEqual(
            sync.load_default_skills(self.repo, "copilot"),
            ["github-cli", "memory-conventions", "safe-deletion"],
        )
        self.assertEqual(
            sync.load_default_skills(self.repo, "codex"),
            ["github-cli", "memory-conventions", "tmux"],
        )
        self.assertEqual(
            sync.load_default_skills(self.repo, "claude"),
            ["github-cli", "memory-conventions"],
        )

    def test_union_covers_every_section_for_apm_install(self) -> None:
        self.write_roster(self.SECTIONED)
        self.assertEqual(
            sync.roster_union(self.repo),
            ["github-cli", "memory-conventions", "safe-deletion", "tmux"],
        )

    def test_neutral_union_excludes_claude_only_skills(self) -> None:
        self.write_roster(self.SECTIONED + "\n[claude]\nprimer\n")
        self.assertEqual(
            sync.neutral_union(self.repo),
            ["github-cli", "memory-conventions", "safe-deletion", "tmux"],
        )

    # -- Tier A mirroring ------------------------------------------------

    def seed_claude_skills(self, *names: str) -> Path:
        claude = self.home / ".claude" / "skills"
        claude.mkdir(parents=True, exist_ok=True)
        for name in names:
            (claude / name).mkdir(exist_ok=True)
        return claude

    def test_mirrors_only_the_neutral_union(self) -> None:
        self.write_roster(self.SECTIONED + "\n[claude]\nprimer\n")
        self.seed_claude_skills(
            "github-cli", "memory-conventions", "safe-deletion", "tmux", "primer"
        )
        self.syncer.ensure_neutral_skills()
        neutral = self.home / ".agents" / "skills"
        self.assertEqual(
            sorted(p.name for p in neutral.iterdir()),
            ["github-cli", "memory-conventions", "safe-deletion", "tmux"],
        )
        self.assertFalse((neutral / "primer").exists())

    def test_removing_from_a_section_removes_the_wrapper_symlink(self) -> None:
        self.write_roster(self.SECTIONED)
        self.seed_claude_skills(
            "github-cli", "memory-conventions", "safe-deletion", "tmux"
        )
        self.syncer.ensure_neutral_skills()
        neutral = self.home / ".agents" / "skills"
        self.assertTrue((neutral / "safe-deletion").is_symlink())

        # drop the [copilot] section entirely
        self.write_roster("github-cli\nmemory-conventions\n\n[codex]\ntmux\n")
        self.syncer.ensure_neutral_skills()
        self.assertFalse((neutral / "safe-deletion").exists())
        self.assertTrue((neutral / "tmux").is_symlink())

    def test_never_removes_a_link_the_wrapper_did_not_create(self) -> None:
        self.write_roster("github-cli\n")
        self.seed_claude_skills("github-cli", "hand-made")
        neutral = self.home / ".agents" / "skills"
        neutral.mkdir(parents=True, exist_ok=True)
        (neutral / "hand-made").symlink_to(self.home / ".claude" / "skills" / "hand-made")
        self.syncer.ensure_neutral_skills()
        self.assertTrue(
            (neutral / "hand-made").exists(),
            "unmanaged links must survive — removal is state-tracked",
        )

    def test_removal_is_recorded_in_state_and_reversible(self) -> None:
        self.write_roster(self.SECTIONED)
        self.seed_claude_skills(
            "github-cli", "memory-conventions", "safe-deletion", "tmux"
        )
        self.syncer.ensure_neutral_skills()
        self.assertIn(
            "safe-deletion", self.syncer.state.get("neutral_skills", [])
        )
        self.write_roster("github-cli\nmemory-conventions\n\n[codex]\ntmux\n")
        self.syncer.ensure_neutral_skills()
        self.assertNotIn(
            "safe-deletion", self.syncer.state.get("neutral_skills", [])
        )
        # restoring the section restores the link
        self.write_roster(self.SECTIONED)
        self.syncer.ensure_neutral_skills()
        self.assertTrue(
            (self.home / ".agents" / "skills" / "safe-deletion").is_symlink()
        )

class RosterReportingTests(SyncTestCase):
    """SPEC §4.1 — status reports resolved rosters; doctor flags drift."""

    def setUp(self) -> None:
        super().setUp()
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[copilot]\nsafe-deletion\n", encoding="utf-8"
        )

    def test_resolved_rosters_are_reported(self) -> None:
        report = self.syncer.roster_report()
        self.assertEqual(report["claude"], ["github-cli"])
        self.assertEqual(report["copilot"], ["github-cli", "safe-deletion"])
        self.assertEqual(report["pi"], ["github-cli"])

    def test_doctor_flags_neutral_path_drift(self) -> None:
        claude = self.home / ".claude" / "skills"
        claude.mkdir(parents=True)
        (claude / "github-cli").mkdir()
        neutral = self.home / ".agents" / "skills"
        neutral.mkdir(parents=True)
        # a link the wrapper recorded, for a skill no longer in any roster
        (neutral / "stale-skill").symlink_to(claude / "github-cli")
        self.syncer.state["neutral_skills"] = ["stale-skill"]
        names = dict(self.syncer.doctor_checks({}))
        self.assertIn("neutral-roster-drift", names)
        self.assertFalse(names["neutral-roster-drift"][0])

    def test_doctor_passes_when_neutral_path_matches(self) -> None:
        claude = self.home / ".claude" / "skills"
        claude.mkdir(parents=True)
        for name in ("github-cli", "safe-deletion"):
            (claude / name).mkdir()
        self.syncer.ensure_neutral_skills()
        names = dict(self.syncer.doctor_checks({}))
        self.assertNotEqual(names["neutral-roster-drift"][0], False)

class PreexistingNeutralLinkTests(SyncTestCase):
    """Links from the pre-§4.1 wholesale mirroring are untracked, so they
    cannot be auto-removed — doctor must surface them instead of leaving a
    scoped skill silently readable on the shared path."""

    def test_untracked_out_of_union_link_is_reported_not_deleted(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[claude]\nprimer\n", encoding="utf-8"
        )
        claude = self.home / ".claude" / "skills"
        claude.mkdir(parents=True)
        for name in ("github-cli", "primer"):
            (claude / name).mkdir()
        neutral = self.home / ".agents" / "skills"
        neutral.mkdir(parents=True)
        # what the old wholesale mirror left behind
        (neutral / "primer").symlink_to(claude / "primer")

        self.syncer.ensure_neutral_skills()
        self.assertTrue(
            (neutral / "primer").exists(), "untracked links are never deleted"
        )
        names = dict(self.syncer.doctor_checks({}))
        check = names["neutral-roster-drift"]
        self.assertFalse(check[0])
        self.assertIn("primer", check[1])

class ClaudeSkillOverrideTests(SyncTestCase):
    """APM installs the union into ~/.claude/skills, so a skill scoped away
    from Claude Code still reaches it. V9 resolved the Tier B lever
    (`skillOverrides`); the wrapper derives it from the roster so the two
    cannot drift."""

    def test_skills_excluded_from_claude_are_turned_off(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[codex]\nsanity-check\n\n[pi]\nsanity-check\n", encoding="utf-8"
        )
        self.assertEqual(sync.claude_skill_overrides(self.repo), {"sanity-check": "off"})

    def test_flat_roster_produces_no_overrides(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\nmemory-conventions\n", encoding="utf-8"
        )
        self.assertEqual(sync.claude_skill_overrides(self.repo), {})

    def test_claude_scoped_skills_are_not_turned_off(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[claude]\nprimer\n", encoding="utf-8"
        )
        self.assertEqual(sync.claude_skill_overrides(self.repo), {})

class NameOnlyRosterTests(SyncTestCase):
    """`name-only` is the third roster state SPEC §4.1 names and #96 asked
    for: keep the skill invocable, stop paying for its description. It is a
    modifier on membership, not an exclusion — so a `@name-only` skill stays
    in the resolved roster and is still deployed."""

    def roster(self, text: str) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(text, encoding="utf-8")

    def test_modifier_is_stripped_from_the_resolved_roster(self) -> None:
        self.roster("github-cli\nobsidian @name-only\n")
        self.assertEqual(
            sync.load_default_skills(self.repo), ["github-cli", "obsidian"]
        )

    def test_name_only_skill_is_still_installed(self) -> None:
        """The whole point: it stays deployed and invocable."""
        self.roster("github-cli\nobsidian @name-only\n")
        self.assertIn("obsidian", sync.roster_union(self.repo))
        self.assertIn("obsidian", sync.neutral_union(self.repo))

    def test_override_is_name_only_not_off(self) -> None:
        self.roster("github-cli\nobsidian @name-only\n")
        self.assertEqual(
            sync.claude_skill_overrides(self.repo), {"obsidian": "name-only"}
        )

    def test_name_only_and_off_coexist(self) -> None:
        """A skill scoped away from Claude is still `off`; the modifier only
        changes skills Claude keeps."""
        self.roster("github-cli\nobsidian @name-only\n\n[codex]\nsanity-check\n")
        self.assertEqual(
            sync.claude_skill_overrides(self.repo),
            {"obsidian": "name-only", "sanity-check": "off"},
        )

    def test_modifier_applies_inside_a_harness_section(self) -> None:
        self.roster("github-cli\n\n[claude]\nprimer @name-only\n")
        self.assertEqual(
            sync.claude_skill_overrides(self.repo), {"primer": "name-only"}
        )

    def test_unknown_modifier_is_refused_rather_than_ignored(self) -> None:
        """Silently dropping an unrecognised modifier would deploy a roster
        that does not match what the file asks for."""
        self.roster("github-cli\nobsidian @nmae-only\n")
        with self.assertRaises(ValueError) as caught:
            sync.load_skill_roster(self.repo)
        self.assertIn("@nmae-only", str(caught.exception))

    def test_skill_modifiers_reports_only_annotated_skills(self) -> None:
        self.roster("github-cli\nobsidian @name-only\n")
        self.assertEqual(sync.skill_modifiers(self.repo), {"obsidian": "name-only"})

class CopilotDisabledSkillsTests(SyncTestCase):
    """Copilot reads the shared ~/.agents/skills directory, so a skill scoped
    to Codex and Pi reaches Copilot too. V10 resolved affirmatively on
    2026-07-27 — `disabledSkills` in ~/.copilot/settings.json, verified live —
    and it is derived from the roster for the same reason Claude Code's is."""

    def test_skills_excluded_from_copilot_are_disabled(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[codex]\nsanity-check\n\n[pi]\nsanity-check\n", encoding="utf-8"
        )
        self.assertEqual(sync.copilot_disabled_skills(self.repo), ["sanity-check"])

    def test_flat_roster_disables_nothing(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\nmemory-conventions\n", encoding="utf-8"
        )
        self.assertEqual(sync.copilot_disabled_skills(self.repo), [])

    def test_copilot_scoped_skills_are_not_disabled(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[copilot]\nsanity-check\n", encoding="utf-8"
        )
        self.assertEqual(sync.copilot_disabled_skills(self.repo), [])

class CodexSkillDisableTests(SyncTestCase):
    """Codex's Tier B lever is `[[skills.config]]` with `enabled = false` in
    ~/.codex/config.toml, keyed by the bare skill name for personal skills
    (plugin skills are namespaced, e.g. `github:yeet`). Verified live on
    2026-07-27: a fresh `codex exec` stopped listing the disabled skill."""

    def test_excluded_skills_render_as_disabled_entries(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[pi]\nsanity-check\n", encoding="utf-8"
        )
        self.assertEqual(sync.codex_disabled_skills(self.repo), ["sanity-check"])

    def test_codex_scoped_skills_are_not_disabled(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[codex]\nsanity-check\n", encoding="utf-8"
        )
        self.assertEqual(sync.codex_disabled_skills(self.repo), [])

    def test_block_is_written_and_leaves_foreign_entries_alone(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[pi]\nsanity-check\n", encoding="utf-8"
        )
        codex = self.home / ".codex"
        codex.mkdir(parents=True, exist_ok=True)
        config = codex / "config.toml"
        config.write_text(
            '[[skills.config]]\nname = "github:yeet"\nenabled = false\n',
            encoding="utf-8",
        )
        sync.Sync(self.repo, self.home).merge_codex_skills()
        text = config.read_text(encoding="utf-8")
        self.assertIn('name = "sanity-check"', text)
        self.assertIn('name = "github:yeet"', text)  # user's own entry survives
        self.assertIn(sync.CODEX_SKILLS_BEGIN, text)

    def test_block_is_removed_when_nothing_is_excluded(self) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n\n[pi]\nsanity-check\n", encoding="utf-8"
        )
        codex = self.home / ".codex"
        codex.mkdir(parents=True, exist_ok=True)
        s = sync.Sync(self.repo, self.home)
        s.merge_codex_skills()
        self.assertIn("sanity-check", (codex / "config.toml").read_text(encoding="utf-8"))
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\nsanity-check\n", encoding="utf-8"
        )
        sync.Sync(self.repo, self.home).merge_codex_skills()
        self.assertNotIn("sanity-check", (codex / "config.toml").read_text(encoding="utf-8"))

class ListOwnershipTests(SyncTestCase):
    """The wrapper must withdraw its own stale entries while leaving foreign
    ones. Union alone leaves residue; replacement alone deletes other
    people's entries. Both failure modes were hit on 2026-07-29."""

    def _roster(self, body: str) -> None:
        (self.repo / "settings" / "default-skills.txt").write_text(body, encoding="utf-8")

    def _live(self) -> Path:
        p = self.home / ".copilot" / "settings.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def test_stale_wrapper_entry_is_withdrawn_when_the_roster_changes(self) -> None:
        live = self._live()
        live.write_text("{}", encoding="utf-8")
        (self.repo / "settings" / "copilot").mkdir(parents=True, exist_ok=True)
        (self.repo / "settings" / "copilot" / "settings.json").write_text("{}", encoding="utf-8")

        self._roster("github-cli\n\n[codex]\nsanity-check\n")
        s = sync.Sync(self.repo, self.home)
        s.merge_settings("copilot", live)
        self.assertEqual(json.loads(live.read_text())["disabledSkills"], ["sanity-check"])

        # sanity-check leaves the roster entirely — its disable must go too
        self._roster("github-cli\nsanity-check\n")
        s.merge_settings("copilot", live)
        self.assertEqual(json.loads(live.read_text()).get("disabledSkills"), [])

    def test_foreign_entry_survives_a_roster_change(self) -> None:
        live = self._live()
        live.write_text(json.dumps({"disabledSkills": ["vendor-thing"]}), encoding="utf-8")
        (self.repo / "settings" / "copilot").mkdir(parents=True, exist_ok=True)
        (self.repo / "settings" / "copilot" / "settings.json").write_text("{}", encoding="utf-8")

        self._roster("github-cli\n\n[codex]\nsanity-check\n")
        s = sync.Sync(self.repo, self.home)
        s.merge_settings("copilot", live)
        self._roster("github-cli\nsanity-check\n")
        s.merge_settings("copilot", live)
        self.assertEqual(json.loads(live.read_text())["disabledSkills"], ["vendor-thing"])
