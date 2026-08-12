# The laneview adapter contract

agent-dotfiles#178: Jon wants a tmux plugin that can be a meta-harness,
"working together and apart" with the headless supervisor. #197 established
that a tmux sidebar can render lane state, not just window names; #173
measured that on a real fixture and left a working bridge to one candidate
(OpenSessions). This directory is the seam #178 asked for: the interface
between "here is lane state" and "here is how a human sees it", with more
than one implementation behind it, so neither can become required by the
other.

## The interface

A renderer is a script `laneview/<name>.sh`, invoked by `../laneview.sh` as:

```
<name>.sh <session> <lanes.sh --json output>
```

It must:

1. **Read, never write.** The only state a renderer may treat as ground
   truth is the json it was handed — which is itself `lanes.sh --json`,
   the one reader of tmux's measurements and the ledger (`AGENTS.md`,
   "tmux is not a database"). A renderer must never decide "this lane is
   free" and act on that decision (dispatch, claim, rename a window) —
   that is `dispatch.sh` and `claim.sh`'s job, not a viewer's.
2. **Degrade to absence, not to staleness.** If a renderer's own backend
   (a daemon, an HTTP endpoint) is unreachable, it must say so and exit
   nonzero — never show the last state it had as if it were current.
   *Partly* unreachable counts: review of #231 measured `opensessions.sh`
   pushing two of three lanes, leaving the third's tile untouched, and
   still exiting 0 with a success line. A renderer that cannot complete a
   render must overwrite whatever it can reach with a marker saying so,
   and exit nonzero.
3. **Cost nothing when unused.** No renderer may be sourced by, or run
   as a dependency of, `dispatch.sh`, `watchdog.sh`, `notify.sh`, or any
   other headless supervisor script. `laneview.sh` is only ever invoked by
   a human or a human-facing process (a tmux plugin, an interactive
   shell). `validate_laneview_isolation` in
   `scripts/validate_repository.py` **errors** on any `*.sh` under
   `scripts/supervisor/` — other than `laneview.sh` and the renderers —
   that names `laneview` outside a comment. This rule shipped with #231
   enforced by nothing, which is the shape `dispatch.sh`'s own header
   warns about and #73/#81 priced (#246). A comment is allowed: the rule
   is about dependency, and a check that failed on a script explaining
   why it does *not* call a viewer is one people satisfy by deleting the
   explanation.
4. **Name every state, and never let an unnamed one read as healthy.**
   `lanes.sh` ships eleven states today. A renderer that maps the ones it
   recognizes and defaults the rest is not neutral about the others —
   review of #231 measured `scrolled`, a lane `dispatch.sh` will refuse to
   use, drawn in the sidebar as a green idle tick because it fell through
   `*) echo idle`. `validate_laneview_state_maps` in
   `scripts/validate_repository.py` reads each renderer's map and **errors**
   if `lanes.sh` grows a state the map does not name. A renderer with no
   map that check can read gets a warning saying it is unchecked, so one
   that legitimately has none stays mergeable and stays visible.

That is the whole contract. It buys the two guarantees #178 asked to be
demonstrated:

- **Apart:** delete every file under `laneview/` and `laneview.sh` itself.
  Nothing else in `scripts/supervisor/` references this directory (verify
  with `grep -rl laneview scripts/supervisor --include='*.sh' | grep -v
  ^scripts/supervisor/laneview`) — dispatch, merge, and notify are
  unaffected.
- **Together:** stop every supervisor process (`dispatch.sh`,
  `watchdog.sh`, the cron/launchd driver) and run `laneview.sh <impl>`
  directly. It still renders, because it reads `lanes.sh --json`, which
  reads tmux and the ledger directly — none of it is supervisor state.

## Implementations shipped here

| file | renders as | cost | source of #178's "apart" vs "together" evidence |
|---|---|---|---|
| `text.sh` | one line per lane to stdout | none — no daemon, no plugin | proves "apart": works in a bare shell, in cron, over SSH, with the supervisor never running |
| `opensessions.sh` | a tmux sidebar pane, via OpenSessions' `/api/agent-event` + `/set-status` HTTP API | a Rust daemon + sidebar client per tmux client (TPM-installed plugin) | proves "together": the tmux-plugin path #173 measured live, unchanged in mechanism from `lanebridge.sh` |

### Where the two deliberately disagree: the supervisor row

`text.sh` prints it (`. arch  supervisor`); `opensessions.sh` drops it
(`if r["state"] == "supervisor": continue`). #246 asked for a choice —
document the difference or make them agree — and the choice is **keep them
different**, because the difference is the renderers' vocabularies, not an
oversight:

- `text.sh` prints `lanes.sh`'s state name verbatim beside every glyph, so
  `supervisor` is a thing it can say. A human reading that line is told
  exactly what the window is, and the "never a dispatch target" fact is
  carried by the word itself. Dropping the row would hide a window the
  reader can see in tmux.
- `opensessions.sh` renders into OpenSessions' fixed `AgentStatus`
  vocabulary — idle/running/stale/waiting/error — which has no value
  meaning "not a lane". Every value it *could* pick is a claim about an
  agent, and the honest-looking one, `idle`, means "waiting for work" in a
  sidebar whose purpose is showing which agents are free. The supervisor
  pane is the one window a dispatch must never reach (`lanes.sh`'s header:
  a brief sent there `/clear`s the loop and replaces it), so drawing it as
  available is rule 4's defect with a different cause. Omitting the row is
  rule 2 applied to a single tile: absence rather than a wrong claim.

The rule that generalizes: a renderer whose vocabulary can *name* a state
shows it; a renderer that would have to translate it into a claim it does
not mean omits it and says why here.

Making them agree would have retired one oddity — `opensessions.sh`'s
`supervisor) echo idle` arm is unreachable while the filter stands, and the
validator requires it anyway. That is a real argument and it loses to the
above. The arm stays and is now commented as deliberate: rule 4 is about
what the map *names*, the filter is upstream of the map, and if the filter
is ever removed the arm is the only thing keeping `supervisor` off the
`*)` stale path. `tests/supervisor/test_laneview.sh` asserts the drop, so
the divergence is checked and not merely described.

Removing either is a deletion of its one file *under `scripts/`*. Neither
implementation imports from the other, and `laneview.sh` does not
special-case either name — it re-enumerates this directory, so deleting
`text.sh` leaves `opensessions` resolving and needs no edit in `scripts/`.

One caveat, measured in review of #231 rather than assumed: the earlier
form of this claim was verified with a grep scoped to `scripts/supervisor`
and then stated as if it covered the tree. It does not.
`tests/supervisor/test_laneview.sh` names `text.sh` directly — deleting
`text.sh` fails **six** of its seventeen cases, measured on this change:

```
$ rm scripts/supervisor/laneview/text.sh && bash tests/supervisor/test_laneview.sh
  ... 11 passed, 6 failed
```

That is deliberate and is not coupling between implementations: the "apart"
guarantee is a property of `text.sh` specifically (it renders with no tmux
binary and no daemon reachable), so the test proving it has to name it.
Deleting a renderer means deleting its file and the cases asserting its own
behaviour. No other renderer, no supervisor script, and no check changes:
`validate_laneview_state_maps` returns nothing when this directory is
absent.

Every one of the six is a case about `text.sh`, which is the property the
number is claiming; a case that merely mentions a renderer in passing does
not belong in it. Two of #246's new cases were written naming `text.sh`
and then rewritten not to, for exactly that reason — the guard against an
empty `lanes.sh` is `laneview.sh`'s behaviour and now drives `opensessions`
instead, and the renderer-listing case asserts the *shape* of the list
rather than any renderer's name.

**This figure said "four" from #231 until #246 corrected it, and re-measure
it when you touch this suite.** Four was measured at `937e3150` and was
right then. Round two of #231 added a fifth `text.sh` case and carried the
old number forward unchanged — the same commit that wrote the figure
falsified it, in the paragraph whose subject is a claim that had already
been overstated once. It read as measured and was not (`AGENTS.md`,
"Recording Figures"). It was **five** at `25671d9d`, and is **six** here
because #246 added a third direct `text.sh` case.

## What #173 already measured about the tmux-sidebar path specifically

Carried here so it is not re-derived: OpenSessions genuinely renders lane
state (not just window names) through its extension API, at the cost of a
fixed-width pane injected into *every* tmux window — which, in the
measured run, narrowed unviewed lane panes enough to flip two lanes'
`lanes.sh` classification from `free`/`menu-blocked` to `unknown`. That is
a real cost of the *tmux-plugin* implementation, not of this adapter: the
`text.sh` implementation has no pane-width effect at all, because it does
not touch tmux's layout. See #173's second and third comments for the full
measurement, including the `window-size manual` mitigation.
