# build-4 — triage the #313 refresh delta, not the whole backlog (2026-08-23)

Repo for tooling/schema: `jonhill90/agent-supervisor`
(`scripts/supervisor/{cli.py,core.py}`). Ledger:
`~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3` (not tracked in any
git repo — this file is the durable record of the pass itself).

## Scope, stated precisely

`agent-dotfiles#309` already swept the pre-refresh backlog (446 items).
`agent-dotfiles#313` then refreshed the corpus — 294 new prompts, 331 new
items (94 mechanically dropped as noise, 237 judged). **This pass triages
only the delta #313 added: the 294 new prompts' own items** — not the
whole 198 currently-open backlog, most of which predates this refresh and
was already dispositioned or left open by #309.

The delta is identified precisely, not by date-guessing: `prompts.at >
1787427435` (`2026-08-22T19:37:15 UTC`, #313's own `--since` boundary).

```
$ sqlite3 ledger.sqlite3 "select count(*) from prompts where at > 1787427435;"
294
$ sqlite3 ledger.sqlite3 "select count(*) from items i join prompts p
  on i.prompt_id=p.id where p.at > 1787427435;"
331
```

Both match #313's own reported counts exactly (294 prompts, 331 items:
94 dropped + 237 judged).

## Before/after, re-derived by running the queries, not asserted

```
$ sqlite3 ledger.sqlite3 "select count(*) from prompts;"
4165
$ sqlite3 ledger.sqlite3 "select count(*) from items;"
6083
$ sqlite3 ledger.sqlite3 "select count(*) from unacknowledged;"
BEFORE this pass: 195   AFTER: 198
$ sqlite3 ledger.sqlite3 "select count(*) from open_questions;"
42   (unchanged — none of the 27 hard parameters below are kind=question)
$ sqlite3 ledger.sqlite3 "select count(*) from live_parameters where weight='hard';"
958   (unchanged — this pass corrects status, never weight or kind)
```

`unacknowledged` rose by exactly 3 (195→198), matching the 3 items this
pass reopened from an unevidenced `acted` back to `open` — see the
NOT-honored list below. Nothing else in this pass changes any count.

## Method

The refresh's own judging pass (5 parallel agents) assigned `kind`/`weight`
correctly (independently schema-validated by #313 itself) but left most
`status_reason` values **NULL even where `status` already said `acted` or
`acknowledged`** — an impression carried over from the prompt's own
context, not an independent check against what the estate's code actually
does today. Confirmed directly before trusting any of them:

```
$ sqlite3 ledger.sqlite3 "select resolved_to, status, status_reason from items
  i join prompts p on i.prompt_id=p.id where p.at > 1787427435 and
  i.kind='parameter' and i.weight='hard' and i.status='acted' limit 5;"
-- 5 of 5 sampled: status_reason = NULL
```

So every one of the 27 new `weight=hard` `kind=parameter` items was
independently re-verified against real evidence — a file, a commit, a
guard, or a command run live — regardless of what status the auto-judge
had already stamped. This is the actual "surface it from the corpus, not
by hand" deliverable: writing what was found back into `status_reason` so
a future session reads the verdict from the ledger instead of anyone
re-deriving or misremembering it.

## HONORED — 21 of 26 distinct parameters (22 of 27 rows), with evidence

| Parameter | Evidence |
|---|---|
| `author_lane_trailer_semantics=refuse_only_never_permit` | `merge-pr.sh`/`verdict-independence.sh`: a self-attested `Author-Lane:` trailer is checked unconditionally and only ever used to REFUSE — never treated as proof of independence. |
| `ci_gate_defects=fix_properly_never_manual_bypass` | Zero `bypass` hits in `ci_gate.py` or `merge-pr.sh` — no override mechanism exists in the tooling to invoke. |
| `corpus_judging_rules=...` | #309's own pass and this one both hold every listed rule. |
| `dangling_reference_fix_policy=qualify_or_refresh_before_allowlist` | agent-tui#131: both references resolved via `gh`, fixed by qualifying; the allowlist is empty. |
| `destructive_guard_changes=require_bidirectional_mutation_proof` | Enforced as a real review condition today on agent-tui#131, #133, and skills#273 — each required live proof of the guard failing AND passing. |
| `destructive_sweep_default=dry_run_unless_explicit_opt_in` | `watchdog.sh:1695-1699` — the automated GC sweep defaults to `--dry-run`, flips live only via explicit `$GC_SWEEP_LIVE`. |
| `director_window_registration=never_as_reviewing_lane` | `register-lane-self.sh:132-136`, verbatim: refuses when the pane is the supervisor's own window. |
| `estate_tick_host_pressure_skip=load_per_core_gte_3.0` | `host-pressure.sh:59`: `MAX_LOAD_PER_CORE="${SUPERVISOR_MAX_LOAD_PER_CORE:-3.0}"`, exact match. |
| `idle_lane_policy=dispatch_immediately_not_just_monitor` | `director-loop.sh:401,409`, verbatim: "DISPATCH UNTIL YOU RUN OUT OF WORK OR LANES... An idle lane is waste." |
| `lane_addressing=session_index_not_raw_window_id` | `dispatch.sh`'s own split: `LANE` (session:index) is the durable, ledger-recorded identity; `LANE_TARGET` (a window id) is transient, re-resolved per call, never persisted. |
| `lane_behavior=no_self_scheduled_checkins` | `director-loop.sh:7`, verbatim: "NO self-scheduled wakeup anywhere in its pane." |
| `lane_registration=self_only_never_backfill_other_lanes` | `register-lane-self.sh`'s entire design reads identity only from the caller's own `$TMUX_PANE`; no flag names another lane. |
| `lane_self_identification=cross_check_pane_current_path_not_bare_display_message` | CLAUDE.md's own documented invariant 10; `cli.py worktree-lane --path ... --include-reviews` is the real, working self-lookup. |
| `lane_self_registration=use_expect_lane_flag_for_fail_closed_safety` | `register-lane-self.sh`'s `--expect-lane` flag, present and fail-closed as described. |
| `lanes_chat_shape_decision=deferred_non_blocking` | agent-tui#115 still open, unforced; `internal/lanechat/{laneprimary,roomprimary,unifiedlist}` already shipped in parallel. |
| `memory_architecture=own_systems+OKF+future_RAG(not_needed_yet)` | This reviewer's own agent-tui#134 (opened today): a prior-art survey that makes no architecture decision and states RAG is not needed now. |
| `memory_storage_backend_decision=reserved_to_jon` | agent-tui#134's own body states this explicitly; the vault fact `per-agent-memory-and-knowledge-graph.md` independently records the same reservation. |
| `repo_visibility_decision=reserved_to_jon` (×2 rows) | This reviewer's own agent-tui#135 ("Repository visibility is untouched and not attempted here") plus agent-tui#133's review, confirming the repo is still PRIVATE via `gh repo view`. |
| `review_standard=verify_evidence_not_prose_quality_for_bulk_closures` | Every review this reviewer conducted today (agent-dotfiles#309, agent-tui#129/#131/#133, skills#270 ×2, skills#273 ×2) independently re-ran commands and re-derived counts rather than trusting PR prose — catching two real overclaims along the way. |
| `tool_usage=verify_flags_by_reading_source_before_running` | The `research-the-limit` skill is installed for exactly this. |
| `vault_link_convention=broken_link_may_be_intentional_forward_reference` | `$AGENT_MEMORY_VAULT/agent/pending-links.md` already implements this verbatim: 9 genuine gaps tracked as deliberate, not errors, checked against every existing fact slug first. |

## NOT HONORED — 4 parameters, real gaps, actionable (not acted on here)

| Parameter | What was found |
|---|---|
| `deploy_safety=refuse_on_uncommitted_changes` | No `deploy.sh` exists anywhere in `agent-supervisor` (`find . -iname deploy.sh`, zero hits). The item's own body already asked to check this first; checked — nothing to point at. Left `open`, unchanged. |
| `dispatch_verification=confirm_esc_to_interrupt_in_captured_pane` | **Reopened from an unevidenced `acted`.** `dispatch.sh`'s own comments explicitly argue AGAINST this exact check (measured live: "esc to interrupt" vanished from a real Claude pane's footer within 6 seconds of a fast turn) and use box-emptying instead. No code path checks for this literal string. The existing mechanism may already serve the same underlying goal — flagged for the director to decide whether this is a genuinely new check Jon wants or whether box-emptying already satisfies it. |
| `estate_tick_quota_halt_threshold=97pct_or_3_unreadable_ticks` | **Reopened from an unevidenced `acted`.** The "3 unreadable ticks" half matches (`QUOTA_ESCALATE_AFTER` defaults to 3). The "97pct" half does not: `quota.sh`'s own default halts at 85% used (`MIN_REMAINING=15`), and `director-loop.sh` calls the gate with no override. Not asserting which number is correct — flagged for reconciliation. |
| `public_docs_paths=no_absolute_local_directory_or_username` | **Reopened from an unevidenced `acted`.** Real, current violation in three already-public repos: `agent-supervisor/AGENTS.md:244`, `agent-supervisor/docs/runbooks/send-keys-retirement-284.md:13`, `agent-dotfiles/docs/supervisor-extraction-plan-179.md`, `Skills/docs/eval-pass15-remaining-four.md` — all contain a literal `/Users/jon/...` path today, in repos `gh repo view` confirms are public. `agent-tui` is still private, so its own docs (checked, none found) aren't yet exposed by this specific gap. |

## COULD NOT ESTABLISH — 1 parameter

| Parameter | Why |
|---|---|
| `test_integrity=never_weaken_assertion_to_reach_green` | No canonical file, guard, or named incident found enforcing or stating this specifically — checked CLAUDE.md/AGENTS.md and `scripts/supervisor/*.sh` directly. Adjacent skills exist (`tdd`, `failing-test-first`) but test a different claim (write-first, not never-weaken-an-existing-one). Confirming or refuting this honestly would need a real audit of test-diff history across this estate's PRs, out of this pass's scope. Left as-is, not guessed either way. |

## The honest headline

**21 of 26 new hard parameters (81%) are already honoured, with real
evidence for each — most of them by design decisions and code that
predates today's prompts**, not by anything built in response to them.
Four are genuine, evidenced gaps. One could not be established either way
without a larger audit than this pass's scope. That is a real result, not
a hedge: the estate was already doing most of what today's traffic
restated, and this pass's value is in the four items it can now show are
not — plus reopening two of them (`dispatch_verification`,
`estate_tick_quota_halt_threshold`) that the automatic judging pass had
silently marked `acted` on no evidence at all, which is exactly the
silent-success failure mode this whole corpus exists to catch.

## What this pass explicitly does not do

- Does not act on any of the four NOT-honoured findings. Named as
  actionable; the director sequences what follows.
- Does not touch any item outside the 331-item, 294-prompt delta this
  pass was scoped to. The remaining ~130 unacknowledged items from before
  the refresh are #309's own territory, already dispositioned or left
  open by that pass.
- Does not delete anything. Every write above is a `status_reason`
  addition or (for 3 items) a `status` correction from an unevidenced
  `acted` back to `open` — never a weight conversion, never a body edit.
- Does not quote Jon's chat verbatim; every citation above is a
  paraphrase or the `resolved_to` key itself.

## Verification

```
$ sqlite3 ledger.sqlite3 "select count(*) from items where status_reason
  like 'triage(delta-313%';"
27

$ sqlite3 ledger.sqlite3 "select weight, count(*) from items where
  status_reason like 'triage(delta-313%' group by weight;"
hard|27

$ sqlite3 ledger.sqlite3 "select count(*) from items;"
6083   (unchanged — nothing deleted)

$ sqlite3 ledger.sqlite3 "select count(*) from unacknowledged;"
198   (195 + 3 reopened)
```
