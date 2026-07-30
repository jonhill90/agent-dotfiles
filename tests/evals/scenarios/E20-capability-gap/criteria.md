PASS: looks for a maintained skill before improvising — runs a search
(`npx skills find` or an equivalent mechanism), proposes installing a
named collection, or actually installs one. An install landing on disk
(`.agents/skills/` or `skills-lock.json` in the fixture) is definitive.

FAIL: improvises the deployment from general knowledge — Bicep, `az`,
`azd`, Dockerfiles, pipelines — without ever looking for an existing
skill. Competence at Azure is not the behaviour under test; looking is.

Scoring note: disk evidence wins and is checked first — an install
cannot be faked by a startup banner or a checkout path, both of which
have produced false PASSes on this scenario's text matcher
(2026-07-29). The text matcher is deliberately conservative and
under-detects; read the transcript before believing a FAIL
(docs/evals.md, "Which artifact wins").
