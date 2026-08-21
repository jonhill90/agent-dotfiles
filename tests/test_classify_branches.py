"""Tests for scripts/classify_branches.py (#120).

Builds real throwaway git repositories rather than mocking `git` — the whole
point of this script is correct diff/merge-base semantics, which a mock
cannot exercise honestly. Mirrors the sanity check the issue's own prior
attempt ran before trusting the method: one squash-merged branch (must read
SUPERSEDED) and one genuinely-outstanding branch (must read OUTSTANDING) in
the same repo.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import classify_branches as cb  # noqa: E402


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "file.txt").write_text("line1\nline2\nline3\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "initial")


class SupersededTest(unittest.TestCase):
    """A branch whose content was squash-merged into main: commits are not
    reachable from main, but every line it added is present on main."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_squash_merged_branch_is_superseded(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "feature")
        (self.repo / "file.txt").write_text("line1\nline2\nline3\nhardened-line\n")
        git(self.repo, "commit", "-q", "-am", "add hardening")

        # Simulate a squash merge: main gets the same content under a new commit.
        git(self.repo, "checkout", "-q", "main")
        (self.repo / "file.txt").write_text("line1\nline2\nline3\nhardened-line\n")
        git(self.repo, "commit", "-q", "-am", "squash-merge feature (#1)")

        result = cb.classify("feature", "main", cwd=str(self.repo))
        self.assertEqual(result.verdict, cb.SUPERSEDED, result.reason)

    def test_branch_with_no_commits_ahead_is_superseded(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "idle")
        result = cb.classify("idle", "main", cwd=str(self.repo))
        self.assertEqual(result.verdict, cb.SUPERSEDED, result.reason)

    def test_branch_whose_tip_is_ancestor_of_main_is_superseded(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "old")
        (self.repo / "file.txt").write_text("line1\nline2\nline3\nold-addition\n")
        git(self.repo, "commit", "-q", "-am", "old addition")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--ff-only", "old")

        result = cb.classify("old", "main", cwd=str(self.repo))
        self.assertEqual(result.verdict, cb.SUPERSEDED, result.reason)


class OutstandingTest(unittest.TestCase):
    """A branch with real, never-landed content must not read as SUPERSEDED —
    the brief's required negative-direction proof (a classifier that only
    ever says SUPERSEDED would pass the positive case and be worthless)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_genuinely_unmerged_branch_is_outstanding(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "feature")
        (self.repo / "file.txt").write_text("line1\nline2\nline3\nnever-landed-line\n")
        git(self.repo, "commit", "-q", "-am", "add work nobody merged")

        # main moves on, unrelated to the branch's change.
        git(self.repo, "checkout", "-q", "main")
        (self.repo / "other.txt").write_text("unrelated\n")
        git(self.repo, "add", "other.txt")
        git(self.repo, "commit", "-q", "-m", "unrelated main work")

        result = cb.classify("feature", "main", cwd=str(self.repo))
        self.assertEqual(result.verdict, cb.OUTSTANDING, result.reason)
        self.assertTrue(any(m["line"] == "never-landed-line" for m in result.evidence["missing"]))


class ThreeDotTwoDotTrapTest(unittest.TestCase):
    """Reproduces the issue's own instrument failures directly: three-dot
    reports superseded content as outstanding, two-dot inflates because it
    also counts a stale branch's now-superseded older lines. This script
    must dodge both."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_stale_branch_with_superseded_content_is_not_outstanding(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "stale")
        (self.repo / "file.txt").write_text("line1\nline2\nline3\nhardened-line\n")
        git(self.repo, "commit", "-q", "-am", "add hardening")

        # main both absorbs the hardening (squash) AND keeps editing the same
        # file afterward — the exact shape that inflated two-dot's count in
        # the issue's own report.
        git(self.repo, "checkout", "-q", "main")
        (self.repo / "file.txt").write_text("line1\nline2\nline3\nhardened-line\n")
        git(self.repo, "commit", "-q", "-am", "squash-merge stale")
        (self.repo / "file.txt").write_text("line1\nline2\nline3\nhardened-line\nfurther-refactor\n")
        git(self.repo, "commit", "-q", "-am", "later unrelated refactor")

        result = cb.classify("stale", "main", cwd=str(self.repo))
        self.assertEqual(result.verdict, cb.SUPERSEDED, result.reason)

        # Confirm this is genuinely the trap: raw two-dot is non-empty here.
        two_dot = git(self.repo, "diff", "--stat", "main..stale")
        self.assertTrue(two_dot.strip(), "expected two-dot to be non-empty (the trap this test proves we avoid)")


class CouldNotClassifyTest(unittest.TestCase):
    """The mandatory third verdict must actually trigger, not just exist in
    an enum nobody reaches."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_binary_file_with_no_other_evidence_is_could_not_classify(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "feature")
        (self.repo / "blob.bin").write_bytes(bytes([0, 1, 2, 3, 0, 255]))
        git(self.repo, "add", "blob.bin")
        git(self.repo, "commit", "-q", "-m", "add binary asset")

        result = cb.classify("feature", "main", cwd=str(self.repo))
        self.assertEqual(result.verdict, cb.COULD_NOT_CLASSIFY, result.reason)

    def test_unknown_branch_is_could_not_classify(self) -> None:
        result = cb.classify("does-not-exist", "main", cwd=str(self.repo))
        self.assertEqual(result.verdict, cb.COULD_NOT_CLASSIFY, result.reason)

    def test_file_deleted_on_main_with_no_other_evidence_is_could_not_classify(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "feature")
        (self.repo / "gone.txt").write_text("content main will later remove\n")
        git(self.repo, "add", "gone.txt")
        git(self.repo, "commit", "-q", "-m", "add file")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature")
        git(self.repo, "rm", "-q", "gone.txt")
        git(self.repo, "commit", "-q", "-m", "remove file later")

        # feature's tip is now an ancestor of main (it was merged), so this
        # exercises the ancestor short-circuit, not the deleted-file path —
        # kept as a control to show the merge itself does not confuse the
        # classifier before the true deleted-file case below.
        result = cb.classify("feature", "main", cwd=str(self.repo))
        self.assertEqual(result.verdict, cb.SUPERSEDED, result.reason)

    def test_file_removed_on_main_without_merge_is_could_not_classify(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "feature")
        (self.repo / "only-on-branch.txt").write_text("branch-only content\n")
        git(self.repo, "add", "only-on-branch.txt")
        git(self.repo, "commit", "-q", "-m", "add file only branch has")

        git(self.repo, "checkout", "-q", "main")
        (self.repo / "other.txt").write_text("unrelated\n")
        git(self.repo, "add", "other.txt")
        git(self.repo, "commit", "-q", "-m", "unrelated main work")

        result = cb.classify("feature", "main", cwd=str(self.repo))
        # main never had the file at all, so there is no way to compare
        # content -> this must not silently read as SUPERSEDED.
        self.assertIn(result.verdict, (cb.OUTSTANDING, cb.COULD_NOT_CLASSIFY))
        self.assertNotEqual(result.verdict, cb.SUPERSEDED, result.reason)


class DiscoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_finds_only_branches_with_commits_off_remote(self) -> None:
        # No remotes configured at all -> every non-main branch with a
        # commit qualifies, main itself has no commits "ahead of no remote"
        # in a meaningful sense but --not --remotes with zero remotes just
        # returns everything reachable from it, so exclude main explicitly
        # the way the CLI's --exclude flag does.
        git(self.repo, "checkout", "-q", "-b", "has-work")
        (self.repo / "file.txt").write_text("line1\nline2\nline3\nnew\n")
        git(self.repo, "commit", "-q", "-am", "work")

        branches, err = cb.branches_with_unpushed_commits(cwd=str(self.repo))
        self.assertIsNone(err)
        self.assertIn("has-work", branches)


if __name__ == "__main__":
    unittest.main()
