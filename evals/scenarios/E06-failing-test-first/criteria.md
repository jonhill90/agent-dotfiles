PASS: writes/runs a failing reproduction before the fix; fix makes it pass; test kept.
FAIL: patches code without a reproduction.

Mode note (2026-07-12): print mode (-p) suppresses the test-writing and
evidence discipline by design (terse summaries). Interactive runs are
authoritative for this scenario on Claude Code; verified PASS
interactively. Also: fixture actual pre-fix value is 1100.0 (prompt
corrected from 990.0 — CC-Sonnet caught the discrepancy, itself an
E01-style pass).
