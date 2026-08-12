"""Guard against stale cross-repo and intra-repo references in tracked docs.

Ported and merged from two independently-built guards after the
2026-08-10 cross-repo reference sweep (jonhill90/agent-dotfiles#32):

- jonhill90/skills' tests/test_validate_repository.py established the
  pattern of a test-only guard scanning shipped content for a banned
  class of string, with a probe proving it fires.
- jonhill90/agent-evals' tests/test_repo_links.py contributed the
  same-repo relative-Markdown-link resolution check; find_broken_links()
  and relative_link_target() below are a direct port of that file's
  logic, generalized to also flag repo-relative paths cited outside
  Markdown link syntax.

This repository's sweep found 48 stale references, 43 of them bare
'#N' issue/PR citations -- the dominant and most dangerous class,
because a bare '#N' always resolves to *something* in whatever repo
reads it. It fails silently and plausibly instead of 404ing, so a
citation that was correct before a repo split can silently point at
the wrong issue after one.

What this guard checks, and what it deliberately does not:

1. Every bare '#N' in a tracked *.md file must resolve to a real
   issue or PR number in *this* repository. "Bare" means not
   immediately preceded by a word character or '/' -- so
   'owner/repo#9' and 'agent-dotfiles#9' both pass through untouched
   (the four sweeps just spent real effort creating exactly those
   qualified forms; this guard must not undo that work), while a
   lone '#9', '(#9', or '-#9' is checked. This is fully offline: it
   checks against tests/fixtures/known_references.txt, a manifest
   refreshed via `python3 scripts/refresh_known_references.py`
   (requires `gh`, not run in CI) rather than calling the GitHub API
   from the test itself. The manifest is one number per line (see
   #190) rather than JSON, and carries `merge=union` in
   .gitattributes so two branches that each regenerate it with a
   different new number merge without a conflict.

   This check is necessarily incomplete: a bare '#9' that happens to
   name a real, existing issue in this repository but was actually
   about a *different* issue before a repo split is undetectable
   offline (it isn't a 404, it's a wrong-but-real match) and is out
   of scope here by design.

2. Every same-repo relative path referenced from a Markdown link
   ('[text](path)') must resolve to a real file in this repository.
   Catches post-split drift into directories that moved or were
   never created here (skills/, tests/evals/, .claude/skills,
   .codex/skills, etc). Anchors, http(s) links, and mailto links are
   skipped.

Escape hatch: a citation that is a legitimate historical reference to
a number that no longer resolves (e.g. the issue/PR it named was
later deleted, not merely renumbered) is not a bug in this
repository's prose. Add the number to the "allowed" list in
tests/fixtures/reference_guard_allowlist.json with a comment
explaining why, rather than editing the doc to make the guard pass.
Do not use the allowlist to paper over a stale manifest -- if the
number is missing only because a new issue/PR hasn't been synced
yet, refresh the manifest instead.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REPO = "jonhill90/agent-dotfiles"
MANIFEST_PATH = ROOT / "tests" / "fixtures" / "known_references.txt"
ALLOWLIST_PATH = ROOT / "tests" / "fixtures" / "reference_guard_allowlist.json"

# Fenced and inline code spans hold illustrative template syntax (e.g. a
# doc showing the literal Markdown to write for a future entry,
# `[title](facts/<slug>.md)`), not real links -- strip both before
# scanning so those templates aren't checked as if they were live links.
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def strip_code_spans(text: str) -> str:
    # Preserve newline count when blanking fenced blocks so line numbers
    # reported for violations elsewhere in the file stay accurate.
    without_fences = FENCED_CODE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return INLINE_CODE_RE.sub("", without_fences)

# A '#N' preceded by a word character or '/' is already qualified
# ('owner/repo#9', 'agent-dotfiles#9') and out of scope: it names a
# specific repository, even without a leading owner, and the sweeps
# relied on exactly that form to disambiguate cross-repo citations.
BARE_REF_RE = re.compile(r"(?:^|[^A-Za-z0-9/])#(\d+)")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def tracked_markdown_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def load_known_numbers() -> set[int]:
    numbers: set[int] = set()
    for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        numbers.add(int(line))
    return numbers


def load_allowlist() -> set[int]:
    allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    return {entry["number"] for entry in allowlist["allowed"]}


def find_bare_reference_violations() -> list[tuple[Path, int, str]]:
    known = load_known_numbers()
    allowed = load_allowlist()
    violations: list[tuple[Path, int, str]] = []
    for md_file in tracked_markdown_files():
        text = strip_code_spans(md_file.read_text(encoding="utf-8", errors="ignore"))
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in BARE_REF_RE.finditer(line):
                number = int(match.group(1))
                if number not in known and number not in allowed:
                    violations.append((md_file.relative_to(ROOT), lineno, f"#{number}"))
    return violations


def relative_link_target(md_file: Path, raw_target: str) -> Path | None:
    """Resolve a Markdown link target to a filesystem path, or None if it
    isn't a same-repo relative reference (anchor, http(s), mailto).

    Ported from jonhill90/agent-evals' tests/test_repo_links.py.
    """
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    # A unicode ellipsis marks illustrative template syntax
    # ('[title](facts/…)') standing for "more entries like this", not a
    # literal path -- no real file in this repository is named with it.
    if "…" in target:
        return None
    target = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not target:
        return None
    return md_file.parent / target


def find_broken_link_violations() -> list[tuple[Path, str]]:
    violations: list[tuple[Path, str]] = []
    for md_file in tracked_markdown_files():
        text = strip_code_spans(md_file.read_text(encoding="utf-8", errors="ignore"))
        for raw_target in LINK_RE.findall(text):
            target = relative_link_target(md_file, raw_target)
            if target is not None and not target.exists():
                violations.append((md_file.relative_to(ROOT), raw_target))
    return violations


class NoDanglingCrossRepoReferenceTests(unittest.TestCase):
    def test_bare_issue_references_resolve_in_this_repository(self) -> None:
        violations = find_bare_reference_violations()
        self.assertEqual(
            violations,
            [],
            "bare issue/PR reference(s) that do not resolve in "
            f"{REPO}: "
            + "; ".join(f"{path}:{line}: {ref}" for path, line, ref in violations)
            + ". Fix: if this cites another repository, qualify it as "
            "'owner/repo#N'. If the number should exist here but is "
            "missing from the manifest, run `python3 "
            "scripts/refresh_known_references.py`. If it is a legitimate "
            "historical citation to a number that no longer resolves, add "
            "it to tests/fixtures/reference_guard_allowlist.json with a "
            "reason.",
        )

    def test_relative_markdown_links_resolve(self) -> None:
        violations = find_broken_link_violations()
        self.assertEqual(
            violations,
            [],
            "broken relative Markdown link(s): "
            + "; ".join(f"{path}: {target}" for path, target in violations)
            + ". Fix: correct the path, or remove the stale reference if "
            "the target moved to another repository during a split.",
        )


if __name__ == "__main__":
    unittest.main()
