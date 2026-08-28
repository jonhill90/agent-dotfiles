"""Skill-source atomicity: backup/restore around `apm install -g`, and the
staleness/collision checks `apply()` fails closed on before running it
(agent-dotfiles#335).

Split out of the former scripts/sync.py (2141 lines). Pure move -- no
behaviour change from the original module.

`apm install -g` fetches from two remote, independently-failing sources
(public jonhill90/skills, private jonhill90/skills-private). A failure
partway through must not leave a harness with a partially overwritten
skill set -- see docs/evals.md-adjacent lesson from scripts/eval_arm.py:
rename aside, never delete, restore on failure. Deployed skill content
lives under two paths: ~/.claude/skills (APM's real files) and
~/.agents/skills (native for Pi/Codex/Copilot, either APM's own files or
ensure_neutral_skills()'s symlinks into the former).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from sync_manifest import basename_collisions, parse_global_local_packages, stale_global_registration
from sync_skills import declared_skill_source_pins


class SkillBackupConflict(RuntimeError):
    """Raised by Sync.backup_skills_dirs() when a `.bak` from an
    interrupted prior apply() already exists (#9). Never resolved
    automatically -- see the exception message for recovery steps."""


class SkillBackupMixin:
    SKILL_DIRS = (Path(".claude/skills"), Path(".agents/skills"))

    def backup_skills_dirs(self) -> dict[Path, Path]:
        """Rename each existing skill dir aside; empty dict if none exist.

        Renaming (not copying) is what makes the immediately-following
        `apm install` see a clean, empty target -- the same reason a
        partial write from a prior failed attempt can never masquerade as
        last-known-good.

        An existing `.bak` is never overwritten or deleted here: it can
        only exist because a previous `apply()` was interrupted before it
        restored or discarded it, which makes it the only surviving
        last-known-good copy. Silently clobbering it on the next `apply()`
        was the original defect this method exists to prevent (#9 review)
        -- so a collision fails the whole call closed, undoing any rename
        this same call already made, rather than proceeding on a guess
        about which directory is authoritative.
        """
        backups: dict[Path, Path] = {}
        conflicts: list[Path] = []
        for relative in self.SKILL_DIRS:
            live = self.home / relative
            backup = live.with_name(live.name + ".bak")
            if backup.exists():
                conflicts.append(backup)
                continue
            if not live.is_dir():
                continue
            live.rename(backup)
            backups[live] = backup
        if conflicts:
            # Undo any rename this call just made so a partial backup set
            # from this attempt cannot itself become tomorrow's conflict.
            self.restore_skills_dirs(backups)
            names = ", ".join(str(path) for path in conflicts)
            raise SkillBackupConflict(
                f"unresolved skill backup(s) found, not touched: {names}. "
                "A previous `apply()` was interrupted before it could "
                "restore or discard this backup, so it may be the only "
                "last-known-good copy of a harness's skills. Inspect it by "
                "hand, then either run "
                "`python3 scripts/sync.py apply --recover-skills-backup` "
                "to restore it (last-known-good wins), or delete it "
                "yourself once you have confirmed the current live "
                "directory is correct."
            )
        return backups

    @staticmethod
    def restore_skills_dirs(backups: dict[Path, Path]) -> None:
        """Put every backed-up skill dir back, discarding whatever a failed
        install left in its place. Never partial: each pair is independent,
        so one harness's dir cannot block another's restore."""
        for live, backup in backups.items():
            if not backup.exists():
                continue
            if live.exists():
                shutil.rmtree(live)
            backup.rename(live)

    @staticmethod
    def discard_skills_backup(backups: dict[Path, Path]) -> None:
        """Drop backups once the install they guarded against has succeeded."""
        for backup in backups.values():
            if backup.exists():
                shutil.rmtree(backup)

    def recover_skills_backup(self) -> int:
        """Explicit, human-invoked recovery for a `.bak` left by an
        interrupted `apply()` (#9). Restores each one over its live
        directory -- last-known-good wins -- and reports what it did. Never
        run automatically; `apply()` fails closed instead and points here."""
        found = False
        for relative in self.SKILL_DIRS:
            live = self.home / relative
            backup = live.with_name(live.name + ".bak")
            if not backup.exists():
                continue
            found = True
            if live.exists():
                shutil.rmtree(live)
            backup.rename(live)
            print(f"[recovered] {live} <- {backup}")
        if not found:
            print("[ok] no unresolved skill backups found")
        return 0

    def pinned_skill_sources(self) -> list[dict[str, str]]:
        """Pinned remote skill sources from the global lockfile (#9), for
        status/doctor reporting. Excludes the local agent-dotfiles entry
        (no `resolved_commit` -- it has no remote ref to pin).

        Parsed with a small line-based reader rather than PyYAML: this
        module is stdlib-only by design, and apm.lock.yaml's dependency
        blocks are a flat, regular `- key: value` shape.
        """
        lockfile = self.home / ".apm" / "apm.lock.yaml"
        if not lockfile.is_file():
            return []
        sources: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for line in lockfile.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^- (\w+): (.*)$", line)
            if match:
                if current.get("resolved_commit"):
                    sources.append(
                        {
                            "name": current.get("name", ""),
                            "repo_url": current.get("repo_url", ""),
                            "resolved_commit": current["resolved_commit"],
                        }
                    )
                current = {match.group(1): match.group(2).strip("'\"")}
                continue
            match = re.match(r"^  (\w+): (.*)$", line)
            if match and current:
                current[match.group(1)] = match.group(2).strip("'\"")
        if current.get("resolved_commit"):
            sources.append(
                {
                    "name": current.get("name", ""),
                    "repo_url": current.get("repo_url", ""),
                    "resolved_commit": current["resolved_commit"],
                }
            )
        return sources

    def stale_skill_source_pins(self) -> dict[str, tuple[str, str]]:
        """alias -> (declared_ref, resolved_commit) for every skill source
        whose commit in the just-written global lockfile does not match
        this repo's apm.yml pin (#41).

        `apm install -g` can exit 0 while resolving a stale cached commit
        for a ref that was just bumped -- the lockfile it writes is the
        only place that discrepancy is visible, since apm's own exit code
        reports success either way. Empty when apm.yml declares no pins
        (nothing to check) or when every resolved commit matches.
        """
        declared = declared_skill_source_pins(self.repo)
        if not declared:
            return {}
        stale: dict[str, tuple[str, str]] = {}
        for source in self.pinned_skill_sources():
            name = source["name"]
            if name in declared and source["resolved_commit"] != declared[name]:
                stale[name] = (declared[name], source["resolved_commit"])
        return stale

    def stale_global_registrations(self) -> list[tuple[str, str]]:
        """Every stale local-package registration in the *global*
        ~/.apm/apm.yml (#14) -- distinct from #9's per-project skill-source
        pins. Empty if the global manifest does not exist yet (nothing has
        ever been installed) or every registration is fine.
        """
        manifest = self.home / ".apm" / "apm.yml"
        if not manifest.is_file():
            return []
        text = manifest.read_text(encoding="utf-8")
        findings: list[tuple[str, str]] = []
        for entry in parse_global_local_packages(text):
            reason = stale_global_registration(entry)
            if reason:
                findings.append((str(entry.get("path", "")), reason))
        return findings

    def local_basename_collisions(self) -> dict[str, list[str]]:
        """Every basename collision among the global manifest's local
        registrations (#15) -- see basename_collisions()'s docstring for
        why this is checked independently of stale_global_registrations().
        """
        manifest = self.home / ".apm" / "apm.yml"
        if not manifest.is_file():
            return {}
        text = manifest.read_text(encoding="utf-8")
        return basename_collisions(parse_global_local_packages(text))
