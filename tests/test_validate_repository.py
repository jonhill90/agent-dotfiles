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


class DestructiveTmuxVerbTests(unittest.TestCase):
    def test_bare_tmux_kill_server_in_tests_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_bad.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("#!/bin/bash\ntmux kill-server\n", encoding="utf-8")

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertTrue(findings)
        self.assertEqual(findings[0].level, "error")
        self.assertIn("bare destructive tmux verb", findings[0].message)

    def test_respawn_window_is_rejected_too(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "scripts" / "supervisor" / "bad.sh"
            script.parent.mkdir(parents=True)
            script.write_text("tmux respawn-window -k\n", encoding="utf-8")

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertTrue(findings)
        self.assertIn("respawn-window", findings[0].message)

    def test_shared_isolation_assertion_allows_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_good.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "cleanup_rt() { unset TMUX; export TMUX_TMPDIR=\"$RT\"; "
                "assert_isolated_tmux; tmux kill-server 2>/dev/null; }\n",
                encoding="utf-8",
            )

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertEqual(findings, [])

    def test_explicit_socket_flags_allow_destructive_verb(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_socket.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "tmux -L \"$SOCKET\" kill-server 2>/dev/null\n"
                "tmux -S \"$SOCKET_PATH\" kill-session -t scratch\n",
                encoding="utf-8",
            )

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertEqual(findings, [])

    def test_tmux_option_with_argument_does_not_hide_bare_destructive_verb(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_f_option.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "tmux -f /dev/null kill-server 2>/dev/null\n",
                encoding="utf-8",
            )

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertTrue(findings)
        self.assertIn("kill-server", findings[0].message)

    def test_multiline_shared_isolation_assertion_allows_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_multiline_good.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "unset TMUX\n"
                "export TMUX_TMPDIR=\"$RT\"\n"
                "assert_isolated_tmux\n"
                "tmux kill-server 2>/dev/null\n",
                encoding="utf-8",
            )

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertEqual(findings, [])

    def test_unset_tmux_alone_does_not_allow_destructive_verb(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_unset_only.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "unset TMUX\n"
                "tmux kill-window -t scratch\n",
                encoding="utf-8",
            )

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertTrue(findings)
        self.assertIn("kill-window", findings[0].message)

    def test_explicit_socket_tmux_wrapper_allows_destructive_verb(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_wrapper.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                'tmux() { "$REAL_TMUX" -L "$SOCKET" "$@"; }\n'
                "tmux kill-server 2>/dev/null\n",
                encoding="utf-8",
            )

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertEqual(findings, [])

    def test_resolved_tmux_binary_variable_does_not_escape_the_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_bin_escape.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "TMUX_BIN=$(command -v tmux)\n"
                '"$TMUX_BIN" kill-server\n',
                encoding="utf-8",
            )

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertTrue(findings)
        self.assertIn("kill-server", findings[0].message)

    def test_resolved_tmux_binary_variable_with_explicit_socket_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_bin_socket.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "REAL_TMUX=$(command -v tmux)\n"
                '"$REAL_TMUX" -L "$SOCKET" kill-server 2>/dev/null\n',
                encoding="utf-8",
            )

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertEqual(findings, [])

    def test_which_tmux_backtick_variable_does_not_escape_the_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_backtick_escape.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "TMUX_BIN=`which tmux`\n"
                '"$TMUX_BIN" kill-session -t scratch\n',
                encoding="utf-8",
            )

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertTrue(findings)
        self.assertIn("kill-session", findings[0].message)

    def test_unreadable_utf8_file_is_reported_not_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            test_file = root / "tests" / "test_bad_bytes.sh"
            test_file.parent.mkdir(parents=True)
            test_file.write_bytes(b"#!/bin/bash\ntmux kill-server\n\xff\xfe garbage\n")

            findings = validator.validate_tmux_destructive_verbs(root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].level, "error")
        self.assertIn("cannot decode as UTF-8", findings[0].message)


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
    def test_unrecognised_skills_are_rejected_from_default_apm_package(self) -> None:
        # The roster file and DEFAULT_APM_SKILLS are a two-place assertion;
        # this proves they cannot drift apart silently.
        #
        # The canary used to be "primer", which broke the moment primer was
        # rostered on 2026-08-10 — the test asserted a specific bench
        # membership rather than the drift property it exists to protect.
        # A synthetic name cannot be rostered, so it cannot rot the same way.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "settings"
            settings.mkdir()
            (settings / "default-skills.txt").write_text(
                "\n".join(sorted(validator.DEFAULT_APM_SKILLS | {"not-a-real-skill"}))
            )

            findings = validator.validate_apm_skill_roster(root)

        self.assertTrue(
            any(
                "unexpected default-package skills: not-a-real-skill" in finding.message
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
        by_harness, unparseable = validator.description_tokens_by_harness(self.root)
        self.assertGreater(by_harness["copilot"], by_harness["claude"])
        self.assertEqual(by_harness["claude"], by_harness["pi"])
        self.assertEqual(unparseable, [])

    def test_flat_roster_charges_every_harness_the_same(self) -> None:
        self.write_roster("shared-one\ncopilot-only\n")
        by_harness, unparseable = validator.description_tokens_by_harness(self.root)
        self.assertEqual(len(set(by_harness.values())), 1)
        self.assertEqual(unparseable, [])


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

    def test_missing_manifest_is_an_error(self) -> None:
        """#29: a moved/renamed/lost manifest must not silently disable
        SPEC §10.1 rule 5 enforcement. Rule 5 has no other check backing
        it, so losing the manifest must fail closed, not report clean."""
        # setUp() creates docs/ but never writes provenance-manifest.md.
        findings = validator.validate_roster_credit(self.root)
        self.assertTrue(findings)
        self.assertEqual(findings[0].level, "error")


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


class RosterResolutionTests(unittest.TestCase):
    """A roster name that resolves to no skill directory passes validation
    today. Deleting skills/<name>/ while leaving its roster line green is a
    silent half-cut, and sync then writes disable entries for a skill that
    does not exist (2026-07-29)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "settings").mkdir(parents=True)
        (self.root / "skills" / "github-cli").mkdir(parents=True)
        (self.root / "skills" / "github-cli" / "SKILL.md").write_text(
            "---\nname: github-cli\ndescription: x\n---\n", encoding="utf-8"
        )

    def _roster(self, body: str) -> None:
        (self.root / "settings" / "default-skills.txt").write_text(body, encoding="utf-8")

    def test_unresolvable_roster_name_is_an_error(self) -> None:
        self._roster("github-cli\nvanished\n")
        findings = validator.validate_roster_resolves(self.root)
        self.assertTrue(findings)
        self.assertIn("vanished", findings[0].message)

    def test_resolvable_names_are_silent(self) -> None:
        self._roster("github-cli\n")
        self.assertEqual(validator.validate_roster_resolves(self.root), [])

    def test_scoped_sections_are_checked_too(self) -> None:
        self._roster("github-cli\n\n[pi]\nvanished\n")
        self.assertTrue(validator.validate_roster_resolves(self.root))


class NoLocalSkillsDirTests(unittest.TestCase):
    """#9: skills are now sourced from jonhill90/skills and
    jonhill90/skills-private via apm.yml, not vendored under skills/.
    Every check that used to assume skills/ exists must degrade cleanly
    (no crash, no spurious findings) when it does not."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "settings").mkdir(parents=True)

    def test_discover_skill_dirs_is_empty_not_a_crash(self) -> None:
        self.assertEqual(validator.discover_skill_dirs(self.root, None), [])

    def test_description_tokens_by_harness_is_unmeasured_everywhere(self) -> None:
        # Was test_description_tokens_by_harness_is_zero_everywhere: it
        # pinned 0.0 as correct, which is what let the description-token
        # cap check pass unconditionally and silently (agent-dotfiles#5).
        # 0.0 means "measured, under budget"; retargeted at the value that
        # actually distinguishes "measured" from "cannot measure" — None.
        (self.root / "settings" / "default-skills.txt").write_text(
            "github-cli\n", encoding="utf-8"
        )
        totals, unparseable = validator.description_tokens_by_harness(self.root)
        self.assertTrue(totals)
        self.assertTrue(all(value is None for value in totals.values()))
        self.assertEqual(unparseable, [])

    def test_validate_roster_resolves_is_silent_without_a_skills_dir(self) -> None:
        (self.root / "settings" / "default-skills.txt").write_text(
            "github-cli\nvanished\n", encoding="utf-8"
        )
        # No skills/ directory anywhere: unresolvable-by-design, not an error
        # -- resolution now happens in the dependency repos' own CI.
        self.assertEqual(validator.validate_roster_resolves(self.root), [])

    def test_validate_static_context_does_not_crash(self) -> None:
        # no skills/ anywhere: must not raise, regardless of other findings
        validator.validate_static_context(self.root)


class DescriptionTokenCapTests(unittest.TestCase):
    """agent-dotfiles#5, repo-side half: description_tokens_by_harness()
    returning 0.0 for "cannot measure" made the cap check at
    validate_static_context()'s `tokens > DESCRIPTION_TOKEN_CAP` line
    unconditionally pass, silently, in every tree without a local skills/
    -- which has been every tree since #9. These prove the replacement
    behaviour: unmeasured is reported, not swallowed; a sighted tree still
    measures real totals; and the cap still fires when a sighted tree
    genuinely exceeds it."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        instructions = self.root / "instructions"
        (instructions / "overlays").mkdir(parents=True)
        (instructions / "global.instructions.md").write_text(
            "x" * 400, encoding="utf-8"
        )

    def _add_skill(self, name: str, description: str) -> None:
        skill = self.root / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
            encoding="utf-8",
        )

    def test_unmeasured_tree_gets_a_warning_finding(self) -> None:
        # No skills/ at all -- the normal state of this repo since #9.
        findings = validator.validate_static_context(self.root)
        warnings = [f for f in findings if f.level == "warning"]
        self.assertTrue(
            any("description-token" in f.message for f in warnings),
            f"no unmeasured warning among: {findings}",
        )
        # And the cap check must not have fired at all -- there is nothing
        # to compare against the cap when the component is unmeasured.
        self.assertFalse(
            any("installed-skill descriptions" in f.message for f in findings)
        )

    def test_sighted_tree_still_computes_real_totals(self) -> None:
        self._add_skill("example-skill", "d" * 100)
        by_harness, unparseable = validator.description_tokens_by_harness(self.root)
        self.assertTrue(by_harness)
        self.assertTrue(all(value is not None for value in by_harness.values()))
        self.assertTrue(all(value > 0 for value in by_harness.values()))
        self.assertEqual(unparseable, [])
        # A sighted tree must not emit the unmeasured warning.
        findings = validator.validate_static_context(self.root)
        self.assertFalse(
            any("description-token" in f.message and f.level == "warning"
                for f in findings)
        )

    def test_cap_check_fires_when_a_sighted_tree_exceeds_it(self) -> None:
        # DESCRIPTION_TOKEN_CAP is 2000 tokens; token_estimate_bytes is
        # size/4, so >8000 description bytes trips it.
        self._add_skill("oversized-skill", "d" * 8100)
        findings = validator.validate_static_context(self.root)
        errors = [f for f in findings if f.level == "error"]
        self.assertTrue(
            any("installed-skill descriptions" in f.message for f in errors),
            f"cap check did not fire: {findings}",
        )


class SightedTreePerNameResolutionTests(unittest.TestCase):
    """agent-dotfiles#5's other repo-side half: inside a *sighted* tree
    (skills/ exists), a roster name that does not resolve to a real skill
    -- or resolves to a broken SKILL.md -- used to be swallowed by
    description_tokens_by_harness()'s `except PARSE_ERRORS: continue` and
    charged 0 bytes, silently. "Missing" and "corrupt" are different
    operator problems and both were invisible before this fix.

    "Missing" is deliberately NOT re-tested against
    description_tokens_by_harness() here: validate_roster_resolves()
    (see RosterResolutionTests) already reports it as an error, tested
    and mutation-checked there. A second, overlapping rule for the same
    cause would just be two findings for one defect. Only "corrupt" is a
    genuine gap this class closes."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        instructions = self.root / "instructions"
        (instructions / "overlays").mkdir(parents=True)
        (instructions / "global.instructions.md").write_text(
            "x" * 400, encoding="utf-8"
        )
        (self.root / "settings").mkdir(parents=True)
        good = self.root / "skills" / "good-skill"
        good.mkdir(parents=True)
        (good / "SKILL.md").write_text(
            "---\nname: good-skill\ndescription: fine\n---\n\n# good-skill\n",
            encoding="utf-8",
        )

    def _roster(self, body: str) -> None:
        (self.root / "settings" / "default-skills.txt").write_text(
            body, encoding="utf-8"
        )

    def test_missing_name_is_not_double_reported_here(self) -> None:
        # Already an error via validate_roster_resolves(); this function
        # must stay silent about it rather than add a second finding.
        self._roster("good-skill\nvanished\n")
        _, unparseable = validator.description_tokens_by_harness(self.root)
        self.assertEqual(unparseable, [])

    def test_corrupt_skill_md_is_distinguished_from_missing(self) -> None:
        broken = self.root / "skills" / "broken-skill"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("not frontmatter at all\n", encoding="utf-8")
        self._roster("good-skill\nbroken-skill\n")

        by_harness, unparseable = validator.description_tokens_by_harness(self.root)
        self.assertTrue(
            any(p.name == "broken-skill" for p in unparseable),
            f"broken-skill not flagged as unparseable: {unparseable}",
        )
        # The good skill's bytes still count -- one broken name must not
        # zero out the whole harness total.
        self.assertTrue(all(value > 0 for value in by_harness.values()))

    def test_corrupt_skill_md_produces_an_error_finding(self) -> None:
        broken = self.root / "skills" / "broken-skill"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("not frontmatter at all\n", encoding="utf-8")
        self._roster("good-skill\nbroken-skill\n")

        findings = validator.validate_static_context(self.root)
        errors = [f for f in findings if f.level == "error"]
        self.assertTrue(
            any("broken-skill" in str(f.path) for f in errors),
            f"no error finding for the corrupt SKILL.md among: {findings}",
        )


class SkillSourcePinTests(unittest.TestCase):
    """#9: apm.yml's remote skill-bundle dependencies must be pinned to an
    immutable commit SHA, not a branch or tag name, so `apm install`
    resolves reproducibly."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _write_apm_yml(self, body: str) -> None:
        (self.root / "apm.yml").write_text(body, encoding="utf-8")

    def test_sha_pinned_dependency_is_silent(self) -> None:
        self._write_apm_yml(
            "name: agent-dotfiles\n"
            "version: 0.1.0\n"
            "dependencies:\n"
            "  apm:\n"
            "    - git: https://github.com/jonhill90/skills.git\n"
            "      ref: 069e2c475e875be1c23a31e7f5da08ffd58d655a\n"
            "      skills: [\"*\"]\n"
            "      alias: skills-public\n"
        )
        self.assertEqual(validator.validate_skill_source_pins(self.root), [])

    def test_branch_pinned_dependency_is_an_error(self) -> None:
        self._write_apm_yml(
            "name: agent-dotfiles\n"
            "version: 0.1.0\n"
            "dependencies:\n"
            "  apm:\n"
            "    - git: https://github.com/jonhill90/skills.git\n"
            "      ref: main\n"
            "      skills: [\"*\"]\n"
            "      alias: skills-public\n"
        )
        findings = validator.validate_skill_source_pins(self.root)
        self.assertTrue(findings)
        self.assertIn("skills-public", findings[0].message)

    def test_missing_ref_is_an_error(self) -> None:
        self._write_apm_yml(
            "name: agent-dotfiles\n"
            "version: 0.1.0\n"
            "dependencies:\n"
            "  apm:\n"
            "    - git: https://github.com/jonhill90/skills-private.git\n"
            "      skills: [\"*\"]\n"
            "      alias: skills-private\n"
        )
        findings = validator.validate_skill_source_pins(self.root)
        self.assertTrue(findings)
        self.assertIn("skills-private", findings[0].message)

    def test_dependency_without_skills_key_is_ignored(self) -> None:
        # not a skill-bundle dependency, so no ref-pin requirement applies
        self._write_apm_yml(
            "name: agent-dotfiles\n"
            "version: 0.1.0\n"
            "dependencies:\n"
            "  apm:\n"
            "    - git: https://github.com/jonhill90/something-else.git\n"
            "      ref: main\n"
            "      alias: not-a-skill-bundle\n"
        )
        self.assertEqual(validator.validate_skill_source_pins(self.root), [])

    def test_missing_apm_yml_is_an_error(self) -> None:
        """#29 sweep: apm.yml is the only record of which skill-bundle
        dependencies must be SHA-pinned (#9's reproducibility requirement).
        Nothing else in this validator checks that apm.yml exists, so a
        moved/renamed/lost apm.yml must fail closed, not report clean."""
        findings = validator.validate_skill_source_pins(self.root)
        self.assertTrue(findings)
        self.assertEqual(findings[0].level, "error")


class RealApmYmlShapeTests(unittest.TestCase):
    """#9 review: validate_skill_source_pins silently discovered zero
    dependencies against the real apm.yml, because it has a comment block
    ahead of each dependency entry and the parser's regex required each
    entry to start immediately after the previous one. Every fixture above
    is comment-free and passed anyway -- this class pins the parser to the
    real, comment-bearing shape, including the actual committed file."""

    # Byte-for-byte the shape actually committed at repo root: a multi-line
    # comment block, then each dependency, repeated, then a shallower `mcp:`
    # line that must terminate the block.
    REAL_SHAPE = (
        "name: agent-dotfiles\n"
        "version: 0.1.0\n"
        "description: >-\n"
        "  Jon Hill's agent dotfiles.\n"
        "dependencies:\n"
        "  apm:\n"
        "    # Candidate public skills collection (jonhill90/skills#127, not yet\n"
        "    # merged). Pinned to that PR branch's head commit rather than the\n"
        "    # branch name: a branch ref moves, and #9 requires a reproducible,\n"
        "    # independently-verifiable pin. Bump this SHA (and re-verify) once\n"
        "    # #127 merges to main, then again on every subsequent skill change.\n"
        "    - git: https://github.com/jonhill90/skills.git\n"
        "      ref: 069e2c475e875be1c23a31e7f5da08ffd58d655a\n"
        "      skills: [\"*\"]\n"
        "      alias: skills-public\n"
        "    # Private companion collection (#9). Pinned the same way. Currently\n"
        "    # carries one harmless, non-rostered fixture (source-probe) proving\n"
        "    # authenticated resolution; see skills-private's own PR.\n"
        "    - git: https://github.com/jonhill90/skills-private.git\n"
        "      ref: b203b1ebf2c2eb35808443ba76cd22aadecf76e7\n"
        "      skills: [\"*\"]\n"
        "      alias: skills-private\n"
        "  mcp: []\n"
    )

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_discovers_both_aliases_through_the_comment_blocks(self) -> None:
        (self.root / "apm.yml").write_text(self.REAL_SHAPE, encoding="utf-8")
        deps = validator.parse_skill_source_dependencies(self.root)
        self.assertEqual(
            {d["alias"] for d in deps}, {"skills-public", "skills-private"}
        )
        by_alias = {d["alias"]: d for d in deps}
        self.assertEqual(
            by_alias["skills-public"]["ref"],
            "069e2c475e875be1c23a31e7f5da08ffd58d655a",
        )
        self.assertEqual(
            by_alias["skills-private"]["ref"],
            "b203b1ebf2c2eb35808443ba76cd22aadecf76e7",
        )

    def test_sha_pinned_real_shape_has_no_findings(self) -> None:
        (self.root / "apm.yml").write_text(self.REAL_SHAPE, encoding="utf-8")
        self.assertEqual(validator.validate_skill_source_pins(self.root), [])

    def test_branch_pinned_real_shape_is_still_caught(self) -> None:
        bad = self.REAL_SHAPE.replace(
            "ref: b203b1ebf2c2eb35808443ba76cd22aadecf76e7", "ref: main"
        )
        (self.root / "apm.yml").write_text(bad, encoding="utf-8")
        findings = validator.validate_skill_source_pins(self.root)
        self.assertTrue(findings)
        self.assertIn("skills-private", findings[0].message)

    def test_against_the_actual_committed_apm_yml(self) -> None:
        # No fixture at all -- the real file, comments and all. This is
        # the test that would have caught the silent false negative.
        repo_root = Path(__file__).resolve().parents[1]
        deps = validator.parse_skill_source_dependencies(repo_root)
        self.assertEqual(
            {d["alias"] for d in deps}, {"skills-public", "skills-private"}
        )
        for dep in deps:
            self.assertRegex(dep["ref"], r"^[0-9a-fA-F]{40}$")
        self.assertEqual(validator.validate_skill_source_pins(repo_root), [])


class SkillBenchTests(unittest.TestCase):
    """agent-dotfiles#181 — a benched skill is a stated decision, not an
    absence, and the estate must be able to tell "withheld" apart from
    "authored and forgotten"."""

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

    def make_skill_dir(self, name: str) -> None:
        skill = self.root / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: d\n---\n\n# {name}\n",
            encoding="utf-8",
        )

    def test_orphaned_skill_is_reported(self) -> None:
        # Test 1: present in skills/, absent from both roster and bench.
        skills = sorted(validator.DEFAULT_APM_SKILLS)
        self.write_roster("\n".join(skills) + "\n")
        self.make_skill_dir("orphan-skill")
        for name in skills:
            self.make_skill_dir(name)
        findings = validator.validate_skill_roster_delta(self.root)
        self.assertTrue(
            any("orphan-skill" in f.message for f in findings),
            f"orphaned skill not reported: {findings}",
        )

    def test_missing_skills_dir_warns_instead_of_silent(self) -> None:
        # PR #185 review, blocking finding: no local skills/ (the normal
        # state of this repo since #9) must produce a warning Finding, not
        # a silent []  indistinguishable from "checked, found no orphans".
        skills = sorted(validator.DEFAULT_APM_SKILLS)
        self.write_roster("\n".join(skills) + "\n")
        findings = validator.validate_skill_roster_delta(self.root)
        self.assertEqual(len(findings), 1, f"expected one warning: {findings}")
        self.assertEqual(findings[0].level, "warning")
        self.assertIn("orphan check cannot run", findings[0].message)

    def test_benched_skill_is_not_reported(self) -> None:
        # Test 2 (part 1): a benched skill with a reason is not flagged
        # as orphaned.
        skills = sorted(validator.DEFAULT_APM_SKILLS)
        self.write_roster(
            "\n".join(skills) + "\n\n[benched]\nbenched-skill  # reason here\n"
        )
        for name in skills:
            self.make_skill_dir(name)
        self.make_skill_dir("benched-skill")
        findings = validator.validate_skill_roster_delta(self.root)
        self.assertEqual(
            findings, [], f"benched skill flagged as orphaned: {findings}"
        )

    def test_empty_bench_reason_fails(self) -> None:
        # Test 2 (part 2): a bench entry without a reason is itself an error.
        skills = sorted(validator.DEFAULT_APM_SKILLS)
        self.write_roster(
            "\n".join(skills) + "\n\n[benched]\nbenched-skill\n"
        )
        findings = validator.validate_skill_bench(self.root)
        self.assertTrue(
            any(
                "benched-skill" in f.message and "no reason" in f.message
                for f in findings
            ),
            f"empty bench reason not rejected: {findings}",
        )

    def test_benched_and_rostered_is_a_contradiction(self) -> None:
        skills = sorted(validator.DEFAULT_APM_SKILLS)
        name = skills[0]
        self.write_roster(
            "\n".join(skills) + f"\n\n[benched]\n{name}  # reason\n"
        )
        findings = validator.validate_skill_bench(self.root)
        self.assertTrue(
            any("both rostered and benched" in f.message for f in findings),
            f"contradiction not reported: {findings}",
        )

    def test_benched_section_is_not_installed(self) -> None:
        # A [benched] header must never behave like a harness section --
        # roster_union() must not fold its members into the install set.
        skills = sorted(validator.DEFAULT_APM_SKILLS)
        self.write_roster(
            "\n".join(skills) + "\n\n[benched]\nbenched-skill  # reason\n"
        )
        from sync import roster_union  # noqa: E402

        self.assertNotIn("benched-skill", roster_union(self.root))

    def test_benched_skills_are_not_in_default_apm_package(self) -> None:
        # Test 3: existing roster validation is unchanged -- a benched
        # skill must not be treated as part of the default package, and
        # validate_apm_skill_roster must keep rejecting foreign names.
        skills = sorted(validator.DEFAULT_APM_SKILLS)
        self.write_roster(
            "\n".join(skills) + "\n\n[benched]\nverify-the-instrument  # reason\n"
        )
        findings = [
            f
            for f in validator.validate_apm_skill_roster(self.root)
            if f.level == "error"
        ]
        self.assertEqual(
            findings, [], f"benched skill counted toward default package: {findings}"
        )

        self.write_roster(
            "\n".join(sorted(validator.DEFAULT_APM_SKILLS | {"not-a-real-skill"}))
        )
        findings = validator.validate_apm_skill_roster(self.root)
        self.assertTrue(
            any(
                "unexpected default-package skills: not-a-real-skill" in f.message
                for f in findings
            )
        )

    def test_the_eleven_are_each_rostered_or_benched(self) -> None:
        # Test 4, against the real committed roster.
        eleven = {
            "ask-a-council",
            "distill",
            "keep-me-honest",
            "loop-contract",
            "loop-memory",
            "mine-transcripts",
            "notify",
            "prd",
            "spec",
            "tdd",
            "verify-the-instrument",
        }
        repo_root = Path(__file__).resolve().parents[1]
        from sync import benched_skills, roster_union  # noqa: E402

        accounted = set(roster_union(repo_root)) | set(benched_skills(repo_root))
        missing = eleven - accounted
        self.assertEqual(missing, set(), f"silently absent: {missing}")
        for name in eleven & set(benched_skills(repo_root)):
            self.assertTrue(
                benched_skills(repo_root)[name],
                f"{name} is benched with an empty reason",
            )

