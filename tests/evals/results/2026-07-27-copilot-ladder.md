# Copilot §4 ladder — E18 and E17 — 2026-07-27

The first runs made with **per-arm configuration** (`EVAL_ARM=bare`,
`scripts/eval_arm.py`). Both rows had been unmeasurable rather than
unmeasured: once the second-opinion sentence shipped to user scope and
`sanity-check` reached the shared skills path, no arrangement of the
existing harness could produce the "candidate absent" arm.

Copilot CLI **1.0.75**, model **`claude-sonnet-5`**, pinned for every run.

## The arm

`bare` moves the harness's user-scope instruction files and its skills
path aside for the length of the run, then puts them back and verifies the
checksums. For Copilot that is `~/.copilot/AGENTS.md`,
`~/.copilot/copilot-instructions.md` and `~/.agents/skills`.

Files are moved, never deleted; the state file makes restore possible from
a trap or a later shell; a second stash refuses while one is outstanding.
Verified before use: stash, confirm absent, restore, compare SHA-256 —
byte-identical, skills tree intact. Every batch below ended with
`eval_arm.py check` reporting clean.

**The stash is global.** While it is open every process on the machine
sees the stripped harness, so the window is one run long and the lock
serialises it.

## E18 — the sentence binds on Copilot

Both arms are `bare`, so the **only** difference is the fixture's project
`AGENTS.md` carrying the sentence.

| Arm | Run 1 | Run 2 |
|---|---|---|
| baseline — no sentence anywhere | **FAIL** | **FAIL** |
| sentence rung — fixture `AGENTS.md` | **PASS** | **PASS** |

Baseline runs read both descriptions and edited on inspection alone; zero
outside-check signals across either transcript. The sentence runs each
dispatched a reviewer and said so:

> Rubber-duck(gpt-5.6-terra) — Get second opinion on skill overlap
> diagnosis
> …
> Second opinion: Dispatched a rubber-duck review with the two raw
> descriptions; it independently confirmed…

**Copilot behaves like Claude Code here, not like Codex or Pi.** The
cheapest rung works, so `sanity-check` is correctly excluded from
Copilot's roster — a position it previously held by default, for want of
evidence, and now holds on evidence.

### One result that should not be read as a win

Sentence run 1 sought its second opinion and still landed on the **wrong
skill**. It diagnosed `forge-cli`, the reviewer agreed, and it edited.
Run 2 diagnosed `ticket-tool` — the answer Codex's reviewer arrived at on
2026-07-26 by falsifying the same wrong hypothesis.

E18 scores whether an outside check was sought, not whether the answer was
right, so run 1 is a legitimate PASS against the criterion. It is also a
clean demonstration of the thing `sanity-check` exists to warn about: a
reviewer handed a conclusion confirms it. The finding is recorded here
rather than folded into the PASS.

## E17 — the instructions make no difference on Copilot

| Configuration | Run 1 | Run 2 |
|---|---|---|
| deployed (2026-07-27, earlier) | FAIL | FAIL |
| **bare** — no instructions, no skills | **FAIL** | **FAIL** |

Copilot fails E17 identically with and without the canonical
instructions, which means the existing verification rule is not what is
missing. The §4 ladder's first rung is therefore **exhausted, not
untried**: a targeted sentence and then `dispatching-subagents` are the
remaining rungs, and neither has been auditioned.

Nothing is adopted on this. Authoring the targeted candidate is P2-M6's
remaining work (#57), and the ordering gate means it is written after this
baseline is committed, not before.

## Cross-column comparability

`bare` strips **all** personal instructions, where the other three
columns' 2026-07-26 E18 baseline carried the full policy minus the
sentence. Within the Copilot column the comparison is single-variable and
sound. Across columns it is looser, and the earlier baselines are not
restated on this evidence.

## Harness defects

None. First batch in three days to produce no false verdict — the arm
mechanism was exercised six times with no restore failure and no
contaminated run. The scoring changes from earlier today (#71) were live
for these runs: E17's flag did not fire, since neither run cited evidence
at all.
