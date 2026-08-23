"""Bridges tests/test_status.sh into the one command CI already runs.

`scripts/status.sh` is a bash script testing bash things (real processes,
real ppid checks, real exit codes) -- rewriting that suite in Python would
either lose fidelity or just reimplement subprocess/ps calls badly. Instead
this wraps the existing bash suite the same shape agent-supervisor's own
`tests/supervisor/test_shell_suites.py` uses for its bash suites: run it as
a subprocess, fail the Python test if it exits non-zero, and surface its own
ok/FAIL lines as the failure message so `python -m unittest discover -s
tests -v` (agent-dotfiles' actual CI step, see .github/workflows/validate.yml)
exercises it without a second, parallel bash-test-runner concept.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
STATUS_SUITE = TESTS_DIR / "test_status.sh"


class TestStatusShellSuite(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "darwin", "status.sh's ps/sysctl fakes assume macOS")
    def test_status_sh_suite_passes(self) -> None:
        result = subprocess.run(
            ["bash", str(STATUS_SUITE)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"tests/test_status.sh failed (exit {result.returncode}):\n"
                f"{result.stdout}\n{result.stderr}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
