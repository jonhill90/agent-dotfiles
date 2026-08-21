"""Tests for scripts/pr_ci_state.py (agent-dotfiles#244).

The bug the issue names is a conflation: "zero check suites" and "could not
reach the API" must never land in the same branch. Every test here drives
`classify()` through a fake `gh` layer so the five states -- and the
could-not-measure path, which is not one of the five -- are each provoked
deliberately rather than inferred from a live poll.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pr_ci_state  # noqa: E402


PR_JSON = {
    "mergeable": "MERGEABLE",
    "mergeStateStatus": "CLEAN",
    "headRefOid": "deadbeef",
    "number": 1,
    "url": "https://github.com/o/r/pull/1",
}


def _pr(**overrides):
    data = dict(PR_JSON)
    data.update(overrides)
    return data


class ClassifyTests(unittest.TestCase):
    def _patch(self, pr, suites, runs, job_names=frozenset()):
        def fake_gh_json(args):
            if args[:2] == ["pr", "view"]:
                return pr
            if "check-suites" in args[-1]:
                return {"check_suites": suites}
            if "check-runs" in args[-1]:
                return {"check_runs": runs}
            if args[-1].endswith(".github/workflows"):
                return []
            raise AssertionError(f"unexpected gh_json call: {args}")

        return mock.patch.object(
            pr_ci_state, "gh_json", side_effect=fake_gh_json
        ), mock.patch.object(
            pr_ci_state, "current_job_names", return_value=job_names or None
        )

    def test_positive_control_sees_a_real_check_suite(self) -> None:
        """Prove the query path can see a suite before trusting any zero."""
        p1, p2 = self._patch(_pr(), suites=[{"id": 1}], runs=[
            {"name": "repository", "status": "completed", "conclusion": "success"}
        ])
        with p1, p2:
            result = pr_ci_state.classify("o/r", 1)
        self.assertEqual(result["suite_count"], 1)
        self.assertEqual(result["state"], "SUCCESS")
        self.assertEqual(result["category"], "clean")

    def test_case1_zero_suites_and_conflicting_is_actionable_not_waiting(self) -> None:
        p1, p2 = self._patch(
            _pr(mergeable="CONFLICTING", mergeStateStatus="DIRTY"),
            suites=[],
            runs=[],
        )
        with p1, p2:
            result = pr_ci_state.classify("o/r", 231)
        self.assertEqual(result["state"], "CONFLICTING")
        self.assertEqual(result["category"], "actionable-problem")
        self.assertEqual(pr_ci_state.EXIT_BY_CATEGORY[result["category"]], 1)

    def test_case2_zero_suites_and_mergeable_is_clean_waiting(self) -> None:
        """A slow-CI lane must not be told to rebase just because suites==0."""
        p1, p2 = self._patch(_pr(mergeable="MERGEABLE", mergeStateStatus="CLEAN"), [], [])
        with p1, p2:
            result = pr_ci_state.classify("o/r", 2)
        self.assertEqual(result["state"], "WAITING")
        self.assertEqual(result["category"], "clean")

    def test_case3_suites_exist_and_pending_is_clean(self) -> None:
        p1, p2 = self._patch(
            _pr(),
            suites=[{"id": 1}],
            runs=[{"name": "repository", "status": "in_progress", "conclusion": None}],
        )
        with p1, p2:
            result = pr_ci_state.classify("o/r", 3)
        self.assertEqual(result["state"], "PENDING")
        self.assertEqual(result["category"], "clean")

    def test_case4_suites_exist_and_failed_is_actionable(self) -> None:
        p1, p2 = self._patch(
            _pr(),
            suites=[{"id": 1}],
            runs=[{"name": "repository", "status": "completed", "conclusion": "failure"}],
        )
        with p1, p2:
            result = pr_ci_state.classify("o/r", 4)
        self.assertEqual(result["state"], "FAILED")
        self.assertEqual(result["category"], "actionable-problem")

    def test_case5_stale_job_shape_is_actionable(self) -> None:
        p1, p2 = self._patch(
            _pr(),
            suites=[{"id": 1}],
            runs=[{"name": "test", "status": "completed", "conclusion": "failure"}],
            job_names={"shell-suites"},
        )
        with p1, p2:
            result = pr_ci_state.classify("o/r", 433)
        self.assertEqual(result["state"], "STALE")
        self.assertEqual(result["stale_check"], "checked")
        self.assertEqual(result["category"], "actionable-problem")

    def test_case5_matching_job_shape_is_not_flagged_stale(self) -> None:
        p1, p2 = self._patch(
            _pr(),
            suites=[{"id": 1}],
            runs=[{"name": "shell-suites (shard 0)", "status": "completed", "conclusion": "success"}],
            job_names={"shell-suites"},
        )
        with p1, p2:
            result = pr_ci_state.classify("o/r", 5)
        self.assertEqual(result["state"], "SUCCESS")
        self.assertEqual(result["stale_check"], "checked")

    def test_could_not_measure_is_distinct_from_zero_suites(self) -> None:
        """The conflation the issue names: an API failure must never be
        reported as if it were a real zero."""

        def raising_gh_json(args):
            raise pr_ci_state.GhError("simulated network failure")

        with mock.patch.object(pr_ci_state, "gh_json", side_effect=raising_gh_json):
            with self.assertRaises(pr_ci_state.GhError):
                pr_ci_state.classify("o/r", 999)

    def test_main_reports_could_not_measure_with_exit_2(self) -> None:
        def raising_resolve(repo):
            raise pr_ci_state.GhError("simulated auth failure")

        with mock.patch.object(pr_ci_state, "resolve_repo", side_effect=raising_resolve):
            with mock.patch("sys.stdout"):
                exit_code = pr_ci_state.main(["999"])
        self.assertEqual(exit_code, 2)

    def test_main_exit_codes_are_three_distinct_values(self) -> None:
        self.assertEqual(
            len(set(pr_ci_state.EXIT_BY_CATEGORY.values())), 3,
            "clean / actionable-problem / could-not-measure must map to three codes",
        )


class ParseJobNamesTests(unittest.TestCase):
    def test_extracts_job_id_and_explicit_name(self) -> None:
        yaml_text = (
            "on:\n  pull_request:\njobs:\n"
            "  repository:\n"
            "    name: Validate repository\n"
            "    runs-on: ubuntu-latest\n"
        )
        names = pr_ci_state.parse_job_names(yaml_text)
        self.assertEqual(names, {"repository", "Validate repository"})

    def test_stops_at_end_of_jobs_block(self) -> None:
        yaml_text = "jobs:\n  build:\n    runs-on: ubuntu-latest\nconcurrency:\n  group: x\n"
        names = pr_ci_state.parse_job_names(yaml_text)
        self.assertEqual(names, {"build"})


if __name__ == "__main__":
    unittest.main()
