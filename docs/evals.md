# Behavioral Evals

The eval suite defines what “behaves like Jon's agent” means. It tests
observable behavior rather than implementation details: orient, plan,
implement, verify, complete, remember, trigger skills, stay within the static
budget, and bootstrap a fresh environment. Its original design is preserved
in commit `106e69c`; runnable scenarios and results live under `evals/`.

## Selection rule

The baseline is canonical instructions plus the harness overlay and tool
skills. Behavioral frameworks, hooks, and process skills are not installed by
default. When a scenario fails, audition the smallest targeted fix in this
order:

1. a canonical instruction or harness-overlay sentence;
2. a small, focused skill;
3. a short session-start injection; and
4. heavier machinery only after lighter options have failed.

Record an adoption in `docs/provenance-manifest.md` with its deciding results
file. One component owns each loop stage; overlapping components do not remain
installed “just in case.” Tool skills use the concrete checks in
`evals/acceptance/` instead of loop scenarios.

## Protocol

- Start a fresh session in the named harness/model pair and run the scenario
  prompt without coaching.
- Score only transcript and filesystem evidence against the scenario's
  criteria.
- Interactive execution is authoritative for tasks whose behavior is altered
  by print/non-interactive mode.
- A required cell passes after two consecutive successful runs. Record skipped
  or blocked cells explicitly; absence of a result is not a pass.
- Store durable matrices in `evals/results/`. Raw transcripts may remain local
  when they contain credentials, private paths, or unnecessary bulk.

The baseline run found one authoritative behavioral failure: Pi deleted
contradictory content from a misleadingly named directory. A small Pi overlay
deletion gate fixed it twice consecutively. E12 also justified explicit memory
write and read-before-recall gates. No behavioral framework or bootstrap hook
was justified; E14 passed through native skill-description matching.

## Static-context acceptance (E15)

Estimate tokens as UTF-8 bytes divided by four. Repository validation reserves
the full memory-index allowance and enforces these component limits:

| Component | Limit |
|---|---:|
| Canonical instructions | 2,000 tokens |
| Largest harness overlay | 1,500 tokens |
| Installed skill descriptions | 2,000 tokens |
| Memory index reserve | 1,500 tokens |
| Thickest total | 8,000 tokens |

Live E15 must include instructions, the applicable overlay, aggregate deployed
skill descriptions, and the actual memory index. Report component and total
measurements, not only root-instruction file size.

## New-machine acceptance (E16)

E16 is a clean, isolated bootstrap completed in at most 15 minutes, followed
by E14, E12, and E15. The platform and skipped optional surfaces must be named.
Linux is an accepted clean-room platform for the shared v1 core; it does not
prove macOS-only Obsidian application integration. Bootstrap or projection
changes require another clean mechanical run. Behavioral evidence may carry
forward only when its instructions and relevant skills are byte-unchanged,
and the combined-evidence boundary must be explicit in the results.
