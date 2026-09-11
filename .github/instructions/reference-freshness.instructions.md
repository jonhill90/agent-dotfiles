---
description: 'Verify reference docs against live sources before relying on local content'
applyTo: 'docs/**/*.md'
---

# Reference Freshness

Reference docs are distilled summaries of external sources. They may be stale.

## Before Relying on Local Content

1. Use MCP tools (context7, microsoft-learn, deepwiki) to fetch current documentation
2. If the local summary contradicts the live source, trust the live source

Local references are a starting point, not the final word.

<!-- Narrowed 2026-09-11 (agent-estate#1397): this rule used to also say
"check the source URLs listed at the top of each reference doc" — no file
under docs/ carries a header of that shape (`grep -rln "^Source:|^\*\*Source"
docs/` returns nothing), so that step was dead instruction. Dropped rather
than reworded; the MCP-tool step above was verified still accurate. -->
