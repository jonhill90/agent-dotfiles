# hooks/

Canonical, harness-agnostic guard scripts (SPEC §3.3). Each of the six guard
scripts below (rows 1-6 in the table) is a Claude Code `PreToolUse` hook: it
reads the attempted tool call as JSON on stdin and decides with an exit code
— `0` allows, `2` blocks and feeds stderr back to the model as the reason. No
model judgment is involved in the decision itself; the model only reads the
refusal. This directory also holds `lib/common.sh`, the shared plumbing the
guards source, and `no-coauthor-trailer`, a separate git `commit-msg` hook —
not a `PreToolUse` hook.

Wiring: `settings/claude/settings.json` declares each hook with a
repo-relative `hooks/<script>.sh` command; `scripts/sync.py`'s
`resolve_hook_commands()` rewrites that to this install's absolute path
before writing `~/.claude/settings.json` (a hook fires from an arbitrary
session cwd, so a relative path there would resolve against the wrong
directory). **Corrected 2026-08-23:** Pi does not yet get these guards —
SPEC §3.3 scopes a thin TS extension that would shell out to the same
`hooks/` scripts, but agent-dotfiles#276 built Claude Code wiring only; the
Pi extension is not yet built (was previously stated as already delivered).
Codex/Copilot have no hook surface and rely on instructions instead.

## Origin — agent-dotfiles#276

> *"dont throw ai to solve every problem."* Most of what governed this
> estate's tmux, git and GitHub usage was prose in `PHASES.md` and
> `agent-supervisor/AGENTS.md` — re-read and re-obeyed by a model on every
> turn, reliable only as far as attention allows. A rule a deterministic
> check can decide does not need that; it needs a `case` statement that
> blocks the call outright, the way `cosmix/loom`'s `hooks/` directory does.

## The enumeration (requirement 5 — do not quote a count for a set nobody
has enumerated)

Every candidate the brief and the source documents named, checked one by
one. Source documents read in full: `PHASES.md` (994 lines, runtime state at
`~/.local/state/agent-dotfiles-supervisor/`), `NOTEBOOK-jon-directives.md`
(437 lines, same location), and `agent-supervisor/AGENTS.md` (the actual
prose home of several of these — see "What did not move" below).

| # | rule | mechanical? | disposition |
|---|---|---|---|
| 1 | Destructive tmux verb must run on an isolated socket (`TMUX_TMPDIR` + `env -u TMUX`) | yes — pattern match on the command | **hook**: `tmux-destructive-verb-guard.sh` |
| 2 | Never target `agent-supervisor:1`, the `Hill90` session family, or write `~/.tmux.conf` | yes — string/path match | **hook**: `tmux-protected-target-guard.sh` (the brief's third clause, "another lane", is NOT covered — see the script's own header) |
| 3 | Never commit to `main` | yes — branch check before commit | **hook**: `main-branch-guard.sh` |
| 4 | Post `gh api` bodies with `-f body="$(cat file)"`, never `--body-file`/`-f body=@file` | yes — flag/pattern match | **hook**: `gh-body-guard.sh` |
| 5 | A lane never closes its own issue | yes, when the branch encodes an issue number (`<type>/<N>-slug`) | **hook**: `lane-self-close-guard.sh` (out of scope, not blocked, when the branch names no issue) |
| 6 | Never open the live ledger for write | yes — path match plus a `-readonly`/`?mode=ro` allowance | **hook**: `ledger-write-guard.sh` |
| 7 | RULE A / RULE B / RULE B2 (AI is for reasoning; council before shipping an idea; cheap check before the council) | no — these ARE the judgment calls | **prose**, unchanged (`PHASES.md` §STANDING RULES) |
| 8 | Telegram is a narrow channel, not a log (RULE C) | no — "is this update worth sending" is a judgment call | **prose**, unchanged |
| 9 | QA gate / "Jon QAs look and feel, agents QA function" / picker-not-prose for design questions | no — deciding what is "lookable" or "a defensible variant" is judgment | **prose**, unchanged |
| 10 | Research before building; cite sources | no — assessing whether a claim is grounded is judgment | **prose**, unchanged |
| 11 | Stand-down must be one message, sent once | partially — "one message" is countable, but recognising a stand-down and composing it is judgment | **prose**, unchanged (no clean hookable predicate: nothing marks a message as "the stand-down") |
| 12 | Reviewer independence / one fix pass per PR / codex-out exception | no — "is this lane a contributor" and "has this been argued enough" are judgment, and the codex-out exception is itself time-boxed prose | **prose**, unchanged |
| 13 | Never modify real user accounts; test with `testuser01` only | yes in principle (string match on account name), **not built** — no source command pattern for "modifies a user account" was found to match against; scope it if/when one recurs | **deferred**, not hooked |

Rows 1–6 are the brief's own table, verified against source rather than
taken on faith — row 2's tmux invariant and row 3's branch convention are
both quoted verbatim from `agent-supervisor/AGENTS.md`; rows 4–6 have no
single canonical sentence anywhere and were reconstructed from the brief's
own wording plus `gh api`'s documented `-f`/`-F` semantics (row 4) and
`agent-supervisor/AGENTS.md` invariant 1 (row 6). Rows 7–13 were the rest of
`PHASES.md` and `NOTEBOOK-jon-directives.md`'s "Standing rules" sections,
read start to end — nothing else in either document reduces to a
deterministic check.

## What did not move — the prose these hooks would duplicate lives elsewhere

Requirement 4 says cut the prose once a rule becomes a hook, or point at it.
Rows 2 and 3's prose is **not in this repository** — it is
`agent-supervisor/AGENTS.md` invariant 4 and the "Conventions" list, a
different repo this dispatch has no branch or PR in. Editing another
repo's `main` from an agent-dotfiles worktree, unasked, is exactly the kind
of hard-to-reverse cross-repo action the operating-loop guardrails require
confirming first — so it was not done here. Filed instead:
`jonhill90/agent-supervisor#250`, pointing at these hooks and asking that
repo trim the now-duplicated sentences.

Rows 1, 4, 5 and 6 have no prose counterpart in `agent-supervisor/AGENTS.md`
at all — they existed only as the brief's own table and this issue's
research, so there is nothing to cut. Rows 7–13 stay in `PHASES.md` because
they are judgment calls, per the brief's own line: "the point is not to
hook everything — it is to stop spending model attention on checks a `case`
statement decides better."
