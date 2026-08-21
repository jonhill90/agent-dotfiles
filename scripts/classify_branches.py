#!/usr/bin/env python3
"""Classify local branches with commits on no remote (#120).

`git diff main...branch` (three-dot) reports a squash-merged branch's content
as still outstanding, because after the squash `main` holds the content under
a different commit than the branch's own. `git diff main..branch` (two-dot)
asks the right question — does `main` already contain this content — but
inflates the answer for a stale branch: it also counts the branch's *older*
versions of files `main` has since changed for unrelated reasons.

Neither is a safe default (the correct diff depends on the question). This
script instead checks, per file the branch actually touched since its merge
base with `main`, whether every line the branch *added* is present somewhere
in `main`'s current version of that file. A branch whose merge base tip is
already an ancestor of `main`, or whose added lines are all present, is
SUPERSEDED. A branch with an added line genuinely absent from `main` is
OUTSTANDING. Anything the check cannot answer (binary files, a file `main`
has since deleted, a missing merge base, a `git` failure) is
COULD-NOT-CLASSIFY — never silently folded into SUPERSEDED, because that
would let blindness pass as cleanliness.

Blind spots this script does not cover, by design:
  - Content-identical-but-reformatted (renamed variables, moved lines,
    re-wrapped prose): an added line that changed even cosmetically will not
    exact-match `main`'s text and reads as OUTSTANDING evidence needing a
    human, not as a false SUPERSEDED.
  - Partial merges: if only some of a branch's contribution landed on
    `main`, the branch classifies OUTSTANDING for the missing part — correct,
    but the report does not say how much of the branch is already present.
  - A branch whose worktree is gone: this script only reads git history
    (refs, trees, blobs), which survive a missing worktree; it does not
    verify a worktree exists and never needs to.
  - Renames: a file renamed and otherwise unchanged looks like a deleted
    file to the per-file walk here (no `-M` rename detection), which reports
    it as COULD-NOT-CLASSIFY rather than guessing.

Read-only. Never runs `git branch -D`, `git worktree remove`, `git gc`, or
any push — it reports, the caller decides.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field

SUPERSEDED = "SUPERSEDED"
OUTSTANDING = "OUTSTANDING"
COULD_NOT_CLASSIFY = "COULD-NOT-CLASSIFY"


@dataclass
class Classification:
    branch: str
    verdict: str
    reason: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "branch": self.branch,
            "verdict": self.verdict,
            "reason": self.reason,
            **self.evidence,
        }


def run_git(args: list[str], cwd: str | None = None) -> tuple[str | None, str | None]:
    """Run `git <args>`. Returns (stdout, None) or (None, error) — never raises."""
    try:
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=30, check=False, cwd=cwd
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"git {' '.join(args)} did not run: {exc}"
    if result.returncode != 0:
        return None, result.stderr.strip() or f"git {' '.join(args)} exited {result.returncode}"
    return result.stdout, None


def merge_base(main: str, branch: str, cwd: str | None) -> tuple[str | None, str | None]:
    out, err = run_git(["merge-base", main, branch], cwd)
    if err is not None:
        return None, err
    return out.strip(), None


def is_ancestor(candidate: str, of_ref: str, cwd: str | None) -> bool:
    out, err = run_git(["merge-base", "--is-ancestor", candidate, of_ref], cwd)
    # is-ancestor exits non-zero (with empty stderr) when it is simply false.
    return err is None


def rev_parse(ref: str, cwd: str | None) -> tuple[str | None, str | None]:
    out, err = run_git(["rev-parse", ref], cwd)
    if err is not None:
        return None, err
    return out.strip(), None


def touched_files(mb: str, branch: str, cwd: str | None) -> tuple[list[str] | None, str | None]:
    out, err = run_git(["diff", "--name-only", mb, branch], cwd)
    if err is not None:
        return None, err
    return [line for line in out.splitlines() if line], None


def added_lines(mb: str, branch: str, path: str, cwd: str | None) -> tuple[list[str] | None, str | None]:
    """Lines the branch added to `path` since `mb`. None means "cannot tell"
    (binary content) rather than "no lines added"."""
    out, err = run_git(["diff", mb, branch, "--", path], cwd)
    if err is not None:
        return None, err
    if "Binary files" in out:
        return None, "binary file"
    lines: list[str] = []
    for line in out.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
    return lines, None


def file_at(ref: str, path: str, cwd: str | None) -> str | None:
    out, err = run_git(["show", f"{ref}:{path}"], cwd)
    if err is not None:
        return None
    return out


def classify(branch: str, main: str, cwd: str | None = None) -> Classification:
    mb, err = merge_base(main, branch, cwd)
    if err is not None:
        return Classification(branch, COULD_NOT_CLASSIFY, f"no merge base with {main}: {err}")

    branch_tip, err = rev_parse(branch, cwd)
    if err is not None:
        return Classification(branch, COULD_NOT_CLASSIFY, f"could not resolve {branch}: {err}")

    if branch_tip == mb:
        return Classification(
            branch, SUPERSEDED, f"no commits ahead of {main} (tip == merge base)", {"merge_base": mb}
        )

    if is_ancestor(branch, main, cwd):
        return Classification(
            branch, SUPERSEDED, f"branch tip {branch_tip[:12]} is an ancestor of {main}", {"tip": branch_tip}
        )

    files, err = touched_files(mb, branch, cwd)
    if err is not None:
        return Classification(branch, COULD_NOT_CLASSIFY, f"could not list touched files: {err}")

    if not files:
        return Classification(branch, SUPERSEDED, "no files differ from merge base", {"merge_base": mb})

    missing: list[dict] = []
    unresolved: list[dict] = []

    for path in files:
        added, err = added_lines(mb, branch, path, cwd)
        if added is None:
            unresolved.append({"file": path, "why": err})
            continue

        meaningful = [line for line in added if line.strip()]
        if not meaningful:
            continue

        main_text = file_at(main, path, cwd)
        if main_text is None:
            unresolved.append({"file": path, "why": f"file not present on {main} (deleted or renamed)"})
            continue

        main_lines = set(main_text.splitlines())
        for line in meaningful:
            if line not in main_lines:
                missing.append({"file": path, "line": line})

    if missing:
        return Classification(
            branch,
            OUTSTANDING,
            f"{len(missing)} added line(s) across {len({m['file'] for m in missing})} "
            f"file(s) not found anywhere in {main}'s current version",
            {"missing": missing[:20], "missing_total": len(missing)},
        )

    if unresolved:
        return Classification(
            branch,
            COULD_NOT_CLASSIFY,
            f"{len(unresolved)} touched file(s) could not be compared "
            "(binary, or removed/renamed on main) and no other file showed "
            "missing content",
            {"unresolved": unresolved},
        )

    return Classification(
        branch,
        SUPERSEDED,
        f"every added line in every touched file is present in {main}'s current content",
        {"merge_base": mb, "files_checked": files},
    )


def branches_with_unpushed_commits(cwd: str | None = None) -> tuple[list[str] | None, str | None]:
    """Local branches that have at least one commit not reachable from any
    remote-tracking ref."""
    out, err = run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads/"], cwd)
    if err is not None:
        return None, err
    result = []
    for branch in (b for b in out.splitlines() if b):
        commits, cerr = run_git(["rev-list", branch, "--not", "--remotes"], cwd)
        if cerr is not None:
            continue  # unreadable branch — surfaced by classify() itself if asked about directly
        if commits.strip():
            result.append(branch)
    return result, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("branches", nargs="*", help="branches to classify; default: auto-discover")
    parser.add_argument("--main", default="main", help="branch to compare against (default: main)")
    parser.add_argument("--cwd", default=None, help="git repository to operate in")
    parser.add_argument("--exclude", action="append", default=[], help="branch name to skip (repeatable)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of a table")
    args = parser.parse_args()

    if args.branches:
        branches = args.branches
    else:
        branches, err = branches_with_unpushed_commits(args.cwd)
        if err is not None:
            print(f"could not enumerate branches: {err}", file=sys.stderr)
            return 2
        branches = [b for b in branches if b not in args.exclude]

    results = [classify(b, args.main, args.cwd) for b in branches]
    counts = {SUPERSEDED: 0, OUTSTANDING: 0, COULD_NOT_CLASSIFY: 0}
    for r in results:
        counts[r.verdict] += 1

    if args.json:
        print(json.dumps({"counts": counts, "results": [r.to_dict() for r in results]}, indent=2, sort_keys=True))
    else:
        for r in results:
            print(f"{r.verdict:20s} {r.branch:50s} {r.reason}")
        print()
        print(f"SUPERSEDED={counts[SUPERSEDED]} OUTSTANDING={counts[OUTSTANDING]} "
              f"COULD-NOT-CLASSIFY={counts[COULD_NOT_CLASSIFY]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
