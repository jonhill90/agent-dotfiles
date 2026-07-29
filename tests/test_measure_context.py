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


if __name__ == "__main__":
    unittest.main()
