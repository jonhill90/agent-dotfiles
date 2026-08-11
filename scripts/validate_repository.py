#!/usr/bin/env python3
"""Validate portable skills and repository compatibility projections."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
# One parser for the roster format, shared with the sync wrapper so the
# two cannot drift on what a section means (SPEC §4.1).
from sync import (  # noqa: E402
    NEUTRAL_HARNESSES,
    apm_dependency_block,
    load_default_skills,
    load_skill_roster,
    roster_union,
)

try:
    import yaml
except ImportError:  # fresh machines lack PyYAML; use the fallback parser
    yaml = None

YAML_ERRORS = (yaml.YAMLError,) if yaml is not None else ()
PARSE_ERRORS = (OSError, UnicodeError, ValueError) + YAML_ERRORS


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
PORTABLE_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
EXECUTABLE_SUFFIXES = {".py", ".sh", ".bash"}
INSTRUCTION_TOKEN_CAP = 2_000
OVERLAY_TOKEN_CAP = 1_500
DESCRIPTION_TOKEN_CAP = 2_000
MEMORY_INDEX_TOKEN_RESERVE = 1_500
TOTAL_STATIC_TOKEN_CAP = 8_000
# Claude Code plus the neutral trio — every harness whose roster is
# resolved separately (SPEC §4.1, §5).
HARNESSES = ("claude", *NEUTRAL_HARNESSES)
DEFAULT_APM_SKILLS = {
    "create-skill",
    "failing-test-first",
    "github-cli",
    "linear",
    "memory-conventions",
    "obsidian",
    "safe-deletion",
    "tmux",
    "close-the-loop",
    "dispatching-subagents",
    "primer",
    "sanity-check",
    "supervised-lane-loop",
}
# Retired at M3: installer-owned projection (APM + scripts/sync.py)
# replaced the committed symlink matrix. Their presence is now an error.
RETIRED_PROJECTIONS = (
    ".agents/skills",
    ".claude/skills",
    ".codex/skills",
    ".claude/agents",
    ".codex/agents",
    ".github/agents",
)


@dataclass(frozen=True)
class Finding:
    level: str
    path: Path
    message: str


def mini_yaml(text: str) -> dict[str, object]:
    """Minimal fallback for flat `key: value` frontmatter when PyYAML is
    unavailable (fresh machines). Handles quoted values and comments;
    values keep embedded colons verbatim."""
    parsed: dict[str, object] = {}
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        parsed[key.strip()] = value
    return parsed


def parse_skill(skill_file: Path) -> tuple[dict[str, object], str]:
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md must start with ---")

    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("SKILL.md has unclosed YAML frontmatter") from exc

    raw = "\n".join(lines[1:closing])
    frontmatter = yaml.safe_load(raw) if yaml else mini_yaml(raw)
    if not isinstance(frontmatter, dict):
        raise ValueError("frontmatter must be a YAML mapping")

    return frontmatter, "\n".join(lines[closing + 1 :]).strip()


def local_link_target(skill_file: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None

    target = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not target:
        return None
    return skill_file.parent / target


def validate_skill(skill_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.is_file():
        return [Finding("error", skill_dir, "missing SKILL.md")]

    try:
        frontmatter, body = parse_skill(skill_file)
    except PARSE_ERRORS as exc:
        return [Finding("error", skill_file, str(exc))]

    unknown_fields = sorted(set(frontmatter) - PORTABLE_FIELDS)
    if unknown_fields:
        findings.append(
            Finding(
                "error",
                skill_file,
                f"non-portable frontmatter fields: {', '.join(unknown_fields)}",
            )
        )

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name:
        findings.append(Finding("error", skill_file, "name must be a non-empty string"))
    else:
        if len(name) > 64:
            findings.append(Finding("error", skill_file, "name exceeds 64 characters"))
        if not NAME_RE.fullmatch(name):
            findings.append(
                Finding("error", skill_file, "name must use lowercase kebab-case")
            )
        if name != skill_dir.name:
            findings.append(
                Finding(
                    "error",
                    skill_file,
                    f"name {name!r} does not match directory {skill_dir.name!r}",
                )
            )

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        findings.append(
            Finding("error", skill_file, "description must be a non-empty string")
        )
    elif len(description) > 1024:
        findings.append(
            Finding("error", skill_file, "description exceeds 1024 characters")
        )

    if not body:
        findings.append(Finding("error", skill_file, "skill body is empty"))

    line_count = len(skill_file.read_text(encoding="utf-8").splitlines())
    if line_count > 500:
        findings.append(
            Finding(
                "warning",
                skill_file,
                f"SKILL.md has {line_count} lines; prefer fewer than 500",
            )
        )

    if (skill_dir / "README.md").exists():
        findings.append(
            Finding("error", skill_dir / "README.md", "skill directories cannot contain README.md")
        )

    for raw_target in LINK_RE.findall(body):
        target = local_link_target(skill_file, raw_target)
        if target is not None and not target.exists():
            findings.append(
                Finding(
                    "error",
                    skill_file,
                    f"relative link does not resolve: {raw_target}",
                )
            )

    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        for script in sorted(path for path in scripts_dir.rglob("*") if path.is_file()):
            if script.suffix in EXECUTABLE_SUFFIXES and not os.access(script, os.X_OK):
                findings.append(
                    Finding("error", script, "script must have an executable mode")
                )

    return findings


def discover_skill_dirs(root: Path, target: Path | None) -> list[Path]:
    if target is None:
        skills_root = root / "skills"
        # #9: this repository no longer vendors skills — they are pinned
        # apm.yml dependencies on jonhill90/skills and jonhill90/skills-private
        # instead, each with its own validator and CI. No local skills/ is
        # the expected steady state, not an error.
        if not skills_root.is_dir():
            return []
        return sorted(path for path in skills_root.iterdir() if path.is_dir())

    target = target.resolve()
    if target.name == "SKILL.md":
        target = target.parent
    if (target / "SKILL.md").is_file():
        return [target]
    if target.name == "skills" and target.is_dir():
        return sorted(path for path in target.iterdir() if path.is_dir())
    raise ValueError(f"target is not a skill directory or skills root: {target}")


# AGENTS.md caps SKILL.md at 500 lines. Enforced since 2026-07-27: it was a
# convention before, and skills/tmux reached 493 lines with nobody notified
# (#82). The warning band exists because "seven lines from breaking" and
# "fine" look identical in a diff.
SKILL_LINE_CAP = 500
SKILL_LINE_WARN = 450


def validate_skill_length(skill_dir: Path) -> list[Finding]:
    """Keep SKILL.md within the cap, and say so before it is breached."""
    path = skill_dir / "SKILL.md"
    if not path.is_file():
        return []
    lines = len(path.read_text(encoding="utf-8").splitlines())
    if lines > SKILL_LINE_CAP:
        return [Finding(
            "error", path,
            f"{lines} lines exceeds the {SKILL_LINE_CAP}-line cap — move "
            "detail into references/ (progressive disclosure)",
        )]
    if lines > SKILL_LINE_WARN:
        return [Finding(
            "warning", path,
            f"{lines} lines, approaching the {SKILL_LINE_CAP}-line cap — "
            "move detail into references/ before it breaks",
        )]
    return []


def validate_projections(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative_path in RETIRED_PROJECTIONS:
        projection = root / relative_path
        if projection.is_symlink() or projection.exists():
            findings.append(
                Finding(
                    "error",
                    projection,
                    "retired compatibility projection present; "
                    "projection is installer-owned (scripts/sync.py)",
                )
            )
    return findings


def description_tokens_by_harness(root: Path) -> dict[str, float]:
    """Static description cost per harness, against its resolved roster.

    A skill scoped to one harness is charged to that harness only — the
    point of per-harness rosters (SPEC §4.1). With a flat roster every
    harness resolves to the same set and the numbers are identical.
    """
    roster = root / "settings" / "default-skills.txt"
    if not roster.is_file():
        names_by_harness = {
            harness: [d.name for d in discover_skill_dirs(root, None)]
            for harness in HARNESSES
        }
    else:
        names_by_harness = {
            harness: load_default_skills(root, harness) for harness in HARNESSES
        }
    totals: dict[str, float] = {}
    # #9: skill descriptions live in jonhill90/skills and
    # jonhill90/skills-private now, not locally, so this repo can no longer
    # compute the description-token component from disk. The live
    # instrument is scripts/measure_e15.py, which reads the *deployed*
    # ~/.claude/skills tree and is the authority for the §6 budget; this
    # function's contribution collapses to 0 without a local skills/.
    if not (root / "skills").is_dir():
        return {harness: 0.0 for harness in HARNESSES}
    for harness, names in names_by_harness.items():
        description_bytes = 0
        for name in sorted(set(names)):
            try:
                frontmatter, _ = parse_skill(root / "skills" / name / "SKILL.md")
            except PARSE_ERRORS:
                continue
            description = frontmatter.get("description")
            if isinstance(description, str):
                description_bytes += len(description.encode("utf-8"))
        totals[harness] = token_estimate_bytes(description_bytes)
    return totals


def validate_apm_skill_roster(root: Path) -> list[Finding]:
    """Keep public skills distinct from the personal default package."""
    roster = root / "settings" / "default-skills.txt"
    if not roster.is_file():
        return [Finding("error", roster, "default skill roster missing")]
    # Per-harness sections (SPEC §4.1): the default package is the union
    # across every section, since APM installs the union.
    actual = set(roster_union(root))
    findings: list[Finding] = []
    missing = sorted(DEFAULT_APM_SKILLS - actual)
    unexpected = sorted(actual - DEFAULT_APM_SKILLS)
    if missing:
        findings.append(
            Finding(
                "error",
                roster,
                f"missing default-package skills: {', '.join(missing)}",
            )
        )
    if unexpected:
        findings.append(
            Finding(
                "error",
                roster,
                f"unexpected default-package skills: {', '.join(unexpected)}",
            )
        )
    return findings


# SPEC §10.1 rule 5. A row promising future verification is exactly what the
# retired prior-bar path looked like, and the promise came due nine days late
# the one time it was used. Cheap to check, so it is checked rather than
# trusted — the 500-line skill cap was a convention nothing enforced and was
# three days from being breached silently (#82).
OPEN_CAVEAT = re.compile(r"\*\*will be\*\*|will be re-verified|prior bar", re.I)


def validate_roster_resolves(root: Path) -> list[Finding]:
    """Every roster name must name a skill that exists here.

    Nothing checked this, so deleting a skill directory while leaving its
    roster line validated clean — and the wrapper would then derive disable
    entries for a skill that is not there. Same silent shape as #93.

    #9: this repo no longer vendors skills/, so a roster name resolves via
    the pinned apm.yml dependencies (jonhill90/skills,
    jonhill90/skills-private) instead — each has its own validator and CI,
    and `apm lock`/`apm install` is the mechanical proof of resolution, not
    a local file check. Skip silently rather than flag every roster line
    as unresolvable.
    """
    roster = root / "settings" / "default-skills.txt"
    if not roster.is_file() or not (root / "skills").is_dir():
        return []
    return [
        Finding(
            "error", roster,
            f"{name} is in the roster but skills/{name}/SKILL.md does not exist",
        )
        for name in roster_union(root)
        if not (root / "skills" / name / "SKILL.md").is_file()
    ]


def validate_roster_credit(root: Path) -> list[Finding]:
    """No default-roster skill may carry an unfinished verification promise."""
    manifest = root / "docs" / "provenance-manifest.md"
    if not manifest.is_file():
        # #29: nothing else in this validator checks SPEC §10.1 rule 5, so a
        # moved/renamed/lost manifest must fail closed, not report clean.
        return [
            Finding(
                "error",
                manifest,
                "provenance manifest is missing; SPEC §10.1 rule 5 "
                "(no default-roster skill with an unfinished verification "
                "promise) cannot be enforced without it",
            )
        ]
    roster = set(roster_union(root))
    findings: list[Finding] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or not OPEN_CAVEAT.search(line):
            continue
        if "caveat cleared" in line.lower():
            continue
        for name in roster:
            if f"`{name}`" in line:
                findings.append(
                    Finding(
                        "error",
                        manifest,
                        f"{name} is in the default roster with an unfinished "
                        "verification promise; SPEC §10.1 rule 5 requires it "
                        "ship opt-in until the bar is cleared",
                    )
                )
    return findings


SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def parse_skill_source_dependencies(root: Path) -> list[dict[str, object]]:
    """Every entry under apm.yml's `dependencies.apm`, as a dict of
    whatever `key: value` pairs it declares, plus `skills` (bool: does
    this entry declare a `skills:` key at all — i.e. is it a skill-bundle
    dependency, not some other kind of APM dependency).

    A small line-based reader, not a general YAML parser — apm.yml's
    `dependencies.apm` list has a flat, regular `    - key: value` shape,
    and this module stays usable on machines without PyYAML. Full-line
    comments (this repository documents *why* each ref is pinned directly
    above the entry) are stripped before splitting into entries: an
    earlier version did not strip them, which broke the entry-boundary
    regex on the very first real comment line and silently returned zero
    entries against the actual committed apm.yml (#9 review) — every
    fixture that exercised this function beforehand was comment-free and
    passed regardless, which is why `RealApmYmlShapeTests` in
    tests/test_validate_repository.py runs this against the literal
    committed file, not just a synthetic string.
    """
    apm_yml = root / "apm.yml"
    if not apm_yml.is_file():
        return []
    block = apm_dependency_block(apm_yml.read_text(encoding="utf-8"))
    block = "\n".join(
        line for line in block.splitlines() if not line.strip().startswith("#")
    )
    entries = re.split(r"(?=^    - )", block, flags=re.M)
    deps: list[dict[str, object]] = []
    for entry in entries:
        if not entry.strip():
            continue
        dep: dict[str, object] = {
            "skills": bool(re.search(r"^\s*skills:", entry, re.M))
        }
        for key in ("git", "ref", "alias"):
            match = re.search(rf"^\s*{key}:\s*(.+?)\s*$", entry, re.M)
            if match:
                dep[key] = match.group(1).strip("'\"")
        deps.append(dep)
    return deps


def validate_skill_source_pins(root: Path) -> list[Finding]:
    """Every skill-bundle dependency in apm.yml (one that declares
    `skills:`) must be pinned to an immutable commit SHA, not a branch or
    tag name (#9). A moving ref makes `apm install` non-reproducible and
    silently changes what gets deployed between runs.
    """
    apm_yml = root / "apm.yml"
    if not apm_yml.is_file():
        # #29 sweep: apm.yml is the sole record of the SHA-pin requirement
        # itself, and nothing else in this validator checks it exists — a
        # moved/renamed/lost apm.yml must fail closed, not report clean.
        return [
            Finding(
                "error",
                apm_yml,
                "apm.yml is missing; skill-bundle dependency pins (#9) "
                "cannot be checked without it",
            )
        ]
    findings: list[Finding] = []
    for dep in parse_skill_source_dependencies(root):
        if not dep.get("skills"):
            continue  # not a skill-bundle dependency; no pin requirement
        alias = dep.get("alias") or "(unnamed dependency)"
        raw_ref = dep.get("ref") or ""
        assert isinstance(raw_ref, str)
        if not raw_ref or not SHA_RE.match(raw_ref.lower()):
            findings.append(
                Finding(
                    "error",
                    apm_yml,
                    f"{alias}: ref must be pinned to a 40-character commit "
                    f"SHA, not {raw_ref or '(missing)'} — a branch or tag "
                    "name is not reproducible",
                )
            )
    return findings


def validate_privacy(root: Path) -> list[Finding]:
    """Flag tracked markdown containing terms from the untracked
    .privacy-denylist (one term per line; the terms never enter git)."""
    denylist_file = root / ".privacy-denylist"
    if not denylist_file.is_file():
        return []
    terms = [
        line.strip()
        for line in denylist_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    findings: list[Finding] = []
    skip_parts = {".git", "apm_modules", "node_modules"}
    for md in sorted(root.rglob("*.md")):
        if skip_parts & set(md.parts) or not md.is_file():
            continue
        text = md.read_text(encoding="utf-8", errors="ignore").lower()
        for index, term in enumerate(terms, start=1):
            if term.lower() in text:
                findings.append(
                    Finding(
                        "error",
                        md,
                        f"contains privacy-denylisted term #{index} "
                        "(see local .privacy-denylist)",
                    )
                )
    return findings


def validate_skill_collection(skill_dirs: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    names: dict[str, Path] = {}

    for skill_dir in skill_dirs:
        findings.extend(validate_skill(skill_dir))
        findings.extend(validate_skill_length(skill_dir))
        try:
            frontmatter, _ = parse_skill(skill_dir / "SKILL.md")
        except PARSE_ERRORS:
            continue
        name = frontmatter.get("name")
        if isinstance(name, str):
            previous = names.get(name)
            if previous is not None:
                findings.append(
                    Finding(
                        "error",
                        skill_dir / "SKILL.md",
                        f"duplicate skill name {name!r}; first declared in {previous}",
                    )
                )
            else:
                names[name] = skill_dir / "SKILL.md"

    return findings


def token_estimate_bytes(size: int) -> float:
    return size / 4


def validate_static_context(root: Path) -> list[Finding]:
    """Enforce the SPEC section 6 static-context budgets.

    The memory index is machine-local, so the repository check reserves its
    full component budget when enforcing the total. E15 measures the live
    index separately.
    """
    findings: list[Finding] = []
    instructions = root / "instructions" / "global.instructions.md"
    if not instructions.is_file():
        return [Finding("error", instructions, "canonical instructions missing")]

    instruction_tokens = token_estimate_bytes(instructions.stat().st_size)
    if instruction_tokens > INSTRUCTION_TOKEN_CAP:
        findings.append(
            Finding(
                "error",
                instructions,
                f"canonical instructions use ~{instruction_tokens:.0f} tokens; "
                f"cap is {INSTRUCTION_TOKEN_CAP}",
            )
        )

    overlay_tokens = 0.0
    overlays = root / "instructions" / "overlays"
    if overlays.is_dir():
        for overlay in sorted(overlays.glob("*.md")):
            tokens = token_estimate_bytes(overlay.stat().st_size)
            overlay_tokens = max(overlay_tokens, tokens)
            if tokens > OVERLAY_TOKEN_CAP:
                findings.append(
                    Finding(
                        "error",
                        overlay,
                        f"harness overlay uses ~{tokens:.0f} tokens; "
                        f"cap is {OVERLAY_TOKEN_CAP}",
                    )
                )

    by_harness = description_tokens_by_harness(root)
    for harness, tokens in sorted(by_harness.items()):
        if tokens > DESCRIPTION_TOKEN_CAP:
            findings.append(
                Finding(
                    "error",
                    root / "skills",
                    f"{harness}: installed-skill descriptions use "
                    f"~{tokens:.0f} tokens; cap is {DESCRIPTION_TOKEN_CAP}",
                )
            )
    # The thickest harness sets the aggregate (SPEC §6 measures the worst
    # case), but each harness is now charged only for its own roster.
    description_tokens = max(by_harness.values(), default=0.0)

    total_tokens = (
        instruction_tokens
        + overlay_tokens
        + description_tokens
        + MEMORY_INDEX_TOKEN_RESERVE
    )
    if total_tokens > TOTAL_STATIC_TOKEN_CAP:
        findings.append(
            Finding(
                "error",
                root / "instructions",
                f"thickest-harness static context uses ~{total_tokens:.0f} "
                f"tokens including the memory-index reserve; cap is "
                f"{TOTAL_STATIC_TOKEN_CAP}",
            )
        )
    return findings


def validate(root: Path, target: Path | None = None) -> list[Finding]:
    skill_dirs = discover_skill_dirs(root, target)
    findings = validate_skill_collection(skill_dirs)

    if target is None:
        findings.extend(validate_projections(root))
        findings.extend(validate_apm_skill_roster(root))
        findings.extend(validate_roster_credit(root))
        findings.extend(validate_roster_resolves(root))
        findings.extend(validate_skill_source_pins(root))
        findings.extend(validate_privacy(root))
        findings.extend(validate_static_context(root))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "target",
        nargs="?",
        type=Path,
        help="optional skill directory, SKILL.md, or skills root",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    target = args.target
    if target is not None and not target.is_absolute():
        target = root / target

    try:
        findings = validate(root, target)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    for finding in findings:
        try:
            display_path = finding.path.relative_to(root)
        except ValueError:
            display_path = finding.path
        print(f"{finding.level.upper()}: {display_path}: {finding.message}")

    error_count = sum(finding.level == "error" for finding in findings)
    warning_count = sum(finding.level == "warning" for finding in findings)
    skill_count = len(discover_skill_dirs(root, target))
    print(
        f"Validated {skill_count} skill(s): "
        f"{error_count} error(s), {warning_count} warning(s)"
    )
    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main())
