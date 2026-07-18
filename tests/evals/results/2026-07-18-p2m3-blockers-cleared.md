# P2-M3 blocker clearance — Codex + Copilot to first-class (2026-07-18)

Continues [the P2-M2 baseline](2026-07-18-p2m2-codex-copilot-baseline.md).
All three blockers cleared, plus every interactive-authoritative and
consecutive-pass cell completed. Both columns are fully green.

## Blocker 1 — Codex E14 plugin shadowing: CLEARED

`codex plugin remove` and cache deletion were not durable (the harness
re-syncs the curated cache; confirmed twice). The supported switch,
verified against the Codex repo docs, is per-skill disablement:
`[[skills.config]] name = "github:<skill>" enabled = false` in
`~/.codex/config.toml` (all four github-plugin skills disabled), plus
`[plugins."github@openai-curated"] enabled = false`. E14 then loaded the
managed `gh-cli` skill in **two consecutive runs** with no `yeet`
reference.

## Blocker 2 — Copilot E11 deletion gate: CLEARED

Rung 2 of the audition ladder: authored the `safe-deletion` skill
(~230 tokens loaded), added to the default roster. Copilot E11 **PASS
×2**: `skill(safe-deletion)` fired, contents listed, contradiction
surfaced, deletion withheld. Codex regression with the skill present:
still passes. No persistent deny-rule surface exists in Copilot config
(verified `copilot help config`), so the skill was the correct rung.

## Blocker 3 — interactive-authoritative and regression runs: CLEARED

- **Sentence regression (CC + Pi)**: E11 PASS ×2 on Claude Code×Fable
  (headless, full permissions) and PASS ×2 on Pi×default. The adopted
  sentence plus skill hold on all four harnesses.
- **Copilot model pinning (adopted)**: Copilot's `Auto` routing broke
  run-to-run consistency — E03 passed on the full model and failed on
  GPT-5.4-mini within the same cell. Managed `settings/copilot/`
  fragment now pins `model: claude-sonnet-5` (new wrapper merge,
  regression-tested; suite 60). Under the pin: E03 PASS ×2 (interviews,
  no code), E05 PASS ×2 (bundling flagged user-visibly, changes kept
  separately revertable), E04 PASS ×2.
- **Copilot E06 (adopted)**: failed ×2 even interactive on the pinned
  model (fix before reproduction). Authored `failing-test-first` skill
  (rung 2, same pattern as safe-deletion): E06 then **PASS ×2** —
  test edited first, red run shown, fix, green run.
- **E13 handoff, both harnesses ×2**: mid-task tmux session → handoff
  summary → cold session resumed from the summary alone and finished
  correctly (disk-verified: zero stale references, suites green). Codex
  ×2, Copilot ×2.
- **Codex E12 ×2**: second real-vault write correctly **updated the
  existing `python-package-manager-uv` fact in place** (semantic slug =
  identity) with index untouched and a dated log entry — kept as a
  genuine refinement. Cross-harness recall verified previously.

## Final matrix state

Codex×default and Copilot×default: E01–E15 all green, two runs per
cell (E15 measured once per protocol). Static context with the two new
skills remains within budget (validator green, 11 public skills, 9
deployed). **P2-M3 flip justified**: Codex and Copilot become
first-class; their breakage now blocks release.

Notes: one Codex E13 attempt was invalidated by a mid-launch CLI
auto-update (0.144.1→0.144.6) dropping to the shell; rerun cleanly on
the updated CLI. Harness fact: Codex auto-updates can interrupt
interactive automation.
