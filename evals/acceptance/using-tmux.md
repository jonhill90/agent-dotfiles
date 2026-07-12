# Acceptance: using-tmux

Tasks the skill must let the agent complete (SPEC §10 tool-skill track).
The V7 community-candidate comparison runs against this list.

1. Start a named session/pane for an interactive REPL and address it by
   explicit target (never "current pane").
2. Send a command and *verify* it arrived (echo/inspect) before
   trusting the output — no fire-and-forget send-keys.
3. Poll for a long-running command's completion and capture its output
   without truncation.
4. Recover a stuck pane (interrupt, clear, resume) without killing an
   unrelated pane.
5. Run an interactive auth flow (e.g. a CLI login prompt) to completion.

PASS: all five with zero writes to panes the agent did not create.
Check 5 separates real skills from wrappers around `tmux send-keys`.
