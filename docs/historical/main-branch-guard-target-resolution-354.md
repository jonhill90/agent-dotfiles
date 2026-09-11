---
type: Document
knowledge_status: historical
updated: 2026-09-11T18:56:14+00:00
---

# A guard resolves its subject from the command, not the session that runs it

**Status:** decided and shipped. `main-branch-guard.sh` was rewritten in #354
(merged `23c12e9`, closing #353) around this principle; it is not a standing
rule written anywhere else in this repo, so it is recorded here rather than
left to be re-derived from the diff.

## What was wrong

`main-branch-guard.sh` read the branch to protect from the hook payload's
`cwd` — the session's own directory — never from where the commit would
actually land. Its own comment claimed the opposite. #353 named the
consequence plainly:

> Every lane works in a worktree, because `protect-shared-checkout` pushes
> it there, so every lane was exactly the session shape that disarmed this
> guard.

That is the serious half: a write landing on `main` was **allowed** whenever
the session sat in a worktree, which is every lane, every time. The guard
also blocked legitimate work in the other direction — a session on `main`
committing into a feature worktree was refused, because the check asked the
wrong question in both directions.

## The decision

**A guard's subject is the thing being acted on, never the actor's own
location.** `main-branch-guard.sh`'s rewrite (`hooks/lib/command_guard.py`'s
`main-targets` rule) resolves every commit's real target from the command
text itself — `git -C <path>`, a preceding `cd` in the same shell scope, or
the session `cwd` only as the last, narrowest fallback — and refuses rather
than guesses when it cannot: an unresolvable `cd`/`-C` target, a `pushd`, a
`||` after a `cd` that might not have run, `--git-dir`/`--work-tree`, a
directory that does not exist. Every one of those returns `UNRESOLVED
<reason>`, never a silent allow.

This is worth stating as a rule the next guard should follow by default, not
just this one's own fix: **`cwd` is a fact about the actor, not the target.**
Any guard whose real subject can differ from where the session happens to be
sitting has the same shape of hole until it resolves the subject explicitly.

## What this does not claim

The rewrite states its own remaining limits rather than pretending it covers
everything — a git alias for `commit` (`git ci`) is not expanded, because
that needs git's own config as a second source of truth; a `cd` inside
`if`/`for`/`while` is read as sequential in the enclosing scope, conservative
toward blocking rather than silently correct. Named as gaps, not claimed as
closed.

## References

- agent-dotfiles#353 — the defect, both directions, plus the third
  (use-vs-mention) defect found while filing it
- agent-dotfiles#354 — the fix, two independent review rounds
  (`53965130` → REQUEST-CHANGES on a `cd -` hole; `6cf668b6` → APPROVE)
