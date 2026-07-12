# evals/

Behavioral-parity acceptance tests (SPEC §10). Scenario definitions
come from [docs/research/eval-scenarios.md](../docs/research/eval-scenarios.md)
(E1–E16); this directory holds their runnable form and results.

## Layout

- `scenarios/E<nn>-<slug>/` — one directory per scenario: `prompt.md`
  (verbatim prompt + setup steps), `criteria.md` (observable PASS/FAIL
  criteria), plus fixture files where the scenario needs a rigged repo
  (E2, E6, E7, E9).
- `results/<date>-<harness>-<model>.md` — one committed matrix per run.

## Protocol (v1: manual by design)

1. Fresh session in the target harness×model pair.
2. Run the scenario prompt verbatim; do not coach.
3. Score PASS/FAIL against `criteria.md` — observable transcript
   evidence only.
4. A pair passes a loop stage when all its scenarios pass **twice
   consecutively** (flake guard).

v1 pairs: Claude Code×Fable (baseline), Claude Code×Sonnet, Pi×default,
Pi×Sonnet-class.

Distillation-matrix conflicts (grilling, TDD, handoff) are closed only
by results files here, referenced from
[docs/provenance-manifest.md](../docs/provenance-manifest.md). Do not
build automation until the scenarios have proven they discriminate.
