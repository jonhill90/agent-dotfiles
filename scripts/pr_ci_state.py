#!/usr/bin/env python3
"""Distinguish CI states `gh pr checks` conflates for a single PR (#244).

`gh api .../check-suites` returns an empty list for two causes that look
identical from the outside: CI has not started yet (legitimate wait), and
CI *cannot* start because the PR is CONFLICTING (GitHub cannot construct a
merge ref, so no workflow is ever queued). #231 sat in the second state for
17 minutes of polling while other lanes' pushes ran fine — Actions was
healthy, the PR's own DIRTY state was the cause. A close/reopen produced
nothing, because there was nothing broken to reset.

There is a second, subtler conflation this script also resolves: a branch
that predates a CI shape change can carry check runs whose names no longer
exist on the base branch (e.g. an old `test` job where current PRs report
`shell-suites (shard 0..4)`). A `failure` conclusion there is a verdict on
a `main` that no longer exists, not on the code — #432 and #433 both sat
"failing" for hours on exactly this and were fine after a rebase.

This script reports which of five states holds for a PR, using three exit
codes, because a caller that cannot distinguish "zero check suites" from
"could not reach the API" will treat the second as the first:

  0  clean              — checks passed, or absent-but-legitimately-pending
  1  actionable-problem — rebase, or read a genuine failure's log
  2  could-not-measure  — a `gh` call failed or returned something this
                           script does not know how to read; never treated
                           as a clean zero

The five states (issue #244):
  1. no check suite, PR mergeable == CONFLICTING  -> actionable: rebase
  2. no check suite, PR mergeable != CONFLICTING  -> clean: wait is legitimate
  3. check suite(s) exist, still running          -> clean: wait
  4. check suite(s) exist, failed, current shape  -> actionable: read the log
  5. check suite(s) exist, failed, stale shape    -> actionable: rebase
     (a failed run's name is absent from the base branch's own latest
     check runs — the job it names no longer exists on current main)

Read-only. Never pushes, rebases, or comments — it reports, the caller acts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field

EXIT_CLEAN = 0
EXIT_ACTIONABLE = 1
EXIT_UNMEASURED = 2

TERMINAL_CONCLUSIONS_OK = {"success", "skipped", "neutral"}


@dataclass
class Verdict:
    exit_code: int
    case: str
    message: str
    detail: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "exit_code": self.exit_code,
                "case": self.case,
                "message": self.message,
                **self.detail,
            },
            indent=2,
            sort_keys=True,
        )


def run_gh(args: list[str]) -> tuple[str | None, str | None]:
    """Run `gh <args>`. Returns (stdout, None) or (None, error) — never raises."""
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"gh {' '.join(args)} did not run: {exc}"
    if result.returncode != 0:
        return None, result.stderr.strip() or f"gh {' '.join(args)} exited {result.returncode}"
    return result.stdout, None


def gh_json(args: list[str]):
    """Run `gh <args>`, parse stdout as JSON. Returns (value, None) or (None, error)."""
    out, err = run_gh(args)
    if err is not None:
        return None, err
    try:
        return json.loads(out), None
    except json.JSONDecodeError as exc:
        return None, f"gh {' '.join(args)} returned unparseable JSON: {exc}"


def resolve_repo(repo: str | None) -> tuple[str | None, str | None]:
    if repo:
        return repo, None
    data, err = gh_json(["repo", "view", "--json", "nameWithOwner"])
    if err is not None:
        return None, f"could not resolve repo: {err}"
    return data["nameWithOwner"], None


def unmeasured(message: str, **detail) -> Verdict:
    return Verdict(EXIT_UNMEASURED, "could-not-measure", message, detail)


def evaluate(pr: str, repo: str | None) -> Verdict:
    resolved_repo, err = resolve_repo(repo)
    if err is not None:
        return unmeasured(err)

    pr_data, err = gh_json(
        [
            "pr",
            "view",
            pr,
            "--repo",
            resolved_repo,
            "--json",
            "headRefOid,mergeable,mergeStateStatus,baseRefName",
        ]
    )
    if err is not None:
        return unmeasured(f"could not read PR #{pr}: {err}", repo=resolved_repo)

    head_sha = pr_data["headRefOid"]
    mergeable = pr_data["mergeable"]
    base_ref = pr_data["baseRefName"]

    suites, err = gh_json(
        ["api", f"repos/{resolved_repo}/commits/{head_sha}/check-suites", "--jq", ".check_suites"]
    )
    if err is not None:
        return unmeasured(f"could not read check-suites for {head_sha}: {err}", repo=resolved_repo)

    detail = {"repo": resolved_repo, "pr": pr, "head_sha": head_sha, "mergeable": mergeable}

    if len(suites) == 0:
        if mergeable == "CONFLICTING":
            return Verdict(
                EXIT_ACTIONABLE,
                "case-1-conflicting-no-suite",
                "no check suite exists and the PR is CONFLICTING with "
                f"{base_ref} — rebase, do not wait; GitHub cannot construct "
                "a merge ref so no workflow will ever be queued",
                detail,
            )
        if mergeable == "UNKNOWN":
            return unmeasured(
                "GitHub has not finished computing mergeable state yet — retry shortly",
                **detail,
            )
        return Verdict(
            EXIT_CLEAN,
            "case-2-mergeable-no-suite",
            "no check suite yet, but the PR is mergeable — Actions may "
            "still be slow to pick it up; waiting is legitimate",
            detail,
        )

    runs, err = gh_json(
        ["api", f"repos/{resolved_repo}/commits/{head_sha}/check-runs", "--jq", ".check_runs"]
    )
    if err is not None:
        return unmeasured(f"could not read check-runs for {head_sha}: {err}", **detail)

    detail["check_run_names"] = sorted(r["name"] for r in runs)

    pending = [r for r in runs if r["status"] != "completed"]
    if pending:
        detail["pending"] = sorted(r["name"] for r in pending)
        return Verdict(
            EXIT_CLEAN,
            "case-3-pending",
            f"{len(pending)} check run(s) still running — wait",
            detail,
        )

    failed = [r for r in runs if r["conclusion"] not in TERMINAL_CONCLUSIONS_OK]
    if not failed:
        return Verdict(EXIT_CLEAN, "case-3-passed", "all check runs completed successfully", detail)

    detail["failed"] = sorted(r["name"] for r in failed)

    base_commit, err = gh_json(["api", f"repos/{resolved_repo}/commits/{base_ref}"])
    if err is None:
        base_sha = base_commit["sha"]
        base_runs, base_err = gh_json(
            ["api", f"repos/{resolved_repo}/commits/{base_sha}/check-runs", "--jq", ".check_runs"]
        )
        if base_err is None:
            base_names = {r["name"] for r in base_runs}
            failed_names = {r["name"] for r in failed}
            if failed_names and failed_names.isdisjoint(base_names):
                detail["base_sha"] = base_sha
                detail["base_check_run_names"] = sorted(base_names)
                return Verdict(
                    EXIT_ACTIONABLE,
                    "case-5-stale-job-shape",
                    "failed job name(s) "
                    f"{sorted(failed_names)} do not appear among {base_ref}'s "
                    f"current check runs {sorted(base_names)} — this branch "
                    "predates a CI shape change; the failure is a verdict "
                    "on an old main, rebase rather than reading the log",
                    detail,
                )

    return Verdict(
        EXIT_ACTIONABLE,
        "case-4-failed",
        f"check run(s) {detail['failed']} failed under the current job "
        "shape — read the log",
        detail,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pr", help="PR number")
    parser.add_argument("--repo", help="owner/name; defaults to the current repo")
    args = parser.parse_args()

    verdict = evaluate(args.pr, args.repo)
    print(verdict.to_json())
    return verdict.exit_code


if __name__ == "__main__":
    sys.exit(main())
