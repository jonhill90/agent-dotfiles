---
name: dispatching-subagents
description: Decide whether to delegate work to subagents, set each one's isolation boundary, and verify their output with external evidence. Use when considering fanning work out to parallel agents, orchestrating multiple agents, or reviewing whether a multi-agent result can be trusted.
---

# Dispatching Subagents

Delegation is an orchestrator-workers decision, not a reflex. It costs
roughly an order of magnitude more tokens than doing the work inline and
it removes your ability to see what happened. Earn it.

Portability: subagent spawning is not available on every harness. This
skill is a decision procedure. Where no dispatch mechanism exists,
execute the same plan sequentially in this context — the boundaries and
verification rules are unchanged.

## Decide first

Delegate only when at least one is true:

- The work is **breadth-first**: several independent paths must be
  explored and their results do not depend on each other.
- The material **exceeds one context window** and splitting it loses
  nothing.
- A **verifier must be independent** of the maker to be worth anything.

Do not delegate when: the subtasks are sequential and each needs the
previous one's output; the task is small enough to read directly; you
cannot state the success criterion for a worker in one paragraph; or you
would be unable to check the result yourself.

If none of the three conditions holds, do the work inline and say so.

## Set the isolation boundary

Before dispatching, state for each worker what it knows about the
others. Default to **nothing**: a self-contained task description, the
required output format, and a fresh context. Shared state between
workers is a cost — justify each piece of it.

Write the boundary down in the plan. "Worker A does not see B's
findings" is a design decision, not an omission.

## Tier the models

Put reasoning-heavy planning, decomposition, and final review on the
strongest model. Put well-specified execution on cheaper ones. A worker
whose task cannot be specified tightly enough for a cheaper model is a
sign the decomposition is not finished.

## Verify with external evidence

Agreement between workers is not verification. Several agents on the
same model reading the same flawed context will agree with each other
and be wrong together.

A result is verified only by evidence from outside the agents:

- test or build output, pasted;
- a command's actual return value;
- a file or record that can be read back;
- human review.

The maker never grades its own work. If a verifier is itself an agent,
it must be given the artifact and the criterion, not the maker's
reasoning.

## Report honestly

State how many workers ran, what each was asked, what came back, and
which claims are backed by external evidence versus by an agent's
assertion. Unverified worker output is reported as unverified.

## Stop conditions

Stop and consolidate when: workers return contradictory results and no
external evidence settles it; a worker fails twice on the same subtask;
or the dispatch has cost more than doing the work inline would have.
Contradiction is a finding to report, not noise to re-roll away.
