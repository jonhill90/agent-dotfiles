# Behavioral Evals

The eval suite defines what “behaves like Jon's agent” means. It tests
observable behavior rather than implementation details: orient, plan,
implement, verify, complete, remember, trigger skills, stay within the static
budget, and bootstrap a fresh environment. Its original design is preserved
in commit `106e69c`; runnable scenarios and results live under `tests/evals/`.

## Selection rule

The baseline is canonical instructions plus the harness overlay and tool
skills. Behavioral frameworks, hooks, and process skills are not installed by
default. When a scenario fails, audition the smallest targeted fix in this
order:

1. a canonical instruction or harness-overlay sentence;
2. a small, focused skill;
3. a short session-start injection; and
4. heavier machinery only after lighter options have failed.

Record an adoption in `docs/provenance-manifest.md` with its deciding results
file. One component owns each loop stage; overlapping components do not remain
installed “just in case.” Tool skills use the concrete checks in
`tests/evals/acceptance/` instead of loop scenarios.

## Running one

`tests/evals/harness/run.sh <cli> <case> <tag>` drives one interactive run
end to end: it builds a fresh git-backed fixture, launches the CLI under
tmux, sends the prompt uncoached, waits for the run to settle, keeps the
transcript, and scores it.

```bash
tests/evals/harness/run.sh copilot e11 cop-e11-1
```

| Case | Scenario |
|---|---|
| `e11` | `safe-deletion` originating scenario — a misleadingly named directory |
| `e06` | `failing-test-first` originating scenario, at the red-green bar |
| `sd-c1` / `sd-c2` | `safe-deletion` counter-scenarios: legitimate path, null trigger |
| `ftf-c1` / `ftf-c2` | `failing-test-first` counter-scenarios: legitimate path, null trigger |
| `e17` | delegation: three reviewers and a majority vote, with a test that settles it |
| `e18` / `e18-sentence` | second opinion, baseline and sentence rung |

`ftf-c1` checks only that the bug is fixed; `e06` checks the reproduction
survives in the suite. They share a fixture and a prompt and answer
different questions — do not substitute one for the other.

It is **single-instance by design**: two orchestrators share tmux session
names and fixture directories and silently overwrite each other's results.
Before clearing the lock, check for the orchestrator script itself, not just
its children — a batch between runs has no live child.

## Running the absent arm

The §4 ladder compares a run with a candidate present against an
otherwise identical run with it absent. Once a candidate ships, the absent
arm stops being reachable: the second-opinion sentence is in every
harness's user-scope instructions and `sanity-check` is on the shared
skills path, so a normal run carries both.

`EVAL_ARM=bare` produces it, by moving that harness's instruction files
and skills path aside for the length of one run:

```bash
EVAL_ARM=bare tests/evals/harness/run.sh copilot e18 cop-e18-base-1
```

The mechanism is deliberately blunt — it uses no harness's
instruction-disable key. Those differ per harness, one of them was
inferred from a CLI bundle rather than documented, and a lever that
silently stopped working would produce a contaminated arm that still
looked clean. **A missing file cannot silently fail to be missing.**

The cost is that the stash is **global**: while it is open, every process
on the machine sees the stripped harness. Hence one run per stash, restore
on the exit trap including interrupts, checksums verified on the way back,
files renamed and never deleted, and a refusal to nest. If a run dies
badly, `python3 scripts/eval_arm.py check <state>` says so and
`restore <state>` finishes the job.

Record the arm in the results row. `bare` removes *all* personal
instructions, not only the candidate, so two `bare` arms compare cleanly
with each other but not with a run made against a deployed configuration.

## Which artifact wins

A scenario has two descriptions of what passing means: its `criteria.md`
and its branch in `scripts/eval_score.py`. They are not equals.

**`criteria.md` is authoritative.** The scorer is a mechanization of it and
is allowed to be *stricter*, never looser: it must not PASS a run the
criteria would fail. Where a criterion cannot be settled mechanically —
"reached the conclusion on the evidence *rather than* on agreement" is a
statement about reasoning, not a string — the scorer does one of three
things, in order of preference: check a stricter proxy, flag the verdict
for reading, or record the gap in the branch's comment. It does not
quietly score the weaker bar.

E17 is the worked example. Its criteria require external evidence *and*
that the conclusion rest on it rather than on the vote. The scorer can
check that the failing assertion was observed; it cannot check what the
run reasoned from. So a run that cites the evidence but still leans on
vote language passes **with a flag** telling you to read the transcript
before closing the row.

## Scoring is code, and every rule is a scar

`scripts/eval_score.py` holds the criteria. Where a rule exists because a
verdict was wrong, the comment names that verdict — about half the branches
carry such a scar, and the rest encode the criterion plainly.

**Every false verdict so far came from the harness; none came from a
skill.** They cluster in three places: reading a pane (an indicator that
did not match the harness's spelling, an answered dialog still matching
from scrollback, a footer pushing the live line out of the window), a
matcher too narrow or too broad for what an agent actually wrote, and the
environment (two orchestrators on one cell, a package manager breaking a
runtime mid-session). Several pointed at a *worse* verdict than the truth
and would have narrowed a working skill had they been believed.

Each results file itemizes the defects that batch produced. Do not trust
the running totals in their headers — they were renumbered across files
and do not reconcile; the per-file lists are the record.

Two habits follow, and they are not optional:

- **Rebuild verdicts from transcripts and fixture state, never from
  `summary.txt`.** A summary is a cache and inherits the staleness of what
  it caches; it has gone stale three times.
- **A verdict whose evidence is missing is not a verdict.** An empty
  transcript and a `FAIL` cannot both be true of one run.

## Protocol

- Start a fresh session in the named harness/model pair and run the scenario
  prompt without coaching.
- Score only transcript and filesystem evidence against the scenario's
  criteria.
- Interactive execution is authoritative for tasks whose behavior is altered
  by print/non-interactive mode.
- A required cell passes after two consecutive successful runs. Record skipped
  or blocked cells explicitly; absence of a result is not a pass.
- Store durable matrices in `tests/evals/results/`. Raw transcripts may remain local
  when they contain credentials, private paths, or unnecessary bulk.

The baseline run found one authoritative behavioral failure: Pi deleted
contradictory content from a misleadingly named directory. A small Pi overlay
deletion gate fixed it twice consecutively. E12 also justified explicit memory
write and read-before-recall gates. No behavioral framework or bootstrap hook
was justified; E14 passed through native skill-description matching.

## Static-context acceptance (E15)

Estimate tokens as UTF-8 bytes divided by four. Repository validation reserves
the full memory-index allowance and enforces these component limits:

| Component | Limit |
|---|---:|
| Canonical instructions | 2,000 tokens |
| Largest harness overlay | 1,500 tokens |
| Installed skill descriptions | 2,000 tokens |
| Memory index reserve | 1,500 tokens |
| Thickest total | 8,000 tokens |

Live E15 must include instructions, the applicable overlay, aggregate deployed
skill descriptions, **enabled plugin skills on Claude Code**, and the actual
memory index. Report component and total measurements, not only
root-instruction file size. Run `python3 scripts/measure_e15.py`, which reads
the deployed tree and encodes the plugin counting rules (SPEC §6); measuring
by hand under-counts plugins, which is how the 2026-07-26 matrix reported
Claude Code 87 tokens light.

A skill on disk is not necessarily in the model's context. Claude Code and
Copilot are both sent the union and then told which entries to drop
(`skillOverrides`, `disabledSkills`), so the script subtracts what each
harness has been told not to load. Counting the directory instead reported
both harnesses 81 tokens heavy on 2026-07-27.

## New-machine acceptance (E16)

E16 is a clean, isolated bootstrap completed in at most 15 minutes, followed
by E14, E12, and E15. The platform and skipped optional surfaces must be named.
Linux is an accepted clean-room platform for the shared v1 core; it does not
prove macOS-only Obsidian application integration. Bootstrap or projection
changes require another clean mechanical run. Behavioral evidence may carry
forward only when its instructions and relevant skills are byte-unchanged,
and the combined-evidence boundary must be explicit in the results.
