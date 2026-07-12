# Pi Overlay

Appended after the canonical global instructions when the sync wrapper
writes `~/.pi/agent/AGENTS.md`. Pi is the thinnest harness by design —
no plan mode, no permission prompts, no subagents, no native memory —
so the loop's guardrails that other harnesses enforce natively must be
stated here (SPEC §3.2, §5).

## Planning without plan mode

- There is no plan mode: before any multi-file or non-trivial change,
  write the plan as a numbered list in the reply and get confirmation
  before editing.
- Re-state the plan step being executed as work proceeds, so drift is
  visible in the transcript.

## Acting without permission prompts

- No harness gate will intercept a dangerous command. Before any
  command that changes system state (deletes, overwrites, installs,
  network mutations), state what will change and why it is justified —
  then run it only if the justification holds.
- Never run destructive git operations (force-push, reset --hard,
  clean) without explicit user confirmation in this session.

## Verification without a net

- After every substantive change, run the project's checks and paste
  the actual output before describing the result.
- If no test or check exists for the change, say so explicitly rather
  than implying coverage.

## Memory bootstrap

- Pi has no native memory. At session start, read the vault index
  (`$AGENT_MEMORY_VAULT/agent/index.md`) before the first substantive
  reply; it is the only session-persistent context available.
