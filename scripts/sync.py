#!/usr/bin/env python3
"""agent-dotfiles sync wrapper — everything APM does not own (SPEC §7).

Commands:
  apply   preflight -> apm install -g -> teardown -> Pi projection ->
          settings merges -> mcp merge -> state file
  status  report managed surfaces vs recorded state
  doctor  environment checks (CLIs, env vars, root-file ownership)
  remove  reverse everything recorded in state

Python 3 stdlib only. Idempotent throughout.

Split by responsibility across sync_*.py modules (agent-dotfiles#335, follow-
up to #332's test split). This file is the composition root: every public
name the old single 2141-line module exposed is still importable from here
under its original name, and `Sync` is still one class assembled from
per-responsibility mixins so every method keeps its original signature and
`self` access to the others. Behaviour-preserving -- no new features, no
signature changes.
"""

from __future__ import annotations

import argparse
import os
import subprocess  # noqa: F401 -- re-exported; tests patch sync.subprocess.run
import sys
from pathlib import Path

from sync_constants import (  # noqa: F401 -- re-exported for callers/tests
    ABSENT,
    APM_MARKER,
    CODEX_MCP_BEGIN,
    CODEX_MCP_END,
    CODEX_SKILLS_BEGIN,
    CODEX_SKILLS_END,
    COMPILED_ROOT_FILES,
    HARNESS_ROOT_FILES,
    MANAGED_ROOT_FILES,
    NEUTRAL_HARNESSES,
    OVERLAY_BEGIN,
    OVERLAY_END,
    OVERLAY_FILES,
    SOURCE_BLOCK_RE,
    SYNC_MARKER,
    UNUSED_ROOT_FILES,
)
from sync_util import (  # noqa: F401 -- re-exported for callers/tests
    CORPORATE_MOUNT_HINTS,
    _description_of,
    deep_merge,
    is_corporate_mount,
    overlay_body,
    resolve_hook_commands,
    strip_frontmatter,
)
from sync_skills import (  # noqa: F401 -- re-exported for callers/tests
    BENCH_SECTION,
    SKILL_MODIFIERS,
    _parse_skill_roster,
    _split_modifier,
    apm_dependency_block,
    benched_skills,
    claude_skill_overrides,
    codex_disabled_skills,
    copilot_disabled_skills,
    declared_skill_source_pins,
    load_default_skills,
    load_skill_roster,
    neutral_union,
    pi_disabled_skills,
    roster_union,
    skill_modifiers,
    skill_source_aliases,
)
from sync_manifest import (  # noqa: F401 -- re-exported for callers/tests
    basename_collisions,
    parse_global_local_packages,
    stale_global_registration,
)
from sync_core import SyncCoreMixin
from sync_git_hooks import GitHooksMixin
from sync_pi import PiMixin
from sync_root_files import RootFilesMixin
from sync_skill_backup import SkillBackupConflict, SkillBackupMixin  # noqa: F401
from sync_settings_merge import SettingsMergeMixin
from sync_mcp import McpMixin
from sync_commands import CommandsMixin


class Sync(
    SyncCoreMixin,
    GitHooksMixin,
    PiMixin,
    RootFilesMixin,
    SkillBackupMixin,
    SettingsMergeMixin,
    McpMixin,
    CommandsMixin,
):
    """Everything this wrapper owns (SPEC §7), assembled from the
    responsibility mixins in sync_*.py. See each mixin's module docstring
    for what it owns; this class adds nothing of its own beyond composing
    them into the single object `apply`/`status`/`doctor`/`remove` share."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["apply", "status", "doctor", "remove"])
    parser.add_argument(
        "--no-apm", action="store_true", help="skip apm install/uninstall"
    )
    parser.add_argument(
        "--recover-skills-backup",
        action="store_true",
        help=(
            "restore a .bak left by an interrupted apply (last-known-good "
            "wins), then exit -- does not run apm install/compile"
        ),
    )
    args = parser.parse_args()

    syncer = Sync(repo_root=Path(__file__).resolve().parents[1])
    if args.command == "apply" and args.recover_skills_backup:
        return syncer.recover_skills_backup()
    if args.command == "apply":
        return syncer.apply(no_apm=args.no_apm)
    if args.command == "status":
        return syncer.status()
    if args.command == "doctor":
        return syncer.doctor(env=dict(os.environ))
    return syncer.remove(no_apm=args.no_apm)


if __name__ == "__main__":
    sys.exit(main())
