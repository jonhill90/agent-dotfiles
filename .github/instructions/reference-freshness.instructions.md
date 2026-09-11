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
under docs/ carries a header of that shape. Verified with a check proven
sensitive first, not an absence claim taken on faith: `grep -rlnE
'^Source:|^\*\*Source' docs/` (note -E; the original PR published this
same pattern without it, which made `|` literal and the check unable to
match anything, positive or negative — corrected on review). Positive
control, piped through stdin ahead of the real run:
    $ printf 'Source: https://example.invalid\n**Source:** https://example.invalid\n' \
        | grep -nE '^Source:|^\*\*Source'
    1:Source: https://example.invalid
    2:**Source:** https://example.invalid
confirms the pattern matches both header shapes when they exist. Run for
real against docs/, it returns nothing — so that step was dead instruction.
Dropped rather than reworded; the MCP-tool step above was verified still
accurate. -->
