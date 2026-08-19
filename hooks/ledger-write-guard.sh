#!/bin/bash
# PreToolUse guard (agent-dotfiles#276, table row 6).
#
# Rule: never open the live ledger for write. ledger.sqlite3 is
# agent-supervisor's durable record of lane ownership, task state and
# verdicts (agent-supervisor AGENTS.md invariant 1: "the ledger is the
# record; tmux is the screen"). An ad hoc write from outside cli.py/core.py
# bypasses the invariants those modules enforce (one open task per lane,
# etc.) and can corrupt the one thing that survives a tmux server loss. A
# path match on the live location is enough to decide this -- no judgement
# involved.
#
# Scope: this guards the LIVE ledger specifically -- a path under
# .../agent-dotfiles-supervisor/ or the default SUPERVISOR_STATE location,
# not a test fixture. The test suite creates its own throwaway
# ledger.sqlite3 copies under a tmp dir; those are unaffected because they
# do not match the live-path pattern below.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

RULE="ledger-write-guard (agent-dotfiles#276)"
hook_require_parsed "$RULE"

# Only in scope for a command that mentions the live ledger at all.
LIVE_LEDGER_RE='(agent-dotfiles-supervisor|\.local/state/[^/[:space:]]*supervisor[^/[:space:]]*)/ledger\.sqlite3'
echo "$HOOK_COMMAND" | grep -qE "$LIVE_LEDGER_RE" || exit 0

# Read-only forms are fine and exactly what a diagnostic dispatch needs:
#   sqlite3 -readonly ...ledger.sqlite3 ...
#   sqlite3 "file:...ledger.sqlite3?mode=ro" ...
#   python3 ...sqlite3.connect("file:...?mode=ro", uri=True)
if echo "$HOOK_COMMAND" | grep -qE '\-readonly\b'; then
  exit 0
fi
if echo "$HOOK_COMMAND" | grep -qE '\?mode=ro\b'; then
  exit 0
fi
# cli.py / core.py are the ledger's own writers and already enforce its
# invariants -- routing a write through them is not an ad hoc open.
if echo "$HOOK_COMMAND" | grep -qE '\b(cli|core)\.py\b'; then
  exit 0
fi

hook_block "$RULE" \
  "this opens the live ledger.sqlite3 directly instead of through cli.py/core.py or a read-only mode. The ledger is the durable record (agent-supervisor AGENTS.md invariant 1) -- an ad hoc write bypasses the invariants those modules enforce. Read it with sqlite3 -readonly or a file:...?mode=ro URI; write it only through the ledger's own API."
