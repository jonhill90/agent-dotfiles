"""agent-dotfiles#261: harness_session.py must resolve a CODEX session id,
not just a claude one -- before this, every codex lane recorded
`harness_session_id=""` at dispatch and restore.sh could never recover it,
even though restore's refusal was itself correct behaviour.

These fixtures are built to the SAME shape codex actually writes, measured
live on 2026-08-12 against a real `codex` rollout file (v0.147.0):
`$CODEX_HOME/sessions/<yyyy>/<mm>/<dd>/rollout-<local-ts>-<uuid>.jsonl`,
first line `type: "session_meta"` carrying `payload.session_id` and
`payload.cwd`, every line carrying a top-level ISO `timestamp`.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

SUPERVISOR_DIR = Path(__file__).resolve().parents[2] / "scripts" / "supervisor"
sys.path.insert(0, str(SUPERVISOR_DIR))

import harness_session  # noqa: E402


CODEX_ID = "019ff758-62f0-74e3-a925-66448003107f"
CLAUDE_ID = "7cef6d59-1111-4111-8111-111111111111"


def _epoch(ts_iso):
    return datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).timestamp()


def _pin_mtime(path, ts_iso):
    # The resolver's "began during this dispatch" test reads BOTH the file's
    # mtime and its first entry's own timestamp -- pin the mtime explicitly
    # rather than relying on whatever wall-clock moment this test happened
    # to run at, so `since` comparisons are deterministic regardless of the
    # real clock.
    epoch = _epoch(ts_iso)
    os.utime(path, (epoch, epoch))


def _write_codex_rollout(root, *, session_id, marker, ts_iso, day="2026/08/12", name=None):
    day_dir = Path(root) / "sessions" / day
    day_dir.mkdir(parents=True, exist_ok=True)
    fname = name or f"rollout-2026-08-12T14-59-52-{session_id}.jsonl"
    path = day_dir / fname
    lines = [
        {
            "timestamp": ts_iso,
            "ordinal": 0,
            "type": "session_meta",
            "payload": {
                "session_id": session_id,
                "id": session_id,
                "timestamp": ts_iso,
                "cwd": marker,
                "originator": "codex-tui",
            },
        },
        {
            "timestamp": ts_iso,
            "ordinal": 1,
            "type": "turn_context",
            "payload": {"cwd": marker},
        },
    ]
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line) + "\n")
    _pin_mtime(path, ts_iso)
    return path


def _write_claude_transcript(root, *, session_id, marker, ts_iso, slug="lanes"):
    proj_dir = Path(root) / ".claude" / "projects" / slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    path = proj_dir / f"{session_id}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "mode", "sessionId": session_id}) + "\n")
        handle.write(
            json.dumps(
                {"type": "user", "sessionId": session_id, "timestamp": ts_iso, "message": f"brief for {marker}"}
            )
            + "\n"
        )
    _pin_mtime(path, ts_iso)
    return path


class CodexResolveTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.codex_home = Path(self._tmp.name) / "codex-home"
        self.ts_iso = "2026-08-12T19:00:47.824Z"  # epoch 1786561247.824
        self.since = 1786561000.0  # a few seconds before `ts_iso`

    def test_resolves_the_one_matching_rollout(self):
        _write_codex_rollout(
            self.codex_home, session_id=CODEX_ID, marker="/worktrees/lane-a", ts_iso=self.ts_iso
        )
        got = harness_session.resolve(
            harness="codex",
            marker="/worktrees/lane-a",
            since=self.since,
            codex_home=str(self.codex_home),
            timeout=0,
        )
        self.assertEqual(got, CODEX_ID)

    def test_refuses_when_no_rollout_carries_the_marker(self):
        _write_codex_rollout(
            self.codex_home, session_id=CODEX_ID, marker="/worktrees/lane-a", ts_iso=self.ts_iso
        )
        with self.assertRaises(LookupError):
            harness_session.resolve(
                harness="codex",
                marker="/worktrees/lane-does-not-exist",
                since=self.since,
                codex_home=str(self.codex_home),
                timeout=0,
            )

    def test_refuses_when_two_lanes_both_carry_the_marker(self):
        # A marker string that is a substring of another lane's marker (e.g.
        # a shared parent path) must never resolve silently -- ambiguous
        # means refuse, same as the claude path.
        _write_codex_rollout(
            self.codex_home,
            session_id=CODEX_ID,
            marker="shared-prefix",
            ts_iso=self.ts_iso,
            name="rollout-2026-08-12T14-59-52-019ff758-62f0-74e3-a925-66448003107f.jsonl",
        )
        other_id = "029ff758-62f0-74e3-a925-66448003107f"
        _write_codex_rollout(
            self.codex_home,
            session_id=other_id,
            marker="shared-prefix",
            ts_iso=self.ts_iso,
            name="rollout-2026-08-12T15-01-02-029ff758-62f0-74e3-a925-66448003107f.jsonl",
        )
        with self.assertRaises(LookupError):
            harness_session.resolve(
                harness="codex",
                marker="shared-prefix",
                since=self.since,
                codex_home=str(self.codex_home),
                timeout=0,
            )

    def test_ignores_a_rollout_from_before_this_dispatch(self):
        # Same marker, but the transcript began well before `since` -- an
        # old conversation in the same worktree must not be mistaken for
        # this dispatch's fresh one.
        _write_codex_rollout(
            self.codex_home, session_id=CODEX_ID, marker="/worktrees/lane-a", ts_iso=self.ts_iso
        )
        with self.assertRaises(LookupError):
            harness_session.resolve(
                harness="codex",
                marker="/worktrees/lane-a",
                since=self.since + 10_000,  # after ts_iso -- transcript predates this dispatch
                codex_home=str(self.codex_home),
                timeout=0,
            )

    def test_ignores_a_file_whose_declared_id_disagrees_with_its_name(self):
        # The mutation case #261 asks be proven, at the resolver layer: a
        # rollout whose own content does not match its filename must never
        # be handed back as a resumable id.
        path = _write_codex_rollout(
            self.codex_home, session_id=CODEX_ID, marker="/worktrees/lane-a", ts_iso=self.ts_iso
        )
        mutated = path.read_text().replace(CODEX_ID, "ffffffff-ffff-4fff-8fff-ffffffffffff", 1)
        # Only mutate the FIRST occurrence (the payload.session_id line);
        # the filename on disk still says CODEX_ID.
        path.write_text(mutated)
        _pin_mtime(path, self.ts_iso)
        with self.assertRaises(LookupError):
            harness_session.resolve(
                harness="codex",
                marker="/worktrees/lane-a",
                since=self.since,
                codex_home=str(self.codex_home),
                timeout=0,
            )

    def test_missing_sessions_directory_refuses_rather_than_crashing(self):
        with self.assertRaises(LookupError):
            harness_session.resolve(
                harness="codex",
                marker="/worktrees/lane-a",
                since=self.since,
                codex_home=str(self.codex_home / "does-not-exist"),
                timeout=0,
            )


class ClaudeResolveStillWorksTests(unittest.TestCase):
    """Adding codex must not disturb the claude path -- this is #261's
    negative guardrail, not new claude coverage."""

    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        self.since = 1_000_000.0
        self.ts_iso = "2026-08-12T19:00:47.824Z"

    def test_resolves_the_one_matching_transcript(self):
        _write_claude_transcript(self.home, session_id=CLAUDE_ID, marker="/worktrees/lane-b", ts_iso=self.ts_iso)
        got = harness_session.resolve(
            harness="claude",
            marker="/worktrees/lane-b",
            since=self.since,
            home=str(self.home),
            timeout=0,
        )
        self.assertEqual(got, CLAUDE_ID)


class UnknownHarnessTests(unittest.TestCase):
    def test_refuses_a_harness_with_no_resolver(self):
        with self.assertRaises(LookupError):
            harness_session.resolve(harness="copilot", marker="x", since=0, timeout=0)


if __name__ == "__main__":
    unittest.main()
