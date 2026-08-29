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

hook_command_violates "$RULE" ledger || exit 0

hook_block "$RULE" \
  "this opens the live ledger.sqlite3 directly instead of through cli.py/core.py or a read-only mode. The ledger is the durable record (agent-supervisor AGENTS.md invariant 1) -- an ad hoc write bypasses the invariants those modules enforce. Read it with sqlite3 -readonly or a file:...?mode=ro URI; write it only through the ledger's own API."
