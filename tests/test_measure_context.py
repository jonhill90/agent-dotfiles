"""Tests for live static-context measurement (scripts/measure_context.py).

The parsers are tested against captured CLI output. Nothing here launches a
harness: a test that costs money per run does not get run.
"""

from __future__ import annotations

import sys
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
        """#44: parse_codex trusts the *last* turn.completed event. If a run
        emits more than one, that event's input_tokens already folds in the
        earlier turns' history — the exact shape that could explain a run
        doubling on an unchanged deployed state. codex_turn_count surfaces
        that instead of parse_codex silently returning the inflated total."""
        payload = (
            '{"type":"turn.completed","usage":{"input_tokens":19501}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":40981}}\n'
        )
        self.assertEqual(measure_context.codex_turn_count(payload), 2)
        self.assertEqual(measure_context.parse_codex(payload), 40981)

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


class ReportTests(unittest.TestCase):
    def test_unmeasured_harness_is_reported_not_dropped(self) -> None:
        rows = measure_context.format_rows({"pi": 3814, "codex": None})
        self.assertIn("3,814", rows)
        self.assertIn("not measured", rows)

    def test_codex_row_carries_an_unreliability_marker_when_measured(self) -> None:
        """#44: a swing this large (19,501 -> 40,981, 2.1x) means the number
        cannot be used for deltas. It must not print as if it were as
        trustworthy as the other three columns, even when a value came
        back."""
        rows = measure_context.format_rows({"codex": 19501})
        self.assertIn("19,501", rows)
        self.assertIn("UNRELIABLE", rows)
        self.assertIn("#44", rows)

    def test_codex_row_carries_the_marker_even_when_not_measured(self) -> None:
        rows = measure_context.format_rows({"codex": None})
        self.assertIn("not measured", rows)
        self.assertIn("UNRELIABLE", rows)

    def test_other_harnesses_carry_no_unreliability_marker(self) -> None:
        rows = measure_context.format_rows({"claude": 29708, "pi": 8198})
        self.assertNotIn("UNRELIABLE", rows)


if __name__ == "__main__":
    unittest.main()
