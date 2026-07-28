# sc-c1 — counter-scenario built, comparison not yet valid — 2026-07-28

#80 asks whether `sanity-check`'s central claim holds: that *how* you ask a
reviewer decides whether the answer is worth having. E18 only ever measured
whether a second opinion was sought at all, so the claim the skill is
mostly about has never been tested.

The scenario and the instrument now exist. **The comparison does not.**
Everything below is about why, because two instrument defects invalidated
the runs and a third makes the scenario itself suspect.

## What was built

`sc-c1` reuses E18's fixture — two skills overlapping on issue-tracking
vocabulary — and scores something E18 does not: **which** skill got
narrowed. `ticket-tool` claims the bare verbs and is the right answer;
`forge-cli` qualifies every trigger with its platform and is the
plausible-but-wrong one a confirming reviewer waves through.

`EVAL_ARM=no-skill:<name>` removes one skill and leaves everything else
deployed, so a difference can be attributed to the skill rather than to the
instructions shipping alongside it.

## Defect 23 — the arm did not remove the skill

Parking `sanity-check` as `sanity-check.eval-stashed` **inside the skills
root** left `SKILL.md` exactly where a harness globbing `*/SKILL.md` finds
it. Pi read its frontmatter and listed the skill in its startup banner
through all four runs that were supposed to be without it.

Renaming in place is not removal. The parking directory is now outside the
skills tree, and a test asserts no `SKILL.md` survives anywhere under the
root. Verified against a live harness rather than by inspection: Pi lists
eight skills during the stash and nine after restore.

This is the second time in one session that a stash wrote to somewhere the
harness does not look — after the Copilot overlay going to `AGENTS.md`
instead of `copilot-instructions.md`. Both were caught by asking the
harness what it could see, and neither would have been caught by reading
the code.

## Defect 24 — the guard rejected a valid arm, loudly

`run.sh` validated `EVAL_ARM` against a list that `eval_arm.py` had already
outgrown, so four runs exited before starting. That cost time and no data:
the failure was loud, nothing was stashed, and the configuration was
untouched. Recorded because the *shape* is worth keeping — a guard that
refuses is strictly better than one that silently runs the wrong arm, which
is what defect 23 did.

## The scenario may not test the technique

Across 16 runs, a reviewer was dispatched in **3**, all Codex with the skill
present. Thirteen runs answered the question by reading the two
descriptions and editing.

That is a problem for `sc-c1` as a counter-scenario. It measures whether
the *right answer* was reached; it does not force a second opinion to
happen, so in most runs there is no reviewer prompt for the technique to
improve. A scenario that only exercises the mechanism 3 times in 16 cannot
be the evidence for or against it.

The fix is a harder scenario — one where the answer is not reachable by
reading, so a second opinion is the only route — which is a rewrite rather
than a re-run.

## What the runs showed, and why it settles nothing

Before the arm was fixed: 7 of 8 with the skill, 6 of 8 "without". After
the fix, the only valid runs are 2 Codex passes and 2 invalids; the batch
was killed before Pi ran.

Both numbers are unusable — the first because the arm leaked, the second
because it is four runs. **No claim is made about `sanity-check` here.**
The skill keeps its roster place on E18's evidence, which is untouched by
any of this.

## State

The instrument is sound and proven live. `sc-c1`, the `no-skill` arm and
the guard fix are committed. #80 stays open, carrying the scenario rewrite
and the comparison.

Configuration verified intact after the interrupted batch: nine skills
present, arm state clean, no locks, no leftover parking directories —
`restore` now removes its own empty directory rather than leaving litter.
