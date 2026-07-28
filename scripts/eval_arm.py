#!/usr/bin/env python3
"""Per-arm configuration for eval runs (SPEC §4 ladder).

The ladder compares a run with a candidate present against an otherwise
identical run with it absent. Once a candidate is deployed — the
second-opinion sentence is in every harness's user-scope instructions, and
`sanity-check` is on the shared skills path — the absent arm can no longer
be produced by running the CLI normally. E18 on Copilot stalled on exactly
this: its baseline arm needs the sentence gone, and a run today measures
neither rung.

The mechanism is deliberately dumb: **move the files aside, run, move them
back**. It does not use any harness's instruction-disable key. Those keys
differ per harness, one of them (`disabledInstructionSources`) is inferred
from a CLI bundle rather than documented, and a lever that silently stops
working would produce a contaminated arm that still looks clean. A missing
file cannot silently fail to be missing.

That bluntness has a cost, and it is the reason for every check here: the
stash window is **global**. While it is open, the harness is stripped for
every process on the machine, not just the eval. So:

* nothing is ever deleted — files are renamed, never removed;
* every payload is checksummed before the move and verified after restore;
* the state file makes restore possible from a trap, another shell, or a
  later session, after the run that opened the stash has died;
* a second stash refuses while one is outstanding, rather than nesting and
  losing the original;
* `check` reports an outstanding stash so a crashed run is visible.

Keep the window short, and never leave one open across a break.

Python 3 stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

SUFFIX = ".eval-stashed"
OVERLAY_BEGIN = "<!-- >>> agent-dotfiles overlay (managed; do not edit) >>> -->"
OVERLAY_END = "<!-- <<< agent-dotfiles overlay <<< -->"

# Arms:
#   bare        — instructions and skills moved aside entirely.
#   no-overlay  — ONLY the managed overlay block removed from the harness's
#                 root file. Everything else stays deployed, which is what
#                 makes it possible to vary a candidate's delivery surface
#                 without also varying instruction volume. `bare` cannot
#                 answer that question because it moves both at once (#87).
ARMS = ("bare", "no-overlay")

# What each harness must lose for a "bare" arm: its user-scope instruction
# file(s) and the skills path it reads. Mirrors measure_e15.HARNESS_LAYOUT;
# Copilot reads two instruction files and leaving either behind leaves the
# candidate in context.
HARNESS_PATHS: dict[str, tuple[str, ...]] = {
    "claude": (".claude/CLAUDE.md", ".claude/skills"),
    "codex": (".codex/AGENTS.md", ".agents/skills"),
    "copilot": (
        ".copilot/AGENTS.md",
        ".copilot/copilot-instructions.md",
        ".agents/skills",
    ),
    "pi": (".pi/agent/AGENTS.md", ".agents/skills"),
}


class StashError(RuntimeError):
    """Refusing to stash — bad harness, or one is already outstanding."""


class RestoreError(RuntimeError):
    """A stashed payload did not come back the way it went in."""


def _digest(path: Path) -> str:
    """Content hash of a file, or of a directory's whole file tree."""
    sha = hashlib.sha256()
    if path.is_file():
        sha.update(path.read_bytes())
        return sha.hexdigest()
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        sha.update(str(child.relative_to(path)).encode("utf-8"))
        sha.update(child.read_bytes())
    return sha.hexdigest()


def _read_state(state_path: Path) -> dict:
    if not state_path.is_file():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def outstanding(state_path: Path) -> bool:
    """True when a stash is open and has not been restored."""
    return bool(_read_state(state_path).get("entries"))


def paths_for(harness: str, home: Path) -> list[Path]:
    if harness not in HARNESS_PATHS:
        raise StashError(
            f"unknown harness {harness!r}; known: {', '.join(sorted(HARNESS_PATHS))}"
        )
    return [home / rel for rel in HARNESS_PATHS[harness]]


def _root_files(harness: str, home: Path) -> list[Path]:
    """Every root context file the harness reads that exists here.

    Copilot has two, and stripping only one leaves the candidate in context
    while the arm claims it is absent.
    """
    found = []
    for rel in HARNESS_PATHS.get(harness, ()):
        if rel.endswith(".md"):
            path = home / rel
            if path.is_file():
                found.append(path)
    return found


def stash(
    harness: str, home: Path, state_path: Path, arm: str = "bare"
) -> list[Path]:
    """Apply an arm. Returns the paths it changed."""
    if arm not in ARMS:
        raise StashError(f"unknown arm {arm!r}; known: {', '.join(ARMS)}")
    if arm == "no-overlay":
        return _stash_overlay(harness, home, state_path)
    if outstanding(state_path):
        raise StashError(
            f"a stash is already outstanding ({state_path}); restore it first "
            "— nesting would lose the original"
        )
    targets = paths_for(harness, home)
    entries, moved = [], []
    for path in targets:
        if not path.exists():
            continue  # absent is already the arm's intent
        parked = path.with_name(path.name + SUFFIX)
        if parked.exists():
            raise StashError(f"stash slot already occupied: {parked}")
        digest = _digest(path)
        path.rename(parked)
        entries.append(
            {"original": str(path), "parked": str(parked), "digest": digest}
        )
        moved.append(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"harness": harness, "entries": entries}, indent=2) + "\n",
        encoding="utf-8",
    )
    return moved


def _stash_overlay(harness: str, home: Path, state_path: Path) -> list[Path]:
    """Remove the managed overlay block, keeping the rest of the root file.

    The whole file is checksummed and parked as a copy rather than edited in
    place, so restore is the same byte-for-byte comparison every other arm
    gets — an edit-and-reinsert would rebuild the block and could differ in
    whitespace while still looking restored.
    """
    if outstanding(state_path):
        raise StashError(
            f"a stash is already outstanding ({state_path}); restore it first"
        )
    entries: list[dict] = []
    changed: list[Path] = []
    for root in _root_files(harness, home):
        text = root.read_text(encoding="utf-8")
        stripped = re.sub(
            r"\n*" + re.escape(OVERLAY_BEGIN) + r".*?" + re.escape(OVERLAY_END) + r"\n?",
            "\n",
            text,
            flags=re.S,
        )
        if stripped != text:
            parked = root.with_name(root.name + SUFFIX)
            if parked.exists():
                raise StashError(f"stash slot already occupied: {parked}")
            parked.write_text(text, encoding="utf-8")
            root.write_text(stripped, encoding="utf-8")
            entries.append({
                "original": str(root),
                "parked": str(parked),
                "digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "replace": True,
            })
            changed.append(root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"harness": harness, "arm": "no-overlay", "entries": entries},
                   indent=2) + "\n",
        encoding="utf-8",
    )
    return changed


def restore(state_path: Path) -> list[Path]:
    """Put everything back and verify it is unchanged. Idempotent."""
    state = _read_state(state_path)
    entries = state.get("entries") or []
    restored, failures = [], []
    for entry in entries:
        original, parked = Path(entry["original"]), Path(entry["parked"])
        if not parked.exists():
            failures.append(f"stashed payload missing: {parked}")
            continue
        if entry.get("replace"):
            # The original was rewritten in place, not moved; the parked copy
            # is the authority.
            original.write_text(parked.read_text(encoding="utf-8"), encoding="utf-8")
            parked.unlink()
            if _digest(original) != entry["digest"]:
                failures.append(f"{original} changed while stashed")
                continue
            restored.append(original)
            continue
        if original.exists():
            # Something recreated it while the stash was open — a sync, or
            # another agent. Keep both rather than choosing silently.
            failures.append(
                f"{original} reappeared while stashed; parked copy left at {parked}"
            )
            continue
        parked.rename(original)
        if _digest(original) != entry["digest"]:
            failures.append(f"{original} changed while stashed")
            continue
        restored.append(original)
    state_path.write_text(
        json.dumps({"harness": state.get("harness"), "entries": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    if failures:
        raise RestoreError("; ".join(failures))
    return restored


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: eval_arm.py stash <harness> <state> | restore <state> "
            "| check <state>",
            file=sys.stderr,
        )
        return 2
    command = argv[1]
    home = Path.home()
    try:
        if command == "stash":
            harness, state = argv[2], Path(argv[3])
            arm = argv[4] if len(argv) > 4 else "bare"
            moved = stash(harness, home, state, arm=arm)
            for path in moved:
                print(f"[arm] stashed {path}")
            if not moved:
                print(f"[arm] nothing to stash for {harness}")
        elif command == "restore":
            state = Path(argv[2])
            for path in restore(state):
                print(f"[arm] restored {path}")
        elif command == "check":
            state = Path(argv[2])
            if outstanding(state):
                print(f"OUTSTANDING: {state} — a harness is still stripped")
                return 1
            print("clean")
        else:
            print(f"unknown command: {command}", file=sys.stderr)
            return 2
    except (StashError, RestoreError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except IndexError:
        print("ERROR: missing argument", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
