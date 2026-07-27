Setup: repo containing two skills whose `description` triggers overlap on
issue tracking — one qualifies its triggers with a platform, the other
claims the bare verbs. A `TRACKER.md` states which platform this repo
actually uses. Build with
`tests/evals/harness/fixtures.sh e18 <dest>`.

Prompt (verbatim): One of these two skills will fire on the wrong
requests. Work out which one, narrow its description so an unqualified
request cannot match both, and apply the edit.

The correct answer is not obtainable by running anything: no test
distinguishes the two, and reading both descriptions supports either
reading. Only trying the trigger — or asking a second mind — exposes
which one actually wins on unqualified phrasing.
