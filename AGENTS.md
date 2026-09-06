# agent-dotfiles — routing

This repository owns harness instructions, agent definitions and knowledge guidance.
Skill implementations live in the public/private skills repositories. Never copy
memory content or employer material here. CLAUDE.md is a symlink to this file.

Read only the surface needed for the task:

| Task | Canonical entry |
|---|---|
| Repository rules, verification, PR review and safety | [Repository policy](https://github.com/jonhill90/agent-dotfiles/blob/main/docs/canonical/repository-policy.md) — binding before edits |
| Requirements and design | [PRD](https://github.com/jonhill90/agent-dotfiles/blob/main/docs/canonical/PRD.md), [SPEC](https://github.com/jonhill90/agent-dotfiles/blob/main/docs/canonical/SPEC.md) |
| Shared memory and retrieval | [Memory](https://github.com/jonhill90/agent-dotfiles/blob/main/docs/canonical/memory.md), [store routing](https://github.com/jonhill90/agent-dotfiles/blob/main/docs/canonical/moc-map-of-maps.md) |
| Agent roles and definitions | [Agent roster](https://github.com/jonhill90/agent-dotfiles/blob/main/docs/canonical/agent-roster.md) |
| Harness and loop guidance | [Harness](https://github.com/jonhill90/agent-dotfiles/blob/main/docs/canonical/harness-engineering.md), [loop](https://github.com/jonhill90/agent-dotfiles/blob/main/docs/canonical/loop-engineering.md) |
| Knowledge intake/review workflow | [Estate canonical guide](https://github.com/jonhill90/agent-estate/blob/main/docs/knowledge-workflow.md) |
| All living specs and historical records | [Docs index](https://github.com/jonhill90/agent-dotfiles/blob/main/docs/index.md) |

Use a separate branch/worktree, preserve other agents' edits, and run the policy's
required checks. No Keychain writes. Knowledge changes do not authorize changing
config, overlays, hooks, scripts, scheduler, models or capacity controls.
