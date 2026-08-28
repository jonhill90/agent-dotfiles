"""Live settings.json merge/restore, ownership-aware for list-valued keys
(agent-dotfiles#335).

Split out of the former scripts/sync.py (2141 lines). Pure move -- no
behaviour change from the original module.
"""

from __future__ import annotations

import json
from pathlib import Path

from sync_constants import ABSENT
from sync_skills import claude_skill_overrides, copilot_disabled_skills, pi_disabled_skills
from sync_util import deep_merge, resolve_hook_commands


class SettingsMergeMixin:
    def merge_settings(self, fragment_name: str, live_path: Path) -> None:
        fragment_file = self.repo / "settings" / fragment_name / "settings.json"
        if not fragment_file.is_file():
            return
        fragment = json.loads(fragment_file.read_text(encoding="utf-8"))
        if fragment_name == "claude":
            # Enforce Claude Code's resolved roster. APM installs the union
            # into ~/.claude/skills, so scoping is only declared until this
            # writes it (SPEC §4.1 Tier B, unlocked by V9).
            overrides = claude_skill_overrides(self.repo)
            if overrides:
                fragment = dict(fragment)
                fragment["skillOverrides"] = deep_merge(
                    fragment.get("skillOverrides", {}), overrides
                )
            # hooks/*.sh commands in the fragment are repo-relative (checked
            # in, portable across machines and worktrees) -- rewrite them to
            # this install's absolute path before they reach the live
            # settings.json, which Claude Code invokes from an arbitrary
            # cwd (agent-dotfiles#276).
            if "hooks" in fragment:
                fragment = dict(fragment)
                fragment["hooks"] = resolve_hook_commands(fragment["hooks"], self.repo)
        if fragment_name == "pi":
            # Pi reads the shared ~/.agents/skills tree too (SPEC §4.1 Tier B,
            # verified under V9). Entries are paths, not names.
            denied = pi_disabled_skills(self.repo)
            if denied:
                fragment = dict(fragment)
                fragment["skills"] = sorted(
                    set(fragment.get("skills", [])) | set(denied)
                )
        if fragment_name == "copilot":
            # Same drift, different directory: Copilot reads the shared
            # ~/.agents/skills tree (SPEC §4.1 Tier B, unlocked by V10).
            disabled = copilot_disabled_skills(self.repo)
            if disabled:
                fragment = dict(fragment)
                fragment["disabledSkills"] = sorted(
                    set(fragment.get("disabledSkills", [])) | set(disabled)
                )
        # Do not bail on an empty fragment when we still own list entries in
        # this file: withdrawing them is exactly the case where the fragment
        # has gone empty because the roster stopped excluding anything.
        if not fragment and not self.state.get("settings_lists", {}).get(
            str(live_path)
        ):
            return

        live = {}
        if live_path.is_file():
            live = json.loads(live_path.read_text(encoding="utf-8"))

        previous = self.state["settings"].setdefault(str(live_path), {})
        for key in fragment:
            if key not in previous:
                previous[key] = live.get(key, ABSENT)

        # List-valued keys need ownership, not replacement and not union.
        # deep_merge replaces lists wholesale, which deletes entries a harness
        # UI or another package wrote. A plain union fixes that and creates
        # the opposite bug: an entry this wrapper wrote earlier can never be
        # withdrawn, which is how a stale `disabledSkills` survived a skill
        # leaving the roster (2026-07-29, found by hand).
        #
        # So: keep what we did not write, drop what we did write and no
        # longer want, add what we want now.
        owned = self.state.setdefault("settings_lists", {}).setdefault(
            str(live_path), {}
        )
        merged = deep_merge(live, fragment)
        # Driven by keys we have ever owned, not only keys in the fragment:
        # when the roster stops excluding anything the key disappears from
        # the fragment entirely, and a withdrawal keyed off the fragment
        # would never fire -- which is exactly how the stale entry survived.
        list_keys = {k for k, v in fragment.items() if isinstance(v, list)}
        list_keys |= set(owned)
        for key in list_keys:
            wanted = fragment.get(key, [])
            if not isinstance(wanted, list):
                continue
            foreign = [
                entry for entry in live.get(key, [])
                if entry not in owned.get(key, [])
            ]
            merged[key] = sorted(set(foreign) | set(wanted))
            owned[key] = sorted(set(wanted))

        # "hooks" is a dict of event -> list of matcher entries, so it is
        # invisible to the plain list_keys dance above (deep_merge would
        # replace each event's list wholesale, deleting a hook the user or
        # another package added by hand). Same ownership discipline as
        # above, adapted for entries that are dicts, not hashable strings
        # (agent-dotfiles#276): keep foreign matcher entries, drop what we
        # previously wrote and no longer want, add what we want now.
        if "hooks" in fragment or "hooks" in owned:
            fragment_hooks = fragment.get("hooks", {})
            live_hooks = live.get("hooks", {})
            owned_hooks = owned.setdefault("hooks", {})
            merged_hooks = dict(live_hooks)
            for event in set(fragment_hooks) | set(owned_hooks):
                wanted_entries = fragment_hooks.get(event, [])
                owned_entries = owned_hooks.get(event, [])
                foreign_entries = [
                    entry for entry in live_hooks.get(event, [])
                    if entry not in owned_entries
                ]
                merged_hooks[event] = foreign_entries + wanted_entries
                owned_hooks[event] = wanted_entries
            merged["hooks"] = merged_hooks

        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_path.write_text(
            json.dumps(merged, indent=2) + "\n",
            encoding="utf-8",
        )

    def restore_settings(self, live_path: Path) -> None:
        """Put one settings file back as it was before the wrapper touched it."""
        previous = self.state.get("settings", {}).get(str(live_path))
        if previous is None or not live_path.is_file():
            return
        live = json.loads(live_path.read_text(encoding="utf-8"))
        for key, value in previous.items():
            if value == ABSENT:
                live.pop(key, None)
            else:
                live[key] = value
        live_path.write_text(json.dumps(live, indent=2) + "\n", encoding="utf-8")
        self.state.get("settings", {}).pop(str(live_path), None)
        self.state.get("settings_lists", {}).pop(str(live_path), None)
