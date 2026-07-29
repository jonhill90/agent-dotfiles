# E18 targeted rung on Pi — 2026-07-29

The rung nobody tried. E18's ladder went generic sentence → skill, and the
generic sentence failed on Pi ×2. E17 later showed a sentence **naming the
specific wrong move** can beat a skill outright, which is why
`dispatching-subagents` was rejected. That form was never tried for E18.

Pi 0.80.6 `(openai-codex) gpt-5.5` medium, `EVAL_ARM=bare` ×3.

## The candidate

> Re-reading the same material is not a second opinion. Before applying an
> edit whose correctness rests only on your own reading, hand the raw
> material to a reviewer without your conclusion, or probe the question a
> second way — then say which you did and what it changed.

Targeted at what Pi actually did: it read the policy **nine times in one
run** and edited anyway. Not a comprehension failure, so restating the
general rule louder was never going to help.

## Results — scorer and reading disagree

| Run | Scorer | Transcript |
|---|---|---|
| 1 | FAIL | *"Second probe used: searched the repo for issue/ticket/Forge references with grep; it confirmed TRACKER.md says work is tracked in Forge Issues."* → narrowed `ticket-tool` (**correct**) |
| 2 | PASS | probes=2 |
| 3 | FAIL | *"I also probed this a second way by extracting trigger terms from both descriptions"* → narrowed `forge-cli` (**wrong**) |

Read-derived: **3 of 3 sought a check outside their own reading**, against a
generic-sentence baseline of **0 of 2** on the same column.

The scorer requires `probes >= 2` and runs 1 and 3 describe probing once.

**The matcher was deliberately not changed.** Loosening it would produce
3/3 clean and would be the same error as 2026-07-27, when widening E17's
evidence matcher to rescue one run flipped a genuine baseline FAIL to PASS
and nearly closed a milestone on a measurement rigged toward its author's
candidate. Under the precedence rule (`docs/evals.md`), the scorer may
under-detect; the transcript decides, and the disagreement is recorded
rather than engineered away.

## What this does and does not establish

**Does:** the ladder was not exhausted. A targeted sentence moves Pi from
never seeking an outside check to seeking one in all three runs. The rung
below the skill works better than the rung that was tried.

**Does not:** justify adopting it. Three runs with a disagreeing scorer is
not the ×3-with-the-model-pinned bar, and one run sought its check and
still reached the **wrong** answer — narrowing `forge-cli`, the
already-qualified skill. That is the same shape as Copilot's ladder run: an
outside check was sought and the answer was still wrong.

Which is precisely the distinction E18 cannot measure and `sanity-check`
claims to address. Nothing here settles that claim either.

## Status

`sanity-check` stays public opt-in. This result strengthens that rather
than weakening it: the cheaper rung looks viable on the one column with a
measured failure, so the skill's remaining justification is thinner, not
thicker.

Adoption of the targeted sentence needs ×3 clean at the bar, on a scorer
that agrees with the transcripts — which means fixing the probe threshold
on evidence rather than to rescue a result, and re-running. Not done here,
deliberately, at the end of a long session.
