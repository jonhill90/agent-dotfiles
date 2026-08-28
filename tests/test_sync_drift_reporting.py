"""Tests for drift reporting between deployed and expected shared-path identities and projected instructions.

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


class SharedPathIdentityTests(SyncTestCase):
    """`doctor` passed by comparing names, and the wrapper owns nothing on the
    shared path, so a foreign skill installed under a managed name would be
    loaded by Codex, Copilot and Pi with every check green (#93).

    Identity is checked on the description rather than the whole file: APM
    rewrites relative links in the body when it installs, so byte-comparison
    reports a false mismatch on a legitimately deployed skill."""

    ALIAS = "skills-public"

    def _pin_alias(self) -> None:
        (self.repo / "apm.yml").write_text(
            "name: agent-dotfiles\nversion: 0.1.0\n"
            "dependencies:\n"
            "  apm:\n"
            "    - git: https://github.com/jonhill90/skills.git\n"
            "      ref: 069e2c475e875be1c23a31e7f5da08ffd58d655a\n"
            "      skills: [\"*\"]\n"
            f"      alias: {self.ALIAS}\n",
            encoding="utf-8",
        )

    def _deploy(self, name: str, description: str) -> None:
        d = self.home / ".agents" / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n\nbody\n",
            encoding="utf-8",
        )

    def _source(self, name: str, description: str, body: str = "body") -> None:
        d = self.home / ".apm" / "apm_modules" / self.ALIAS / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
            encoding="utf-8",
        )

    def test_substituted_skill_is_reported(self) -> None:
        """#35 reproduction: a foreign SKILL.md planted under a trusted
        rostered name, with the real source present in the local APM
        cache under its pinned alias -- must be reported, not silently
        cleared."""
        self._pin_alias()
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n", encoding="utf-8"
        )
        self._source("github-cli", "Manage GitHub via CLI.")
        self._deploy("github-cli", "Totally different thing from elsewhere.")
        mismatches = sync.Sync(self.repo, self.home).neutral_identity()
        self.assertEqual(mismatches, ["github-cli"])

    def test_matching_deployment_is_silent(self) -> None:
        self._pin_alias()
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n", encoding="utf-8"
        )
        self._source("github-cli", "Manage GitHub via CLI.")
        self._deploy("github-cli", "Manage GitHub via CLI.")
        self.assertEqual(sync.Sync(self.repo, self.home).neutral_identity(), [])

    def test_body_differences_do_not_trip_it(self) -> None:
        """APM rewrites relative links on install; that is not substitution."""
        self._pin_alias()
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n", encoding="utf-8"
        )
        self._source("github-cli", "Manage GitHub via CLI.", body="see [x](../y.md)")
        self._deploy("github-cli", "Manage GitHub via CLI.")
        self.assertEqual(sync.Sync(self.repo, self.home).neutral_identity(), [])

    def test_absent_skill_is_not_a_mismatch(self) -> None:
        self._pin_alias()
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n", encoding="utf-8"
        )
        self._source("github-cli", "Manage GitHub via CLI.")
        self.assertEqual(sync.Sync(self.repo, self.home).neutral_identity(), [])

    def test_unlocatable_source_is_reported_not_silently_cleared(self) -> None:
        """The #35 design constraint: if the new source of truth (the local
        APM cache, keyed by apm.yml's declared alias) cannot locate a
        rostered, deployed skill's source at all -- no matching alias
        pinned, or the cache entry missing -- that must fail closed like a
        mismatch, not silently report clean the way the dead
        `repo/skills` path used to."""
        self._pin_alias()
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n", encoding="utf-8"
        )
        self._deploy("github-cli", "Manage GitHub via CLI.")
        # Deliberately no self._source(): the cache entry the deployed copy
        # should trace back to was never created (or was pruned).
        mismatches = sync.Sync(self.repo, self.home).neutral_identity()
        self.assertEqual(len(mismatches), 1)
        self.assertIn("github-cli", mismatches[0])

    def test_no_pinned_alias_but_deployed_skill_fails_closed(self) -> None:
        """apm.yml declaring no skill-bundle dependency at all (no
        `dependencies.apm` block) must not be read as "nothing to verify"
        once a rostered name is actually deployed -- that is exactly the
        #35 shape, just with the source location unconfigured instead of
        merely absent."""
        (self.repo / "settings" / "default-skills.txt").write_text(
            "github-cli\n", encoding="utf-8"
        )
        self._deploy("github-cli", "Manage GitHub via CLI.")
        mismatches = sync.Sync(self.repo, self.home).neutral_identity()
        self.assertEqual(len(mismatches), 1)
        self.assertIn("github-cli", mismatches[0])

class ProjectedInstructionsDriftTests(SyncTestCase):
    """Skills had real drift detection (`neutral_drift`/`neutral_identity`);
    nothing compared deployed *instructions* against the repo, so a change
    like #27's to `instructions/overlays/copilot.md` could reach `main`
    while the deployed copy stayed stale and `status`/`doctor` stayed green
    (#36). Mirrors #37's shape: compare deployed content against a source
    that exists at check time, offline, with no change to `apply()`."""

    def _overlay(self, name: str, body: str) -> None:
        d = self.repo / "instructions" / "overlays"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(body, encoding="utf-8")

    def _deployed_root(self, rel: Path, overlay_text: str | None) -> Path:
        path = self.home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "core instructions\n"
        if overlay_text is not None:
            text += (
                "\n" + sync.OVERLAY_BEGIN + "\n\n" + overlay_text
                + "\n\n" + sync.OVERLAY_END + "\n"
            )
        path.write_text(text, encoding="utf-8")
        return path

    def test_stale_overlay_is_reported(self) -> None:
        """#36 reproduction: the repo's overlay moved on but the deployed
        copy still carries the old text."""
        self._overlay("copilot", "# Copilot Overlay\n\nnew rule.\n")
        path = self._deployed_root(sync.HARNESS_ROOT_FILES["copilot"][0], "old rule.")
        drifted = sync.Sync(self.repo, self.home).instructions_drift()
        self.assertEqual(drifted, [str(path)])

    def test_matching_deployment_is_silent(self) -> None:
        self._overlay("copilot", "# Copilot Overlay\n\nthe rule.\n")
        self._deployed_root(sync.HARNESS_ROOT_FILES["copilot"][0], "the rule.")
        self.assertEqual(
            sync.Sync(self.repo, self.home).instructions_drift(), []
        )

    def test_copilot_instructions_md_is_checked_independently_of_agents_md(self) -> None:
        """Copilot reads copilot-instructions.md, not AGENTS.md — a wrapper
        bug of exactly this kind was already caught once by an eval. A
        fresh AGENTS.md must not mask a stale copilot-instructions.md."""
        self._overlay("copilot", "# Copilot Overlay\n\nnew rule.\n")
        agents_md, copilot_instructions = sync.HARNESS_ROOT_FILES["copilot"]
        self._deployed_root(agents_md, "new rule.")
        stale = self._deployed_root(copilot_instructions, "old rule.")
        drifted = sync.Sync(self.repo, self.home).instructions_drift()
        self.assertEqual(drifted, [str(stale)])

    def test_never_applied_root_file_is_not_reported(self) -> None:
        """A machine that has never run `apply` has no deployed root file
        at all — that is `apply()`'s job to fill in, not this check's to
        flag; `status`/`doctor` already report it as missing separately."""
        self._overlay("copilot", "# Copilot Overlay\n\nnew rule.\n")
        self.assertEqual(
            sync.Sync(self.repo, self.home).instructions_drift(), []
        )

    def test_emptied_overlay_still_present_on_disk_is_reported(self) -> None:
        """The repo's overlay was emptied (should project nothing) but the
        deployed root file still carries the old block — a stale apply
        that a teardown-on-next-apply would fix, and this check must not
        stay silent about it in the meantime."""
        self._overlay("copilot", "# Copilot Overlay\n\nIntentionally empty.\n")
        path = self._deployed_root(sync.HARNESS_ROOT_FILES["copilot"][0], "old rule.")
        drifted = sync.Sync(self.repo, self.home).instructions_drift()
        self.assertEqual(drifted, [str(path)])

    def _write_pi_root(self, text: str) -> Path:
        pi_dir = self.home / ".pi" / "agent"
        pi_dir.mkdir(parents=True, exist_ok=True)
        path = pi_dir / "AGENTS.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_stale_pi_root_is_reported(self) -> None:
        path = self._write_pi_root(f"{sync.SYNC_MARKER}\n\nstale core\n\nstale overlay\n")
        drifted = sync.Sync(self.repo, self.home).instructions_drift()
        self.assertEqual(drifted, [str(path)])

    def test_matching_pi_root_is_silent(self) -> None:
        core = sync.strip_frontmatter(
            (self.repo / "instructions" / "global.instructions.md").read_text(
                encoding="utf-8"
            )
        )
        overlay = (self.repo / "instructions" / "overlays" / "pi.md").read_text(
            encoding="utf-8"
        )
        self._write_pi_root(
            f"{sync.SYNC_MARKER}\n\n{core.strip()}\n\n{overlay.strip()}\n"
        )
        self.assertEqual(sync.Sync(self.repo, self.home).instructions_drift(), [])

    def test_hand_authored_pi_root_is_not_reported(self) -> None:
        """No SYNC_MARKER means project_pi() itself refuses to touch the
        file; this check must not manage what apply() would not."""
        self._write_pi_root("hand-authored content, no marker\n")
        self.assertEqual(sync.Sync(self.repo, self.home).instructions_drift(), [])

    def test_status_reports_the_drift_as_an_issue(self) -> None:
        self._overlay("copilot", "# Copilot Overlay\n\nnew rule.\n")
        self._deployed_root(sync.HARNESS_ROOT_FILES["copilot"][0], "old rule.")
        self.assertEqual(sync.Sync(self.repo, self.home).status(), 1)

    def test_doctor_reports_the_drift(self) -> None:
        self._overlay("copilot", "# Copilot Overlay\n\nnew rule.\n")
        path = self._deployed_root(sync.HARNESS_ROOT_FILES["copilot"][0], "old rule.")
        checks = dict(sync.Sync(self.repo, self.home).doctor_checks(env={}))
        ok, detail = checks["instructions-drift"]
        self.assertFalse(ok)
        self.assertIn(str(path), detail)

    def test_doctor_is_clean_when_nothing_deployed(self) -> None:
        checks = dict(sync.Sync(self.repo, self.home).doctor_checks(env={}))
        ok, detail = checks["instructions-drift"]
        self.assertTrue(ok)
        self.assertIn("match the repo", detail)
