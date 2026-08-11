#!/usr/bin/env python3
"""Ask each harness how large its static context actually is.

`measure_e15.py` estimates the footprint *this repository deploys* by reading
files on disk. It cannot see what a harness ships itself, and on Claude Code
that gap was 5.3x (#5). This script closes it from the other direction: send
a one-token prompt and read the input-token count the CLI reports back. That
number is the whole static context — system prompt, tool definitions, skills,
instructions, memory — measured by the thing that pays for it.

The two are complements, not rivals. `measure_e15` is free, runs in CI, and
governs what we control. This costs an API call per harness and answers what
is actually being sent.

**Every measurement costs money.** One trivial turn per harness. Nothing here
runs automatically; it is invoked deliberately.

Method notes that matter for reading the numbers:

* Cached tokens count. A prompt cache changes what is billed, not what the
  model is sent, and "input_tokens: 2" for a 24,000-token context is the
  wrong answer to this question.
* Run-to-run variance is real. Repeat probes on one harness moved 3,814 ->
  5,723 and 24,717 -> 27,113, because cache state and session context differ.
  Treat a difference under a few thousand tokens as noise, and take the
  smallest of several runs when comparing.
* Numbers are not comparable across harnesses as a quality judgement. They
  use different models and tokenizers, and a larger context is not worse if
  it buys more capability. What they are good for is *deltas* — the same
  harness with a population disabled — and for noticing an order-of-magnitude
  difference that no one intended.

Python 3 stdlib only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

PROBE = "hi"

# Argument vectors that produce machine-readable usage for a trivial turn.
HARNESS_COMMANDS: dict[str, list[str]] = {
    "claude": ["claude", "-p", "--output-format", "json", PROBE],
    "codex": ["codex", "exec", "--skip-git-repo-check", "--json", PROBE],
    "pi": ["pi", "-p", "--mode", "json", PROBE],
    "copilot": ["copilot", "-p", PROBE, "--allow-all-tools"],
}


def parse_claude(payload: str) -> int | None:
    """Claude reports fresh, cache-read and cache-creation separately."""
    try:
        usage = json.loads(payload).get("usage") or {}
    except ValueError:
        return None
    keys = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    if not any(k in usage for k in keys):
        return None
    return sum(int(usage.get(k, 0)) for k in keys)


def parse_codex(payload: str) -> int | None:
    """Codex emits JSONL; `turn.completed` carries a total that already
    includes the cached portion, so cached tokens must not be added again.

    Known unreliable (#44): a rerun against an unchanged deployed state
    swung 19,501 -> 40,981 (2.1x). The cause is not confirmed. This parser
    trusts the *last* `turn.completed` event, on the assumption that one
    trivial prompt produces exactly one turn — but nothing here checks that
    assumption. If a run emits more than one (extra tool-discovery turns, a
    resumed session's prior turns replayed into this stream), the "last"
    event's `input_tokens` already includes the earlier turns' conversation
    history, and this function would silently return the inflated total.
    `codex_turn_count()` exposes the count so a caller can flag that instead
    of trusting it blind; callers must still treat this column as unreliable
    even when the count is 1, since #44's swing has not been explained."""
    total = None
    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        usage = event.get("usage")
        if isinstance(usage, dict) and "input_tokens" in usage:
            total = int(usage["input_tokens"])
    return total


def codex_turn_count(payload: str) -> int:
    """Count `turn.completed` events carrying usable usage. parse_codex
    trusts only the last one; more than one means that trust is unfounded —
    see the #44 note on parse_codex."""
    count = 0
    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        usage = event.get("usage")
        if isinstance(usage, dict) and "input_tokens" in usage:
            count += 1
    return count


def parse_pi(payload: str) -> int | None:
    """Pi streams events; take the last non-zero usage, which is the final
    accounting rather than the zeroed `message_start`."""
    total = None
    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        usage = (event.get("message") or {}).get("usage") or event.get("usage")
        if isinstance(usage, dict) and usage.get("totalTokens"):
            total = int(usage.get("input", 0)) + int(usage.get("cacheRead", 0))
    return total


def parse_copilot(payload: str) -> int | None:
    """Copilot prints a human-facing token line; there is no JSON mode."""
    match = re.search(r"Tokens\s*[↑^]\s*([\d,.]+)\s*([kKmM])?", payload)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    return int(value * {"k": 1_000, "m": 1_000_000}.get(suffix, 1))


PARSERS = {
    "claude": parse_claude,
    "codex": parse_codex,
    "pi": parse_pi,
    "copilot": parse_copilot,
}


# Harnesses whose reported number is known not to be trustworthy yet.
# codex (#44): consecutive runs against an identical deployed state swung
# 19,501 -> 40,981 (2.1x); the cause is unconfirmed (see parse_codex). A
# number this volatile must not be printed as if it were comparable to the
# other columns, so every codex row carries this marker regardless of value
# -- silence is the failure mode being avoided here, not just a wrong number.
UNRELIABLE = {
    "codex": "UNRELIABLE (#44) -- 2.1x swing between runs on unchanged state, cause unconfirmed",
}


def probe(harness: str, timeout: int = 240) -> tuple[int | None, str]:
    """Run one trivial turn and return (static-context size, raw output)."""
    command = HARNESS_COMMANDS.get(harness)
    if not command:
        return None, ""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    text = result.stdout + result.stderr
    return PARSERS[harness](text), text


def format_rows(measured: dict[str, int | None]) -> str:
    lines = [f"{'harness':10} {'static context':>15}"]
    for harness, tokens in measured.items():
        shown = f"{tokens:,}" if tokens else "not measured"
        lines.append(f"{harness:10} {shown:>15}")
        note = UNRELIABLE.get(harness)
        if note:
            lines.append(f"{'':10} {note}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    wanted = [a for a in argv[1:] if not a.startswith("-")] or list(HARNESS_COMMANDS)
    unknown = [h for h in wanted if h not in HARNESS_COMMANDS]
    if unknown:
        print(f"unknown harness: {', '.join(unknown)}", file=sys.stderr)
        return 2
    print(
        "Each harness below is sent one trivial prompt. This costs an API "
        "call per harness.\n"
    )
    probed = {h: probe(h) for h in wanted}
    measured = {h: value for h, (value, _text) in probed.items()}
    print(format_rows(measured))
    if "codex" in probed:
        turns = codex_turn_count(probed["codex"][1])
        if turns > 1:
            print(
                f"\ncodex: {turns} turn.completed events in this run — "
                "parse_codex trusts only the last, so this number likely "
                "includes earlier turns' conversation history (see #44)."
            )
    print(
        "\nWhat this counts: everything sent before the model answered, "
        "cached or not.\nNot comparable across harnesses as a judgement — "
        "different models and tokenizers.\nUse it for deltas on one harness, "
        "and for differences nobody intended."
    )
    return 0 if any(measured.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
