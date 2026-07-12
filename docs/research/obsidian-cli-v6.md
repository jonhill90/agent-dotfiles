# V6: Obsidian CLI Selection (Official vs Third-Party)

- **Date:** 2026-07-12
- **Question (SPEC §11 V6, blocks M4):** does the official Obsidian CLI
  cover the memory backend's needs well enough to replace the
  third-party obsidian-cli the `obsidian` skill wraps?
- **Criteria:** the five checks in
  [evals/acceptance/obsidian.md](../../evals/acceptance/obsidian.md) —
  headless create, read, search, append/update, deterministic vault
  resolution with no GUI dependency.
- **Method:** official docs + release coverage (web, 2026-07-12);
  hands-on inspection of the installed third-party CLI. Official CLI
  could not be trialed hands-on (see machine-state findings).

## Verdict

**Keep the third-party obsidian-cli (Yakitrak) for v1, pinned.** The
official CLI fails acceptance check 5 by design and is not installable
on this machine today. Revisit trigger defined below.

## The contenders

### Official Obsidian CLI (`obsidian`) — shipped in app v1.12.4 (2026-02-27)

- 100+ commands: create/read/search/append, plus daily notes, tasks,
  templates, plugin management, JS execution, TUI mode. Vault targeting
  by `vault=<name>` — deterministic.
- **Architecture: a remote control for the running desktop app.** If
  Obsidian isn't running, the first command launches it. Not a
  standalone binary; no true headless mode. macOS install requires
  admin privileges (symlink creation).
- Official headless client exists (`ob`, obsidianmd/obsidian-headless,
  Node 22+) but covers **Sync/Publish only** — no note CRUD; it exists
  for CI sync, not vault manipulation.

### Third-party obsidian-cli v0.2.3 (Yakitrak; installed at ~/bin)

- create (`--content`, `--append`, `--overwrite`), print, search,
  search-content, frontmatter view/modify, move (updates links), list,
  set-default/print-default.
- **Architecture: direct file operations.** GUI touched only with an
  explicit `--open` flag. Vault name → path resolved from Obsidian's
  own registry plus its own default-vault config — deterministic with
  the app closed.

## Acceptance scoring

| Check | Official CLI | Third-party CLI |
|---|---|---|
| 1. Create note w/ frontmatter, non-interactive | PARTIAL — works, but auto-launches the app | PASS (file write) |
| 2. Read note by path | PASS | PASS (`print`) |
| 3. Search vault | PASS (real search index — *better* results) | PASS (`search-content`; plain text match) |
| 4. Append/update without clobbering | PASS (`append`) | PASS (`create --append`, `frontmatter`) |
| 5. Deterministic vault, no GUI dependency | **FAIL** — requires the app process by design | PASS |

Also decisive for the PRD's portability rubric: Pi/CI/headless-Linux
contexts (Phase 3) can never run the official CLI; the third-party
binary runs anywhere files exist.

## Machine-state findings (this Mac, 2026-07-12)

1. **Obsidian.app is 1.5.12** (~2 years old) — below the 1.12.4 the
   official CLI ships with. The official CLI isn't even present until
   the app updates. Not a blocker for the verdict; noted for hygiene.
2. **⚠ The current default vault is employer-hosted:** `Second Brain`
   at `~/Library/CloudStorage/OneDrive-Gentiva/...`. The memory vault
   (`AGENT_MEMORY_VAULT`) **must not** point there — personal agent
   memory syncing through employer storage violates the employer
   boundary (AGENTS.md/PRD). **New spec requirement:** `sync doctor`
   must fail if `AGENT_MEMORY_VAULT` resolves under a corporate mount
   (`OneDrive-<Org>` pattern), and M4 setup must create/choose a
   personal vault (Obsidian Sync or iCloud) for memory.

## Consequences

- `obsidian` skill keeps wrapping the third-party CLI; pin `v0.2.3`
  (or latest tag at M4) in the install tooling.
- Official CLI becomes an optional *human-side* enhancement (daily
  notes, tasks, templates via TUI) — not part of the agent contract.
- **Revisit trigger:** the official CLI (or `ob`) gains GUI-free note
  CRUD, or the third-party CLI is abandoned upstream. Then re-run the
  same acceptance checks — the criteria file, not this doc, is the
  contract.

Sources: [Obsidian CLI help](https://obsidian.md/help/cli),
[Obsidian 1.12 changelog](https://obsidian.md/changelog/2026-02-27-desktop-v1.12.4/),
[obsidianmd/obsidian-headless](https://github.com/obsidianmd/obsidian-headless),
[Headless Sync help](https://obsidian.md/help/sync/headless),
[DEV overview of the official CLI](https://dev.to/shimo4228/obsidians-official-cli-is-here-no-more-hacking-your-vault-from-the-back-door-3123)
