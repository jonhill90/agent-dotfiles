# agent-dotfiles

Dotfiles for AI coding agents: one versioned repo that makes any machine,
running any supported harness, behave like the same agent.

Portable Agent Skills form the common core and remain individually
installable. Canonical instructions, hooks, agents, settings, and MCP
declarations are the other managed layers, deployed at user scope via APM
plus a thin sync wrapper. Product requirements: [docs/PRD.md](docs/PRD.md);
technical design: [docs/SPEC.md](docs/SPEC.md).

## Install Skills

Browse the collection and select individual skills:

```bash
npx skills add jonhill90/agent-dotfiles
```

Install a specific skill:

```bash
npx skills add jonhill90/agent-dotfiles --skill primer
```

First-class harnesses (end state): Claude Code, Codex, GitHub Copilot, Pi.
Other Agent Skills-compatible harnesses may work through the same installer.

## Repository Model

```text
apm.yml          APM package manifest (user-scope deployment)
.apm/            APM source tree — symlinks into the canonical directories
skills/          Portable Agent Skills source
instructions/    Canonical global agent instructions + per-harness overlays
agents/          Reusable agent definitions
hooks/           Canonical hook scripts, harness-agnostic
settings/        Wrapper-owned config fragments (claude, pi, mcp)
evals/           Behavioral-parity scenarios and committed results
docs/            PRD, spec, provenance manifest, research
.agents/         Codex and cross-harness compatibility projection
.claude/         Claude-specific configuration and development hooks
.codex/          Codex-specific configuration and policy
.github/         GitHub Copilot instructions and repository automation
tools/           Standalone tools used by selected skills
```

Canonical content lives in the top-level directories. Harness directories
contain configuration or symlinks back to canonical source; they are not
independent copies, and the committed symlinks are slated for retirement
once the sync wrapper owns projection (SPEC §2).

## Core Workflow Skills

| Skill | Purpose |
|---|---|
| `primer` | Orient in an unfamiliar codebase |
| `using-tmux` | Operate persistent interactive terminal sessions safely |
| `closing-the-loop` | Produce implementation plans tied to verification |
| `create-skill` | Design portable skills with progressive disclosure |
| `validate-skill` | Validate skills against this repository's portable contract |

Additional skills integrate with GitHub, Azure DevOps, Linear, Microsoft Learn,
Context7, Obsidian, and YouTube transcripts. Install them selectively to avoid
overlapping triggers and unnecessary context.

General software-development methodology skills such as TDD, Git worktrees,
and parallel-agent dispatch are provided by
[Superpowers](https://github.com/obra/superpowers) and are intentionally not
duplicated here.

## Authoring Contract

Each skill lives at `skills/<name>/SKILL.md`:

```text
skills/example-skill/
├── SKILL.md
├── scripts/       Optional deterministic helpers
├── references/    Optional detail loaded on demand
└── assets/        Optional output resources
```

Portable skills use `name` and `description` frontmatter. The directory name
must match `name`. Keep the core instructions concise and move detail into
directly linked references.

Validate the repository:

```bash
python3 scripts/validate_repository.py
python3 -m unittest discover -s tests -v
```

## Distribution Direction

Two installation layers are intentional:

- `npx skills` installs independent public skills.
- APM installs the whole repo as a user-scope package (`apm install -g`),
  the backbone of the personal sync design (SPEC §1).

## Content Boundaries

- Generic personal workflow improvements should originate here.
- Project-specific deployment and operational policy remains in its project.
- Employer repository material is research input only and is not copied,
  migrated, or adapted into this repository.

See [docs/provenance-manifest.md](docs/provenance-manifest.md) for every
adopt/adapt/author/reject decision (and its predecessor,
[docs/migration-audit.md](docs/migration-audit.md), for the original skill
migration).

See [AGENTS.md](AGENTS.md) for contribution rules.
