"""Tests for scripts/docs_lint.py. Every fixture is a throwaway tempdir
git repo -- this suite never touches this repo's own docs/ tree."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

P = (Path(__file__).parent.parent / "scripts" / "docs_lint.py").resolve()
spec = importlib.util.spec_from_file_location("docs_lint", P)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

TOMBSTONE = (
    "# name\n\n"
    "Status: superseded routing location. Canonical content moved, not copied.\n\n"
    "Continue to [name](canonical/name.md).\n"
)


def git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)


def git_add(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)


class UnclassifiedRootFiles(unittest.TestCase):
    def test_classified_tree_is_clean(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs" / "canonical").mkdir(parents=True)
            (root / "docs" / "canonical" / "a.md").write_text("A\n")
            self.assertEqual(m.check_unclassified_root_files(root), [])

    def test_loose_non_tombstone_root_file_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "loose.md").write_text("just some prose\n")
            violations = m.check_unclassified_root_files(root)
            self.assertEqual(len(violations), 1)
            self.assertIn("docs/loose.md", violations[0])

    def test_valid_tombstone_is_not_a_violation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs" / "canonical").mkdir(parents=True)
            (root / "docs" / "canonical" / "name.md").write_text("real content\n")
            (root / "docs" / "name.md").write_text(TOMBSTONE)
            self.assertEqual(m.check_unclassified_root_files(root), [])

    def test_tombstone_whose_target_does_not_exist_is_a_violation(self):
        # A broken routing stub is worse than a plain unclassified file --
        # it looks routed and isn't. Never silently exempted.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "name.md").write_text(TOMBSTONE)  # no canonical/name.md
            violations = m.check_unclassified_root_files(root)
            self.assertEqual(len(violations), 1)
            self.assertIn("docs/name.md", violations[0])

    def test_tombstone_whose_target_is_outside_classified_subdirs_is_a_violation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "elsewhere.md").write_text("real but unclassified\n")
            (root / "docs" / "name.md").write_text(
                "# name\n\n"
                "Status: superseded routing location. Canonical content moved, not copied.\n\n"
                "Continue to [name](elsewhere.md).\n")
            violations = m.check_unclassified_root_files(root)
            # Two real violations: elsewhere.md is itself an unclassified
            # root file, AND name.md's tombstone doesn't count because its
            # target isn't under a classified subdirectory either.
            self.assertEqual(len(violations), 2)

    def test_wrong_status_line_is_not_recognized_as_a_tombstone(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs" / "canonical").mkdir(parents=True)
            (root / "docs" / "canonical" / "name.md").write_text("real\n")
            (root / "docs" / "name.md").write_text(
                "# name\n\nStatus: moved, trust me.\n\nSee canonical/name.md.\n")
            violations = m.check_unclassified_root_files(root)
            self.assertEqual(len(violations), 1)

    def test_allowlisted_root_file_is_not_a_violation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "index.md").write_text("# Documentation\n")
            (root / "docs" / ".gitkeep").write_text("")
            self.assertEqual(m.check_unclassified_root_files(root), [])

    def test_unrecognized_subdirectory_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs" / "scratch").mkdir(parents=True)
            violations = m.check_unclassified_root_files(root)
            self.assertEqual(len(violations), 1)
            self.assertIn("docs/scratch/", violations[0])


class NoStateFilesInDocs(unittest.TestCase):
    def test_clean_tree_has_no_violations(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs" / "canonical").mkdir(parents=True)
            (root / "docs" / "canonical" / "a.md").write_text("A\n")
            self.assertEqual(m.check_no_state_files_in_docs(root), [])

    def test_json_anywhere_under_docs_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs" / "canonical").mkdir(parents=True)
            (root / "docs" / "canonical" / "state.json").write_text("{}")
            violations = m.check_no_state_files_in_docs(root)
            self.assertEqual(len(violations), 1)
            self.assertIn("state.json", violations[0])

    def test_jsonl_fails_too(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "log.jsonl").write_text("")
            violations = m.check_no_state_files_in_docs(root)
            self.assertEqual(len(violations), 1)


class ZeroDuplicateChecksums(unittest.TestCase):
    def test_unique_files_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_repo(root)
            (root / "a.md").write_text("alpha\n")
            (root / "b.md").write_text("beta\n")
            git_add(root)
            self.assertEqual(m.check_zero_duplicate_checksums(root), [])

    def test_byte_identical_tracked_files_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_repo(root)
            (root / "a.md").write_text("same content\n")
            (root / "b.md").write_text("same content\n")
            git_add(root)
            violations = m.check_zero_duplicate_checksums(root)
            self.assertEqual(len(violations), 1)
            self.assertIn("a.md", violations[0])
            self.assertIn("b.md", violations[0])

    def test_symlink_alias_is_not_a_duplicate(self):
        # CLAUDE.md -> AGENTS.md, this repo's own real shape.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_repo(root)
            (root / "AGENTS.md").write_text("shared content\n")
            (root / "CLAUDE.md").symlink_to("AGENTS.md")
            git_add(root)
            self.assertEqual(m.check_zero_duplicate_checksums(root), [])

    def test_untracked_duplicate_is_not_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_repo(root)
            (root / "a.md").write_text("same\n")
            git_add(root)
            (root / "b.md").write_text("same\n")  # never git add'ed
            self.assertEqual(m.check_zero_duplicate_checksums(root), [])


class Run(unittest.TestCase):
    def test_clean_repo_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_repo(root)
            (root / "docs" / "canonical").mkdir(parents=True)
            (root / "docs" / "canonical" / "a.md").write_text("A\n")
            git_add(root)
            code, lines = m.run(root)
            self.assertEqual(code, 0)
            self.assertTrue(any("all three rules hold" in l for l in lines))

    def test_violations_across_all_three_rules_are_all_reported_together(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git_repo(root)
            (root / "docs").mkdir()
            (root / "docs" / "loose.md").write_text("dup\n")
            (root / "docs" / "state.json").write_text("{}")
            (root / "other-dup.md").write_text("dup\n")
            git_add(root)
            code, lines = m.run(root)
            self.assertEqual(code, 1)
            joined = "\n".join(lines)
            self.assertIn("unclassified root file", joined)
            self.assertIn("state file under docs/", joined)
            self.assertIn("full-text duplicate", joined)


if __name__ == "__main__":
    unittest.main()
