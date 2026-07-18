---
name: safe-deletion
description: Gate destructive file and directory operations by verifying contents match their described purpose before removing anything. Use whenever asked to delete, remove, clean up, clear out, purge, or empty files, directories, logs, caches, or artifacts.
---

# Safe Deletion

Deletion is irreversible. Run this gate before any destructive file
operation, including when the user explicitly says to delete.

## Gate

1. List the target's actual contents first (`ls -la`, `git ls-files`,
   or equivalent). Never delete blind.
2. Compare what is there against how the target was described or named.
   A directory called `old-logs`, `tmp`, `backup`, or `scratch` that
   contains source code, schema definitions, documents, or the only
   copy of anything does NOT match its description.
3. On mismatch: STOP. Do not delete. Report exactly what was found and
   why it contradicts the description, then ask how to proceed. An
   explicit instruction to delete does not waive this step — the
   instruction was given before the contents were known.
4. On match: proceed, then report precisely what was removed and how it
   was verified (e.g. listing before and after).

## Scope

Applies to shell removals (`rm`, `find -delete`, `git clean`), file
tools, and bulk overwrites. For version-controlled paths, prefer
recoverable operations (`git rm`, a commit before cleanup) and say so.
