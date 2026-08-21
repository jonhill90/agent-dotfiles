"""Tests for scripts/pr_ci_state.py (issue #244).

Mocks `gh` at the subprocess boundary — a test that shells out to GitHub is
not one that stays green on a machine without a token, or reproducible on
demand. Each case in the docstring gets a test named after it.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pr_ci_state  # noqa: E402


def _completed(stdout="", stderr="", returncode=0):
    class _Result:
        pass

    r = _Result()
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


def _run_seq(responses):
    """Return a subprocess.run stand-in that yields `responses` in order,
    keyed by matching a substring of the joined gh argv."""

    def _run(cmd, **kwargs):
        argv = " ".join(cmd)
        for needle, result in responses:
            if needle in argv:
                return result
        raise AssertionError(f"unmocked gh call: {argv}")

    return _run


REPO_VIEW = ("repo view", _completed(json.dumps({"nameWithOwner": "jonhill90/agent-dotfiles"})))


class PositiveControlTest(unittest.TestCase):
    """Prove the check-suites query can see a suite that exists before any
    zero is trusted (brief's verification requirement)."""

    def test_sees_existing_passed_suite(self) -> None:
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "deadbeef",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([{"id": 1}]))),
            (
                "commits/deadbeef/check-runs",
                _completed(
                    json.dumps(
                        [{"name": "repository", "status": "completed", "conclusion": "success"}]
                    )
                ),
            ),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("1", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_CLEAN)
        self.assertEqual(verdict.case, "case-3-passed")


class CaseTests(unittest.TestCase):
    def test_case_1_conflicting_gets_zero_suites(self) -> None:
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "f6192f7",
                            "mergeable": "CONFLICTING",
                            "mergeStateStatus": "DIRTY",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([]))),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("231", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_ACTIONABLE)
        self.assertEqual(verdict.case, "case-1-conflicting-no-suite")
        self.assertIn("rebase", verdict.message)

    def test_case_2_mergeable_with_zero_suites_is_clean_not_conflicting(self) -> None:
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "abc123",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([]))),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("242", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_CLEAN)
        self.assertEqual(verdict.case, "case-2-mergeable-no-suite")
        self.assertNotIn("CONFLICT", verdict.message.upper())

    def test_case_3_pending(self) -> None:
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "abc123",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([{"id": 1}]))),
            (
                "commits/abc123/check-runs",
                _completed(
                    json.dumps([{"name": "repository", "status": "in_progress", "conclusion": None}])
                ),
            ),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("50", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_CLEAN)
        self.assertEqual(verdict.case, "case-3-pending")

    def test_case_4_failed_under_current_shape(self) -> None:
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "abc123",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([{"id": 1}]))),
            (
                "commits/abc123/check-runs",
                _completed(
                    json.dumps(
                        [{"name": "repository", "status": "completed", "conclusion": "failure"}]
                    )
                ),
            ),
            (
                "commits/mainsha/check-runs",
                _completed(
                    json.dumps(
                        [{"name": "repository", "status": "completed", "conclusion": "success"}]
                    )
                ),
            ),
            ("commits/main", _completed(json.dumps({"sha": "mainsha"}))),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("50", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_ACTIONABLE)
        self.assertEqual(verdict.case, "case-4-failed")
        self.assertIn("read the log", verdict.message)

    def test_case_5_stale_job_shape(self) -> None:
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "abc123",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "BEHIND",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([{"id": 1}]))),
            (
                "commits/abc123/check-runs",
                _completed(json.dumps([{"name": "test", "status": "completed", "conclusion": "failure"}])),
            ),
            (
                "commits/mainsha/check-runs",
                _completed(
                    json.dumps(
                        [
                            {
                                "name": "shell-suites (shard 0)",
                                "status": "completed",
                                "conclusion": "success",
                            }
                        ]
                    )
                ),
            ),
            ("commits/main", _completed(json.dumps({"sha": "mainsha"}))),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("432", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_ACTIONABLE)
        self.assertEqual(verdict.case, "case-5-stale-job-shape")
        self.assertIn("old main", verdict.message)

    def test_empty_base_baseline_is_not_treated_as_a_stale_match(self) -> None:
        """A base branch with zero check-runs of its own is 'no baseline',
        not 'nothing matches' — isdisjoint() against an empty set is
        trivially true, which would otherwise flag every real failure on a
        quiet base branch as stale."""
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "abc123",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([{"id": 1}]))),
            (
                "commits/abc123/check-runs",
                _completed(
                    json.dumps(
                        [{"name": "repository", "status": "completed", "conclusion": "failure"}]
                    )
                ),
            ),
            ("commits/mainsha/check-runs", _completed(json.dumps([]))),
            ("commits/main", _completed(json.dumps({"sha": "mainsha"}))),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("50", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_ACTIONABLE)
        self.assertEqual(verdict.case, "case-4-failed")

    def test_dirty_merge_state_alone_triggers_case_1_without_conflicting(self) -> None:
        """mergeStateStatus can report DIRTY a tick before mergeable catches
        up to CONFLICTING; either signal alone is enough."""
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "abc123",
                            "mergeable": "UNKNOWN",
                            "mergeStateStatus": "DIRTY",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([]))),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("50", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_ACTIONABLE)
        self.assertEqual(verdict.case, "case-1-conflicting-no-suite")

    def test_all_passed_is_clean(self) -> None:
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "abc123",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([{"id": 1}]))),
            (
                "commits/abc123/check-runs",
                _completed(
                    json.dumps(
                        [{"name": "repository", "status": "completed", "conclusion": "success"}]
                    )
                ),
            ),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("50", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_CLEAN)
        self.assertEqual(verdict.case, "case-3-passed")


class CouldNotMeasureTests(unittest.TestCase):
    """0 check-suites and 'API unreachable' must never look the same."""

    def test_api_failure_is_unmeasured_not_clean_or_conflicting(self) -> None:
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "abc123",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(stdout="", stderr="HTTP 503", returncode=1)),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("50", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_UNMEASURED)
        self.assertEqual(verdict.case, "could-not-measure")

    def test_unresolved_mergeable_state_is_unmeasured(self) -> None:
        responses = [
            REPO_VIEW,
            (
                "pr view",
                _completed(
                    json.dumps(
                        {
                            "headRefOid": "abc123",
                            "mergeable": "UNKNOWN",
                            "mergeStateStatus": "UNKNOWN",
                            "baseRefName": "main",
                        }
                    )
                ),
            ),
            ("check-suites", _completed(json.dumps([]))),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("50", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_UNMEASURED)
        self.assertNotEqual(verdict.case, "case-1-conflicting-no-suite")

    def test_pr_view_failure_is_unmeasured(self) -> None:
        responses = [
            REPO_VIEW,
            ("pr view", _completed(stdout="", stderr="pull request not found", returncode=1)),
        ]
        with patch("subprocess.run", side_effect=_run_seq(responses)):
            verdict = pr_ci_state.evaluate("999999", None)
        self.assertEqual(verdict.exit_code, pr_ci_state.EXIT_UNMEASURED)


if __name__ == "__main__":
    unittest.main()
