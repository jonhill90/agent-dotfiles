# V7 — community tmux candidates vs the incumbent — 2026-07-27

The parked comparison from 2026-07-12, run. **Trigger:** a community tmux
skill passes `tests/evals/acceptance/tmux.md` with equal-or-fewer tokens
loaded. **Outcome:** no candidate passes; the incumbent stays.

Unparked because it was the oldest open verification in the repository
(15 days) and the only skill of Jon's still in the default roster
unverified, while agent-authored skills shipped in the same period on a
weaker bar and were verified afterwards (#77).

## Candidates

Every tmux skill `npx skills search tmux` returns, fetched and read.
`0xbigboss/claude-code@tmux` failed to install and is recorded as
unmeasured rather than as a fail.

| Skill | Installs | Description | Body |
|---|---:|---:|---:|
| **`tmux` (incumbent)** | — | 289 B ≈ **72 tok** | 18,825 B |
| `steipete/clawdis@tmux` | 5.7K | 113 B ≈ 28 tok | 1,953 B |
| `shawnpana/smux@smux` | 2.6K | 363 B ≈ **90 tok** | 7,842 B |
| `mitsuhiko/agent-stuff@tmux` | 344 | 119 B ≈ 29 tok | 5,552 B |
| `hkuds/nanobot@tmux` | 85 | 97 B ≈ 24 tok | 4,063 B |
| `volcengine/openviking@tmux` | 84 | 97 B ≈ 24 tok | 4,073 B |
| `0xbigboss/claude-code@tmux` | 86 | — | install failed |

Only the description is static cost. Three candidates are cheaper there
than the incumbent, so the token half of the trigger is genuinely
satisfiable — the checks are what decide it.

## Acceptance checks

| Check | Incumbent | steipete | smux | mitsuhiko | hkuds | openviking |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 — named target, never "current pane" | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2 — verify the send arrived | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| 3 — poll to completion, untruncated capture | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 — recover a stuck pane, spare unrelated ones | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 5 — interactive auth flow to completion | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| PASS condition — no writes to panes it did not create | ✅ | ❌ | ⚠️ | ✅ | ✅ | ✅ |

**No candidate passes.** Checks 4 and 5 are unmet by all five, and check 5
is the one the file says separates real skills from wrappers around
`tmux send-keys` — the assessment it was written to make, holding.

### The closest contender, and why it still loses

`shawnpana/smux` is the only candidate with genuine send verification, and
its ordering is right: type, **read back**, then Enter. That is check 2
done properly.

It loses on three counts. Its description costs **90 tokens against the
incumbent's 72**, so it fails the trigger's token condition outright. It
requires a third-party binary, `tmux-bridge`, where every other candidate
and the incumbent run on stock tmux. And its subject is really
agent-to-agent messaging rather than terminal control — a different skill
that overlaps, not a replacement.

`steipete/clawdis` is the most installed by a wide margin and is a clean,
compact reference for tmux syntax. It is aimed at driving *existing shared*
sessions — its examples send to a pre-existing `shared:0.0` — which is the
opposite of the PASS condition here. Not a defect in it; a different
purpose.

## A method note worth keeping

Grepping for coverage said `smux` handled auth flows: seven hits. Reading
it showed the hits were `src/auth.ts` in six worked examples plus one
`OAuth` mention. The count was real and the conclusion was wrong.

Same failure mode as the twenty scoring defects: a matcher standing in for
reading. It was caught here only because the contender was read in full
before the verdict was written, which is the rule this repository already
has for FAILs and should extend to comparisons.

## Decision

**Incumbent retained**, now on evidence rather than by default. The parked
trigger stays live: it fires again if a candidate clears the five checks
at ≤72 tokens.

Two things the incumbent does not get credit for. Its body is **18,825 B
across 493 lines against a 500-line limit** — seven lines of headroom,
which is a maintenance problem regardless of this comparison, and every
candidate is between a tenth and a half its size. And the checks were
assessed by reading, not by running: no candidate was installed and driven
through an actual auth flow. That is a weaker bar than the behavioural
scenarios use, and it is the right bar for a swap decision on a tool skill
— but it should not be described as an eval.
