# Docs Layout Council — agent-dotfiles#138

Findings for #138: whether `docs/{architecture,decisions,product,runbooks,reference}` —
the layout `jonhill90/Hill90` accreted while an agent built that repo one file
at a time — should be adopted anywhere in `agent-dotfiles`, `skills`,
`skills-private`, or `agent-evals`. Raw batch data:
[`docs/research/docs-layout-council-138/`](research/docs-layout-council-138/).

**This document's own location is part of its answer.** It sits flat at
`docs/`, not in a subdirectory, because that is what the evidence below
supports for a repo this size — see §4. If you disagree with §4 after reading
it, this file is misplaced and that is itself informative.

**This PR also recreates `docs/research/`** — the exact directory class whose
2026-07-13 deletion is cited below (§4) as the strongest evidence for staying
flat. That is a real tension, not a technicality, and it does not resolve
itself: the raw batch data has to live somewhere, and it is not living
documentation, so it does not belong in flat `docs/` next to `PRD.md` and
`SPEC.md` either. The resolution is in the difference between what
2026-07-13 removed and what this adds. The 2026-07-13 `docs/research/` held
*distilled-then-orphaned* prose — research whose conclusions had already been
folded into living docs, left behind as a stale duplicate. This
`docs/research/docs-layout-council-138/` holds *undistilled raw evidence* —
the 12 arm transcripts this document's own claims cite by file name (e.g.
Q1's link to `copilot-concrete.txt`) — material a reader needs in order to
audit the claims above it, not a leftover. `docs/PRD.md`'s own rule (quoted
in full at §4) is explicit that research prose gets "deleted at each spec
iteration's exit" once distilled — it does not say audit trails for a
findings document are barred from existing at all beforehand. Once Jon acts
on this document's conclusions, this raw folder has served its purpose and
should be deleted then, same as its 2026-07-13 predecessor was — the
raw-results README says so already. If it is still here at the next spec
iteration's exit with nothing left citing it, that is the signal to remove
it, not a standing exception to the rule it currently satisfies.

## Method: why a council, and how it was built to disagree

Asking several language models "is this layout good" produces agreement
regardless of whether the layout is good, because the layout came out of the
same kind of model in the first place — echoing training-data convention back
is not independent verification. To get evidence instead of an echo, this
review ran **12 arms**: 3 harnesses (Claude, Codex, GitHub Copilot CLI) × 4
prompt variants, each prompt varying *what the arm was told and how it was
told to reason*, not just which model answered:

| Variant | What it changes |
|---|---|
| **control** | Naive framing: "is this layout good, should these repos adopt it?" Included as the trap the issue warns about, for comparison. |
| **adversarial** | Told to argue the layout is *wrong* and propose better, with no hint anyone likes it. |
| **blind** | Repo and file names replaced with neutral labels (`dir-a`, `doc-1`, …); the arm reasons from document content and count only, with no access to which real repos these are or that a "fifth repo" pattern is even under debate. |
| **concrete** | Only placement questions about six specific real documents plus two real, dated git-history facts (the 2026-07-13 `docs/research/` removal and the 2026-08-09 `skills` docs/ removal). No abstract "is this good" question asked at all. |

Full prompts, the shared corpus given to every arm, and all 12 raw responses
are in [`docs/research/docs-layout-council-138/`](research/docs-layout-council-138/).
Every arm ran read-only, against inlined text only, with no access to the
four repos' real working trees, so nothing an arm says about "precedent" was
looked up — it was told directly in the prompt, and its use of that
information (or failure to use it) is part of the evidence.

**Model tiers:** Claude arms ran on the `haiku` tier via a `general-purpose`
subagent; Codex arms ran `codex exec` at `model_reasoning_effort=low`
(the account in use does not expose Codex's smaller named models — confirmed
directly, see the raw-results README); Copilot arms ran the `copilot` CLI
at its default model with `write` and `shell` tools denied. No stronger tier
was reserved for synthesis; this document's synthesis is by the dispatched
agent (Claude, this session), not by a model arm.

**Copilot note:** the *PR-review* Copilot bot's quota was exhausted at
dispatch time (confirmed on #132 and agent-evals#19). The *CLI* arm used here
is a separate quota and every Copilot call in this batch completed
normally — Jon confirmed on the issue that the CLI's employer-authenticated
login (`jon-hill_gentiva`) was fine to use as-is. There is no missing-harness
gap in this council.

## Question 1 — Does each existing document sit in the right directory?

At today's flat layout, yes, with one qualification. Evidence:

- **6 of the 12 arms shown this repo's real identity** (control ×3, concrete's
  Claude and Codex responses) converge on "no document needs to move,"
  each citing a *different* concrete reason per file rather than a blanket
  rule — e.g. Claude-control: `hierarchy-naming-57.md` is self-describing by
  filename already; Codex-concrete: `supervisor-disposition.md` is "active
  decision-support," not a stable category.
- **Copilot-concrete dissents** on two files: it would move
  `migration-audit.md` to a `docs/decisions/`-style archival subdirectory
  (superseded-by-`provenance-manifest.md`) and `agent-engineering-lineage.md`
  to `docs/reference/` (cited glossary, not live guidance) — see
  [`copilot-concrete.txt`](research/docs-layout-council-138/copilot-concrete.txt).
  This is the most defensible dissent in the batch: both files really do have
  a different shelf-life than the rest of `docs/` (one is explicitly
  historical, the other explicitly "not a methodology"), and if `docs/`
  ever exceeds the ~2 items-per-shelf point where a subdirectory earns
  its keep (§4), these two are the most likely first movers.
- No arm in any variant proposed moving `PRD.md`, `SPEC.md`, `handoff.md`,
  `harness-engineering.md`, `loop-engineering.md`, `memory.md`,
  `provenance-manifest.md`, `work-tracking.md`, or `evals.md`
  (`agent-evals`) anywhere.

**Verdict:** no move needed now. `migration-audit.md` and
`agent-engineering-lineage.md` are the two files with a plausible future case
for relocation if `docs/` grows; that case isn't strong enough yet to act on
(Copilot's is a minority view, 1 of 12 arms, and its own reasoning is "if any
subdirectory is introduced" — conditional, not a standalone recommendation).

## Question 2 — Is there noise to strip?

Not found. `docs/handoff.md` already flags its own staleness inline (banner
dated 2026-08-09, #10) rather than existing as undisclosed stale content —
that is the pattern the issue asks whether other docs lack. Checked every
other file's own status line/banner:

- `SPEC.md` — carries a dated status line, updated 2026-07-29, not stale.
- `provenance-manifest.md`, `migration-audit.md` — both explicitly historical
  by design (audit/ledger documents); `migration-audit.md` states its own
  successor (`provenance-manifest.md`) in its first paragraph — this *is*
  the banner pattern the issue describes from Hill90's `docs/product/`,
  just spelled as prose instead of a blockquote.
- No file in any of the four repos' `docs/` was found undated, unbannered,
  and stale. `agent-evals/docs/evals.md` is a single, current file.

No superseded record was found carrying **no** signal of its status — the
failure mode Q2 asks about does not currently exist in these four repos.
This is a direct-inspection finding (the agent that wrote this document read
every file's opening lines), not a council-arm claim.

## Question 3 — Should `skills` / `skills-private` have `docs/` at all?

No, and this is the strongest evidence in the whole batch, for an unusual
reason: **it is unanimous across all 12 arms, and the unanimity is not a red
flag here** — see "Was the disagreement real?" below for why.

- `skills`' `docs/` was not merely absent — it was **removed on 2026-08-09**,
  deliberately, in a commit whose message states the goal directly: strip
  "agent-dotfiles harness machinery" and other non-native content to make
  `skills` "the standalone public skills collection" (`069e2c4`,
  `jonhill90/skills`). `skills-private` has never had one.
- Every arm shown this fact (concrete ×3) treated it as decisive: none
  recommended reversing it. The **blind** arms — which were *not* told this
  history, only that `dir-c`/`dir-d` are "pure content repositories" with no
  `docs/` today — independently reached the same conclusion from structure
  alone ("adding an empty `docs/` speculatively creates a directory with no
  content to justify its existence," Claude-blind; "no evidence anyone will
  populate it," Copilot-blind).
- Both blind and informed arms name the same reversal condition: it flips
  only if the repos start accumulating documentation genuinely native to a
  skill collection (not harness machinery) that no longer fits in
  `README.md`/`AGENTS.md`.

**Verdict:** absence is correct, not a gap. Confirmed by direct inspection
(the 2026-08-09 commit and its message, cited above) plus 12/12 council
agreement across a design built to let them disagree.

## Question 4 — Is the split itself right, or is flatter better at this size? At what size does the answer change?

This is where the batch produced its real finding. Short version: **flat is
right for these four repos today, but that verdict tracks which arms could
see this repo's real identity, not the layout being self-evidently
correct** — and even that is not the whole story; the exact variable takes
some sorting out below, and doing that sorting out is most of this section.
The batch also surfaced a second, opposite reading of pure document count
that deserves to be on record, not buried under the majority.

**The split, tallied by prompt variant** (12 arms; "subdivide" = would give
`agent-dotfiles`'s 12 docs more than one directory *now*):

| Variant | Claude | Codex | Copilot | Net |
|---|---|---|---|---|
| control | flat | flat | flat | 3 flat |
| adversarial | flat (index+frontmatter, no dirs) | **subdivide** (own 6-way split) | **subdivide** (own 4-way split) | 1 flat / 2 subdivide |
| blind | **subdivide** (5 cats) | **subdivide** (5 cats) | **subdivide** (4 cats) | 3 subdivide |
| concrete | flat | flat | partial (2 of 12 files move) | 2 flat / 1 partial |

Totals: **6 of 12 arms recommend staying purely flat now; 5 recommend
subdividing `agent-dotfiles`' docs/ outright; 1 (Copilot-concrete) takes a
partial middle position** — moving 2 of the 12 files while leaving the rest
flat. Counted the strict way (partial counts as "introduces some
structure," since it does propose directories), that is **6 flat vs. 6
non-flat — a coin flip**, not the "N models, N yeses" pattern the issue
warns about. It lines up with *what each arm was told*, which is the
signature of real reasoning rather than echo:

**Testing candidate variables against all four groups, not just the two that
motivated the first draft of this section:**

An earlier version of this document claimed the deciding variable was
"whether the arm was told this repo's own git history" (the 2026-07-13
`docs/research/` flattening). That claim does not survive checking it
against **control**: the control prompt never mentions that history either
— it gives no git facts at all — yet control went 3/3 flat, matching
concrete's flat lean rather than blind's subdivide lean. A variable that
predicts concrete correctly but gets control backwards is not the variable.

The variable that actually separates the four groups correctly is coarser:
**whether the arm could see real, recognizable repo and file names at all.**

| Variant | Real names visible? | Told this repo's own history? | Explicitly told to argue/critique? | Result |
|---|---|---|---|---|
| control | yes | no | no | 3 flat |
| adversarial | yes | no | yes | 1 flat / 2 subdivide |
| concrete | yes | yes | no | 2 flat / 1 partial |
| blind | **no** | no | no | 3 subdivide |

Grouped by that one column: the three name-visible variants are 6 flat / 1
partial / 2 subdivide across 9 arms (flat-leaning, 67% strict-flat); the
name-blind variant is 0 flat / 3 subdivide across 3 arms (100%
subdivide). That is the cut that actually holds across all four groups —
control and concrete agree with each other and disagree with blind, which
"history known" cannot explain since control didn't have it, and this
column does.

**What it does not explain: adversarial's internal split.** Two of three
adversarial arms subdivided despite seeing real names — the same names
control saw, which went 3/3 flat. Being explicitly instructed to argue the
layout is wrong and propose something better appears to trigger a
"produce an alternative structure" response somewhat independent of whether
the names were real, and this batch cannot cleanly separate that effect from
the possibility that *any* instruction to actively redesign (rather than
evaluate or answer narrow placement questions) pulls toward proposing
directories. Blind's own prompt asked the arm to "design... from scratch,"
which is closer in spirit to adversarial's "propose better" than to
control's or concrete's evaluate/answer framing — so blind's 3/3 subdivide
result is consistent with *either* "no real names" *or* "asked to design
rather than evaluate" as the operative cause, and this design cannot tell
those two apart. Naming that limit is more honest than picking whichever
story is more interesting.

**What this batch supports, precisely:** arms shown this project's real
identity and given a narrow, evaluative task (control, concrete) converge
on flat; the one arm-group with neither real names nor an evaluative framing
(blind) converges on subdivide; the one group with real names but an
explicit redesign instruction (adversarial) splits down the middle. The
strongest single-variable fit across all four groups is name-visibility, not
history-awareness — but "was asked to redesign vs. evaluate" is a live
alternative or contributing explanation that a 3-arms-per-cell batch cannot
rule out. Both readings point the same direction for this document's actual
question (should real, named `agent-dotfiles` adopt a split *now*, given its
real history) — the arms that had all three of real names, this repo's
history, and a narrow evaluative task (concrete) are the closest match to
that question, and they lean flat (2 flat / 1 partial, not 3/3, so this is
still not unanimous even in the best-matched cell).

**Answer to "at what size does it change":** the batch's own numbers put a
soft floor at 4–8 heterogeneous documents for the *content-only, no-real-
identity* reading (blind arms: Claude "5-6," Codex "6 to 8," Copilot "4-5" —
already below `agent-dotfiles`' current 12). That reading does not automatically
transfer to the real, named repo, precisely because name-visibility is the
variable that best explains why the other three groups diverge from it. The
honest statement is: *if* `agent-dotfiles` were evaluated as an anonymous
12-document pile with no identity or history attached, this batch's evidence
says it would already be past the subdividing threshold; *as the actual,
named repo with its own recorded reversal on this exact question*, the
groups that had access to that identity lean flat. Which reading should
govern is a judgment call this document is making explicitly (below), not
one the data alone settles.

**Verdict:** stay flat in `agent-dotfiles` and `agent-evals` for now. This
is a scoped call resting on this repo's real identity, its own history, and
its current sub-2026-08 file count — not a portable rule, and not a
unanimous one even within the best-matched arm group (concrete: 2 flat / 1
partial, not 3/3). The next re-review of this question should re-run a
name-blind, content-only arm against whatever the file set looks like then
as a deliberate check against inherited precedent, precisely because this
batch shows that arm answers differently when it cannot see "but we already
decided this."

## Question 5 — What is the actual convention outside this estate? (cite real repositories)

Verified externally, with citations:

- **Architecture Decision Records (ADRs) getting their own subfolder is a
  real, widely-used convention** — this is the one piece of Hill90's
  five-way split with a genuine external match. `npryce/adr-tools`
  (the most common ADR tooling) defaults new ADR logs to `doc/adr`
  ([github.com/npryce/adr-tools](https://github.com/npryce/adr-tools));
  the MADR (Markdown ADR) project's own template repo uses `docs/decisions`
  ([adr.github.io](https://adr.github.io/), [github.com/adr/madr](https://github.com/adr/madr)).
  `agent-dotfiles` already has an ADR-shaped document
  (`provenance-manifest.md`, explicitly "successor to migration-audit.md,"
  an adopt/adapt/author/reject ledger) — if it ever splits into one file per
  decision, `docs/decisions/` would be adopting a real, named, externally
  common convention, not inventing one.
- **Diátaxis is a real, widely-adopted competing convention, organized by
  a different axis than Hill90's split.** Diátaxis groups docs by *reader
  need* — tutorial / how-to / reference / explanation — not by *document
  type* the way `architecture/decisions/product/runbooks/reference` does.
  It was created by Daniele Procida (Django core developer) and has been
  adopted to restructure real, large documentation sets at Django, Cloudflare,
  Gatsby, and NumPy ([diataxis.fr](https://diataxis.fr/)). None of the four
  repos in scope here have enough distinct reader personas (tutorial-seeker
  vs. reference-looker) for this to apply yet, but it is the more common
  real convention at genuine scale than an artifact-type split is.
- **Large real projects that do subdivide docs by category subdivide by
  ownership/domain, not by generic artifact type.** Kubernetes' enhancement
  proposals live under `keps/` split into per-SIG subdirectories, not a
  single flat `architecture`/`decisions`/etc. taxonomy
  ([github.com/kubernetes/enhancements](https://github.com/kubernetes/enhancements/tree/master/keps),
  [kubernetes.dev/resources/keps](https://www.kubernetes.dev/resources/keps/)).
- **What I could not verify:** a real, external, named project using
  exactly Hill90's five-way split — `architecture/` + `decisions/` +
  `product/` + `runbooks/` + `reference/` as flat siblings under one
  `docs/`. Search surfaced one community-authored, agent-oriented
  documentation-convention gist recommending `architecture/` with a nested
  `architecture/decisions/`, explicitly written "because humans and AI
  agents are only as reliable as the context they can find," but it does
  **not** include `product/`, `runbooks/`, or `reference/` as named
  top-level folders — it is a partial, not exact, match, and it is a
  personal gist, not an attested convention at any real organization
  ([gist.github.com/lukewilson2002](https://gist.github.com/lukewilson2002/cb48062397d8b51954034d94b8c19d6d)).
  I am stating this as unverified rather than naming a repository I cannot
  point to, per the brief's instruction.

**Verdict:** the *pieces* of Hill90's split are real conventions (ADRs get
a subfolder; category-based docs organization is common at scale) but the
*specific five-category combination* is not one I can cite as an attested
external pattern. Treat it as this estate's own invention, assembled from
real building blocks, not as "the convention outside this estate."

## Was the disagreement real?

Yes, on Q4 (§ above) — a near-even 6-flat/5-subdivide/1-partial split, and
the split lines up with an information axis (could the arm see this repo's
real, recognizable identity, or only anonymized content) rather than with
model or harness lines: the one name-blind group is 3/3 subdivide, the three
name-visible groups are collectively flat-leaning but not unanimous — one of
them (adversarial) splits down the middle on its own. That is the finding
this issue exists to surface, and it is reported in full in §4, including
the parts of it a single tidy variable does not explain, rather than
compressed to "flat won."

On Q3, the batch was unanimous (12/12: no `docs/` for `skills`/
`skills-private`). Per the issue's own instruction, unanimity here needs an
explicit account of why the arms were still capable of disagreeing, not a
free pass:

1. **The blind arms had no access to the real removal history** and
   reached the same verdict from structure alone (empty holding area, pure
   content repo) — this rules out "the arms just repeated a fact I fed
   them," since two-thirds of the unanimous arms were never fed that fact.
2. **The adversarial arm was explicitly instructed to argue against
   received wisdom** and still did not contest this point (none of the
   three adversarial responses proposed a `docs/` for `skills` or
   `skills-private` — all three left it out entirely, treating it as settled).
3. There is a real, dated, first-party commit (`069e2c4`, 2026-08-09)
   driving this, independent of any model's opinion — this question has a
   ground-truth answer the council converged on, rather than a
   matter-of-taste question that happens to poll unanimously.

That is a materially different situation from Q1/Q4's echo risk, where no
comparable hard fact exists and the split was real. I am not treating Q3's
unanimity as strong evidence on its own merits — it is strong because of
(1)-(3), and would not be if the arms had all just been told the same fact
and repeated it back.

## Recommendation

- **No file moves now**, in any of the four repos (hard constraint of this
  issue; also consistent with the reasoning above — the arms that could see
  this repo's real identity leaned flat, even though the full 12-arm vote
  was a near-even split and even that best-matched group was not unanimous).
- **Do not adopt Hill90's five-way split anywhere in scope.** It is not
  externally well-precedented as a combined pattern (Q5), and this repo
  already tried and reversed subdividing `docs/` once — `533f275`,
  2026-07-13, verified by direct inspection of the commit rather than
  asserted by any arm (Q4).
- **Revisit, don't schedule.** The trigger for `agent-dotfiles` is a new
  document class that doesn't fit the current 12 (see `migration-audit.md`
  / `agent-engineering-lineage.md` as the closest existing candidates for
  eventual relocation, §1) — not a raw file count. When that trigger fires,
  re-run a blind-style arm against the file set at that time rather than
  reasoning from this document's conclusion, since this document's own
  "stay flat" verdict depends on precedent that a future, larger `docs/`
  may no longer share.
- **If `agent-dotfiles` ever does split**, `docs/decisions/` for
  `provenance-manifest.md`-style content is the one piece with genuine
  external precedent (Q5) — start there, not with a five-way split copied
  from Hill90.
- **`skills` / `skills-private` stay without `docs/`.** Confirmed by a real
  commit and unanimous, differently-informed council agreement (Q3).
- **This document stays flat at `docs/docs-layout-council-138.md`**,
  consistent with the above.
