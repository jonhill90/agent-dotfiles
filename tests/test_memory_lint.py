"""Tests for scripts/memory_lint.py: the read-only OKF v0.2 vault linter.

All fixtures are synthetic (invented facts about a fictional "widget"
system), never real vault content -- this file must not carry Jon's
memory content, per the brief's constraint (agent-dotfiles#280).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import memory_lint as ml  # noqa: E402


def write_fact(facts_dir: Path, slug: str, frontmatter: str, body: str = "") -> None:
    (facts_dir / f"{slug}.md").write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")


class MemoryLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        self.agent = self.vault / "agent"
        self.facts = self.agent / "facts"
        self.facts.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_index(self, body: str) -> None:
        (self.agent / "index.md").write_text(body, encoding="utf-8")

    # -- conformance -----------------------------------------------------

    def test_conforming_fact_passes(self) -> None:
        write_fact(self.facts, "widget-color", "type: reference\ntitle: Widget color\ndescription: it is blue")
        self.write_index("# Facts\n\n- [Widget color](facts/widget-color.md) — it is blue\n")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertEqual(report.errors(), [])

    def test_missing_type_is_an_error(self) -> None:
        write_fact(self.facts, "no-type", "title: No type here")
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertTrue(any("type" in f.message for f in report.errors()))
        self.assertEqual(ml.main(["--vault", str(self.vault)]), 1)

    def test_unparseable_frontmatter_is_an_error(self) -> None:
        # An unquoted colon inside a scalar value breaks YAML mapping
        # parsing -- this is the real defect the linter found in the live
        # vault (two facts, reported in the PR by count only).
        write_fact(self.facts, "bad-yaml", 'title: Remembered word: BANANA\ntype: reference')
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertTrue(any(f.check == "conformance" and f.level == "error" for f in report.findings))

    def test_never_writes_to_the_vault(self) -> None:
        write_fact(self.facts, "widget-color", "type: reference")
        self.write_index("")
        before = {p: p.stat().st_mtime for p in self.vault.rglob("*") if p.is_file()}
        ml.build_report(self.vault, date(2026, 1, 1), 90)
        after = {p: p.stat().st_mtime for p in self.vault.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    # -- recommended fields (OKF §4.1) ------------------------------------

    def test_missing_title_and_description_are_warnings_not_errors(self) -> None:
        write_fact(self.facts, "bare", "type: reference")
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertEqual(report.errors(), [])
        self.assertTrue(any(f.check == "recommended-fields" and f.level == "warn" for f in report.findings))

    # -- freshness: stale_after (OKF §5.5) --------------------------------

    def test_stale_after_in_the_past_is_flagged(self) -> None:
        write_fact(self.facts, "expired", "type: reference\nstale_after: 2020-01-01")
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "freshness"]
        self.assertTrue(any("1/1" in m for m in msgs))

    def test_stale_after_in_the_future_is_not_flagged_as_stale(self) -> None:
        write_fact(self.facts, "fresh", "type: reference\nstale_after: 2099-01-01")
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "freshness"]
        self.assertTrue(any("0/1" in m for m in msgs))

    # -- trust: verified[] (OKF §5.2/§5.3) --------------------------------

    def test_verified_recency_flags_old_verification(self) -> None:
        write_fact(
            self.facts,
            "old-verify",
            "type: reference\nverified: { by: human:jon, at: 2020-01-01T00:00:00Z }",
        )
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "trust" and "no verification within" in f.message]
        self.assertTrue(any("1/1" in m for m in msgs))

    def test_bare_verified_mapping_treated_as_one_element_list(self) -> None:
        # OKF §5.2: a bare {by, at} mapping MUST be treated as a
        # one-element list, not rejected.
        write_fact(
            self.facts,
            "bare-verify",
            "type: reference\nverified: { by: human:jon, at: 2026-01-01T00:00:00Z }",
        )
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertEqual(report.errors(), [])

    # -- link integrity (OKF §6.1) -----------------------------------------

    def test_broken_wikilink_is_flagged(self) -> None:
        write_fact(self.facts, "a", "type: reference", body="See [[does-not-exist]].\n")
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "link-integrity"]
        self.assertTrue(any("1/1" in m for m in msgs))

    def test_resolvable_wikilink_is_not_flagged(self) -> None:
        write_fact(self.facts, "a", "type: reference", body="See [[b]].\n")
        write_fact(self.facts, "b", "type: reference")
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "link-integrity"]
        self.assertTrue(any("0/1" in m for m in msgs))

    # -- near-duplicates (hash-based) --------------------------------------

    def test_identical_bodies_are_flagged_as_duplicates(self) -> None:
        write_fact(self.facts, "dup-a", "type: reference", body="The widget is blue.\n")
        write_fact(self.facts, "dup-b", "type: reference", body="The widget is blue.\n")
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "near-duplicates"]
        self.assertTrue(any("1 exact-duplicate" in m for m in msgs))

    def test_distinct_bodies_are_not_flagged_as_duplicates(self) -> None:
        write_fact(self.facts, "dup-a", "type: reference", body="The widget is blue.\n")
        write_fact(self.facts, "dup-b", "type: reference", body="The widget is red.\n")
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "near-duplicates"]
        self.assertTrue(any("0 exact-duplicate" in m for m in msgs))

    # -- possible contradictions (heuristic, never a verdict) --------------

    def test_similar_slugs_with_differing_bodies_are_flagged_as_candidates(self) -> None:
        write_fact(self.facts, "widget-color-blue-variant", "type: reference", body="The widget is blue.\n")
        write_fact(self.facts, "widget-color-red-variant", "type: reference", body="The widget is red.\n")
        self.write_index("")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "possible-contradictions"]
        self.assertTrue(any("1 fact pair" in m and "candidates for AI review" in m for m in msgs))

    # -- index reconciliation (read-only "rebuild") -------------------------

    def test_fact_missing_from_index_is_flagged(self) -> None:
        write_fact(self.facts, "orphan", "type: reference")
        self.write_index("# Facts\n\nnothing links here\n")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "index" and "corresponding index.md link" in f.message]
        self.assertTrue(any("1/1" in m for m in msgs))

    def test_index_link_to_deleted_fact_is_flagged(self) -> None:
        self.write_index("# Facts\n\n- [Ghost](facts/ghost.md) — no longer exists\n")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        msgs = [f.message for f in report.findings if f.check == "index" and "no longer exists" in f.message]
        self.assertTrue(any("1 index.md" in m for m in msgs))

    def test_okf_version_declaration_is_read_not_required(self) -> None:
        write_fact(self.facts, "a", "type: reference")
        self.write_index('---\nokf_version: "0.2"\n---\n\n- [[a]]\n')
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertTrue(any("okf_version" in f.message and "0.2" in f.message for f in report.findings))

    # -- strict mode (agent-dotfiles#300 guard) -----------------------------

    def test_unlinked_fact_is_not_an_error_by_default(self) -> None:
        write_fact(self.facts, "orphan", "type: reference")
        self.write_index("# Facts\n\nnothing links here\n")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertEqual(report.errors(), [])
        self.assertEqual(ml.main(["--vault", str(self.vault)]), 0)

    def test_unlinked_fact_is_a_strict_error(self) -> None:
        write_fact(self.facts, "orphan", "type: reference")
        self.write_index("# Facts\n\nnothing links here\n")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertTrue(any(f.check == "index" for f in report.strict_errors()))
        self.assertEqual(ml.main(["--vault", str(self.vault), "--strict"]), 1)

    def test_fully_linked_vault_passes_strict(self) -> None:
        write_fact(self.facts, "a", "type: reference")
        self.write_index("# Facts\n\n- [[a]]\n")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertEqual(report.strict_errors(), [])
        self.assertEqual(ml.main(["--vault", str(self.vault), "--strict"]), 0)

    def test_broken_link_target_stays_advisory_even_in_strict_mode(self) -> None:
        # #280: a linter may FLAG a dangling [[link]], never ASSIGN one --
        # so strict mode must not fail the build on it.
        write_fact(self.facts, "a", "type: reference", body="See [[does-not-exist]].\n")
        self.write_index("# Facts\n\n- [[a]]\n")
        report = ml.build_report(self.vault, date(2026, 1, 1), 90)
        self.assertEqual(report.strict_errors(), [])
        self.assertEqual(ml.main(["--vault", str(self.vault), "--strict"]), 0)


if __name__ == "__main__":
    unittest.main()
