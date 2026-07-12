# Acceptance: obsidian

Tasks the skill must let the agent complete (SPEC §10 tool-skill track).
These double as the memory backend's requirements (SPEC §3.6) — the V6
CLI decision (official Obsidian CLI vs third-party obsidian-cli) is
made against this same list.

1. Create a note at a given vault path with frontmatter, from a script
   (non-interactive; no GUI required).
2. Read a note's full contents back by path.
3. Search the vault for a term and return matching note paths.
4. Append/update a line in an existing note (index-update pattern)
   without clobbering the rest.
5. Resolve the target vault deterministically (by name or path — no
   "last open vault" ambiguity) with the vault closed in the GUI.

PASS: all five headless from a shell. Check 5 is the historical failure
mode — treat any GUI dependency as FAIL.
