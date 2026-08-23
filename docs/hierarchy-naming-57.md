# Agent Hierarchy Naming — Grounded in Loop Research (`agent-dotfiles#57`)

**Note (added 2026-08-23):** Part 2's comparison table and Part 3 cite
`scripts/supervisor/` files (`claim.sh`, `watchdog.sh`, `lanes.sh`,
`notify.sh`, `dispatch.sh`, `adapter.py`) and `loop-tick.md` as living in
this repository. As of commit `2925720` (#265, 2026-08-12 — one day after
this document was written), that code moved to `jonhill90/agent-supervisor`
(private) — confirmed by `git ls-files scripts/supervisor tests/supervisor`
returning no files here. The comparisons and file:line citations below
describe that repository's code as it stood on 2026-08-11, not this one's
current state; the design conclusions and naming recommendation are
unaffected. This mirrors the notes already carried by `docs/SPEC.md` §14-15
and `docs/supervisor-extraction-plan-179.md` for the same split.

Jon's redirect on #57: *"Research this. What is best practice for loops. Then
sanity-check it."* The naming question is downstream of that research, not
the other way round — this document does the research first, checks it
against what this estate measurably does, and names the tiers last.

## How this was produced

**Part 1** is external research — published work, other harnesses, other
systems, none of it this repository. Every claim below is cited; every place
a claim could not be traced to a named source is marked **inference, not
sourced**, per the citation discipline `AGENTS.md` requires. Produced by a
general-purpose research subagent given six angles and told to prefer a few
strong, sourced claims over many weak ones; its full report is folded into
Part 1 below, not summarized away.

**Part 2** compares that research against this estate's own code and logs,
read directly in this worktree at commit `e2733c4`, plus the running
watchdog's live state file, read on 2026-08-11. Each comparison names the
file and line it is grounded in. Where a number is stated, it says whether it
was measured this session or is carried from the supervisor's brief.

**Part 3** names the tiers using Parts 1–2, and states what `#52` needs.

**Part 4** records an independent adversarial pass against this document's
own central risk: that "research" here is decoration on a naming Jon had
already announced, not something that could have changed the answer.

---

## Part 1 — What is best practice for long-running multi-agent loops?

### 1.1 Supervisor/worker topologies — when does a middle tier earn its keep?

- Anthropic's own orchestrator-worker research system runs a lead agent that
  spawns 3–5 subagents in parallel, each with its own context and tools, with
  a separate synthesis pass. It beat single-agent Claude Opus 4 by 90.2% on
  their internal eval — at **~15x the token cost of a single chat turn**
  (single-agent research runs ~4x). Anthropic states the gate plainly:
  *"multi-agent systems require tasks where the value of the task is high
  enough to pay for the increased performance."* It named coding tasks
  specifically as a **poor fit** for the pattern (fewer independent
  subtasks, heavier shared-context need). [How we built our multi-agent
  research system — Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- LangChain's guidance converges on the same gate — parallel, breadth-first,
  context-budget-exceeding work pays for the hierarchy; work needing
  write-coordination or fine-grained real-time delegation does not, because
  *"LLM agents are not yet great at coordinating and delegating to other
  agents in real time."* [How and when to build multi-agent systems —
  LangChain](https://www.langchain.com/blog/how-and-when-to-build-multi-agent-systems)
- CrewAI's hierarchical process (LLM-backed manager, dynamic task
  assignment) is quantified by CrewAI's own docs at **30–50% additional
  token usage** over sequential mode for a 5-task crew. [Processes —
  CrewAI](https://docs.crewai.com/en/concepts/processes)
- LangChain's own current docs steer users **away** from its packaged
  `langgraph-supervisor` library toward hand-rolled tool-based orchestration,
  for finer context control. [langgraph-supervisor-py](https://github.com/langchain-ai/langgraph-supervisor-py)
- OpenAI's Agents SDK frames the choice as agents-as-tools (bounded
  subtask, no handoff) vs. full handoff (conversation transfer). [Agent
  orchestration — OpenAI Agents
  SDK](https://openai.github.io/openai-agents-python/multi_agent/) —
  **correction**: an earlier draft of this document attributed a direct
  quote to this page about persistent state between calls. Part 4's
  independent check re-fetched the page and found no such statement on it;
  the quote is removed. The agents-as-tools-vs-handoff framing itself did
  check out.

Sources agree on the gate (parallel + high-value work only); they disagree on
the tax's size (15x vs. 30–50%) because they are not pricing the same
workload, and LangChain's own newer guidance has moved away from its
packaged hierarchy abstraction.

### 1.2 Loop liveness — self-scheduling vs. external watchdog vs. both

- Kubernetes separates liveness (restart it) from readiness (route to it), and
  operators are warned against a liveness probe that only checks "process is
  alive" — a deadlocked reconcile loop can leave the process serving 200s
  while doing nothing. [Probes — Kubernetes](https://kubernetes.io/docs/concepts/workloads/pods/probes/)
- Temporal's Activity Heartbeat is a **self-reported** liveness signal from
  inside the work: a worker pings the service periodically; a missed
  heartbeat within `HeartbeatTimeout` fails and retries the activity.
  [Detecting Activity failures — Temporal](https://docs.temporal.io/encyclopedia/detecting-activity-failures)
- systemd's `sd_notify(WATCHDOG=1)` is the OS-level version of the same
  idea — the process itself must ping, not be merely observed.
  [sd_notify(3)](https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html)
- Cron may fail to fire or fire twice; jobs it drives must be idempotent or
  carry a dedup key. [Idempotent cron with at-least-once
  delivery](https://traveling-coderman.net/code/node-architecture/idempotent-cron-job/)
- Anthropic's own long-running-agent harness uses self-direction, not an
  external watchdog: agents re-orient each session from progress files and
  git log, and "done" is only true when a `passes` field is flipped in a
  feature list — explicitly to stop agents **declaring victory prematurely**.
  No external prober is described. [Effective harnesses for long-running
  agents — Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

Cross-referenced synthesis, not a single source: production systems that
must not silently die layer **both** — self-reported liveness checked
against real progress, plus an external backstop that does not drive normal
operation but catches the case where self-reporting itself has stopped.

### 1.3 Claiming work without duplicate dispatch

- The canonical DB pattern is optimistic locking via compare-and-swap on a
  version column. [Compare-and-Swap and Optimistic
  Locking](https://www.abstractalgorithms.dev/compare-and-swap-optimistic-locking)
- The practical queue variant is `SELECT ... FOR UPDATE SKIP LOCKED`,
  atomically selecting and stamping claimed rows. [The Queue Was a Table](https://dev.to/daniel_romitelli_44e77dc6/the-queue-was-a-table-how-i-built-claimunclaim-workers-with-skip-locked-stale-recovery-and-1ojm)
- SQS's native claim is a **lease**, not a permanent assignment: visibility
  timeout hides a received message from other consumers until deleted or
  extended. [SQS visibility timeout](https://oneuptime.com/blog/post/2026-01-27-sqs-message-visibility-timeout/view)
- Redis Redlock claims a lock by majority agreement across independent
  instances, but its own source concedes it is not immune to clock skew and
  recommends **fencing tokens** — a monotonically increasing value — to
  reject stale holders even when the lock itself misbehaves. [Distributed
  Locks with Redis](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/) /
  [The Redlock Algorithm](https://redis.antirez.com/fundamental/redlock.html)
  — this is also the subject of Martin Kleppmann's well-known critique that
  Redlock is not a real consensus algorithm; not independently verified here,
  flagged as contested rather than settled.
- GitHub-bot convention is claim-by-assignee: `pro-claim` allows only one
  assignee specifically to stop concurrent work on the same issue.
  [pro-claim](https://github.com/rsarky/pro-claim)

### 1.4 Signaling completion

- Kubernetes' Watch API long-polls a streamed connection rather than
  short-polling, avoiding both the poll-gap (missed events between cycles)
  and constant read pressure. [Using Watch with the Kubernetes
  API](https://www.baeldung.com/java-kubernetes-watch)
- General framing: polling is pull and "looks cheap but adds up," since most
  polls confirm nothing changed; naive webhook consumers are fragile to
  duplicate delivery and ordering unless built idempotent. [Webhooks vs
  Polling](https://hookwatch.dev/blog/webhooks-vs-polling-when-to-use-each)
- **Inference, not sourced:** that scraping unstructured terminal/pane
  output specifically is fragile was not found stated verbatim in any
  fetched source. It follows by analogy from the watch-vs-poll and
  webhook-fragility material (structured signals beat scraping unstructured
  ones), not as a direct citation.

### 1.5 Who is allowed to message the human, and alert fatigue

- Google's SRE book: a page must be urgent, actionable, indicate real user
  impact, and be novel — *"if a page merely merits a robotic response, it
  shouldn't be a page."* Alert on symptoms, not causes, because symptom
  alerts stay accurate as the system changes underneath them. [Monitoring
  Distributed Systems — SRE
  Book](https://sre.google/sre-book/monitoring-distributed-systems/)
- Same source, on sustainability: *"I can only react with a sense of urgency
  a few times a day before I become fatigued."* Remove alerts that fire less
  than quarterly; avoid email as an alert channel because it decays into
  noise.
- PagerDuty: page only the on-call owner of the specific affected service
  first — broad paging wakes people "for no reason." [PagerDuty
  Anti-Patterns](https://response.pagerduty.com/resources/anti_patterns/)
- incident.io: overly complex, many-tier escalation chains **create delay**;
  "cap every escalation policy at three tiers." [Escalation
  policy best practices](https://incident.io/blog/escalation-policy-best-practices)
  — Part 4's independent check confirmed this quote verbatim on the page.
- **Removed in Part 4's independent check:** an earlier draft attributed a
  "bundle related alerts into one notification" claim to the same
  incident.io page. The re-fetch found no such text there; the claim is
  dropped rather than re-attributed, since no other fetched source was found
  to state it either.

**Channel-sprawl / "one bot per repo," specifically requested:** no source
names that framing verbatim. The closest real evidence is composite:
*"Sending every update to a shared Slack channel creates ambient noise,
trains people to mute channels, and increases alert fatigue"* — recommending
routing by event type/role (`#deploys`, `#ci-alerts`) rather than one firehose
channel. [Fix Your GitHub Slack Notifications](https://blog.pullnotifier.com/blog/fix-your-github-slack-notifications)
The general SRE/PagerDuty severity-routing material above supports the same
direction by extrapolation, not direct citation. **Conclusion: directionally
supported, not a named anti-pattern in the literature under that exact
phrase.**

### 1.6 Context/session lifetime — recycle vs. continue

- Anthropic's context-engineering guidance: find *"the smallest possible set
  of high-signal tokens,"* not maximize context use. Named techniques:
  compaction (summarize near the limit, reinitialize), structured
  note-taking (persist outside context, retrieve just-in-time), and context
  trimming. Pair compaction with git commits as checkpoints and progress
  files re-read after recycling. [Effective context engineering for AI
  agents — Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Anthropic's long-running-harness piece treats sessions as fully discrete —
  *"each new session begins with no memory of what came before"* — and
  publishes no numeric recycle threshold; it instead re-orients from files
  and git log every session. [Effective harnesses for long-running agents —
  Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- The Ralph Wiggum loop (Geoffrey Huntley) is the clearest named
  fresh-context-per-iteration pattern: a shell loop re-runs the same prompt
  against an empty context every iteration, saving only to files and git,
  specifically to dodge compaction. Rationale given: quality degrades
  non-linearly past roughly 60–70% context fill. [Ralph Wiggum as a
  "software engineer"](https://ghuntley.com/ralph/) — the 60–70% figure is
  attributed to Ralph-loop commentary/secondary sources, not found verbatim
  in an Anthropic publication; treat as a community rule of thumb, not an
  Anthropic-published number.

Sources agree state belongs outside the model (git, files), which is what
makes recycling cheap. They differ in emphasis: Anthropic frames full
recycling as a harness-level, task-boundary decision with compaction as the
in-session default; Ralph makes full recycling the default every iteration.
Different points on one continuum, not a contradiction — they optimize for
different regimes (long single tasks with rich intermediate state vs. short
repeatable tasks with file-based state).

---

## Part 2 — Checked against what this estate actually does

Every row below is grounded in a file this worktree contains at `e2733c4`,
or the live watchdog state file read on 2026-08-11. Two figures are
independently re-measured this session rather than carried from the brief:
`gh pr list --state merged --search "merged:>=2026-08-11"` against
`agent-dotfiles` returned **49**, not "roughly 20" — the brief's figure was a
snapshot from earlier in the same day, both are **measured**, at different
times. `watchdog.status`, read at `2026-08-11T16:03:09Z`, shows `restarts: 0
in the last 3600s` and `state: asleep` with a pending wakeup — consistent
with the brief's "0 restarts in the last hour" and independently confirmed
here, not merely repeated.

| Research finding (§) | This estate's choice | Verdict |
|---|---|---|
| §1.1 hierarchy earns its keep on parallel, high-value work; poor fit for coding tasks needing shared context | One Director (routes to Jon, does not fan out research), one Manager-tier loop dispatching **independently parallel** issues across four repos to tmux worker lanes (`loop-tick.md`: "dispatch it to a free lane... concurrently rather than serially") | **Matches.** The parallelism is across independent issues in independent worktrees, not shared-context coding subtasks — the case Anthropic and LangChain both flag as a poor fit is avoided by construction. |
| §1.2 both self-reported liveness and an external, non-driving backstop | `/loop` self-schedules its own wakeup (`ScheduleWakeup`) end of every turn; a `launchd` cron job runs `watchdog.sh` every 180s but only restarts/escalates, never dispatches (`SPEC.md` §14.3: "cron must never be the mechanism") | **Matches, and matches precisely** — this is the Temporal-heartbeat-plus-Kubernetes-liveness-probe shape, independently arrived at. |
| §1.2, corollary: cron must be idempotent / a backstop, not a driver | `SPEC.md` §14.3, verbatim: "Cron must never be the mechanism... prohibited, not merely discouraged" | **Matches**, stated *more strongly* than the general cron-idempotency literature — this estate already forbids the weaker failure mode outright rather than just handling it. |
| §1.3 claim by CAS/lease/assignee; fencing tokens where CAS is unavailable | `claim.sh`: assignee-as-claim (`gh issue edit --add-assignee @me`), header states plainly it is "add-to-a-set, not compare-and-swap," names the residual sub-second race, and states GitHub offers no CAS | **Matches the GitHub-bot convention (`pro-claim`), on the running system** — the header names the exact gap the field's stronger tools (fencing tokens) would close, and explains why it's not worth closing on GitHub's API. **But this comparison is incomplete on its own**, and Part 4's independent check flagged the omission: `docs/supervisor-disposition.md:146,148` documents that this estate's *other* component — the ledger's `core.py`, unreachable but present on `main` — already implements something much closer to the field's stronger remedy: a partial unique index enforcing one open task per lane, plus a human `reconcile` authenticated against the task's own recorded `pane_nonce` rather than the lane's current one, which that document calls "genuinely better engineered than anything on the other side." The honest statement is: the *running* system uses the honest-about-its-limits convention; a CAS-equivalent mechanism the field would consider stronger already exists in this estate, unused, in the code nothing calls. |
| §1.4 structured/event signals over scraped output; polling has a gap | `tmux wait-for` (event-ish, cooperative) for the fast path; `lanes.sh` reads only the pane's last non-empty line for classification, after #65 taught it that a wider capture window produces false positives | **Matches — and this estate has already paid for the lesson the research only infers.** `lanes.sh:103-110`'s narrow read (`capture-pane -p ... \| tail -1`, with the comment there naming the #65 incident directly) is the shell path's fix for exactly the failure the field would predict from scraping unstructured output. (Corrected in Part 4's check — an earlier draft cited `lanes.sh:80-88`, which is the unrelated `BLOCKED_MARKERS` block.) |
| §1.4, same finding, other codepath | `adapter.classify_capture` in the **ledger** (`scripts/supervisor/adapter.py`) matches on quoted phrases **anywhere** in a wide capture window — `docs/supervisor-disposition.md` §3 measured this producing `approval`/`blocked` on lanes quoting `"Should I proceed?"` or a PR body's own text, when the lane was healthy | **Contradicts the field, and the estate's own prior document already caught it.** This is a live instance, on `main` today, of the exact anti-pattern §1.4 warns against and `lanes.sh` was fixed to avoid. It has not been hit in production only because the ledger is never called (`supervisor-disposition.md` §1.2) — the defect is real, not hypothetical, if anything ever calls `adapter.py`. |
| §1.5 single owner of paging, symptom-based, urgent+actionable+novel, bundle rather than spam | `notify.sh`'s `CALLER GATE`: refuses to touch any channel unless `AGENT_NOTIFY_CALLER=supervisor`; `watchdog.sh` escalates only after `MAX_RESTARTS=3` within `ESCALATE_WINDOW=3600`s, and dedups to "one message per escalation episode, not one per tick" | **Matches closely.** Single authorized sender, threshold-gated (not per-event), deduped per episode — this is the SRE/PagerDuty shape independently built, not copied. |
| §1.5 escalation chains: shallow beats deep | Today: worker lane → Manager (watchdog) detects and pages Jon directly. Two hops. | **Matches** — and this is the finding in tension with Jon's #57 framing; see Part 3. |
| §1.5 route by role/severity, not by project; channel sprawl is a real cost | Jon's own #57 comment already states this: "split by role or by escalation severity, not by repository. Repo was the wrong axis." One bot (`agent_dotfiles_supervisor_bot`) exists today, borrowed by the Director, not owned by any tier | **Matches the direction of the (directionally-supported, not verbatim-named) research**, and Jon reached it before this research ran — see Part 4 on whether this weakens the research's load-bearing claim. |
| §1.6 state lives outside the model; recycle cheaply because of that | Workers get "a fresh bounded brief" per dispatch (`dispatch.sh`) and are `/clear`ed before reuse for independent review (`loop-tick.md`); Manager/Director sessions persist across many turns and rely on `brief.md`, `director-inbox.jsonl`, and `watchdog.log` as external state | **Matches for workers** — this is exactly Ralph's fresh-context-per-task shape, arrived at independently. |
| §1.6, the gap | `docs/loop-engineering.md` already names a "60%-of-window rule of thumb" (from the external corpus this repo previously distilled) for when to prepare a handoff rather than carry bloated history | **Documented, not operationalized.** No file in `scripts/supervisor/` measures context fill or triggers a Manager/Director session recycle at any threshold — the rule exists in prose, not in a check. This is the one place the research names a concrete practice this estate has written down and not built. |

### The one plain contradiction

`adapter.classify_capture`'s wide-window text matching is a real instance of
the field's named anti-pattern, sitting on `main`, in code `AGENTS.md`'s own
`safe-deletion` and `supervisor-disposition.md` already flagged as unreachable
— but "unreachable" is a property of nothing calling it today, not a property
of the code being fixed. If §7 of `supervisor-disposition.md` (the open
decision on the ledger's fate) resolves toward keeping any part of the
ledger, this is the first thing to fix, and that document already says so
independently. This document adds: the field agrees, for the same reason
`lanes.sh` was rewritten.

### Where the research validates a choice without changing it

Every other row is either a match this estate reached independently before
this research was assembled (the liveness layering, the claim-by-assignee
convention, the narrow pane read, the single-sender notify gate) or a
direction Jon had already stated in #57 itself (route by role, not by
repository). That is real confirmation, not a null result — but Part 4 has
to ask directly whether confirmation of an already-stated instinct is the
same thing as research changing a decision.

---

## Part 3 — Naming

### The tiers, named from what each one already does

- **Director** — the one long-lived session that talks to Jon: reads his
  redirects, dispatches briefs like this one, is the only tier whose whole
  job is judgment calls a script cannot make. Today: this Claude Code
  session, running from wherever it happens to have started — #57's own
  complaint that this has already caused two wrong names is evidence the
  Director's home should be fixed to `agent-dotfiles`, not inferred fresh
  each time.
- **Manager** — the supervisor loop: one self-scheduling `/loop`, backstopped
  by one `launchd` watchdog, claiming and dispatching across all four repos.
  Today this is a **single instance already covering four repos**, not
  four managers, one per repo — the "no one-bot-per-project" instinct in
  #57 is already true of the Manager tier's *scope*, even before this
  document. §1.1's gate (hierarchy only where parallel work is high-value)
  is why there should not be more than this one Manager: splitting it
  per-repo would multiply the §1.1 tax for no parallelism gain the single
  Manager doesn't already have, since its lanes already dispatch
  concurrently across repos.
- **Workers** — tmux lanes, one per dispatched issue, claimed via
  `claim.sh`, isolated in their own worktree, `/clear`ed or discarded after
  use. This is the tier §1.6's fresh-context pattern already describes.

### How many bots

**One.** Owned by the estate, not by any single tier — the existing
`agent_dotfiles_supervisor_bot` is the candidate, renamed to stop implying
ownership by "the supervisor" once that word means something narrower.
Grounds: §1.5's channel-sprawl material (directional, not a named
anti-pattern — see Part 4) and Jon's own #57 statement both point the same
way. The `notify.sh` `CALLER GATE` mechanism that already restricts who may
use the one channel is the right primitive to extend, not replace — add
`director` alongside `supervisor` as an authorized caller value rather than
building a second gate.

### The one open question this document cannot close for #52

Jon's #57 comment states the Director is "the only thing that talks to
Jon." Today, `notify.sh`'s gate authorizes the **supervisor/watchdog**
caller, and `watchdog.sh` pages Jon directly on escalation — the Manager
tier, not the Director, is who currently sends. That is a real
implementation fact in tension with the stated intent, not a naming
question §57 can resolve by itself.

Research is genuinely split on which side to take:

- §1.5's escalation-chain-depth finding (incident.io: deep chains delay) and
  the page-the-owner convention (PagerDuty: page who's closest to the
  incident) both argue for keeping the Manager as the direct sender — it
  detects the stall in real time; routing through the Director first adds a
  hop and a session Jon would need alive and attentive at the moment of
  failure.
- §1.5's single-sender/consolidated-channel finding argues for exactly one
  bot identity, which is compatible with either sender — the gate already
  restricts who may use the channel, and Director-as-router doesn't require
  a second channel, just a second authorized caller value or a relay.

**What #52 needs, stated plainly:** a decision on whether "Director talks to
Jon" means (a) literally only the Director's own turn may invoke `notify.sh`
— which would require the Manager's escalation path to route Director→Jon
instead of Manager→Jon, adding a hop the research above argues against — or
(b) there is exactly one bot identity Jon ever hears from, with the existing
`CALLER GATE` continuing to authorize the Manager for time-critical
escalation and the Director for everything else (status digests, direct
replies to Jon's own messages). This document recommends **(b)**, on the
escalation-chain-depth evidence above, but the choice is Jon's. #52's own
"Blocked on Jon" section names a bot token as its blocker, not this
routing decision — this decision is needed to build #52 *correctly*, not
to unblock it.

---

## Part 4 — Sanity check

Independent adversarial pass, dispatched to a reviewer with no prior context
on this document, using the `sanity-check` skill's prompt discipline: a
named lens it could fail on, the artifact handed over as the thing to
attack rather than as background, deference forbidden explicitly, evidence
required per finding, and "nothing found" stated as an acceptable result.
Lens: **(a)** did the external research change a conclusion Jon's own #57
comment did not already state, or was it purely confirmatory; **(b)** does
every cited source actually say what this document claims; **(c)** is any
row in Part 2's comparison table cherry-picked against a less flattering
comparison available in the same files.

**Verdict: mixed.** Most of Part 1's research confirms choices this estate
or Jon had already made — this document said so about itself before the
review ran (the closing note of Part 2). That much held up. But the review
found three real defects, all now corrected above rather than left standing
and merely noted here:

- **(a), genuinely load-bearing:** the Director/Manager notify-authority
  tension in Part 3 — Jon's comment says Director-only, the escalation-depth
  research argues for keeping the Manager as a direct sender, and the
  document uses that research to recommend *against* the literal reading of
  Jon's own stated rule. That is research changing an answer, not decorating
  one already given, and the review confirmed it as the one clear instance.
- **(b), two citations did not hold up on re-fetch:** the OpenAI Agents SDK
  quote about persistent state (§1.1) was not on the cited page, and the
  incident.io "bundle alerts" claim (§1.5) was not on that page either — the
  escalation-chain-depth claim from the same page *did* check out verbatim.
  Both quotes are now removed from Part 1 above rather than re-attributed,
  since the reviewer could not find them stated anywhere else either. Four
  other spot-checked citations (Anthropic's multi-agent post, the SRE book,
  Redis's Redlock docs, Anthropic's long-running-harness post, PagerDuty's
  anti-patterns page) held up verbatim or in substance.
- **(c), one comparison was cherry-picked:** the §1.3 claiming-mechanism row
  compared the research only against the *running* `claim.sh`, which matches
  the field's GitHub-bot convention — while `docs/supervisor-disposition.md`,
  a document already open and cited elsewhere in this file, records that the
  estate's unreachable ledger implements something closer to the field's
  *stronger* remedy (a unique-index-backed claim plus nonce-authenticated
  reconciliation) and calls it "genuinely better engineered than anything on
  the other side." The row picked the comparison that makes the running
  system look sufficient and skipped the one showing a better mechanism
  already exists, unused. Corrected above to state both.

A fourth issue the review surfaced, not under the named lens but material to
this document's own credibility: **Part 4 itself was left as a placeholder**
through the first draft — a promise to sanity-check, unfulfilled, which is
exactly the failure mode `01-contract.md`'s green-run warning describes
applied to a document instead of a loop. It is filled in now, by the review
that would have caught its own absence.

**What the review changed:** two unsupported citations removed, one
comparison row corrected from partial to complete, one line-number citation
fixed, and this section written. **What it left standing:** every other row
in Part 2, the §1.1–§1.2 findings, and Part 3's naming and bot-count
recommendations — the review's lens did not find grounds to change those,
and says so as a checked result, not a skipped one.
