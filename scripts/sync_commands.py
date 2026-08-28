"""The `apply`/`status`/`doctor`/`remove` CLI commands and their supporting
roster/drift reports (agent-dotfiles#335).

Split out of the former scripts/sync.py (2141 lines). Pure move -- no
behaviour change from the original module.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from sync_constants import (
    ABSENT,
    APM_MARKER,
    COMPILED_ROOT_FILES,
    MANAGED_ROOT_FILES,
    NEUTRAL_HARNESSES,
    SYNC_MARKER,
    UNUSED_ROOT_FILES,
)
from sync_skill_backup import SkillBackupConflict
from sync_skills import load_default_skills, load_skill_roster, neutral_union, roster_union, skill_source_aliases
from sync_util import _description_of, is_corporate_mount


class CommandsMixin:
    def apply(self, no_apm: bool = False) -> int:
        if not (self.repo / "apm.yml").is_file():
            print(f"ERROR: {self.repo} is not the agent-dotfiles repo")
            return 2
        # ensure the neutral user-scope skills path exists so APM
        # populates it even when no other harness is detected yet
        (self.home / ".agents" / "skills").mkdir(parents=True, exist_ok=True)
        if not no_apm:
            # Fail closed before any APM invocation at all (#14): a stale
            # local-package registration in the *global* ~/.apm/apm.yml is
            # exactly what let apm compile contaminated output during #11
            # -- apm itself did not fail, it silently accumulated cached
            # content from registrations whose source had moved, vanished,
            # or drifted. Checked first, ahead of even the skill backup.
            stale = self.stale_global_registrations()
            collisions = self.local_basename_collisions()
            if stale or collisions:
                print("ERROR: stale global APM registration(s), aborting apply before running apm:")
                for path, reason in stale:
                    print(f"  {path}: {reason}")
                for basename, paths in collisions.items():
                    # A collision is reported even when neither path is
                    # individually stale (#15): apm's cache and apm:source
                    # markers are keyed by basename only, so two distinct
                    # registrations sharing one are unsafe together
                    # regardless of either one's own validity.
                    print(
                        f"  basename collision '{basename}': {', '.join(paths)} "
                        f"share ~/.apm/apm_modules/_local/{basename}"
                    )
                print(
                    "Recovery is manual and reviewable -- see README.md's "
                    "'Stale Global Registrations and Recovery' section. "
                    "Never delete apm_modules/ or edit apm.yml by hand. If "
                    "any path above is part of a basename collision, "
                    "`apm uninstall -g <path>` for just that path does NOT "
                    "prove the colliding path's cache/source identity is "
                    "untouched -- evaluate and recover the whole collision "
                    "group together, then reinstall any surviving "
                    "registration before compiling again."
                )
                return 4
            # Snapshot the last-good deployed skill set before touching two
            # independently-failing remote sources (#9: public jonhill90/skills
            # + private jonhill90/skills-private). A fetch failure from either
            # must not leave a harness with a partially overwritten skill set.
            try:
                skill_backups = self.backup_skills_dirs()
            except SkillBackupConflict as exc:
                print(f"ERROR: {exc}")
                return 3
            skill_args = [
                argument
                for skill in roster_union(self.repo)
                for argument in ("--skill", skill)
            ]
            # #41: `apm install -g` has been observed to exit 0 while
            # resolving a stale, cached commit for a ref that was just
            # bumped in apm.yml -- a second, identical invocation then
            # resolves correctly. The exit code alone cannot be trusted as
            # proof the pinned commit was reached, so the just-written
            # global lockfile is checked against apm.yml's declared pins
            # after every attempt. One redrive is allowed so a single
            # `sync.py apply` still suffices for the operator; if the
            # second attempt is *also* stale, this is no longer the known
            # one-retry cache-miss pattern and apply fails closed instead
            # of reporting an unreached state as success.
            stale: dict[str, tuple[str, str]] = {}
            attempts_remaining = 2
            while attempts_remaining:
                attempts_remaining -= 1
                try:
                    result = self.runner(
                        ["apm", "install", "-g", str(self.repo), *skill_args],
                        check=False,
                    )
                except Exception as exc:
                    # A launch failure (missing binary, OS error, ...) never
                    # returns a process result at all -- restore must run on
                    # the exception path too, not only on a bad returncode
                    # (#9 review), and the failure must reach the caller as
                    # a return code, not an uncaught exception mid-deployment.
                    self.restore_skills_dirs(skill_backups)
                    print(f"ERROR: apm install raised {exc!r}; aborting apply")
                    return 1
                if result.returncode != 0:
                    self.restore_skills_dirs(skill_backups)
                    print("ERROR: apm install failed; aborting apply")
                    return result.returncode
                stale = self.stale_skill_source_pins()
                if not stale:
                    break
                if attempts_remaining:
                    print(
                        "[retry] apm install -g resolved a stale cached "
                        f"commit for {', '.join(sorted(stale))}; redriving "
                        "apm install once (#41)"
                    )
            if stale:
                self.restore_skills_dirs(skill_backups)
                for name, (declared_ref, resolved) in sorted(stale.items()):
                    print(
                        f"ERROR: {name} still resolved to {resolved[:8]} "
                        f"after retry; apm.yml pins {declared_ref[:8]} (#41)"
                    )
                print(
                    "ERROR: apm install did not reach the pinned skill "
                    "source(s) after a redrive; aborting apply"
                )
                return 5
            self.discard_skills_backup(skill_backups)
            # install does NOT reliably compile root files on fresh
            # machines (E16 failure 2026-07-13) -- compile explicitly,
            # BEFORE teardown so stale unused-harness roots are removed.
            # Marker-owned managed roots are detached first: APM has also
            # reported "unchanged" for stale output after source edits (V8).
            root_backups = self.detach_managed_root_files()
            try:
                compile_result = self.runner(["apm", "compile", "-g"], check=False)
            except Exception as exc:
                self.restore_root_files(root_backups)
                print(f"ERROR: apm compile raised {exc!r}; aborting apply")
                return 1
            if compile_result.returncode != 0:
                self.restore_root_files(root_backups)
                print("ERROR: apm compile failed; aborting apply")
                return compile_result.returncode
            # A detected harness should be regenerated. If APM skipped one,
            # preserve its last-known-good marker-owned root instead of
            # turning a refresh into accidental removal.
            self.restore_root_files(root_backups)
        self.apply_overlays()
        self.ensure_neutral_skills()
        removed = self.teardown_unused_root_files()
        hooks_ok, hooks_detail = self.install_git_hooks()
        if not hooks_ok:
            print(f"[warn] git hooks not installed: {hooks_detail}")
        pi = self.project_pi()
        self.merge_settings("claude", self.home / ".claude" / "settings.json")
        self.merge_settings("pi", self.home / ".pi" / "agent" / "settings.json")
        if (self.home / ".copilot").is_dir():
            self.merge_settings(
                "copilot", self.home / ".copilot" / "settings.json"
            )
        self.merge_mcp()
        self.merge_codex_skills()
        self.merge_codex_mcp()
        self.merge_copilot_mcp()
        self.state["repo"] = str(self.repo)
        self.save_state()
        print(f"[ok] apply complete (teardown: {len(removed)}, pi: {bool(pi)})")
        return 0

    def status(self) -> int:
        issues = 0
        shared, sections = load_skill_roster(self.repo)
        for harness, names in sorted(self.roster_report().items()):
            scoped = len(names) - len(shared)
            suffix = f" ({len(shared)} shared + {scoped} scoped)" if sections else ""
            print(f"[roster] {harness}: {len(names)} skill(s){suffix}")
        for source in self.pinned_skill_sources():
            short_sha = source["resolved_commit"][:8]
            print(f"[source] {source['name']}: {source['repo_url']}@{short_sha}")
        for name, (declared_ref, resolved) in sorted(
            self.stale_skill_source_pins().items()
        ):
            # #41: apply() already retries once and fails closed rather
            # than report this, but a lockfile can also go stale between
            # applies (e.g. an operator bumps apm.yml and runs `status`
            # before the next `apply`) -- surface that here too, so
            # `status`/`doctor` do not silently agree with a stale `apply`.
            print(
                f"[stale-pin] {name}: resolved {resolved[:8]}, "
                f"apm.yml pins {declared_ref[:8]}"
            )
            issues += 1
        for path, reason in self.stale_global_registrations():
            print(f"[stale-global] {path}: {reason}")
            issues += 1
        for basename, paths in self.local_basename_collisions().items():
            print(
                f"[basename-collision] {basename}: "
                f"{', '.join(paths)} share ~/.apm/apm_modules/_local/{basename}"
            )
            issues += 1
        drift = self.neutral_drift()
        if drift:
            print(f"[drift] ~/.agents/skills: unwanted {', '.join(drift)}")
            issues += 1
        substituted = self.neutral_identity()
        if substituted:
            print(
                "[substituted] ~/.agents/skills: not our copy -- "
                f"{', '.join(substituted)}"
            )
            issues += 1
        for relative in MANAGED_ROOT_FILES:
            path = self.home / relative
            if not path.parent.is_dir():
                print(f"[skip] {path} (harness not installed)")
                continue
            if not path.is_file():
                print(f"[missing] {path}")
                issues += 1
            elif APM_MARKER not in path.read_text(encoding="utf-8"):
                print(f"[unmanaged] {path} (no APM marker)")
                issues += 1
            else:
                print(f"[ok] {path}")
        for path in self.instructions_drift():
            print(f"[drift] {path}: deployed content does not match the repo")
            issues += 1
        for relative in COMPILED_ROOT_FILES:
            path = self.home / relative
            for finding in self.compiled_root_source_findings(path):
                print(f"[source-blocks] {path}: {finding}")
                issues += 1
        for relative in UNUSED_ROOT_FILES:
            path = self.home / relative
            if path.is_file() and APM_MARKER in path.read_text(encoding="utf-8"):
                print(f"[stale] {path} (marker-owned, unused harness)")
                issues += 1
        pi = self.state.get("pi_agents_md")
        if pi:
            print(f"[ok] {pi}" if Path(pi).is_file() else f"[missing] {pi}")
        declared = self.declared_mcp_servers()
        if declared:
            surfaces: list[tuple[str, set[str]]] = []
            claude_json = self.home / ".claude.json"
            if claude_json.is_file():
                names = set(
                    json.loads(claude_json.read_text(encoding="utf-8")).get(
                        "mcpServers", {}
                    )
                )
                surfaces.append(("claude", names))
            codex_toml = self.home / ".codex" / "config.toml"
            if codex_toml.parent.is_dir():
                text = (
                    codex_toml.read_text(encoding="utf-8")
                    if codex_toml.is_file()
                    else ""
                )
                names = {
                    n for n in declared if f"[mcp_servers.{n}]" in text
                }
                surfaces.append(("codex", names))
            copilot_json = self.home / ".copilot" / "mcp-config.json"
            if (self.home / ".copilot").is_dir():
                names = set()
                if copilot_json.is_file():
                    names = set(
                        json.loads(
                            copilot_json.read_text(encoding="utf-8")
                        ).get("mcpServers", {})
                    )
                surfaces.append(("copilot", names))
            for surface, present in surfaces:
                for name in sorted(declared):
                    if name in present:
                        print(f"[ok] mcp:{surface}:{name}")
                    else:
                        print(f"[missing] mcp:{surface}:{name} (declared, not projected)")
                        issues += 1
        print(f"{issues} issue(s)")
        return 1 if issues else 0

    def roster_report(self) -> dict[str, list[str]]:
        """Each harness's resolved roster (SPEC §4.1)."""
        return {
            harness: load_default_skills(self.repo, harness)
            for harness in ("claude", *NEUTRAL_HARNESSES)
        }

    def neutral_drift(self) -> list[str]:
        """Wrapper-managed links on the shared path that no roster wants.

        Auto-removed by the next apply.
        """
        wanted = set(neutral_union(self.repo))
        return sorted(set(self.state.get("neutral_skills", [])) - wanted)

    def neutral_identity(self) -> list[str]:
        """Roster skills on the shared path whose deployed copy is not ours.

        `neutral_untracked` skips any name the roster wants, so a foreign
        skill installed under a managed name is invisible to it -- and the
        wrapper owns nothing on that path (`ensure_neutral_skills` only links
        when the target is absent), so nothing else notices either. Three
        harnesses would load a third party's procedure, and its scripts,
        under a trusted name with every check green (#93).

        The true source used to be `self.repo / "skills" / <name>`, but #9
        removed `skills/` from this repository entirely -- that comparison
        was `source.is_file() == False` unconditionally, so this returned
        `[]` no matter what was deployed (#35). Skill content now arrives
        through the pinned APM dependencies declared in this repo's own
        apm.yml (`dependencies.apm`, each carrying a `skills:` key and an
        `alias:`); `apm install -g` resolves each into
        `~/.apm/apm_modules/<alias>/skills/<name>/SKILL.md`, and that copy
        is what the deployed `~/.agents/skills/<name>` was made from --
        confirmed by diffing a live deployment against its cache entry.
        That is the source of truth used here: unlike the pinned upstream
        repos themselves, it needs no network at check time; unlike a hash
        recorded at apply time, it needs no change to apply() (deployment-
        critical code this fix does not touch).

        Fails closed, not open, on the new path: a rostered name that *is*
        deployed but whose source cannot be found under any declared alias
        is reported as mismatched, same as a description mismatch would
        be -- the whole point of #35 is that "cannot verify" must not
        collapse to "assumed fine". A name with nothing deployed yet is
        not an error -- that is `neutral_drift`'s and `apply()`'s job, not
        this one's, and every machine that has never run `apply` would
        otherwise show permanently red for skills it does not even have.

        Compared on the description, not the whole file: APM rewrites
        relative links in the body on install, so byte-comparison reports a
        false mismatch on a legitimately deployed skill.
        """
        aliases = skill_source_aliases(self.repo)
        cache_root = self.home / ".apm" / "apm_modules"
        mismatched: list[str] = []
        for name in neutral_union(self.repo):
            deployed = self.home / ".agents" / "skills" / name / "SKILL.md"
            if not deployed.is_file():
                continue
            source = next(
                (
                    candidate
                    for alias in aliases
                    if (candidate := cache_root / alias / "skills" / name / "SKILL.md").is_file()
                ),
                None,
            )
            if source is None:
                mismatched.append(
                    f"{name} (source unlocatable under {cache_root}"
                    f"/{{{', '.join(aliases) or 'no pinned skill sources in apm.yml'}}})"
                )
                continue
            if _description_of(deployed) != _description_of(source):
                mismatched.append(name)
        return mismatched

    def neutral_untracked(self) -> list[str]:
        """Out-of-union links on the shared path this wrapper did not create.

        Machines synced before §4.1 carry links from the old wholesale
        mirroring, which are untracked and therefore never auto-removed. A
        harness-scoped skill would stay readable on the shared path with no
        signal, so report them for manual removal rather than deleting
        something the wrapper does not own.
        """
        neutral = self.home / ".agents" / "skills"
        if not neutral.is_dir():
            return []
        wanted = set(neutral_union(self.repo))
        managed = set(self.state.get("neutral_skills", []))
        return sorted(
            entry.name
            for entry in neutral.iterdir()
            if entry.name not in wanted and entry.name not in managed
        )

    def doctor_checks(self, env: dict) -> list[tuple[str, tuple[bool | None, str]]]:
        checks: list[tuple[str, tuple[bool | None, str]]] = []
        drift = self.neutral_drift()
        substituted = self.neutral_identity()
        untracked = self.neutral_untracked()
        if drift or untracked or substituted:
            parts = []
            if drift:
                parts.append(f"managed, removed on next apply: {', '.join(drift)}")
            if untracked:
                parts.append(
                    f"untracked (pre-§4.1 mirror), remove manually: "
                    f"{', '.join(untracked)}"
                )
            if substituted:
                # The one that fails silently: the name is wanted, so drift
                # and untracked both skip it, and three harnesses load a copy
                # this repository did not author (#93).
                parts.append(
                    f"not our copy, deployed under a managed name: "
                    f"{', '.join(substituted)}"
                )
            message = "~/.agents/skills — " + "; ".join(parts)
        else:
            message = "~/.agents/skills matches the neutral roster"
        checks.append(
            (
                "neutral-roster-drift",
                (not (drift or untracked or substituted), message),
            )
        )
        instructions_drift = self.instructions_drift()
        checks.append(
            (
                "instructions-drift",
                (
                    not instructions_drift,
                    "deployed instructions/overlays match the repo"
                    if not instructions_drift
                    else "deployed content does not match the repo, run "
                    "`sync.py apply` to refresh: "
                    + ", ".join(instructions_drift),
                ),
            )
        )
        checks.append(
            ("apm-cli", (shutil.which("apm") is not None, "apm on PATH"))
        )
        hook_target = self.git_hooks_dir() / "commit-msg"
        hook_source = self.repo / "hooks" / "no-coauthor-trailer"
        hooks_path = self.configured_hooks_path()
        if hooks_path != str(self.git_hooks_dir()):
            checks.append(
                (
                    "no-coauthor-trailer-hook",
                    (
                        False,
                        "core.hooksPath is "
                        f"{hooks_path or '(unset)'}, expected "
                        f"{self.git_hooks_dir()} — run `sync.py apply`",
                    ),
                )
            )
        elif not hook_target.is_file() or (
            hook_source.is_file()
            and hook_target.read_bytes() != hook_source.read_bytes()
        ):
            checks.append(
                (
                    "no-coauthor-trailer-hook",
                    (
                        False,
                        f"{hook_target} missing or stale — run `sync.py apply`",
                    ),
                )
            )
        else:
            checks.append(
                ("no-coauthor-trailer-hook", (True, str(hook_target)))
            )
        stale_backups = [
            self.home / relative.with_name(relative.name + ".bak")
            for relative in self.SKILL_DIRS
            if (self.home / relative.with_name(relative.name + ".bak")).exists()
        ]
        checks.append(
            (
                "skill-backup-conflict",
                (
                    not stale_backups,
                    "no unresolved skill backup"
                    if not stale_backups
                    else "unresolved skill backup(s), apply() will refuse to "
                    "run until recovered: "
                    + ", ".join(str(p) for p in stale_backups)
                    + " — see `apply --recover-skills-backup`",
                ),
            )
        )
        stale_global = self.stale_global_registrations()
        checks.append(
            (
                "stale-global-registrations",
                (
                    not stale_global,
                    "no stale global APM registrations"
                    if not stale_global
                    else "apply() will refuse to run until recovered — "
                    + "; ".join(f"{path}: {reason}" for path, reason in stale_global),
                ),
            )
        )
        collisions = self.local_basename_collisions()
        checks.append(
            (
                "local-registration-basename-collisions",
                (
                    not collisions,
                    "no basename collisions among local registrations"
                    if not collisions
                    else "apm's cache and apm:source markers are keyed by "
                    "basename only, so these share identity — evaluate the "
                    "whole group before removing any of it: "
                    + "; ".join(
                        f"{basename}: {', '.join(paths)}"
                        for basename, paths in collisions.items()
                    ),
                ),
            )
        )
        source_block_findings: list[str] = []
        for relative in COMPILED_ROOT_FILES:
            path = self.home / relative
            for finding in self.compiled_root_source_findings(path):
                source_block_findings.append(f"{path}: {finding}")
        checks.append(
            (
                "compiled-root-sources",
                (
                    not source_block_findings,
                    "no duplicate or foreign apm:source blocks"
                    if not source_block_findings
                    else "; ".join(source_block_findings),
                ),
            )
        )
        checks.append(
            (
                "cowork-pin",
                (
                    bool(env.get("APM_COPILOT_COWORK_SKILLS_DIR")) or None,
                    "APM_COPILOT_COWORK_SKILLS_DIR (needed with multiple OneDrive mounts)",
                ),
            )
        )
        vault = env.get("AGENT_MEMORY_VAULT")
        if not vault:
            checks.append(
                ("memory-vault-personal", (None, "AGENT_MEMORY_VAULT not set (M4)"))
            )
        elif is_corporate_mount(vault):
            checks.append(
                (
                    "memory-vault-personal",
                    (False, f"memory vault on a corporate mount: {vault}"),
                )
            )
        elif not Path(vault).is_dir():
            checks.append(
                (
                    "memory-vault-personal",
                    (False, f"memory vault path does not exist: {vault}"),
                )
            )
        else:
            checks.append(("memory-vault-personal", (True, vault)))
        sources = self.pinned_skill_sources()
        if not sources:
            checks.append(
                (
                    "skill-sources",
                    (None, "no pinned skill sources (apm.lock.yaml absent or empty)"),
                )
            )
        else:
            for source in sources:
                short_sha = source["resolved_commit"][:8]
                checks.append(
                    (
                        f"skill-source-{source['name']}",
                        (True, f"{source['repo_url']}@{short_sha}"),
                    )
                )
        fragment_file = self.mcp_fragment_file()
        if fragment_file.is_file():
            text = fragment_file.read_text(encoding="utf-8")
            for var in sorted(set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", text))):
                if env.get(var):
                    checks.append((f"mcp-env-{var}", (True, f"{var} set")))
                else:
                    checks.append(
                        (
                            f"mcp-env-{var}",
                            (
                                None,
                                f"{var} referenced by settings/mcp/servers.json"
                                " but not set",
                            ),
                        )
                    )
        for harness, root in (
            ("claude", Path(".claude/CLAUDE.md")),
            ("codex", Path(".codex/AGENTS.md")),
            ("copilot", Path(".copilot/AGENTS.md")),
        ):
            root_file = self.home / root
            if not root_file.parent.is_dir():
                checks.append(
                    (f"{harness}-root-file", (None, f"{harness} not installed"))
                )
            else:
                checks.append(
                    (
                        f"{harness}-root-file",
                        (
                            root_file.is_file()
                            and APM_MARKER
                            in root_file.read_text(encoding="utf-8"),
                            str(root_file),
                        ),
                    )
                )
        return checks

    def doctor(self, env: dict) -> int:
        failed = 0
        for name, (ok, detail) in self.doctor_checks(env=env):
            if ok is True:
                print(f"[pass] {name}: {detail}")
            elif ok is None:
                print(f"[warn] {name}: {detail}")
            else:
                print(f"[FAIL] {name}: {detail}")
                failed += 1
        return 1 if failed else 0

    def remove(self, no_apm: bool = False) -> int:
        pi = self.state.get("pi_agents_md")
        if pi and Path(pi).is_file():
            text = Path(pi).read_text(encoding="utf-8")
            if SYNC_MARKER in text:
                Path(pi).unlink()
        self.state["pi_agents_md"] = None

        for live_path_str, previous in self.state.get("settings", {}).items():
            live_path = Path(live_path_str)
            if not live_path.is_file():
                continue
            live = json.loads(live_path.read_text(encoding="utf-8"))
            for key, value in previous.items():
                if value == ABSENT:
                    live.pop(key, None)
                else:
                    live[key] = value
            live_path.write_text(
                json.dumps(live, indent=2) + "\n", encoding="utf-8"
            )
        self.state["settings"] = {}

        for live_path_str, previous in self.state.get("mcp", {}).items():
            live_path = Path(live_path_str)
            if not live_path.is_file():
                continue
            live = json.loads(live_path.read_text(encoding="utf-8"))
            servers = live.get("mcpServers", {})
            for name, value in previous.items():
                if value == ABSENT:
                    servers.pop(name, None)
                else:
                    servers[name] = value
            live["mcpServers"] = servers
            live_path.write_text(
                json.dumps(live, indent=2) + "\n", encoding="utf-8"
            )
        self.state["mcp"] = {}

        codex_config = self.state.get("codex_mcp")
        if codex_config and Path(codex_config).is_file():
            path = Path(codex_config)
            path.write_text(
                self._strip_codex_block(path.read_text(encoding="utf-8")),
                encoding="utf-8",
            )
        self.state["codex_mcp"] = None

        for overlay_root in self.state.get("overlays") or []:
            path = Path(overlay_root)
            if path.is_file():
                path.write_text(
                    self._strip_overlay_block(path.read_text(encoding="utf-8")),
                    encoding="utf-8",
                )
        self.state["overlays"] = []

        codex_skills = self.state.get("codex_skills")
        if codex_skills and Path(codex_skills).is_file():
            path = Path(codex_skills)
            path.write_text(
                self._strip_codex_skills_block(path.read_text(encoding="utf-8")),
                encoding="utf-8",
            )
        self.state["codex_skills"] = None

        if not no_apm and self.state.get("repo"):
            self.runner(
                ["apm", "uninstall", "-g", self.state["repo"]], check=False
            )
        self.save_state()
        print("[ok] remove complete")
        return 0
