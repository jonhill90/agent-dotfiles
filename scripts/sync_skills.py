"""Skill-roster resolution (agent-dotfiles#335).

Split out of the former scripts/sync.py (2141 lines): everything that reads
`settings/default-skills.txt` and this repo's own `apm.yml` to resolve, per
harness, which skills are wanted. Pure move -- no behaviour change from the
original module.
"""

from __future__ import annotations

import re
from pathlib import Path

from sync_constants import NEUTRAL_HARNESSES

# Per-entry roster modifiers. `name-only` is Claude Code's third
# `skillOverrides` state (SPEC §4.1, #96): the skill stays installed and
# invocable, but its description is not charged until it fires. A modifier
# qualifies membership; it never removes it.
SKILL_MODIFIERS = frozenset({"name-only"})

# Reserved section name (agent-dotfiles#181): a skill that is authored but
# deliberately withheld from every harness's roster, with a stated reason.
# Not a harness -- `roster_union`/`neutral_union` must never fold it into an
# install set, which is why it is parsed into its own structure below rather
# than into `sections`.
BENCH_SECTION = "benched"


def _split_modifier(entry: str) -> tuple[str, str | None]:
    """`obsidian @name-only` -> ("obsidian", "name-only")."""
    name, _, rest = entry.partition("@")
    name = name.strip()
    modifier = rest.strip() or None
    if modifier is not None and modifier not in SKILL_MODIFIERS:
        raise ValueError(
            f"unknown roster modifier @{modifier} on {name!r}; "
            f"known: {', '.join(sorted(SKILL_MODIFIERS))}"
        )
    return name, modifier


def load_skill_roster(repo: Path) -> tuple[list[str], dict[str, list[str]]]:
    """Parse `settings/default-skills.txt` into (shared, per-harness sections).

    Lines before any `[harness]` header are shared by every harness, so a
    flat file keeps its original meaning (SPEC §4.1). A trailing
    `@<modifier>` qualifies the entry and is stripped here, so every caller
    that only wants membership keeps working unchanged; `skill_modifiers()`
    reads the annotations.
    """
    shared, sections, _, _ = _parse_skill_roster(repo)
    return shared, sections


def skill_modifiers(repo: Path) -> dict[str, str]:
    """Roster entries carrying a modifier, as `{skill: modifier}`."""
    return _parse_skill_roster(repo)[2]


def benched_skills(repo: Path) -> dict[str, str]:
    """Skills authored but deliberately withheld, as `{skill: reason}`.

    Read from the `[benched]` section of `default-skills.txt`. A skill
    present here is a stated decision, not an absence -- agent-dotfiles#181
    found eleven authored, unrostered skills with no record of which of
    those two shapes applied. `reason` may be empty for an entry with no
    trailing `# ...` comment; `validate_skill_bench` is what rejects that,
    not the parser.
    """
    return _parse_skill_roster(repo)[3]


def _parse_skill_roster(
    repo: Path,
) -> tuple[list[str], dict[str, list[str]], dict[str, str], dict[str, str]]:
    roster = repo / "settings" / "default-skills.txt"
    shared: list[str] = []
    sections: dict[str, list[str]] = {}
    modifiers: dict[str, str] = {}
    benched: dict[str, str] = {}
    current: list[str] | None = None
    in_bench = False
    for raw in roster.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            header = line[1:-1].strip().lower()
            if header == BENCH_SECTION:
                in_bench = True
                current = None
            else:
                in_bench = False
                current = sections.setdefault(header, [])
            continue
        if in_bench:
            name, _, reason = line.partition("#")
            benched[name.strip()] = reason.strip()
            continue
        name, modifier = _split_modifier(line)
        if modifier is not None:
            modifiers[name] = modifier
        (shared if current is None else current).append(name)
    return shared, sections, modifiers, benched


def load_default_skills(repo: Path, harness: str | None = None) -> list[str]:
    """Resolved roster: shared alone, or shared + that harness's section."""
    shared, sections = load_skill_roster(repo)
    if harness is None:
        return shared
    return shared + sections.get(harness.lower(), [])


def roster_union(repo: Path) -> list[str]:
    """Every skill any harness asks for -- what APM installs (SPEC §4.1)."""
    shared, sections = load_skill_roster(repo)
    names = set(shared)
    for values in sections.values():
        names.update(values)
    return sorted(names)


def neutral_union(repo: Path) -> list[str]:
    """What the shared `~/.agents/skills` path may contain: the neutral
    trio's rosters only, so Claude-scoped skills never leak into it."""
    shared, sections = load_skill_roster(repo)
    names = set(shared)
    for harness in NEUTRAL_HARNESSES:
        names.update(sections.get(harness, []))
    return sorted(names)


def claude_skill_overrides(repo: Path) -> dict[str, str]:
    """`skillOverrides` entries that enforce Claude Code's resolved roster.

    APM installs the union into `~/.claude/skills` and keeps ownership of it
    (SPEC §4.1), so a skill scoped away from Claude Code still reaches the
    model's list. V9 resolved the Tier B lever -- `skillOverrides` with a value
    of `off` -- and this derives it from the roster so the declaration and the
    enforcement cannot drift.

    Two states come out of the roster. A skill Claude Code is not scoped to
    is `off`. A skill it keeps but which carries `@name-only` is
    `name-only`: listed without its description, so it costs a name instead
    of a description and stays invocable (SPEC §4.1, #96).
    """
    claude = set(load_default_skills(repo, "claude"))
    overrides = {name: "off" for name in roster_union(repo) if name not in claude}
    for name, modifier in skill_modifiers(repo).items():
        if modifier == "name-only" and name in claude:
            overrides[name] = "name-only"
    return overrides


def copilot_disabled_skills(repo: Path) -> list[str]:
    """`disabledSkills` entries that enforce Copilot's resolved roster.

    Copilot discovers personal skills from `~/.agents/skills` -- the directory
    the neutral harnesses share -- so a skill scoped to Codex and Pi reaches
    Copilot as well, and Tier A cannot separate them. V10 resolved
    affirmatively on 2026-07-27: `disabledSkills` in `~/.copilot/settings.json`,
    which the wrapper already manages, and a fresh Copilot process stops
    listing the skill. Derived from the roster so the declaration and the
    enforcement cannot drift.
    """
    copilot = set(load_default_skills(repo, "copilot"))
    return [name for name in roster_union(repo) if name not in copilot]


def codex_disabled_skills(repo: Path) -> list[str]:
    """Skill names Codex's resolved roster excludes.

    Codex reads the shared `~/.agents/skills` tree, so Tier A cannot separate
    it from Copilot and Pi. Its Tier B lever is `[[skills.config]]` with
    `enabled = false`. Personal skills are keyed by bare name; plugin skills
    are namespaced (`github:yeet`), which is why the managed block is written
    between markers and the user's own entries are left alone.
    """
    codex = set(load_default_skills(repo, "codex"))
    return [name for name in roster_union(repo) if name not in codex]


def pi_disabled_skills(repo: Path) -> list[str]:
    """Denylist entries enforcing Pi's resolved roster.

    Pi's `skills` key takes paths, and a leading `-` removes one.
    """
    pi = set(load_default_skills(repo, "pi"))
    return [
        f"-skills/{name}/SKILL.md"
        for name in roster_union(repo)
        if name not in pi
    ]


def apm_dependency_block(text: str) -> str:
    """Every line belonging to an apm.yml's `dependencies: apm:` list,
    comments and all, up to the next line dedented to two spaces or less
    (a sibling key like `mcp:`, or end of the mapping). Indentation-based,
    not a fixed line-shape regex -- the caller may still contain
    full-line comments, which this does not strip. Shared between
    validate_repository.py (project-level apm.yml, skill-source pins,
    #9) and this module (the global ~/.apm/apm.yml, local-package
    registrations, #14) so the two never drift on what counts as the
    dependencies.apm block.
    """
    match = re.search(r"^dependencies:\n(?:.*\n)*?  apm:\n", text, re.M)
    if not match:
        return ""
    lines: list[str] = []
    for line in text[match.end():].splitlines():
        if line.strip() and (len(line) - len(line.lstrip(" "))) <= 2:
            break  # dedented to a sibling key or back to top level
        lines.append(line)
    return "\n".join(lines) + "\n"


def skill_source_aliases(repo: Path) -> list[str]:
    """Every `alias:` declared by a skill-bundle dependency (one that
    carries a `skills:` key) in this repo's own apm.yml (#9's pinned
    dependency shape) -- the same entries validate_repository.py's
    parse_skill_source_dependencies() parses, re-read here rather than
    imported: that module imports from this one (apm_dependency_block),
    so the reverse import would cycle.

    Empty apm.yml, no `dependencies.apm` block, or no skill-bundle entry
    all return [] -- callers must treat that as "no local cache location
    is known", not as "nothing to verify".
    """
    apm_yml = repo / "apm.yml"
    if not apm_yml.is_file():
        return []
    block = apm_dependency_block(apm_yml.read_text(encoding="utf-8"))
    block = "\n".join(
        line for line in block.splitlines() if not line.strip().startswith("#")
    )
    aliases: list[str] = []
    for entry in re.split(r"(?=^    - )", block, flags=re.M):
        if not entry.strip() or not re.search(r"^\s*skills:", entry, re.M):
            continue
        match = re.search(r"^\s*alias:\s*(.+?)\s*$", entry, re.M)
        if match:
            aliases.append(match.group(1).strip("'\""))
    return aliases


def declared_skill_source_pins(repo: Path) -> dict[str, str]:
    """alias -> pinned `ref:` for every skill-bundle dependency in this
    repo's apm.yml (#41).

    `apply()` uses this as the ground truth to verify `apm install -g`
    actually reached the pinned commit, rather than trusting its exit
    code alone: #41 reproduced `apm install -g` exiting 0 while
    resolving a stale, cached commit for a ref that had just been
    bumped, so the exit code cannot be treated as proof the pin was
    applied.
    """
    apm_yml = repo / "apm.yml"
    if not apm_yml.is_file():
        return {}
    block = apm_dependency_block(apm_yml.read_text(encoding="utf-8"))
    block = "\n".join(
        line for line in block.splitlines() if not line.strip().startswith("#")
    )
    pins: dict[str, str] = {}
    for entry in re.split(r"(?=^    - )", block, flags=re.M):
        if not entry.strip() or not re.search(r"^\s*skills:", entry, re.M):
            continue
        alias_match = re.search(r"^\s*alias:\s*(.+?)\s*$", entry, re.M)
        ref_match = re.search(r"^\s*ref:\s*(.+?)\s*$", entry, re.M)
        if alias_match and ref_match:
            pins[alias_match.group(1).strip("'\"")] = ref_match.group(1).strip("'\"")
    return pins
