"""Tests for detecting and fail-closing on stale global APM manifest registrations.

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

from sync_helpers import (  # noqa: E402
    APM_MARKER,
    SYNTHETIC_GLOBAL_MANIFEST,
    SyncTestCase,
    make_repo,
)


class StaleGlobalRegistrationDetectionTests(SyncTestCase):
    """Sync.stale_global_registrations() (#14): reads the *global*
    ~/.apm/apm.yml (not the project apm.yml #9 already covers) and
    reports every stale local-package entry, by exact path."""

    def _write_global_manifest(self, body: str) -> Path:
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True, exist_ok=True)
        manifest = apm_dir / "apm.yml"
        manifest.write_text(body, encoding="utf-8")
        return manifest

    def test_empty_when_no_global_manifest_exists(self) -> None:
        self.assertEqual(self.syncer.stale_global_registrations(), [])

    def test_reports_a_missing_source_path_by_exact_path(self) -> None:
        missing = self.home / "gone"
        self._write_global_manifest(
            "dependencies:\n"
            "  apm:\n"
            f"    - path: {missing}\n"
            "      skills:\n"
            "        - tmux\n"
        )
        findings = self.syncer.stale_global_registrations()
        self.assertEqual(len(findings), 1)
        path, reason = findings[0]
        self.assertEqual(path, str(missing))
        self.assertIn("no longer exist", reason)

    def test_current_valid_registration_is_not_reported(self) -> None:
        valid = self.home / "valid-project"
        valid.mkdir()
        (valid / "apm.yml").write_text("name: valid-project\nversion: 0.1.0\n")
        self._write_global_manifest(
            "dependencies:\n"
            "  apm:\n"
            f"    - path: {valid}\n"
            "      skills:\n"
            "        - tmux\n"
        )
        self.assertEqual(self.syncer.stale_global_registrations(), [])

class ApplyFailsClosedOnStaleGlobalRegistrationTests(SyncTestCase):
    """apply() must refuse to invoke apm at all when the global manifest
    carries a stale local-package registration (#14) -- the incident was
    apm silently compiling contaminated output from exactly this state,
    not apm failing loudly."""

    def test_apply_never_calls_apm_when_a_registration_is_stale(self) -> None:
        missing = self.home / "gone"
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True)
        (apm_dir / "apm.yml").write_text(
            "dependencies:\n"
            "  apm:\n"
            f"    - path: {missing}\n"
            "      skills:\n"
            "        - tmux\n"
        )

        def runner(cmd, check=False):
            raise AssertionError("apm must not run while a global registration is stale")

        self.syncer.runner = runner
        rc = self.syncer.apply()

        self.assertNotEqual(rc, 0)

    def test_apply_names_the_exact_stale_path_in_its_error(self) -> None:
        import contextlib
        import io

        missing = self.home / "gone"
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True)
        (apm_dir / "apm.yml").write_text(
            "dependencies:\n"
            "  apm:\n"
            f"    - path: {missing}\n"
            "      skills:\n"
            "        - tmux\n"
        )
        self.syncer.runner = lambda cmd, check=False: (_ for _ in ()).throw(
            AssertionError("apm must not run")
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.syncer.apply()
        self.assertIn(str(missing), buf.getvalue())

    def test_apply_proceeds_normally_when_global_manifest_is_clean(self) -> None:
        valid = self.home / "valid-project"
        valid.mkdir()
        (valid / "apm.yml").write_text("name: valid-project\nversion: 0.1.0\n")
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True)
        (apm_dir / "apm.yml").write_text(
            "dependencies:\n"
            "  apm:\n"
            f"    - path: {valid}\n"
            "      skills:\n"
            "        - tmux\n"
        )

        def runner(cmd, check=False):
            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        self.assertEqual(self.syncer.apply(), 0)

class StatusDoctorStaleGlobalReportingTests(SyncTestCase):
    """status() and doctor() must name the exact stale path (#14) -- not
    just say "something is stale" -- so a human can act on it without
    re-deriving which registration is the problem."""

    def _write_stale_global_manifest(self) -> Path:
        missing = self.home / "gone-for-status"
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True)
        (apm_dir / "apm.yml").write_text(
            "dependencies:\n"
            "  apm:\n"
            f"    - path: {missing}\n"
            "      skills:\n"
            "        - tmux\n"
        )
        return missing

    def test_status_prints_a_stale_global_line_with_the_exact_path(self) -> None:
        import contextlib
        import io

        missing = self._write_stale_global_manifest()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.syncer.status()
        self.assertIn(f"[stale-global] {missing}:", buf.getvalue())
        self.assertNotEqual(rc, 0)

    def test_status_is_clean_without_stale_global_registrations(self) -> None:
        self.assertEqual(self.syncer.stale_global_registrations(), [])

    def test_doctor_check_fails_and_names_the_exact_path(self) -> None:
        missing = self._write_stale_global_manifest()
        checks = dict(self.syncer.doctor_checks(env={}))
        self.assertIn("stale-global-registrations", checks)
        ok, message = checks["stale-global-registrations"]
        self.assertFalse(ok)
        self.assertIn(str(missing), message)

    def test_doctor_check_passes_when_clean(self) -> None:
        checks = dict(self.syncer.doctor_checks(env={}))
        ok, _ = checks["stale-global-registrations"]
        self.assertTrue(ok)

class GlobalManifestParsingTests(unittest.TestCase):
    """#14: parse ~/.apm/apm.yml's dependencies.apm *local* (path:)
    registrations. Real YAML apm itself emits, not hand-authored -- these
    fixtures reproduce the literal shapes captured from a real global
    manifest, with synthetic, non-personal paths substituted for the real
    ones (#15 review) while preserving every shape that matters: inline
    `path:`, a bare string item, a `path:` value wrapped onto the next
    line, and a nested `skills:` block list."""

    def test_discovers_all_four_local_registrations(self) -> None:
        entries = sync.parse_global_local_packages(SYNTHETIC_GLOBAL_MANIFEST)
        self.assertEqual(len(entries), 4)
        paths = [entry["path"] for entry in entries]
        self.assertEqual(
            paths,
            [
                "/home/example/projects/skills-checkout",
                "/tmp/build-a1b2c3d4/repo",
                "/tmp/scratchpad/example-issue/repo-bad-private-ref",
                "/home/example/projects/agent-dotfiles",
            ],
        )

    def test_parses_the_inline_path_and_its_skills_list(self) -> None:
        entries = sync.parse_global_local_packages(SYNTHETIC_GLOBAL_MANIFEST)
        skills_entry = entries[0]
        self.assertEqual(skills_entry["path"], "/home/example/projects/skills-checkout")
        self.assertEqual(
            skills_entry["skills"],
            [
                "az-devops", "create-skill", "failing-test-first", "gh-cli",
                "github-cli", "linear", "memory-conventions", "obsidian",
                "safe-deletion", "sanity-check", "tmux", "using-tmux",
            ],
        )

    def test_parses_a_bare_string_entry_with_no_path_key(self) -> None:
        entries = sync.parse_global_local_packages(SYNTHETIC_GLOBAL_MANIFEST)
        bare = entries[1]
        self.assertEqual(bare["path"], "/tmp/build-a1b2c3d4/repo")
        self.assertEqual(bare.get("skills", []), [])

    def test_parses_a_path_wrapped_onto_the_next_line(self) -> None:
        entries = sync.parse_global_local_packages(SYNTHETIC_GLOBAL_MANIFEST)
        wrapped = entries[2]
        self.assertEqual(wrapped["path"], "/tmp/scratchpad/example-issue/repo-bad-private-ref")
        self.assertIn("create-skill", wrapped["skills"])

    def test_no_manifest_text_is_empty_list(self) -> None:
        self.assertEqual(sync.parse_global_local_packages(""), [])

    def test_manifest_with_no_apm_dependencies_is_empty_list(self) -> None:
        self.assertEqual(
            sync.parse_global_local_packages("name: jon\nversion: 1.0.0\n"), []
        )

class StaleGlobalRegistrationTests(unittest.TestCase):
    """#14: a local registration is stale when its source is missing, or
    when it no longer structurally constitutes an APM package, or when it
    is a bare skill-bundle registration whose requested skill names no
    longer exist in the bundle. A registration with its own apm.yml is
    never flagged structurally -- #14 explicitly requires preserving
    legitimate independent global packages."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _skill_bundle(self, root: Path, names: list[str]) -> Path:
        for name in names:
            skill_dir = root / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: x\n---\n", encoding="utf-8"
            )
        return root

    def test_missing_source_directory_is_stale(self) -> None:
        entry = {"path": str(self.root / "does-not-exist"), "skills": []}
        reason = sync.stale_global_registration(entry)
        self.assertIsNotNone(reason)
        self.assertIn("no longer exist", reason)

    def test_source_with_apm_yml_is_never_stale_even_with_skill_drift(self) -> None:
        pkg = self.root / "real-project"
        pkg.mkdir()
        (pkg / "apm.yml").write_text("name: real-project\nversion: 0.1.0\n")
        self._skill_bundle(pkg, ["current-skill"])
        entry = {"path": str(pkg), "skills": ["vanished-skill"]}
        self.assertIsNone(sync.stale_global_registration(entry))

    def test_bundle_registration_with_all_requested_names_present_is_fine(self) -> None:
        pkg = self._skill_bundle(self.root / "bundle", ["tmux", "github-cli"])
        entry = {"path": str(pkg), "skills": ["tmux", "github-cli"]}
        self.assertIsNone(sync.stale_global_registration(entry))

    def test_bundle_registration_with_a_missing_requested_name_is_stale(self) -> None:
        # exactly the Skills registration's real shape: some renamed/deleted
        pkg = self._skill_bundle(
            self.root / "bundle",
            ["create-skill", "github-cli", "tmux"],  # renamed from gh-cli/using-tmux
        )
        entry = {
            "path": str(pkg),
            "skills": ["create-skill", "gh-cli", "using-tmux", "az-devops"],
        }
        reason = sync.stale_global_registration(entry)
        self.assertIsNotNone(reason)
        self.assertIn("gh-cli", reason)
        self.assertIn("using-tmux", reason)
        self.assertIn("az-devops", reason)
        self.assertNotIn("create-skill", reason)

    def test_source_with_no_package_markers_at_all_is_stale(self) -> None:
        pkg = self.root / "empty"
        pkg.mkdir()
        (pkg / "README.md").write_text("nothing here\n")
        entry = {"path": str(pkg), "skills": []}
        reason = sync.stale_global_registration(entry)
        self.assertIsNotNone(reason)
        self.assertIn("no longer contains an APM package", reason)

    def test_root_level_skill_md_counts_as_a_package(self) -> None:
        pkg = self.root / "single-skill"
        pkg.mkdir()
        (pkg / "SKILL.md").write_text("---\nname: single-skill\ndescription: x\n---\n")
        entry = {"path": str(pkg), "skills": []}
        self.assertIsNone(sync.stale_global_registration(entry))

    def test_no_path_recorded_is_stale(self) -> None:
        self.assertIsNotNone(sync.stale_global_registration({}))

    def test_flow_style_skills_value_fails_closed_not_a_crash(self) -> None:
        # apm.yml's own emitter always writes a block list, but a
        # hand-edited or foreign-tool-written manifest could carry
        # `skills: [a, b, c]` on one line -- parse_global_local_packages
        # then stores the *raw string* "[a, b, c]" under "skills" rather
        # than a real list, since only the block-list shape is parsed
        # (#15 review). stale_global_registration() must not crash on
        # that (the prior `assert isinstance(requested, list)` would
        # raise AssertionError, and asserts are also stripped under -O);
        # it must fail closed instead.
        pkg = self._skill_bundle(self.root / "bundle", ["tmux"])
        entry = {"path": str(pkg), "skills": "[tmux, github-cli]"}
        reason = sync.stale_global_registration(entry)
        self.assertIsNotNone(reason)
        self.assertIn("skills", reason.lower())

    def test_non_list_non_string_skills_value_fails_closed(self) -> None:
        pkg = self._skill_bundle(self.root / "bundle", ["tmux"])
        entry = {"path": str(pkg), "skills": {"not": "a list"}}
        reason = sync.stale_global_registration(entry)
        self.assertIsNotNone(reason)
