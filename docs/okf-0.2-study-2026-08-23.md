# OKF study, build-3 — what 0.2 costs, whether we use 0.1 correctly, what the tooling gives free

Companion to `docs/okf-adoption-280.md` (agent-dotfiles#282, 2026-08-16),
not a replacement. That PR already read the v0.2 spec, built the
gap-report contract, shipped the read-only linter (`scripts/memory_lint.py`,
extended by #301), and designed the additive migration. This document:
corrects one stale premise, adds what changed since that read, checks
today's live vault (75 facts, up from that PR's 53) against the spec with
two independent tools instead of one, answers the bundle-scoping and
RAG questions #280/#282 didn't reach, and gives a sequence. **No vault
write in this PR** — same constraint #282 held.

## 0. The premise that needed correcting

The task brief that opened this study states: *"nobody here has read
[the OKF spec] from source"* and *"there is NO local checkout of the spec
anywhere."* The second half is true and is exactly what this PR fixes.
The first half is not: `docs/okf-adoption-280.md` (agent-dotfiles#282,
merged 2026-08-16) fetched the v0.2 SPEC directly (`gh api`) and produced
a field-by-field gap table against it. What was actually missing was a
**persistent, re-inspectable checkout** — a fetch-and-discard isn't one,
and a spec that moves out from under a stale URL (§1 below) is exactly
the failure mode that gap creates. That checkout now exists.

## 1. What's canonical now, and where it's cloned

`docs/okf-adoption-280.md` cites
`github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md`.
That citation is now stale: `lorsabyan/okf-skill`'s own changelog records
that upstream **followed the format out to its own repository**,
`GoogleCloudPlatform/open-knowledge-format`, and the `knowledge-catalog`
copy is a "frozen, unmaintained snapshot" per that README. Confirmed
directly, not taken on the changelog's word: `SPEC.md` is byte-identical
between the two repos as of today (`diff` against
`knowledge-catalog@c06e3ee`, zero lines of difference) — so #282's gap
findings are not invalidated by the move, but the *citation* is broken
for anyone following it forward from here, and `okf-skill`'s own commit
history (below) shows real change has landed at the new address since.

Cloned into `/Users/jon/source/repos/skills-research/` (research checkouts
live there, per this task's own instruction — `microsoft-skills`,
`hve-core` already there):

| Repo | License | What it is |
|---|---|---|
| `GoogleCloudPlatform/open-knowledge-format` | Apache-2.0 | **Canonical spec** (`SPEC.md`) + a BigQuery-oriented reference agent/CLI (`enrich`, `visualize`) + sample bundles. Full history unshallowed: 6 commits total, oldest 2026-08-14. |
| `lorsabyan/okf-skill` | Apache-2.0 | Claude Code / Codex **Agent Skill** for OKF v0.2: `SKILL.md`, a stdlib-only `validate_okf.py` and `generate_index.py`, a benchmark suite, pinned to a specific upstream commit with a CI job that watches for drift. |
| `openknowledge-sh/openknowledge` | Apache-2.0 | Go CLI, larger surface (`agent`, `setup-skill`, `registry`, `deploy`, `automation` subcommands). Not evaluated command-by-command — see §8, "not determined." |
| `zosmaai/pi-llm-wiki` | MIT | Obsidian-integrated, "native OKF v0.2," 12 slash commands + an MCP server — built for the **`pi` harness**, not Claude Code. |
| `coleam00/cole-medin-ai-coding` | **none** | A real, worked **v0.1** bundle (not 0.2) shipped as content. No `licenseInfo` on the repo — **study-only**, nothing from it is adopted or copied. |

## 2. What changed 0.1 → 0.2 — from the spec's own §13, not a summary

Quoting the spec's own changelog section directly (SPEC.md §13):

> v0.2 supersedes OKF v0.1 and is a minor version bump under §12, except
> for two deliberate breaking changes... A v0.1 bundle is consumable by a
> v0.2 consumer under the fallbacks noted here.

**Breaking (§13.1), both with a required fallback for consumers:**
- `timestamp` → `generated: { by, at }`. Consumers MAY fall back to legacy
  `timestamp` when `generated` is absent.
- Body `# Citations` list → frontmatter `sources`. Consumers SHOULD read
  `sources`, MAY still parse a legacy `# Citations` list.

**Additive (§13.2), absence yields a plain v0.1 concept:**
- `sources` with per-source credibility signals (`author`, `usage_count`,
  `last_modified`) and its `usage_window` sibling.
- `generated`, `verified` (trust).
- `status`, `stale_after` (lifecycle).
- A new concept type, `Attested Computation`, and its keys (`runtime`,
  `parameters`, `computation`, `executor`, `attester`), plus the
  `# Computation` body heading.
- The `<producer>/<version>` / `human:<id>` / `process:<id>` actor
  convention for `generated.by` and `verified[].by`.

Everything else — bundle structure, reserved filenames, `type` as the
only required key, `index.md`/`log.md` format, permissive conformance —
**carries forward unchanged**. This matches #282's gap table field for
field; nothing above contradicts that PR's read of the spec.

### New since #282's read (2026-08-16), and not yet anywhere in our docs

`open-knowledge-format`'s own commit history (unshallowed, all 6 commits
inspected):

```
ad30107  2026-08-21  Merge pull request #6 from .../okf-iso-datetimes
0b87c52  2026-08-20  drop the timestamp conformance bullet from SPEC 11
6a2845d  2026-08-20  drop the duplicated timestamp conformance prose
3dc3029  2026-08-20  make every timestamp an ISO 8601 datetime with an explicit offset
```

**Every timestamp field now requires an explicit UTC offset** — tightened
2026-08-20/21, four days after #282 read the spec, **without an
`okf_version` bump to signal it**. `okf-skill`'s own `CHANGELOG.md`
documents getting caught by exactly this: its validator's bare-`YYYY-MM-DD`
check "warned on the exact form upstream now writes," producing 16
spurious warnings that turned a `--strict` CI gate red, discovered only by
hand. Its own conclusion, worth carrying into our design directly: *"the
job... states that `okf_version` is not a reliable signal of a format
change."* If we ever populate `stale_after` or `sources[].last_modified`
(both currently 0/74, per §5 below), write them as full ISO 8601 with an
offset, not a bare date — `log.md`'s `## YYYY-MM-DD` heading form is
unaffected (§9 is explicit that's still bare-date).

## 3. Are we using 0.1 correctly today? — two independent tools, live vault

Ran both `scripts/memory_lint.py` (this repo, vault-aware, extended by
#301) and `okf-skill/okf/scripts/validate_okf.py` (community, generic,
scans the **whole** `agent/` tree per spec §11's literal scope — "every
non-reserved `.md` file") against the live vault today. They disagree in
scope in a way that matters, not just in numbers.

**`memory_lint.py`** (facts + index/log only):

```
facts: 75   index lines: 81   index bytes: 12504
[ERROR] 1 fact: unparseable YAML — an un-quoted em dash in a `title:`
  scalar breaks block-mapping parsing (a NEW, different fact than the
  two #282 found on 2026-08-16 — that class of defect recurred)
[WARN]  2/74 facts missing recommended `description`
[WARN]  9/124 internal links resolve to a missing fact
[INFO]  0/74 facts carry any of generated/verified/status/stale_after/sources
[INFO]  index.md declares okf_version: '0.1'
```

**`validate_okf.py`** (whole `agent/` tree, spec-literal scope):

```
ERROR  corpus/README.md: missing or unparseable YAML frontmatter block
ERROR  pending-links.md: missing or unparseable YAML frontmatter block
warning facts/: no index.md (progressive disclosure)
warning corpus/: no index.md (progressive disclosure)
warning log.md: link to missing concept — 2 targets
76 concept doc(s), 2 error(s), 7 warning(s)
```

**The two ERRORs the community tool found are real and were previously
invisible to us**: `corpus/README.md` and `pending-links.md` are
non-reserved `.md` files inside the bundle tree, so spec §11 rule 1
("every non-reserved `.md` file... contains a parseable YAML frontmatter
block") applies to them. Neither carries frontmatter. This is not a
`memory_lint.py` bug — that script scopes itself to `facts/` + the two
reserved files by design, and never claimed wider coverage — but it means
**our own tooling's conformance check is narrower than the spec's actual
rule**, and the gap was invisible until an independently-scoped tool was
run against the same tree. Deviation, not a decision: report it, don't
fix it here (brief's constraint).

**The link-syntax deviation, checked directly rather than assumed:**
`memory_lint.py` resolves both `[[wikilink]]` and `[markdown](link)`
syntax (`WIKILINK_RE` and `MDLINK_RE`, both defined in the script). The
spec's own §6.1 defines a Link as *"a standard markdown link"* — the word
"wikilink" does not appear anywhere in `SPEC.md` (grepped, zero hits),
and `okf-skill`'s validator's own `LINK_RE` (`\[[^\]]*\]\(([^)]+)\)`)
cannot match `[[bare-name]]` at all — confirmed by inspecting the regex,
not inferred. Concretely: `agent/index.md` alone carries 42 `[[wikilink]]`
occurrences against 32 standard markdown links. Every one of those 42 is
**invisible to any spec-conformant OKF consumer that isn't our own
`memory_lint.py`**, including the community validator, the reference
viewer, and (materially, given #272) any future OKF-based RAG layer built
to spec rather than to our specific script. This is internally consistent
today and externally non-portable — a real deviation worth naming, not a
mistake worth panicking about; the fix is a link-syntax convention
decision, not something this PR makes.

**Corroborates #282 exactly on one point, three days apart in fact count:**
recommended-field coverage was 10/51 missing both `title`/`description`
on 2026-08-16 (53 facts); today it's 0/74 missing *both*, 2/74 missing
`description` alone (75 facts, one grew mid-session between two
measurements in this task — noted, not chased, per `determine-signals`
discipline: the drift is real, the vault is live). The gap closed
substantially between #282 and now, evidence the linter's advisory
reporting is actually being acted on, at least for that one field pair.

## 4. Bundles, scoping, per-agent knowledge — checked against the spec directly

Grepped `SPEC.md` for every term a multi-bundle mechanism would use:
`multiple bundle`, `registry`, `scop`, `per-agent`, `federat`. **Zero
hits for any first-class multi-bundle relationship.** §2's own definition
of Bundle is exhaustive: *"a self-contained, hierarchical collection of
knowledge documents. The unit of distribution."* Nothing in the spec
describes how two bundles relate, merge, or get addressed as a set — a
bundle is a directory tree, full stop; nesting one bundle's *subdirectory*
under another isn't a defined relationship either, just two unrelated
directory trees that happen to share a filesystem.

Checked the tooling too, not just the spec: none of `okf-skill`,
`openknowledge`, or `pi-llm-wiki`'s docs describe a per-agent or
multi-bundle convention (same grep, zero hits across all three).

**This directly answers agent-supervisor/agent-dotfiles#281's open
question 2** ("does scope belong [in frontmatter], or is it derived") —
OKF gives no native answer either way. A per-agent bundle would be an
**invented convention** layered on top of OKF, exactly as much work as it
would have been before this study — most plausibly either (a) a new
frontmatter key (cheap, allowed under §4.1's "Extensions" clause, but a
bespoke field #281 itself says needs justifying) or (b) a genuinely
separate bundle directory per agent, which OKF's directory-tree model
supports mechanically but doesn't name or coordinate. **#281 should not
wait on OKF for this — it isn't coming.** This document is the "read the
OKF issue first" input #281 asked for; the scoping decision itself stays
#281's, not this PR's.

`index.md`'s progressive-disclosure role (§8) is explicitly **unchanged**
by v0.2 (§13.2: "everything else... index files... carried forward
unchanged"). One real structural gap found while checking this, though,
not a version question: the spec's own convention is a subdirectory
`index.md` at *every* level (§3's tree diagram shows one per directory);
`coleam00/cole-medin-ai-coding` (the worked v0.1 example, study-only)
does this correctly — `videos/index.md`, `concepts/index.md` alongside
its root index. Our vault has **only** the root `agent/index.md**; `facts/`
and `corpus/` have none — flagged by `validate_okf.py` above. Not a v0.1
vs v0.2 question (unchanged either way) and not fixed here.

## 5. The RAG question — already settled, and 0.2 is its implementation path

agent-dotfiles#272 (2026-08-21, open, not this PR's to reopen) already
answered "RAG alongside OKF, not replacing it": both retrieval-first
candidates surveyed (`forgetful`, `cognee`) were rejected because our
failure mode is **staleness**, not retrieval, and neither tool's README
had a single real hit for `stale|expir|invalidat|supersede`. #272's own
recommendation was to add local `expires:`/`verified:` fields and a
validator that fails on a fact past its re-verification date.

**That is, field for field, what OKF v0.2's trust and lifecycle family
already is** — `verified: { by, at }` (§5.2), `status` (§5.4),
`stale_after` (§5.5) — not a coincidence worth treating as new insight, a
convergence worth stating plainly: adopting v0.2's additive fields *is*
the concrete implementation of what #272 already decided to build, rather
than a second, parallel schema. Today's coverage is 0/74 for all three
(§3 above) — the gap #272 named is still open, and v0.2 is the vehicle,
not a competing option.

## 6. What upgrading actually costs

**Not a structural break.** #282 already established this and it still
holds: zero live exposure to either breaking change (`timestamp`:
0/74 today, up from 0/53; body `# Citations`: 0/75). The two v0.1→v0.2
breaking renames in §13.1 are moot for us specifically because we never
populated the fields they replace.

**Concretely, the upgrade is:**
1. A one-line frontmatter bump, `okf_version: "0.1"` → `"0.2"` in
   `agent/index.md` — declarative only, per §12 consumers fall back to
   best-effort on an unrecognized version regardless.
2. Optionally, and only where a fact has enough information to populate
   them honestly: `generated`, `verified`, `status`, `stale_after`,
   `sources`. All additive; §11 keeps a bare-`type` fact fully
   conformant with none of them.

**What it does not require:** no rename of `source`/`created`/`updated`
(not OKF fields; allowed as Extensions under §4.1, consumers must
preserve unknown keys), no file moves, no change to `index.md`/`log.md`
format, no change to the `type` taxonomy we already use
(`user`/`feedback`/`project`/`reference` — a category scheme, not the
spec's own worked examples' asset-kind scheme like `BigQuery Table`, but
the spec places no constraint on `type`'s values beyond non-empty and
"consumers must tolerate unknown types," so this is a legitimate, if
non-idiomatic, producer choice, not a violation).

## 7. What the tooling gives free

`lorsabyan/okf-skill` is the most directly reusable find, Apache-2.0,
built specifically for Claude Code and Codex:
- `validate_okf.py` — stdlib-only, no dependency beyond Python's own
  stdlib, checks the same conformance floor `memory_lint.py` checks plus
  the whole-tree scope gap found in §3.
- `generate_index.py` — **non-destructive** index regeneration: an
  existing `index.md`'s curated order, hand-abridged titles, and entry
  descriptions survive a re-run; only entries whose target vanished are
  dropped and new concepts appended. `--rebuild` opts into the fully
  mechanical convention instead. This is a real capability
  `memory_lint.py` doesn't have today (it reports index drift as counts,
  never writes one) and directly answers "regenerate the index safely"
  if `facts/`/`corpus/` ever get their own.
- A CI discipline worth borrowing regardless of whether we take the skill
  itself as a dependency: **pin the upstream spec to a commit SHA**, and
  run a separate, non-blocking `spec-drift` job that diffs the *pinned*
  copy against upstream's current default branch — exactly the mechanism
  that would have caught §1's timestamp-format tightening before it was
  found by hand, and the same "spec drift" class of problem this whole
  task exists to close for us.

Nothing in the canonical `open-knowledge-format` repo itself is a Claude
Code slash command — its CLI (`enrich`, `visualize`) is a Python
subcommand tool aimed at BigQuery/Dataplex ingestion, not vault
management, and not directly applicable to our use case.

`zosmaai/pi-llm-wiki` genuinely ships 12 slash commands
(`wiki-init`/`wiki-ingest`/`wiki-discover`/`wiki-digest`/`wiki-lint`/
`wiki-query`/`wiki-record`/`wiki-req`/`wiki-retro`/`wiki-run`/
`wiki-skills`/`wiki-status`) plus an MCP server and is genuinely
Obsidian-integrated — but it's built against the **`pi`** harness's
command/extension model, not Claude Code's, and its own frontmatter
vocabulary (`domain`, `category`) and Obsidian wikilink-first design
diverge from strict OKF markdown-link syntax the same way ours does
(§3). Worth a second look if we ever adopt `pi` as a harness; not a
drop-in for Claude Code today.

## 8. What I could not determine

- `openknowledge-sh/openknowledge`'s full command surface (`agent`,
  `setup-skill`, `registry`, `deploy`, `automation` subcommands) was not
  evaluated command-by-command — cloned and confirmed Apache-2.0 and
  OKF-v0.2-badged, but whether any subcommand does something
  `okf-skill`'s narrower validator/index-generator pair doesn't is
  unassessed.
- Whether any real-world OKF consumer beyond the two validators run here
  treats `okf_version` as load-bearing for parsing strictness (rather than
  informational) was not checked beyond these two repos.
- agent-dotfiles#281's own open item 5 ("find the Google article on
  progressive disclosure Jon means") is that issue's work, not this
  study's; not attempted here.

## Recommended sequence

1. **Doc-only, low-risk, not gated on anything else:** fix
   `docs/okf-adoption-280.md`'s citation from the frozen
   `knowledge-catalog` mirror to `GoogleCloudPlatform/open-knowledge-format`,
   and note the ISO-8601-offset tightening (§2) so a future reader doesn't
   re-derive it. Small enough to fold into this PR or take separately —
   Jon's call, flagged rather than done, since it touches a doc this PR
   is a companion to, not the vault itself.
2. **Report-only pilot, no vault write:** run `validate_okf.py` against
   the vault as a *second*, wider-scoped check alongside `memory_lint.py`
   rather than replacing it — `memory_lint.py` has vault-specific checks
   (near-duplicate detection, contradiction heuristics, index-cap
   tracking against #281's own thresholds) the generic validator doesn't,
   and doesn't need to. Decide whether to extend `memory_lint.py`'s own
   scope to match §11's whole-tree rule (closing the `corpus/README.md`
   gap) or to keep running both.
3. **First vault write, separately reviewed:** the one-line
   `okf_version: "0.1"` → `"0.2"` bump. Purely declarative per §12.
4. **Second vault write:** fix the 2 files `validate_okf.py` flagged
   with no frontmatter (`corpus/README.md`, `pending-links.md`) — either
   give them `type`, or document explicitly that they're bundle
   housekeeping, not concepts, and exempt them by convention.
5. **Decide #281 (scoping) using §4 above as input** — OKF supplies no
   native mechanism, so the decision is purely ours to make, informed but
   not resolved by this document.
6. **Only after 3–5 are stable:** populate `generated`/`verified`/
   `status`/`stale_after`/`sources` fact-by-fact, AI-reviewed per #280's
   existing Rule E boundary (tools detect and report, never rewrite
   meaning) — this is the step that actually closes #272's staleness gap,
   and it's the one this document recommends doing last, not first.

Ref: agent-dotfiles#280, agent-dotfiles#281, agent-dotfiles#272

Author-Lane: estate:3
