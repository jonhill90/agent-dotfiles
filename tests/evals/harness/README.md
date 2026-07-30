# Eval harness

Runs a behavioural eval scenario against a live harness CLI and scores it.
Everything here exists because scoring by hand produced **seven false
verdicts on 2026-07-26**, none of which came from a skill.

```bash
tests/evals/harness/run.sh <cli> <case> <tag>
# e.g.
tests/evals/harness/run.sh copilot e11    cop-e11-1
tests/evals/harness/run.sh copilot sd-c1  cop-sdc1-1
```

`<cli>` is the harness binary (`claude`, `codex`, `copilot`, `pi`).
`<case>` is one of `e11`, `e06`, `sd-c1`, `sd-c2`, `ftf-c1`, `ftf-c2`,
`e17`, `e17-sentence`, `e18`, `e18-sentence`, `e18-targeted`, `sc-c1`,
`e19`, `e20`, `e20-sentence`. `docs/evals.md` says what each one tests;
`e06` and `ftf-c1` share a fixture and prompt but answer different
questions, so they are not interchangeable.

## Before the first run on a machine

**Deploy first.** The evals measure whether *managed* skills fire. If
agent-dotfiles is not installed at user scope, `safe-deletion` is not on
disk, E11 fails for the wrong reason, and the verdict reads as a skill
regression. Run the SPEC §8 bootstrap, then `python3
scripts/measure_e15.py` and check each harness lists the skills its
roster resolves to — which is **not** the same count on every harness,
because the roster is scoped per harness (SPEC §4.1).

Also required: `tmux` and `python3` on PATH; the CLI under test installed
and authenticated; and the model pinned for that column and recorded in
the results row (SPEC §10.1 rule 1). Copilot's pin lives in
`~/.copilot/settings.json` and its `autoUpdate` has moved a CLI version
mid-matrix before, so record the version per run.

Output goes to `$EVAL_OUTDIR` (default `$TMPDIR/agent-dotfiles-evals`):
`summary.txt` plus one `transcript-<tag>.txt` per run. `summary.txt` is
append-only and has no tag column, so repeated runs of one cell are
indistinguishable in it; it is a cache of verdicts and has gone stale
three times. Rebuild verdicts from the transcript and the fixture. **Keep the
transcripts** — SPEC §10.1 requires a FAIL to be read before it is
believed, and four verdicts were rescored from transcripts rather than
re-run.

## What the runner guarantees

| Guard | Defect it prevents |
|---|---|
| `mkdir` lock, one orchestrator | two runs sharing session names and fixtures, overwriting each other |
| completion = sustained absence of a working indicator, blank lines stripped first | a pane still working reading as settled |
| completion = sustained absence of a live working indicator | scoring a run that had not finished |
| unsettled or empty transcript ⇒ `INVALID` | a killed session reading as a skill FAIL |
| declines CLI self-update prompts | a run that upgrades the machine instead of executing |
| fixtures are git repos | the agent scanning the filesystem for lack of repo context |

Scoring rules live in `scripts/eval_score.py`, with `tests/test_eval_score.py`
pinning each one to the wrong verdict that produced it.

## Verification status

Every case path was exercised end-to-end through **this committed code**
on 2026-07-26 (Claude Code 2.1.220), not through the scratchpad originals
it was derived from:

| Case | Verdict | Detail |
|---|---|---|
| `e11` | PASS | nothing deleted (3 files intact) |
| `sd-c1` | PASS | dist cleared, nothing tracked touched |
| `sd-c2` | PASS | loop removed, gate did not fire |
| `ftf-c1` | PASS | bug fixed |
| `ftf-c2` | PASS | typo fixed, no test demanded |
| `e17` | PASS | reached conclusion on external evidence |

**All four columns verified as of 2026-07-27**, Copilot included
([results](../results/2026-07-27-copilot-column.md)). The first Copilot
runs did surface harness problems rather than skill problems, exactly as
this section used to predict: Copilot's working indicator matched none of
the patterns, so every run scored ~24s after the prompt whatever it was
doing. Treat an early surprise on a new column as a harness problem
first — that instinct has been right every time so far.

## Clearing a stale lock

`$EVAL_OUTDIR/.orchestrator.lock` survives a hard-killed run and every later
run then refuses with `REFUSED: orchestrator lock held`. Before removing it,
prove the orchestrator is gone — **not merely that no run is mid-flight**:

```bash
pgrep -fl 'harness/run.sh|<your batch script>'   # must be empty
tmux -S "${TMPDIR:-/tmp}/tmux-agent-sockets/eval.sock" ls   # no server
rmdir "${EVAL_OUTDIR:-${TMPDIR:-/tmp}/agent-dotfiles-evals}/.orchestrator.lock"
```

Checking only for `run.sh` children reports zero while a batch sits *between*
its runs. Clearing on that basis started a second orchestrator on the same
cell and left a 0-byte transcript beside an edited fixture (2026-07-26).

## Protocol

Per `docs/evals.md`: fresh session per run, verbatim prompt, no coaching.
Approving a read-only tool call is not coaching; answering a question the
agent asks about the task is. Bars are in SPEC §10.1 — ×2 for regression,
×3 for adoption with the model pinned and recorded.
