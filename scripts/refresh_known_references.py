#!/usr/bin/env python3
"""Refresh tests/fixtures/known_references.json from GitHub.

Maintenance tool, not part of CI. tests/test_cross_repo_references.py must
run offline, so it checks bare '#N' citations against a manifest checked
into the repository rather than calling the GitHub API itself. Run this
script (requires `gh` authenticated against this repository) whenever a
new issue or PR is opened and referenced by number in a doc, or whenever
the reference guard reports a false positive caused by a stale manifest:

    python3 scripts/refresh_known_references.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = "jonhill90/agent-dotfiles"
MANIFEST_PATH = Path(__file__).parents[1] / "tests" / "fixtures" / "known_references.json"


def fetch_numbers(kind: str) -> list[int]:
    result = subprocess.run(
        ["gh", kind, "list", "--repo", REPO, "--state", "all", "--json", "number", "--limit", "1000"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [item["number"] for item in json.loads(result.stdout)]


def main() -> int:
    numbers = sorted(set(fetch_numbers("issue")) | set(fetch_numbers("pr")))
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "repo": REPO,
                "generated_by": "scripts/refresh_known_references.py",
                "numbers": numbers,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(numbers)} known reference numbers to {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
