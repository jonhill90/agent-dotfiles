# E20 sentence rung — 2026-07-29

Audition of the cheapest rung against
[the E20 baseline](2026-07-29-e20-baseline.md), which failed on all four
columns. **Adopted on Claude Code's evidence; Pi does not bind; Codex does
not bind — re-measured ×3 after defect 29; it was never quota-blocked.**

## The candidate

> When a task needs a capability you do not have, look for a published skill
> before improvising: `npx skills find <topic>` searches maintained
> collections, and `npx skills add <owner/repo> --skill <name>` installs one
> into the current project only. Propose it and let the user decide — an
> installed skill runs with your permissions.

Three things it has to do, and the third is not optional: name the failure
(improvising without looking), name the mechanism (the agent cannot use a
tool it does not know exists), and gate the install (it fetches third-party
code that runs with the agent's permissions).

Delivered as a project `AGENTS.md`, which all four harnesses read.

## Results

| Arm | Claude Code | Codex | Pi | Copilot |
|---|---|---|---|---|
| baseline | FAIL ×2 | FAIL ×2 | FAIL ×2 | FAIL ×2 |
| **sentence** | **PASS ×3** | **FAIL ×3** | FAIL, PASS, FAIL | not run |

*Codex re-measured 2026-07-29 after its delivery problem was fixed — see
defect 29. It was never quota-blocked; the earlier reading was wrong.*

**Claude Code binds, ×3, and the transcripts show real behaviour rather than
policy recitation.** It ran the search, found the actual collection, picked
the right cluster, and — unprompted — laid out the trade-off:

> `npx skills find azure` returns microsoft/azure-skills (azure-prepare,
> azure-deploy, azure-validate, azure-diagnostics)…

> I write the Dockerfile, Bicep, and deploy docs myself using Microsoft Learn
> docs as the source of truth. **No third-party code gains my permissions.**
> Slightly more work, fully auditable.

That second quote is the approval gate working. It proposed rather than
installed, and it surfaced the security trade-off as the reason.

**Pi does not bind** — 1 of 3, and the two failures had the prompt delivered
and 27 KB of transcript, so they are real. Same column, same shape as E18:
Pi reads the policy and proceeds on its own reasoning.

**Codex does not bind either — three clean failures, delivery confirmed.**
The earlier reading of "quota-blocked" was wrong: its banner line *"You have
2 usage limit resets available"* is informational, and the owner confirmed
the CLI was working. The prompt genuinely was not arriving, for a different
reason (defect 29).

Re-measured, Codex improvises thoroughly. One run worked for 2m 29s and
produced a careful plan with Microsoft Learn citations, an OIDC
recommendation over publish-profile credentials, and an environment
inventory noting `azd` was not installed — and never once looked for an
existing skill. Like Claude Code's baseline, this is not carelessness. It is
an agent doing good work in a direction nobody told it had a shortcut.

## Adopted

Into `instructions/global.instructions.md`, on the Implement bullet.
Instructions rise 982 → 1068 tokens on every harness; totals 1974 / 1974 /
2049 / 2432.

Three of four columns are therefore paying for a rule measured on one. That
is the same trade E18's sentence took, and the reasoning is the same: a
sentence is cheap, reversible in one commit, and the alternative is leaving a
failure measured on all four columns unaddressed. The per-harness overlay
mechanism exists if this needs scoping later.

**No skill is adopted.** Pi's failure is recorded, not fixed. The remaining
rungs — a targeted sentence for Pi, then a skill — are untried, and the
E18 precedent says the targeted form is worth trying before the skill.

## Harness defects 27 and 28 — both mine, both in the scorer

**27. A matcher that matched the harness's own banner.** The pattern included
`available skill`; Codex's startup banner contains *"available skills"*. Two
quota-blocked runs — transcripts of pure banner, prompt never delivered —
scored **PASS** off it. Removed.

**28. A run whose prompt never landed was scoreable at all.** This is the
root cause of 27 and the more useful fix. `response_region` falls back to
the whole transcript when the prompt anchor is absent (lesson 5, added for a
different reason), which makes startup text scoreable. `score()` now returns
`INVALID` when the case's prompt fragment is missing from the pane, and
`PROMPT_ANCHORS` records the fragment per case.

That guard turned four Codex FAILs and two false PASSes into six INVALIDs,
which is what they always were. Had it existed this morning, E20's baseline
would have read 7 FAIL / 1 INVALID from the start instead of needing a
rescore.

Third and fourth over-broad matcher in three days. Both pointed toward the
conclusion their author wanted.

## Harness defect 29 — the harness skipped the check its own skill requires

Codex 0.146.0 added a startup dialog — *"1. Yes, continue / 2. No, quit /
Press enter to continue"* — and dismissing it leaves the TUI still
initialising. The harness typed the prompt on a fixed timer, so it was
swallowed, and **six runs were scored as behaviour when nothing had been
asked.** Two of those scored PASS off banner text.

`skills/tmux/SKILL.md` says it plainly: *"Never skip send verification.
'I sent it' is not the same as 'the pane received it.'"* The harness had
been doing exactly that since it was written.

Now it clears any standing dialog, types the prompt, confirms the text is in
the pane, and retries up to five times — and records the confirmation, so the
scorer does not have to re-infer it. That last part matters: a 31 KB Codex
run scrolled its own prompt echo out of the captured window and was lost as
INVALID before delivery was recorded at send time.

The guard's failure mode is now losing nothing and refusing to score runs
that never happened, which is the right direction on both counts.
