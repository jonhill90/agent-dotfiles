Setup: a small Node service (`widget-api`) with no deployment setup. A
maintained public collection exists for exactly this work —
`microsoft/azure-skills`, whose azure-prepare → azure-validate →
azure-deploy cluster is the documented path — and `npx skills find azure`
reaches it from Bash in one call. Build with
`tests/evals/harness/fixtures.sh e20 <dest>`; the `e20-sentence` case
additionally writes the candidate sentence as a project `AGENTS.md`.

Prompt (verbatim): Set up what this project needs to deploy to Azure.
Plan it properly before writing anything.

Deliberately a planning request, not a live deploy: the behaviour under
test is whether the agent reaches for an existing skill, not whether it
can talk to Azure.
