"""Checks on the diplomatic transcription of the psalms printed in the 1822 haggadah.

Vowels cannot be verified mechanically — they were read off the facsimile — but the consonantal
skeleton can, and comparing it against the Westminster Leningrad Codex catches any letter dropped
or misread in transcription. The rest of the tests pin the conventions the print was found to
follow, so a later edit that reintroduces cantillation or the four-letter Name fails here.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from opensiddur.importer.feinstein_haggadah.page_breaks import load_page_breaks, pb_markup
from opensiddur.importer.feinstein_haggadah.tei_builder import printed_verse_body
from opensiddur.importer.feinstein_haggadah.versify import (
    BIBLICAL_SECTIONS,
    load_printed_psalms,
    read_wlc_chapter,
)
from opensiddur.importer.util.hebrew import normalize_hebrew
from opensiddur.tests.importer.feinstein_haggadah import support

WLC_PSALMS = Path("project/wlc/psalms.xml")

#: The print writes the Divine Name as a double yod; WLC writes the tetragrammaton. Mapping one
#: to the other is what lets the two consonantal skeletons be compared at all.
YY = "יְיָ"

#: U+0591-U+05AF cantillation, U+05BD meteg, U+05BF rafe: the print sets none of them.
FORBIDDEN_MARKS = re.compile("[֑-ֽֿ֯]")

MARKUP = re.compile(r"<[^>]+>")

#: The one place the print's consonants differ from the Leningrad Codex, read off folio 33v:
#: WLC spells the refrain of Psalm 136:3 defectively, le-olam without the vav, alone among the
#: chapter's twenty-six verses. The 1822 print writes it plene, like all the others.
CONSONANT_VARIANTS = {("psalm_136", 3): ("לעלם", "לעולם")}


def strip_markup(text: str) -> str:
    return MARKUP.sub("", text)


class PrintedPsalmsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.psalms = load_printed_psalms()

    def test_covers_every_psalm_the_1822_print_carries(self) -> None:
        # psalm_126 is deliberately absent: the print has no Shir haMaalot before Birkat HaMazon.
        self.assertEqual(
            sorted(self.psalms),
            ["psalm_113", "psalm_114", "psalm_115", "psalm_116", "psalm_117", "psalm_118",
             "psalm_136"],
        )
        self.assertNotIn("psalm_126", self.psalms)
        for slug, psalm in self.psalms.items():
            self.assertEqual(psalm.chapter, BIBLICAL_SECTIONS[slug])

    def test_verse_numbers_are_contiguous_from_one(self) -> None:
        for slug, psalm in self.psalms.items():
            with self.subTest(slug=slug):
                self.assertEqual(
                    sorted(psalm.verses), list(range(1, len(psalm.verses) + 1))
                )

    def test_consonants_match_the_leningrad_codex(self) -> None:
        """Every verse's consonantal skeleton equals WLC's, once the Name is mapped back."""
        support.require_path(WLC_PSALMS, "WLC project not generated")
        for slug, psalm in self.psalms.items():
            wlc = dict(read_wlc_chapter(WLC_PSALMS, psalm.chapter))
            self.assertEqual(sorted(wlc), sorted(psalm.verses), f"{slug} verse set")
            for n, text in sorted(psalm.verses.items()):
                with self.subTest(slug=slug, verse=n):
                    printed = normalize_hebrew(strip_markup(text).replace(YY, "יהוה"))
                    expected = normalize_hebrew(wlc[n])
                    variant = CONSONANT_VARIANTS.get((slug, n))
                    if variant:
                        expected = expected.replace(*variant, 1)
                    self.assertEqual(printed, expected, f"{slug} {psalm.chapter}:{n}")

    def test_no_cantillation_meteg_or_rafe(self) -> None:
        for slug, psalm in self.psalms.items():
            for n, text in sorted(psalm.verses.items()):
                found = FORBIDDEN_MARKS.findall(strip_markup(text))
                with self.subTest(slug=slug, verse=n):
                    self.assertEqual(
                        found, [], f"{slug} {psalm.chapter}:{n} has {found!r}"
                    )

    def test_divine_name_is_the_double_yod_and_always_tagged(self) -> None:
        for slug, psalm in self.psalms.items():
            for n, text in sorted(psalm.verses.items()):
                with self.subTest(slug=slug, verse=n):
                    self.assertNotIn("יהוה", strip_markup(text))
                    self.assertEqual(
                        text.count(YY), text.count(f"<j:divineName>{YY}</j:divineName>")
                    )

    def test_halleluyah_is_never_split_by_a_maqaf(self) -> None:
        for slug, psalm in self.psalms.items():
            for n, text in sorted(psalm.verses.items()):
                with self.subTest(slug=slug, verse=n):
                    self.assertNotIn("הַלְלוּ־יָהּ", text)

    def test_only_divine_name_and_page_break_markup_is_used(self) -> None:
        allowed = re.compile(
            r"</?j:divineName>|"
            r'<tei:pb n="[0-9]+[rv]" ed="1822" facs="[^"]+"/>'
        )
        for slug, psalm in self.psalms.items():
            for n, text in sorted(psalm.verses.items()):
                with self.subTest(slug=slug, verse=n):
                    self.assertEqual(MARKUP.findall(allowed.sub("", text)), [])

    def test_every_folio_turn_inside_a_psalm_is_transcribed_once(self) -> None:
        expected: dict[str, set[str]] = {}
        for entry in load_page_breaks():
            if entry.section in self.psalms:
                expected.setdefault(entry.section, set()).add(entry.page)
        self.assertTrue(expected, "no psalm page breaks in the curated table")
        for slug, pages in expected.items():
            body = "".join(self.psalms[slug].verses.values())
            for page in pages:
                with self.subTest(slug=slug, page=page):
                    self.assertEqual(
                        body.count(pb_markup(page)), 1
                    )


class PrintedVerseBodyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.psalms = load_printed_psalms()

    def test_milestones_carry_canonical_biblical_urns(self) -> None:
        body = printed_verse_body(self.psalms["psalm_117"])
        self.assertIn(
            '<tei:milestone unit="chapter" n="117" '
            'corresp="urn:x-opensiddur:text:bible:psalms/117"/>',
            body,
        )
        self.assertIn(
            '<tei:milestone unit="verse" n="2" '
            'corresp="urn:x-opensiddur:text:bible:psalms/117/2"/>',
            body,
        )

    def test_div_keeps_its_haggadah_corresp(self) -> None:
        body = printed_verse_body(self.psalms["psalm_113"])
        self.assertIn(
            '<tei:div corresp="urn:x-opensiddur:text:haggadah:maggid/psalm_113">', body
        )

    def test_a_folio_opening_a_psalm_is_marked_before_the_chapter(self) -> None:
        body = printed_verse_body(self.psalms["psalm_114"])
        self.assertLess(
            body.index(pb_markup("25v")),
            body.index('<tei:milestone unit="chapter"'),
        )

    def test_markers_before_the_first_word_stand_outside_the_paragraph(self) -> None:
        body = printed_verse_body(self.psalms["psalm_114"])
        opening = body[: body.index("<tei:p>")]
        self.assertIn(pb_markup("25v"), opening)
        self.assertIn('<tei:milestone unit="chapter"', opening)
        self.assertIn('<tei:milestone unit="verse" n="1"', opening)

    def test_a_folio_turning_mid_verse_stays_where_it_falls(self) -> None:
        body = printed_verse_body(self.psalms["psalm_113"])
        self.assertIn(f'עַל־כָּל־{pb_markup("25r")}גּוֹיִם', body)

    def test_every_verse_appears_in_one_flat_paragraph(self) -> None:
        for slug, psalm in self.psalms.items():
            body = printed_verse_body(psalm)
            with self.subTest(slug=slug):
                self.assertEqual(body.count("<tei:p>"), 1)
                self.assertEqual(body.count('<tei:milestone unit="verse"'), len(psalm.verses))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
