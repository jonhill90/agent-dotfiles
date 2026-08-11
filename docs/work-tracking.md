# Work tracking

GitHub Issues on `jonhill90/agent-dotfiles` is the tracking surface for
open work. `gh` is the CLI (repo rule: CLI-first), and it needs no
credential beyond the one a machine already has for the repository.

## What the tracker is *not*

`docs/SPEC.md` §11–§13 hold milestones and verification items;
`docs/provenance-manifest.md` holds decisions. **Those documents are
canonical.** An issue cites its section rather than restating it, and
when an issue and the SPEC disagree, **the SPEC wins and the issue is
corrected**.

This is a knowing duplication, not a free one. Eight issues were ported
from the previous tracker; two more were not, because they were already
finished. Of the eight, only the five `Parked:` issues carried a fact the
repo did not already own — the other three mirror SPEC rows that already
say "Open" and carry a done-when clause. Those three are tracked anyway
because a milestone that exists only in a table is not surfaced between
sessions, which is the failure the tracker exists to fix. Adding an issue
for something SPEC already states is a deliberate cost, not the default.

## Labels — the whole taxonomy

| Label | Meaning |
|---|---|
| `milestone` | tracks a SPEC §12/§13 milestone |
| `verification` | tracks a SPEC §11 verification item |
| `parked` | decision deferred behind a revisit trigger; not actionable |
| `blocked:quota` | cannot proceed until a vendor quota resets |
| `blocked:vendor` | cannot proceed until a vendor ships a capability |

No GitHub Projects and no GitHub Milestones. SPEC already holds the
phase structure; mirroring it into GitHub is a second copy that drifts.

## Rules

1. Open work that is expected to happen gets an issue citing its SPEC
   section.
2. **Parked decisions get an issue.** A decision deferred, benched, or
   rejected-pending-evidence carries a revisit trigger, and a trigger
   buried in a wide manifest table never fires. Title it
   `Parked: <subject>`; state the decision, the trigger, and any
   ordering against a related candidate. The manifest row stays
   canonical; the issue exists only so the trigger is visible.
3. **Do not open issues for finished work.** History lives in git and
   the provenance manifest. A backfill would be a second, lossier copy
   of facts git already owns, written from recollection rather than
   from the evidence that settled them.
4. Close with `Fixes #N` in the PR body — native GitHub behaviour, no
   integration required.
5. **An assignee means the issue is claimed by a lane.** Dispatchers take
   the claim with `scripts/supervisor/claim.sh take <n> <repo> <lane>`
   before sending any brief, and select work with `claim.sh list`, which
   omits claimed issues. Do not hand-assign an issue you are not
   dispatching — it reads as taken and will be skipped. The claim goes
   away when the PR closes the issue; `claim.sh release <n> <repo>` drops
   it by hand, and `claim.sh stale <repo>` reports claims whose lane is
   gone. Before this existed, nothing wrote a claim anywhere: #28 was
   dispatched to two lanes ninety seconds apart and fixed twice (#68
   merged, #69 closed).

## Flow

```bash
gh issue list                                  # open work
gh issue list --label parked                   # dormant decisions
gh issue view 56                               # a runbook
gh issue create --title "..." --label milestone --body-file body.md
```

Branch with the repository's type prefix (`docs/`, `feat/`, `chore/`),
land through a PR; CI gates on `pull_request`.

Write large issue bodies with `--body-file`. Fenced code blocks and
indentation survive; passing long bodies inline through a shell does not
reliably preserve them.

## Historical `AI-###` references

Work was tracked in Linear (workspace `jonhill90`, team `AI`) for about a
day. Commit messages and PR bodies from jonhill90/skills#44–jonhill90/skills#50 carry `Refs AI-259`
style references. An `AI-` autolink is registered on the repository so
those keep resolving:

```bash
gh api repos/jonhill90/agent-dotfiles/autolinks     # verify
```

Keep it. GitHub autolinks are prefix-triggered, so `AI-` and `#` cannot
collide, and removing it would degrade seven PR bodies to plain text for
no gain. The Linear issues are closed, not deleted.

| Linear | GitHub | Subject |
|---|---|---|
| AI-259 | — | P2-M4 (completed before migration) |
| AI-262 | — | V9 (resolved before migration) |
| AI-260 | jonhill90/skills#56 | P2-M5 |
| AI-261 | jonhill90/skills#57 | P2-M6 |
| AI-263 | jonhill90/skills#58 | V10 |
| AI-264 | jonhill90/skills#51 | Parked: tmux (V7) |
| AI-265 | jonhill90/skills#52 | Parked: typed relations |
| AI-266 | jonhill90/skills#53 | Parked: Graphiti |
| AI-267 | jonhill90/skills#54 | Parked: memory lint |
| AI-268 | jonhill90/skills#55 | Parked: fact-schema type enum |

## Verify writes

`gh` is well-behaved, but the standing rule from the previous tracker
survives because it cost real time there: **a command's exit status is
not the result.** Read back after a write that matters.

```bash
gh issue edit 56 --add-label blocked:quota
gh issue view 56 --json labels -q '[.labels[].name]'
```
