# E12 Memory Write-Back — 2026-07-12

- **Pairs:** Claude Code×Fable, Pi×default (gemini). Non-interactive
  (`claude -p --allowedTools 'Read,Write,Edit,Glob,Grep,Bash'`, `pi -p`),
  fresh sessions, scratch repos, driven via tmux.
- **Stack:** canonical instructions (+ Pi overlay) + memory-conventions
  skill + Agent Memory vault (iCloud). No hooks, no superpowers.

## Final matrix (each cell = 2 consecutive runs)

| Check | CC×Fable | Pi×default |
|---|---|---|
| Write-back: stated preference lands in `agent/facts/` + index | PASS | PASS |
| Cross-harness recall: fresh session, different directory, fact written by the *other* harness | PASS | PASS |

## Failure→fix history (baseline-first §4 auditions, in order)

1. **CC write FAIL #1:** claimed "Saved" but wrote only native
   auto-memory (project-local). Fix auditioned: instruction sentence
   "native memory does not substitute for the vault."
2. **CC write FAIL #2:** same behavior; wording insufficient. Fix
   sharpened to a completion gate: "a remember request is NOT complete
   until the vault file exists … verify before confirming."
3. **CC write FAIL #3 (different cause):** CC now *tried* the vault but
   reached for the **stale basic-memory MCP server** still registered
   at user scope — §9.3 migration debt. Fix: removed basic-memory from
   `~/.claude.json` (backup: `~/.claude.json.bak-m4`).
4. **CC write FAIL #4 (test-rig artifact):** without `Bash` in
   allowedTools, `$AGENT_MEMORY_VAULT` cannot be resolved. Test fixed,
   not the system. → **write PASS**.
5. **CC recall FAIL:** claimed vault "empty" without reading it
   (explicit read worked — behavioral, not access). Fix auditioned:
   recall-trigger rule "never claim not-on-record without reading the
   index this session." → **recall PASS ×2**.
6. **Pi:** passed write on first attempt (no native memory to
   interfere); recall PASS ×2.

## Adopted (recorded in provenance manifest)

- Two Memory-section instruction rules (completion gate for writes;
  read-before-recall) — adopted via failing-eval evidence, this file.
- basic-memory user-scope MCP registration removed from the machine.

## Observations

- Harness-native memory is the main adversary of cross-harness memory
  on CC; the completion-gate wording held only after the stale MCP
  server was gone. Watch E12 on Sonnet-class pairs at M5.
- Pi's zero-native-memory design makes it the clean-room control, as
  predicted in the Pi survey.
