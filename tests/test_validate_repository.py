from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "validate_repository.py"
SPEC = importlib.util.spec_from_file_location("validate_repository", SCRIPT_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class ValidateRepositoryTests(unittest.TestCase):
    def make_skill(
        self,
        root: Path,
        directory: str = "example-skill",
        frontmatter: str | None = None,
        body: str = "# Example\n\nRun the example.",
    ) -> Path:
        skill_dir = root / "skills" / directory
        skill_dir.mkdir(parents=True)
        metadata = frontmatter or (
            f"name: {directory}\n"
            "description: Run an example workflow. Use for validator tests."
        )
        (skill_dir / "SKILL.md").write_text(
            f"---\n{metadata}\n---\n\n{body}\n",
            encoding="utf-8",
        )
        return skill_dir

    def messages(self, findings: list[object]) -> list[str]:
        return [finding.message for finding in findings]

    def test_valid_skill_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill_dir = self.make_skill(Path(temporary))
            self.assertEqual([], validator.validate_skill(skill_dir))

    def test_name_must_match_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill_dir = self.make_skill(
                Path(temporary),
                frontmatter=(
                    "name: different-name\n"
                    "description: Run an example workflow. Use for validator tests."
                ),
            )
            findings = validator.validate_skill(skill_dir)
            self.assertTrue(
                any("does not match directory" in message for message in self.messages(findings))
            )

    def test_unknown_frontmatter_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill_dir = self.make_skill(
                Path(temporary),
                frontmatter=(
                    "name: example-skill\n"
                    "description: Run an example workflow. Use for validator tests.\n"
                    "argument-hint: value"
                ),
            )
            findings = validator.validate_skill(skill_dir)
            self.assertIn(
                "non-portable frontmatter fields: argument-hint",
                self.messages(findings),
            )

    def test_broken_relative_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill_dir = self.make_skill(
                Path(temporary),
                body="# Example\n\nRead [missing](references/missing.md).",
            )
            findings = validator.validate_skill(skill_dir)
            self.assertIn(
                "relative link does not resolve: references/missing.md",
                self.messages(findings),
            )

    def test_script_must_be_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill_dir = self.make_skill(Path(temporary))
            script = skill_dir / "scripts" / "run.sh"
            script.parent.mkdir()
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(script, 0o644)
            findings = validator.validate_skill(skill_dir)
            self.assertIn("script must have an executable mode", self.messages(findings))

    def test_duplicate_names_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.make_skill(root, directory="first")
            second = self.make_skill(
                root,
                directory="second",
                frontmatter=(
                    "name: first\n"
                    "description: Run another workflow. Use for duplicate tests."
                ),
            )
            findings = validator.validate_skill_collection([first, second])
            self.assertTrue(
                any("duplicate skill name" in message for message in self.messages(findings))
            )


class PrivacyDenylistTests(unittest.TestCase):
    def test_flags_denylisted_terms_in_tracked_markdown(self) -> None:
        import tempfile
        from pathlib import Path
        import validate_repository as vr

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".privacy-denylist").write_text("AcmeCorp\nsecretproject\n")
            docs = root / "docs"; docs.mkdir()
            (docs / "note.md").write_text("mentions AcmeCorp storage\n")
            (docs / "clean.md").write_text("nothing to see\n")
            findings = vr.validate_privacy(root)
            self.assertEqual(len(findings), 1)
            self.assertIn("note.md", str(findings[0].path))
            # the term itself must not appear in the finding message
            self.assertNotIn("AcmeCorp", findings[0].message)

    def test_no_denylist_file_means_no_findings(self) -> None:
        import tempfile
        from pathlib import Path
        import validate_repository as vr

        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(vr.validate_privacy(Path(td)), [])

    def test_broken_symlink_is_skipped(self) -> None:
        import tempfile
        from pathlib import Path
        import validate_repository as vr

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".privacy-denylist").write_text("term\n")
            (root / "gone.md").symlink_to(root / "missing-target.md")
            self.assertEqual(vr.validate_privacy(root), [])


class FallbackFrontmatterTests(unittest.TestCase):
    def test_mini_yaml_matches_real_yaml_for_skill_frontmatter(self) -> None:
        import validate_repository as vr
        import yaml as real_yaml

        text = (
            "name: my-skill\n"
            "description: Does things safely. Use when testing.\n"
            'license: "MIT"\n'
        )
        self.assertEqual(vr.mini_yaml(text), real_yaml.safe_load(text))
        # the fallback is deliberately more lenient than YAML: embedded
        # colons stay verbatim instead of raising
        self.assertEqual(
            vr.mini_yaml("description: a: b\n"), {"description": "a: b"}
        )

    def test_mini_yaml_strips_quotes_and_ignores_comments(self) -> None:
        import validate_repository as vr

        parsed = vr.mini_yaml("# comment\nname: 'x'\n\ndescription: y\n")
        self.assertEqual(parsed, {"name": "x", "description": "y"})

    def test_invalid_skill_is_reported_without_pyyaml(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill_dir = Path(temporary) / "skills" / "bad-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("not frontmatter\n")
            with mock.patch.object(validator, "yaml", None):
                findings = validator.validate_skill(skill_dir)
            self.assertEqual(len(findings), 1)
            self.assertIn("must start with ---", findings[0].message)


class StaticContextBudgetTests(unittest.TestCase):
    def make_root(self, temporary: str, instruction_bytes: int = 400) -> Path:
        root = Path(temporary)
        instructions = root / "instructions"
        (instructions / "overlays").mkdir(parents=True)
        (instructions / "global.instructions.md").write_text(
            "x" * instruction_bytes
        )
        (instructions / "overlays" / "pi.md").write_text("pi overlay\n")
        skill = root / "skills" / "example-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: example-skill\n"
            "description: Run examples. Use when testing.\n---\n\n# Skill\n"
        )
        return root

    def test_static_context_within_budget_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            self.assertEqual([], validator.validate_static_context(root))

    def test_instruction_component_over_budget_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary, instruction_bytes=8_004)
            findings = validator.validate_static_context(root)
            self.assertTrue(
                any("canonical instructions" in finding.message for finding in findings)
            )


class ApmPackageRosterTests(unittest.TestCase):
    def test_benched_skills_are_not_in_default_apm_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "settings"
            settings.mkdir()
            (settings / "default-skills.txt").write_text(
                "\n".join(sorted(validator.DEFAULT_APM_SKILLS | {"primer"}))
            )

            findings = validator.validate_apm_skill_roster(root)

        self.assertTrue(
            any(
                "unexpected default-package skills: primer" in finding.message
                for finding in findings
            )
        )


if __name__ == "__main__":
    unittest.main()


class SectionedRosterTests(unittest.TestCase):
    """SPEC §4.1 — validator understands per-harness roster sections."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_roster(self, text: str) -> Path:
        settings = self.root / "settings"
        settings.mkdir(parents=True, exist_ok=True)
        path = settings / "default-skills.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def test_union_of_sections_satisfies_the_default_package(self) -> None:
        skills = sorted(validator.DEFAULT_APM_SKILLS)
        self.write_roster(
            "\n".join(skills[:-1]) + f"\n\n[copilot]\n{skills[-1]}\n"
        )
        findings = validator.validate_apm_skill_roster(self.root)
        self.assertEqual(
            [f for f in findings if f.level == "error"],
            [],
            "a sectioned skill still counts toward the default package",
        )

    def test_section_headers_are_not_treated_as_skill_names(self) -> None:
        self.write_roster(
            "\n".join(sorted(validator.DEFAULT_APM_SKILLS)) + "\n\n[copilot]\n"
        )
        errors = [
            f
            for f in validator.validate_apm_skill_roster(self.root)
            if f.level == "error"
        ]
        self.assertEqual(errors, [], f"header parsed as a skill: {errors}")

    def test_flat_roster_still_validates(self) -> None:
        self.write_roster("\n".join(sorted(validator.DEFAULT_APM_SKILLS)) + "\n")
        self.assertEqual(
            [
                f
                for f in validator.validate_apm_skill_roster(self.root)
                if f.level == "error"
            ],
            [],
        )


class PerHarnessBudgetTests(unittest.TestCase):
    """SPEC §4.1 — the budget is measured against each harness's
    resolved roster, not against the union."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "settings").mkdir(parents=True)
        for name, description in (
            ("shared-one", "s" * 100),
            ("copilot-only", "c" * 400),
        ):
            skill = self.root / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_roster(self, text: str) -> None:
        (self.root / "settings" / "default-skills.txt").write_text(
            text, encoding="utf-8"
        )

    def test_scoped_skill_counts_only_against_its_own_harness(self) -> None:
        self.write_roster("shared-one\n\n[copilot]\ncopilot-only\n")
        by_harness = validator.description_tokens_by_harness(self.root)
        self.assertGreater(by_harness["copilot"], by_harness["claude"])
        self.assertEqual(by_harness["claude"], by_harness["pi"])

    def test_flat_roster_charges_every_harness_the_same(self) -> None:
        self.write_roster("shared-one\ncopilot-only\n")
        by_harness = validator.description_tokens_by_harness(self.root)
        self.assertEqual(len(set(by_harness.values())), 1)


class RosterCreditTests(unittest.TestCase):
    """SPEC §10.1 rule 5: nothing enters the default roster on a promise to
    verify later. The rule existed as prose for two components before it was
    written down; a limit nothing checks is a convention, which is how
    skills/tmux reached 493 of 500 permitted lines unnoticed (#82)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "settings").mkdir(parents=True)
        (self.root / "docs").mkdir(parents=True)
        (self.root / "settings" / "default-skills.txt").write_text(
            "github-cli\nsafe-deletion\n", encoding="utf-8"
        )

    def _manifest(self, body: str) -> None:
        (self.root / "docs" / "provenance-manifest.md").write_text(
            body, encoding="utf-8"
        )

    def test_roster_skill_with_an_open_caveat_is_an_error(self) -> None:
        self._manifest(
            "| `safe-deletion` skill | self | Author | adopted at the prior "
            "bar; **will be** re-verified at the ×3 adoption bar in P2-M5 |\n"
        )
        findings = validator.validate_roster_credit(self.root)
        self.assertTrue(findings)
        self.assertIn("safe-deletion", findings[0].message)

    def test_cleared_caveat_is_fine(self) -> None:
        self._manifest(
            "| `safe-deletion` skill | self | Author | **Caveat cleared "
            "2026-07-27**: re-verified at the ×3 adoption bar |\n"
        )
        self.assertEqual(validator.validate_roster_credit(self.root), [])

    def test_opt_in_skill_may_carry_an_open_caveat(self) -> None:
        """Opt-in costs nothing at request time, so an unfinished promise
        there is not the failure the rule is about."""
        self._manifest(
            "| `dispatching-subagents` skill | self | public opt-in; "
            "**will be** re-verified once a scenario exists |\n"
        )
        self.assertEqual(validator.validate_roster_credit(self.root), [])


class SkillLengthTests(unittest.TestCase):
    """AGENTS.md caps SKILL.md at 500 lines and nothing enforced it, so
    skills/tmux reached 493 unnoticed (#82). A cap nothing checks is a
    convention."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.skill = Path(self.tmp.name) / "demo"
        self.skill.mkdir()

    def _write(self, lines: int) -> Path:
        body = "---\nname: demo\ndescription: x\n---\n" + "\n".join(
            f"line {i}" for i in range(lines)
        )
        path = self.skill / "SKILL.md"
        path.write_text(body + "\n", encoding="utf-8")
        return path

    def test_over_the_cap_is_an_error(self) -> None:
        self._write(520)
        findings = validator.validate_skill_length(self.skill)
        self.assertTrue(findings)
        self.assertEqual(findings[0].level, "error")

    def test_approaching_the_cap_warns_early(self) -> None:
        """493 of 500 is seven lines from breaking and read as fine. A warning
        is what turns 'nobody noticed' into 'somebody was told'."""
        self._write(470)
        findings = validator.validate_skill_length(self.skill)
        self.assertTrue(findings)
        self.assertEqual(findings[0].level, "warning")

    def test_comfortably_short_is_silent(self) -> None:
        self._write(120)
        self.assertEqual(validator.validate_skill_length(self.skill), [])
