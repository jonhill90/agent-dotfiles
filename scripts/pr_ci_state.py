#!/usr/bin/env python3
"""Distinguish "CI hasn't started" from "CI cannot start" (agent-dotfiles#244).

`gh pr checks` collapses five different truths into the same silence:

1. no check suite exists **and the PR is CONFLICTING**  -> rebase, do not wait
2. no check suite exists **and the PR is mergeable**     -> Actions may be slow;
   waiting is legitimate
3. checks exist and are pending                          -> wait
4. checks exist and failed                                -> read the log
5. checks exist but are from a **stale job shape**        -> rebase, the result
   is a verdict on a `main` that no longer exists

GitHub cannot construct a merge ref for a CONFLICTING pull request, so its
`pull_request`-triggered workflows never queue: zero check suites is not a
transient "not yet", it is a permanent "never", and it looks identical to
Actions being slow or down. #231 spent 25 minutes waiting on exactly that.

This script reports which of the five holds, and treats "the API call
failed" as its own outcome distinct from "the API answered zero" -- the
conflation the issue names is code that lets an exception fall through to
the same branch as `len(check_suites) == 0`. It never does; a failed `gh`
call raises before any suite-count logic runs.

Case 5 (stale job shape) is implemented but WEAKLY verified: this repo has
one workflow with one job today, so there is no live PR here to prove a
stale-name mismatch against. It is covered by a unit test with fabricated
job/run names, not by a real GitHub response. Treat it as covered-in-logic,
not covered-in-the-wild.

Exit codes (the distinction the issue asks for):
  0  clean             -- nothing to do; wait is legitimate, or checks passed
  1  actionable-problem -- rebase, or go read a failure log
  2  could-not-measure  -- the `gh` call itself failed; this is NOT a zero

Python 3 stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

FAILURE_CONCLUSIONS = {"failure", "timed_out", "cancelled", "action_required"}
IN_PROGRESS_STATUSES = {"queued", "in_progress", "requested", "waiting", "pending"}

# state -> category the issue asked for: clean / actionable-problem / could-not-measure
CATEGORY_BY_STATE = {
    "WAITING": "clean",
    "MERGEABILITY_PENDING": "clean",
    "PENDING": "clean",
    "SUCCESS": "clean",
    "CONFLICTING": "actionable-problem",
    "FAILED": "actionable-problem",
    "STALE": "actionable-problem",
}
EXIT_BY_CATEGORY = {"clean": 0, "actionable-problem": 1, "could-not-measure": 2}


class GhError(Exception):
    """A `gh`/API call did not succeed. The state is UNMEASURED, not zero."""


def run_gh(args: list[str], timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GhError(f"gh {' '.join(args)} did not run: {exc}") from exc
    if result.returncode != 0:
        raise GhError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def gh_json(args: list[str]) -> Any:
    try:
        return json.loads(run_gh(args))
    except json.JSONDecodeError as exc:
        raise GhError(f"gh {' '.join(args)} returned non-JSON: {exc}") from exc


def resolve_repo(repo: str | None) -> str:
    if repo:
        return repo
    data = gh_json(["repo", "view", "--json", "nameWithOwner"])
    return data["nameWithOwner"]


def fetch_pr(repo: str, pr_number: int) -> dict:
    return gh_json(
        [
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo,
            "--json",
            "mergeable,mergeStateStatus,headRefOid,number,url",
        ]
    )


def fetch_check_suites(repo: str, sha: str) -> list[dict]:
    data = gh_json(["api", f"repos/{repo}/commits/{sha}/check-suites"])
    return data.get("check_suites", [])


def fetch_check_runs(repo: str, sha: str) -> list[dict]:
    data = gh_json(["api", f"repos/{repo}/commits/{sha}/check-runs"])
    return data.get("check_runs", [])


_JOB_ID_RE = re.compile(r"^([A-Za-z0-9_.-]+):\s*(#.*)?$")
_JOB_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$")


def parse_job_names(workflow_yaml: str) -> set[str]:
    """Best-effort job-id/job-name extraction, no PyYAML dependency.

    Returns the set of job identifiers and any explicit `name:` overrides
    declared directly under `jobs:` in one workflow file's text.
    """
    names: set[str] = set()
    in_jobs = False
    jobs_indent = None
    current_job_id = None
    for line in workflow_yaml.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if stripped == "jobs:":
            in_jobs = True
            jobs_indent = indent
            continue
        if not in_jobs:
            continue
        if indent <= jobs_indent:
            in_jobs = False
            continue
        if indent == jobs_indent + 2:
            match = _JOB_ID_RE.match(stripped)
            if match:
                current_job_id = match.group(1)
                names.add(current_job_id)
            continue
        if current_job_id is not None:
            match = _JOB_NAME_RE.match(stripped)
            if match:
                names.add(match.group(1).strip("'\""))
    return names


def current_job_names(repo: str) -> set[str] | None:
    """Job names declared in this repo's *current* default-branch workflows.

    Returns None -- not an empty set -- when the workflow list itself could
    not be fetched, so callers can tell "no current jobs" (impossible; that
    would mean no CI at all) apart from "could not check, skip the stale
    comparison" (routine: a private repo without the extra scope, a
    transient API error).
    """
    try:
        listing = gh_json(["api", f"repos/{repo}/contents/.github/workflows"])
    except GhError:
        return None
    if not isinstance(listing, list):
        return None
    names: set[str] = set()
    for entry in listing:
        entry_name = entry.get("name", "")
        if not entry_name.endswith((".yml", ".yaml")):
            continue
        try:
            raw = run_gh(
                [
                    "api",
                    "-H",
                    "Accept: application/vnd.github.raw",
                    f"repos/{repo}/contents/.github/workflows/{entry_name}",
                ]
            )
        except GhError:
            continue
        names |= parse_job_names(raw)
    return names or None


def _observed_name_is_stale(observed: str, current_names: set[str]) -> bool:
    """True if an observed check-run name matches none of the current jobs.

    Matrix jobs render as "job (shard 0)"; match on exact name or on the
    job name being a prefix followed by a space, e.g. "shell-suites" against
    "shell-suites (shard 0)".
    """
    return not any(
        observed == job or observed.startswith(job + " ") for job in current_names
    )


def classify(repo: str, pr_number: int) -> dict:
    pr = fetch_pr(repo, pr_number)
    sha = pr["headRefOid"]
    mergeable = pr.get("mergeable")
    merge_state = pr.get("mergeStateStatus")

    suites = fetch_check_suites(repo, sha)
    suite_count = len(suites)

    result: dict[str, Any] = {
        "repo": repo,
        "pr": pr_number,
        "sha": sha,
        "mergeable": mergeable,
        "mergeStateStatus": merge_state,
        "suite_count": suite_count,
        "stale_check": "skipped",
    }

    if suite_count == 0:
        if mergeable == "CONFLICTING" or merge_state == "DIRTY":
            result["state"] = "CONFLICTING"
            result["message"] = (
                "no check suite exists and the PR is CONFLICTING -- GitHub "
                "cannot build a merge ref, so pull_request workflows will "
                "never queue. Rebase; do not wait."
            )
        elif mergeable == "UNKNOWN":
            result["state"] = "MERGEABILITY_PENDING"
            result["message"] = (
                "GitHub has not finished computing mergeability yet. "
                "Transient -- poll again shortly."
            )
        else:
            result["state"] = "WAITING"
            result["message"] = (
                "no check suite yet and the PR is mergeable. Actions may be "
                "slow to queue; waiting is legitimate."
            )
        result["category"] = CATEGORY_BY_STATE[result["state"]]
        return result

    runs = fetch_check_runs(repo, sha)
    statuses = {r.get("status") for r in runs}
    conclusions = {r.get("conclusion") for r in runs if r.get("conclusion")}

    if conclusions & FAILURE_CONCLUSIONS:
        result["state"] = "FAILED"
        result["message"] = "checks exist and at least one failed -- read the log."
    elif statuses - {"completed"}:
        result["state"] = "PENDING"
        result["message"] = "checks exist and are still running -- wait."
    else:
        result["state"] = "SUCCESS"
        result["message"] = "checks exist and all completed successfully."

    job_names = current_job_names(repo)
    if job_names is not None and runs:
        result["stale_check"] = "checked"
        observed_names = {r.get("name", "") for r in runs}
        if all(_observed_name_is_stale(name, job_names) for name in observed_names):
            result["state"] = "STALE"
            result["message"] = (
                "checks exist but none match this repo's current "
                "pull_request job names -- this branch predates a CI "
                "change and the verdict is about a main that no longer "
                "exists. Rebase."
            )

    result["category"] = CATEGORY_BY_STATE[result["state"]]
    return result


def format_report(result: dict) -> str:
    lines = [f"{result.get('state', 'ERROR')} ({result.get('category', '?')})"]
    if "message" in result:
        lines.append(result["message"])
    for key in ("repo", "pr", "sha", "mergeable", "mergeStateStatus", "suite_count", "stale_check"):
        if key in result:
            lines.append(f"  {key}: {result[key]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pr_number", type=int)
    parser.add_argument("--repo", help="owner/name; defaults to the current repo")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    try:
        repo = resolve_repo(args.repo)
        result = classify(repo, args.pr_number)
    except GhError as exc:
        result = {
            "state": "ERROR",
            "category": "could-not-measure",
            "message": str(exc),
        }

    print(json.dumps(result) if args.json else format_report(result))
    return EXIT_BY_CATEGORY[result["category"]]


if __name__ == "__main__":
    sys.exit(main())
