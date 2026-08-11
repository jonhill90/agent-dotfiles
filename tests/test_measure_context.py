"""Tests for live static-context measurement (scripts/measure_context.py).

The parsers are tested against captured CLI output. Nothing here launches a
harness: a test that costs money per run does not get run.
"""

from __future__ import annotations

import io
import contextlib
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import measure_context  # noqa: E402


class ParserTests(unittest.TestCase):
    """Each harness reports usage in its own shape. The number that matters is
    the same everywhere: everything the model was sent before it answered,
    cached or not. Counting only the uncached part reports 2 tokens for a
    24,000-token context."""

    def test_claude_sums_fresh_cache_read_and_cache_creation(self) -> None:
        payload = (
            '{"usage": {"input_tokens": 2, "cache_read_input_tokens": 18270,'
            ' "cache_creation_input_tokens": 6445, "output_tokens": 9}}'
        )
        self.assertEqual(measure_context.parse_claude(payload), 24717)

    def test_codex_reads_input_tokens_which_already_include_cached(self) -> None:
        payload = (
            '{"type":"thread.started"}\n'
            '{"type":"turn.completed","usage":{"input_tokens":62110,'
            '"cached_input_tokens":39424,"output_tokens":354}}\n'
        )
        self.assertEqual(measure_context.parse_codex(payload), 62110)

    def test_codex_turn_count_is_one_for_a_normal_run(self) -> None:
        payload = (
            '{"type":"thread.started"}\n'
            '{"type":"turn.completed","usage":{"input_tokens":19501}}\n'
        )
        self.assertEqual(measure_context.codex_turn_count(payload), 1)

    def test_codex_turn_count_flags_more_than_one_turn(self) -> None:
        """#44's original hypothesis, kept as a regression test for the
        last-turn-wins behaviour even though the measured cause turned out to
        be different. Three billed runs on 2026-08-11 emitted exactly *one*
        `turn.completed` each and still swung 41,816 -> 62,674; the varying
        unit was model requests inside one turn, not turns. See
        `test_codex_refuses_a_turn_that_took_more_than_one_model_request`."""
        payload = (
            '{"type":"turn.completed","usage":{"input_tokens":19501}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":40981}}\n'
        )
        self.assertEqual(measure_context.codex_turn_count(payload), 2)
        self.assertIsNone(measure_context.parse_codex(payload))

    # --- #44: the measured cause -------------------------------------------
    #
    # Fixtures below are minimal reconstructions of the event shapes observed
    # in three billed runs on 2026-08-11 (payloads under
    # ~/.agent-dotfiles/measure-context-payloads, not committed: they contain
    # system prompts and vault contents). The numbers are the real ones.
    #
    # What the rollout logs showed, per model request within the single turn:
    #
    #   run   requests   last_token_usage.input_tokens   turn.completed total
    #   1     3          19,787 / 20,744 / 22,143        62,674
    #   2     2          19,787 / 22,029                 41,816
    #   3     2          19,787 / 22,085                 41,872
    #
    # `turn.completed.input_tokens` is codex's *cumulative* input across every
    # request in the turn -- the same field the rollout log calls
    # `total_token_usage`. It is a billing total, not a context size. The
    # static context is the first request's figure, which was byte-identical
    # (19,787) in all three runs.

    def test_codex_request_count_is_one_when_the_model_answered_directly(self) -> None:
        """No tool calls means one model request, so the turn total *is* the
        static context and the number can be trusted."""
        payload = (
            '{"type":"thread.started","thread_id":"t"}\n'
            '{"type":"turn.started"}\n'
            '{"type":"item.completed","item":{"id":"item_0",'
            '"type":"agent_message","text":"Hi."}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":19787}}\n'
        )
        self.assertEqual(measure_context.codex_request_count(payload), 1)
        self.assertEqual(measure_context.parse_codex(payload), 19787)

    def test_codex_request_count_counts_each_tool_call_round(self) -> None:
        """Every tool call sends the conversation back to the model, so N tool
        calls in a turn means N+1 requests. Run 1 of 2026-08-11: two shell
        commands, three requests."""
        payload = (
            '{"type":"thread.started","thread_id":"t"}\n'
            '{"type":"item.completed","item":{"id":"item_0",'
            '"type":"agent_message","text":"I will check memory first."}}\n'
            '{"type":"item.completed","item":{"id":"item_1",'
            '"type":"command_execution","command":"sed -n 1,220p SKILL.md",'
            '"exit_code":0}}\n'
            '{"type":"item.completed","item":{"id":"item_2",'
            '"type":"command_execution","command":"sed -n 1,220p index.md",'
            '"exit_code":0}}\n'
            '{"type":"item.completed","item":{"id":"item_3",'
            '"type":"agent_message","text":"Hi."}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":62674}}\n'
        )
        self.assertEqual(measure_context.codex_request_count(payload), 3)

    def test_codex_refuses_a_turn_that_took_more_than_one_model_request(self) -> None:
        """The #44 swing, explained and refused. 41,816 is not a 41,816-token
        context: it is two requests of roughly 20,900 summed. Returning it
        would report a billing total as a context size -- and it is what
        produced 19,501 -> 40,981, since those two runs differed only in
        whether the agent ran one shell command before answering.

        Blank is the correct output. An inflated number that reads as a
        measurement is the fail-open this estate keeps removing."""
        payload = (
            '{"type":"thread.started","thread_id":"t"}\n'
            '{"type":"item.completed","item":{"id":"item_1",'
            '"type":"command_execution","command":"sed -n 1,220p index.md",'
            '"exit_code":0}}\n'
            '{"type":"item.completed","item":{"id":"item_2",'
            '"type":"agent_message","text":"Hi."}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":41816}}\n'
        )
        self.assertEqual(measure_context.codex_request_count(payload), 2)
        self.assertIsNone(measure_context.parse_codex(payload))

    def test_codex_ignores_usage_on_events_that_are_not_turn_completed(self) -> None:
        """Both docstrings say these functions key on `turn.completed`. Neither
        looked at the event type -- they took any event carrying
        `usage.input_tokens`. Every fixture above contains only
        `turn.completed` events, so all of them passed with or without the
        filter, and the promise in the docstring was never tested.

        This matters for #44 specifically: the count is reported to the operator
        as "N turn.completed events in this run". If a non-terminal event
        carries usage, that number names something it did not count, and the
        diagnostic built to explain the 2.1x swing becomes another thing to
        mistrust.
        """
        payload = (
            '{"type":"thread.started"}\n'
            '{"type":"turn.completed","usage":{"input_tokens":19501}}\n'
            '{"type":"item.completed","usage":{"input_tokens":999999}}\n'
        )
        self.assertEqual(measure_context.codex_turn_count(payload), 1)
        self.assertEqual(measure_context.parse_codex(payload), 19501)

    def test_codex_returns_none_when_usage_exists_but_no_turn_completed(self) -> None:
        """Fail loud rather than quietly wrong. If codex ever renames the
        terminal event, the honest outcome is an empty column that someone
        investigates -- not a confident number taken from whatever event
        happened to be last. An unreadable measurement reported as a reading is
        the failure this estate keeps hitting.
        """
        payload = '{"type":"item.completed","usage":{"input_tokens":40981}}\n'
        self.assertIsNone(measure_context.parse_codex(payload))
        self.assertEqual(measure_context.codex_turn_count(payload), 0)

    def test_pi_sums_input_and_cache_read_from_the_last_usage(self) -> None:
        payload = (
            '{"message":{"usage":{"input":0,"cacheRead":0,"totalTokens":0}}}\n'
            '{"message":{"usage":{"input":1254,"cacheRead":2560,'
            '"totalTokens":3828}}}\n'
        )
        self.assertEqual(measure_context.parse_pi(payload), 3814)

    def test_copilot_reads_its_printed_token_line(self) -> None:
        payload = "QUOTA-OK\n\nChanges +0 -0\nTokens     ↑ 30.4k (30.4k written) • ↓ 10\n"
        self.assertEqual(measure_context.parse_copilot(payload), 30400)

    def test_copilot_handles_plain_integers(self) -> None:
        self.assertEqual(
            measure_context.parse_copilot("Tokens ↑ 8,912 (8,912 written) • ↓ 4"), 8912
        )

    def test_a_parser_returns_none_rather_than_guessing(self) -> None:
        for parse in (
            measure_context.parse_claude,
            measure_context.parse_codex,
            measure_context.parse_pi,
            measure_context.parse_copilot,
        ):
            self.assertIsNone(parse("no usage here"))


class PayloadPersistenceTests(unittest.TestCase):
    """#44: the raw JSONL from the two runs that swung 19,501 -> 40,981 no
    longer exists, so the leading hypothesis can't be checked without
    spending a paid rerun. These tests drive a fake harness command --
    never a real CLI -- to prove capture and retention work without that
    cost."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base_dir = Path(self._tmp.name) / "measure-context-payloads"

    def test_probe_payload_is_persisted_verbatim(self) -> None:
        fake_command = [
            sys.executable,
            "-c",
            "print('{\"usage\": {\"input_tokens\": 5}}')",
        ]
        original = measure_context.HARNESS_COMMANDS.get("claude")
        measure_context.HARNESS_COMMANDS["claude"] = fake_command
        try:
            value, text = measure_context.probe("claude")
        finally:
            if original is not None:
                measure_context.HARNESS_COMMANDS["claude"] = original

        self.assertEqual(value, 5)
        written = measure_context.persist_run(self.base_dir, "20260101T000000000000Z", {"claude": text})
        persisted = written["claude"].read_text(encoding="utf-8")
        self.assertEqual(persisted, text)
        # What the parser saw is exactly what landed on disk.
        self.assertEqual(measure_context.parse_claude(persisted), value)

    def test_prune_runs_evicts_oldest_beyond_the_cap(self) -> None:
        run_ids = [f"2026010{n}T000000000000Z" for n in range(1, 8)]
        for run_id in run_ids:
            measure_context.persist_run(self.base_dir, run_id, {"claude": "payload"})

        removed = measure_context.prune_runs(self.base_dir, keep=3)

        remaining = sorted(p.name for p in self.base_dir.iterdir())
        self.assertEqual(remaining, run_ids[-3:])
        self.assertEqual(sorted(p.name for p in removed), run_ids[:-3])

    def test_prune_runs_is_a_noop_under_the_cap(self) -> None:
        measure_context.persist_run(self.base_dir, "20260101T000000000000Z", {"claude": "x"})
        removed = measure_context.prune_runs(self.base_dir, keep=5)
        self.assertEqual(removed, [])
        self.assertEqual(len(list(self.base_dir.iterdir())), 1)

    def test_prune_runs_ignores_directories_it_did_not_create(self) -> None:
        """#105: a manual note dropped next to the run directories sorted
        before the timestamps and was deleted as if it were the oldest run.
        Pruning must only ever touch directories matching the run-id
        pattern persist_run itself writes."""
        self.base_dir.mkdir(parents=True)
        manual_note = self.base_dir / "0-manual-note"
        manual_note.mkdir()
        (manual_note / "notes.txt").write_text("do not delete", encoding="utf-8")
        run_ids = [f"2026010{n}T000000000000Z" for n in range(1, 8)]
        for run_id in run_ids:
            measure_context.persist_run(self.base_dir, run_id, {"claude": "payload"})

        removed = measure_context.prune_runs(self.base_dir, keep=3)

        self.assertTrue(manual_note.is_dir())
        self.assertNotIn(manual_note, removed)
        remaining = sorted(p.name for p in self.base_dir.iterdir())
        self.assertEqual(remaining, ["0-manual-note", *run_ids[-3:]])

    def test_persist_run_sets_restrictive_permissions(self) -> None:
        """#105: payloads can contain system prompts, file contents and
        anything the harness echoed -- including a token. Directories must
        be 0o700 and files 0o600, not the 0o755/0o644 world-readable
        defaults."""
        written = measure_context.persist_run(
            self.base_dir, "20260101T000000000000Z", {"claude": "secret payload"}
        )

        run_dir = self.base_dir / "20260101T000000000000Z"
        self.assertEqual(stat.S_IMODE(run_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.base_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(written["claude"].stat().st_mode), 0o600)

    def test_main_survives_a_persist_failure(self) -> None:
        """#105: persist_run/prune_runs ran unguarded after the billed
        probe() calls, so a NotADirectoryError (base_dir exists as a file)
        crashed the tool after the API spend and printed nothing. Capture
        must warn on stderr and the table must still print."""
        fake_command = [sys.executable, "-c", "print('{\"usage\": {\"input_tokens\": 5}}')"]
        original_commands = dict(measure_context.HARNESS_COMMANDS)
        measure_context.HARNESS_COMMANDS.clear()
        measure_context.HARNESS_COMMANDS["claude"] = fake_command
        original_payload_dir = measure_context.payload_dir
        blocked = Path(self._tmp.name) / "blocked-base-dir"
        blocked.write_text("not a directory", encoding="utf-8")
        measure_context.payload_dir = lambda home=None: blocked
        try:
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = measure_context.main(["measure_context.py", "claude"])
        finally:
            measure_context.HARNESS_COMMANDS.clear()
            measure_context.HARNESS_COMMANDS.update(original_commands)
            measure_context.payload_dir = original_payload_dir

        self.assertEqual(exit_code, 0)
        self.assertIn("claude", stdout.getvalue())
        self.assertIn("5", stdout.getvalue())
        self.assertIn("warning", stderr.getvalue().lower())
        self.assertIn(str(blocked), stderr.getvalue())


class ReportTests(unittest.TestCase):
    def test_unmeasured_harness_is_reported_not_dropped(self) -> None:
        rows = measure_context.format_rows({"pi": 3814, "codex": None})
        self.assertIn("3,814", rows)
        self.assertIn("not measured", rows)

    def test_codex_row_carries_an_unreliability_marker_when_measured(self) -> None:
        """#44: the codex column must not print as if it were as trustworthy as
        the other three, even when a value came back.

        These three assert on `#44` rather than the literal word `UNRELIABLE`.
        The wording changed once the cause was measured -- a number that prints
        now means a one-request turn, which is a real reading, so "unreliable"
        overstated it -- and a test that pins prose stops the note from being
        corrected. What must not change is that every codex row carries a
        marker pointing at the issue that explains how to read it."""
        rows = measure_context.format_rows({"codex": 19501})
        self.assertIn("19,501", rows)
        self.assertIn("#44", rows)

    def test_codex_row_carries_the_marker_even_when_not_measured(self) -> None:
        rows = measure_context.format_rows({"codex": None})
        self.assertIn("not measured", rows)
        self.assertIn("#44", rows)

    def test_other_harnesses_carry_no_unreliability_marker(self) -> None:
        rows = measure_context.format_rows({"claude": 29708, "pi": 8198})
        self.assertNotIn("#44", rows)


if __name__ == "__main__":
    unittest.main()
