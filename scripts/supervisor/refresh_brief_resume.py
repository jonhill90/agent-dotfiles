#!/usr/bin/env python3
"""Regenerate the `## Resume point` block in brief.md from live state.

WHY THIS IS A SCRIPT AND NOT A RULE
-----------------------------------
`brief.md` is what a cold session reads first, and its resume block is the part
a reader trusts most: shas, test counts, what is open. It went stale three times
on 2026-08-11 alone --

  08:04  block claimed `40a349a` / 301 tests while sections beneath were current
  11:39  block still said "state as of 08:11 UTC" -- 3.5 hours old -- and the
         file had been WRITTEN nine minutes earlier
  11:49  rewritten by hand at 11:42, stale again within ten minutes

-- each time because someone edited a section below it and left the heading
alone. The file already carried a prominent warning about the first occurrence
when the second and third happened. A warning that has been ignored three times
is not a control; it is a note about a control that does not exist.

So this block is now derived rather than remembered. Everything it prints is
read at run time; nothing is carried forward from the previous copy.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not touch anything outside the resume block. The rest of `brief.md` is
prose written by whoever knew something, and regenerating that would destroy the
judgement it holds. If the markers are missing, this refuses rather than guessing
where the block starts -- a mangled brief is worse than a stale one, because the
staleness is at least visible.

It does not run the test suites. Counting tests means running them, which takes
~40s and is the caller's decision, not this script's; pass the numbers in with
--tests if you have just run them, and the line says so honestly when you have
not.

Usage:
    python3 scripts/supervisor/refresh_brief_resume.py [--brief PATH] [--tests N]
    python3 scripts/supervisor/refresh_brief_resume.py --check   # non-zero if stale
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

BEGIN = "<!-- resume-point:begin -->"
END = "<!-- resume-point:end -->"

REPOS = ("agent-dotfiles", "skills", "skills-private", "agent-evals")
REPO_ROOT = Path.home() / "source" / "repos" / "Personal"


def _run(args: list[str], cwd: Path | None = None) -> str | None:
    """Return stdout, or None if the command could not be run or failed.

    None means "could not measure" and is rendered as such. It is never
    collapsed into an empty string or a zero -- that conflation is the defect
    this estate has hit most often (agent-dotfiles #59, #92, #95, #100).
    """
    try:
        proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def repo_head(name: str) -> str:
    path = REPO_ROOT / name
    if not path.is_dir():
        # A missing checkout is not a repo at an unknown sha; say which it is.
        return "no local checkout"
    _run(["git", "fetch", "-q", "origin"], cwd=path)
    sha = _run(["git", "rev-parse", "--short", "origin/main"], cwd=path)
    return sha or "unreadable"


def open_items(repo: str, kind: str) -> str:
    """`kind` is "pr" or "issue". Returns a rendered list or an explicit failure."""
    out = _run(["gh", kind, "list", "-R", f"jonhill90/{repo}", "--state", "open",
                "--limit", "40", "--json", "number,title"])
    if out is None:
        return "could not read (gh failed) — NOT the same as none"
    try:
        rows = json.loads(out)
    except ValueError:
        return "could not parse (gh returned malformed JSON) — NOT the same as none"
    if not rows:
        return "none"
    return ", ".join(f"#{r['number']}" for r in sorted(rows, key=lambda r: -r["number"]))


def build_block(tests: str | None) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    heads = {name: repo_head(name) for name in REPOS}
    lines = [
        BEGIN,
        f"## Resume point — generated {now}",
        "",
        "**Generated, not written.** `scripts/supervisor/refresh_brief_resume.py`",
        "derives this block from live state. Do not hand-edit it: run the script.",
        "Everything outside the markers is prose and is yours to edit.",
        "",
        "```",
    ]
    width = max(len(n) for n in REPOS)
    for name in REPOS:
        lines.append(f"{name.ljust(width)}  main {heads[name]}")
    if tests:
        lines.append("")
        lines.append(f"agent-dotfiles suite: {tests}")
    else:
        lines.append("")
        lines.append("agent-dotfiles suite: not run by this refresh — run it and pass --tests")
    lines.append("```")
    lines.append("")
    for repo in REPOS:
        lines.append(f"- **{repo}** — PRs: {open_items(repo, 'pr')} · issues: {open_items(repo, 'issue')}")
    lines.extend([
        "",
        "A `could not read` above means the query failed, which is **not** the same",
        "as nothing being open. Re-run before concluding the estate is quiet.",
        END,
    ])
    return "\n".join(lines)


def splice(text: str, block: str) -> str:
    if BEGIN not in text or END not in text:
        raise SystemExit(
            f"refresh_brief_resume: markers not found in brief.\n"
            f"Add {BEGIN} / {END} around the resume block first. Refusing to guess "
            f"where it starts — a mangled brief is worse than a stale one."
        )
    return re.sub(
        re.escape(BEGIN) + ".*?" + re.escape(END), lambda _: block, text, flags=re.S
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", type=Path,
                    default=Path.home() / ".local/state/agent-dotfiles-supervisor/brief.md")
    ap.add_argument("--tests", default=None,
                    help='e.g. "399 python, 15 lanes, 26 watchdog, 0 failed"')
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the block would change; write nothing")
    args = ap.parse_args(argv)

    if not args.brief.is_file():
        print(f"refresh_brief_resume: no brief at {args.brief}", file=sys.stderr)
        return 2

    text = args.brief.read_text()
    updated = splice(text, build_block(args.tests))
    if args.check:
        if updated == text:
            print("resume block is current")
            return 0
        print("resume block is STALE — run without --check to regenerate", file=sys.stderr)
        return 1
    args.brief.write_text(updated)
    print(f"refresh_brief_resume: rewrote the resume block in {args.brief}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
