---
name: sanity-check
description: Verify a claim before reporting it, using a check that would fail if the claim were false. Use before saying something is done, fixed, verified, passing, or working, and before believing a failure report — especially when the evidence is a tool's exit status, a log tail, or a single passing case.
---

# Sanity Check

A claim is verified by a check that **would fail if the claim were false**.
A check that passes either way is not evidence, however true its output.

Most wrong reports are not lies. They are a narrow observation stated as a
wide conclusion: one case passing described as "all cases pass", a pane with
output described as "still running", a green suite described as "the feature
works".

## Before reporting a claim

1. **Name the claim exactly.** "The harness works" is not a claim; "all six
   case paths score correctly through the committed runner" is.
2. **Name the check that would falsify it.** If you cannot describe an
   outcome that would prove the claim wrong, you have no test.
3. **Run that check, not a convenient neighbour.** Verifying one case does
   not verify six. Verifying on your branch does not verify on `main`.
4. **Quote the output.** A claim without pasted evidence is unverified, and
   should be reported as unverified rather than dropped.

## Traps that produce confident wrong answers

| Trap | Why it fools you | The check that actually falsifies |
|---|---|---|
| Exit status | Many tools exit 0 on a write that did not apply, or a query that silently filtered everything out | Read the state back afterwards |
| "It printed output" | Output persists after the process producing it has died | Check the process, not the pane |
| One passing case | Passes regardless of whether the others work | Run every path the claim covers |
| Passing on your branch | The consumer reads a different ref | Check the ref the consumer will use |
| Absence of an error | A crashed step and a skipped step both stay quiet | Assert the positive result |
| A matcher that found nothing | Zero hits can mean "clean" or "searched the wrong region" | Prove the matcher fires on a known positive |

## Before believing a failure

Failures deserve the same scrutiny as successes, and are more often wrong.

- **A failure with no artifact is not a finding.** If the run died before it
  produced evidence, the result is *invalid*, not *failed*.
- **Check the harness before blaming the subject.** A bad fixture, a matcher
  that hits a banner instead of a response, or two jobs sharing a directory
  will fail consistently — so repeating the run reproduces the wrong answer
  rather than catching it.
- **Read the artifact before acting on the verdict.** Narrowing a working
  component to satisfy a broken test is the expensive outcome.

## Reporting

State what was checked, what the check would have shown had the claim been
false, and the output. Where something is unverified, say so plainly and name
what would settle it — an unverified claim reported honestly costs a sentence;
reported as fact it costs the reader's trust in everything beside it.
