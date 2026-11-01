"""Tests for the hand-curated 1822 page-break table and how it is applied."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.feinstein_haggadah.convert import page_ranges
from opensiddur.importer.feinstein_haggadah.page_breaks import (
    PageBreak,
    PageBreakError,
    facsimile_page,
    facsimile_url,
    folio_at_facsimile_page,
    find_break_offset,
    load_page_breaks,
    load_section_ranges,
    page_breaks_by_section,
)
from opensiddur.importer.feinstein_haggadah.sections import (
    CONTENT_BEARING_INDEX_NODES,
    HALLEL_SUBSECTION_PREFIXES,
    INDEX_CHILDREN,
    INDEX_NODES,
    NIRTZAH_SUBSECTION_PREFIXES,
    document_order_slugs,
)
from opensiddur.importer.feinstein_haggadah.tei_builder import (
    _paragraph_xml,
    _pb,
    citation_bibl,
    content_body,
    header_with_page_scope,
    index_body,
    page_break_anchors,
)
from opensiddur.importer.util.hebrew import normalize_hebrew, normalize_with_offsets

ALL_FOLIOS = [f"{folio}{side}" for folio in range(2, 41) for side in ("r", "v")]


class TestFacsimileMapping(unittest.TestCase):
    """The folio-to-scan-page mapping behind tei:pb/@facs.

    Every value below was read off Hebrewbooks_org_4909.pdf rather than derived, including
    one in the middle of the book: the viewer clamps an out-of-range pgnum to the last page,
    so an off-by-one mapping still resolves the final folio while everything before it is
    wrong, and endpoints alone cannot catch that.
    """

    def test_maps_the_ends_of_the_range(self) -> None:
        self.assertEqual(facsimile_page("2r"), 3)  # first page of text
        self.assertEqual(facsimile_page("40v"), 80)  # last page of the scan

    def test_verso_follows_its_recto(self) -> None:
        self.assertEqual(facsimile_page("3r"), 5)
        self.assertEqual(facsimile_page("3v"), 6)  # qaddesh, checked in the viewer

    def test_alternation_is_unbroken_across_the_whole_book(self) -> None:
        pages = [facsimile_page(folio) for folio in ALL_FOLIOS]
        self.assertEqual(pages, list(range(3, 3 + len(ALL_FOLIOS))))

    def test_rejects_designations_it_cannot_map(self) -> None:
        for bad in ("5", "v5", "5x", "", "5 r", "1r"):
            with self.subTest(page=bad), self.assertRaises(ValueError):
                facsimile_page(bad)

    def test_page_break_exposes_its_scan_page(self) -> None:
        self.assertEqual(PageBreak(page="3v", section="qaddesh").facsimile_page, 6)

    def test_url_deep_links_the_scan(self) -> None:
        self.assertEqual(
            facsimile_url("3v"),
            "https://www.hebrewbooks.org/pdfpager.aspx?req=4909&pgnum=6",
        )

    def test_inverts_back_to_the_folio(self) -> None:
        for folio in ALL_FOLIOS:
            with self.subTest(folio=folio):
                self.assertEqual(folio_at_facsimile_page(facsimile_page(folio)), folio)

    def test_front_matter_and_overrun_carry_no_folio(self) -> None:
        for page in (0, 1, 2, 81, 200):
            with self.subTest(page=page), self.assertRaises(ValueError):
                folio_at_facsimile_page(page)

    def test_milestone_keeps_the_printed_foliation_and_adds_the_link(self) -> None:
        self.assertEqual(
            _pb("3v"),
            '<tei:pb n="3v" ed="1822"'
            ' facs="https://www.hebrewbooks.org/pdfpager.aspx?req=4909&amp;pgnum=6"/>',
        )


class TestNormalizeHebrew(unittest.TestCase):
    def test_strips_marks_and_non_letters(self) -> None:
        self.assertEqual(normalize_hebrew("קַדֵּשׁ!"), "קדש")

    def test_drops_latin_and_parentheses(self) -> None:
        self.assertEqual(normalize_hebrew("(שַׁבָּת) x2"), "שבת")

    def test_offsets_point_back_at_the_original(self) -> None:
        text = "בָּרוּךְ אַתָּה"
        normalized, offsets = normalize_with_offsets(text)
        self.assertEqual(normalized, "ברוךאתה")
        self.assertEqual(len(normalized), len(offsets))
        for index, char in enumerate(normalized):
            self.assertEqual(text[offsets[index]], char)


class TestFindBreakOffset(unittest.TestCase):
    #: Vowelled and punctuated the way the transcription is, unlike the curated anchors.
    TEXT = "מַה נִּשְׁתַּנָּה הַלַּֽיְלָה הַזֶּה. שֶׁבְּכָל־הַלֵּילוֹת אָנוּ אוֹכְלִין חָמֵץ׃"

    def test_matches_unpointed_anchors(self) -> None:
        offset = find_break_offset(self.TEXT, "שבכל", "הלילות אנו אוכלין")
        self.assertEqual(normalize_hebrew(self.TEXT[offset:]), "הלילותאנואוכליןחמץ")

    def test_offset_falls_between_the_two_anchors(self) -> None:
        offset = find_break_offset(self.TEXT, "הזה", "שבכל הלילות")
        self.assertTrue(normalize_hebrew(self.TEXT[:offset]).endswith("הזה"))
        self.assertTrue(normalize_hebrew(self.TEXT[offset:]).startswith("שבכל"))

    def test_raises_when_neither_side_matches(self) -> None:
        with self.assertRaises(PageBreakError) as caught:
            find_break_offset(self.TEXT, "אבגד", "הוזח")
        self.assertIn("before_text and after_text", str(caught.exception))

    def test_raises_when_only_one_side_matches(self) -> None:
        with self.assertRaises(PageBreakError) as caught:
            find_break_offset(self.TEXT, "שבכל", "אבגדהוז")
        self.assertIn("after_text", str(caught.exception))

    def test_raises_when_the_sides_are_not_adjacent(self) -> None:
        with self.assertRaises(PageBreakError) as caught:
            find_break_offset(self.TEXT, "מה נשתנה", "אנו אוכלין")
        self.assertIn("not adjacent", str(caught.exception))

    def test_raises_when_the_anchor_is_ambiguous(self) -> None:
        with self.assertRaises(PageBreakError) as caught:
            find_break_offset("אבגאבג", "אב", "ג")
        self.assertIn("more than once", str(caught.exception))

    def test_rejects_an_empty_anchor(self) -> None:
        with self.assertRaises(PageBreakError):
            find_break_offset(self.TEXT, "", "הלילות")


class TestCuratedTable(unittest.TestCase):
    """Invariants of page_breaks_1822.json itself."""

    def setUp(self) -> None:
        self.breaks = load_page_breaks()

    def test_covers_every_folio_side_exactly_once_in_order(self) -> None:
        self.assertEqual([entry.page for entry in self.breaks], ALL_FOLIOS)

    def test_every_section_is_a_known_leaf(self) -> None:
        leaves = set(document_order_slugs())
        for entry in self.breaks:
            self.assertIn(entry.section, leaves, f"page {entry.page}")

    def test_pages_advance_with_document_order(self) -> None:
        position = {slug: i for i, slug in enumerate(document_order_slugs())}
        sequence = [position[entry.section] for entry in self.breaks]
        self.assertEqual(sequence, sorted(sequence))

    def test_anchors_are_paired(self) -> None:
        for entry in self.breaks:
            self.assertEqual(
                entry.before_text is None,
                entry.after_text is None,
                f"page {entry.page} has only one side of the break",
            )

    def test_section_range_overrides_name_real_sections(self) -> None:
        for slug, (first, last) in load_section_ranges().items():
            self.assertIn(slug, document_order_slugs())
            self.assertIn(first, ALL_FOLIOS)
            self.assertIn(last, ALL_FOLIOS)


class TestSectionOrder(unittest.TestCase):
    """The transclusion order follows the 1822 print, not the Open Siddur compilation."""

    def test_folio_38r_reads_as_printed(self) -> None:
        """Ki Lo Na'eh, לשנה הבאה, the two fourth-cup blessings, then Chasal Siddur Pesach."""
        order = INDEX_CHILDREN["nirtzah"]
        start = order.index("ki_lo_naeh")
        self.assertEqual(
            order[start : start + 5],
            [
                "ki_lo_naeh",
                "leshanah_habaah",
                "kos_revii",
                "al_hagefen",
                "chasal_siddur_pesach",
            ],
        )

    def test_fourth_cup_blessings_left_hallel(self) -> None:
        for slug in ("kos_revii", "al_hagefen"):
            self.assertNotIn(slug, INDEX_CHILDREN["hallel"])

    def test_hallel_transcludes_its_psalms_in_order(self) -> None:
        order = INDEX_CHILDREN["hallel"]
        psalms = [slug for slug in order if slug.startswith("psalm_")]
        self.assertEqual(
            psalms, ["psalm_115", "psalm_116", "psalm_117", "psalm_118", "psalm_136"]
        )
        # Yehalelukha sits between Psalms 118 and 136, which is why Hallel had to become an
        # index node rather than keeping the non-psalms inline.
        self.assertLess(order.index("psalm_118"), order.index("yehalalukha"))
        self.assertLess(order.index("yehalalukha"), order.index("psalm_136"))

    def test_second_cup_blessings_close_magid(self) -> None:
        self.assertEqual(
            INDEX_CHILDREN["maggid"][-2:], ["asher_gealanu", "kos_sheni"]
        )

    def test_barekh_transcludes_psalm_126(self) -> None:
        self.assertEqual(INDEX_CHILDREN["barekh"], ["psalm_126"])

    def test_every_parsed_hallel_subsection_is_transcluded_somewhere(self) -> None:
        placed = set(document_order_slugs())
        for _, slug in HALLEL_SUBSECTION_PREFIXES:
            self.assertIn(slug, placed)

    def test_sefirat_haomer_sits_between_addir_hu_and_echad_mi_yodea(self) -> None:
        order = INDEX_CHILDREN["nirtzah"]
        self.assertEqual(order.index("sefirat_haomer"), order.index("addir_hu") + 1)
        self.assertEqual(
            order.index("echad_mi_yodea"), order.index("sefirat_haomer") + 1
        )

    def test_sefirat_haomer_left_the_seder_node(self) -> None:
        self.assertNotIn("sefirat_haomer", INDEX_CHILDREN["seder"])

    def test_every_parsed_nirtzah_subsection_is_transcluded(self) -> None:
        """The prefix list drives parsing; the child list drives order. Keep them in step."""
        for _, slug in NIRTZAH_SUBSECTION_PREFIXES:
            self.assertIn(slug, INDEX_CHILDREN["nirtzah"])

    def test_each_leaf_is_transcluded_exactly_once(self) -> None:
        order = document_order_slugs()
        self.assertEqual(len(order), len(set(order)))


class TestPageRanges(unittest.TestCase):
    def test_section_with_a_break_at_its_start(self) -> None:
        ranges = page_ranges(load_page_breaks())
        self.assertEqual(ranges["qaddesh"], ("3v", "4r"))

    def test_section_beginning_on_the_preceding_page(self) -> None:
        """mah_nishtanah opens on 5r, which was opened by ha_lachma_anya."""
        ranges = page_ranges(load_page_breaks())
        self.assertEqual(ranges["mah_nishtanah"], ("5r", "6r"))

    def test_section_wholly_inside_one_page(self) -> None:
        ranges = page_ranges(load_page_breaks())
        first, last = ranges["urechatz"]
        self.assertEqual(first, last)
        self.assertEqual(first, "4r")

    def test_index_spans_the_whole_book(self) -> None:
        ranges = page_ranges(load_page_breaks())
        self.assertEqual(ranges["index"], ("2r", "40v"))

    def test_index_nodes_span_their_subtree(self) -> None:
        ranges = page_ranges(load_page_breaks())
        for node in INDEX_NODES - CONTENT_BEARING_INDEX_NODES:
            children = INDEX_CHILDREN[node]
            self.assertEqual(ranges[node][0], ranges[children[0]][0], node)
            self.assertEqual(ranges[node][1], ranges[children[-1]][1], node)

    def test_content_bearing_node_spans_past_its_children(self) -> None:
        """Barech transcludes Psalm 126 and then runs on for another thirty paragraphs."""
        ranges = page_ranges(load_page_breaks())
        self.assertEqual(ranges["psalm_126"], ("27r", "27r"))
        self.assertEqual(ranges["barekh"], ("27r", "30v"))

    def test_hallel_needs_no_override(self) -> None:
        """The override existed only because the fourth-cup blessings were stuck inside Hallel."""
        self.assertEqual(load_section_ranges(), {})
        self.assertEqual(page_ranges(load_page_breaks())["hallel"], ("30v", "35v"))

    def test_override_replaces_the_derived_range(self) -> None:
        overridden = page_ranges(load_page_breaks(), {"hallel": ("30v", "38r")})
        self.assertEqual(overridden["hallel"], ("30v", "38r"))


class TestParagraphRendering(unittest.TestCase):
    def test_page_break_lands_inside_the_paragraph(self) -> None:
        rendered = _paragraph_xml("אבגד הוזח", [(5, '<tei:pb n="5v" ed="1822"/>')])
        self.assertEqual(rendered, '<tei:p>אבגד <tei:pb n="5v" ed="1822"/>הוזח</tei:p>')

    def test_page_break_at_a_paragraph_boundary_opens_the_next_paragraph(self) -> None:
        expected = '<tei:p>אבגד</tei:p>\n<tei:p><tei:pb n="5v" ed="1822"/>הוזח</tei:p>'
        for offset in (4, 5, 6):  # end of the first, the gap, start of the second
            with self.subTest(offset=offset):
                rendered = _paragraph_xml(
                    "אבגד\n\nהוזח", [(offset, '<tei:pb n="5v" ed="1822"/>')]
                )
                self.assertEqual(rendered, expected)

    def test_page_break_past_all_text_is_a_trailing_sibling(self) -> None:
        rendered = _paragraph_xml("אבגד", [(4, "<PB/>")])
        self.assertEqual(rendered, "<tei:p>אבגד</tei:p>\n<PB/>")

    def test_text_around_a_break_is_still_escaped(self) -> None:
        rendered = _paragraph_xml("a&b<c", [(3, "<PB/>")])
        self.assertEqual(rendered, "<tei:p>a&amp;b<PB/>&lt;c</tei:p>")

    def test_offsets_survive_multiple_breaks_in_one_paragraph(self) -> None:
        rendered = _paragraph_xml("אבגדהו", [(2, "<X/>"), (4, "<Y/>")])
        self.assertEqual(rendered, "<tei:p>אב<X/>גד<Y/>הו</tei:p>")


class TestContentBody(unittest.TestCase):
    def _section(self, text: str, **kwargs):
        from opensiddur.importer.feinstein_haggadah.sections import (
            SectionContent,
            TextBlock,
        )

        return SectionContent(
            slug="karpas",
            blocks=[TextBlock(kind="paragraph", hebrew=text, starts_paragraph=True)],
            **kwargs,
        )

    def test_break_at_section_start_is_the_first_child_of_the_div(self) -> None:
        body = content_body(
            "karpas",
            self._section("אבגד"),
            lang="he",
            anchors=page_break_anchors([PageBreak(page="3v", section="karpas")]),
        )
        self.assertRegex(body, r"<tei:div[^>]*>\s*" + re.escape(_pb("3v")))

    def test_anchored_break_is_placed_in_the_text(self) -> None:
        body = content_body(
            "karpas",
            self._section("אבגד הוזח"),
            lang="he",
            anchors=page_break_anchors(
                [
                    PageBreak(
                        page="4r", section="karpas", before_text="אבגד", after_text="הוזח"
                    )
                ]
            ),
        )
        self.assertIn(f'אבגד {_pb("4r")}הוזח', body)

    def test_anchored_break_against_an_empty_section_is_an_error(self) -> None:
        with self.assertRaises(PageBreakError):
            content_body(
                "urechatz",
                None,
                lang="he",
                anchors=page_break_anchors(
                    [
                        PageBreak(
                            page="4r", section="urechatz", before_text="א", after_text="ב"
                        )
                    ]
                ),
            )

    def test_failure_names_the_page_and_section(self) -> None:
        with self.assertRaises(PageBreakError) as caught:
            content_body(
                "karpas",
                self._section("אבגד"),
                lang="he",
                anchors=page_break_anchors(
                    [
                        PageBreak(
                            page="9v", section="karpas", before_text="קץ", after_text="סוף"
                        )
                    ]
                ),
            )
        self.assertIn("9v", str(caught.exception))
        self.assertIn("karpas", str(caught.exception))

    def test_paragraph_milestones_can_be_suppressed(self) -> None:
        """A biblical section is numbered by chapter and verse, not by paragraph."""
        body = content_body(
            "karpas", self._section("אבגד"), lang="he", number_paragraphs=False
        )
        self.assertNotIn('unit="paragraph"', body)


class TestPositionalTransclusion(unittest.TestCase):
    """A section can hold text both before and after its transclusions."""

    def _section(self, children_at: int | None):
        from opensiddur.importer.feinstein_haggadah.sections import (
            SectionContent,
            TextBlock,
        )

        return SectionContent(
            slug="seder",
            blocks=[
                TextBlock(kind="head", hebrew="בָּרֵךְ"),
                TextBlock(kind="paragraph", hebrew="אחרי", starts_paragraph=True),
            ],
            children_at=children_at,
        )

    def test_children_land_at_the_recorded_position(self) -> None:
        body = index_body("seder", ["psalm_126"], self._section(1), lang="he")
        head = body.index("<tei:head>")
        transclude = body.index("<j:transclude")
        paragraph = body.index("אחרי")
        self.assertLess(head, transclude)
        self.assertLess(transclude, paragraph)

    def test_children_default_to_the_end(self) -> None:
        body = index_body("seder", ["psalm_126"], self._section(None), lang="he")
        self.assertLess(body.index("אחרי"), body.index("<j:transclude"))

    def test_index_node_without_content_still_transcludes(self) -> None:
        body = index_body("pre_seder", ["bediqat_chametz"], None, lang="he")
        self.assertIn("<j:transclude", body)


class TestCitationBibl(unittest.TestCase):
    def test_pointer_uses_the_index_file_fragment(self) -> None:
        bibl = citation_bibl("heidenheim_haggadah_1822", "5r", "6r")
        self.assertIn(
            'target="/heidenheim_haggadah_1822/index#project_source_bibl"', bibl
        )
        self.assertIn('<tei:biblScope unit="pages" from="5r" to="6r"/>', bibl)

    def test_appended_inside_source_desc(self) -> None:
        header = (
            "<tei:teiHeader><tei:fileDesc><tei:sourceDesc>"
            '<tei:bibl xml:id="project_source_bibl"/>'
            "</tei:sourceDesc></tei:fileDesc></tei:teiHeader>"
        )
        scoped = header_with_page_scope(
            header, project_id="p", from_page="2r", to_page="3v"
        )
        self.assertLess(scoped.index("<tei:biblScope"), scoped.index("</tei:sourceDesc>"))

    def test_header_without_source_desc_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            header_with_page_scope("<tei:teiHeader/>", project_id="p", from_page="2r", to_page="3v")


class TestLoading(unittest.TestCase):
    def test_load_from_an_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "breaks.json"
            path.write_text(
                json.dumps(
                    {
                        "_comment": "ignored",
                        "pages": [
                            {"page": "2r", "section": "karpas"},
                            {
                                "page": "2v",
                                "section": "karpas",
                                "before_text": "א",
                                "after_text": "ב",
                            },
                        ],
                        "section_ranges": {"karpas": {"from": "2r", "to": "2v"}},
                    }
                ),
                encoding="utf-8",
            )
            breaks = load_page_breaks(path)
            self.assertEqual([entry.page for entry in breaks], ["2r", "2v"])
            self.assertTrue(breaks[0].at_section_start)
            self.assertFalse(breaks[1].at_section_start)
            self.assertEqual(load_section_ranges(path), {"karpas": ("2r", "2v")})

    def test_grouping_preserves_book_order(self) -> None:
        grouped = page_breaks_by_section(load_page_breaks())
        self.assertEqual([entry.page for entry in grouped["qaddesh"]], ["3v", "4r"])


if __name__ == "__main__":
    unittest.main()
