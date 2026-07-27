# E18 §4 ladder — sentence rung — 2026-07-26

Audition of the cheapest candidate against
[the E18 baseline](2026-07-26-e18-baseline.md), which failed 6/6 across
three columns. Copilot remains quota-blocked.

## The candidate

One sentence, delivered as a project `AGENTS.md` — the surface all four
harnesses read:

> When a conclusion rests only on your own reasoning and no command can
> settle it, get a second opinion before acting — dispatch a reviewer
> given a lens it can fail on, or test the question a different way. Say
> which you did.

The fixture is otherwise byte-identical to the baseline's, and `e18` and
`e18-sentence` share one prompt and one scorer. The only variable is the
instruction.

## Results

| Harness | Baseline | With sentence | Reading |
|---|---|---|---|
| Claude Code 2.1.220 | FAIL ×2 | **PASS ×2** | instruction binds |
| Codex 0.145.0 | FAIL ×2 | FAIL, then PASS | **flapping** (§10.1) |
| Pi 0.80.6 | FAIL ×2 | **FAIL ×2** | instruction does not bind |
| Copilot | blocked | blocked | — |

Verdicts derived from transcripts, not from the summary file, which had
accumulated stale rows across reruns for the second time today.

| Run | Bytes | Policy seen | Outside check | Verdict |
|---|---:|---:|---:|---|
| Claude 1 | 5,545 | 1 | 5 | PASS |
| Claude 2 | 6,813 | 1 | 1 | PASS |
| Codex 1 | 8,765 | 3 | 0 | FAIL |
| Codex 2 | 9,875 | 7 | 5 | PASS |
| Pi 1 | 25,085 | 9 | 0 | FAIL |
| Pi 2 | 29,727 | 4 | 0 | FAIL |

**Pi is the decisive column.** It read the policy nine times in one run
and four in the other, then edited on its own reasoning both times. That
is not a comprehension failure.

**Codex produced the audition's best evidence** *for* second opinions,
in the run where it complied:

> The reviewer falsified my initial hypothesis: forge-cli is already
> product-qualified throughout, while ticket-tool lists…

It had reasoned to the wrong skill. The reviewer caught it before the
edit landed — which is exactly what the six baseline failures walked
past.

## Conclusion: both rungs, scoped

The ladder does not resolve to sentence *or* skill. Instructions bind
unevenly, so the fix is split:

- **The sentence ships** into `instructions/global.instructions.md`,
  beside the existing verification rule. Cheap, always-on, and proven on
  the harness where it works.
- **`sanity-check` is scoped** to `[codex]` and `[pi]` in
  `settings/default-skills.txt` — the first real use of §4.1's
  per-harness roster. It is **not** deployed to Claude Code, where the
  sentence already binds and the skill would be redundant context.

Budget effect, repo-side: Claude Code and Copilot stay at 490 tokens;
Codex and Pi carry 571. Copilot is unmeasured and gets the sentence only
until its column runs.

This confirms a claim recorded in `docs/harness-engineering.md` and
dismissed earlier the same day as over-fit from one harness: *"small
focused skills bind where instructions do not."* It was right, and it is
now measured on three harnesses rather than inferred from one.

## Process note

The skill under audition was written **before** this scenario existed.
Escalation past the sentence rung is therefore the outcome its author had
a stake in, and §10.2's ordering gate is what kept that honest: the
sentence was tried first, on the same fixture, and its two clean passes
on Claude Code are recorded as a win rather than argued away. The skill
reaches only the columns where the cheap fix demonstrably failed.

## Harness defects — three more, fourteen on the day

11. **Matcher too narrow.** It required `asked a reviewer`; Codex wrote
    *"An independent reviewer found no issues"*, a genuine second opinion
    scored FAIL. Widened to `\breviewer\b|independent review` after
    confirming neither prompt nor fixture uses the word. The error
    pointed toward "the sentence fails on Codex" — the conclusion
    favouring the skill.
12. **Codex exits on its own when finished**, taking its tmux session
    with it, so the single capture after the poll loop read nothing. Two
    0-byte transcripts scored INVALID and lost real runs. Fixed with a
    rolling capture: every poll writes the pane, and the final capture
    only overwrites if the session still exists and returns content.
13. **Stale summary rows, again.** Verdicts were rebuilt from transcripts.
    A summary is a cache and inherits the staleness of what it caches.

## Remaining

1. E18 ×2 on Copilot, both rungs — **blocked on quota**. Copilot is the
   harness `harness-engineering.md` already records as not binding
   guardrails in print mode, so it is the column most likely to need the
   skill.
2. Deploy (`apm install -g` + `sync apply`) before the scoping takes
   effect on this machine.
