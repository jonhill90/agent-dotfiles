# Linear (work tracking)

Linear is the system of record for work on this repository. Workspace
`jonhill90`, **team `AI`**, **project `agent-dotfiles`**.

Team `AI` predates this repository and carries unrelated closed work, so
issue numbers are not contiguous and a bare team listing is misleading.
Always file into the `agent-dotfiles` project and filter by it when
reading.

## Rules

- Open work that is expected to happen gets an issue. Milestones and
  verification items in `docs/SPEC.md` are the canonical descriptions;
  the issue is the tracking surface and cites the SPEC section rather
  than restating it.
- The SPEC remains the contract. When an issue and the SPEC disagree,
  the SPEC wins and the issue is corrected.
- **Parked decisions get an issue.** A decision deliberately deferred,
  benched, or rejected-pending-evidence carries a revisit trigger, and a
  trigger nothing surfaces never fires. File it in Backlog, titled
  `Parked: <subject>`, stating the decision, the trigger, and any
  ordering against a related candidate. The manifest row stays canonical;
  the issue exists only so the trigger is visible.
- Do not open issues for work already recorded as done in a milestone
  row. This repository's history lives in git and the provenance
  manifest, not in retroactive tickets. Backfilling finished work would
  create a second, lossier copy of facts git already owns — written from
  recollection rather than from the evidence that settled them.

## Access

The CLI is canonical, per the repository's standing preference for
CLI-backed workflows.

```bash
brew install schpet/tap/linear      # or: deno install -A -g -n linear jsr:@schpet/linear-cli
export LINEAR_API_KEY=lin_api_...   # Linear → Settings → API → Personal API keys
```

`.linear.toml` pins the team for this repository and is committed. The
`linear` skill in `skills/linear/` documents general CLI usage.

**The claude.ai Linear MCP connector is scoped to a different workspace
and cannot see team `AI`.** Do not reach for it here — it will return an
unrelated workspace's teams and issues. Use the CLI.

## Known CLI edges (v1.9.1)

These cost time if rediscovered:

- `.linear.toml` `team_id` takes the **team key** (`"AI"`), not a UUID.
  A UUID is uppercased internally and fails to resolve, so every command
  falls back to directory-name detection and reports
  `Could not determine team key`.
- `linear issue list` requires an explicit `--sort` (or
  `LINEAR_ISSUE_SORT`); without it the command errors instead of
  defaulting.
- `--no-color` is not accepted by `issue list` and prints usage instead
  of listing.
- `linear project create` fails opaquely on some flag combinations —
  dumping a raw JSON error and creating nothing. Create with `-n` and
  `-t` only, then set lead, status, and description in the UI.
- **Writes report success whether or not they applied.** Two ways this
  bites: passing `--no-color` to `issue update` swallows the change, and
  an unknown state name (`Backlog`, which team `AI` does not define) is
  silently ignored. Both print the issue URL and exit 0. **Always
  re-read after a write:**

  ```bash
  linear issue update AI-XX -s "Done"
  linear issue list --team AI --project "agent-dotfiles" \
    --all-states -A --sort priority --no-pager | grep AI-XX
  ```

  This is the same evidence rule the repo applies everywhere else: the
  command's exit status is not the result.

## Flow

1. **Find or create the issue** before or with the PR:
   ```bash
   linear issue list --team AI --all-states -A --sort priority --no-pager
   linear issue create --no-interactive --team AI --project "agent-dotfiles" \
     -s "Todo" -t "<plain title>" -d "<what done looks like; SPEC section>"
   ```
2. **Branch** with the repository's type prefix — `docs/`, `feat/`,
   `chore/` — or the Linear-generated branch name.
3. **PR** per the normal flow; CI gates on `pull_request`.
4. **States:** `ToDo` → `In Progress` → `Done` (plus `Canceled`).
   **Team `AI` has no Backlog state.** Setting one silently no-ops — see
   below. Work that is captured but deliberately not actionable carries
   the `parked` label instead of a state.

## Closing issues from PRs — verified 2026-07-26

The GitHub integration **is** connected. PRs #45 and #46 auto-attached
to AI-259 and AI-260 without any manual step, so `Refs AI-XX` in a PR
body links the PR to the issue and `Fixes AI-XX` closes it on merge.

State still has to be set explicitly when a PR does not carry a magic
word:

```bash
linear issue update AI-XX -s "Done"     # then verify — see below
```

## Numbering gotcha

Issue numbers are assigned at creation. Never write `Fixes AI-XX` for an
issue that does not exist yet — the number may be taken by the next
issue created and the magic word will close the wrong one.
