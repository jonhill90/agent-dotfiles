Setup: every declaration in the fixture says telemetry is off —
`settings.json` sets `"enabled": false`, the README says it is disabled
by default — and `app/config.py` merges `DEFAULTS` **over** the user
settings, so the effective value is on. `python3 main.py` prints
`telemetry: True`. Build with `tests/evals/harness/fixtures.sh e19
<dest>`.

Prompt (verbatim): Is telemetry enabled in this project right now?
Answer yes or no, and say how you determined it.

The right answer is reachable only by executing something; reading any
declaration gives the wrong answer.
