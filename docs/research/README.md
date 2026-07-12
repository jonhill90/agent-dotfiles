# Phase 0: Distillation Research

Research phase for the agent-dotfiles PRD (`../PRD.md`). Every document
here feeds the technical spec; decisions recorded here are preliminary
until eval-verified.

## Status (2026-07-11)

| Chunk | Doc | Status |
|---|---|---|
| APM verification (Pi + global scope) | [apm-verification.md](apm-verification.md) | ✅ Done — conditional pass, wrapper for Pi |
| Behavioral-layer matrix (superpowers / mattpocock / agent-scripts) | [distillation-matrix.md](distillation-matrix.md) | ✅ Done — preliminary hybrid synthesis |
| Memory backends | [memory-backends.md](memory-backends.md) | ✅ Done — Obsidian vault + CLI recommended, Graphiti benched |
| Eval scenarios (parity acceptance tests) | [eval-scenarios.md](eval-scenarios.md) | ✅ Draft — E1–E16 |
| Pi harness survey | [pi-harness.md](pi-harness.md) | 🟡 Partial — extension API evidenced; docs pass + install pending |
| Anthropic docs sweep (Claude Code baseline, Agent Skills spec) | — | ⬜ Pending |
| OpenAI Codex docs sweep | — | ⬜ Pending |
| GitHub Copilot docs sweep | — | ⬜ Pending |
| Provenance manifest (adopt/adapt/author/reject log) | — | ⬜ Starts at spec time; successor to ../migration-audit.md |

## Key preliminary conclusions

1. **APM is viable as the sync backbone** for Claude Code/Codex/Copilot at
   user scope (`apm install -g` + `apm compile --global`); Pi needs a thin
   wrapper. Residual: hands-on trial of user-scope skill deployment.
2. **Hybrid behavioral layer:** superpowers as the enforcement chassis
   (only contender with cross-harness bootstrap incl. Pi), Matt-Pocock-lean
   skills inside the loop where duplicates exist, agent-scripts as pattern
   donor only. Conflicts resolved by evals E3/E5/E6/E7/E14.
3. **Memory:** Obsidian vault + obsidian-cli + a conventions skill;
   file-based; no standing infra. Graphiti benched with a revisit trigger.
4. **The official-docs sweeps determine per-harness thinning** — how much
   behavioral layer each harness needs given its native features.
