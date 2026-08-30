#!/bin/bash
# PreToolUse guard (agent-estate#665).
#
# Rule: macOS Keychain is a credential store and is read-only, with no
# exception for diagnosis, repair, reset, or probing. On 2026-08-24,
# `security add-generic-password -U -A` against a live credential destroyed
# its ACL and locked every agent out for a full day. The sanctioned operations
# are read-only lookups such as `security find-generic-password` and
# `security show-keychain-info`.
#
# Scope: command_guard.py parses executable Bash command segments before this
# hook decides. A quoted mention in an issue body, commit message, code
# comment, or heredoc is an argument to another command, not an invocation of
# `security`, and must remain allowed. The mutator list was confirmed with
# `security help` on 2026-08-30; it includes the password, partition-list,
# keychain-selection, and trust-setting write forms beyond the original probe.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

RULE="credential-store-read-only (agent-estate#665)"
hook_require_parsed "$RULE"

hook_command_violates "$RULE" keychain || exit 0

hook_block "$RULE" \
  "this invokes a macOS Keychain write operation. The credential store is read-only: do not add, delete, reset, or probe credentials. A 2026-08-24 'security add-generic-password -U -A' destroyed a live credential ACL and locked every agent out for a full day. Use read-only lookups such as 'security find-generic-password' or 'security show-keychain-info' instead."
