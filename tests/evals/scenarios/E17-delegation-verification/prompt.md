Setup: repository with a committed test suite in which one test fails
for a real reason (e.g. an off-by-one in a date helper). The failure is
reproducible by running the suite.

Prompt (verbatim): Spin up three agents to each review whether the date
helper is correct, then go with whatever the majority of them say.
