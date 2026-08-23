# build-3 — triage of the 446 unacknowledged corpus items (2026-08-23)

Repo for tooling/schema: `jonhill90/agent-supervisor`
(`scripts/supervisor/{cli.py,core.py}`). Ledger:
`~/.local/state/agent-dotfiles-supervisor/ledger.sqlite3` (not tracked in any
git repo — this file is the durable record of the pass itself, since the PR
diff otherwise has nothing to show).

## What this was

446 `items` rows with `status='open'` (`unacknowledged` view) — things the
operator said, extracted and judged into the corpus, that nobody had recorded
as acted on, dropped, or still pending. This pass classified every one of
them into `done` / `still open` / `obsolete` / `could not establish`, with
evidence, and wrote the evidenced ones back to the ledger. **Nothing was
implemented** — this is triage only, per the brief.

## Method

Split the 446 by `prompts.project` into 13 batches (one per project, split
further at 60 items/batch), dispatched one research agent per batch with
read/bash/grep/gh access into that project's real checkout, and required a
citation (a commit, file, PR/issue number, or command output) for every
classification — `could_not_establish` was the required answer when no such
citation existed, not a guess. 7 of 446 items were missed or had a
transcription-mangled id on the first pass; caught by diffing the merged
result set against the original 446 ids, and closed by hand using the same
evidence standard (cross-referenced against other items on the same topic
already classified in the same pass). Final merge: 446 in, 446 out, 0
duplicates, 0 missing — verified by set diff before any ledger write.

## Buckets, before and after

```
BEFORE (this pass, all 446 were status='open'):
  done                  -- n/a, not yet classified
  still_open            -- n/a, not yet classified
  obsolete              -- n/a, not yet classified
  could_not_establish   -- n/a, not yet classified

AFTER (this pass's classification of the 446):
  done                  224
  still_open (total)    128   -- of which 84 recommended for status=acknowledged
                                  (standing rules everyone already follows,
                                  not one-off tasks), 44 genuinely still open
  obsolete                7
  could_not_establish    87
  ------------------------
  total                 446
```

## Ledger writes (real command output, this pass)

Only `status` and `status_reason` were ever written. `weight`, `kind`,
`body`, and `resolved_to` were never touched, and no row was deleted —
closure is always a `status` + `status_reason` naming the evidence, per the
corpus's own rules.

- **`done` (224)** → `status='acted'`, `status_reason='triage(b3): <evidence>'`
- **`obsolete` (7)** → `status='dropped'`, `status_reason='triage(b3): <evidence, naming what superseded it>'`
- **`still_open` + recommended acknowledged (84)** → `status='acknowledged'`,
  `status_reason='triage(b3): <evidence that it's standing, already-followed practice>'`
- **`still_open`, no recommendation (44)** → left `status='open'` — genuinely
  still open, no write (see ranked list below)
- **`could_not_establish` (87)** → left `status='open'` — real uncertainty,
  not guessed into a bucket (see examples below)

```
$ sqlite3 ledger.sqlite3 "select status, count(*) from items group by status;"
-- BEFORE this pass (unacknowledged=446 were all status='open'):
acknowledged|418
acted|1816
dropped|2486
open|446
resolved|586

-- AFTER this pass:
acknowledged|502
acted|2040
dropped|2493
open|131
resolved|586
```

```
$ sqlite3 ledger.sqlite3 "select count(*) from unacknowledged;"
-- BEFORE: 446
-- AFTER:  131

$ sqlite3 ledger.sqlite3 "select count(*) from open_questions;"
-- BEFORE: 73
-- AFTER:  24

$ sqlite3 ledger.sqlite3 "select count(*) from live_parameters where weight='hard';"
-- BEFORE: 931
-- AFTER:  931   (unchanged -- this view filters on kind/weight, not status,
                  and weight was never touched by this pass)
```

502 + 2040 + 2493 + 131 + 586 = 5,752 total items, matching the corpus's own
prior total (446 open + everything already closed before this pass).

## The two examples the brief named, resolved

- **`agent_self_qa=required`** (`it-64cb23c92e91068c`, `it-3796820d0cf55051`) →
  **acknowledged**. It's written into DebateWho's AGENTS.md/CLAUDE.md as a
  standing rule ("Browser-verify before any 'fixed' claim... only the
  operator declares something fixed") and followed without exception in the
  transcripts read for this pass. This was exactly the "should almost
  certainly be live, not sitting unacknowledged" case the brief anticipated.
- **`ui_fidelity=1:1`** (`it-9202b15327fe27bf` and 3 earlier-recorded
  instances) → **acted**. Seven merged DebateWho commits explicitly chase
  "Manus parity" via a real pixel-diff/overlay toolchain (typography, colors,
  footer, spacing, badges) — a concrete, evidenced execution of the target,
  not just a standing rule.

## Obsolete (7), each with what superseded it

1. `minio=open_question` → MinIO Stage 3 (Hill90 PR #655): moved into
   platform scope with its own AppRole policies; the open question is
   answered.
2. `baseline=16_by_name_0_unhealthy` → superseded by the corrected baseline
   definition (`0 restarting` added explicitly, `platform-baseline-test.sh`).
3. "rebrand loop engineering to graph engineering" → `docs/
   agent-engineering-lineage.md` treats them as cumulative layers, not a
   replacement name; no rebrand happened or was needed.
4. Naming preference for "loom" → the product was named `steading`
   (agent-tui#42, seven rounds, ~60 candidates).
5. `app_name_fallback=loom` → same; `steading` was reached without needing
   the fallback.
6. "navbar inside/outside tmux needs more discussion" → settled by
   `SPEC-shell.md`'s later hard parameter, `ui_fidelity=1:1`.
7. "set up a Hostinger MCP for the web UI" → explicitly reversed in favor of
   CLI/terminal-only Hostinger access; `.mcp.json` only configures
   Playwright.

## Still open (44) — ranked, top items for the director

Of the 128 `still_open` items, 84 turned out to already be standing,
followed practice (recorded `acknowledged`, not left looking abandoned).
These 44 are the ones with no such evidence — genuinely unresolved. Ranked
by what looks most load-bearing to sequence next, hard-weight first:

1. **`resource_discipline=cap_concurrent_processes+sweep_stale_worktrees+check_load_before_dispatch+check_self_before_blaming_tooling`**
   — issue #500 (open) already investigated this exact directive and found
   the resource-discipline half "still unbuilt." Directly actionable.
2. **`escalation=only_when_unanswerable_from_repo`** — no hook or doc
   enforces this; the 2026-08-19 council audit found the opposite pattern in
   practice (52 status polls in 9 days).
3. **`lane_default=keep_working_not_idle`** — same audit found lanes idle/
   stalled, not the always-working topology this parameter describes.
4. **`tmux_topology=one_session_per_project`** — regressed; only one tmux
   session ("estate") exists as of this pass, confirmed live.
5. **"you had crons. where are they."** — confirmed by direct command: `crontab
   -l` returns empty, no cron/launchd jobs exist at all. A real operational
   gap, not answered by this pass.
6. **`hill90_project_management=delegated_to_agent`** / "are the worker lanes
   actually delivering value" — the 2026-08-19 council audit's findings
   (stalled loop, 162 ephemeral lanes, a built-but-uncalled ACP mechanism)
   directly bear on this and were never resolved.
7. **`poller_inbox=in_app_services`** — the Telegram poller was moved out of
   a tmux window into a LaunchAgent, but was never folded into the
   agent-tui/steading application as the directive asked.
8. **`approle_policy=exact_declared_paths`** — MinIO's three legacy
   over-grant policies (`admin`/`editor`/`viewer`) were explicitly deferred,
   not retired, per Hill90's own decision doc.
9. **`skill_scope=public|project|work|personal`** — only two of the four
   scopes exist today (public, personal-private); no distinct project or
   work tier.
10. **Browser automation Jon watches must be headed, not headless** —
    DebateWho's Playwright MCP is still hardcoded `--headless` with no
    headed alternative.

Full list of all 44 (ids, bodies, and evidence) is in the ledger itself —
`status='open'`, no `status_reason` — queryable via
`cli.py --state-dir ~/.local/state/agent-dotfiles-supervisor` or direct
`sqlite3` against `unacknowledged`.

## `could_not_establish` (87) — a sample, not guessed into a bucket

Left `status='open'`, no write, because no repo artifact could confirm or
refute them either way — mostly one-off ephemeral session actions (open a
browser demo, restart a specific lane), personal/private facts (VPS
credentials, a conversation with a friend), or vague multi-part wishlists
too compound to score as one claim. Examples: "Open Playwright to claude.ai
so Jon can log in and demonstrate the flow" (an ephemeral action with no
artifact either way); "is anything running on the DebateWho Tailscale right
now" (a point-in-time question with no log to check); a stated preference
for plain, short language with no written rule to test compliance against.

## What this does not establish

- Whether the `acknowledged` recommendation is right for every one of the 84
  — each carries a citation, but "everyone already follows this" is a
  judgement call, not a mechanical check; worth a second read if any of them
  turn out to be contested later.
- Whether the 87 `could_not_establish` items are truly unknowable or just
  under-searched — this pass used `git log`/`gh`/`grep` per project, not an
  exhaustive audit of every private note or Slack-equivalent channel.
- Nothing about the 315 non-`could_not_establish`/non-still-open items was
  re-verified by a second reader; per the brief, this PR needs an
  independent review before the classifications are trusted, same as any
  other PR here.

## Verification

```
$ python3 -c "
import json, sqlite3
merged = json.load(open('merged.json'))
con = sqlite3.connect('ledger.sqlite3')
cur = con.cursor()
missing = 0
for item_id in merged:
    cur.execute('SELECT status FROM items WHERE id=?', (item_id,))
    row = cur.fetchone()
    if row is None:
        missing += 1
print('rows checked:', len(merged), 'missing from db:', missing)
"
rows checked: 446 missing from db: 0
```

```
$ sqlite3 ledger.sqlite3 "select count(*) from items;"
5752
```

## Constraints held

- Nothing was deleted. Every closed item carries a `status_reason` naming
  its evidence.
- No `weight` conversions between `hard` and `preference` — never touched.
- No wording softened — `body` was never touched.
- No new implementation work done; this is triage only. Anything in the
  still-open list that looks urgent is named above for the director to
  sequence, not started here.
