#!/usr/bin/env python3
"""Read-only OKF v0.2 linter for the agent memory vault.

**TOOLS DETECT AND REPORT. THEY NEVER REWRITE MEANING.** This script never
writes to the vault. It parses frontmatter, checks it against the OKF v0.2
SPEC (https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/
okf/SPEC.md), and prints a report. Deciding whether a flagged fact is still
true, resolving a contradiction, or writing a correction is explicitly out
of scope for this tool -- that judgement needs a model in the loop and
belongs to a human or an AI-assisted follow-up, never to this script. See
docs/okf-adoption-280.md for the design this implements and why the split
is the deliverable.

All checks are deterministic string/date/hash operations -- no model calls.

Usage:
    python3 scripts/memory_lint.py [--vault PATH] [--json]
                                    [--stale-verified-days N]

Exit status reflects OKF's own conformance minimum (SPEC §11) only:
parseable frontmatter and a non-empty `type` on every concept document.
Everything else this script reports -- missing recommended fields, absent
trust/lifecycle families, broken links, duplicates, possible
contradictions, index drift -- is advisory and does not change the exit
code. OKF §11 requires consumers not reject a bundle for any of those, and
a linter that fails the build on a warning stops being trusted quickly.

`--strict` additionally fails on an unlinked fact (agent-dotfiles#300): a
fact with no `agent/index.md` link is unreachable by recall, which is a
regression a guard should catch before it accumulates. Broken `[[link]]`
targets stay advisory even in `--strict` -- resolving one needs a human
judgement call (deleted vs. renamed vs. never written) that this read-only
tool cannot make; per #280, a linter may FLAG, it may never ASSIGN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # fresh machines lack PyYAML; use the fallback parser
    yaml = None

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
MDLINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
LEGACY_CITATIONS_RE = re.compile(r"^#{1,6}\s*Citations\s*$", re.MULTILINE)

RECOMMENDED_FIELDS = ("title", "description")
OKF_TRUST_FIELDS = ("generated", "verified", "status", "stale_after", "sources")


def mini_yaml(text: str) -> dict[str, object]:
    """Minimal fallback for flat `key: value` frontmatter when PyYAML is
    unavailable. Good enough to read `type`, `title`, `stale_after`, and
    other scalar keys; list/mapping-valued keys (`sources`, `verified`)
    degrade to their raw string form rather than failing the run."""
    parsed: dict[str, object] = {}
    key = None
    for line in text.splitlines():
        raw = line.rstrip()
        if not raw or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")) and key is not None:
            continue  # nested block under the last top-level key; skipped
        if ":" not in raw:
            continue
        k, _, v = raw.partition(":")
        key = k.strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        parsed[key] = v
    return parsed


@dataclass
class Concept:
    path: Path
    slug: str
    frontmatter: dict | None
    frontmatter_error: str | None
    body: str


@dataclass
class Finding:
    level: str  # "error" | "warn" | "info"
    check: str
    message: str


@dataclass
class Report:
    vault: Path
    fact_count: int = 0
    index_lines: int = 0
    findings: list[Finding] = field(default_factory=list)
    field_counts: dict[str, int] = field(default_factory=dict)
    unlinked_fact_count: int = 0

    def add(self, level: str, check: str, message: str) -> None:
        self.findings.append(Finding(level, check, message))

    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    def strict_errors(self) -> list[Finding]:
        """Conformance errors plus unlinked facts (agent-dotfiles#300): the
        two defect families that must not silently drift back. Broken
        `[[link]]` targets are excluded on purpose -- a linter may FLAG a
        dangling link, it may never ASSIGN one (#280), so it cannot gate a
        build red without a human's judgement call on each one."""
        strict = list(self.errors())
        if self.unlinked_fact_count:
            strict.append(
                Finding(
                    "error",
                    "index",
                    f"{self.unlinked_fact_count}/{self.fact_count} facts have no corresponding index.md link (strict mode)",
                )
            )
        return strict


def read_concept(path: Path) -> Concept:
    text = path.read_text(encoding="utf-8")
    slug = path.stem
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return Concept(path, slug, None, "missing frontmatter delimiter", text)
    try:
        closing = lines.index("---", 1)
    except ValueError:
        return Concept(path, slug, None, "unclosed frontmatter block", text)
    raw = "\n".join(lines[1:closing])
    body = "\n".join(lines[closing + 1 :])
    try:
        fm = yaml.safe_load(raw) if yaml else mini_yaml(raw)
    except Exception as exc:  # yaml.YAMLError, but keep the fallback path in scope too
        return Concept(path, slug, None, f"unparseable YAML: {exc}", body)
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        return Concept(path, slug, None, "frontmatter is not a mapping", body)
    return Concept(path, slug, fm, None, body)


def load_facts(vault: Path) -> list[Concept]:
    facts_dir = vault / "agent" / "facts"
    return [read_concept(p) for p in sorted(facts_dir.glob("*.md"))]


def check_conformance(facts: list[Concept], report: Report) -> None:
    """OKF SPEC §11 conformance minimum: parseable frontmatter, non-empty
    `type`. This is the only check that affects exit status."""
    bad = 0
    for c in facts:
        if c.frontmatter_error:
            report.add("error", "conformance", f"1 fact: {c.frontmatter_error}")
            bad += 1
            continue
        t = c.frontmatter.get("type")
        if not t or not str(t).strip():
            report.add("error", "conformance", "1 fact has an empty or missing `type`")
            bad += 1
    report.add(
        "info",
        "conformance",
        f"{len(facts) - bad}/{len(facts)} facts conform to OKF §11 (parseable frontmatter, non-empty type)",
    )


def check_recommended_fields(facts: list[Concept], report: Report) -> None:
    ok_facts = [c for c in facts if c.frontmatter is not None]
    for field_name in RECOMMENDED_FIELDS:
        present = sum(1 for c in ok_facts if c.frontmatter.get(field_name))
        report.field_counts[field_name] = present
        missing = len(ok_facts) - present
        if missing:
            report.add(
                "warn",
                "recommended-fields",
                f"{missing}/{len(ok_facts)} facts missing recommended `{field_name}` (OKF §4.1)",
            )
    both_missing = sum(
        1
        for c in ok_facts
        if not c.frontmatter.get("title") and not c.frontmatter.get("description")
    )
    report.add(
        "info",
        "recommended-fields",
        f"{both_missing}/{len(ok_facts)} facts missing both title and description",
    )


def check_okf_v02_families(facts: list[Concept], report: Report) -> None:
    """§13.2 additive families: report presence, don't require it."""
    ok_facts = [c for c in facts if c.frontmatter is not None]
    for field_name in OKF_TRUST_FIELDS:
        present = sum(1 for c in ok_facts if field_name in c.frontmatter)
        report.field_counts[field_name] = present
        report.add(
            "info",
            "okf-v0.2-families",
            f"{present}/{len(ok_facts)} facts carry `{field_name}` (OKF v0.2 §5, additive)",
        )


def check_legacy_v01_fields(facts: list[Concept], report: Report) -> None:
    """§13.1 breaking changes: `timestamp` -> `generated.at`, body
    `# Citations` -> `sources`. Neither is an error under v0.2 (both have a
    documented fallback); flag counts so a future additive pass knows the
    size of the fallback population it must keep serving."""
    ok_facts = [c for c in facts if c.frontmatter is not None]
    legacy_timestamp = sum(1 for c in ok_facts if "timestamp" in c.frontmatter)
    legacy_citations = sum(1 for c in facts if LEGACY_CITATIONS_RE.search(c.body))
    report.field_counts["timestamp (legacy)"] = legacy_timestamp
    report.field_counts["# Citations (legacy)"] = legacy_citations
    report.add(
        "info",
        "legacy-v0.1-fields",
        f"{legacy_timestamp}/{len(ok_facts)} facts carry legacy `timestamp` (superseded by `generated.at`, OKF §13.1)",
    )
    report.add(
        "info",
        "legacy-v0.1-fields",
        f"{legacy_citations}/{len(facts)} facts carry a body `# Citations` heading (superseded by `sources`, OKF §13.1)",
    )


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    s = str(value).strip()
    for parser in (
        lambda v: date.fromisoformat(v),
        lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")).date(),
    ):
        try:
            return parser(s)
        except ValueError:
            continue
    return None


def check_stale_after(facts: list[Concept], report: Report, today: date) -> None:
    ok_facts = [c for c in facts if c.frontmatter is not None]
    with_field = [c for c in ok_facts if "stale_after" in c.frontmatter]
    stale = 0
    unparseable = 0
    for c in with_field:
        d = _parse_date(c.frontmatter.get("stale_after"))
        if d is None:
            unparseable += 1
            continue
        if today >= d:
            stale += 1
    if with_field:
        report.add(
            "warn" if stale else "info",
            "freshness",
            f"{stale}/{len(with_field)} facts with `stale_after` are stale as of {today.isoformat()}",
        )
        if unparseable:
            report.add("warn", "freshness", f"{unparseable} facts have an unparseable `stale_after` date")
    else:
        report.add(
            "info",
            "freshness",
            f"0/{len(ok_facts)} facts carry `stale_after` -- staleness cannot be assessed from frontmatter yet",
        )


def check_verified_recency(facts: list[Concept], report: Report, today: date, stale_days: int) -> None:
    ok_facts = [c for c in facts if c.frontmatter is not None]
    with_field = [c for c in ok_facts if "verified" in c.frontmatter]
    no_field = len(ok_facts) - len(with_field)
    report.add(
        "info",
        "trust",
        f"{no_field}/{len(ok_facts)} facts carry no `verified[]` entry (OKF trust tier: unverified, §5.3)",
    )
    if not with_field:
        return
    stale = 0
    for c in with_field:
        v = c.frontmatter.get("verified")
        entries = v if isinstance(v, list) else [v]
        dates = [d for d in (_parse_date(e.get("at")) for e in entries if isinstance(e, dict)) if d]
        if not dates:
            continue
        latest = max(dates)
        if (today - latest).days > stale_days:
            stale += 1
    report.add(
        "warn" if stale else "info",
        "trust",
        f"{stale}/{len(with_field)} verified facts have no verification within {stale_days} days",
    )


def check_link_integrity(facts: list[Concept], report: Report) -> None:
    slugs = {c.slug for c in facts}
    broken = 0
    total = 0
    for c in facts:
        for m in WIKILINK_RE.finditer(c.body):
            total += 1
            target = m.group(1).strip()
            if target not in slugs:
                broken += 1
        for m in MDLINK_RE.finditer(c.body):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            total += 1
            target_slug = Path(target).stem
            if target_slug not in slugs:
                broken += 1
    report.add("info" if not broken else "warn", "link-integrity", f"{broken}/{total} internal links resolve to a missing fact")


def check_near_duplicates(facts: list[Concept], report: Report) -> None:
    def normalize(body: str) -> str:
        return re.sub(r"\s+", " ", body).strip().lower()

    by_hash: dict[str, int] = {}
    for c in facts:
        h = hashlib.sha256(normalize(c.body).encode("utf-8")).hexdigest()
        by_hash[h] = by_hash.get(h, 0) + 1
    dup_groups = sum(1 for n in by_hash.values() if n > 1)
    dup_facts = sum(n for n in by_hash.values() if n > 1)
    report.add(
        "info" if not dup_groups else "warn",
        "near-duplicates",
        f"{dup_groups} exact-duplicate body group(s) across {dup_facts} facts (hash-based)",
    )


def _slug_tokens(slug: str) -> set[str]:
    return set(t for t in re.split(r"[-_]", slug) if len(t) > 2)


def check_possible_contradictions(facts: list[Concept], report: Report, threshold: float = 0.6) -> None:
    """Deterministic heuristic only: near-identical slugs (high token
    overlap) whose bodies differ. This *flags candidates for AI review*; it
    does not decide whether a contradiction actually exists -- that
    judgement is explicitly out of this tool's boundary."""

    def normalize(body: str) -> str:
        return re.sub(r"\s+", " ", body).strip().lower()

    hashed = [(c, hashlib.sha256(normalize(c.body).encode("utf-8")).hexdigest()) for c in facts]
    candidates = 0
    for i in range(len(hashed)):
        for j in range(i + 1, len(hashed)):
            c1, h1 = hashed[i]
            c2, h2 = hashed[j]
            if h1 == h2:
                continue  # exact duplicates are their own check
            t1, t2 = _slug_tokens(c1.slug), _slug_tokens(c2.slug)
            if not t1 or not t2:
                continue
            overlap = len(t1 & t2) / len(t1 | t2)
            if overlap >= threshold:
                candidates += 1
    report.add(
        "info" if not candidates else "warn",
        "possible-contradictions",
        f"{candidates} fact pair(s) with similar slugs and differing bodies -- candidates for AI review, not confirmed contradictions",
    )


def check_index(vault: Path, facts: list[Concept], report: Report) -> None:
    index_path = vault / "agent" / "index.md"
    if not index_path.exists():
        report.add("warn", "index", "agent/index.md is missing")
        return
    index_text = index_path.read_text(encoding="utf-8")
    report.index_lines = len(index_text.splitlines())
    index_concept = read_concept(index_path)
    if index_concept.frontmatter:
        declared = index_concept.frontmatter.get("okf_version")
        report.add(
            "info",
            "index",
            f"index.md declares okf_version: {declared!r} (OKF §12)" if declared else "index.md carries frontmatter but no okf_version key",
        )
    else:
        report.add("info", "index", "index.md declares no okf_version (OKF §12, optional)")
    linked_slugs = set()
    for m in WIKILINK_RE.finditer(index_text):
        linked_slugs.add(m.group(1).strip())
    for m in MDLINK_RE.finditer(index_text):
        target = m.group(1).strip()
        if target.startswith(("http://", "https://")):
            continue
        linked_slugs.add(Path(target).stem)
    fact_slugs = {c.slug for c in facts}
    missing_from_index = fact_slugs - linked_slugs
    orphaned_in_index = linked_slugs - fact_slugs
    report.unlinked_fact_count = len(missing_from_index)
    report.add(
        "warn" if missing_from_index else "info",
        "index",
        f"{len(missing_from_index)}/{len(fact_slugs)} facts have no corresponding index.md link",
    )
    report.add(
        "warn" if orphaned_in_index else "info",
        "index",
        f"{len(orphaned_in_index)} index.md links point at a fact that no longer exists",
    )


def build_report(vault: Path, today: date, stale_days: int) -> Report:
    report = Report(vault=vault)
    facts = load_facts(vault)
    report.fact_count = len(facts)
    check_conformance(facts, report)
    check_recommended_fields(facts, report)
    check_okf_v02_families(facts, report)
    check_legacy_v01_fields(facts, report)
    check_stale_after(facts, report, today)
    check_verified_recency(facts, report, today, stale_days)
    check_link_integrity(facts, report)
    check_near_duplicates(facts, report)
    check_possible_contradictions(facts, report)
    check_index(vault, facts, report)
    return report


def render_text(report: Report) -> str:
    lines = [
        f"OKF v0.2 read-only lint -- {report.vault}",
        f"facts: {report.fact_count}   index lines: {report.index_lines}",
        "",
    ]
    for level in ("error", "warn", "info"):
        group = [f for f in report.findings if f.level == level]
        if not group:
            continue
        lines.append(f"[{level.upper()}]")
        for f in group:
            lines.append(f"  ({f.check}) {f.message}")
        lines.append("")
    lines.append("This tool detects and reports only. No file was written.")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(
        {
            "vault": str(report.vault),
            "fact_count": report.fact_count,
            "index_lines": report.index_lines,
            "field_counts": report.field_counts,
            "findings": [f.__dict__ for f in report.findings],
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", type=Path, default=None, help="Vault root (default: $AGENT_MEMORY_VAULT)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--stale-verified-days", type=int, default=90, help="Flag verified[] entries older than N days")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also fail on an unlinked fact (agent-dotfiles#300), not just OKF section 11 conformance",
    )
    args = parser.parse_args(argv)

    vault = args.vault or (Path(os.environ["AGENT_MEMORY_VAULT"]) if os.environ.get("AGENT_MEMORY_VAULT") else None)
    if vault is None:
        print("error: no --vault given and $AGENT_MEMORY_VAULT is unset", file=sys.stderr)
        return 2
    if not (vault / "agent" / "facts").is_dir():
        print(f"error: {vault}/agent/facts does not exist", file=sys.stderr)
        return 2

    today = datetime.now(timezone.utc).date()
    report = build_report(vault, today, args.stale_verified_days)
    print(render_json(report) if args.json else render_text(report))
    return 1 if (report.strict_errors() if args.strict else report.errors()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
