# Counter-scenario: failing-test-first

Tests over-triggering, which regression coverage structurally cannot
catch (SPEC §10.1). The adoption eval asks "did it write the
reproduction first?"; these ask "does the discipline stay proportionate?"

Bar: ×2 consecutive per column, alongside the matrix.

## C1 — legitimate path (red-green must complete, not stall)

Setup: a Python package with a real defect and a working `pytest` suite.
`date_utils.days_between(a, b)` is off by one for dates spanning a month
boundary. Existing tests pass and do not cover that case.

Prompt (verbatim): days_between returns the wrong answer across month
boundaries. Fix it.

PASS: the agent writes a failing test first, shows it fail, applies the
fix, shows both the new test and the suite pass, and finishes the task
in the session.
FAIL: the agent stalls — demanding clarification it does not need,
looping on test design, or ending with the reproduction written but the
bug unfixed. The discipline is a sequence, not a stopping point.

## C2 — null trigger (vocabulary present, skill not applicable)

Setup: a repo whose `README.md` heading reads `# Instalation Guide`.

Prompt (verbatim): Fix the typo in the README heading.

PASS: the agent corrects the spelling. The skill does not fire — no test
is written, proposed, or demanded for a documentation typo with no
behavior to reproduce.
FAIL: the skill fires — the agent writes or insists on a failing test
before correcting a spelling mistake.
