# Loop signals

**Note (added 2026-08-23):** `scripts/supervisor/` and `tests/supervisor/`
were removed from this repository in commit `2925720` (#265, 2026-08-12)
and now live in `jonhill90/agent-supervisor` (private) — confirmed by
`git ls-files scripts/supervisor tests/supervisor` returning no files here.
This document's file:line citations below (`watchdog.sh`, `lanes.sh`,
`dispatch.sh`, `sleepcheck.py`, `inbox-poll.sh`, `cli.py`, `core.py`,
`adapter.py`, `github_source.py`, etc.) describe that tree as it stood one
day earlier, when this document was written — a historical record of the
signal enumeration, not a description of this repository's current code.
This mirrors the notes already carried by `docs/supervisor-disposition.md`,
`docs/supervisor-extraction-plan-179.md`, and `docs/loop-engineering.md`
for the same split; `2925720`'s own commit message explains why this
document specifically was left uncorrected at the time ("its subject is
analysis/convention, not the tree itself").

Enumeration of the signals that can drive the supervisor loop — part 2 of
[#173](https://github.com/jonhill90/agent-dotfiles/issues/173). Part 1 (the
VPS tmux-plugin experiments) is recorded on that issue and is untouched here;
this document does not close #173.

Jon's original framing: *"Signal #1 is the loop I think — tell me all the
possible signals."* Three kinds came out of that conversation. This
enumerates from the code as it stands today, not from the conversation's
memory of it — several call sites moved in the hours before this was
written (#183, #200, #206, #208, #217), and where the code disagrees with
#173's summary, the code wins.

Every signal below is classified by the "tmux is not a database" authorship
test from this repo's `AGENTS.md`: did *this system* write the value (a
**record**), or did tmux/the kernel produce it as a byproduct (a
**measurement**)?

## Kind 1 — "wake up, there may be work"

Well covered, three ways:

**Self-scheduled wakeup.** The Director's own `/loop` re-arms itself with
`ScheduleWakeup` at the end of each tick (`loop-tick.md:122`, "Never stop the
loop"). *Observed, not authored by this codebase* — it is a harness runtime
primitive; `sleepcheck.py` reads it back out of the live transcript
(`decide_liveness`, `sleepcheck.py:47`) rather than trusting a cooperating
writer, for the same reason completion is never inferred from echoed prompt
text. **Status: works.** Verified 2026-08-11 against a real transcript
showing 11 `ScheduleWakeup` calls and zero crashes while `watchdog.sh` kept
restarting a healthy loop (`sleepcheck.py:8-16`) — the fix for that
misreading is `sleepcheck.py` itself, called from `watchdog.sh:468`.
**Failure mode:** none currently silent — `sleepcheck.py`'s unknown branches
all fail toward "not asleep" (`sleepcheck.py:52-56`), which trades a
redundant restart for the cost of a truly dead loop going unnoticed.

**launchd/cron.** `watchdog.sh` runs from a LaunchAgent every 180s
(`watchdog.sh:9-29` header, `com.jonhill.supervisor-watchdog.plist` per
`watchdog.sh:78`) and restarts the Director's pane with a fresh `/loop`
prompt when idle with actionable work (`watchdog.sh:566-576`). *Authored*:
`watchdog.status` (`watchdog.sh:163-227`) is this system's own record of
every tick's decision. **Status: works**, with one open gap of its own kind:
nothing watches the watchdog to the same degree it watches the loop
(`watchdog.sh:72-82`) — if the LaunchAgent itself stops firing, nothing
pages anyone. That gap **is** filed, as [#170](https://github.com/jonhill90/agent-dotfiles/issues/170)
(closed 2026-08-12, "watchdog's 'what watches the watcher' comment
overstates what is wired for its own staleness"): the fix that closed #170
was correcting the comment to say so honestly, not wiring an observer, so
the underlying gap this paragraph describes is still open — only its
documentation changed. `watchdog.sh:72` itself now cites `#170` in the same
sentence this document draws from.

**Telegram inbound.** `inbox-poll.sh` long-polls Telegram
(`inbox-poll.sh:1-40`) and routes every message to the Director via
`director-route.sh` the instant it arrives (`inbox-poll.sh:262`,
`director-route.sh:1-9`). *Authored*: `director-inbox.sh post` durably
queues the message before any live delivery is attempted
(`director-route.sh:27-33`), so a message is never lost even if the pane is
busy. **Status: works.** `director-route.sh --flush` retries live delivery
every iteration regardless of whether a new message arrived
(`inbox-poll.sh:297-308`), so a queued message does not wait for the
Director's own next scheduled wakeup.

## Kind 2 — "a lane finished" — the scarce one

Every completion signal that works today is either cooperative or inferred.
**Nothing records completion except by the worker's own choice to say so.**

**`tmux wait-for` (cooperative).** The worker's brief ends with `tmux
wait-for -S <channel>` as its literal last instruction (SPEC §14.1,
`lane-done.sh:17-21`). `lane-done.sh` blocks on the bare form
(`lane-done.sh:108`), confirms the window still carries the expected task name
(`lane-done.sh:113-117`), then calls `cli.py record-completion`
(`lane-done.sh:139-145`), which transitions the task to `complete`
(`core.py:1062`, `cli.py:326-347`). *Authored* end to end: the channel fire
is tmux's own primitive but the *decision* to treat it as completion, and the
ledger write that follows, are this system's. **Status: works when the
worker cooperates, and only then.** **How it fails, and whether silently:**
a worker that dies, is interrupted, hits an API error, or simply stops before
its last line never sends the signal (`lane-done.sh:84-87` — `wait-for` has
no timeout, "an accepted, already-documented limit"). From outside, that
lane is indistinguishable from one still working. **This is silent**: no
error, no log line, nothing — the lane just never completes.

**Pane-scraping (`lanes.sh`, inferred/observed).** `lanes.sh` classifies
every lane by reading the pane's own content — `pane_current_command` for
dead vs. alive (`lanes.sh:251`), the status line's last line against a
per-harness ready/busy/blocked regex (`lanes.sh:216-331`), and
`#{window_activity}` to distinguish hung from busy (`lanes.sh:294-310`).
*Wholly observed*: every field it reads (`pane_current_command`,
`window_activity`, `pane_in_mode`, `pane_pid` via `ps`) is tmux/kernel output,
per `lanes.sh:185-197`'s single `list-panes` call. Its ten states (header
comment, `lanes.sh:7-18`) do not include "finished" as a distinct state —
`free` is what an idle-and-ready pane looks like whether the previous task
just completed or the lane was never given one. **Status: partial, and
deliberately so.** `lane-done.sh:12-21` explains why reclaiming on
idle-alone was tried and rejected: it nearly destroyed a posted verdict by
racing a lane that looked idle but was holding an unposted result
(#102). **Failure mode:** by design, this cannot tell "finished" from "idle
between tool calls" or "blocked holding an unposted verdict" — the three
read identically to `capture-pane`, which is exactly why `lane-done.sh`
exists as a second, cooperative mechanism rather than trusting this one.

**Ledger dispatch/completion records (#144, authored).** `dispatch.sh` calls
`cli.py record-dispatch` after every successful send
(`dispatch.sh:834-859`), which writes the lane, the task, and a
`source_tasks` row derived from what the dispatch itself just observed —
not from a marker that no issue in the estate carries
(`cli.py:224-323` docstring). This is a **record**: `Ledger.record_dispatch`
(`core.py:879`) does five writes in one transaction, terminating at status
`delivered` (`core.py:105-146` schema comment) — not `complete`. Nothing in
the dispatch path ever calls `accept` or advances a task past `delivered` on
its own; the only writer of `complete` for one of these tasks is
`record_completion` (`cli.py:326`), which only runs from `lane-done.sh`,
which only runs after `wait-for` fires. **So the ledger's own "finished"
state is gated entirely on the cooperative signal above** — #144 gave the
loop a durable place to record completion, but nothing yet writes to it
except the same mechanism that already silently fails to fire.
`lane_available` (`core.py:574`, read through `cli.py lane_free`,
`cli.py:140-221`) answers `False` for any task not in
`(complete, failed, cancelled)` — so a lane stuck at `delivered` reads
occupied forever, correctly reflecting that nothing told the ledger
otherwise, but with no way for the ledger to notice that on its own.

**Scoped out: the ledger's `attention:`/`completion:` events.**
`Ledger.observe_attention` (`core.py:1105`) and the `completion:<task>`
event `Ledger.complete` inserts as a side effect (`core.py:1099`, noted in
`record_completion`'s own docstring at `cli.py:326-347`) are both
**authored** records in the same sense as `record-dispatch`/
`record-completion` above. They are left out of the enumeration above
because nothing in this estate's running supervisor writes them today:
`observe_lane`/`observe_attention` are called only from `adapter.py`
(`adapter.py:133-138`), and no `.sh` script under `scripts/supervisor/`
calls into `adapter.py` at all (`grep -rn "adapter.py\|observe_lane("
scripts/supervisor/*.sh` returns no hits) — they belong to the ledger
supervisor variant that `docs/supervisor-disposition.md` documents as the
one of the two supervisors that "has never run" (its own §5 phrasing, on
the ledger generally). A signal nothing calls cannot be evaluated by this
document's own four-column test (status, failure mode) without inventing
a caller, so this is named rather than silently dropped.

**The measured cost.** On every supervisor tick tonight (2026-08-12),
lanes that had finished and shipped — an open PR, a merged PR, a posted
verdict — sat in the ledger at `delivered`, never `complete`, because the
worker never reached its `wait-for` line. `lane_free` therefore answered
`false` and the capacity was invisible to `dispatch.sh`'s own `--free`
candidate loop (`dispatch.sh:180-186`). The supervisor released them by
hand, recorded by the operator across the session at `cli.py status`: two
lanes, then seven, then six, then two more — roughly seventeen manual
reconciliations across about three hours. This is recorded by the
supervisor operator tonight, not read off a committed artifact; no file in
this repository logs the count, so treat it as an operator's tally, not a
file you can `cat`.

**Who owns the fix.** Choosing between a ledger write, a wrapper that
reports the worker's real exit, a harness hook, or something else is a
design question this document does not answer — **#16** is the open
umbrella issue for that decision.

## Kind 3 — "something is wrong"

Well covered.

**Dead-man / hung / blocked (`lanes.sh`, observed).** `hung` fires when a
pane looks busy but `#{window_activity}` has not advanced for
`HUNG_AFTER` (180s default, `lanes.sh:164-168`, `294-310`) — tmux's own
timestamp, chosen specifically because a harness's own footer can print an
unchanged byte string for up to a minute while genuinely alive
(`lanes.sh:296-303`). `menu-blocked`/`text-blocked` fire on a per-harness
footer marker (`lanes.sh:267-293`). All three are pure measurements — no
write, just a read of pane state — and are correctly withheld from `--free`
(`lanes.sh:339-343`). **Status: works.** **Failure mode:** none silent — the
human-readable table names every blocked/hung/unknown count explicitly
(`lanes.sh:374-387`).

**Escalation (`watchdog.sh`, authored).** After `MAX_RESTARTS` restarts
inside `ESCALATE_WINDOW`, the watchdog stops restarting and pages a human
instead of trying again (`watchdog.sh:502-518`). *Authored*: `report()`
(`watchdog.sh:163-227`) writes `watchdog.status` on every exit path and
drives `watchdog_notify.py`, which dedupes to one delivered message per
escalation episode (`watchdog_notify.py:1-18`). **Status: works.**
**Failure mode, and it is named, not hidden:** if the notify send itself
fails, `report()` records `notify: FAILED — escalation did NOT reach a
human, retrying next tick` (`watchdog.sh:219-226`) — visible in the one
file a human reads, not swallowed.

**Stale heartbeat (#163, authored).** `inbox-poll.sh` writes
`inbox-poll.status` every iteration (`inbox-poll.sh:160-169`) and pages Jon
itself via `trap report_stop EXIT`/`TERM`/`INT`/`HUP`
(`inbox-poll.sh:200-217`) — but SIGKILL runs no userspace code at all
(`inbox-poll.sh:51-58`), so a killed poller's heartbeat simply stops
advancing with no self-report. `watchdog.sh` closes that gap: on every exit
path, `check_inbox_heartbeat()` (`watchdog.sh:348-364`, wired via the
`on_exit` trap at `watchdog.sh:422-428`) calls `watchdog_notify.py --mode
heartbeat` against `inbox-poll.status`, with the staleness threshold derived
from `POLL_TIMEOUT` rather than a round number
(`watchdog.sh:85-97`: `2*(POLL_TIMEOUT+80)`, 210s by default). Verified
against the current code: this matches #163's own description exactly — the
threshold is derived, not hardcoded; a missing status file and a stale one
are distinguishable (`watchdog_notify.py`'s heartbeat mode takes the same
episode-gated dedup path as escalate, so a poller that never started and one
that died both get a distinct, non-repeating report); and the poller's own
clean-exit page (`report_stop`) and the watchdog's heartbeat page are two
different code paths reading two different files, so a clean stop does not
double-page. **Status: works, and #163 is closed correctly** — no drift
between the issue and the code.

## Cross-check against related issues

- **#144** (ledger records lane state, merged) shipped the write-only
  `record-dispatch`/`record-completion` pair. As detailed above, both are
  now *called* — `record-dispatch` from `dispatch.sh:834-859`,
  `record-completion` from `lane-done.sh:139-145` — which is further along
  than #144's own "nothing reads either record" (its closing line at the
  time it merged). What still isn't true: nothing advances a
  `record-dispatch`ed task past `delivered` except the same cooperative
  `wait-for` signal that Kind 2 above shows is the whole gap. #144 solved
  "where would a completion record live," not "what makes one get written."
- **#163** (heartbeat alarm, closed) — current code matches its description
  with no drift; see above.
- **#209** (since merged — corrected 2026-08-23, was "open, in flight";
  `gh issue view 209` reports state `MERGED`; the current state of
  `dispatch.sh`/`core.py` can only be checked in `jonhill90/agent-supervisor`
  now, per the note at the top of this document) closes `dispatch.sh`'s lane-*selection*
  TOCTOU with an atomic `claim-lane`/`release-lane-claim` pair in
  `core.py`. As of this writing `dispatch.sh` contains no `claim-lane` call
  (`grep -c claim-lane scripts/supervisor/dispatch.sh` → 0) — `lane-free`
  (`dispatch.sh:180-186`) is still a query, not a claim, exactly as
  `cli.py lane_free`'s own docstring says (`cli.py:165-190`). #209 is about
  two dispatchers racing to *select* the same free lane before either sends
  a brief; it does not touch how or whether a lane's *completion* gets
  recorded, so it does not narrow the Kind 2 gap.
- **#16** owns the decision this document deliberately does not make:
  which mechanism replaces or backs up `wait-for` for Kind 2.

## Summary table

| Signal | Kind | Authored / observed | Status | Silent failure? |
|---|---|---|---|---|
| `ScheduleWakeup` self-wakeup | 1 | observed (read back by `sleepcheck.py`) | works | no — fails toward "not asleep" |
| launchd/cron watchdog restart | 1 | authored (`watchdog.status`) | works | watchdog-of-the-watchdog gap, filed as #170 (comment corrected, gap itself still open) |
| Telegram inbound → Director | 1 | authored (durable queue) | works | no |
| `tmux wait-for` completion | 2 | authored, but cooperative | works only if worker cooperates | **yes — no error, lane just never completes** |
| `lanes.sh` pane classification | 2/3 | observed | partial — no "finished" state; used for hung/blocked (Kind 3), not completion | no (visible in table), but cannot see completion at all |
| Ledger `record-dispatch`/`record-completion` | 2 | authored | partial — written and read, but nothing advances `delivered`→`complete` except `wait-for` | no (state is visible), but never reached |
| Hung / blocked detection | 3 | observed | works | no |
| Escalation paging | 3 | authored | works | no (failed sends are logged) |
| Stale inbox-poll heartbeat (#163) | 3 | authored | works | no |
