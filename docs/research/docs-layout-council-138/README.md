# Raw council results — agent-dotfiles#138

Raw batch data supporting `docs/docs-layout-council-138.md`. This is scaffolding,
not a living document — per `docs/PRD.md`'s own stated docs/ convention
("research prose is scaffolding — distilled into topical living docs and
deleted at each spec iteration's exit; git/PRs are the archive"), expect this
directory to be deleted once the findings doc's conclusions are acted on. Git
history preserves it regardless.

## What is here

- `shared-corpus.txt` — the real repo/doc inventory given to every arm (control,
  adversarial, concrete prompts inline it directly; the blind prompt restates
  the same facts with names replaced by neutral labels — see `prompt-blind.txt`).
- `prompt-<variant>.txt` — the exact prompt text sent for each of the four
  variants: `control` (naive "is this good" framing), `adversarial` (argue the
  layout is wrong, propose better, no hint anyone likes it), `blind` (directory
  and repo names replaced with `dir-a`/`doc-1`/etc.), `concrete` (placement
  questions about six specific real documents, no abstract framing).
- `<harness>-<variant>.txt` — one file per arm: harness × prompt variant, 3 × 4
  = 12 arms total. Each file is the full raw response, harness metadata
  (model, tokens where reported) included at the top or bottom as that
  harness's CLI/tool reported it.

## Harnesses and model tiers used

- **Claude** — Agent tool, `general-purpose` subagent, `haiku` model override
  (cheap tier).
- **Codex** — `codex exec -c model_reasoning_effort=low --sandbox read-only`,
  default account model (gpt-5.5) at low reasoning effort (cheap tier;
  the ChatGPT-plan account this ran under does not expose the smaller
  `gpt-5-mini` / `gpt-5.1-codex-mini` model IDs — confirmed by direct
  `codex exec` calls with those model names both returning
  `"not supported when using Codex with a ChatGPT account"`).
- **Copilot** — `copilot -p ... --allow-all-tools --deny-tool='write'
  --deny-tool='shell'`, default model, authenticated as the employer
  (`jon-hill_gentiva` / `github.com/enterprises/gentivahs`) account per Jon's
  explicit instruction on the issue ("leave as is. I will be using my stuff at
  work."). The separate PR-review quota (`gh`'s Copilot bot on #132 and
  agent-evals#19) was exhausted at dispatch time; the CLI arm path used here
  is a different quota and did not hit any limit for these four calls.

No model was asked to write, move, or execute anything — every arm was a
read-only reasoning prompt over inlined text, run from a scratch directory
with no access to the four real repos' working trees. Codex ran with
`--sandbox read-only`; Copilot ran with `write` and `shell` explicitly denied.

## How to check independence

Each arm file states its own harness and prompt variant. To check whether the
12 arms actually reasoned independently rather than converging on a shared
"safe" answer: compare `*-blind.txt` (3 files) against `*-control.txt` and
`*-concrete.txt` (6 files) — the blind arms could not see repo names, the
fifth repo's actual category names, or agent-dotfiles' own git history, and
all three still landed on "subdivide the 12-document set," while 5 of 6
control/concrete arms landed on "stay flat." That is a real split correlated
with what information each arm had, not with which harness produced it — see
`docs-layout-council-138.md` §"Was the disagreement real?" for the full
tally and reasoning.
