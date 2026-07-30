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

First-class harnesses: Claude Code, Codex, GitHub Copilot, Pi — all four
sync-managed and eval-verified; breakage on any of them blocks release.
Other Agent Skills-compatible harnesses may work through the same installer.

## Repository Model

```text
apm.yml          APM package manifest (user-scope deployment)
.apm/            APM source tree — symlinks into the canonical directories
skills/          Portable Agent Skills source
instructions/    Canonical global agent instructions + per-harness overlays
agents/          Reusable agent definitions
hooks/           Canonical hook scripts, harness-agnostic
settings/        Wrapper-owned config fragments (claude, copilot, pi, mcp)
                 plus default-skills.txt, the per-harness skill roster
scripts/         Sync wrapper, repository validation, static-context measurement
tests/           Unit suite plus evals/ (scenarios, counter-scenarios, harness, results)
docs/            Living product, architecture, memory, and eval documentation
.claude/         Claude-specific repo-development configuration and hooks
.github/         GitHub Copilot instructions and repository automation
```

Canonical content lives in the top-level directories. Deployment is
installer-owned: `apm install -g` places skills/instructions/agents at
user scope and `scripts/sync.py apply` covers what APM does not (Pi
projection, settings merges, teardown). The committed symlink matrix is
retired (SPEC §2).

## Where a Skill Belongs

Decide this before writing anything. Most skills do **not** belong in this
repository, and nothing here should ever be copied into a project.

| Situation | Where it goes | Evidence bar |
|---|---|---|
| Useful in every project, every day | this repo's roster | **applies** — §10.1 |
| Only true in one repository | that repo's `.claude/skills/` or `.agents/skills/` | none |
| Useful often, not always | roster, marked `name-only` so it lists without its description | applies |
| Needed once, or maintained by someone else | nothing installed — `npx skills use <package>@<skill>` | none |

**The evidence bar governs the roster, not every skill you write.** A skill
that ships to four harnesses on every request has to earn that cost. A
skill in one project costs nothing anywhere else and needs no eval, no
scenario and no manifest row. Do not run the ladder on a project skill.

### Someone else's skill

Vendor and community collections — Azure, Microsoft, a teammate's — are
**never vendored** into this repository. Two ways to reach them:

```bash
# find what exists (runs non-interactively; an agent can call it too)
npx skills find azure

# install into THIS project only — pinned by content hash in skills-lock.json
npx skills add microsoft/azure-skills \
  --skill azure-prepare --skill azure-validate --skill azure-deploy \
  --agent '*' -y

# a private source works identically — any path or URL the machine can reach
npx skills add git@github.com:you/private-skills.git --skill internal-deploy --agent '*' -y
```

Verified rather than assumed: `$HOME` is untouched, the skills land in
`.agents/skills/` with a `.claude/skills/` symlink, and `skills-lock.json`
pins content hashes so the install is reproducible.

Two things to expect. **Collections are often workflows, not menus** — the
Azure skills reference each other, and `azure-deploy` refuses to run without
`azure-prepare` and `azure-validate`, so the unit is a cluster (~550 tokens).
And **Pi gates project skills behind Project Trust**, which in
non-interactive mode falls back to ignoring them; set
`defaultProjectTrust: "always"` if you need them headless.

`npx skills use <pkg>@<skill>` exists but does something different: it prints
a prompt to stdout for you to paste. It does not install and does not make a
skill reachable by an agent.

### Project skills

Put them in the project, next to the code they describe:

```text
your-project/
├── .claude/skills/deploy-widget/SKILL.md    # Claude Code
└── .agents/skills/deploy-widget/SKILL.md    # Codex, Copilot, Pi
```

They travel with the repository, teammates get them by cloning, and they
cost nothing in any other project. Two behaviours worth knowing: skills
**hot-reload**, so adding one takes effect without restarting; and a
project skill **overrides a bundled skill of the same name**, which is how
one repository replaces `/code-review` locally without affecting others.

Nested directories work too — a skill under `apps/web/.claude/skills/`
loads when the agent touches that package, which suits a monorepo.

## Core Workflow Skills

The default roster is `settings/default-skills.txt`. It is **scoped per
harness**, not one flat list: a skill can ship to some harnesses and be
disabled on others. Where the roster scopes a skill away from a harness,
the wrapper writes that exclusion into that harness's own settings, so the
roster is enforced rather than merely declared. All four harnesses are
covered: `skillOverrides` on Claude Code, `disabledSkills` on Copilot, a
`[[skills.config]]` block on Codex, and a `skills` denylist on Pi
(SPEC §4.1).

| Skill | Purpose | Deployed to |
|---|---|---|
| `create-skill` | Design and validate portable skills with progressive disclosure | all four |
| `failing-test-first` | Reproduce a bug with a failing test before fixing it | all four |
| `github-cli` | Pull requests, issues, workflows, releases via `gh` | all four |
| `linear` | Linear issues and projects via the Linear CLI | all four |
| `memory-conventions` | Read and write durable memory in the Obsidian vault | all four |
| `obsidian` | Notes, vaults and daily notes via the Obsidian CLI | all four |
| `safe-deletion` | Verify contents match their described purpose before deleting | all four |
| `tmux` | Operate persistent interactive terminal sessions safely | all four |

The per-harness mechanism is built and enforced on all four harnesses, but
**nothing currently uses it** — every harness resolves the same eight
skills. `sanity-check` was its one live instance until 2026-07-29, when it
moved to public opt-in for failing §10.1 rule 5: no skill-rung run was ever
measured, and its counter-scenario is explicitly invalid.

Four further skills are published here but excluded from the default
package — `primer`, `close-the-loop`, `dispatching-subagents`, and
`sanity-check` —
because no failing eval justified their static description cost. All four
remain independently installable, and the reasoning for each is recorded in
[docs/provenance-manifest.md](docs/provenance-manifest.md).

The behavioral layer is deliberately minimal: loop discipline lives in the
canonical instructions, and skills are added only when a failing eval
justifies them (baseline-first rule — see
[docs/SPEC.md](docs/SPEC.md) §4). Each kept tool skill has acceptance
checks under [tests/evals/acceptance/](tests/evals/acceptance/).

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
