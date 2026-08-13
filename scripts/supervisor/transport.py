"""Small tmux transport; terminal output stays inside the adapter process."""

from __future__ import annotations

import subprocess
import time


TMUX_TIMEOUT_SECONDS = 10


class TmuxTransport:
    def __init__(self, tmux_bin="tmux", *, timeout=TMUX_TIMEOUT_SECONDS):
        self.tmux_bin = tmux_bin
        self.timeout = timeout

    def _run(self, *args, check=True):
        return subprocess.run(
            [self.tmux_bin, *args],
            check=check,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

    def metadata(self, target):
        fmt = (
            "#{pane_id}|#{pane_current_command}|#{pane_current_path}"
            "|#{socket_path}|#{session_created}|#{session_id}|#{pane_tty}"
        )
        output = self._run("display-message", "-p", "-t", target, fmt).stdout.rstrip("\n")
        pane_id, command, path, socket_path, session_created, session_id, tty = output.split("|", 6)
        return {
            "pane_id": pane_id,
            "command": command,
            "path": path,
            "server_id": f"{socket_path}:{session_created}",
            "session_id": session_id,
            "argv": self.foreground_argv(tty),
        }

    def foreground_argv(self, tty):
        """The full command line(s) of the pane's foreground process group.

        agent-dotfiles#234. `#{pane_current_command}` is a process NAME, and
        `codex` and `copilot` share one (`node`) -- so it cannot distinguish
        them and the plausibility check accepted either. argv can: a Node
        harness's command line carries the script path, which names the tool
        (`node /opt/homebrew/bin/copilot`).

        This is a MEASUREMENT, not a record, in the sense CLAUDE.md's "tmux
        is not a database" rule uses: the kernel wrote it, not this system,
        so reading it is fine. `ps` is asked for the pane's tty and filtered
        to the FOREGROUND process group (`+` in `stat`) -- the same
        processes tmux derives `pane_current_command` from, so the two
        readings describe one thing rather than two.

        Every failure returns "" -- no tty, `ps` missing, `ps` erroring, a
        timeout. "" cannot confirm anything, and `command_verdict` treats a
        shared command it cannot confirm as ambiguous, i.e. refused. The
        failure direction is the #124/#126 one: unreadable withholds.
        """
        if not tty:
            return ""
        name = tty[len("/dev/"):] if tty.startswith("/dev/") else tty
        try:
            proc = subprocess.run(
                ["ps", "-t", name, "-o", "stat=,args="],
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        if proc.returncode != 0:
            return ""
        lines = []
        for line in proc.stdout.splitlines():
            stat, _, args = line.strip().partition(" ")
            args = args.strip()
            if "+" in stat and args:
                lines.append(args)
        return "\n".join(lines)

    def capture(self, target, lines=25):
        return self._run("capture-pane", "-p", "-J", "-t", target, "-S", f"-{int(lines)}").stdout

    def set_option(self, target, name, value):
        self._run("set-option", "-p", "-t", target, name, value)

    def get_option(self, target, name):
        return self._run("display-message", "-p", "-t", target, f"#{{{name}}}").stdout.rstrip("\n")

    def send_literal(self, target, payload):
        self._run("send-keys", "-t", target, "C-u")
        self._run("send-keys", "-t", target, "-l", "--", payload)
        time.sleep(0.1)
        self._run("send-keys", "-t", target, "Enter")
        time.sleep(0.5)

    def respawn_pane(self, target):
        """Kill whatever is running in `target` and restart its command.

        Used by `recycle.respawn_supervisor` to replace a long-lived
        supervisor session with a fresh one; `send_literal` afterward seeds
        the tick prompt. `-k` kills the current pane process first, so this
        is destructive to whatever was running there -- it is never called
        against a pane with unflushed state.
        """
        self._run("respawn-pane", "-k", "-t", target)
