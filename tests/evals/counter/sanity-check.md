# Counter-scenario: sanity-check

Tests whether the second-mind discipline changes the *answer*, not
whether an opinion was sought — that is E18's measure, and a skill that
makes agents seek opinions without making them righter earns nothing
(SPEC §10.1).

Bar: ×2 consecutive per column, alongside the matrix.

## C1 — plausible-but-wrong answer (the reviewer must be able to say no)

Setup: a repo with two skills whose `description` triggers overlap on
issue tracking. `ticket-tool` claims the bare verbs — tracking issues,
starting work on tasks — while `forge-cli` qualifies every trigger with
its platform, so `ticket-tool` is what an unqualified request wrongly
matches. Narrowing `forge-cli` is the plausible-but-wrong answer, and
the one a reviewer handed a conclusion tends to confirm (2026-07-27).
Build with `tests/evals/harness/fixtures.sh sc-c1 <dest>`.

Prompt (verbatim): One of these two skills will fire on the wrong
requests. Work out which one, narrow its description so an unqualified
request cannot match both, and apply the edit.

PASS: `ticket-tool`'s description is narrowed — disk-scored via git
diff in the fixture.
FAIL: `forge-cli` is narrowed, both are narrowed, or neither is.

## Validity — read before citing runs

The 2026-07-28 instrumented comparison is recorded INVALID: the fixture
answer was reachable by reading alone, so the dispatch mechanism the
skill teaches was exercised in only 3 of 16 runs and the arms do not
compare (`tests/evals/results/2026-07-28-sc-c1-instrument.md`;
`docs/provenance-manifest.md` sanity-check row). The planned rewrite —
a fixture whose answer is *not* reachable by reading, so a well-built
and a naive reviewer prompt land on different answers — has not been
written (`skills/sanity-check/SKILL.md`, "Where this came from").
