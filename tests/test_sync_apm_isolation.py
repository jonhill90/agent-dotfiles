"""Tests that apm subprocess calls are isolated to the sandboxed HOME.

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


class ApmSubprocessIsolationTests(SyncTestCase):
    """A real incident during #9 review: an "isolated" Sync(home=...) test
    run still drove real `apm` against the real machine's $HOME, because
    subprocess calls resolve their own environment independently of
    self.home. Every call the default runner makes must see
    HOME=str(self.home), not the process's real environment -- otherwise
    the `home=` constructor parameter is a lie for anything that shells
    out, which is exactly what happened."""

    def test_default_runner_passes_the_isolated_home_to_apm(self) -> None:
        calls = []

        def fake_subprocess_run(cmd, check=False, env=None):
            calls.append((cmd, env))

            class R:
                returncode = 0

            return R()

        with mock.patch("sync.subprocess.run", fake_subprocess_run):
            self.syncer.runner(["apm", "status"], check=False)

        self.assertEqual(len(calls), 1)
        _, env = calls[0]
        self.assertIsNotNone(env)
        self.assertEqual(env["HOME"], str(self.home))
        self.assertNotEqual(env["HOME"], str(Path.home()))

    def test_apply_never_launches_apm_against_the_real_home(self) -> None:
        seen_homes = []

        def fake_subprocess_run(cmd, check=False, env=None):
            seen_homes.append(env.get("HOME") if env else None)

            class R:
                returncode = 0

            return R()

        with mock.patch("sync.subprocess.run", fake_subprocess_run):
            self.syncer.apply()

        self.assertTrue(seen_homes)  # install + compile both ran
        for home in seen_homes:
            self.assertEqual(home, str(self.home))
            self.assertNotEqual(home, str(Path.home()))

    def test_remove_never_launches_apm_against_the_real_home(self) -> None:
        self.syncer.state["repo"] = str(self.repo)
        seen_homes = []

        def fake_subprocess_run(cmd, check=False, env=None):
            seen_homes.append(env.get("HOME") if env else None)

            class R:
                returncode = 0

            return R()

        with mock.patch("sync.subprocess.run", fake_subprocess_run):
            self.syncer.remove()

        self.assertTrue(seen_homes)
        for home in seen_homes:
            self.assertEqual(home, str(self.home))

    def test_default_runner_is_the_isolated_wrapper_not_raw_subprocess_run(self) -> None:
        # #14: a direct, structural guard beside the behavioural ones
        # above. If a future edit ever reverts __init__ to
        # `self.runner = subprocess.run`, this fails immediately and
        # explains why, rather than only failing indirectly (and
        # possibly not at all, in a test that happens to mock
        # self.syncer.runner itself and never exercises the default).
        fresh = sync.Sync(repo_root=self.repo, home=self.home)
        self.assertEqual(fresh.runner, fresh._run_apm)  # bound methods compare by (func, instance)
        self.assertEqual(fresh.runner.__func__, sync.Sync._run_apm)
        self.assertNotEqual(fresh.runner.__func__, subprocess.run)
