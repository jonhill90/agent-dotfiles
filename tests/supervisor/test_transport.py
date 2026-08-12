import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SUPERVISOR_DIR = Path(__file__).resolve().parents[2] / "scripts" / "supervisor"
sys.path.insert(0, str(SUPERVISOR_DIR))

from transport import TmuxTransport  # noqa: E402


class TransportTest(unittest.TestCase):
    def test_tmux_calls_have_a_bounded_timeout(self):
        with patch("transport.subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="", stderr="")) as run:
            TmuxTransport("/opt/homebrew/bin/tmux").capture("%19")
        self.assertEqual(10, run.call_args.kwargs["timeout"])


class ForegroundArgvTest(unittest.TestCase):
    """agent-dotfiles#234: the observation that tells two harnesses sharing
    one process name apart. Every way of failing to read it must return ""
    -- which confirms nothing, so `command_verdict` withholds the lane
    rather than admitting it on a recorded value alone."""

    PS_OUTPUT = (
        "STAT ARGS\n"
        "Ss   -zsh\n"
        "S+   node /opt/homebrew/bin/copilot --allow-all\n"
        "S    node /some/background/child.js\n"
    )

    def argv_from(self, **run_kwargs):
        with patch("transport.subprocess.run", **run_kwargs) as run:
            argv = TmuxTransport().foreground_argv("/dev/ttys012")
        return argv, run

    def test_it_reads_only_the_foreground_process_group(self):
        """`ps` lists every process on the tty. Only the foreground group
        (`+` in STAT) is the one tmux derives `pane_current_command` from,
        so only it may answer for the pane -- a background child, or the
        shell above it, is a different question."""
        argv, run = self.argv_from(
            return_value=subprocess.CompletedProcess([], 0, stdout=self.PS_OUTPUT, stderr="")
        )
        self.assertEqual("node /opt/homebrew/bin/copilot --allow-all", argv)
        self.assertEqual(["ps", "-t", "ttys012", "-o", "stat=,args="], run.call_args.args[0])
        self.assertEqual(10, run.call_args.kwargs["timeout"])

    def test_every_unreadable_case_answers_with_the_empty_string(self):
        cases = {
            "no tty": (None, dict(return_value=subprocess.CompletedProcess([], 0, stdout=self.PS_OUTPUT, stderr=""))),
            "ps failed": ("/dev/ttys012", dict(return_value=subprocess.CompletedProcess([], 1, stdout="", stderr="x"))),
            "ps missing": ("/dev/ttys012", dict(side_effect=FileNotFoundError("ps"))),
            "ps timed out": ("/dev/ttys012", dict(side_effect=subprocess.TimeoutExpired("ps", 10))),
            "nothing in the foreground": (
                "/dev/ttys012",
                dict(return_value=subprocess.CompletedProcess([], 0, stdout="STAT ARGS\nSs   -zsh\n", stderr="")),
            ),
        }
        for name, (tty, run_kwargs) in cases.items():
            with self.subTest(case=name):
                with patch("transport.subprocess.run", **run_kwargs):
                    self.assertEqual("", TmuxTransport().foreground_argv(tty))


if __name__ == "__main__":
    unittest.main()
