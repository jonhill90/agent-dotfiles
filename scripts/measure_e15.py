#!/usr/bin/env python3
"""Live static-context measurement (E15, SPEC §6).

The repository validator can only weigh what the repository contains.
Enabled Claude Code *plugin* skills are in the model's context but are not
vendored here, so a plugin can grow the static footprint without any
repo-side check noticing (found 2026-07-26). This script measures the
deployed reality on a machine: root instructions, that harness's skills
path, enabled plugin skills, and the real memory index.

Python 3 stdlib only. Read-only — it never writes to a harness.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

INSTRUCTION_TOKEN_CAP = 2_000
DESCRIPTION_TOKEN_CAP = 2_000
MEMORY_INDEX_TOKEN_RESERVE = 1_500
TOTAL_STATIC_TOKEN_CAP = 8_000

DESCRIPTION_RE = re.compile(r"^description:\s*(.+?)\s*$", re.M)

# Root instruction file and skills path per harness (SPEC §5). Only Claude
# Code loads plugin skills; the neutral trio read ~/.agents/skills.
HARNESS_LAYOUT = {
    "claude": (Path(".claude/CLAUDE.md"), Path(".claude/skills"), True),
    "codex": (Path(".codex/AGENTS.md"), Path(".agents/skills"), False),
    "copilot": (Path(".copilot/AGENTS.md"), Path(".agents/skills"), False),
    "pi": (Path(".pi/agent/AGENTS.md"), Path(".agents/skills"), False),
}


def token_estimate(byte_count: int) -> float:
    """Bytes / 4 — the same estimator the validator and the research used."""
    return byte_count / 4


def description_bytes(skill_md: Path) -> int:
    """Bytes of the description text itself.

    Plugin authors commonly quote the value; the quotes are YAML syntax and
    never reach the model, so they are not charged.
    """
    if not skill_md.is_file():
        return 0
    match = DESCRIPTION_RE.search(skill_md.read_text(encoding="utf-8", errors="replace"))
    if not match:
        return 0
    text = match.group(1).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1]
    return len(text.encode("utf-8"))


def skill_dir_bytes(skills_dir: Path) -> tuple[int, list[str]]:
    if not skills_dir.is_dir():
        return 0, []
    total = 0
    names: list[str] = []
    for entry in sorted(skills_dir.iterdir()):
        payload = description_bytes(entry / "SKILL.md")
        if payload:
            total += payload
            names.append(entry.name)
    return total, names


def enabled_plugins(settings: dict) -> set[str]:
    """Plugin names the settings fragment turns on (`name@marketplace`)."""
    declared = settings.get("enabledPlugins", {})
    return {key.split("@")[0] for key, value in declared.items() if value}


def plugin_skill_bytes(plugins_root: Path, enabled: set[str]) -> tuple[int, list[str]]:
    """Description cost of *enabled* plugins' skills and commands.

    Installed content lives under `cache/<marketplace>/<plugin>/<version>/`.
    Three traps, each found on a live machine 2026-07-26:

    * `marketplaces/` holds the catalogue of every *available* plugin, with
      the same skill files under a differently-nested path. Scanning the
      whole tree double-counts anything installed. Only `cache/` is read.
    * A plugin may ship `commands/*.md` instead of `skills/*/SKILL.md`;
      Claude Code merges commands into skills, so they cost description
      tokens too. `ralph-loop` is entirely commands.
    * A cached-but-disabled plugin costs nothing — `superpowers` sits in
      the cache while the manifest records it as rejected.
    """
    cache = plugins_root / "cache"
    if not cache.is_dir():
        return 0, []
    total = 0
    plugins: set[str] = set()

    def charge(path: Path, plugin: str) -> None:
        nonlocal total
        payload = description_bytes(path)
        if payload:
            total += payload
            plugins.add(plugin)

    for marketplace in sorted(p for p in cache.iterdir() if p.is_dir()):
        for plugin_dir in sorted(p for p in marketplace.iterdir() if p.is_dir()):
            if plugin_dir.name not in enabled:
                continue
            for skill_md in sorted(plugin_dir.rglob("skills/*/SKILL.md")):
                charge(skill_md, plugin_dir.name)
            for command_md in sorted(plugin_dir.rglob("commands/*.md")):
                charge(command_md, plugin_dir.name)
    return total, sorted(plugins)


def measure(
    home: Path, enabled: set[str] | None = None, memory_index: Path | None = None
) -> dict[str, dict]:
    if enabled is None:
        settings_path = home / ".claude" / "settings.json"
        settings = (
            json.loads(settings_path.read_text(encoding="utf-8"))
            if settings_path.is_file()
            else {}
        )
        enabled = enabled_plugins(settings)
    memory_tokens = (
        token_estimate(memory_index.stat().st_size)
        if memory_index and memory_index.is_file()
        else 0.0
    )
    plugin_bytes, plugin_names = plugin_skill_bytes(
        home / ".claude" / "plugins", enabled
    )

    report: dict[str, dict] = {}
    for harness, (root_rel, skills_rel, loads_plugins) in HARNESS_LAYOUT.items():
        root = home / root_rel
        instructions = token_estimate(root.stat().st_size) if root.is_file() else 0.0
        skill_bytes, skill_names = skill_dir_bytes(home / skills_rel)
        plugin_tokens = token_estimate(plugin_bytes) if loads_plugins else 0.0
        report[harness] = {
            "instructions": instructions,
            "skills": token_estimate(skill_bytes),
            "plugin_skills": plugin_tokens,
            "memory": memory_tokens,
            "skill_names": skill_names,
            "plugin_names": plugin_names if loads_plugins else [],
            "root_present": root.is_file(),
            "total": instructions
            + token_estimate(skill_bytes)
            + plugin_tokens
            + memory_tokens,
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure live static context (E15)")
    parser.add_argument("--home", default=str(Path.home()))
    args = parser.parse_args()
    home = Path(args.home)

    vault = os.environ.get("AGENT_MEMORY_VAULT")
    memory_index = Path(vault) / "agent" / "index.md" if vault else None
    report = measure(home, memory_index=memory_index)

    print(
        f"{'harness':9} {'instr':>7} {'skills':>7} {'plugin':>7} "
        f"{'mem':>7} {'TOTAL':>8}  cap {TOTAL_STATIC_TOKEN_CAP}"
    )
    over = 0
    for harness, row in sorted(report.items()):
        flag = "" if row["total"] <= TOTAL_STATIC_TOKEN_CAP else "  OVER"
        if flag:
            over += 1
        print(
            f"{harness:9} {row['instructions']:7.0f} {row['skills']:7.0f} "
            f"{row['plugin_skills']:7.0f} {row['memory']:7.0f} "
            f"{row['total']:8.0f}{flag}"
        )
        if not row["root_present"]:
            print(f"   ! root instruction file missing for {harness}")
        descriptions = row["skills"] + row["plugin_skills"]
        if descriptions > DESCRIPTION_TOKEN_CAP:
            print(
                f"   ! {harness}: descriptions ~{descriptions:.0f} tokens "
                f"exceed the {DESCRIPTION_TOKEN_CAP} cap"
            )
            over += 1
    plugins = report["claude"]["plugin_names"]
    print(f"\nenabled plugins charged to Claude Code: {', '.join(plugins) or 'none'}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
