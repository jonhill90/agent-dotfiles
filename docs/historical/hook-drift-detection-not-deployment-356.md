---
type: Document
knowledge_status: historical
updated: 2026-09-11T18:56:14+00:00
---

# Detecting hook drift is not deploying a fix, on purpose

**Status:** decided and shipped, in `agent-estate`, not this repository —
recorded here because the consequence lands entirely on this repo's own
checkout. `estate hook-status` (agent-estate#1416, merged `ca79f8f`) reports
this checkout's own drift against `origin/main`; it does not, and by design
cannot, repair it.

## Why this repo needed the separation stated explicitly

#353's own fix (#354) merged and did not run — the deployed checkout was 17
commits behind the SHA that carried it, and nothing said so. That silence is
what #356 named: *"a hook that silently runs an old version looks exactly
like a hook that is working."* The natural next step — build a tool that also
*fixes* the drift it finds — was considered and deliberately not taken.
`hookstatus`'s own doc comment states the boundary directly:

> This package is DETECTION ONLY: it reads the checkout and origin/main,
> classifies every file under `hooks/`, and reports. It never fetches,
> pulls, tidies, writes to, or otherwise mutates the checkout it inspects —
> deployment policy is a decision for a human, not this package (see the
> package's own callers in main.go, which refuse a `--fix` flag on
> purpose).

No repair path was built at all — `estate hook-status` recognizes exactly one
flag (`--json`); anything else, including a hypothetical `--fix`, is refused
the same as any other unrecognized flag. Reporting and repairing were never
merged into one command that could quietly grow a `--fix` later without a
separate decision to add it.

## Why, for this repo specifically

Deployment policy for *this checkout* is Jon's, unresolved as of #356/#357:
whether the checkout should pin to a deliberate, recorded revision, auto-follow
`origin/main`, or something else entirely is still open. An automated tool
that also deployed would have pre-empted that choice the first time it ran —
exactly backwards from what #357 itself argued for the one guard it found
completely undeployed (`keychain-write-guard.sh`): *"Adding a hook to
`settings.json` changes what every session refuses ... the kind of change
that should be his, even when the control is protective."* Detection-only
lets the reporting half exist now, continuously (wired into `estate tick
check`, agent-estate#1419, so staleness surfaces without anyone remembering
to run it by hand) while the policy half still waits on him.

## What this changes here, and what it does not

`agent-dotfiles`'s own deployed `hooks/` checkout is now visible-when-stale
by construction, every few minutes, from outside this repository. It is not
auto-repaired, not pinned, and not blocked from drifting further — this
record exists so that absence is read as "the decision is still open," not
as an oversight nobody built a fix for.

## References

- agent-estate#1416 — `hookstatus`, detection-only by design
- agent-estate#1419 — wired into `estate tick check`, non-fatal disclosure
- agent-dotfiles#356 — the original "nothing reports it" finding
- agent-dotfiles#357 (quoted above) — the parallel argument for the one
  guard, applied here to the mechanism as a whole
- agent-dotfiles#353 (reopened,
  [permalink](https://github.com/jonhill90/agent-dotfiles/issues/353#issuecomment-5634489160)) —
  "a merged hook fix that does not deploy is a gap in the mechanism, not an
  accident of this one PR"
