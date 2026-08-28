"""Tests for reporting pinned skill sources and detecting stale pins.

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


class PinnedSourceReportingTests(SyncTestCase):
    def test_pinned_skill_sources_reads_the_global_lockfile(self) -> None:
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True)
        (apm_dir / "apm.lock.yaml").write_text(
            "lockfile_version: '1'\n"
            "dependencies:\n"
            "- repo_url: _local/repo\n"
            "  name: agent-dotfiles\n"
            "  source: local\n"
            "- repo_url: jonhill90/skills\n"
            "  name: skills-public\n"
            "  resolved_commit: 069e2c475e875be1c23a31e7f5da08ffd58d655a\n"
            "- repo_url: jonhill90/skills-private\n"
            "  name: skills-private\n"
            "  resolved_commit: b203b1ebf2c2eb35808443ba76cd22aadecf76e7\n",
            encoding="utf-8",
        )
        self.assertEqual(
            self.syncer.pinned_skill_sources(),
            [
                {
                    "name": "skills-public",
                    "repo_url": "jonhill90/skills",
                    "resolved_commit": "069e2c475e875be1c23a31e7f5da08ffd58d655a",
                },
                {
                    "name": "skills-private",
                    "repo_url": "jonhill90/skills-private",
                    "resolved_commit": "b203b1ebf2c2eb35808443ba76cd22aadecf76e7",
                },
            ],
        )

    def test_pinned_skill_sources_empty_when_no_lockfile(self) -> None:
        self.assertEqual(self.syncer.pinned_skill_sources(), [])

    def test_status_prints_a_source_line_per_pinned_dependency(self) -> None:
        import contextlib
        import io

        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True)
        (apm_dir / "apm.lock.yaml").write_text(
            "dependencies:\n"
            "- repo_url: jonhill90/skills\n"
            "  name: skills-public\n"
            "  resolved_commit: 069e2c475e875be1c23a31e7f5da08ffd58d655a\n",
            encoding="utf-8",
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.syncer.status()
        self.assertIn(
            "[source] skills-public: jonhill90/skills@069e2c47", buf.getvalue()
        )

class StaleSkillSourcePinTests(SyncTestCase):
    """#41: `apm install -g` has been observed to exit 0 on its first
    invocation after a pin bump while resolving the *previous* commit
    from cache, then resolve correctly on an identical second call.
    apply() must not report success for a state it did not reach."""

    def _pin_apm_yml(self) -> None:
        (self.repo / "apm.yml").write_text(
            "name: agent-dotfiles\nversion: 0.1.0\n"
            "dependencies:\n"
            "  apm:\n"
            "    - git: https://github.com/jonhill90/skills.git\n"
            "      ref: 0ebaf91e6b2adc7ab2ac6e9aa86c8ddb099afd94\n"
            '      skills: ["*"]\n'
            "      alias: skills-public\n"
            "  mcp: []\n",
            encoding="utf-8",
        )

    def _write_lockfile(self, sha: str) -> None:
        apm_dir = self.home / ".apm"
        apm_dir.mkdir(parents=True, exist_ok=True)
        (apm_dir / "apm.lock.yaml").write_text(
            "dependencies:\n"
            "- repo_url: jonhill90/skills\n"
            "  name: skills-public\n"
            f"  resolved_commit: {sha}\n",
            encoding="utf-8",
        )

    def test_stale_skill_source_pins_flags_a_mismatched_lockfile(self) -> None:
        self._pin_apm_yml()
        self._write_lockfile("069e2c475e875be1c23a31e7f5da08ffd58d655a")
        self.assertEqual(
            self.syncer.stale_skill_source_pins(),
            {
                "skills-public": (
                    "0ebaf91e6b2adc7ab2ac6e9aa86c8ddb099afd94",
                    "069e2c475e875be1c23a31e7f5da08ffd58d655a",
                )
            },
        )

    def test_stale_skill_source_pins_empty_when_matched(self) -> None:
        self._pin_apm_yml()
        self._write_lockfile("0ebaf91e6b2adc7ab2ac6e9aa86c8ddb099afd94")
        self.assertEqual(self.syncer.stale_skill_source_pins(), {})

    def test_apply_redrives_a_single_stale_resolve_and_still_reports_success(
        self,
    ) -> None:
        # Reproduces #41: the first `apm install -g` writes a lockfile
        # holding the *previous* commit (as if resolved from a stale
        # cache); the second, identical call writes the correct one. A
        # single `sync.py apply` invocation must still end up at the
        # pinned commit and report success -- not the stale one.
        self._pin_apm_yml()
        install_calls = {"n": 0}

        def runner(cmd, check=False):
            if cmd[:2] == ["apm", "install"]:
                install_calls["n"] += 1
                sha = (
                    "069e2c475e875be1c23a31e7f5da08ffd58d655a"
                    if install_calls["n"] == 1
                    else "0ebaf91e6b2adc7ab2ac6e9aa86c8ddb099afd94"
                )
                self._write_lockfile(sha)

            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        self.assertEqual(self.syncer.apply(), 0)
        self.assertEqual(install_calls["n"], 2)
        self.assertEqual(self.syncer.stale_skill_source_pins(), {})

    def test_status_flags_a_stale_pin_left_over_between_applies(self) -> None:
        # A lockfile can go stale between applies too (apm.yml bumped,
        # `status` run before the next `apply`) -- `status` must not
        # silently agree with it.
        import contextlib
        import io

        self._pin_apm_yml()
        self._write_lockfile("069e2c475e875be1c23a31e7f5da08ffd58d655a")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = self.syncer.status()
        output = buf.getvalue()
        self.assertIn(
            "[stale-pin] skills-public: resolved 069e2c47, "
            "apm.yml pins 0ebaf91e",
            output,
        )
        self.assertNotEqual(result, 0)

    def test_apply_fails_closed_when_the_retry_is_also_stale(self) -> None:
        # If a redrive does not fix it, this is no longer the known
        # one-retry cache-miss pattern -- apply must fail closed rather
        # than report the unreached stale commit as installed.
        self._pin_apm_yml()
        install_calls = {"n": 0}

        def runner(cmd, check=False):
            if cmd[:2] == ["apm", "install"]:
                install_calls["n"] += 1
                self._write_lockfile("069e2c475e875be1c23a31e7f5da08ffd58d655a")

            class R:
                returncode = 0

            return R()

        self.syncer.runner = runner
        self.assertNotEqual(self.syncer.apply(), 0)
        self.assertEqual(install_calls["n"], 2)
