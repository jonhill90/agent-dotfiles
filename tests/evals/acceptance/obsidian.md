# Acceptance: obsidian

Tasks the skill must let the agent complete (SPEC §10 tool-skill track).
The skill wraps the **official Obsidian CLI** (owner decision, V6
addendum); the app must be running. Checks 1–4 verified hands-on
2026-07-12 on 1.12.7.

1. Create a note at a given vault path with frontmatter, from a shell
   (`obsidian create name=… content=…`).
2. Read a note's full contents back by path (`obsidian read`).
3. Search the vault and get machine-readable results
   (`obsidian search query=… format=json`).
4. Append to an existing note without clobbering it
   (`obsidian append`), and read/set a frontmatter property
   (`property:read` / `property:set`).
5. Target a named vault deterministically (`vault=<name>` first
   parameter) and fail *loudly and fast* when the app is not running —
   never hang or write to the wrong vault.

**Memory-backend note:** the memory contract does NOT run through this
skill or any CLI — it is direct file operations on the vault directory
(SPEC §3.6), so memory works headless on every harness regardless of
these checks.
