"""Guard against path-scoped instruction files that bind to nothing.

`.github/instructions/*.instructions.md` are VS Code / Copilot path-scoped
instructions: each carries an `applyTo` glob, and the harness loads the file
only for a file the glob matches. A glob matching nothing is worse than no
glob, because the file reads as a guard while enforcing nothing -- the same
instrument-blindness class as a measurement that silently scores zero
(jonhill90/agent-dotfiles#28).

This set is not covered by `scripts/validate_repository.py`, which validates
the canonical `instructions/` tree that `sync.py` compiles. The `.github/`
set is a different surface with a different consumer, and until this test it
had no check at all: `skills/**/*.md` survived #9 removing the `skills/`
directory it named.

Scope: this asserts each *file* binds to at least one tracked path, not that
each *pattern* does. A file may legitimately carry a forward-looking pattern
alongside live ones (`**/*.ps1` matches nothing today), and failing that is a
different, narrower judgement than "this file is dead".
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTRUCTIONS = REPO / ".github" / "instructions"


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return out.stdout.split()


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a VS Code `applyTo` glob.

    VS Code semantics, not `fnmatch` and not git pathspec: `**` matches zero
    or more path segments, so `docs/**/*.md` matches `docs/SPEC.md`. Using
    git pathspec here would report `docs/**/*.md` as dead and hide the one
    file that really is.
    """
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:[^/]+/)*"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile("^" + out + "$")


def apply_to_patterns(text: str) -> list[str]:
    """Read `applyTo` from frontmatter, in either shape the set uses.

    A comma-separated scalar (`applyTo: 'docs/**/*.md'`) and a YAML block
    list (`applyTo:` then `- 'tests/**'`) both appear here.
    """
    frontmatter = text.split("---")[1]
    scalar = re.search(r"^applyTo:[ \t]*(\S.*)$", frontmatter, re.M)
    if scalar:
        return [p.strip().strip("'\"") for p in scalar.group(1).split(",") if p.strip()]
    block = re.search(
        r"^applyTo:[ \t]*\n((?:[ \t]*-[ \t]*.+\n)+)", frontmatter, re.M
    )
    if block:
        return [
            line.strip().lstrip("-").strip().strip("'\"")
            for line in block.group(1).strip().split("\n")
        ]
    return []


def matches(pattern: str, files: list[str]) -> list[str]:
    regex = glob_to_regex(pattern)
    return [f for f in files if regex.match(f)]


class InstructionGlobTests(unittest.TestCase):
    def test_every_instruction_file_declares_an_applyto(self) -> None:
        for path in sorted(INSTRUCTIONS.glob("*.instructions.md")):
            with self.subTest(path.name):
                self.assertTrue(
                    apply_to_patterns(path.read_text(encoding="utf-8")),
                    f"{path.name} has no applyTo; it would never load",
                )

    def test_every_instruction_file_binds_to_a_tracked_file(self) -> None:
        files = tracked_files()
        for path in sorted(INSTRUCTIONS.glob("*.instructions.md")):
            with self.subTest(path.name):
                patterns = apply_to_patterns(path.read_text(encoding="utf-8"))
                hits = {p: matches(p, files) for p in patterns}
                self.assertTrue(
                    any(hits.values()),
                    f"{path.name} matches no tracked file: "
                    + ", ".join(f"{p!r} -> 0" for p in patterns)
                    + ". Repoint applyTo at what exists, or remove the file.",
                )

    def test_probe_a_dead_glob_is_detected(self) -> None:
        """Without this, the check above passes vacuously if the matcher is
        wrong in the permissive direction."""
        files = tracked_files()
        self.assertEqual(matches("skills/**/*.md", files), [])
        self.assertNotEqual(matches("docs/**/*.md", files), [])
        self.assertIn("docs/SPEC.md", matches("docs/**/*.md", files))


if __name__ == "__main__":
    unittest.main()
