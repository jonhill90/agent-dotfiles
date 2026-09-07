#!/usr/bin/env python3
"""Enforce the docs standard (P12 item 2, agent-estate-lanes/run/
iteration-queue.md): three rules, all hard failures, none advisory.

Classification (which doc is canonical/historical/research) is a human
judgment call. In THIS repository that judgment was already made and
already executed by #345 ("docs: organize canonical knowledge surfaces"):
every doc that used to live flat under docs/ is now either real content
under docs/canonical/, docs/historical/, or docs/research/, or a 5-line
TOMBSTONE at its old flat path pointing forward to where the content
actually lives. This script does not re-sort anything and does not
re-decide any classification -- it only enforces the structural
invariants that judgment call depends on staying true, going forward,
without a human re-checking it by hand on every PR:

  1. No unclassified root file directly under docs/. Every real doc lives
     in docs/canonical/, docs/historical/, docs/research/, or docs/corpus/
     (all pre-existing, #345-created or earlier). A file sitting directly
     under docs/ is allowed in exactly two shapes: named on ROOT_ALLOWLIST
     below with a stated reason (a genuine entry point, e.g. the taxonomy
     index itself, or a known, already-decided exception awaiting Jon's
     say-so -- never a place to dump a new file to dodge classification),
     or a TOMBSTONE: a real routing stub whose own three fixed lines match
     TOMBSTONE_LINE2 below and whose link target resolves to a real file
     under one of the four classified subdirectories. A stub whose link
     target does NOT resolve (a typo, a target that was itself since
     moved or deleted) is NOT exempt -- that is a broken tombstone, which
     is worse than an unclassified file because it looks routed and isn't.
  2. No state file (.json/.jsonl) anywhere under docs/, recursively.
     Documentation and generated/derived state are different trees.
  3. Zero full-text duplicates by checksum, across every tracked .md and
     .py file in the repo. A symlink (e.g. CLAUDE.md -> AGENTS.md, this
     repo's own multi-harness entry-point convention) is excluded: it is
     an alias to one file, not an independent copy that can drift.

Every check function takes `repo` as its own parameter, never a
module-level default -- tests/test_docs_lint.py points these at
throwaway fixture directories, never this repository's own tree.

Exit 0 = all three rules hold. Exit 1 = at least one violation, printed
with the specific path so a fix is mechanical, not a re-investigation.
This script does not repair anything.

Run: python3 scripts/docs_lint.py
"""
from __future__ import annotations
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Genuine entry points a reader expects directly under docs/, or a known,
# already-recorded exception awaiting Jon's own decision -- never a place
# to drop a new file to dodge classification. Each entry needs a reason.
ROOT_ALLOWLIST = {
    "index.md": "the docs/ taxonomy signpost #345 created -- routes to "
                "canonical/historical, the one file at this level that is "
                "genuinely an index, not a doc that needs its own home.",
    ".gitkeep": "P12 Phase 1's own DELETE-CANDIDATE (run/p12-dotfiles-"
                "disposition.md): a vestigial empty-dir placeholder docs/ "
                "has not needed since before its own history. Listed for "
                "Jon, not deleted by this or any pass without his say-so "
                "-- named here so the lint does not flag a file already "
                "on record as a known, undecided exception.",
}

CLASSIFIED_SUBDIRS = {"canonical", "historical", "research", "corpus"}

# The fixed second content line every real tombstone #345 created carries
# (line 1 is "# <name>", line 2 blank, line 3 this, line 4 blank, line 5
# the forwarding link) -- verified against every tombstone in the real
# tree before being hardcoded here, not guessed.
TOMBSTONE_LINE3 = "Status: superseded routing location. Canonical content moved, not copied."
TOMBSTONE_LINK_RE = re.compile(r"^Continue to \[[^\]]+\]\(([^)]+)\)\.$")


def _is_valid_tombstone(path: Path, docs: Path) -> bool:
    """A real tombstone: line 3 matches exactly, and line 5's link target
    resolves to a real file under one of the classified subdirectories.
    A stub whose target is missing or points somewhere unclassified is
    NOT valid -- it is a broken routing stub, not a legitimate exception."""
    try:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError):
        return False
    if len(lines) < 5 or lines[2] != TOMBSTONE_LINE3:
        return False
    m = TOMBSTONE_LINK_RE.match(lines[4])
    if not m:
        return False
    target = (path.parent / m.group(1)).resolve()
    try:
        rel = target.relative_to(docs.resolve())
    except (ValueError, OSError):
        return False
    if not rel.parts or rel.parts[0] not in CLASSIFIED_SUBDIRS:
        return False
    return target.is_file()


def check_unclassified_root_files(repo: Path) -> list[str]:
    """Rule 1: every direct child of docs/ is a classified subdirectory,
    a file on ROOT_ALLOWLIST, or a valid tombstone (see above)."""
    docs = repo / "docs"
    violations = []
    if not docs.is_dir():
        return violations
    for entry in sorted(docs.iterdir()):
        if entry.is_dir():
            if entry.name not in CLASSIFIED_SUBDIRS:
                violations.append(
                    f"docs/{entry.name}/: unrecognized top-level directory "
                    f"(expected one of {sorted(CLASSIFIED_SUBDIRS)})")
            continue
        if entry.name in ROOT_ALLOWLIST:
            continue
        if _is_valid_tombstone(entry, docs):
            continue
        violations.append(
            f"docs/{entry.name}: unclassified root file -- not on "
            f"ROOT_ALLOWLIST and not a valid tombstone (a stub whose "
            f"line 3 matches the standard wording and whose forwarding "
            f"link resolves to a real file under docs/canonical/, "
            f"docs/historical/, docs/research/, or docs/corpus/)")
    return violations


def check_no_state_files_in_docs(repo: Path) -> list[str]:
    """Rule 2: no .json/.jsonl anywhere under docs/, recursively."""
    docs = repo / "docs"
    violations = []
    if not docs.is_dir():
        return violations
    for p in sorted(docs.rglob("*")):
        if p.suffix in (".json", ".jsonl"):
            violations.append(
                f"{p.relative_to(repo)}: state file under docs/ -- "
                f"documentation and generated/derived state are different "
                f"trees, this does not belong here")
    return violations


def check_zero_duplicate_checksums(repo: Path) -> list[str]:
    """Rule 3: no two tracked .md/.py files share a sha256 of their full
    byte content. Scope is the whole repo, not just docs/."""
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "*.md", "*.py"],
        capture_output=True, text=True, check=True,
    ).stdout
    by_hash: dict[str, list[str]] = {}
    for rel in out.splitlines():
        if not rel.strip():
            continue
        path = repo / rel
        if path.is_symlink() or not path.is_file():
            # CLAUDE.md -> AGENTS.md is this repo's own real shape: an
            # ALIAS to one file, not an independent copy that can drift.
            continue
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        by_hash.setdefault(h, []).append(rel)
    violations = []
    for h, paths in sorted(by_hash.items()):
        if len(paths) > 1:
            violations.append(
                f"full-text duplicate (sha256 {h[:12]}): {', '.join(sorted(paths))}")
    return violations


def run(repo: Path) -> tuple[int, list[str]]:
    checks = [
        ("no unclassified root files under docs/", check_unclassified_root_files),
        ("no state files under docs/", check_no_state_files_in_docs),
        ("zero full-text duplicates by checksum", check_zero_duplicate_checksums),
    ]
    lines = []
    total = 0
    for label, fn in checks:
        violations = fn(repo)
        if violations:
            lines.append(f"FAIL -- {label} ({len(violations)}):")
            for v in violations:
                lines.append(f"  - {v}")
        else:
            lines.append(f"ok   -- {label}")
        total += len(violations)
    lines.append("")
    if total:
        lines.append(f"docs-lint: {total} violation(s). Fix them; this script does not repair anything.")
        return 1, lines
    lines.append("docs-lint: all three rules hold.")
    return 0, lines


def main() -> int:
    code, lines = run(REPO)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
