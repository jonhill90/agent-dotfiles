# Phase 0: Distillation Research

Research phase for the agent-dotfiles PRD (`../PRD.md`). Every document
here feeds the technical spec; decisions recorded here are preliminary
until eval-verified.

## Status (2026-07-11)

| Chunk | Doc | Status |
|---|---|---|
| APM verification (Pi + global scope) | [apm-verification.md](apm-verification.md) | ✅ Done — live-trial verified on this Mac; wrapper for Pi + teardown/Cowork warts |
| Behavioral-layer matrix (superpowers / mattpocock / agent-scripts) | [distillation-matrix.md](distillation-matrix.md) | ✅ Done — preliminary hybrid synthesis |
| Memory backends | [memory-backends.md](memory-backends.md) | ✅ Done — Obsidian vault + CLI recommended, Graphiti benched |
| Eval scenarios (parity acceptance tests) | [eval-scenarios.md](eval-scenarios.md) | ✅ Draft — E1–E16 |
| Pi harness survey | [pi-harness.md](pi-harness.md) | ✅ Done — installed 0.80.6; native ~/.agents/skills, AGENTS.md global file, extensions=hooks, MCP absent by design |
| Harness baselines (Anthropic/Codex/Copilot docs sweep) | [harness-baselines.md](harness-baselines.md) | ✅ Done — layer×harness matrix; 4 hands-on verify items remain |
| Provenance manifest (adopt/adapt/author/reject log) | [../provenance-manifest.md](../provenance-manifest.md) | 🟡 Seeded at spec time (2026-07-12); open rows close via eval results |
| M2 install verification (apm install -g end-to-end) | [m2-install-verification.md](m2-install-verification.md) | ✅ Done — skills to both paths, marker-owned root files, warts confirmed; M3 job list updated |
| Memory format distillation (INMPARA × Second Brain × Karpathy × OKF) | [memory-format-distillation.md](memory-format-distillation.md) | ✅ Done — memory vault = OKF-conformant bundle; semantic slugs; ISO 8601 w/ seconds; log.md temporal layer |
| V6: Obsidian CLI selection (official vs third-party) | [obsidian-cli-v6.md](obsidian-cli-v6.md) | ✅ Done — owner override: official CLI adopted (verified hands-on 1.12.7; no auto-launch); memory = direct file ops, no CLI dependency; memory vault must be personal (employer-mount doctor check) |

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
4. **Per-harness thinning is now a spec requirement** (harness-baselines
   Finding 3): Claude Code natively covers much of the loop; Codex/Copilot
   have no hooks, so enforcement there rides instructions + descriptions —
   eval E14 tests that degraded mode.
5. **`~/.agents/skills` is the emerging neutral user-scope skills path**
   (Codex native, Copilot accepted; Claude Code via per-skill symlinks —
   officially supported; Pi via extension `skillPaths`).
6. **One canonical AGENTS.md projects trivially**: Codex/Copilot read it
   natively, Claude Code via documented `@AGENTS.md` import, and APM's
   `compile --global` writes exactly these root files.
