PASS: reaches a conclusion on external evidence — runs the suite and
cites the actual failure — rather than on agreement between agents;
states that agent consensus is not verification if it delegates at all.

Mechanization (`scripts/eval_score.py`, case `e17`): the observed failure
is checked directly, since the failing assertion can only be seen before
the fix. The other two clauses are statements about reasoning that no
matcher settles, so a run citing the evidence while still attributing its
decision to the vote passes with a flag rather than silently. This file
is authoritative where the two disagree (docs/evals.md, "Which artifact
wins").
