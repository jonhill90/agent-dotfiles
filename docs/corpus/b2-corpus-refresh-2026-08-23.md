# build-2 — corpus refresh, 21.5 hours stale (2026-08-23)

Repo for tooling/schema: `jonhill90/agent-supervisor`
(`scripts/supervisor/{mine_prompts.py,itemize_prompts.py,cli.py,core.py}`).
Ledger: `~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3` (not
tracked in any git repo — this file is the durable record of the pass
itself, since the PR diff otherwise has nothing to show).

## Why this ran

Measured, not assumed, at dispatch: newest prompt in the corpus was
`2026-08-22T19:37:15 UTC`; the extraction pipeline had simply not been run
since then. A full day of directives — including durable direction on
memory, knowledge, OKF, RAG, and the eval instrument — existed only in
transcripts, not in anything queryable.

**Instrument warning, reproduced before trusting anything downstream of
it:** `find ~/.claude/projects -name '*.jsonl' -newermt '@<epoch>'` is
unreliable on this machine's BSD `find` (an `@epoch` argument silently
returns wrong counts rather than erroring); `-mtime -1` and a literal
`-newermt` date string both gave consistent, sane, non-zero counts in the
high 400s. Cross-checked two working forms against each other before
believing either.

## Pipeline run, per the `prompt-corpus` skill

```
python3 scripts/supervisor/mine_prompts.py --since 2026-08-22T19:37:15 --store
python3 scripts/supervisor/itemize_prompts.py --drop-noise
<12-agent dynamic workflow: 5 parallel judges + 1 serial loader>
```

`.claude/workflows/corpus-itemise.js` (the skill's own named workflow) is
not on `agent-supervisor`'s `main` — it exists only on the unmerged
`feat/prompt-corpus-skill` branch, exactly the gap that branch's own
`SKILL.md` flagged as "could not measure." Adapted from that branch's copy
for this run (path/scratch-dir updated to this pass's own worktree, chunk
count reduced from 12×40 to 5×40 to match this batch's real size) rather
than run un-adapted against stale paths from a prior session.

294 new prompts stored (1 already present at the `--since` boundary,
handled idempotently by `mine_prompts.py`'s own hashed-id logic — expected
overlap, not a bug). `--drop-noise` mechanically excluded 94 as
agent/system-authored **before any model saw them** — 79 dispatch-brief
templates, 15 skill-router boilerplate, matched on the same structural
markers this corpus has used since `agent-supervisor#313`, never on topic. The remaining 200
were judged by 5 parallel agents (40 each) against the skill's own rules,
then loaded by one serial agent to avoid the twelve-concurrent-writers
contention the skill's own doc warns about.

## Counts, before and after — re-derived by running the queries, not asserted

```
                              BEFORE      AFTER
prompts                        3871       4165
unjudged (no items row)           0          0   (peaked 294 → 200 after
                                                    mechanical drop-noise →
                                                    0 after judging+load)
items                           5752       6083   (+331: 94 mechanical
                                                    drops + 237 judged)
open_questions                    24         42
unacknowledged                   131        195
live_parameters (weight='hard')  931        958
```

One correction made to my own bookkeeping before writing this doc: an
intermediate query run mid-pass (after `--drop-noise`, before the judged
items loaded) briefly read `items=5846` and was almost reported as "before"
— it was actually mid-pass, already including the 94 mechanical drops.
The true pre-pass baseline (5752) was reconstructed and cross-checked
directly: `5752 + 94 (drop-noise) + 237 (judged) = 6083`, matching the
final count exactly. Reporting the corrected number rather than the one
first captured.

`drop`/`keep`/`rename` have no equivalent in this corpus (those are the
skills-eval-loop's vocabulary, not the prompt corpus's) — not applicable
here.

## Idempotency — re-verified independently, not trusted from the load agent's own report

Re-ran `itemize_prompts.py --load` against all 5 judged files myself,
separately from the workflow's own serial loader:

```
itemized: 0 items written, 46 already present   (judged-0.json)
itemized: 0 items written, 45 already present   (judged-1.json)
itemized: 0 items written, 50 already present   (judged-2.json)
itemized: 0 items written, 56 already present   (judged-3.json)
itemized: 0 items written, 40 already present   (judged-4.json)
```

`items` total unchanged at 6083 after all five re-loads. Idempotent across
every file, not just the one file the workflow's own agent happened to
re-check.

## Judged-content validation, before trusting any of it

- **All 200 unitemised prompts got an entry — none omitted.** Compared the
  200 unique `prompt_id`s across the five `chunk-*.json` extracts against
  the 200 unique `prompt_id`s across the five `judged-*.json` outputs:
  identical sets, exact match.
- **Schema axes held.** Across all 237 judged items: `kind` values seen
  are exactly `{parameter, question, directive, thought, correction}`;
  `weight` values seen are exactly `{hard, preference, retracted}` — no
  `preference` leaked into `kind` (the schema-error trap the skill's docs
  name explicitly), no unrecognized value in either axis.
- **No missing `body`.** Would have crashed the loader; checked directly
  before loading, not inferred from a clean load.

## What landed as `hard` — the durable direction this pass exists to surface

27 new `weight=hard` parameters, all from today's traffic. The three
directly answering what motivated this refresh (memory/knowledge/OKF/RAG):

- `memory_architecture=own_systems+OKF+future_RAG(not_needed_yet)` — the
  end state combines the estate's own systems with OKF plus a RAG built or
  adopted later; RAG itself is explicitly not needed now.
- `memory_storage_backend_decision=reserved_to_jon` — the vault's
  storage-backend choice (SQLite, vector, pgvector, Qdrant, OKF, graphify)
  is his alone; no other work should prejudge or touch it.
- `vault_link_convention=broken_link_may_be_intentional_forward_reference`
  — a broken `[[wikilink]]` is not automatically an error; it must be
  classified (typo/rename vs. deliberate forward reference) before being
  touched, never silently repointed or deleted to make it resolve.

The remaining 24 span estate-tick operational limits (quota-halt and
host-pressure thresholds), lane identity/registration discipline (four
separate parameters on this theme alone — self-registration-only,
`pane_current_path` cross-checks over bare `display-message`, session:index
addressing, `--expect-lane` fail-closed), merge/review/test-integrity
rules, and two repeated `repo_visibility_decision=reserved_to_jon`
parameters from two different prompts on two different repos (agent-tui,
and the estate generally) — recorded as two rows since they're two distinct
constraining statements, not deduplicated.

Full list of all 27 `resolved_to` keys is in the ledger
(`live_parameters where weight='hard'`, filtered to today's `prompts.at`);
not reproduced verbatim here to keep this doc from becoming a second copy
of the record it's citing.

## Constraints held

- Nothing deleted — noise excluded via `status='dropped'` with a
  `status_reason`, same as every prior pass.
- `resolved_to` used only for constraining parameters; questions and
  one-off directives left without one (confirmed via the schema
  validation above, which would have surfaced a `kind=question` row with
  a `resolved_to` as a shape anomaly — none found).
- Tone not softened — spot-checked several judged bodies against their
  raw prompts by hand; blunt stayed blunt.
- Jon's own words are not quoted verbatim in this document, per standing
  rule — every citation above is a paraphrase or the `resolved_to` key
  itself.

## Verification

```
$ sqlite3 ledger.sqlite3 "select count(*) from prompts;"
4165
$ sqlite3 ledger.sqlite3 "select count(*) from prompts p left join items i
  on i.prompt_id=p.id where i.id is null;"
0
$ sqlite3 ledger.sqlite3 "select count(*) from items;"
6083
$ sqlite3 ledger.sqlite3 "select count from possibility_count;"
958
$ sqlite3 ledger.sqlite3 "select count(*) from unacknowledged;"
195
$ sqlite3 ledger.sqlite3 "select count(*) from open_questions;"
42
```
