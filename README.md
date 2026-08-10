# agent-dotfiles

Dotfiles for AI coding agents: one versioned repo that makes any machine,
running any supported harness, behave like the same agent.

Canonical instructions, hooks, agents, settings, and MCP declarations are
managed here and deployed at user scope via APM plus a thin sync wrapper.
Product requirements: [docs/PRD.md](docs/PRD.md); technical design:
[docs/SPEC.md](docs/SPEC.md).

**Four repositories, one harness (#9, #10):**

| Repository | Owns |
|---|---|
| `jonhill90/agent-dotfiles` (this repo) | canonical instructions, hooks, agents, settings, MCP config, install/sync behavior, and the skill *roster* (`settings/default-skills.txt`) — not skill content |
| [`jonhill90/skills`](https://github.com/jonhill90/skills) | portable public Agent Skills content, individually installable |
| `jonhill90/skills-private` | portable private Agent Skills content, authenticated, consumed the same way |
| `jonhill90/agent-evals` (private) | behavioral scenarios, counter-scenarios, harness runners, results/transcripts, scoring/arming tools, eval methodology |

This repository declares the two skill collections as pinned `apm.yml`
dependencies (see "Skill Sources" below) rather than vendoring skill
content — it does not contain a `skills/` directory.

## Install the Harness

On a new machine, clone and run the bootstrap. This is the path the
new-machine criterion in [docs/PRD.md](docs/PRD.md) is measured against:

```bash
git clone https://github.com/jonhill90/agent-dotfiles.git
cd agent-dotfiles && ./install.sh          # --non-interactive to skip prompts
python3 scripts/sync.py apply
python3 scripts/sync.py doctor             # environment checks
```

`install.sh` prompts once for `$AGENT_MEMORY_VAULT`, writes a marker-fenced
block to your shell profile, and sources `~/.zshrc.local` if present.
**It does not prompt for MCP credentials** — set `CONTEXT7_API_KEY` yourself;
`doctor` reports it missing.

## Install Individual Skills

Skill content lives in [`jonhill90/skills`](https://github.com/jonhill90/skills)
(public) and `jonhill90/skills-private` (private, authenticated), not here.
Browse and select from the public collection directly:

```bash
npx skills add jonhill90/skills
npx skills add jonhill90/skills --skill primer
```

The private collection works identically, authenticated by whatever `git`
already has configured for `github.com` (GitHub CLI's credential helper,
an SSH key, or `GITHUB_APM_PAT`):

```bash
npx skills add jonhill90/skills-private
```

First-class harnesses: Claude Code, Codex, GitHub Copilot, Pi — all four
sync-managed; breakage on any of them blocks release.
Other Agent Skills-compatible harnesses may work through the same installer.

## Repository Model

```text
apm.yml          APM package manifest — also declares the two pinned skill-
                 source dependencies (jonhill90/skills, jonhill90/skills-private)
apm.lock.yaml    Resolved commit + content hash per dependency (committed)
.apm/            APM source tree — symlinks into the canonical directories
instructions/    Canonical global agent instructions + per-harness overlays
agents/          Reusable agent definitions
hooks/           Canonical hook scripts, harness-agnostic
settings/        Wrapper-owned config fragments (claude, copilot, pi, mcp)
                 plus default-skills.txt, the per-harness skill roster
scripts/         Sync wrapper, repository validation, static-context measurement
tests/           Unit suite for scripts/ (behavioral evals live in the
                 private jonhill90/agent-evals repository — see #10)
docs/            Living product, architecture, and memory documentation
.claude/         Claude-specific repo-development configuration and hooks
.github/         GitHub Copilot instructions and repository automation
```

Canonical content lives in the top-level directories. Deployment is
installer-owned: `apm install -g` resolves the two skill-source
dependencies plus instructions/agents and places them at user scope;
`scripts/sync.py apply` covers what APM does not (Pi projection, settings
merges, teardown). The committed symlink matrix is retired (SPEC §2).

## Skill Sources

`apm.yml`'s `dependencies.apm` list declares two skill-bundle
dependencies, each pinned to a commit SHA — never a branch or tag, so
`apm install` resolves the same content every time
(`scripts/validate_repository.py`'s `validate_skill_source_pins` enforces
this):

```yaml
dependencies:
  apm:
    - git: https://github.com/jonhill90/skills.git
      ref: <commit-sha>
      skills: ["*"]
      alias: skills-public
    - git: https://github.com/jonhill90/skills-private.git
      ref: <commit-sha>
      skills: ["*"]
      alias: skills-private
```

`python3 scripts/sync.py status` and `doctor` print the pinned
`repo_url@short-sha` for each, read from the deployed
`~/.apm/apm.lock.yaml` — the same file `apm install -g` writes.

**Atomicity — scoped to what is actually guaranteed.** `scripts/sync.py`'s
`apply()` snapshots `~/.claude/skills` and `~/.agents/skills` (rename
aside, never copy or delete) before calling `apm install -g`, and restores
them verbatim if that specific step fails — whether `apm` returns a
nonzero exit code *or* raises before returning a result at all (missing
binary, OS error). The snapshot is discarded only once `apm install`
itself has succeeded. This covers the two skill-content directories around
that one step; it is not a whole-`apply()` transaction — root-instruction
compilation has its own separate detach/restore (unchanged, pre-#9), and
later `apply()` steps (settings merges, MCP merges, Pi projection,
teardown) carry no rollback of their own.

**Fail-closed on an unresolved backup.** If a previous `apply()` was
interrupted before it could restore or discard its snapshot, a `.bak`
survives — the only remaining last-known-good copy. The next `apply()`
never overwrites or deletes it: it refuses to run `apm` at all and exits
non-zero with the exact path and a recovery instruction.
`python3 scripts/sync.py doctor` also flags an unresolved backup outside
of an `apply()` attempt. Recover explicitly with
`python3 scripts/sync.py apply --recover-skills-backup` (restores the
backup over the live directory; last-known-good wins) once you've
confirmed which copy is correct.

Proven against a real broken private ref, not just a mock: `apm install`
deployed the public skills, then failed cloning the private one (`git
checkout` exit 128), and `apply()` restored the prior 8-skill set
byte-for-byte (sha256-verified) and returned the failing exit code.

## Stale Global Registrations and Recovery

`apm install -g` is additive: every machine that has ever run it carries a
*global* manifest, `~/.apm/apm.yml`, distinct from this repo's own
`apm.yml`. Every `apm install -g <path>` a machine has ever run — not just
agent-dotfiles' own — adds a `path:`-registered entry there and leaves its
content cached under `~/.apm/apm_modules/_local/<name>`. Neither is pruned
when the source directory is deleted, moved, or its shape changes (a skill
renamed or removed upstream). A real deployment surfaced exactly this
(#11 → #14): two registrations pointed at deleted temp directories, and a
third — a local checkout of `jonhill90/skills` registered before its #126
restructuring — had three of its twelve originally-requested skill names
(`az-devops`, `gh-cli`, `using-tmux`) renamed or deleted out from under it.
`apm compile` does not fail on this; it silently accumulates cached
content from every stale registration into whatever it compiles next. The
Copilot legacy surface, `~/.copilot/copilot-instructions.md`, ended up
with four consecutive copies of the same canonical instructions block,
each carrying a `<!-- apm:source:NAME -->` comment naming a different
stale registration.

### Registration identity is full-path; cache and marker identity is basename-only

**This mismatch is the reason recovery cannot be "just uninstall the exact
stale path" (#15).** `~/.apm/apm.yml` distinguishes registrations by their
full path, but `~/.apm/apm_modules/_local/<name>` and every compiled
`<!-- apm:source:NAME -->` marker are keyed by `Path(local_path).name` —
the basename alone. The real manifest that motivated #14 has exactly this:
two *different* temp-directory registrations that both happen to end in a
subdirectory literally named `repo`, sharing one cache slot,
`_local/repo`, between two unrelated sources. This is not limited to two
stale entries colliding with each other — a stale registration sharing a
basename with a currently-legitimate one is exactly as unsafe, and so is
two otherwise-fine registrations sharing one. `apm uninstall -g
<exact-path>` operates on the full-path manifest entry; it does **not**
by itself prove the basename-keyed cache slot or source marker now belongs
cleanly to whichever registration is left. Treating a single exact-path
uninstall as isolated recovery is false and is not what this repository
does.

**Detection, in `status` and `doctor`:**

- `[stale-global] <path>: <reason>` in `status`, and a `stale-global-registrations`
  check in `doctor` — one line per stale entry in `~/.apm/apm.yml`, naming
  the exact path. A registration is stale when its source directory no
  longer exists, when the source has no package markers at all (no
  `apm.yml`, no root `SKILL.md`, no `skills/<name>/SKILL.md` bundle), or
  when it is a bare skill-bundle registration (no `apm.yml` of its own)
  whose requested `skills:` selection names something no longer present
  in the bundle. **A registration with its own `apm.yml` is never flagged**
  — a real, independent global package's manifest is authoritative about
  itself; #14 requires not rejecting one just because its `skills/`
  directory happens to differ from what was last requested. A `skills:`
  value that cannot be parsed as a list (a hand-edited or foreign-tool
  flow-style `skills: [a, b]`, or any other shape) fails closed the same
  way, rather than crashing or being silently trusted.
- `[basename-collision] <basename>: <path>, <path>, ...` in `status`, and a
  `local-registration-basename-collisions` check in `doctor` — every
  group of two or more registrations that resolve to the same
  `Path(path).name`, named by the shared basename and every full path in
  the group. Checked independently of staleness: the collision itself is
  the hazard, whether or not either colliding registration would
  individually be flagged stale.
- `[source-blocks] <path>: <finding>` in `status`, and a
  `compiled-root-sources` check in `doctor` — every compiled root file
  (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.copilot/AGENTS.md`,
  `~/.copilot/copilot-instructions.md`, `~/.pi/agent/AGENTS.md`) is
  scanned for `apm:source` blocks. Zero blocks is normal for most of them
  (they use a different, single-line marker). More than one block, or any
  block not naming the current local package, is flagged by exact file
  and source name.

**`apply()` fails closed.** If `status`/`doctor` would report a stale
global registration *or* a basename collision, `apply()` refuses to
invoke `apm` at all — checked first, before even the skill-directory
backup — and exits non-zero naming every stale path and every colliding
group. It does not attempt to guess which registration is safe to ignore,
and a collision-only state (neither registration individually stale)
fails closed exactly the same as a stale-only state.

### Recovery

**Manual, reviewable, and only through APM's own mechanism — never
arbitrary directory deletion, and never hand-edited `apm.yml` or
`apm_modules/`.** The exact steps differ depending on what `status`/`doctor`
reported:

**No basename collision — a stale path stands alone.** Safe to evaluate
and remove on its own:

```bash
apm uninstall -g <path> --dry-run   # review what it would remove
apm uninstall -g <path>             # then actually remove it
```

**A basename collision is reported — evaluate and recover the whole group,
not one path at a time:**

1. **Snapshot first.** Back up `~/.apm/apm.yml` and
   `~/.apm/apm_modules/_local/<shared-basename>/` before touching
   anything, so the pre-recovery state is recoverable if a step below
   goes wrong.
2. **Dry-run every path in the group**, not just the one you believe is
   stale — `apm uninstall -g <path> --dry-run` for each. Read every
   output. The shared cache slot means a dry-run for one path may not
   fully reflect what is actually cached there if another registration in
   the group last wrote it.
3. **Decide the group's outcome as a whole**: which paths are genuinely
   gone or invalid, and which (if any) is the one you want to keep. Do
   not assume the uninstall of one leaves the other's identity clean —
   the shared basename means it may not.
4. **Uninstall every path in the group** with `apm uninstall -g <path>`
   (real, not dry-run) — including a path you intend to keep, if that is
   the only way to guarantee the shared cache slot and `apm:source`
   marker no longer carry another registration's stale content.
5. **Reinstall the surviving, legitimate registration** (`apm install -g
   <path>`) *before* running `apm compile` or `sync.py apply` again — the
   basename's cache slot must be repopulated from the source you actually
   want, not left empty or with residue from step 4.
6. Re-run `sync.py doctor`. Confirm `stale-global-registrations`,
   `local-registration-basename-collisions`, and `compiled-root-sources`
   are all clean before running `apply()`.

Never claim, and never assume, that removing one path out of a
basename-colliding group is isolated to that path alone.

## Where a Skill Belongs

Decide this before writing anything. Most skills do **not** belong in this
repository, and nothing here should ever be copied into a project.

| Situation | Where it goes | Evidence bar |
|---|---|---|
| Useful in every project, every day, and shareable | author it in `jonhill90/skills`, roster it here (`settings/default-skills.txt`) | **applies** — §10.1 |
| Useful every day but must not be public | author it in `jonhill90/skills-private`, roster it here the same way | **applies** — §10.1 |
| Only true in one repository | that repo's `.claude/skills/` or `.agents/skills/` | none |
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

The default roster is `settings/default-skills.txt` — currently a flat list
of eight names. The wrapper *can* scope it per harness, and enforces that on
all four, but nothing uses the mechanism today. Where the roster scopes a skill away from a harness,
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

Five further skills are published here but excluded from the default
package — `primer`, `close-the-loop`, `dispatching-subagents`,
`sanity-check`, and `supervised-lane-loop` —
because no failing eval justified their static description cost. All five
remain independently installable, and the reasoning for each is recorded in
[docs/provenance-manifest.md](docs/provenance-manifest.md).
`supervised-lane-loop` is the newest and the least measured: it is vendored
practice from another repository, carries its own "practice, not measured"
status line, and has no eval behind it at all.

The behavioral layer is deliberately minimal: loop discipline lives in the
canonical instructions, and skills are added only when a failing eval
justifies them (baseline-first rule — see
[docs/SPEC.md](docs/SPEC.md) §4). Each kept tool skill has acceptance
checks under `tests/evals/acceptance/` in the private repository
jonhill90/agent-evals, evidence unavailable publicly.

## Authoring a New Skill

Skill content is authored in `jonhill90/skills` (public) or
`jonhill90/skills-private` (private only) — never here. Each has its own
`skills/<name>/SKILL.md` authoring contract and validator; see that
repository's `AGENTS.md`.

To roster a skill that already exists in one of those two repositories:

1. Add its name to `settings/default-skills.txt` here.
2. Bump the corresponding dependency's `ref:` in `apm.yml` if the skill
   was just added upstream (pinned refs do not move on their own).
3. Run `python3 scripts/validate_repository.py` — `validate_skill_source_pins`
   confirms the ref is still a commit SHA, not a branch.

Validate this repository (roster, instructions, projections — not skill
content, which is validated in its own repository):

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
