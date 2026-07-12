# evals/

Behavioral-parity acceptance tests (SPEC §10). Scenario definitions
come from [docs/research/eval-scenarios.md](../docs/research/eval-scenarios.md)
(E1–E16); this directory holds their runnable form and results.

## Layout

- `scenarios/E<nn>-<slug>/` — one directory per scenario: `prompt.md`
  (verbatim prompt + setup steps), `criteria.md` (observable PASS/FAIL
  criteria), plus fixture files where the scenario needs a rigged repo
  (E2, E6, E7, E9).
- `acceptance/<skill>.md` — per-tool-skill acceptance checks (3–5
  concrete tasks). Community candidates displace a personal skill only
  by passing the same checks with equal-or-fewer tokens loaded.
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

## Baseline-first (SPEC §4/§10)

The first run is the **baseline**: canonical instructions only — no
behavioral skills, no hooks, superpowers uninstalled (rip-out day is
baseline day). Whatever passes needs nothing. Each failing scenario gets
the smallest fix auditioned (instruction line → ~100–200-token
injection → lean skill), re-run twice, then a full-matrix re-run to
catch regressions. Adoptions are closed only by results files here,
referenced from
[docs/provenance-manifest.md](../docs/provenance-manifest.md). Do not
build automation until the scenarios have proven they discriminate.
