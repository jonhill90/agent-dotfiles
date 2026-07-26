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
- Do not open issues for work already recorded as done in a milestone
  row. This repository's history lives in git and the provenance
  manifest, not in retroactive tickets.

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
4. **States:** Backlog (captured, not scheduled) → Todo → In Progress →
   Done.

## Closing issues from PRs — unverified

Linear closes issues from PR bodies via magic words (`Fixes AI-XX`;
`Refs AI-XX` links without closing), but that requires the Linear
workspace to have the GitHub integration connected to this repository.
**That connection has not been verified for `jonhill90/agent-dotfiles`.**

Until someone confirms it in Linear → Settings → Integrations → GitHub,
treat magic words as best-effort and close issues explicitly:

```bash
linear issue update AI-XX -s "Done"
```

## Numbering gotcha

Issue numbers are assigned at creation. Never write `Fixes AI-XX` for an
issue that does not exist yet — the number may be taken by the next
issue created and the magic word will close the wrong one.
