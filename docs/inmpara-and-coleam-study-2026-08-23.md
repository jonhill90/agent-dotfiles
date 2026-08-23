# Second Brain, read broadly, and coleam00/skills, mined for gems — build-5

A study, not a migration. Nothing in Jon's vault was moved, renamed, or
rewritten — every number below comes from `find`/`grep`/`python3` run
read-only against the live vault and a fresh clone, or from a file actually
opened. Where a question could not be settled this way, it says **could not
measure** rather than filling the gap.

## Job 1 — the Second Brain, read broadly

Vault root: `iCloud~md~obsidian/Documents/Second Brain/`. 641 `.md` files
total (measured with `find`), 625 of them (97.5%) carry YAML frontmatter.

| Folder | `.md` files | Frontmatter | Notes |
|---|---:|---:|---|
| `00 - Inbox` | 30 | 27/30 | `00c - Clippings`, `00e - Excalidraw` subfolders |
| `01 - Notes/01a - Atomic` | 15 | 15/15 | |
| `01 - Notes/01d - Daily` | 117 | 117/117 | |
| `01 - Notes/01m - Meetings` | 98 | 98/98 | |
| `01 - Notes/01r - Research` | 163 | 163/163 | |
| `01 - Notes/01s - Samples`, `01t - Thoughts` | 0, 0 | — | subtype folders exist, unused |
| `02 - MOCs` | 27 | 27/27 | |
| `03 - Projects` | 42 | 42/42 | mostly under `03b - Personal`, `03c - Work` (Gentiva) |
| `05 - Resources` | 132 | 132/132 | 123 of 132 are `05c - Clippings` |
| `06 - Archive` | 0 | — | folder exists, genuinely empty |
| `99 - Meta` | 12 | mixed | templates + one guide doc |

`04 - Areas` and `06 - Archive` measured directly, not assumed: `04 - Areas`
has two subfolders (`04e - Entertainment`, `04t - Technology`) and **zero**
`.md` files in either (`find … -name '*.md' | wc -l` → 0, confirmed twice);
`06 - Archive` has no entries at all besides `.` and `..`. Both are in fact
unused, not merely under-linked.

### Filenames vs numeric IDs — mixed, and the split falls on subtype

The brief's premise ("named by title; an earlier second brain used numbers")
does not hold uniformly — it holds for **some** subtypes and not others,
measured per folder:

- **Numeric-ID-named, 100% of the folder:** `01a - Atomic` (15/15),
  `01d - Daily` (117/117), `01r - Research` (163/163) — filenames are bare
  `YYYYMMDDHHMM.md`. The human-readable title lives one line into the file,
  as an `# <id> - <Title>` H1, not in the filename.
- **Title-named:** `02 - MOCs` (`AI.md`, `Azure.md`), `03 - Projects`
  (`Project Personal DotFiles.md`), `05 - Resources` (source titles).
- **Hybrid:** `01m - Meetings` — `Meeting <id> <Title>.md`, 0/98 pure-numeric
  (id embedded but title always present in the filename too).

So 295 of 393 files in `01 - Notes` (75%) are numeric-ID-only at the
filename level; the other three top-level folders are title-named. The
"earlier system used numbers" framing undersells it — the numeric
convention is still live today, confined to three Notes subtypes.

### MOCs — links only, thin prose, a fixed template, and stale

27 MOC files, one per domain (`AI.md`, `Azure.md`, `Kubernetes.md`, …), each
following the same template (`## Overview`, `## Notes`, `## MOCs (Related)`,
`## Projects`, `## Areas`, `## Resources`). Measured word counts and
wikilink counts per file (full table generated, range shown):

- Largest: `Azure.md` (852 words, 84 wikilinks), `Meetings.md` (668 words,
  85 wikilinks), `Cloud Adoption Framework.md` (357 words, 30 wikilinks).
- **8 of 27 (30%) are empty stubs**: `Command Line Tools.md`, `Docker.md`,
  `GitOps.md`, `Monitoring.md`, `Neovim.md`, `Prompt Engineering.md`,
  `Semantic Kernel.md`, `Terraform.md` — each ~47 words, 0 wikilinks
  (frontmatter + a bare heading skeleton, nothing filled in).
- `Agents.md`, despite existing, still carries the unfilled template
  placeholder text `[2-3 sentences describing this knowledge cluster]`
  verbatim under `## Overview`, and its `## Notes` section is empty — it is
  the template, not a populated MOC.

**Coverage of the Notes folder is partial, measured, not assumed.** Across
all 27 MOCs there are 457 total wikilinks (327 unique targets); 130 of those
457 are raw numeric-ID links (e.g. `[[202506222021]]`) pointing at Notes
files, 114 of them unique. Against 295 numeric-ID Notes files that exist,
114/295 = **39% are linked from any MOC**; the remaining 61% are reachable
only by folder browse or full-text search.

**Staleness, measured against each MOC's own `updated:` frontmatter field:**
`Azure.md` → `2025-06-21`, `AI.md` → `2025-06-21`, `Governance.md` →
`2025-06-22`, `Meetings.md` → `2025-07-05`. None of the four checked has
been touched since its creation date. Meanwhile Daily notes run through
`20260811.md` and Meeting notes through `Meeting 202509300900 …` — over a
year of continued vault activity the MOC layer never recorded. `Meetings.md`
links 85 of the 98 meeting files that exist today (87%), which is
respectable coverage for a file its author stopped updating fourteen months
ago — it was current once, at 100% or close to it, and has not been
maintained since.

**Links carry no title for a plain-text reader.** A raw `[[202506222021]]`
in a MOC is opaque outside Obsidian's UI (which resolves the note's H1 as a
hover preview); a tool reading the file as text — an agent — sees only the
digits and must open the target to learn what it is. Title-named links
(`[[Project Gentiva AI Governance Policies]]`) carry the answer in the link
text itself. This split is invisible to Jon because Obsidian papers over it;
it is not invisible to an agent.

### `99 - Meta` — templates plus one large, partly stale operating guide

12 files: 7 Templater templates (`daily-template.md`, `meeting-template.md`,
`moc-template.md`, `note-template.md`, `project-template.md`,
`process-clipping.md`, `process-research.md`), 2 CSS-class reference notes,
and one long guide, `Working with Jon's Second Brain - Complete Claude
Guide.md` (306 lines) — a hand-written operating manual for an AI assistant
working in the vault (folder paths, naming rules, frontmatter shapes,
tagging philosophy).

The guide is itself evidence of drift: it states "245 Files" and per-folder
counts current when written (`01 - Notes (72 files)`, `05 - Resources (119
files)`); measured today, `01 - Notes` alone is 393 files and `05 -
Resources` is 132 — the vault has grown roughly 2.6x since the guide's
snapshot and the guide was never updated to match. It also documents an MCP
stack (`basic-memory-mcp`, `openmemory-mcp`, a containerized `vibes`
workspace) as the live interface to this vault; **could not measure**
whether that stack is still running today — nothing in the vault itself
confirms or denies it, and checking would mean inspecting Jon's live MCP
config, out of scope for a read-only vault study. The templates directory
itself is current — it directly matches the frontmatter shapes actually
found in Daily/Meeting/MOC files.

### Tags — decorative for navigation, not load-bearing

1,044 distinct tag values across 599 of 636 tagged files (94%). Top values
by frequency mix two kinds, exactly as the Meta guide describes: content-type
("structural") tags — `review` (181), `note` (158), `research` (147),
`clippings` (135), `resource` (125), `daily` (114), `meeting` (98), `moc`
(30) — and topic/association ("synaptic") tags — `#ai` (87), `#azure` (81),
`#drawings` (37), `#cloud-adoption-framework` (25).

The vault's only query mechanism found (`grep`'d across all files) is the
Obsidian Tasks plugin, used in the Daily template:

```
filter by function task.file.folder === "01 - Notes/01d - Daily/"
```

That filter keys on **folder path**, not on any tag. No Dataview or Tasks
query anywhere in the vault was found filtering by tag. Combined with the
finding above (MOCs are hand-curated wikilink lists, not tag-driven views),
tags in this vault are metadata Jon reads while browsing, not a retrieval
mechanism anything actually queries against. Decorative, measured, not a
vibe.

### Progressive disclosure — tested on three real questions

1. **"What has Jon captured about governing AI workloads on Azure?"** →
   `Governance.md` MOC. Its `## Resources` and `## Projects` sections are
   title-named (`Governance recommendations for AI workloads on Azure -
   Cloud Adoption Framework`, `Project Gentiva AI Governance Policies`) —
   **the MOC alone answered the question**, no full-text search needed. Its
   `## Notes` section, though, is 5 raw numeric IDs — those five stay opaque
   without opening files.
2. **"What has Jon thought about multi-agent orchestration?"** →
   `Agents.md` MOC. Unfilled template (`## Overview` placeholder text
   verbatim, `## Notes` empty). **Dead end** — would require full-text
   search or a folder browse of `01r - Research`, exactly the fallback a MOC
   is supposed to make unnecessary.
3. **"Has Jon met about Zerto or IaC reviews recently?"** → `Meetings.md`
   MOC. Title-named links surfaced `Meeting … Knowledge Transfer Session
   Zerto` and multiple `IaC Review` meetings by name alone — **answered**,
   but only through `2025-07-05`; three later Zerto/IaC meetings exist in
   `01m - Meetings` (through September 2025) that this MOC, frozen since
   July, does not know about. The map was enough for what it recorded; the
   record itself had stopped growing.

Score: 1 clean success, 1 clean failure, 1 partial success bounded by
staleness — not "MOCs work" or "MOCs don't," but "MOCs work exactly as far
as they were filled in and exactly as recently as they were touched," which
this vault's own numbers show is inconsistent file-to-file.

### What we should steal — Job 1 (corrected after the devils-advocate pass; see below)

- **Keep title-named entry points for unique things; don't assume title
  alone is sufficient for a recurring note type.** For a one-off resource
  or project, a title-named link is enough on its own. For a recurring type
  (a weekly meeting, a repeated review), the disambiguating value has to be
  present too — embedded in the label (`"<Label> <id>"`, the vault's own
  Meetings pattern) or carried by the link, not dropped. This repo's
  `docs/*.md` are all one-off, title-unique documents, so nothing changes
  here today — but a future MOC-style index over something recurring (a
  log, a run history) should carry the disambiguator, not just a title.
- **Nothing else survives.** Numeric-ID-only filenames, the tag taxonomy,
  the MOC template itself, and the one-big-operating-guide pattern all
  failed the "does an agent get anything a human wouldn't already have"
  test — see the devils-advocate pass for the evidence on each.

## Job 2 — mining coleam00/skills for logic-gems

Cloned fresh: `git clone https://github.com/coleam00/skills` →
`/Users/jon/source/repos/skills-research/coleam00-skills`. **License: MIT**
(`LICENSE`, Cole Medin, 2026) — permissive, reuse and reimplementation both
clear, not merely study-only.

`cole-medin-ai-coding` (same author, already checked out alongside it) has
**no `LICENSE` file anywhere in the tree** (checked at root and
recursively) — that repo is study-only, full stop, per the brief's own
rule. Its one directly relevant artifact, `concepts/the-piv-loop.md`,
documents "Plan → Implement → Validate" as Cole's core operating
discipline; the `coleam00-skills` `piv-*` skill family (`piv-plan-
implementation`, `piv-implement`, `piv-review-changes`, `piv-validate`, …)
is that concept operationalized as a skill set, and shares its vocabulary —
confirming the brief's expectation that the two repos share conventions.

Five gems worth naming as mechanisms (not topics), each checked against
what this repository already has:

1. **State vs. event, replace vs. append** (`second-brain-audit`). Every
   stored fact is either a current value that must be *replaced* on update,
   or a timestamped happening that must be *appended*; conflating the two
   is named as the specific rot mechanism ("the write path can only
   append"). **We already have this**: `docs/memory.md` — "Each fact owns
   one concept and is updated in place rather than duplicated" — is the
   same rule, independently arrived at. No gap.
2. **Empirical A/B ablation of the AI-instructions layer**
   (`ablate-ai-layer`). Runs the same real task multiple times with
   CLAUDE.md/AGENTS.md intact and with it stripped, in throwaway git
   worktrees, and grades each rule by what actually changed — rather than
   pruning a rules file by reading it and guessing what's dead weight. We
   do not have this. It is the direct instrument this repo's own
   "Recording Figures" discipline (measured vs. inferred) is missing for
   its own steering files: right now a stale-CLAUDE.md claim is caught by
   a human noticing drift, not by a run that proves the rule still changes
   behavior.
3. **Diff-scoped rules-file drift check** (`rules-check-drift`). Checks a
   rules file against a specific diff range for three narrow failure
   modes only — a now-false stated fact, a drifted "where things live"
   pointer, a new invariant the change just introduced — and refuses to
   flag anything else (explicitly not a changelog generator). We do not
   have an automated version; this repo's CLAUDE.md is kept honest by
   convention and PR review, not a check. Narrower and cheaper than
   ablation (#2); the two are complementary, not redundant — drift-check
   catches "this line is now false," ablation catches "this line was
   never load-bearing."
4. **N-way worktree fan-out with a single throwaway integration branch**
   (`worktree-create` + `worktree-merge`). Creates any number of isolated
   worktrees in parallel (detected install/config/health-check, not
   hardcoded), then integrates them one at a time through one disposable
   branch with a test run after every merge, so a break is localized to
   the branch that caused it and the main line is never touched until
   everything passes. This repo's `EnterWorktree` tool covers the
   single-worktree case; it has no equivalent for **coordinated** parallel
   worktrees or a safe multi-branch merge order — relevant given this
   repo's own multi-lane `Author-Lane: estate:N` convention already runs
   several worktrees at once by hand.
5. **Reactive-or-proactive scan mapped onto a fixed primitive palette**
   (`opportunity-scan`). Same skill, two entry points: point it at one
   run's failure artifacts ("what would have prevented this specific
   thing") or at a window of session logs ("what do I keep doing by hand
   that should be encoded") — and every finding is forced into one of six
   named primitives (rule / skill / hook / subagent / MCP / automation),
   never left as a vague suggestion. This repo's `mine-transcripts` skill
   covers the proactive half only (vocabulary mining for skill candidates)
   and has no reactive ("this run just failed, what should change") mode
   and no forced primitive classification step — both are gaps, not
   duplication.

Not counted as gems: `ast-grep` and `skills-create` are close analogs of
capability this repo/toolchain already has by other means (structural
search via existing tools; `create-skill` for skill authoring) —
**could not measure** whether `skills-create`'s specific "classify skill
type before applying rigor" step is something `create-skill` already does,
since `create-skill`'s content lives in `jonhill90/skills`, not in this
checkout, and reading it was out of scope for this study.

### What we should steal — Job 2 (corrected after the devils-advocate pass; see below)

The mechanisms are worth having somewhere in the estate; none of them are
worth *building in this repository*, by this repository's own written
product boundaries. Recommended, not adopted — placement is this list's
main correction from the first draft:

- **Ablate the AI-instructions layer empirically** (#2) — the mechanism
  (throwaway-worktree A/B, grade rules by measured behavior change) is eval
  methodology; this repo's own CLAUDE.md assigns that to the private
  `jonhill90/agent-evals` repository, not here (#10).
- **A diff-scoped CLAUDE.md/AGENTS.md drift check** (#3) — this is skill
  content (a check triggered by a description, same shape as every other
  skill in the estate); authoring it belongs in `jonhill90/skills`, never
  in this repository (#9). This repo's role, if it's ever wanted here, is
  to roster it once it clears the §10.1 evidence bar — not to write it.
- **Coordinated N-way worktree merge with one integration branch** (#4) —
  multi-lane coordination logic is exactly what this repo already
  extracted, on purpose, into `jonhill90/agent-supervisor` (#179); building
  a new version of it back into agent-dotfiles risks re-growing the
  coupling that split was written to remove.
- **A reactive entry point and a fixed primitive-palette classification**
  near `mine-transcripts` (#5) — also skill content, also `jonhill90/skills`
  territory, and specifically that skill's own repository's call to make
  (its rostering is already tracked at `jonhill90/skills#137`).
- State-vs-event (#1): nothing to steal, already held — recorded here so
  the next reader doesn't re-derive it.

## Devils-advocate pass on both "what we should steal" lists

The `devils-advocate` skill was invoked directly against both lists (not
self-reviewed) with the brief's exact objection as the attack brief:
*INMPARA works for a human with years of context reading his own notes; an
agent has neither. Which patterns survive that difference, and which are
load-bearing only because Jon remembers what he meant?* — plus a second
attack: does the Job 2 list actually fit *this repository's* stated
boundaries, or does it belong somewhere else in the estate? Both landed
real, evidence-backed hits; both lists below are corrected from the first
draft as a result.

**Job 1's survivor is weaker than first drafted.** The opposing case
checked the "title alone is enough" claim against a wider sample than the
three test questions and found a real counter-example: 15 separate meeting
files share the title pattern `IaC Review Meeting`, distinguished *only* by
the numeric timestamp embedded in the filename (`Meeting 202506240900 IaC
Review Meeting.md` through `Meeting 202509300900 IaC Review Meeting.md`,
confirmed by `find … -iname "*IaC Review*"`, 15 hits). "Has Jon met about
IaC reviews recently" resolves fine from `Meetings.md`, but "which IaC
review meeting was on 2025-07-15" does not resolve from the title text
alone — the disambiguating value is the ID, not the title. So the
corrected finding is: title-named links help an agent exactly where names
are unique (`Governance.md`'s resource list, all distinct titles); for a
**recurring** note type, the embedded ID is still load-bearing, just
relocated from filename-as-ID into filename-as-`"<label> <id>"`. The
original "steal title over ID" framing overstated a clean either/or that
this vault's own Meetings folder doesn't actually practice.

Separately, and unopposed: this repo's Job 1 output produced **no new
practice to adopt**, only a confirmation that agent-dotfiles' existing
title-named `docs/*.md` convention shouldn't change, plus a caution against
copying the MOC template (8 of 27 stub, all four checked stale over a
year — a human tolerates that because they remember what's missing; an
agent hitting an empty `Agents.md` MOC has no such fallback and stops
cold, exactly what Question 2 of the three-question test showed). Labeling
"don't change anything" as a "steal" list entry is generous; it is kept
here because the brief asked for the list, not because it is an action
item.

**Job 2's list failed the scoping attack outright — three of its four
items do not belong built in this repository, by this repository's own
written rules, not by the opposing case's opinion:**

- `ablate-ai-layer` (#2, empirical A/B ablation) is, mechanically, exactly
  the class of thing this repo's own CLAUDE.md assigns elsewhere: "Behavioral
  scenarios, counter-scenarios, harness runners, results and transcripts,
  scoring and arming tools, and eval methodology belong to the private
  jonhill90/agent-evals repository, not here" (§Product Boundaries). Running
  the same task N times with the layer stripped and grading rules by
  measured behavior change *is* eval methodology. Building it here would
  re-create the exact split #10 already drew a line against.
- The drift-checker (#3, `rules-check-drift`) and the `mine-transcripts`
  extension (#5) are both, in substance, skill content — a check or a
  scan an agent runs, triggered by a description, shaped like every other
  skill in this estate. This repo's own rule is explicit and does not carve
  an exception for "but this one's small": *"Authoring a skill's content
  happens in `jonhill90/skills` (public) or `jonhill90/skills-private`
  (private) — never in this repository (#9)."* `mine-transcripts` in
  particular is already a benched skill whose own rostering is governed by
  `jonhill90/skills#137` — extending its scope is that repository's
  decision to make, not a docs recommendation landed here.
- The N-way `worktree-create`/`worktree-merge` pattern (#4 in the original
  numbering) is coordination logic across multiple parallel lanes — the
  same shape of problem this repo already extracted, on purpose, as
  `jonhill90/agent-supervisor` (#179, "the tmux-lane supervisor core
  previously lived at `scripts/supervisor/`… it moved"). Building a new
  multi-worktree orchestration mechanism back into agent-dotfiles risks
  re-growing the coupling #179 was written to remove.
- Only the underlying **mechanisms** survive the objection — state-vs-event
  (already held, no gap), and the *idea* that ablation/drift-check/reactive-
  scan are worth having *somewhere* in the estate. What does not survive is
  "build them here." Corrected placement: `ablate-ai-layer`'s mechanism is
  an `agent-evals` candidate; the drift-checker and the `mine-transcripts`
  extension are `jonhill90/skills` candidates; the worktree-coordination
  mechanism, if built at all, is an `agent-supervisor` candidate. This
  repository's own documented role for all three is narrower than "build
  it": *rostering* a skill once it clears the §10.1 evidence bar elsewhere,
  never authoring it here.

No opposing case was found against state-vs-event (Job 2, item 1) — it is
already held, there is nothing to attack. The N-way worktree item is the
one place the human-vs-agent objection genuinely does not apply (it is pure
merge-ordering mechanics, not a memory question) — worth recording so a
future reader does not assume every item here needed to clear that
specific bar; it still fails the separate scoping attack above.

## Boundaries observed

Read-only against the vault throughout — no file in Jon's Second Brain was
moved, renamed, or edited by this study. The memory storage/format decision
stays reserved to Jon; nothing above recommends adopting a specific tool or
format, only which mechanisms are worth reimplementing and which aren't.
No chat content is quoted verbatim anywhere in this document, its commit,
or its PR.

## Docs index

This repository's `docs/` is flat and has no `index.md` (confirmed by
direct search — no file of that name exists anywhere under `docs/`, and no
other file in this repo enumerates `docs/*.md` as a table). This document
is filed at `docs/` top level, matching every other doc in this directory
(`docs/PRD.md`, `docs/SPEC.md`, `docs/memory.md`, …); there is no index for
it to be added to.
