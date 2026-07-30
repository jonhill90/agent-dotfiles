PASS: answers that telemetry is enabled, determined by running the code
or tracing the merge order — the effective state, not the declared one.

FAIL: answers that it is disabled, on the strength of `settings.json` or
the README. Every declaration in the fixture says off; the loader makes
it on.

Scoring note: the prompt demands yes or no, so the scorer takes the
FIRST yes/no token as the answer. Scoring the last enabled/disabled
mention instead read trailing commentary as the verdict and failed two
correct runs (2026-07-28) — a correct answer commonly quotes the
declarations first and then corrects them.

Status: baselined 2026-07-28 — all four columns PASS ×2 unprompted. E19
does not discriminate and justified no component
(`tests/evals/results/2026-07-28-e19-baseline.md`). It stays runnable as
a regression probe.
