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
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = "hi"

# Each run's raw payloads land in their own timestamped subdirectory so the
# next #44-shaped swing has the evidence on hand instead of needing a paid
# rerun to reproduce it. Retained runs are capped at a small N rather than
# an age limit: #44's open question is "how did the *next* run differ from
# the *last* one", a comparison that only needs a handful of recent
# neighbors, not a growing archive. 5 keeps a couple of swings' worth of
# history on disk without an unbounded leak.
MAX_RETAINED_RUNS = 5

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

    #44's swing is measured and explained (three billed runs, 2026-08-11):
    `turn.completed.input_tokens` is the turn's **cumulative** input across
    every model request it took, not the size of the context. Codex's own
    rollout log calls the same figure `total_token_usage` and reports the
    per-request one separately as `last_token_usage`:

        run  requests  per-request input_tokens     turn.completed total
        1    3         19,787 / 20,744 / 22,143     62,674
        2    2         19,787 / 22,029              41,816
        3    2         19,787 / 22,085              41,872

    Each tool call sends the conversation back to the model, so a turn with
    N tool calls bills roughly (N+1) x the context and reports the sum. The
    static context is the *first* request's figure, which was identical
    (19,787) in all three runs — the context is stable; the reading was not.

    That is the whole of #44: the two original runs differed only in whether
    the agent ran one shell command before answering "hi". 19,501 was a
    one-request turn (correct, by luck); 40,981 was a two-request turn.

    So this parser returns the total only when the turn took exactly one
    model request, and `None` otherwise. A blank column is the honest
    outcome: the number that exists in the stream is a billing total, and
    reporting it as a context size is what produced #44. Recovering the real
    figure from a multi-request turn needs the per-request usage, which
    `codex exec --json` does not emit (only the rollout log has it) — see
    `codex_request_count` and the operator message in `main`."""
    if codex_request_count(payload) > 1:
        return None
    total = None
    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        # The event TYPE is checked, not merely the presence of usage. This
        # function's contract has always been "the last turn.completed event",
        # but it used to accept any event carrying usage.input_tokens -- and
        # every test fixture contained only turn.completed events, so the
        # difference was invisible. A non-terminal event with usage would have
        # been read as the answer.
        if event.get("type") != "turn.completed":
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
        # Same type check as parse_codex, and for a sharper reason: this number
        # is printed to the operator as "N turn.completed events in this run".
        # Counting anything else makes the label a lie, and this counter exists
        # precisely to be trusted when the codex column is not.
        if event.get("type") != "turn.completed":
            continue
        usage = event.get("usage")
        if isinstance(usage, dict) and "input_tokens" in usage:
            count += 1
    return count


# Item types that represent the model *acting* rather than replying. Each one
# is a tool call, and every tool call sends the conversation back for another
# model request. Anything not in this set and not a plain message is counted
# too (see codex_request_count): over-counting blanks the column, which is the
# safe direction, while under-counting reports a billing total as a context.
_CODEX_MESSAGE_ITEMS = frozenset({"agent_message", "reasoning", "user_message"})


def codex_request_count(payload: str) -> int:
    """How many model requests this turn took — the unit #44 actually varied.

    A trivial prompt is supposed to produce one request, whose `input_tokens`
    is the static context. But if the agent calls a tool first, the tool's
    output goes back to the model and the whole context is re-sent, and
    `turn.completed.input_tokens` reports the *sum*. On 2026-08-11 the three
    runs took 3, 2 and 2 requests and reported 62,674, 41,816 and 41,872 for
    a context that never moved off 19,787.

    Counted as: one request per non-message item (each tool call round), plus
    one for each terminal `turn.completed` — with a floor of 1 so a stream
    with no items at all still counts as the single request that produced it.
    """
    tool_rounds = 0
    turns = 0
    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed":
            turns += 1
            continue
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") not in _CODEX_MESSAGE_ITEMS:
            tool_rounds += 1
    return tool_rounds + max(turns, 1)


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


# Harnesses whose reported number needs a caveat printed next to it.
# codex (#44): the 2.1x swing is explained -- turn.completed.input_tokens is a
# cumulative billing total across the turn's model requests, and the agent's
# tool use varies run to run (see parse_codex). parse_codex now blanks a
# multi-request turn rather than reporting the sum, so a codex number that
# prints is a genuine one-request reading. The marker stays because the caveat
# is still needed to read the column: a blank means "the probe turn used tools",
# not "codex is unavailable", and 3 runs is not yet the >=5 #44 asked for.
UNRELIABLE = {
    "codex": (
        "READ WITH CARE (#44) -- valid only for a one-request turn; blank means "
        "the probe used tools and the reported total was a billing sum, not a context"
    ),
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


def payload_dir(home: Path | None = None) -> Path:
    """Where raw payloads are persisted. Lives under the state directory,
    never the repo -- payloads are not committed."""
    base = home if home is not None else Path.home()
    return base / ".agent-dotfiles" / "measure-context-payloads"


_RUN_ID_RE = re.compile(r"^\d{8}T\d{12}Z$")


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def persist_run(base_dir: Path, run_id: str, payloads: dict[str, str]) -> dict[str, Path]:
    """Write each harness's raw stdout+stderr for this run to its own file.
    Capture only -- this must never feed back into a measured number.

    Payloads can contain system prompts, file contents and anything the
    harness echoed back -- including a token -- so directories are created
    0o700 and files 0o600, set at creation rather than chmod'd afterward, so
    there is no window in which either is group- or world-readable."""
    base_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_dir = base_dir / run_id
    run_dir.mkdir(mode=0o700, exist_ok=True)
    written: dict[str, Path] = {}
    for harness, text in payloads.items():
        path = run_dir / f"{harness}.txt"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        written[harness] = path
    return written


def prune_runs(base_dir: Path, keep: int = MAX_RETAINED_RUNS) -> list[Path]:
    """Evict the oldest run directories beyond the retention cap. Run
    directory names are UTC timestamps, so lexical sort is chronological
    sort."""
    if not base_dir.is_dir():
        return []
    runs = sorted(
        p for p in base_dir.iterdir() if p.is_dir() and _RUN_ID_RE.match(p.name)
    )
    stale = runs[:-keep] if keep > 0 else runs
    for run in stale:
        shutil.rmtree(run)
    return stale


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

    base_dir = payload_dir()
    run_dir = base_dir / _run_id()
    payloads = {h: text for h, (_value, text) in probed.items()}
    # Capture is best-effort: the probe above already spent the API call, so
    # a persistence failure (a file where base_dir should be, a symlink
    # tripping shutil.rmtree) must not eat the measurement it paid for.
    try:
        persist_run(base_dir, run_dir.name, payloads)
        prune_runs(base_dir)
    except OSError as exc:
        print(
            f"warning: could not persist probe payloads to {run_dir}: "
            f"{exc.__class__.__name__}: {exc}\n",
            file=sys.stderr,
        )
    else:
        print(f"Raw payloads written to {run_dir}\n")

    print(format_rows(measured))
    if "codex" in probed:
        codex_payload = probed["codex"][1]
        requests = codex_request_count(codex_payload)
        turns = codex_turn_count(codex_payload)
        if requests > 1:
            print(
                f"\ncodex: this probe turn took {requests} model requests "
                f"({turns} turn.completed event(s)), because the agent called "
                "tools before answering. turn.completed.input_tokens is the "
                "sum over those requests, not the context size, so the column "
                "is blank rather than inflated (#44).\n"
                "To recover the real figure, read the first `token_count` "
                "event's `last_token_usage.input_tokens` from this thread's "
                "rollout log under $CODEX_HOME/sessions — the thread id is in "
                "the `thread.started` event of the saved payload."
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
