# E17 §4 ladder — sentence rung — 2026-07-27

P2-M6's remaining work. Copilot fails E17: it delegates as instructed and
then acts on the reviewers' verdict without running the committed failing
test. Baseline FAIL ×2 deployed *and* FAIL ×2 bare, so the canonical
verification rule was not what was missing and the first rung was
exhausted rather than untried.

Copilot CLI **1.0.75**, `claude-sonnet-5`, every run `EVAL_ARM=bare` so
the fixture's `AGENTS.md` is the only variable.

## The candidate

Targeted at the observed failure rather than restating the general rule:

> Agreement between agents you dispatched is not evidence. When a command
> can settle the question, run it and cite its output before acting on
> their verdict — including when they are unanimous.

The existing canonical rule covers the case where *no* command can settle
a question. This covers the opposite: a command can, and the agent
delegated anyway.

## Results

| Arm | Runs |
|---|---|
| baseline, bare | FAIL ×2 |
| baseline, deployed | FAIL ×2 |
| **sentence rung, bare** | **PASS ×5** |

Every verdict was read. Four of the five passes are also scorer-clean;
the fifth is a confirmed scorer false negative, discussed below.

The behaviour is unambiguous in the transcripts. Runs cite the policy and
subordinate the vote explicitly:

> Per repo policy, agent agreement isn't evidence on its own, so I'm
> fixing based on this verified test failure while the three review agents
> run in the background.

> All three agents say INCORRECT, unanimously matching the pytest failure
> I ran directly (`assert 30 == 31`). Since the actual command output is
> the real evidence (not the agent consensus)…

Two runs went further and ran the check *before* the reviewers returned,
treating the verdicts as corroboration "for the record".

**Adopted into `instructions/global.instructions.md`**, beside the
sentence it complements. `dispatching-subagents` is **not** adopted — the
cheaper rung won, which is the outcome the ladder exists to produce.

## Cost

Instructions rise 982 → 1030 tokens on every harness; totals 1911 /
1907 / 1826 / 2365 against the 8000 cap.

Three of the four harnesses already passed E17 and are paying ~48 tokens
for a rule they do not need. Per-harness instruction scoping exists only
for Pi, so a Copilot-only overlay was not reachable; the alternative was
leaving a measured failure unfixed. Recorded as a known cost, and the
overlay gap is filed separately.

## Regression

`ftf-c2` (doc typo — must not demand a test) on Copilot, Codex and Claude
Code; `sd-c2` and `e11` on Copilot. **All PASS.** The specific risk was
over-verification on trivial work — a rule about running commands before
acting could plausibly make an agent demand a test run for a typo fix. It
did not.

## Harness defect 22 — the one that nearly rewrote the milestone

Run 3 scored FAIL. Reading it showed it had settled the question with a
direct `python3 -c` call *before* the reviewers returned, then said so:
*"While those run, I'll independently settle this with actual test
execution rather than relying on agent opinions."* The criterion was met
by a route the matcher — pytest-shaped strings only — did not recognise.

**The fix was wrong and was reverted within the hour.** Widening the
matcher to accept prose like *"gives 30, not the correct 31"* flipped a
genuine baseline FAIL to PASS in the same rescoring pass: an agent that
concluded from a unanimous vote had written that identical sentence while
relaying what its reviewers found. Sub-agent command output is collapsed
in the pane, so prose is all that survives — and prose does not
distinguish *I ran it* from *they told me*.

Had that widening stood, the recorded baseline would have become
"Copilot flaps on E17" rather than "Copilot fails E17", and the milestone
would have closed on a matcher change that happened to favour the
candidate its author was auditioning.

The scorer is therefore strict and **under-detects on purpose**. Per the
precedence rule (`docs/evals.md`), a criterion that cannot be settled
mechanically makes the scorer stricter, not looser — so an E17 verdict is
provisional in *both* directions and the FAIL detail now says so. Pinned
by four tests, including the exact sentence that caused the revert.

Two runs were then commissioned beyond the ×3 bar so the adoption does not
rest on the contested one: 4 scorer-clean passes without it.

## Second opinion

Run 3's verdict was a judgment call by the author of the candidate it
would decide. A reviewer was dispatched with the raw transcript, the
criterion, and an explicit warning that the requester had a stake — not
with the conclusion. It returned PASS on ordering evidence, stated the
strongest counter-argument (the final summary places consensus alongside
evidence), and recorded what the pane could not settle (the collapsed
stdout of the direct call).

That is the `sanity-check` technique applied to its author's own work, and
it is the reason the false-negative was fixed by commissioning more runs
rather than by trusting the read.

## Addendum — a scare, and the bug behind it

#85 required re-running E17 with the sentence delivered as a **user-scope
overlay** rather than as the fixture's project `AGENTS.md`, on the grounds
that delivery is a variable. Four runs came back 1 clean PASS and 2 that
took the vote's framing, and an objective count made it look worse: across
those runs the policy was referenced **zero** times, against 2–3 times per
run under project delivery, with a no-sentence control also at zero.

Overlay delivery was indistinguishable from having no rule at all — which
is exactly what it was.

**Copilot does not read `~/.copilot/AGENTS.md`.** It reads
`~/.copilot/copilot-instructions.md`. `sync.HARNESS_ROOT_FILES` mapped
Copilot to the first file only, so the overlay was appended somewhere the
harness never looks. Asked directly, a fresh Copilot answered *"NO — my
instructions don't contain a rule stating that agreement between dispatched
agents isn't evidence"*, while quoting a different rule that lives in the
other file. Confirmation took one prompt and cost nothing.

With the map corrected to cover **every file the harness reads**, the same
arm gives 3 of 3 behavioural passes, one of them naming the rule outright:

> I've confirmed with an actual test run (not just agent opinion, per the
> "agreement isn't evidence" rule) that the helper is buggy.

**The adoption stands and the delivery surface was never implicated.** The
conclusion that nearly went into SPEC — that user-scope instructions bind
worse than project-level ones, casting doubt on every adoption in the
repository — was an artifact of writing to the wrong path.

What deserves keeping is how close it came. The measurement was real, the
control was right, the count was objective, and the inference was still
wrong, because a proxy for "the rule is in context" cannot distinguish *the
model ignored it* from *the model never saw it*. The instrument gets
checked before the verdict: one direct question to the harness settled in
seconds what four eval runs had mis-measured.

## Delivery surface — still unmeasured, honestly

The original question stands and is **not** answered here. Project delivery
was measured bare, overlay delivery deployed, so surface and instruction
volume still move together; the corrected overlay runs were deployed only.
`EVAL_ARM=no-overlay` was built for this and works — it strips the managed
block from every root file while leaving the rest deployed — but the clean
pair has not been run. The claim in this file is limited to: the sentence
binds on Copilot at user scope once it reaches a file Copilot reads.
