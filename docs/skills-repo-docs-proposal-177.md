# Should `jonhill90/skills` carry docs? — agent-dotfiles#177

Proposal only — no docs written, no files moved. Findings for #177: what
`jonhill90/skills` should carry, using Matt Pocock's `mattpocock/skills` as
the concrete reference Jon named, rather than re-quoting #143's council at
him a second time.

## Correcting the premise this issue was opened to fix

#177 says the Director answered "why does `skills` have no docs?" by
quoting #143's council, and that this was wrong because #143 ruled on
*layout* (should `agent-dotfiles`'s `docs/` subdivide into
`architecture/decisions/product/runbooks/reference`), not on *whether
`skills` should have docs at all*.

That is not quite what #143 did. Reading
[`docs/docs-layout-council-138.md`](docs-layout-council-138.md) directly:
**Question 3 of that council was literally "Should `skills` /
`skills-private` have `docs/` at all?"**, and it answered **no, 12/12
unanimous**, for two independent reasons — the repo had just had a
harness-machinery `docs/` deliberately stripped from it
(`069e2c4`, 2026-08-09, "make this repository the standalone public skills
collection"), and no arm found evidence anyone would populate a fresh one.
So the Director's citation was on-topic; it was not a non-answer.

What makes this issue genuinely open anyway is that **Q3 itself named its own
reversal condition**, verbatim: *"it flips only if the repos start
accumulating documentation genuinely native to a skill collection (not
harness machinery) that no longer fits in `README.md`/`AGENTS.md`."*
Matt Pocock's `skills` repo is exactly that class of evidence — a real,
external, populated example of docs native to a skill collection — and it
did not exist as input to the council. That is the correct scope for this
issue: **test Q3's reversal condition with the evidence Jon supplied**, not
relitigate Q4 (the five-way layout split), which stays out of scope per
#177's own constraint and stays decided for `agent-dotfiles`/`agent-evals`.

## 1. What `mattpocock/skills` actually has

Repo: [`github.com/mattpocock/skills`](https://github.com/mattpocock/skills).
Structure, read directly from the tree (`gh api
repos/mattpocock/skills/git/trees/main?recursive=1`), not from reputation:

```text
AGENTS.md / CLAUDE.md      # authoring + repo policy (symlink pair, same as agent-dotfiles)
README.md                  # pitch, install, "why these skills exist," full skill index
CONTEXT.md                 # shared vocabulary doc (the pattern the skills themselves teach)
.agents/
  writing-docs.md          # the docs-page template + when to write one (authoring material)
  invocation.md            # user-invoked vs. model-invoked mechanics
  install-block.md         # canonical install wording, quoted verbatim elsewhere
  adr/0001-*.md, 0002-*.md # two dated decision records
.claude-plugin/
  plugin.json, marketplace.json   # Claude Code plugin packaging
skills/
  engineering/<name>/SKILL.md     # 13 skills
  productivity/<name>/SKILL.md    # 7 skills
  misc/, in-progress/, deprecated/<name>/SKILL.md   # not promoted, no docs
  engineering/README.md, productivity/README.md     # per-bucket index
docs/
  engineering/<name>.md    # one file per *promoted* engineering skill
  productivity/<name>.md   # one file per *promoted* productivity skill
```

Two things stand out immediately, both verifiable from the tree above:

- **`docs/` holds exactly one audience.** Every file under `docs/` is a
  human-facing page about *using* a skill — nothing about how to author one.
  `docs/engineering/code-review.md`
  ([raw](https://github.com/mattpocock/skills/blob/main/docs/engineering/code-review.md))
  is representative: `## What it does`, `## When to reach for it`, `##
  Prerequisites`, a free-form middle section, `## Common questions`, `##
  It's working if`, `## Where it fits`. 94 lines. It never reproduces
  `SKILL.md`'s steps, never explains frontmatter, never says how to write a
  new skill.
- **The authoring material — the audience this issue is told to keep
  separate — is not in `docs/` at all.** It is in `.agents/writing-docs.md`
  ([raw](https://github.com/mattpocock/skills/blob/main/.agents/writing-docs.md)),
  a 96-line spec covering exactly this: the docs-page template, the
  section-by-section bar each part has to clear, when a page is required vs.
  skipped (only the `engineering/`/`productivity/` buckets get one — `misc/`,
  `in-progress/`, `deprecated/` do not), and how to hunt for real "Common
  questions" instead of inventing them. `AGENTS.md`
  ([raw](https://github.com/mattpocock/skills/blob/main/AGENTS.md)) states
  the same split as repo policy in one paragraph and points into
  `.agents/writing-docs.md` for the mechanics.
- **Depth is deliberately shallow and templated, not a sprawling reference
  tree.** One file per promoted skill, ~60–95 lines, same seven-section
  shape every time. No nested subcategories, no nesting deeper than
  `docs/<bucket>/<name>.md`. Only 20 of the repo's skills get a page at all
  (`engineering/` + `productivity/`); `misc/`, `in-progress/`, and
  `deprecated/` are explicitly excluded — the boundary is "promoted for
  external use," not "every skill in the repo."
- **The pages are republished externally, not just read in-repo.**
  `docs/engineering/code-review.md`'s content is what renders at
  `https://aihero.dev/skills-code-review` — the docs page is written for a
  browser reader deciding whether to install a slash command, with every
  link absolute (`writing-docs.md`: "a relative link that works in the repo
  breaks once published").

So the honest one-line summary: **`mattpocock/skills` has docs because it
has an external site to feed, and those docs are 100% "should I reach for
this skill" content — the authoring contract lives next to `AGENTS.md`, not
inside `docs/`.**

## 2. What a person landing on `jonhill90/skills` cold cannot answer

Current state, read directly (`gh api
repos/jonhill90/skills/git/trees/main?recursive=1`): 24 skills under
`skills/`, `AGENTS.md`/`CLAUDE.md` (authoring contract + repo policy),
`README.md`, `scripts/`, `tests/`, no `docs/`.

Two gaps, one of them evidence the other already exists in practice:

- **The README's own skill table is already stale, independent of any docs/
  decision.** `README.md`'s "Skills in this collection" table lists 13
  skills. The repo has 24: `ask-a-council`, `distill`, `keep-me-honest`,
  `loop-contract`, `loop-memory`, `mine-transcripts`, `notify`, `prd`,
  `spec`, `tdd`, and `verify-the-instrument` — eleven skills, nearly half
  the collection — are not in the index at all. A person landing on the
  README cannot discover that these skills exist, let alone what they do or
  when to reach for them. This is not a hypothetical failure mode Pocock's
  repo protects against; it has already happened here, in the one file that
  currently plays index.
- **Nothing distinguishes user-invoked from model-invoked skills, or says
  when to reach for one sibling over another.** `mattpocock/skills`' README
  and each bucket `README.md` split every entry into **User-invoked** /
  **Model-invoked**, because a user-invoked skill is invisible to the agent
  — a human is the only index that remembers it exists. `jonhill90/skills`
  makes no such split anywhere at the collection level; that classification
  currently lives only inside each skill's own `description` frontmatter
  (per `AGENTS.md`'s "Skill Authoring" section), which means finding out
  requires opening all 24 `SKILL.md` files. Concretely unanswerable today
  without doing that: is `sanity-check` something you type, or something
  the agent reaches for on its own — and how is it different from
  `dispatching-subagents` or `keep-me-honest`, three skills whose names
  alone suggest overlapping moments to reach for them? `mattpocock/skills`
  answers exactly this shape of question in `## When to reach for it` on
  every page, with a table for anything that branches (`writing-docs.md`:
  "branches go in a table or a list, never in a paragraph").

## 3. The two audiences, and the real cost of moving one of them

Reference's split, restated precisely because #177 asks me not to conflate
them:

| Audience | Reference's home | Content |
|---|---|---|
| **Using** a skill | `docs/<bucket>/<name>.md`, published externally | what it does, when to reach for it, prerequisites, common questions, "it's working if," where it fits |
| **Authoring** a skill | `.agents/*.md` + `AGENTS.md` | the docs-page template itself, frontmatter/invocation mechanics, ADRs, install wording |

`jonhill90/skills` already has an authoring-contract home: `AGENTS.md`'s
"Skill Authoring" section (name/directory match, frontmatter fields, the
500-line cap, `references/`, imperative instructions, model- vs.
user-invoked classification). That is functionally the same placement
Pocock uses — repo policy plus a `.agents/`-style adjunct, not `docs/` — it
is just merged into one file rather than split into `AGENTS.md` +
`.agents/writing-docs.md`. **Adding a "using" `docs/` tree does not require
moving anything.** The authoring-vs-using split this issue is worried about
conflating is already structurally intact today: `AGENTS.md` owns authoring,
nothing currently owns using.

The real, distinct decision this repository would face — separately from
Pocock's precedent — is `create-skill` and the SPEC material that live in
`agent-dotfiles`, not `jonhill90/skills`. Those are the generic,
harness-portable "how to author any Agent Skill" instructions; they are one
level more general than `jonhill90/skills`' own repo-specific `AGENTS.md`
section, the same way a style guide differs from a single project's lint
config. Moving `create-skill`/SPEC content into `jonhill90/skills` would:

- duplicate authoring guidance that already exists generically in
  `agent-dotfiles` and is meant to travel to *other* people's skill repos,
  not just this one — `jonhill90/skills`' `AGENTS.md` already explicitly
  scopes itself as "this repository's" authoring rules and leaves the
  general skill-format contract to the spec `create-skill` teaches;
- couple a **public** repository's authoring contract to a **private**
  personal-harness repository's canonical instructions, inverting the
  dependency direction `agent-dotfiles`' own `CLAUDE.md` states today
  ("Skill content is not vendored here … declared as pinned dependencies");
- gain nothing Pocock's example actually asks for — his `.agents/` material
  is scoped to *his* repo's own conventions (his triage labels, his ADR
  format), not a portable authoring spec, so it is not evidence for
  centralizing `create-skill` anywhere.

**Recommendation: do not move `create-skill`/SPEC.** The audience split
Pocock demonstrates is satisfiable entirely within `jonhill90/skills`
as it already stands (`AGENTS.md` = authoring, a new `docs/` = using); moving
the generic authoring material is a different, larger, and currently
uncosted decision this issue should not fold in.

## 4. Concrete recommendation

1. **Fix the README table first, independent of everything else.** Eleven
   skills are missing from the index today. This is a pure bug, not a docs
   architecture question, and it is the cheapest evidence available that a
   "using" index needs upkeep discipline regardless of where it lives.
2. **Add `docs/<name>.md` per skill** (flat — `jonhill90/skills` has no
   bucket structure to mirror, unlike Pocock's `engineering/`/
   `productivity/` split), scoped to *using* only: what it does, when to
   reach for it (with a table against confusable siblings, e.g.
   `sanity-check` vs. `dispatching-subagents` vs. `keep-me-honest`), and
   where it fits relative to neighbors. Skip `## Common questions`/`## It's
   working if` until there is real evidence to fill them — Pocock's own
   rule (`writing-docs.md`: "sized to what it found, not padded") argues
   against writing a fixed seven-section template for 24 skills with zero
   observed questions behind most of them. Grow those two sections only
   where an issue, a repeat question, or a changelog entry earns them.
3. **Leave `AGENTS.md` as the authoring home**, unsplit into a `.agents/`
   subdirectory — `jonhill90/skills`' authoring section is currently 25
   lines inside a 158-line file; Pocock split his out because his `.agents/`
   holds four separate documents plus ADRs. Revisit only if the authoring
   section grows enough to crowd `AGENTS.md`'s other sections, mirroring
   #143 Q3's own reversal condition applied one level down.
4. **This reopens #143 Q3, explicitly, not Q4.** Q3's "no docs/" verdict
   was correct for the repo's 2026-08-09 state and is being revisited here
   because its own stated condition — genuinely native, non-harness content
   that outgrows `README.md`/`AGENTS.md` — is now demonstrably met by an
   external precedent Jon named. Q4 (the five-way `architecture/decisions/
   product/runbooks/reference` split) is untouched: nothing above proposes
   subdividing `jonhill90/skills`' new `docs/` tree, and Pocock's own
   `docs/` is flat-per-bucket, not five-way.

## 5. Agent Plugins — one paragraph, not a recommendation

The [Agent Plugins spec](https://github.com/microsoft/agent-plugins),
published 2026-08-06 and backed by Microsoft, GitHub, OpenAI, AWS, Cursor,
and Vercel, defines a portable package format built on exactly the
`skills/<name>/SKILL.md` layout `jonhill90/skills` already uses;
Pocock's repo demonstrates the delta concretely — it adds
`.claude-plugin/plugin.json` and `marketplace.json`, and records *why*
Claude-first in a dated ADR
([`.agents/adr/0002-ship-as-a-claude-code-plugin.md`](https://github.com/mattpocock/skills/blob/main/.agents/adr/0002-ship-as-a-claude-code-plugin.md))
rather than silently picking one harness. This is adjacent to the docs
question only in that a public repo choosing to describe itself to the
outside world (this proposal) and a public repo choosing to package itself
for the outside world (plugin manifest) are the same posture applied to two
different files. **Not proposed here** — it is a separate, larger decision
with its own packaging and CI cost that #177 did not ask this document to
carry.

## What this document does not do

- It does not move any file, write any `docs/<name>.md` page, or touch
  `jonhill90/skills` at all — that repository is not this repository, and
  #177's own constraint is proposal-then-react, same as #143.
- It does not reopen #143 Q4 (the five-way layout split) for
  `agent-dotfiles` or `agent-evals` — those stay flat, unchanged.
- It does not implement Agent Plugins packaging.
