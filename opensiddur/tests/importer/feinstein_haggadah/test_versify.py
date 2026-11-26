"""Tests for the biblical verse milestones in the haggadah."""

import re
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.common.versification import WLC_PROJECT
from opensiddur.importer.feinstein_haggadah.convert import EN_PROJECT, HE_PROJECT
from opensiddur.importer.feinstein_haggadah.page_breaks import find_break_offset
from opensiddur.importer.feinstein_haggadah.sections import document_order_slugs
from opensiddur.importer.feinstein_haggadah.tei_builder import verse_anchors
from opensiddur.importer.feinstein_haggadah.versify import (
    BIBLICAL_SECTIONS,
    build_section,
    load_printed_psalms,
    load_verse_anchors,
    read_wlc_chapter,
    verse_offsets,
)
from opensiddur.importer.util.hebrew import normalize_hebrew
from opensiddur.tests.importer.feinstein_haggadah import support

TEI = "{http://www.tei-c.org/ns/1.0}"
WLC_PSALMS = Path("project") / WLC_PROJECT / "psalms.xml"
PROJECT = Path("project") / HE_PROJECT

#: Masoretic verse counts, as a check independent of whatever the WLC reader returns.
VERSE_COUNTS = {113: 9, 114: 8, 115: 18, 116: 19, 117: 2, 118: 29, 126: 6, 136: 26}


class TestCuratedVerseAnchors(unittest.TestCase):
    """Checks on the curated table alone.

    ``verse_anchors.json`` is committed inside the package, so none of this needs the
    sourcetexts checkout. Whether the anchors still *match* the source is
    ``TestAnchorsAgainstTheSource`` below.
    """

    def setUp(self) -> None:
        self.sections = load_verse_anchors()

    def test_covers_every_complete_biblical_unit(self) -> None:
        self.assertEqual(set(self.sections), set(BIBLICAL_SECTIONS))

    def test_sections_exist_and_are_transcluded(self) -> None:
        placed = set(document_order_slugs())
        for slug in self.sections:
            self.assertIn(slug, placed)

    def test_verse_counts_are_masoretic(self) -> None:
        for slug, section in self.sections.items():
            self.assertEqual(
                len(section.verses), VERSE_COUNTS[section.chapter], slug
            )

    def test_verses_are_numbered_from_one_without_gaps(self) -> None:
        for slug, section in self.sections.items():
            self.assertEqual(
                [verse.n for verse in section.verses],
                list(range(1, len(section.verses) + 1)),
                slug,
            )

    def test_only_the_first_verse_opens_its_section(self) -> None:
        for slug, section in self.sections.items():
            opening = [verse.n for verse in section.verses if verse.at_section_start]
            self.assertEqual(opening, [1], slug)


class TestAnchorsAgainstTheSource(unittest.TestCase):
    """The curated anchors must still match the compilation they were read off.

    Needs the sourcetexts checkout; skips without it. A source rewording fails the conversion
    in ``convert.py`` on the same conditions.
    """

    def setUp(self) -> None:
        self.sections = load_verse_anchors()
        self.texts = support.compilation_section_texts()

    def test_every_anchor_resolves_to_one_place(self) -> None:
        for slug, section in self.sections.items():
            text = self.texts[slug]
            for verse in section.verses:
                if verse.at_section_start:
                    continue
                with self.subTest(section=slug, verse=verse.n):
                    find_break_offset(text, verse.before_text, verse.after_text)

    def test_verses_run_forwards_and_cover_the_whole_text(self) -> None:
        """No verse may overlap, skip, or drop text between it and the next."""
        for slug, section in self.sections.items():
            text = self.texts[slug]
            offsets = [
                0
                if verse.at_section_start
                else find_break_offset(text, verse.before_text, verse.after_text)
                for verse in section.verses
            ]
            self.assertEqual(offsets, sorted(offsets), slug)
            covered = "".join(
                normalize_hebrew(text[start:end])
                for start, end in zip(offsets, offsets[1:] + [len(text)])
            )
            self.assertEqual(covered, normalize_hebrew(text), slug)


class TestVerseOffsets(unittest.TestCase):
    def test_boundaries_transfer_across_orthographic_drift(self) -> None:
        """The haggadah differs from WLC by a letter here and there; boundaries still land."""
        wlc = [(1, "אבג דה"), (2, "וזח טי"), (3, "כלמ נס")]
        offsets = verse_offsets("אבג דה וזח טיו כלמ נס", wlc)
        self.assertEqual(sorted(offsets), [1, 2, 3])
        self.assertEqual(offsets[1], 0)

    def test_unlocatable_verse_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            verse_offsets("אבג", [(1, "אבג"), (2, "שרק צפע")])

    def test_first_verse_has_no_anchor(self) -> None:
        section = build_section(
            "psalm_x", "psalms", 1, "אבג דה וזח", [(1, "אבג דה"), (2, "וזח")]
        )
        self.assertTrue(section.verses[0].at_section_start)
        self.assertFalse(section.verses[1].at_section_start)


class TestWlcReader(unittest.TestCase):
    def setUp(self) -> None:
        support.require_path(WLC_PSALMS, "WLC project not generated")

    def test_reads_masoretic_verse_counts(self) -> None:
        for chapter, count in VERSE_COUNTS.items():
            self.assertEqual(len(read_wlc_chapter(WLC_PSALMS, chapter)), count, chapter)

    def test_descends_into_kri_ktiv_choices(self) -> None:
        """Psalm 126:4 is a kri/ktiv; a tail-only walk would drop the word entirely."""
        verses = dict(read_wlc_chapter(WLC_PSALMS, 126))
        self.assertIn("שוב", normalize_hebrew(verses[4]))
        self.assertGreater(len(normalize_hebrew(verses[4])), 20)


class TestVerseAnchorMarkup(unittest.TestCase):
    def test_chapter_and_verse_carry_canonical_urns(self) -> None:
        section = load_verse_anchors()["psalm_115"]
        anchors = verse_anchors(section)
        self.assertIn(
            '<tei:milestone unit="chapter" n="115" '
            'corresp="urn:x-opensiddur:text:bible:psalms/115"/>',
            anchors[0].markup,
        )
        self.assertIn(
            'corresp="urn:x-opensiddur:text:bible:psalms/115/1"', anchors[1].markup
        )

    def test_chapter_milestone_opens_the_section(self) -> None:
        anchors = verse_anchors(load_verse_anchors()["psalm_115"])
        self.assertTrue(anchors[0].at_section_start)


class TestGeneratedPsalms(unittest.TestCase):
    """Checks against the committed project, skipped when it is not present."""

    def setUp(self) -> None:
        support.require_path(PROJECT, "haggadah project not generated")
        support.require_path(WLC_PSALMS, "WLC project not generated")

    def _milestones(self, slug: str, unit: str) -> list[tuple[str, str]]:
        tree = etree.parse(str(PROJECT / f"{slug}.xml"))
        return [
            (element.get("n"), element.get("corresp"))
            for element in tree.iter(f"{TEI}milestone")
            if element.get("unit") == unit
        ]

    def test_verse_urns_match_wlc(self) -> None:
        for slug, chapter in BIBLICAL_SECTIONS.items():
            expected = [
                (str(n), f"urn:x-opensiddur:text:bible:psalms/{chapter}/{n}")
                for n, _ in read_wlc_chapter(WLC_PSALMS, chapter)
            ]
            self.assertEqual(self._milestones(slug, "verse"), expected, slug)

    def test_each_psalm_has_exactly_one_chapter_milestone(self) -> None:
        for slug, chapter in BIBLICAL_SECTIONS.items():
            self.assertEqual(
                self._milestones(slug, "chapter"),
                [(str(chapter), f"urn:x-opensiddur:text:bible:psalms/{chapter}")],
                slug,
            )

    def test_psalms_carry_no_paragraph_milestones(self) -> None:
        for slug in BIBLICAL_SECTIONS:
            self.assertEqual(self._milestones(slug, "paragraph"), [], slug)

    def test_psalms_cite_wlc_only_where_wlc_is_the_source(self) -> None:
        """The transcribed psalms cite the 1822 print; only Psalm 126 still cites WLC.

        The seven psalms the print carries are transcribed from the facsimile, so naming WLC as
        their text source would be a false provenance claim. See ``heidenheim_psalms_1822.json``.
        """
        printed = load_printed_psalms()
        for slug, chapter in BIBLICAL_SECTIONS.items():
            text = (PROJECT / f"{slug}.xml").read_text("utf-8")
            with self.subTest(slug=slug):
                if slug in printed:
                    self.assertNotIn(
                        f'target="urn:x-opensiddur:text:bible:psalms@{WLC_PROJECT}"', text
                    )
                    continue
                self.assertIn(f'target="urn:x-opensiddur:text:bible:psalms@{WLC_PROJECT}"', text)
                self.assertIn(
                    f'<tei:biblScope unit="chapter" from="{chapter}" to="{chapter}"/>', text
                )

    def test_text_is_unchanged_by_versification(self) -> None:
        """Splicing milestones in must not disturb a single letter.

        Only applies where the anchor mechanism does the splicing. The transcribed psalms carry
        their own verse divisions and deliberately depart from the compilation's wording, so
        ``test_printed_psalms`` checks their letters against WLC instead.
        """
        printed = load_printed_psalms()
        texts = support.compilation_section_texts()
        for slug in BIBLICAL_SECTIONS:
            if slug in printed:
                continue
            tree = etree.parse(str(PROJECT / f"{slug}.xml"))
            div = tree.find(f".//{TEI}body/{TEI}div")
            rendered = "".join(
                "".join(element.itertext())
                for element in div
                if etree.QName(element).localname == "p"
            )
            self.assertEqual(
                normalize_hebrew(rendered), normalize_hebrew(texts[slug]), slug
            )

    def test_barech_keeps_its_english_instructions_interleaved(self) -> None:
        """The regression a trailing-content hack would have caused in the translation."""
        english = Path("project") / EN_PROJECT / "barekh.xml"
        support.require_path(english, "translation project not generated")
        body = english.read_text("utf-8")
        body = body[body.index("<tei:body>") :]
        kinds = re.findall(r"<tei:(note|p)\b", body)
        self.assertIn("note", kinds)
        # Notes must not all be bunched ahead of the paragraphs.
        self.assertGreater(kinds.index("p"), 0)
        self.assertIn("note", kinds[kinds.index("p") :])


if __name__ == "__main__":
    unittest.main()
