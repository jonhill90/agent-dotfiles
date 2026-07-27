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
`<case>` is one of `e11`, `sd-c1`, `sd-c2`, `ftf-c1`, `ftf-c2`, `e17`.

Output goes to `$EVAL_OUTDIR` (default `$TMPDIR/agent-dotfiles-evals`):
`summary.txt` plus one `transcript-<tag>.txt` per run. **Keep the
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

**Not verified: the Copilot column.** Its quota was exhausted, so no case
has been run against `copilot` through this harness. The runner is
CLI-agnostic and Copilot was driven successfully by the scratchpad
predecessor, but that is inference, not evidence. Expect to debug prompt
delivery or completion detection on the first Copilot run, and treat an
early surprise as a harness problem before concluding anything about a
skill.

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
