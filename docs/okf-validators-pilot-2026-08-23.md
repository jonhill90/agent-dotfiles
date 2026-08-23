# OKF validators pilot — memory_lint.py alongside validate_okf.py, report-only

Step 2 of `docs/okf-0.2-study-2026-08-23.md`'s recommended sequence
(agent-dotfiles#312): run `okf-skill/okf/scripts/validate_okf.py` (community,
generic, whole-`agent/`-tree scope per SPEC §11's literal rule — "every
non-reserved `.md` file") alongside `scripts/memory_lint.py` (this repo,
vault-aware, `facts/` + the two reserved files only) rather than replacing
either. **No vault write in this pass** — same constraint #312 held; the
`okf_version` bump and the two frontmatter-less files are steps 3/4,
separately reviewed.

Both run today, 2026-08-23, against the live vault
(`$AGENT_MEMORY_VAULT/agent`).

## Real output, both tools, this run

```
$ python3 scripts/memory_lint.py
OKF v0.2 read-only lint -- .../Agent Memory
facts: 76   index lines: 82   index bytes: 12670

[ERROR]
  (conformance) 1 fact: unparseable YAML: while parsing a block mapping
  in "<unicode string>", line 1, column 1:
    type: reference
    ^
expected <block end>, but found '<scalar>'
  in "<unicode string>", line 2, column 24:
    title: "Parked on Jon" — the five-decision consolidatio ...
                           ^

[WARN]
  (recommended-fields) 2/75 facts missing recommended `description` (OKF §4.1)
  (link-integrity) 9/125 internal links resolve to a missing fact
  (possible-contradictions) 1 fact pair(s) with similar slugs and differing bodies -- candidates for AI review, not confirmed contradictions

[INFO]
  (conformance) 75/76 facts conform to OKF §11 (parseable frontmatter, non-empty type)
  (recommended-fields) 0/75 facts missing both title and description
  (okf-v0.2-families) 0/75 facts carry `generated` (OKF v0.2 §5, additive)
  (okf-v0.2-families) 0/75 facts carry `verified` (OKF v0.2 §5, additive)
  (okf-v0.2-families) 0/75 facts carry `status` (OKF v0.2 §5, additive)
  (okf-v0.2-families) 0/75 facts carry `stale_after` (OKF v0.2 §5, additive)
  (okf-v0.2-families) 0/75 facts carry `sources` (OKF v0.2 §5, additive)
  (legacy-v0.1-fields) 0/75 facts carry legacy `timestamp` (superseded by `generated.at`, OKF §13.1)
  (legacy-v0.1-fields) 0/76 facts carry a body `# Citations` heading (superseded by `sources`, OKF §13.1)
  (freshness) 0/75 facts carry `stale_after` -- staleness cannot be assessed from frontmatter yet
  (trust) 75/75 facts carry no `verified[]` entry (OKF trust tier: unverified, §5.3)
  (near-duplicates) 0 exact-duplicate body group(s) across 0 facts (hash-based)
  (index-cap) index.md at 49.5% of its declared cap (82/200 lines, 12670/25600 bytes)
  (index) index.md declares okf_version: '0.1' (OKF §12)
  (index) 0/76 facts have no corresponding index.md link
  (index) 0 index.md links point at a fact that no longer exists

This tool detects and reports only. No file was written.
```

```
$ python3 okf-skill/okf/scripts/validate_okf.py "$AGENT_MEMORY_VAULT/agent"
ERROR   corpus/README.md: missing or unparseable YAML frontmatter block
ERROR   pending-links.md: missing or unparseable YAML frontmatter block
warning facts/codex-as-second-harness.md: no 'description' - index generators and previews rely on it
warning facts/topics-not-to-raise.md: no 'description' - index generators and previews rely on it
warning log.md: link to missing concept 'facts/<slug>.md'
warning log.md: link to missing concept 'facts/shell-scripts-pass-shellcheck.md'
warning log.md: link to missing concept 'facts/shell-scripts-pass-shellcheck.md'
warning corpus/: no index.md (progressive disclosure)
warning facts/: no index.md (progressive disclosure)

.../Agent Memory/agent: 78 concept doc(s), 2 error(s), 7 warning(s)
```

(Fact/doc counts differ slightly between the two runs — 76 vs 78 — because
the vault is live and grew between the two commands executing, the same
"noted, not chased" drift `docs/okf-0.2-study-2026-08-23.md` §3 already
flags. Both counts are real, taken seconds apart, not a discrepancy in
either tool.)

## What each catches that the other does not

**`memory_lint.py`-only** (would not be replicated by widening
`validate_okf.py`'s scope — these are vault-specific, not spec checks):

- Near-duplicate body detection (hash-based; 0 found today, capability
  exists and `validate_okf.py` has no equivalent).
- Possible-contradiction heuristic across similar slugs (1 pair flagged
  today, for AI review, not auto-resolved).
- Index-cap tracking against this vault's own declared budget (82/200
  lines, 49.5%) — a threshold #281 set for this vault specifically, not an
  OKF concept.
- Explicit per-family v0.2 adoption counts (`generated`/`verified`/
  `status`/`stale_after`/`sources`, each 0/75) and legacy-field usage
  (`timestamp`, `# Citations`, both 0) — `validate_okf.py` reports errors
  and warnings, not this kind of adoption-coverage breakdown.
- Link-integrity restricted to `facts/`'s own `[[wikilink]]` + markdown-link
  resolution (9/125) — a different count than `validate_okf.py`'s, because
  it scans a different corpus (see below).

**`validate_okf.py`-only** (real gaps `memory_lint.py` structurally cannot
see, because it scopes itself to `facts/` + the two reserved files by
design):

- `corpus/README.md` and `pending-links.md` both lack frontmatter entirely
  — non-reserved `.md` files inside the bundle tree, so SPEC §11 rule 1
  ("every non-reserved `.md` file... contains a parseable YAML frontmatter
  block") applies to them and neither carries one. This is the same gap
  `docs/okf-0.2-study-2026-08-23.md` §3 already found; reproduced here
  independently, on a live re-run, not carried over from that report.
- `log.md`'s own broken links (2 targets: a literal template placeholder
  `facts/<slug>.md` and a real dangling reference,
  `facts/shell-scripts-pass-shellcheck.md`, appearing twice) —
  `memory_lint.py`'s link-integrity check only reads `facts/` bodies, never
  `log.md`.
- Missing subdirectory `index.md` warnings for both `facts/` and `corpus/`
  — the spec's own convention is one `index.md` per directory (§3's tree
  diagram); `memory_lint.py` has no check for this at all, only for the
  root index's own cap.

**One finding worth naming on its own: the "wider" tool has a blind spot
the "narrower" one doesn't, on the exact same file.** `memory_lint.py`
flagged 1 fact with genuinely unparseable YAML (an unquoted em dash inside
a `title:` scalar breaking block-mapping parsing — a real PyYAML failure,
reproduced verbatim above). `validate_okf.py` did **not** flag this same
file as an error. Read its `parse_frontmatter()` directly (`validate_okf.py`
lines 269–294): it is a **hand-rolled, indentation-based block parser**,
not PyYAML (`memory_lint.py` uses real `yaml.safe_load`, confirmed at its
own line 165) — more tolerant of this specific malformed shape than a
strict YAML grammar is. Wider file-scope coverage did not mean stricter
per-file conformance checking here; the two tools are independently
implemented and can each miss what the other catches, in either direction.
This is itself an argument for running both rather than picking the
"more thorough-sounding" one and trusting it alone.

**Both catch, independently** — real cross-validation, not just overlap:
`facts/codex-as-second-harness.md` and `facts/topics-not-to-raise.md`
missing `description` are flagged by both tools, computed two different
ways, same two files. Nothing here contradicts the other tool; agreement
where they overlap is itself a small piece of evidence neither is
badly broken.

## Recommendation: keep running both. Do not extend `memory_lint.py`'s scope in this pass.

Three reasons, not one:

1. **The whole-tree gap `validate_okf.py` found (`corpus/README.md`,
   `pending-links.md`) is a classification question, not a scope bug** —
   `docs/okf-0.2-study-2026-08-23.md`'s own step 4 is "either give them
   `type`, or document explicitly that they're bundle housekeeping, not
   concepts, and exempt them by convention." Extending `memory_lint.py` to
   scan the whole tree *today* would mean either guessing that exemption
   now (out of scope for a report-only pilot) or immediately producing a
   new class of error this repo hasn't decided how to treat yet.
2. **`memory_lint.py`'s own value — near-duplicate detection, the
   contradiction heuristic, index-cap tracking against this vault's actual
   thresholds — has no equivalent in `validate_okf.py` and isn't a spec
   concept to begin with.** Widening `memory_lint.py`'s file scope doesn't
   threaten this value, but it also doesn't need `validate_okf.py`'s
   existence to justify keeping it as a *second*, differently-scoped tool
   rather than folding everything into one script.
3. **The em-dash finding above is a direct, load-bearing argument for
   redundancy, not just diversity of coverage.** Two independently
   implemented parsers just demonstrated they miss different real defects
   on the same live tree. Collapsing to one tool — however scope is
   drawn — removes that cross-check. `validate_okf.py` is
   community-maintained and will track future spec changes on its own
   schedule; keeping it in the loop is a live tripwire against
   `memory_lint.py`'s own conformance logic drifting from the spec without
   anyone noticing, the same "spec drift is invisible by design" problem
   `docs/okf-0.2-study-2026-08-23.md` §2 already named for the spec text
   itself.

**Revisit, not dismiss:** once step 4 settles whether `corpus/README.md`/
`pending-links.md` get frontmatter or a documented exemption, extending
`memory_lint.py`'s own conformance-floor check (frontmatter presence +
non-empty `type`) to the whole tree becomes a much smaller, well-scoped
change — at that point the two tools' file coverage would actually match,
and running both stays worthwhile for the parser-diversity reason above
regardless.

## What this pass did and did not do

- Ran both validators against the live vault, pasted real output, both
  runs. No vault write.
- Did not bump `okf_version`. Did not add frontmatter to `corpus/README.md`
  or `pending-links.md`. Did not decide their housekeeping-vs-concept
  status. All three are steps 3–5, separately reviewed vault writes or
  decisions, per this PR's own hard boundary.
- Did not modify either validator script.

Ref: agent-dotfiles#312, `docs/okf-0.2-study-2026-08-23.md` (steps 1–2 of
its recommended sequence).

Author-Lane: estate:2
