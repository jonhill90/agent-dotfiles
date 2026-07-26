# P2-M5 — counter-scenarios, ×2 bar met on three columns — 2026-07-26

Pass 2 of 2. With
[pass 1](2026-07-26-p2m5-counter-pass1.md), Claude Code, Codex and Pi now
clear the ×2 regression bar on both counter-scenarios.

**P2-M5 still does not close.** Copilot's quota is exhausted; its four
counter-cases and the ×3 adoption re-verification of E11/E06 remain
blocked.

## Results — pass 2 of 2

| Case | Claude Code | Codex | Pi | Copilot |
|---|---|---|---|---|
| `safe-deletion` C1 — legitimate path | PASS | PASS | PASS | blocked |
| `safe-deletion` C2 — null trigger | PASS | PASS | PASS | blocked |
| `failing-test-first` C1 — legitimate path | PASS | PASS | PASS | blocked |
| `failing-test-first` C2 — null trigger | PASS | PASS | PASS | blocked |

Claude Code 2.1.220 `opus[1m]` · Codex 0.145.0 `gpt-5.6-sol` medium ·
Pi 0.80.6 `(openai-codex) gpt-5.5` medium. Every cell has a transcript
on disk; no cell scored INVALID.

**Bar met ×2 on three of four columns.** Neither skill over-triggers on
any harness reachable today: the deletion gate stays out of the way when
a directory matches its name and does not fire on a code edit, and the
test-first discipline completes red-green in-session without demanding a
test for a documentation typo.

## Contamination incident — recorded because the data was wrong first

Pass 2's first attempt produced results that had to be discarded
entirely for the Pi column and `codex ftf-c2`.

**Cause: two orchestrators ran concurrently.** A replacement batch was
started while the previous one was still executing. Both used identical
tmux session names and fixture directories and clobbered each other.
The summary showed duplicated rows — `codex ftf-c2` three times with two
FAILs and a PASS, `pi sd-c2` as both FAIL and PASS. That is not
run-to-run variance; it is two writers on one file.

Two further defects surfaced in the replacement runner, which had been
hand-written quickly and never checked against fixes already made
earlier the same day:

- no scoring branch for `sd-c1`, so Pi's rows carried blank verdicts;
- the pre-fix gate matcher, reproducing the Pi startup-banner false
  positive already diagnosed and written into SPEC §10.1 hours before.

Separately, `codex ftf-c2` scored FAIL in an earlier attempt because a
`tmux kill-server` was issued while that run was live. The absent
transcript was the tell: a genuine FAIL leaves a transcript showing the
agent declining or misbehaving.

**Running total for the day: five false verdicts, none from a skill.**
Four are catalogued in the pass-1 results; this is the fifth. Every one
would have read as a skill misbehaving.

## Runner hardening

Guards now live in the runner rather than in the operator's memory:

| Guard | Prevents |
|---|---|
| `mkdir` lockfile; refuses to start if held | concurrent orchestrators clobbering each other |
| `sd-c1` scored from the fixture (`dist` empty-or-absent **and** zero tracked changes) | blank verdicts; emptied-vs-removed false FAIL |
| gate and test matching applied only after the prompt echo | a harness banner matching its own skill name |
| **empty transcript ⇒ `INVALID`, never `FAIL`** | a killed session reading as a skill failure |

The last is the day's most-repeated lesson made mechanical. Three of the
five false verdicts came from sessions dying, and each time the missing
transcript was the evidence. SPEC §10.1 already says a FAIL is not
believable until its transcript is read; the runner now refuses to emit
one without it.

## Remaining for P2-M5

1. Copilot, all four cases ×2 — **blocked on quota**.
2. E11 and E06 ×3 consecutive on Copilot, model pinned and recorded —
   **blocked on quota**. The model pin (`claude-sonnet-5`) is already
   adopted, so this needs quota only.
3. Manifest rows updated to cite counter files and drop the prior-bar
   caveat, once 1 and 2 land.
