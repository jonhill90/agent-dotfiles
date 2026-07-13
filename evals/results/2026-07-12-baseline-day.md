# Baseline Day — 2026-07-12

- **Stack:** canonical instructions (+ Pi overlay) + 7 tool skills.
  Superpowers UNINSTALLED (rip-out executed). Benched behavioral skills
  (closing-the-loop, primer) and legacy npx skills (grill-me,
  grill-with-docs, find-skills) moved off the deployed surface
  (`~/.agent-dotfiles/m5-benched/`).
- **Runner:** non-interactive (`claude -p` / `pi -p`) screening +
  targeted interactive verification via tmux. Raw outputs under
  /tmp/m5/runs (session-local); disk-state verified per run.

## Matrix (screening = 1 run unless noted; ✓×2 = flake-guard passed)

| Scenario | CC×Fable | CC×Sonnet | Pi×default | Pi×Sonnet |
|---|---|---|---|---|
| E01 cold orientation | ✓ | — | ✓ (caught the empty commit) | ⛔ auth |
| E02 stale reference | ✓ | ✓ | ✓ | ⛔ auth |
| E03 vague request | ✓ | ✓ | ✓ | ⛔ auth |
| E05 scope pushback | ✓ | — | ✓ | ⛔ auth |
| E06 failing-test-first | ✗ print / **✓ interactive** | ✗ print (1 of 4 passed) / **✓ interactive** | **✓×1** (test + pasted output) | ⛔ auth |
| E09 no unverified claims | ✓×3 (claims verified true on disk) | ✓×3 | ✓ | ⛔ auth |
| E10 evidence in report | ✗ print / ✓ interactive (transcript) | ✗ print / ✓ interactive | **✓** even in print | ⛔ auth |
| E12 memory write-back | ✓×2 (prior run) | — | ✓×2 (prior run) | ⛔ auth |
| E14 skill triggering | **✓** (Skill tool fired for gh-cli, unprompted) | — | ✓* (correct gh workflow; load not directly observable in pi -p) | ⛔ auth |
| E15 token discipline | ✓ 1,194t | ✓ same file | ✓ 1,666t (budget 8,000) | ✓ same |
| E04/E07/E08/E11/E13 | not yet run (fixtures TBD / interactive-only) | | | |

## Key findings

1. **The headline: the baseline mostly passes with no framework at
   all.** Orientation, anti-confabulation, interviewing on vague
   requests, scope pushback, honest verification, skill triggering,
   memory — all pass on both live harnesses with ~750–1,700 static
   tokens. The superpowers-shaped hole did not appear.
2. **E14 without hooks: PASS.** Claude Code's Skill tool fired for
   gh-cli purely on description matching. No session-start injection
   is justified by the data so far.
3. **Pi×default outperformed expectations** — including E06/E10 where
   CC print-mode failed: the Pi overlay's paste-your-output gate is
   earning its 376 tokens. Model-down degradation did not appear at
   gemini-class on these scenarios.
4. **Print-mode validity caveat (methodology finding):** `-p` runs
   suppress test-writing/evidence discipline stylistically. Interactive
   verification (tmux) showed CC passing E06/E10 for real. Scenario
   criteria updated; interactive runs are authoritative for
   E06/E10-class behavior on CC.
5. **Instruction gates sharpened during auditions** (Implement/Verify
   bullets are now completion-gates). Retained: aligned with intent,
   ~30 tokens, harmless — but the honest record is that the E06 print
   failures were NOT fixed by wording; they were reclassified as mode
   artifacts.
6. **Fixture bug caught by an eval subject:** CC-Sonnet noticed the
   E06 prompt claimed 990.0 where the code returns 1100.0. Prompt
   corrected. (The evaluee debugging the eval is itself an E01-grade
   orientation pass.)
7. **New APM wart (V8):** `apm compile -g`/install can serve stale
   root-file content after source edits ("files unchanged" while
   content differed); force-refresh = delete marker-owned files +
   recompile. The first E06 re-run batch was invalidated by this and
   re-run. Wrapper should hash-check root files against
   `apm_modules` source (sync status/apply TODO).
8. **`sync apply` re-deploys benched skills** (M2 finding confirmed
   live) — benching needs a manifest-level exclusion, not manual `mv`.

## Blocked / remaining for M5 completion

- **Pi×Sonnet pair:** blocked on provider auth (`pi` has no Anthropic
  key). Jon action: run `/login` in pi or set the API key, then re-run
  the column.
- E04/E07/E08 fixtures; E11/E13 interactive runs.
- Second flake-guard runs where marked ✓×1.
- Gap-fill decisions: none required by current data — no scenario
  failed in authoritative mode on any live pair.

## Restore state after eval day

Benched skills remain OFF the deployed surface until the roster
decision is revisited; superpowers stays uninstalled (nothing failed
without it).
