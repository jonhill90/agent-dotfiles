# Handoff — current state

Living document. Rewritten, not appended to. Last verified **2026-07-29**.

**Stale as of 2026-08-09 (#10):** the eval scenarios, counter-scenarios,
harness, results/transcripts, scoring/arming tools, and `docs/evals.md`
moved to the private jonhill90/agent-evals (evidence unavailable publicly)
repository. Everything below dated 2026-07-29 or earlier that discusses
`tests/evals/...` content, defect counts, or eval-apparatus size describes
that repository now, not this one; mechanical numbers (test counts, skill
counts) were not re-measured for this note and need a fresh verification
pass before they're trusted again. This banner replaces a full rewrite,
which the split alone does not justify.

Two reviewers audited this file before you got it. The mechanical numbers below
were re-run and hold exactly. Nine *narrative* numbers were wrong on the first
draft — each one drifted toward the point its sentence was making. Corrected
here, with the correction marked where it matters. Where a claim cannot be
checked from the repository, it now says so; treat those as hearsay.

## What this repository is

Jon's personal harness for AI coding agents — dotfiles for agents. One user,
two machines, four first-class harnesses: Claude Code, Codex, Copilot, Pi.
Portable skills stay individually installable; instructions, agents, settings
and MCP declarations are deployed at user scope by APM plus a thin wrapper
(`scripts/sync.py`).

The GitHub repository is **`jonhill90/agent-dotfiles`**. The local checkout
directory is `agent-dotfiles` — see Traps for a sibling directory that has
caused confusion.

Read in this order: `AGENTS.md` (repo policy — this is the one that governs how
you work), `README.md` (where a skill belongs), `docs/PRD.md` (intent),
`docs/SPEC.md` (design), `docs/provenance-manifest.md` (every adopt/reject
decision), `docs/work-tracking.md` (issue conventions). The eval vocabulary
used throughout this file now lives in `docs/evals.md` in the private
jonhill90/agent-evals (evidence unavailable publicly) repository.

`AGENTS.md`, `CLAUDE.md` and `.github/copilot-instructions.md` are the same file
by symlink. Edit `AGENTS.md`.

## How work lands here — read before you change anything

- **Branch with a type prefix**: `docs/`, `feat/`, `chore/`. Do not commit to
  `main`.
- **Open a PR.** CI gates on `pull_request`. Close issues with `Fixes #N` in
  the PR body.
- **Issues on this repository are the only tracker.** `gh issue list`.
  Conventions and labels: `docs/work-tracking.md`. This repo does not track
  work in Linear or anywhere else — `linear` is in the skill roster for Jon's
  other projects, not for this one.
- **The §10.1 evidence bar governs the default roster, not every skill.**
  `README.md` lines 71–118 has the decision table. Do not run the eval ladder
  on a project skill; it costs real runs and answers a question nobody asked.

## Verify before you act

These five are read-only and take under a minute.

```bash
python3 scripts/validate_repository.py     # expect: 12 skills, 0 errors, 0 warnings
python3 -m unittest discover -s tests      # expect: 200 tests, OK
python3 scripts/sync.py status             # expect: 0 issue(s)
python3 scripts/sync.py doctor             # expect: 8 [pass], 0 [FAIL]
npx skills add . --list                    # expect: 12 skills enumerated
```

Re-run at `84db88b` (PRs jonhill90/skills#113 and jonhill90/skills#114 merged): all five produce exactly that.

**Corrected 2026-08-23 — these expected values are stale, re-measure at
current HEAD before trusting them:**
- `validate_repository.py` no longer counts skills at all: agent-dotfiles#9
  (2026-08-10) removed the local `skills/` directory in favor of pinned
  `jonhill90/skills`/`jonhill90/skills-private` dependencies in `apm.yml`,
  so the validator now prints `Validated 0 skill(s): 0 error(s), 2
  warning(s)` (the two warnings say the orphan/description-token checks
  "cannot run: no local skills/") — not "12 skills, 0 errors, 0 warnings".
- `python3 -m unittest discover -s tests` currently runs **413 tests, OK**,
  not 200 — the count has grown substantially since this table was last
  measured.
- `npx skills add . --list` has no local `skills/` directory to enumerate
  from either, for the same #9 reason.
- `sync.py status`/`doctor`'s pass/fail counts describe deployed machine
  state under `$HOME`, which this document elsewhere correctly warns moves
  without a commit — not re-pinned here, just flagged as volatile.
An independent reviewer confirmed the same five at the previous commit with 198
tests; jonhill90/skills#114 added two. If your count is 200 and rising, that is expected.

### Two things in this repo spend Jon's money or change his machine

**`scripts/sync.py` has `apply` and `remove` as well as `status` and
`doctor`.** `status` and `doctor` only read. **`apply` rewrites files under
`$HOME` for all four harnesses** (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`,
`~/.copilot/AGENTS.md` and `copilot-instructions.md`, `~/.pi/agent/AGENTS.md`)
and `remove` reverses the recorded state. If `status` reports drift, **report it
to Jon — do not apply.** `install.sh` is the documented first-time deploy path
and is equally out of bounds unprompted.

**Eval runs cost money.** `scripts/measure_context.py` invokes all four CLIs;
anything under `tests/evals/harness/` drives real CLIs; a single scenario ×3 on
four columns is twelve billed agent sessions. Two reviewers ran
`measure_context.py` by accident last week — reportedly ~8 billed turns, which
is not something the repo records. **Get Jon's go-ahead before commissioning
runs.** Reading existing results in `tests/evals/results/` is free and is
usually enough.

## The one thing to understand before touching the evals

Every scenario reaches its verdict one of two ways, and the two fail
differently. This is the most useful thing in this file, and the first draft
overstated it — here it is with the numbers a reviewer could actually confirm.

| Method | Cases | How it fails |
|---|---|---|
| **Disk / execution** — read the fixture, run the code | `e06`, `e11`, `sd-c1`, `sd-c2`, `ftf-c1`, `sc-c1` | Instrument breaks loudly: blank verdicts, INVALID runs, false **FAIL**s. Caught, then re-run. |
| **Text** — read the terminal, match words | `e17`, `e18`, `e19` | False **PASS**es that survive, and they point toward the conclusion the matcher's author expected. |
| Disk-first, text fallback | `e20` (since jonhill90/skills#114), `ftf-c2` | — |

`e20` was converted by **jonhill90/skills#114**: it now returns PASS when `.agents/skills/` or
`skills-lock.json` exists in the fixture, and only falls back to the text
matcher for a run that looked and proposed without installing. That is the
pattern the rest of this section argues for, already demonstrated — copy it for
`e17`–`e19` rather than reinventing it.

Disk-scored cases have produced at least five recorded defects — defect 1
(`sd-c1`'s removal check), a missing `sd-c1` branch that left Pi's verdicts
blank, defects 23 and 24 which invalidated every `sc-c1` run, and defect 19
which scored two `e06` runs FAIL for the wrong reason. **They were all caught,
because a broken disk check produces obvious garbage.**

Text-scored cases produced the dangerous class: a matcher that hit Codex's
startup banner, a matcher that hit the checkout path (`Personal-Skills`), a
settle detector blind to three harnesses' spellings of "working", a prompt that
never arrived being scored as behaviour. Three of those produced false PASSes.

**Do not trust the defect totals.** Roughly 29 harness defects are recorded
across 2026-07-26/29, but the numbering does not reconcile: 5–7 are
double-assigned between E17 and E18, 20 and 21 are never defined, and one
running total is arithmetically wrong. Any figure derived from it — including
the "~12 text-method defects" the first draft of this file asserted — is an
estimate. What is solid and unanimous across every results file: **no defect
came from a skill.** All of them are in the measuring apparatus.

**Consequence for trust.** `safe-deletion` and `failing-test-first` rest on
disk-verified evidence — trust them. The three adopted instruction sentences
rest on text-matched evidence — treat them as provisional.

**The fix is not more matchers.** Redesign text-scored scenarios so the verdict
lands on disk. Two cases already do it: `sc-c1` scores *which skill got edited*,
not what the agent said about editing it, and `e20` scores whether an install
landed. `e17`–`e19` are the remainder.

Archiving transcripts was proposed as a workaround and withdrawn — it preserves
the weak method instead of replacing it, and would put 148 files carrying Jon's
email into a public repo. (The count and the email are from the withdrawn
proposal; the transcript directory is under `$TMPDIR` and no longer exists, so
neither is checkable now.)

## Deployed state, verified

Roster is flat — eight skills, no per-harness sections:

```
create-skill  failing-test-first  github-cli  linear
memory-conventions  obsidian  safe-deletion  tmux
```

**Stale as of 2026-08-10 (#9):** this repository no longer has a `skills/`
directory — skill content moved to `jonhill90/skills` (public) and
`jonhill90/skills-private`, consumed as pinned `apm.yml` dependencies. The
line below describing "twelve skills in `skills/`" describes the pre-split
layout; the count and the four opt-in names were not re-verified against
the new source repositories for this note.

Twelve skills existed in `skills/` before the split. Four were published but
deliberately out of the roster: `primer`, `close-the-loop`,
`dispatching-subagents`, `sanity-check`.

Static context (`measure_e15.py`) at `84db88b`:

```
claude   1932     codex   1932     copilot  2007     pi  2390     cap 8000
instr 1068 | skills 490 | plugin 0 | mem 374
```

**`measure_e15.py` reads the *deployed* files under `$HOME`, not the repo**
(`--home` defaults to `Path.home()`). So this table can move without any commit,
and it did: the same command read 1892/1892/1968/2350 earlier the same day, 40
instruction tokens lower, because the deployed copy was behind. If your reading
disagrees with this table, suspect deployment drift before suspecting the doc —
and check `sync.py status` rather than running `apply`.

**These numbers are a fraction of reality and §6 has not been reconciled.**
One live measurement exists (`docs/evals.md`, single run, 2026-07-29): **Pi
~3.8k, Claude Code ~24.7k, Copilot ~30.4k, Codex ~62.1k.** One run, no range —
the first draft of this file quoted four inflated figures and a range with no
source. Claude Code alone carries ~14 bundled skills (~1,758 tokens) the
disk-based script cannot see; `measure_e15.py` now prints a `NOT COUNTED ABOVE`
section naming its blind spots. Issue #5 carries the unresolved half: what §6
is actually for.

## Open work — as measured 2026-08-23, 14 open issues, one plausibly blocking

**Corrected 2026-08-23:** this table previously said "6 issues, none
blocking" and listed #5 as an open milestone. `gh issue list --repo
jonhill90/agent-dotfiles --state open` currently returns 14 open issues:
#1, #2, #3, #4, #6, #16, #44, #52, #57, #139, #266, #272, #281, agent-dotfiles#302 — and
#5 is closed (2026-08-11), not open. Notably agent-dotfiles#302 ("An unclaimed git stash
in the shared agent-dotfiles checkout blocks EVERY new lane in this
repo") reads as actively blocking, unlike the rest of this list. The table
below is not re-derived in full here (that needs its own pass reading each
issue); treat the "none blocking" framing as stale and re-check agent-dotfiles#302
specifically before relying on it.

| # | State | Honest read |
|---|---|---|
| jonhill90/skills#96 | closed 2026-08-03 | `name-only` is real — one of four `skillOverrides` values — and unbuilt. It optimises ~490 tokens while ~1,758 sit untouched behind `disableBundledSkills`. |
| #6 | parked | Rejected design for managing foreign skills. At least one of its five rejection arguments is undercut by this repo's own later finding that `npx skills use` does not install. Revisit trigger: a foreign skill actually landing. |
| jonhill90/skills#52–jonhill90/skills#55 | parked | Memory-design questions behind explicit triggers. Leave them. |
| agent-dotfiles#302 | open, not triaged here | Titled as actively blocking every new lane in the shared checkout — needs its own read, not covered by this handoff. |

**#5 and #6 were `jonhill90/skills#95` and `#97` until 2026-08-09**, when they
were transferred here. GitHub redirects the old numbers, so
`gh api repos/jonhill90/skills/issues/95` still answers — with *this*
repository's issue #5. That redirect is why the 2026-08-10 sweep read them as
open duplicates in two repositories (#28): it compared each issue to itself.
There is one copy of each, and it is here. Documents describing what was
decided in July may still name the old number as a historical referent; a
pointer to where the question lives *today* is #5 or #6.

Only #5 has comments — two, both measurements. Elsewhere, where this file says
"reviewers judged X", that is unrecorded conversation, not an artifact you can
go read.

Not on the tracker:

- **Stale figures across `docs/`** — plugin token counts from before two
  plugins were disabled, phase markers, superseded numbers. **jonhill90/skills#113 fixed a
  batch** (status lines, opt-in lists, case tables, and `docs/evals.md`'s
  live-context figures, which now read 3.8k/24.7k/30.4k/62.1k). How many remain
  is unknown: there is **no inventory and no checker**, and the "~40" this file
  once quoted was arithmetic on a round number. Build the list before quoting a
  count.
- **Redesign `e17`–`e19` to be disk-scored.** `e20` is done (jonhill90/skills#114); these three
  are the remainder, and they are the ones carrying the provisional
  instruction-sentence evidence.
- **Phase 3** (Windows/WSL, Linux) is unstarted; Jon has two Macs, so it is a
  solution without an instance today. `docs/PRD.md:114` also lists a Phase 4
  (curated public bundles), likewise unstarted.

## Decisions already made — do not re-litigate without new evidence

- **`sanity-check` is public opt-in, not roster.** It failed §10.1 rule 5
  (nothing enters the roster on credit): no skill-rung run of E18 exists on any
  column, and its counter-scenario runs are invalid (3 of 16). Putting it back is
  Jon's call, not an eval question. `SPEC.md:341`, `provenance-manifest.md:59`.
  Note that jonhill90/skills#114 added `tests/evals/counter/sanity-check.md`, so the
  counter-scenario is now *specified* — C1 tests whether the discipline changes
  the answer, not whether an opinion was sought. It has not been *run*. That is
  the measurement that would settle the skill's status, and it costs money.
- **`dispatching-subagents` rejected.** A targeted sentence beat it ×5 on E17
  (`SPEC.md:855`).
- **E19 rejected.** All four harnesses PASS ×2 unprompted; the scenario
  justified no component.
- **`tmux` beat five community candidates** and stays; three were cheaper. A
  sixth candidate failed to install and is recorded as unmeasured, not as a
  loss.
- **`ralph-loop` and `frontend-design` disabled**, ~352 tokens; `playwright`
  kept (MCP tools only, 0 static cost). The settings are deployed and
  `measure_e15.py` reports no plugins charged to Claude Code. The token saving
  itself can only be confirmed by a paid live measurement.
- Deletions (`az-devops`, `lint-agents`, `validate-skill`,
  `youtube-transcript`) are manifest rows and settled. See
  `docs/provenance-manifest.md` rather than re-deciding.

## What Jon actually asked for, and where it stands

He wants to use skills he does not author — public collections and private
sources — pulled in when a job needs them, without vendoring them here.

**Mechanically solved. Both commands verified to exist, with every name
checked** (`microsoft/azure-skills` resolves, 28 skills, all three named
skills present):

```bash
# public, project-scoped, pinned by content hash in skills-lock.json
npx skills add microsoft/azure-skills \
  --skill azure-prepare --skill azure-validate --skill azure-deploy \
  --agent '*' -y

# private — same command, any path or URL the machine can reach
npx skills add git@github.com:you/private-skills.git --skill internal --agent '*' -y
```

`$HOME` untouched; the install lands in `.agents/skills/` inside that project
only. The "~550 tokens" figure came from a hand-test and would need a reinstall
to re-confirm.

**Behaviourally one of four.** The E20 baseline is **8 FAIL out of 8** across
all four columns — not one run looked for an existing skill. (The prompt-delivery
guard added later that day would have made a re-scored baseline read 7 FAIL /
1 INVALID; jonhill90/skills#113 recorded that as a note on the results file, where it belongs.
The first draft of this handoff quoted the counterfactual as if it were the
measurement. The recorded result is 8 FAIL.) A sentence in the canonical
instructions fixed Claude Code (PASS ×3). Codex FAILs ×3 — re-measured after
defect 29, never quota-blocked, and jonhill90/skills#113 corrected the results file's old
"quota-blocked" header. Pi 1 of 3, Copilot unmeasured. The next rung is a
*targeted* sentence, which worked on E17 and E18 where a generic one did not —
and that is an eval run, so ask Jon first.

Two constraints found by hand-testing and recorded nowhere but here: vendor
collections are often **workflows, not menus** (`azure-deploy` refused to run
without two siblings), and **Pi gates project skills behind Project Trust**
(`pi --help` exposes `--approve`), appearing to ignore them non-interactively.

## Traps

- **A sibling checkout is named `Skills`, one directory over from this repo's
  `agent-dotfiles`.** Pre-split, this repository's own working path contained
  the word "Skills" (`…/Personal-Skills/…`), and any matcher touching that
  word matched it — that caused five false PASSes. Post-split, `Skills` is
  the checkout of the separate `jonhill90/skills` repository (#9), not this
  one, but the hazard is not gone: a matcher for "skills" can still hit that
  sibling directory's path, or this repo's own `settings/default-skills.txt`.
  Searching this repository's metadata for "Skills" finds nothing — the
  *repository* is `agent-dotfiles`.
- **A harness's startup banner is in the transcript.** `available skills`,
  `1. Yes, continue`, `Update Available` all appear before the prompt. Match
  the live tail, never the whole capture.
- **Codex 0.146.0 shows a trust dialog** and stays initialising after it is
  dismissed. `run.sh` now confirms the prompt reached the pane and retries; do
  not replace that with a fixed sleep.
- **APM's `--skill` filter does not prune.** A skill removed from the roster
  survives on disk until deleted by hand; `apm prune` removes packages, not
  skills.
- **`deep_merge` recurses into dicts but replaces lists.** Settings list keys
  are ownership-tracked for this reason; do not "simplify" it to a union.
- **Copilot reads two root files** — `AGENTS.md` *and*
  `copilot-instructions.md`, both marker-owned by APM (`SPEC.md:451`,
  `sync.py:50`), and `doctor` gates on both. The 2026-07-27 defect was narrower
  than "Copilot ignores AGENTS.md": the *overlay* was written only to
  `AGENTS.md`, so four runs measured a rule that was never in context. Do not
  delete either projection target.

## Rules earned the hard way — apply these, they cost real money to learn

- **Never widen a matcher toward the expected answer.** Read transcripts, or
  commission more runs with Jon's approval. This happened four times last week;
  once it flipped a genuine FAIL to PASS and nearly closed a milestone on a
  rigged measurement. `docs/evals.md` has the precedence rule: the scorer may
  under-detect, the transcript decides, and disagreement gets recorded rather
  than engineered away.
- **Verify a command runs before you publish it.** `npx skills use
  microsoft/skills@azure-naming` was in the README for a day: wrong package,
  invented skill name, and `use` only prints a prompt.
- **Cite only what exists.** `sanity-check` once cited a manifest and results
  files for anecdotes that lived in a commit message — and a *new*
  overstatement was introduced while fixing that.
- **"FAIL" here usually means a scenario is good.** Say which failures affect
  the user and which are the apparatus reporting on itself. Jon's repeated "is
  the system flawed?" was a reasonable response to a stream of FAIL reports
  about the measuring instrument.
- **Apply the evidence bar to the winner too.** §10.1 demoted `sanity-check`
  and was never applied to the sentence that replaced it, adopted at ×2 with a
  flapping column. Recorded in the manifest rather than resolved.
- **This file's own failure mode, twice over:** narrative numbers that drift
  toward the argument. Nine of them in the first draft, all in the flattering
  direction, in a document whose subject is that exact habit. Check the number
  against the source file, not against your memory of it.

## On the size of the eval apparatus

~4,620 lines of evaluation machinery govern ~346 lines of behavioural
configuration — a 13:1 ratio in a one-person repo, and three reviewers called
it disproportionate. `instructions/global.instructions.md`, arguably the
highest-leverage file here, is 90 lines and took 20 of 10,904 changed lines
last week.

**The counterweight, which the first draft omitted:** that apparatus is what
established the two behavioural skills this file tells you to trust, and what
caught every one of the defects listed above. It is also what would catch the
next one. Cutting it is a real option and it is **Jon's call, not a mandate you
inherit** — and note that this repo ships `safe-deletion` precisely because
agents arrive with deletion energy and act on it.

## Suggested first moves

1. **Re-run the five read-only verification commands.**
2. **Build the stale-figures inventory** — grep `docs/` for token counts, phase
   markers and defect totals, and diff each against its source. This is the
   only substantial task here that is unblocked, free, and specified. Start by
   reconciling `docs/evals.md`'s live-context figures against this file.
3. **Audit the four recent correction PRs** — jonhill90/skills#111 (nine claims) and jonhill90/skills#112
   (fifteen defects) = the 24 fixed on 2026-07-29, then jonhill90/skills#113 (stale status
   lines, opt-in lists, case tables) and jonhill90/skills#114 (E20 on disk, criteria for
   caseless scenarios). Three times last week a fix introduced a new defect
   nearby, and jonhill90/skills#113/jonhill90/skills#114 have had no adversarial read at all. This is free —
   read the diffs, not the behaviour.
4. **Then talk to Jon** about the eval apparatus and about whether `e17`–`e19`
   get redesigned before anything else is measured.

Ask Jon before: running any eval or `measure_context.py`, `sync.py apply` or
`remove`, `install.sh`, putting `sanity-check` back, setting
`disableBundledSkills`, changing `settings/`, or anything else that touches his
machine outside a fixture.
