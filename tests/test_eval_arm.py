"""Tests for per-arm eval configuration (scripts/eval_arm.py).

The §4 ladder needs a run with a candidate present and an otherwise
identical run with it absent. Both levers live in user-scope configuration
that the harness also uses for real work, so the mechanism moves files
aside and must put every one of them back byte-identically — an eval that
leaves a harness stripped is worse than an eval not run.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import eval_arm  # noqa: E402


class ArmTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.state = Path(self.tmp.name) / "arm-state.json"
        for rel, body in (
            (".copilot/AGENTS.md", "policy with the second opinion sentence"),
            (".copilot/copilot-instructions.md", "same policy again"),
            (".claude/CLAUDE.md", "claude policy"),
        ):
            path = self.home / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        skills = self.home / ".agents" / "skills" / "sanity-check"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: sanity-check\n---\n", encoding="utf-8")


class StashRestoreTests(ArmTestCase):
    def test_stash_removes_instructions_and_skills_then_restores(self) -> None:
        instructions = self.home / ".copilot" / "AGENTS.md"
        skills = self.home / ".agents" / "skills"
        before = instructions.read_text(encoding="utf-8")

        eval_arm.stash("copilot", self.home, self.state)
        self.assertFalse(instructions.exists(), "instruction file still readable")
        self.assertFalse(skills.exists(), "skills path still readable")

        eval_arm.restore(self.state)
        self.assertTrue(instructions.is_file())
        self.assertEqual(instructions.read_text(encoding="utf-8"), before)
        self.assertTrue((skills / "sanity-check" / "SKILL.md").is_file())

    def test_restore_detects_a_corrupted_payload(self) -> None:
        eval_arm.stash("copilot", self.home, self.state)
        stashed = next(Path(self.tmp.name).rglob("*" + eval_arm.SUFFIX))
        target = stashed if stashed.is_file() else next(stashed.rglob("*"))
        target.write_text("tampered", encoding="utf-8")
        with self.assertRaises(eval_arm.RestoreError):
            eval_arm.restore(self.state)

    def test_restore_is_idempotent(self) -> None:
        eval_arm.stash("copilot", self.home, self.state)
        eval_arm.restore(self.state)
        eval_arm.restore(self.state)  # must not raise
        self.assertTrue((self.home / ".copilot" / "AGENTS.md").is_file())

    def test_second_stash_refuses_while_one_is_outstanding(self) -> None:
        eval_arm.stash("copilot", self.home, self.state)
        with self.assertRaises(eval_arm.StashError):
            eval_arm.stash("copilot", self.home, self.state)

    def test_outstanding_reports_an_unrestored_stash(self) -> None:
        self.assertFalse(eval_arm.outstanding(self.state))
        eval_arm.stash("copilot", self.home, self.state)
        self.assertTrue(eval_arm.outstanding(self.state))
        eval_arm.restore(self.state)
        self.assertFalse(eval_arm.outstanding(self.state))

    def test_copilot_stashes_both_of_its_instruction_files(self) -> None:
        """Copilot reads AGENTS.md *and* copilot-instructions.md; leaving
        either behind leaves the candidate in context and the arm measures
        nothing."""
        eval_arm.stash("copilot", self.home, self.state)
        self.assertFalse((self.home / ".copilot" / "AGENTS.md").exists())
        self.assertFalse((self.home / ".copilot" / "copilot-instructions.md").exists())

    def test_absent_paths_are_skipped_not_fatal(self) -> None:
        (self.home / ".claude" / "CLAUDE.md").unlink()
        eval_arm.stash("claude", self.home, self.state)
        eval_arm.restore(self.state)
        self.assertFalse((self.home / ".claude" / "CLAUDE.md").exists())

    def test_unknown_harness_is_rejected(self) -> None:
        with self.assertRaises(eval_arm.StashError):
            eval_arm.stash("emacs", self.home, self.state)


if __name__ == "__main__":
    unittest.main()


class OverlayArmTests(ArmTestCase):
    """Isolating delivery surface needs an arm that removes ONLY the
    candidate's user-scope copy, leaving the rest of the deployed
    configuration intact. `bare` cannot do it: it strips everything, so
    surface and instruction volume move together (#87)."""

    def setUp(self) -> None:
        super().setUp()
        root = self.home / ".copilot" / "AGENTS.md"
        root.write_text(
            "# canonical\n\ncore policy\n\n"
            + eval_arm.OVERLAY_BEGIN
            + "\n\nthe candidate sentence\n\n"
            + eval_arm.OVERLAY_END
            + "\n",
            encoding="utf-8",
        )

    def test_no_overlay_removes_only_the_overlay_block(self) -> None:
        root = self.home / ".copilot" / "AGENTS.md"
        eval_arm.stash("copilot", self.home, self.state, arm="no-overlay")
        text = root.read_text(encoding="utf-8")
        self.assertIn("core policy", text)
        self.assertNotIn("the candidate sentence", text)
        self.assertTrue((self.home / ".agents" / "skills").is_dir())

    def test_restore_puts_the_overlay_back_byte_identically(self) -> None:
        root = self.home / ".copilot" / "AGENTS.md"
        before = root.read_text(encoding="utf-8")
        eval_arm.stash("copilot", self.home, self.state, arm="no-overlay")
        eval_arm.restore(self.state)
        self.assertEqual(root.read_text(encoding="utf-8"), before)

    def test_bare_still_strips_everything(self) -> None:
        eval_arm.stash("copilot", self.home, self.state, arm="bare")
        self.assertFalse((self.home / ".copilot" / "AGENTS.md").exists())
        eval_arm.restore(self.state)
