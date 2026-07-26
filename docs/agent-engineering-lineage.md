# Agent Engineering Lineage

Reference for the vocabulary around agent design: what each term means,
who coined it and when, which vendor documents it, and which layer of
the stack it governs. Recorded because the naming churns fast — four
labels arrived between 2020 and July 2026 — while the practices under
them mostly did not.

This document is not a methodology. It exists so that a term appearing
in a prompt, an article, or a PR can be resolved to a layer and a
primary source instead of adopted on vibes.

## The four layers

Terms are aliases for layers, not competitors. Each layer contains the
one above it.

| Layer | Question it answers | Term of the moment |
|---|---|---|
| 1. Instruction | What goes in the window? | prompt engineering |
| 2. Window | What stays in it, and for how long? | context engineering |
| 3. Iteration | What re-runs the model until done? | loop engineering |
| 4. Composition | How do several loops connect? | graph engineering |

The layers are cumulative. A graph's nodes are loops; each step of a
loop is a managed context; a context contains prompts. "Loops versus graphs"
was never a real opposition — see *Contested claims* below.

## Layer 1 — Prompt engineering

Writing and organising the instructions themselves. Oldest of the four,
universally documented, no longer contested.

- Google: [Prompt Engineering whitepaper](https://www.kaggle.com/whitepaper-prompt-engineering)
  (Lee Boonstra, September 2024, 69pp) — 12 techniques including ReAct.
- OpenAI: [prompt engineering guide](https://developers.openai.com/api/docs/guides/prompt-engineering)
  and the per-model [GPT-5 prompting guide](https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide).
- Microsoft: [prompt engineering techniques](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/prompt-engineering).

## Layer 2 — Context engineering

Coined by **Dex Horthy** (HumanLayer), April 2025. Curating and
maintaining the set of tokens present at inference — system prompt,
tools, examples, history, retrieved data — as a finite resource those
consumers compete for.

Anthropic's framing is the cleanest available: prompt engineering is
writing instructions; context engineering is curating what lands in the
window around them.

- Anthropic: [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  (2025-09-29); [Claude Cookbook — compaction, tool-result clearing,
  memory](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools).
- Microsoft: [ai-agents-for-beginners ch. 12](https://github.com/microsoft/ai-agents-for-beginners/blob/main/12-context-engineering/README.md)
  — splits context into instructions, knowledge, tools.
- OpenAI: [session memory / trimming and compression](https://cookbook.openai.com/examples/agents_sdk/session_memory).
- Non-vendor: [12-factor-agents](https://github.com/humanlayer/12-factor-agents),
  especially [factor 3, own your context window](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md).

Caveat on sourcing: the widely-quoted definition "the discipline of
designing and building dynamic systems that provide the right
information and tools, in the right format, at the right time" is
Philipp Schmid's personal blog post. He works at Google DeepMind, but
it is not a Google publication and should not be cited as one.

## Layer 3 — Loop engineering

Popularised by **Addy Osmani**, 2026-06-07, building on Boris Cherny
(Anthropic) and Peter Steinberger. Thesis: stop being the person who
prompts the agent; design the system that does it instead.

A loop is plan → act → check → continue/stop, running until a
termination condition fires. Osmani's components: automations
(scheduling, which is what makes it a loop rather than a session),
worktrees, skills, connectors, subagents for verification, plus
persistent external state so progress survives between runs.

- [Loop Engineering](https://addyosmani.com/blog/loop-engineering/) —
  the origin essay; [O'Reilly Radar repost](https://www.oreilly.com/radar/loop-engineering/).
- **No vendor documents this term.** The nearest vendor primary is
  Anthropic's [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
  (2025-11-26), which describes the same discipline six months earlier
  under "harness": an initializer agent plus a coding agent that leaves
  artifacts for the next context window, framed as engineers working
  shifts with no memory of the previous shift. Reference
  implementation: [anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents).

This repository's `closing-the-loop` skill occupies this layer.

## Layer 4 — Composition

Two distinct things get discussed here. Keep them apart.

**Orchestrator-workers** is the durable one. A central model decomposes
a task, delegates to workers, and synthesises results; the
distinguishing feature is that subtasks are *not* pre-defined but chosen
by the orchestrator from the input. Documented by Anthropic in December
2024 — eighteen months before either 2026 buzzword.

- Anthropic: [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
  (the pattern); [How we built our multi-agent research
  system](https://www.anthropic.com/engineering/multi-agent-research-system)
  (lead agent + subagents in production, reported 90.2% over
  single-agent at ~15x the tokens of normal chat); [when *not* to use
  multi-agent](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them).
- OpenAI: [A Practical Guide to Building Agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)
  — manager pattern (agents-as-tools) vs. handoffs.
- Google: [ADK workflow agents](https://google.github.io/adk-docs/agents/workflow-agents/)
  — Sequential, Parallel, and Loop as named API primitives.
- Microsoft: [Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/)
  — graph workflows with typed edges and checkpoint/resume.

**Graph engineering** is the label. Posed by Peter Steinberger on
2026-07-18; formalised hours later by Hamel Husain as "Loop Engineering
Is Dead. Enter Graph Engineering." Nodes (agents, calls, code, human
decisions), edges (conditional routing), state (what flows between).
No vendor uses the term.

The load-bearing design question at this layer, per Anthropic, is the
**isolation boundary**: what does each worker need to know about what
the others are doing? For research their answer is "almost nothing" —
self-contained task, output format, fresh context window.

## Contested claims

Recorded so they are not re-litigated.

- **"Loop engineering is dead."** False framing. A loop is a graph whose
  path returns to an earlier node, and graphs contain loops. Nothing was
  superseded. ([Turing Post](https://www.turingpost.com/p/is-graph-engineering-real-why-everyone-is-talking-about-it),
  [Louis Bouchard](https://www.louisbouchard.ai/graph-engineering-explained/))
- **"18% higher accuracy, 85% lower cost."** Traced to a narrow
  industrial-diagram study, not industry adoption. Do not cite.
- **"Microsoft, Stanford and Anthropic all adopted graph engineering."**
  Disparate projects retold as a coordinated shift.
- **The structure is not new.** Workflow engines and DAG schedulers have
  drawn these graphs for a decade; LangChain says so
  [themselves](https://www.langchain.com/blog/3-years-of-graph-engineering-with-langgraph).
  What changed is that nodes now behave non-deterministically.
- **Multi-agent consensus is not verification.** Several agents on the
  same model reading the same flawed context produce agreement, not
  correctness — "organised nonsense at scale." Verification requires
  external evidence: test output, real transactions, human review. This
  is the same evidence rule this repo applies to its own evals (SPEC
  §10.1).

## Framing above the stack

Andrej Karpathy has not written on any of the four terms. His
contribution is the frame they sit inside: Software 3.0 — the context
window is the program, the model is the interpreter, and the surrounding
system starts to look like an operating system
([Latent Space writeup](https://www.latent.space/p/s3)).

## Relevance to this repository

- Layers 1–2 are covered by `instructions/global.instructions.md` and
  the token budget (SPEC §6) — the budget *is* a context-engineering
  control.
- Layer 3 is covered by the `closing-the-loop` skill.
- Layer 4 is covered by `dispatching-subagents`, which is deliberately
  written as decision discipline rather than harness plumbing: subagent
  spawning is not portable across the v1 harness set, so the skill must
  degrade to sequential self-execution (SPEC §4.1, harness-engineering
  portability rule).
- The awesome-list ecosystem around "harness engineering" (six
  near-identical repositories within weeks) is a hype signal, not a
  source. Cite the primaries above instead.
