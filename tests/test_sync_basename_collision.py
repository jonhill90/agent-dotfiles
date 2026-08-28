"""Tests for basename-collision detection across global manifest registrations.

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


class BasenameCollisionTests(unittest.TestCase):
    """#15 review: APM's local cache (~/.apm/apm_modules/_local/<name>)
    and its compiled apm:source marker names are keyed by
    Path(local_path).name only -- not the full path. Two distinct
    registrations that happen to share a basename collide in that one
    cache slot regardless of whether either individually passes
    stale_global_registration(). This is real, not hypothetical: the
    actual global manifest that motivated #14 has two different stale
    temp-directory registrations that both end in `/repo`."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_no_collision_when_all_basenames_are_distinct(self) -> None:
        entries = [
            {"path": "/tmp/build-aaa/repo-one"},
            {"path": "/tmp/build-bbb/repo-two"},
        ]
        self.assertEqual(sync.basename_collisions(entries), {})

    def test_two_stale_temp_paths_sharing_basename_repo_collide(self) -> None:
        # the exact real shape: two different tempfile-style directories
        # that both happen to end in a subdirectory literally named "repo"
        entries = [
            {"path": "/tmp/build-a1b2c3d4/repo", "skills": ["github-cli"]},
            {"path": "/tmp/build-e5f6a7b8/repo", "skills": ["github-cli"]},
        ]
        collisions = sync.basename_collisions(entries)
        self.assertEqual(set(collisions), {"repo"})
        self.assertEqual(
            sorted(collisions["repo"]),
            ["/tmp/build-a1b2c3d4/repo", "/tmp/build-e5f6a7b8/repo"],
        )

    def test_stale_and_legitimate_entries_sharing_a_basename_still_collide(self) -> None:
        # the danger isn't limited to two stale entries -- a legitimate,
        # currently-valid registration sharing a basename with a stale one
        # is exactly as unsafe to "just apm uninstall the stale one" against,
        # because the cache slot and source marker name are shared.
        entries = [
            {"path": "/home/example/projects/widget"},
            {"path": "/tmp/build-zzzz/widget"},
        ]
        collisions = sync.basename_collisions(entries)
        self.assertEqual(set(collisions), {"widget"})

    def test_two_legitimate_entries_sharing_a_basename_still_collide(self) -> None:
        # even two otherwise-fine packages collide if named the same
        entries = [
            {"path": "/home/example/projects/widget"},
            {"path": "/home/example/other-projects/widget"},
        ]
        collisions = sync.basename_collisions(entries)
        self.assertEqual(set(collisions), {"widget"})

    def test_entry_without_a_path_is_ignored_not_a_crash(self) -> None:
        entries = [{"skills": ["x"]}, {"path": "/tmp/build-aaa/repo"}]
        self.assertEqual(sync.basename_collisions(entries), {})

    def test_against_the_real_incident_shape(self) -> None:
        entries = sync.parse_global_local_packages(
            SYNTHETIC_GLOBAL_MANIFEST
        )
        # this particular fixture has no collision (all four basenames
        # differ) -- confirms the detector is not a false-positive trap
        self.assertEqual(sync.basename_collisions(entries), {})

    def test_against_a_manifest_with_the_real_two_tmp_path_collision(self) -> None:
        # this is the shape the real manifest actually had: two
        # tempfile-style local packages both landing on a "repo" leaf
        manifest = (
            "dependencies:\n"
            "  apm:\n"
            "    - path: /tmp/build-a1b2c3d4/repo\n"
            "      skills:\n"
            "        - github-cli\n"
            "        - memory-conventions\n"
            "    - path: /tmp/build-e5f6a7b8/repo\n"
            "      skills:\n"
            "        - github-cli\n"
            "        - memory-conventions\n"
        )
        entries = sync.parse_global_local_packages(manifest)
        collisions = sync.basename_collisions(entries)
        self.assertEqual(set(collisions), {"repo"})
        self.assertEqual(len(collisions["repo"]), 2)

class LocalBasenameCollisionSyncTests(SyncTestCase):
    """Sync.local_basename_collisions() (#15): reads the global manifest
    the same way stale_global_registrations() does."""

    def _write_global_manifest(self, body: str) -> None:
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True, exist_ok=True)
        (apm_dir / "apm.yml").write_text(body, encoding="utf-8")

    def test_empty_when_no_global_manifest_exists(self) -> None:
        self.assertEqual(self.syncer.local_basename_collisions(), {})

    def test_finds_the_two_path_same_basename_collision(self) -> None:
        self._write_global_manifest(
            "dependencies:\n"
            "  apm:\n"
            "    - path: /tmp/build-a1b2c3d4/repo\n"
            "      skills:\n"
            "        - github-cli\n"
            "    - path: /tmp/build-e5f6a7b8/repo\n"
            "      skills:\n"
            "        - github-cli\n"
        )
        collisions = self.syncer.local_basename_collisions()
        self.assertEqual(set(collisions), {"repo"})
        self.assertEqual(len(collisions["repo"]), 2)

    def test_no_collision_among_distinct_basenames(self) -> None:
        self._write_global_manifest(
            "dependencies:\n"
            "  apm:\n"
            "    - path: /tmp/build-aaa/alpha\n"
            "    - path: /tmp/build-bbb/beta\n"
        )
        self.assertEqual(self.syncer.local_basename_collisions(), {})

class StatusDoctorBasenameCollisionReportingTests(SyncTestCase):
    """status()/doctor() must name every colliding full path and the
    shared basename (#15) -- not just say "a collision exists"."""

    def _write_colliding_manifest(self) -> None:
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True, exist_ok=True)
        (apm_dir / "apm.yml").write_text(
            "dependencies:\n"
            "  apm:\n"
            "    - path: /tmp/build-a1b2c3d4/repo\n"
            "      skills:\n"
            "        - github-cli\n"
            "    - path: /tmp/build-e5f6a7b8/repo\n"
            "      skills:\n"
            "        - github-cli\n"
        )

    def test_status_names_the_shared_basename_and_both_full_paths(self) -> None:
        import contextlib
        import io

        self._write_colliding_manifest()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.syncer.status()
        out = buf.getvalue()
        self.assertIn("[basename-collision]", out)
        self.assertIn("repo", out)
        self.assertIn("/tmp/build-a1b2c3d4/repo", out)
        self.assertIn("/tmp/build-e5f6a7b8/repo", out)
        self.assertNotEqual(rc, 0)

    def test_doctor_names_the_shared_basename_and_both_full_paths(self) -> None:
        self._write_colliding_manifest()
        checks = dict(self.syncer.doctor_checks(env={}))
        self.assertIn("local-registration-basename-collisions", checks)
        ok, message = checks["local-registration-basename-collisions"]
        self.assertFalse(ok)
        self.assertIn("/tmp/build-a1b2c3d4/repo", message)
        self.assertIn("/tmp/build-e5f6a7b8/repo", message)

    def test_doctor_is_clean_without_a_collision(self) -> None:
        checks = dict(self.syncer.doctor_checks(env={}))
        ok, _ = checks["local-registration-basename-collisions"]
        self.assertTrue(ok)

class ApplyFailsClosedOnBasenameCollisionTests(SyncTestCase):
    """apply() must remain fail-closed when a basename collision exists,
    even if neither colliding registration is individually "stale" per
    stale_global_registration() (#15) -- the collision itself is the
    hazard, independent of either entry's own validity."""

    def _write_colliding_manifest_of_two_legitimate_entries(self) -> None:
        # both otherwise "fine" (no staleness reason on their own) --
        # proves the collision check is independent of staleness
        first = self.home / "projects-a" / "widget"
        first.mkdir(parents=True)
        (first / "apm.yml").write_text("name: widget\nversion: 0.1.0\n")
        second = self.home / "projects-b" / "widget"
        second.mkdir(parents=True)
        (second / "apm.yml").write_text("name: widget\nversion: 0.1.0\n")
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True, exist_ok=True)
        (apm_dir / "apm.yml").write_text(
            "dependencies:\n"
            "  apm:\n"
            f"    - path: {first}\n"
            f"    - path: {second}\n"
        )
        return first, second

    def test_apply_never_calls_apm_on_a_collision_alone(self) -> None:
        self._write_colliding_manifest_of_two_legitimate_entries()
        # sanity: neither entry is individually stale
        self.assertEqual(self.syncer.stale_global_registrations(), [])
        self.assertTrue(self.syncer.local_basename_collisions())

        def runner(cmd, check=False):
            raise AssertionError("apm must not run while a basename collision exists")

        self.syncer.runner = runner
        rc = self.syncer.apply()
        self.assertNotEqual(rc, 0)

    def test_apply_names_both_colliding_paths_in_its_error(self) -> None:
        import contextlib
        import io

        first, second = self._write_colliding_manifest_of_two_legitimate_entries()
        self.syncer.runner = lambda cmd, check=False: (_ for _ in ()).throw(
            AssertionError("apm must not run")
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.syncer.apply()
        out = buf.getvalue()
        self.assertIn(str(first), out)
        self.assertIn(str(second), out)
