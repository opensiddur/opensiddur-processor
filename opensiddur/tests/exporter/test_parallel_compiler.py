"""Unit tests for parallel compiler functionality in ExternalCompilerProcessor."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lxml import etree

from opensiddur.exporter.compiler import (
    JLPTEI_NAMESPACE,
    PROCESSING_NAMESPACE,
    _ProcessingCommand,
    _ProcessingContext,
)
from opensiddur.exporter.external_compiler import (
    STRUCTURAL_BLOCKS,
    TEI_NS,
    ExternalCompilerProcessor,
    _shared_split_points,
)
from opensiddur.exporter.linear import (
    LinearData,
    ParallelColumnOrder,
    get_linear_data,
    reset_linear_data,
)
from opensiddur.exporter.urn import ResolvedUrn, ResolvedUrnRange

P_NS = PROCESSING_NAMESPACE
J_NS = JLPTEI_NAMESPACE
XML_NS = "http://www.w3.org/XML/1998/namespace"

# Minimal valid JLPTEI document used by multiple tests
_MINIMAL_TEI = b"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
         xml:lang="he">
  <tei:text xml:lang="he">
    <tei:body>
      <tei:div corresp="urn:x-test:body">
        <tei:p>Body text</tei:p>
      </tei:div>
    </tei:body>
  </tei:text>
</tei:TEI>"""


# ── _build_parallel_urn ─────────────────────────────────────────────────────

class TestBuildParallelUrn(unittest.TestCase):

    def test_appends_project_when_no_suffix(self):
        r = ExternalCompilerProcessor._build_parallel_urn("urn:x-opensiddur:foo", "trans")
        self.assertEqual(r, "urn:x-opensiddur:foo@trans")

    def test_replaces_existing_suffix(self):
        r = ExternalCompilerProcessor._build_parallel_urn("urn:x-opensiddur:foo@orig", "trans")
        self.assertEqual(r, "urn:x-opensiddur:foo@trans")

    def test_preserves_path_components(self):
        r = ExternalCompilerProcessor._build_parallel_urn("urn:x-opensiddur:foo/bar@orig", "trans")
        self.assertEqual(r, "urn:x-opensiddur:foo/bar@trans")

    def test_hyphenated_project_name(self):
        r = ExternalCompilerProcessor._build_parallel_urn("urn:foo@original-example", "translation-example")
        self.assertEqual(r, "urn:foo@translation-example")


# ── _assemble_parallel_streams ──────────────────────────────────────────────

def assert_parallel_invariants(test, elements):
    """The two compiled-output invariants (specs/COMPILER_SPECIFICATION.md, Parallel Compilation).

    1. a p:parallel never has a p:parallel ancestor
    2. a p:parallelItem never contains an external p:transclude
    """
    for el in elements:
        for par in el.iter(f"{{{P_NS}}}parallel"):
            ancestors = [a.tag for a in par.iterancestors()]
            test.assertNotIn(
                f"{{{P_NS}}}parallel", ancestors,
                "p:parallel must never have a p:parallel ancestor")
        for item in el.iter(f"{{{P_NS}}}parallelItem"):
            nested = [
                t for t in item.iter(f"{{{P_NS}}}transclude")
                if t.get("type") in (None, "external")
            ]
            test.assertEqual(
                nested, [],
                "p:parallelItem must not contain an external p:transclude; "
                "the parallel block ends at that boundary")


class TestAssembleParallelStreams(unittest.TestCase):

    def setUp(self):
        self.ns = {"p": P_NS, "tei": TEI_NS}

    def _div(self, text="x"):
        el = etree.Element(f"{{{TEI_NS}}}div", nsmap=self.ns)
        el.text = text
        return el

    def _transclude(self, target="urn:test@orig", *children, lang=None):
        el = etree.Element(f"{{{P_NS}}}transclude", nsmap=self.ns)
        el.set("target", target)
        el.set("type", "external")
        if lang:
            el.set(f"{{{XML_NS}}}lang", lang)
        for child in (children or (self._div("inner"),)):
            el.append(child)
        return el

    def _assemble(self, prim, par, column_order="primary_first"):
        return ExternalCompilerProcessor._assemble_parallel_streams(
            prim, "he", "proj-a", "a.xml",
            par, "en", "proj-b", "b.xml",
            column_order, self.ns,
        )

    def test_no_transcludes_produces_one_parallel(self):
        result = self._assemble([self._div("p")], [self._div("q")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].tag, f"{{{P_NS}}}parallel")
        items = list(result[0])
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].get("role"), "primary")
        self.assertEqual(items[1].get("role"), "parallel")

    def test_column_order_attribute_set(self):
        result = self._assemble([self._div()], [self._div()], column_order="primary_last")
        self.assertEqual(result[0].get("column-order"), "primary_last")

    def test_xml_lang_and_project_on_parallelItem(self):
        result = self._assemble([self._div()], [self._div()])
        prim_item = list(result[0])[0]
        par_item = list(result[0])[1]
        self.assertEqual(prim_item.get(f"{{{XML_NS}}}lang"), "he")
        self.assertEqual(prim_item.get(f"{{{P_NS}}}project"), "proj-a")
        self.assertEqual(par_item.get(f"{{{XML_NS}}}lang"), "en")
        self.assertEqual(par_item.get(f"{{{P_NS}}}project"), "proj-b")

    def test_one_transclude_produces_three_elements(self):
        t1 = self._transclude("urn:t@orig")
        t2 = self._transclude("urn:t@trans")
        prim = [self._div("before"), t1, self._div("after")]
        par = [self._div("par-before"), t2, self._div("par-after")]
        result = self._assemble(prim, par)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].tag, f"{{{P_NS}}}parallel")
        self.assertEqual(result[1].tag, f"{{{P_NS}}}transclude")
        self.assertEqual(result[2].tag, f"{{{P_NS}}}parallel")

        # Inner p:parallel inside the combined p:transclude
        inner_children = list(result[1])
        self.assertEqual(len(inner_children), 1)
        inner_par = inner_children[0]
        self.assertEqual(inner_par.tag, f"{{{P_NS}}}parallel")
        inner_items = list(inner_par)
        self.assertEqual(inner_items[0].get("role"), "primary")
        self.assertEqual(inner_items[1].get("role"), "parallel")

    @staticmethod
    def _texts(element):
        return "".join(element.itertext())

    def test_transclusions_pair_by_what_they_transclude(self):
        """The parallel side transcludes one file more; nothing is dropped or mispaired."""
        prim = [self._transclude("urn:y@orig", self._div("Y-he"))]
        par = [self._transclude("urn:x@trans", self._div("X-en")),
               self._transclude("urn:y@trans", self._div("Y-en"))]
        result = self._assemble(prim, par)
        transcludes = [el for el in result if el.tag == f"{{{P_NS}}}transclude"]
        self.assertEqual([t.get("target") for t in transcludes], ["urn:x@trans", "urn:y@orig"])
        self.assertEqual(self._texts(transcludes[0]), "X-en")
        # Y's translation is beside Y, not beside nothing.
        y_items = list(transcludes[1].find(f"{{{P_NS}}}parallel"))
        self.assertEqual([self._texts(item) for item in y_items], ["Y-he", "Y-en"])

    def test_a_primary_transclusion_without_a_counterpart_is_set_alone(self):
        prim = [self._transclude("urn:x@orig", self._div("X-he")),
                self._transclude("urn:y@orig", self._div("Y-he"))]
        par = [self._transclude("urn:y@trans", self._div("Y-en"))]
        result = self._assemble(prim, par)
        transcludes = [el for el in result if el.tag == f"{{{P_NS}}}transclude"]
        self.assertEqual([self._texts(t) for t in transcludes], ["X-he", "Y-heY-en"])

    def _transcluded_texts(self, result):
        return [self._texts(el) for el in result if el.tag == f"{{{P_NS}}}transclude"]

    def test_crossed_transclusions_pair_as_many_as_keep_their_order(self):
        """[X, A, B] beside [A, B, X]: A and B pair; X is set alone on each side."""
        prim = [self._transclude(f"urn:{k}@orig", self._div(f"{k}-he")) for k in "XAB"]
        par = [self._transclude(f"urn:{k}@trans", self._div(f"{k}-en")) for k in "ABX"]
        with self.assertLogs("opensiddur.exporter.external_compiler", level="WARNING") as logs:
            result = self._assemble(prim, par)
        self.assertEqual(self._transcluded_texts(result), ["X-he", "A-heA-en", "B-heB-en", "X-en"])
        self.assertEqual(sum("no counterpart" in line for line in logs.output), 2)

    def test_unrelated_transclusions_are_not_paired_by_position(self):
        for left, right in [("urn:prayer:qedushah", "urn:prayer:eruv"),
                            ("urn:prayer:modim", "urn:prayer:modim_extra")]:
            with self.subTest(left=left, right=right):
                prim = [self._transclude(left + "@orig", self._div("Hebrew only"))]
                par = [self._transclude(right + "@trans", self._div("Other English"))]
                result = self._assemble(prim, par)
                self.assertEqual(self._transcluded_texts(result),
                                 ["Hebrew only", "Other English"])

    def test_unrelated_gaps_between_shared_transclusions_stay_separate(self):
        prim = [self._transclude("urn:" + k + "@orig", self._div(k + "-he"))
                for k in ("a", "hebrew_only", "b")]
        par = [self._transclude("urn:" + k + "@trans", self._div(k + "-en"))
               for k in ("a", "english_only", "b")]
        result = self._assemble(prim, par)
        self.assertEqual(self._transcluded_texts(result),
                         ["a-hea-en", "hebrew_only-he", "english_only-en", "b-heb-en"])

    def test_the_same_text_at_different_granularity_still_pairs(self):
        """A chapter beside its first verse: their ancestor relationship allows pairing."""
        prim = [self._transclude("urn:x/1/1@orig", self._div("verse-he"))]
        par = [self._transclude("urn:x/1@trans", self._div("chapter-en"))]
        result = self._assemble(prim, par)
        self.assertEqual(self._transcluded_texts(result), ["verse-hechapter-en"])

    def test_an_empty_type_ends_a_parallel_block(self):
        """type="" is external, so the transclusion is a block boundary like any other."""
        prim = [self._div("before"), self._transclude("urn:t@orig"), self._div("after")]
        par = [self._div("vor"), self._transclude("urn:t@trans"), self._div("nach")]
        for transclusion in (prim[1], par[1]):
            transclusion.set("type", "")
        result = self._assemble(prim, par)
        self.assertEqual([el.tag for el in result],
                         [f"{{{P_NS}}}parallel", f"{{{P_NS}}}transclude", f"{{{P_NS}}}parallel"])

    def test_a_repeated_alignment_key_is_reported(self):
        def verse(urn):
            milestone = etree.Element(f"{{{TEI_NS}}}milestone", nsmap=self.ns)
            milestone.set("unit", "verse")
            milestone.set("corresp", urn)
            return milestone
        one = "urn:x-opensiddur:text:t/1"
        prim = [verse(one), self._div("one"), verse(one), self._div("again")]
        par = [verse(one), self._div("eins")]
        with self.assertLogs("opensiddur.exporter.external_compiler", level="WARNING") as logs:
            self._assemble(prim, par)
        self.assertIn("more than once", "".join(logs.output))

    def test_nested_transclude_is_hoisted_not_embedded(self):
        """A transclude inside a transclude ends the inner block too, at every depth.

        Regression: the boundary rebuild used to call make_rows directly, so a nested
        p:transclude landed as a direct child of a p:parallelItem and its parallels ended up
        nested inside the outer ones.
        """
        prim_inner = self._transclude("urn:inner@orig", self._div("deep"))
        par_inner = self._transclude("urn:inner@trans", self._div("deep-par"))
        prim_outer = self._transclude(
            "urn:outer@orig", self._div("a"), prim_inner, self._div("b"))
        par_outer = self._transclude(
            "urn:outer@trans", self._div("pa"), par_inner, self._div("pb"))

        result = self._assemble([prim_outer], [par_outer])

        assert_parallel_invariants(self, result)
        outer = result[0]
        self.assertEqual(outer.tag, f"{{{P_NS}}}transclude")
        self.assertEqual(
            [etree.QName(c).localname for c in outer],
            ["parallel", "transclude", "parallel"])
        inner = list(outer)[1]
        self.assertTrue(all(c.tag == f"{{{P_NS}}}parallel" for c in inner))

    def test_three_level_nesting_keeps_invariants(self):
        prim = self._transclude("urn:1@o", self._transclude(
            "urn:2@o", self._transclude("urn:3@o", self._div("deep"))))
        par = self._transclude("urn:1@t", self._transclude(
            "urn:2@t", self._transclude("urn:3@t", self._div("deep-par"))))

        result = self._assemble([prim], [par])

        assert_parallel_invariants(self, result)
        depth = len(result[0].findall(f".//{{{P_NS}}}transclude")) + 1
        self.assertEqual(depth, 3)

    def test_nested_transclude_only_in_primary(self):
        """An inner transclude with no parallel counterpart still yields a well-formed row."""
        prim = self._transclude(
            "urn:outer@orig", self._div("a"), self._transclude("urn:inner@orig"))
        par = self._transclude("urn:outer@trans", self._div("pa"))

        result = self._assemble([prim], [par])

        assert_parallel_invariants(self, result)
        for par_el in result[0].iter(f"{{{P_NS}}}parallel"):
            self.assertEqual(len(list(par_el)), 2)

    def test_nested_transclude_language_override_propagates(self):
        """Regression (#p856): a nested transclude into a different-language document must
        stamp its own p:parallelItem with that document's language, not the outer stream's.

        The Ki Tisa haftarah (Hebrew humash) transcludes 1 Kings 8 from the jps1917 English
        translation; the resulting p:parallelItem kept the outer xml:lang="he", so
        reledmac.xslt wrapped the genuinely-English text in \\begin{hebrew}, and pdfTeX's
        \\textdir primitive mirrored it (backwards English on the printed page).
        """
        prim_inner = self._transclude("urn:inner@orig", self._div("english text"), lang="en")
        par_inner = self._transclude("urn:inner@trans", self._div("hebrew parallel"), lang="he")
        prim_outer = self._transclude("urn:outer@orig", self._div("a"), prim_inner)
        par_outer = self._transclude("urn:outer@trans", self._div("pa"), par_inner)

        result = self._assemble([prim_outer], [par_outer])

        outer = result[0]
        inner_transclude = [c for c in outer if etree.QName(c).localname == "transclude"][0]
        inner_parallel = list(inner_transclude)[0]
        prim_item, par_item = list(inner_parallel)
        self.assertEqual(prim_item.get(f"{{{XML_NS}}}lang"), "en")
        self.assertEqual(par_item.get(f"{{{XML_NS}}}lang"), "he")

    def test_nested_transclude_without_lang_override_inherits_outer_language(self):
        """A nested transclude that doesn't declare its own xml:lang keeps the outer language."""
        prim_inner = self._transclude("urn:inner@orig", self._div("deep"))
        par_inner = self._transclude("urn:inner@trans", self._div("deep-par"))
        prim_outer = self._transclude("urn:outer@orig", self._div("a"), prim_inner)
        par_outer = self._transclude("urn:outer@trans", self._div("pa"), par_inner)

        result = self._assemble([prim_outer], [par_outer])

        outer = result[0]
        inner_transclude = [c for c in outer if etree.QName(c).localname == "transclude"][0]
        inner_parallel = list(inner_transclude)[0]
        prim_item, par_item = list(inner_parallel)
        self.assertEqual(prim_item.get(f"{{{XML_NS}}}lang"), "he")
        self.assertEqual(par_item.get(f"{{{XML_NS}}}lang"), "en")

    def test_milestone_alignment_survives_inside_nested_transclude(self):
        def _ms(corresp):
            el = etree.Element(f"{{{TEI_NS}}}milestone", nsmap=self.ns)
            el.set("corresp", corresp)
            el.set("unit", "verse")
            return el

        prim = self._transclude(
            "urn:o@orig", _ms("urn:v:1"), self._div("v1"), _ms("urn:v:2"), self._div("v2"))
        par = self._transclude(
            "urn:o@trans", _ms("urn:v:1"), self._div("t1"), _ms("urn:v:2"), self._div("t2"))

        result = self._assemble([prim], [par])

        assert_parallel_invariants(self, result)
        rows = list(result[0].iter(f"{{{P_NS}}}parallel"))
        self.assertGreaterEqual(len(rows), 2)
        for row in rows:
            items = list(row)
            self.assertEqual([i.get("role") for i in items], ["primary", "parallel"])

    def _milestone(self, corresp, unit="verse"):
        el = etree.Element(f"{{{TEI_NS}}}milestone", nsmap=self.ns)
        el.set("corresp", corresp)
        el.set("unit", unit)
        return el

    def _rows_by_corresp(self, result):
        """The corresp each parallel row is keyed on, with its two columns' text."""
        rows = []
        for row in result[0].iter(f"{{{P_NS}}}parallel") if result else []:
            items = list(row)
            texts = ["".join(item.itertext()) for item in items]
            rows.append(texts)
        return rows

    def test_half_verses_fold_into_the_verse_the_other_side_has(self):
        """The Hebrew divides at its accents; a translation cannot, and must not lose its
        text to an empty row because of it."""
        prim = self._transclude(
            "urn:o@orig",
            self._milestone("urn:v/1"),
            self._milestone("urn:v/1/a", unit="half-verse"),
            self._div("first-half"),
            self._milestone("urn:v/1/b", unit="half-verse"),
            self._div("second-half"),
        )
        par = self._transclude(
            "urn:o@trans", self._milestone("urn:v/1"), self._div("whole-verse"))

        result = self._assemble([prim], [par])

        assert_parallel_invariants(self, result)
        rows = self._rows_by_corresp(result)
        # One row for the verse, with both halves of the Hebrew against the whole English.
        self.assertEqual(len(rows), 1, rows)
        primary_text, parallel_text = rows[0]
        self.assertIn("first-half", primary_text)
        self.assertIn("second-half", primary_text)
        self.assertIn("whole-verse", parallel_text)

    def test_folding_happens_in_both_directions(self):
        """Whichever side is divided more finely is the one that folds."""
        prim = self._transclude(
            "urn:o@orig", self._milestone("urn:v/1"), self._div("whole-verse"))
        par = self._transclude(
            "urn:o@trans",
            self._milestone("urn:v/1"),
            self._milestone("urn:v/1/a", unit="half-verse"),
            self._div("first-half"),
            self._milestone("urn:v/1/b", unit="half-verse"),
            self._div("second-half"),
        )

        result = self._assemble([prim], [par])

        rows = self._rows_by_corresp(result)
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("whole-verse", rows[0][0])
        self.assertIn("first-half", rows[0][1])
        self.assertIn("second-half", rows[0][1])

    def test_both_sides_divided_alike_still_align_at_the_finer_division(self):
        """Folding is a fallback, not a ceiling: matching halves keep their own rows."""
        def stream(prefix):
            return self._transclude(
                f"urn:o@{prefix}",
                self._milestone("urn:v/1"),
                self._milestone("urn:v/1/a", unit="half-verse"),
                self._div(f"{prefix}-a"),
                self._milestone("urn:v/1/b", unit="half-verse"),
                self._div(f"{prefix}-b"),
            )

        result = self._assemble([stream("orig")], [stream("trans")])

        rows = self._rows_by_corresp(result)
        self.assertEqual(len(rows), 3, rows)  # the verse milestone, then each half
        self.assertIn("orig-a", rows[1][0])
        self.assertIn("trans-a", rows[1][1])
        self.assertIn("orig-b", rows[2][0])
        self.assertIn("trans-b", rows[2][1])

    def test_a_verse_the_other_side_does_not_subdivide_stays_in_one_piece(self):
        """Folding must happen before the split, not after it.

        Every split suspends the structure open across it and resumes it on the far side.
        Splitting at a half-verse and merging the rows afterwards would leave those carriers
        behind, breaking the verse into three pieces inside its own row.
        """
        prim = self._transclude(
            "urn:o@orig",
            self._milestone("urn:v/1"),
            self._milestone("urn:v/1/a", unit="half-verse"),
            self._div("first-half"),
            self._milestone("urn:v/1/b", unit="half-verse"),
            self._div("second-half"),
        )
        par = self._transclude(
            "urn:o@trans", self._milestone("urn:v/1"), self._div("whole-verse"))

        result = self._assemble([prim], [par])

        primary = list(result[0].iter(f"{{{P_NS}}}parallel"))[0][0]
        self.assertEqual(
            [el.get(f"{{{P_NS}}}suspend") for el in primary.iter()
             if el.get(f"{{{P_NS}}}suspend")],
            [],
            "the half-verses should not have suspended anything",
        )

    def _assert_no_half_empty_row(self, rows):
        """Both sides had content, so no row may face an empty cell."""
        for i, (primary_text, parallel_text) in enumerate(rows):
            self.assertTrue(primary_text.strip(), f"row {i} has an empty primary: {rows}")
            self.assertTrue(parallel_text.strip(), f"row {i} has an empty parallel: {rows}")

    def test_a_division_the_other_side_does_not_mark_is_not_a_row_boundary(self):
        """Folding only ever moves text onto a URN both sides actually mark.

        Neither of these URNs is one, so neither is a boundary: the two texts are set
        against each other whole, which is the only correspondence declared.
        """
        prim = self._transclude(
            "urn:o@orig", self._milestone("urn:v/9/a", unit="half-verse"), self._div("orphan"))
        par = self._transclude(
            "urn:o@trans", self._milestone("urn:v/1"), self._div("elsewhere"))

        result = self._assemble([prim], [par])

        rows = self._rows_by_corresp(result)
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("orphan", rows[0][0])
        self.assertIn("elsewhere", rows[0][1])

    def test_disjoint_milestone_sets_produce_one_row_with_both_columns(self):
        """The Heidenheim Psalm 126 shape: the two sides divide on different URN axes.

        The Hebrew is divided by biblical chapter and verse, the translation by haggadah
        paragraph. Nothing is shared, so promoting either side's URNs to boundaries set the
        whole psalm in rows facing nothing and printed the translation below the Hebrew
        instead of beside it.
        """
        prim = self._transclude(
            "urn:o@orig",
            self._milestone("urn:x-opensiddur:text:bible:psalms/126", unit="chapter"),
            self._milestone("urn:x-opensiddur:text:bible:psalms/126/1"),
            self._div("hebrew-one"),
            self._milestone("urn:x-opensiddur:text:bible:psalms/126/2"),
            self._div("hebrew-two"),
            self._milestone("urn:x-opensiddur:text:bible:psalms/126/3"),
            self._div("hebrew-three"),
        )
        par = self._transclude(
            "urn:o@trans",
            self._milestone(
                "urn:x-opensiddur:text:haggadah:barech/psalm_126/1", unit="paragraph"),
            self._div("the whole translation"),
        )

        result = self._assemble([prim], [par])

        assert_parallel_invariants(self, result)
        rows = self._rows_by_corresp(result)
        self.assertEqual(len(rows), 1, rows)
        self._assert_no_half_empty_row(rows)
        for verse in ("hebrew-one", "hebrew-two", "hebrew-three"):
            self.assertIn(verse, rows[0][0])
        self.assertIn("the whole translation", rows[0][1])

    def test_a_side_with_no_milestones_at_all_pairs_with_the_whole_other_side(self):
        """An undivided translation faces the whole of what it translates."""
        prim = self._transclude(
            "urn:o@orig",
            self._milestone("urn:v/1"), self._div("one"),
            self._milestone("urn:v/2"), self._div("two"),
            self._milestone("urn:v/3"), self._div("three"),
        )
        par = self._transclude("urn:o@trans", self._div("undivided"))

        result = self._assemble([prim], [par])

        rows = self._rows_by_corresp(result)
        self.assertEqual(len(rows), 1, rows)
        self._assert_no_half_empty_row(rows)
        self.assertIn("undivided", rows[0][1])

    def test_a_one_sided_division_folds_inline_rather_than_trailing(self):
        """The jps1917 parsha shape: one side marks a division the other has no notion of.

        Parallel-only keys were ordered after every primary key, so such a milestone did not
        merely get a row of its own — it got it at the end of the book.
        """
        prim = self._transclude(
            "urn:o@orig",
            self._milestone("urn:b/1"), self._div("orig-one"),
            self._milestone("urn:b/2"), self._div("orig-two"),
        )
        par = self._transclude(
            "urn:o@trans",
            self._milestone("urn:b/1"), self._div("trans-one"),
            self._milestone("urn:b/bereshit", unit="parsha"), self._div("parsha-text"),
            self._milestone("urn:b/2"), self._div("trans-two"),
        )

        result = self._assemble([prim], [par])

        assert_parallel_invariants(self, result)
        rows = self._rows_by_corresp(result)
        self.assertEqual(len(rows), 2, rows)
        self._assert_no_half_empty_row(rows)
        # The parsha text stays in the row of the shared division it falls under, and the
        # last row is still the last shared division — nothing trails the text.
        self.assertIn("parsha-text", rows[0][1])
        self.assertIn("orig-two", rows[1][0])
        self.assertIn("trans-two", rows[1][1])

    def test_a_preamble_on_only_the_parallel_side_stays_first(self):
        """Leading text belongs at the top of the block, not after every row of it."""
        prim = self._transclude(
            "urn:o@orig",
            self._milestone("urn:v/1"), self._div("orig-one"),
            self._milestone("urn:v/2"), self._div("orig-two"),
        )
        par = self._transclude(
            "urn:o@trans",
            self._div("leading-translation"),
            self._milestone("urn:v/1"), self._div("trans-one"),
            self._milestone("urn:v/2"), self._div("trans-two"),
        )

        result = self._assemble([prim], [par])

        rows = self._rows_by_corresp(result)
        self.assertIn("leading-translation", rows[0][1], rows)
        self.assertIn("trans-two", rows[-1][1], rows)

    def test_disjoint_divisions_are_reported(self):
        """The fold is right, but the encoding that forced it is worth naming."""
        prim = self._transclude(
            "urn:o@orig", self._milestone("urn:bible:psalms/126/1"), self._div("hebrew"))
        par = self._transclude(
            "urn:o@trans",
            self._milestone("urn:haggadah:barech/psalm_126/1"), self._div("english"))

        with self.assertLogs(
                "opensiddur.exporter.external_compiler", level="WARNING") as logged:
            self._assemble([prim], [par])

        message = "\n".join(logged.output)
        self.assertIn("a.xml", message)
        self.assertIn("b.xml", message)

    def test_a_shared_division_is_not_reported(self):
        """The warning names a real encoding gap, so it must not cry wolf."""
        prim = self._transclude(
            "urn:o@orig", self._milestone("urn:v/1"), self._div("hebrew"))
        par = self._transclude(
            "urn:o@trans", self._milestone("urn:v/1"), self._div("english"))

        with self.assertNoLogs(
                "opensiddur.exporter.external_compiler", level="WARNING"):
            self._assemble([prim], [par])

    def test_an_undivided_side_is_not_reported(self):
        """Unsegmented prose is not a mismatch of axes."""
        prim = self._transclude(
            "urn:o@orig", self._milestone("urn:v/1"), self._div("hebrew"))
        par = self._transclude("urn:o@trans", self._div("english"))

        with self.assertNoLogs(
                "opensiddur.exporter.external_compiler", level="WARNING"):
            self._assemble([prim], [par])

    def _bounded_stream(self, prefix, corresp="urn:insertion", rubric=False):
        before = self._div(prefix + " before")
        start = etree.Element(f"{{{TEI_NS}}}div", corresp=corresp)
        start.set(f"{{{P_NS}}}start", prefix + "-insertion")
        end = etree.Element(f"{{{TEI_NS}}}div")
        end.set(f"{{{P_NS}}}end", prefix + "-insertion")
        end.tail = prefix + " continuation"
        stream = [before]
        if rubric:
            condition = etree.Element(f"{{{J_NS}}}conditional")
            instruction = etree.SubElement(condition, f"{{{TEI_NS}}}note", type="instruction")
            instruction.text = prefix + " rubric"
            stream.append(condition)
        stream.extend([start, self._div(prefix + " insertion"), end])
        return stream

    def test_bounded_correspondences_align_insertion_and_continuation(self):
        result = self._assemble(self._bounded_stream("he"), self._bounded_stream("en"))
        rows = [["".join(item.itertext()) for item in row] for row in result]
        self.assertEqual(rows, [
            ["he before", "en before"],
            ["he insertion", "en insertion"],
            ["he continuation", "en continuation"],
        ])
        assert_parallel_invariants(self, result)
        insertion = result[1][0]
        self.assertEqual(insertion[-1].get(f"{{{P_NS}}}suspend"), "he-insertion")
        continuation = result[2][0]
        self.assertEqual(continuation[0].get(f"{{{P_NS}}}resume"), "he-insertion")

    def test_conditional_rubric_follows_its_structural_alignment_boundary(self):
        result = self._assemble(
            self._bounded_stream("he", rubric=True), self._bounded_stream("en", rubric=True))
        rows = [["".join(item.itertext()) for item in row] for row in result]
        self.assertEqual(rows[0], ["he before", "en before"])
        self.assertEqual(rows[1], ["he rubriche insertion",
                                  "en rubricen insertion"])

    def test_structural_correspondence_can_align_with_a_milestone(self):
        result = self._assemble(
            self._bounded_stream("he"),
            [self._div("en before"), self._milestone("urn:insertion"),
             self._div("en insertion and continuation")])
        rows = [["".join(item.itertext()) for item in row] for row in result]
        self.assertEqual(rows, [
            ["he before", "en before"],
            ["he insertionhe continuation", "en insertion and continuation"],
        ])

    def test_nested_structural_correspondences_preserve_all_text(self):
        def stream(prefix):
            start = etree.Element(f"{{{TEI_NS}}}div", corresp="urn:outer")
            start.set(f"{{{P_NS}}}start", prefix + "-outer")
            end = etree.Element(f"{{{TEI_NS}}}div")
            end.set(f"{{{P_NS}}}end", prefix + "-outer")
            end.tail = prefix + " outside"
            return [start, *self._bounded_stream(prefix), end]

        result = self._assemble(stream("he"), stream("en"))
        rows = [["".join(item.itertext()) for item in row] for row in result]
        self.assertEqual(rows, [
            ["he before", "en before"],
            ["he insertion", "en insertion"],
            ["he continuation", "en continuation"],
            ["he outside", "en outside"],
        ])

    def test_unshared_bounded_correspondence_does_not_split(self):
        result = self._assemble(
            self._bounded_stream("he"), self._bounded_stream("en", corresp="urn:different"))
        self.assertEqual(len(result), 1)
        self.assertIn("he continuation", "".join(result[0][0].itertext()))
        self.assertIn("en insertion", "".join(result[0][1].itertext()))

    def test_mismatched_transclude_counts(self):
        t1 = self._transclude()
        prim = [self._div("a"), t1, self._div("b")]  # 1 transclude
        par = [self._div("c")]                        # 0 transcludes
        # Should not raise
        result = self._assemble(prim, par)
        self.assertGreaterEqual(len(result), 2)
        tags = [el.tag for el in result]
        self.assertIn(f"{{{P_NS}}}parallel", tags)


# ── Base for tests that need a real processor ───────────────────────────────

class _ProcessorBase(unittest.TestCase):

    def setUp(self):
        reset_linear_data()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.project = "test-proj"
        proj_dir = Path(self.temp_dir.name) / self.project
        proj_dir.mkdir(parents=True)
        (proj_dir / "index.xml").write_bytes(_MINIMAL_TEI)

        self.linear_data = get_linear_data()
        self.linear_data.xml_cache.base_path = Path(self.temp_dir.name)

    def _make_processor(self, in_parallel_compilation=False):
        # Suppression is ambient on LinearData, not a processor kwarg, so that nested
        # processors inherit it.
        self.linear_data.parallel_compilation_depth = 1 if in_parallel_compilation else 0
        return ExternalCompilerProcessor(
            self.project, "index.xml",
            linear_data=self.linear_data,
        )


# ── _shared_split_points ────────────────────────────────────────────────────

class TestSharedSplitPoints(unittest.TestCase):

    def test_is_symmetric(self):
        """Both streams are cut at one key set, so the argument order cannot matter."""
        a = {"urn:v/1", "urn:v/1/a", "urn:v/2"}
        b = {"urn:v/1", "urn:v/3"}
        self.assertEqual(_shared_split_points(a, b), _shared_split_points(b, a))

    def test_keeps_what_both_sides_mark(self):
        self.assertEqual(
            _shared_split_points({"urn:v/1", "urn:v/2"}, {"urn:v/2", "urn:v/3"}),
            {"urn:v/2"},
        )

    def test_is_empty_when_the_sets_are_disjoint(self):
        """The Psalm 126 case: nothing shared, so nothing is a boundary."""
        self.assertEqual(
            _shared_split_points(
                {"urn:x-opensiddur:text:bible:psalms/126/1"},
                {"urn:x-opensiddur:text:haggadah:barech/psalm_126/1"},
            ),
            set(),
        )

    def test_a_containing_division_is_not_a_boundary_unless_marked(self):
        """Containment is not marking: `urn:v` divides nothing this side declared."""
        self.assertEqual(_shared_split_points({"urn:v/1"}, {"urn:v"}), set())

    def test_an_undivided_side_shares_nothing(self):
        self.assertEqual(_shared_split_points({"urn:v/1", "urn:v/2"}, set()), set())


# ── _split_at_milestones ────────────────────────────────────────────────────

class TestSplitAtMilestones(unittest.TestCase):

    def setUp(self):
        self.ns = {"p": P_NS, "tei": TEI_NS}

    def _ms(self, corresp, tail=None):
        el = etree.Element(f"{{{TEI_NS}}}milestone", nsmap=self.ns)
        el.set("unit", "verse")
        el.set("corresp", corresp)
        if tail:
            el.tail = tail
        return el

    def _start(self, tag, p_id):
        el = etree.Element(f"{{{TEI_NS}}}{tag}", nsmap=self.ns)
        el.set(f"{{{P_NS}}}start", p_id)
        return el

    def _end(self, tag, p_id):
        el = etree.Element(f"{{{TEI_NS}}}{tag}", nsmap=self.ns)
        el.set(f"{{{P_NS}}}end", p_id)
        return el

    def _split(self, elements):
        return ExternalCompilerProcessor._split_at_milestones(elements, self.ns)

    def test_no_milestones_returns_single_preamble(self):
        div = etree.Element(f"{{{TEI_NS}}}div", nsmap=self.ns)
        result = self._split([div])
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0][0])
        self.assertEqual(len(result[0][1]), 1)

    def test_empty_input_returns_single_empty_preamble(self):
        result = self._split([])
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0][0])

    def test_one_milestone_splits_into_milestone_sub_segment(self):
        result = self._split([self._ms("urn:x-test:1")])
        corresps = [c for c, _ in result]
        self.assertIn("urn:x-test:1", corresps)
        # Empty preamble is filtered out
        self.assertNotIn(None, corresps)

    def test_milestone_in_preamble_creates_split(self):
        """Milestones always start a new sub-segment."""
        elements = [
            self._start("p", "p1"),
            self._ms("urn:x-test:1", "verse 1 text"),
            self._ms("urn:x-test:2", "verse 2 text"),
            self._end("p", "p1"),
        ]
        result = self._split(elements)
        corresps = [c for c, _ in result]
        self.assertIn("urn:x-test:1", corresps)
        self.assertIn("urn:x-test:2", corresps)

    def test_open_elements_get_suspend_and_resume(self):
        """Elements open at a milestone boundary get suspend/resume markers."""
        elements = [
            self._start("div", "d1"),
            self._start("p", "p1"),
            self._ms("urn:x-test:1"),
            self._end("p", "p1"),
            self._end("div", "d1"),
        ]
        result = self._split(elements)
        # preamble should have d1 and p1 suspends (LIFO: p1 first, then d1)
        preamble_els = result[0][1]
        suspend_ids = [el.get(f"{{{P_NS}}}suspend") for el in preamble_els if el.get(f"{{{P_NS}}}suspend")]
        self.assertEqual(suspend_ids, ["p1", "d1"])  # LIFO

        # milestone sub-segment should have d1 and p1 resumes (FIFO: d1 first, then p1)
        ms_els = result[1][1]
        resume_ids = [el.get(f"{{{P_NS}}}resume") for el in ms_els if el.get(f"{{{P_NS}}}resume")]
        self.assertEqual(resume_ids, ["d1", "p1"])  # FIFO

    def test_milestone_tail_preserved(self):
        elements = [self._ms("urn:x-test:1", "verse text")]
        result = self._split(elements)
        ms_sub = next(els for c, els in result if c == "urn:x-test:1")
        milestone = next(el for el in ms_sub if el.tag == f"{{{TEI_NS}}}milestone")
        self.assertEqual(milestone.tail, "verse text")

    def test_multiple_milestones_each_get_own_sub_segment(self):
        elements = [
            self._ms("urn:x-test:1", "v1"),
            self._ms("urn:x-test:2", "v2"),
            self._ms("urn:x-test:3", "v3"),
        ]
        result = self._split(elements)
        corresps = [c for c, _ in result if c is not None]
        self.assertEqual(corresps, ["urn:x-test:1", "urn:x-test:2", "urn:x-test:3"])

    def test_p_resume_pushed_to_open_stack(self):
        """p:resume markers are treated as element-open for milestone splitting."""
        resume = etree.Element(f"{{{TEI_NS}}}div", nsmap=self.ns)
        resume.set(f"{{{P_NS}}}resume", "d1")
        ms = self._ms("urn:x-test:1")
        end = etree.Element(f"{{{TEI_NS}}}div", nsmap=self.ns)
        end.set(f"{{{P_NS}}}end", "d1")

        result = self._split([resume, ms, end])
        preamble_els = result[0][1]
        suspend_ids = [el.get(f"{{{P_NS}}}suspend") for el in preamble_els if el.get(f"{{{P_NS}}}suspend")]
        self.assertIn("d1", suspend_ids)


# ── _process_element_as_marker ──────────────────────────────────────────────

class TestProcessElementAsMarker(_ProcessorBase):

    def _push_context(self, proc):
        """Push a minimal processing context so _get_path_hash works."""
        proc.linear_data.processing_context.append(_ProcessingContext(
            project=proc.project,
            file_name=proc.file_name,
            element_path=None,
            from_start=None,
            to_end=None,
            before_start=False,
            after_end=False,
            include_tail_after_end=False,
            inside_deepest_common_ancestor=False,
            command=_ProcessingCommand.COPY_AND_RECURSE,
        ))

    def _pop_context(self, proc):
        proc.linear_data.processing_context.pop()

    def test_text_becomes_start_marker_tail(self):
        proc = self._make_processor()
        proc.marker_stack = []
        self._push_context(proc)
        try:
            tei_p = etree.Element(f"{{{TEI_NS}}}p")
            tei_p.text = "before text"
            tei_p.tail = "after tail"
            result = proc._process_element_as_marker(tei_p)
        finally:
            self._pop_context(proc)

        self.assertGreater(len(result), 0)
        start_marker = result[0]
        self.assertEqual(start_marker.get(f"{{{P_NS}}}start") is not None, True)
        self.assertEqual(start_marker.tail, "before text")

    def test_tail_becomes_end_marker_tail(self):
        proc = self._make_processor()
        proc.marker_stack = []
        self._push_context(proc)
        try:
            tei_p = etree.Element(f"{{{TEI_NS}}}p")
            tei_p.text = "text"
            tei_p.tail = " after element"
            result = proc._process_element_as_marker(tei_p)
        finally:
            self._pop_context(proc)

        end_marker = result[-1]
        self.assertIsNotNone(end_marker.get(f"{{{P_NS}}}end"))
        self.assertEqual(end_marker.tail, " after element")

    def test_start_and_end_markers_same_id(self):
        proc = self._make_processor()
        proc.marker_stack = []
        self._push_context(proc)
        try:
            tei_p = etree.Element(f"{{{TEI_NS}}}p")
            result = proc._process_element_as_marker(tei_p)
        finally:
            self._pop_context(proc)

        start_id = result[0].get(f"{{{P_NS}}}start")
        end_id = result[-1].get(f"{{{P_NS}}}end")
        self.assertIsNotNone(start_id)
        self.assertEqual(start_id, end_id)

    def test_milestone_child_preserved_in_output(self):
        proc = self._make_processor()
        proc.marker_stack = []
        self._push_context(proc)
        try:
            tei_p = etree.Element(f"{{{TEI_NS}}}p")
            ms = etree.SubElement(tei_p, f"{{{TEI_NS}}}milestone")
            ms.set("unit", "verse")
            ms.set("n", "1")
            ms.tail = "verse text"
            result = proc._process_element_as_marker(tei_p)
        finally:
            self._pop_context(proc)

        # Should be: [start_marker, milestone, end_marker]
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1].tag, f"{{{TEI_NS}}}milestone")
        self.assertEqual(result[1].get("unit"), "verse")
        self.assertIn("verse text", result[1].tail or "")

    def test_external_transclude_child_produces_suspend_and_resume(self):
        proc = self._make_processor()
        proc.marker_stack = []
        self._push_context(proc)
        try:
            tei_p = etree.Element(f"{{{TEI_NS}}}p")
            transclude = etree.SubElement(tei_p, f"{{{J_NS}}}transclude")
            transclude.set("type", "external")
            transclude.set("target", "urn:x-test:nonexistent")
            transclude.tail = " post-transclude"
            # Mock _transclude to return None (unresolvable URN fallback)
            with patch.object(proc, "_transclude", return_value=None):
                result = proc._process_element_as_marker(tei_p)
        finally:
            self._pop_context(proc)

        p_start_markers = [el for el in result if el.get(f"{{{P_NS}}}start")]
        p_suspend_markers = [el for el in result if el.get(f"{{{P_NS}}}suspend")]
        p_resume_markers = [el for el in result if el.get(f"{{{P_NS}}}resume")]
        p_end_markers = [el for el in result if el.get(f"{{{P_NS}}}end")]

        self.assertEqual(len(p_start_markers), 1)
        self.assertEqual(len(p_suspend_markers), 1)
        self.assertEqual(len(p_resume_markers), 1)
        self.assertEqual(len(p_end_markers), 1)

        # All markers use the same element tag (tei:p)
        for marker in p_start_markers + p_suspend_markers + p_resume_markers + p_end_markers:
            self.assertEqual(marker.tag, f"{{{TEI_NS}}}p")

    def test_hash_reproducible_for_same_element(self):
        proc = self._make_processor()
        proc.marker_stack = []
        self._push_context(proc)
        try:
            tei_p = etree.fromstring(b'<tei:p xmlns:tei="http://www.tei-c.org/ns/1.0">text</tei:p>')
            result1 = proc._process_element_as_marker(tei_p)
            proc.marker_stack = []  # reset for second call
            result2 = proc._process_element_as_marker(tei_p)
        finally:
            self._pop_context(proc)

        id1 = result1[0].get(f"{{{P_NS}}}start")
        id2 = result2[0].get(f"{{{P_NS}}}start")
        self.assertEqual(id1, id2)

    def test_nested_structural_element_gets_own_markers(self):
        proc = self._make_processor()
        proc.marker_stack = []
        self._push_context(proc)
        try:
            outer = etree.fromstring(
                b'<tei:div xmlns:tei="http://www.tei-c.org/ns/1.0"'
                b'         xmlns:j="http://jewishliturgy.org/ns/jlptei/2">'
                b'  <j:transclude type="external" target="urn:x-test:nope"/>'
                b'</tei:div>')
            # Mock _transclude to avoid URN resolution failure
            with patch.object(proc, "_transclude", return_value=None):
                result = proc._process_element_as_marker(outer)
        finally:
            self._pop_context(proc)

        # outer div markers
        div_starts = [el for el in result if el.tag == f"{{{TEI_NS}}}div" and el.get(f"{{{P_NS}}}start")]
        div_ends = [el for el in result if el.tag == f"{{{TEI_NS}}}div" and el.get(f"{{{P_NS}}}end")]
        self.assertEqual(len(div_starts), 1)
        self.assertEqual(len(div_ends), 1)

    def test_comment_child_is_dropped_and_its_tail_kept(self):
        """A comment in marker mode is dropped; the text after it is document text (#41)."""
        proc = self._make_processor()
        proc.marker_stack = []
        self._push_context(proc)
        try:
            tei_p = etree.fromstring(
                b'<tei:p xmlns:tei="http://www.tei-c.org/ns/1.0">'
                b'text<!-- an editorial remark --> after comment</tei:p>')
            result = proc._process_element_as_marker(tei_p)
        finally:
            self._pop_context(proc)

        serialized = ''.join(etree.tostring(el, encoding='unicode') for el in result)
        self.assertNotIn('an editorial remark', serialized)
        self.assertIn(' after comment', ''.join(el.tail or '' for el in result))


# ── parallel-compilation suppression ────────────────────────────────────────

class TestParallelCompilationFlag(_ProcessorBase):

    def test_in_parallel_compilation_suppresses_root_trigger(self):
        """A non-zero parallel_compilation_depth means process() skips _process_parallel_root."""
        self.linear_data.parallel_projects = ["some-proj"]
        proc = self._make_processor(in_parallel_compilation=True)

        with patch.object(proc, "_process_parallel_root") as mock_root:
            proc.process()
            mock_root.assert_not_called()

    def test_in_parallel_compilation_false_triggers_root(self):
        """At depth 0, parallel_projects causes _process_parallel_root to be called."""
        self.linear_data.parallel_projects = ["some-proj"]
        proc = self._make_processor(in_parallel_compilation=False)

        with patch.object(proc, "_process_parallel_root", return_value=[]) as mock_root:
            proc.process()
            mock_root.assert_called_once()

    def test_root_returning_none_falls_through_to_normal_compilation(self):
        """No root counterpart must not abort parallel processing, only defer it.

        Returning None leaves parallel_compilation_depth at 0 so that each transclusion
        pairs itself; swallowing it here would drop the parallel column entirely.
        """
        self.linear_data.parallel_projects = ["some-proj"]
        proc = self._make_processor(in_parallel_compilation=False)

        with patch.object(proc, "_process_parallel_root", return_value=None) as mock_root:
            result = proc.process()
            mock_root.assert_called_once()

        self.assertEqual(self.linear_data.parallel_compilation_depth, 0)
        self.assertTrue(result, "compilation must still produce output")

    def test_structural_elements_always_get_markers_in_marker_mode(self):
        """In marker mode, all structural elements get start/end marker pairs."""
        proc = self._make_processor(in_parallel_compilation=True)
        proc.marker_stack = []
        self.linear_data.parallel_projects = ["par-proj"]

        result = proc.process()

        result_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        self.assertIn(":start=", result_xml)


class TestParallelCompilationDepth(_ProcessorBase):
    """Suppression must be ambient, so processors constructed anywhere inherit it."""

    def test_nested_processor_inherits_suppression(self):
        """A processor built without any parallel kwarg still sees the ambient depth.

        Regression: the old per-instance flag was dropped by every nested construction site,
        so a sub-compilation's own transclusions re-triggered parallel processing.
        """
        self.linear_data.parallel_compilation_depth = 0
        outer = self._make_processor()
        self.assertFalse(outer._in_parallel_compilation)

        with outer._parallel_sub_compilation():
            self.assertTrue(outer._in_parallel_compilation)
            nested = ExternalCompilerProcessor(
                self.project, "index.xml", linear_data=self.linear_data)
            self.assertTrue(
                nested._in_parallel_compilation,
                "a nested processor must inherit parallel suppression")

        self.assertFalse(outer._in_parallel_compilation)

    def test_depth_is_restored_when_sub_compilation_raises(self):
        """_process_parallel_root swallows sub-compilation errors; depth must not leak."""
        proc = self._make_processor()
        self.assertEqual(self.linear_data.parallel_compilation_depth, 0)

        with self.assertRaises(RuntimeError):
            with proc._parallel_sub_compilation():
                raise RuntimeError("boom")

        self.assertEqual(self.linear_data.parallel_compilation_depth, 0)

    def test_depth_nests(self):
        proc = self._make_processor()
        with proc._parallel_sub_compilation():
            with proc._parallel_sub_compilation():
                self.assertEqual(self.linear_data.parallel_compilation_depth, 2)
            self.assertEqual(self.linear_data.parallel_compilation_depth, 1)
        self.assertEqual(self.linear_data.parallel_compilation_depth, 0)


if __name__ == "__main__":
    unittest.main()
