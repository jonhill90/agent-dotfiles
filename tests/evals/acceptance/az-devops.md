# Acceptance: az-devops

Tasks the skill must let the agent complete (SPEC §10 tool-skill track).

1. List active PRs in a given repo and report reviewers + vote status.
2. Create a work item, link it to a PR, and update its state.
3. Queue a pipeline run for a named definition and report the result of
   the triggered build.
4. Fetch the log of a failing pipeline stage and identify the failing
   step.
5. Set the default organization/project so subsequent commands need no
   flags.

PASS: all five without invented `az devops`/`az repos`/`az pipelines`
syntax; extension/auth preconditions surfaced, not assumed.

**Not exercisable in this repository.** These tasks need a live Azure
DevOps organization, and the only one configured here is employer-scoped —
its name is a `.privacy-denylist` term and cannot enter tracked markdown.
Run these checks against a repo and organization that permit it, and cite
the run without naming the organization. The skill is public opt-in and
not in the default roster (`settings/default-skills.txt`).
