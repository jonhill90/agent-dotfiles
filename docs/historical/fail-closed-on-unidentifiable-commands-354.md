---
type: Document
knowledge_status: historical
updated: 2026-09-11T18:56:14+00:00
---

# The shared guard parser fails closed when it cannot identify the command — and that has a measured cost

**Status:** decided and standing. `hooks/lib/common.sh`'s `hook_require_parsed`
and `command_guard.py`'s own `ParseError` path refuse rather than guess; this
governs every guard built on the shared parser (#354 onward), not just one
hook, so the trade-off is recorded once here rather than per-guard.

## The rule

Two call sites in `hooks/lib/common.sh` state it directly:

> could not identify executable commands in this Bash payload well enough to
> apply the guard -- refusing rather than guessing.

> could not parse the tool call well enough to decide -- refusing rather
> than guessing (agent-dotfiles#276 requirement 2: ambiguity must never
> resolve to allowed).

An unterminated quote, heredoc, subshell, substitution, or a dangling
trailing backslash — all structurally invalid bash on their own terms — exits
the guard blocked, not allowed. This is the same posture `main-branch-guard`'s
own target resolution takes for a `cd`/`-C` path it cannot resolve (see the
sibling record on this repo's subject-resolution decision): ambiguity is a
refusal, never a coin flip toward "probably fine."

## The cost, measured, not asserted

This is a real trade, not a free one. The partial-deployment audit on #353
measured it directly rather than assuming a low rate:

> Fed 51 ordinary one-liners representative of this repo's own usage
> (git/gh/tmux/python/pipes/subshells/backslash-continuations/etc.) through
> the exact scope-check rule (`command_guard.py main`): 0/51 refused. So the
> false-positive rate on ordinary usage looks low, but not zero — the
> deploying session did hit one real refusal on a compound one-liner,
> meaning the edge case is real even if rare. Worth watching, not blocking.

**One documented refusal, not several** — the audit's own count, not a
larger figure. A compound one-liner outside the 51-case sample was blocked
once during the session that deployed this parser. That is the evidence this
record rests on; a claim of repeated, routine friction would overstate it.

## Why the trade is still the right one

The alternative — resolving an unparseable payload as "probably not a
violation" — is exactly the failure class agent-dotfiles#276 requirement 2
exists to close, and it is also how #353's own third defect went unnoticed
for as long as it did: a guard confident about the wrong thing is worse than
one that visibly refuses. A refusal is loud, immediate, and named in the
same tick it happens; a wrong allow is silent until something depends on it.
The measured cost (rare, but real, on ordinary compound one-liners) is worth
carrying because the alternative failure mode is the one this whole guard
family was built to stop being invisible.

## References

- `hooks/lib/common.sh` — `hook_require_parsed`, the two refusal messages
  quoted above
- agent-dotfiles#353 (audit comment,
  [permalink](https://github.com/jonhill90/agent-dotfiles/issues/353#issuecomment-5637948982)) —
  the 51-case measurement and the one real refusal
- agent-dotfiles#276 — requirement 2, "ambiguity must never resolve to
  allowed"
