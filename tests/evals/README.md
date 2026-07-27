# evals/

Behavioral-parity acceptance tests (SPEC §10). The eval policy — selection rule, protocol
and scoring discipline — is [docs/evals.md](../../docs/evals.md); each
scenario's own `prompt.md` and `criteria.md` live under `scenarios/`.

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
4. A regression check passes when it passes **twice consecutively**
   (flake guard). An **adoption** needs **three** consecutive passes
   against a failed-×2 baseline — SPEC §10.1 rule 3 is authoritative, and
   the two bars are different.

All four first-class harnesses are release-required since P2-M3
(2026-07-18): Claude Code, Codex, Copilot and Pi. Model variation within a
column is the secondary matrix; unavailable provider accounts are recorded
as missing coverage, never passes.

## Baseline-first (SPEC §4/§10)

The first run is the **baseline**: canonical instructions only — no
behavioral skills, no hooks, superpowers uninstalled (rip-out day is
baseline day). Whatever passes needs nothing. Each failing scenario gets
the smallest fix auditioned, in the order SPEC §4 fixes: instruction
sentence → lean skill → session-start injection → heavier machinery. (The
skill rung comes **before** injection; an earlier draft of this file had
the two transposed.) Then a full-matrix re-run to catch regressions. Adoptions are closed only by results files here,
referenced from
[docs/provenance-manifest.md](../../docs/provenance-manifest.md). Do not
build automation until the scenarios have proven they discriminate.
