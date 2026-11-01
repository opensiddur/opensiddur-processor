"""Tests for emitting a pair of parshiyot that are sometimes read together as one file.

The readings are synthetic, so the tests keep their meaning when MAM or hebcal is updated.
"""

import json
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.humash import build, names
from opensiddur.importer.util.hebrew import normalize_hebrew
from opensiddur.importer.humash.aliyot import CombinedParsha, Parsha
from opensiddur.importer.humash.readings import Passage
from opensiddur.importer.humash.refs import (
    UNIT_ALIYAH,
    UNIT_ALIYAH_COMBINED,
    UNIT_MAFTIR,
    UNIT_PARSHA,
    UNIT_PARSHA_COMBINED,
    VARIATION_COMBINED,
    ReadingSpan,
    VerseRef,
    triennial_unit,
)

TEI = "{http://www.tei-c.org/ns/1.0}"
J = "{http://jewishliturgy.org/ns/jlptei/2}"
XML = "{http://www.w3.org/XML/1998/namespace}"

PAIR = "tazria_metzora"
PATTERNS = {"TTS": "A", "TST": "B", "STT": "C"}


def _ref(chapter: int, verse: int) -> VerseRef:
    return VerseRef("leviticus", chapter, verse)


def _span(unit: str, label: str, start, end, owner=None) -> ReadingSpan:
    return ReadingSpan(
        unit=unit, label=label, start=_ref(*start), end=_ref(*end), owner=owner
    )


class TestDivisionPath(unittest.TestCase):
    """A division's URN path below its parshah: legal URN components, the triennial cycle a path."""

    def path(self, unit, label, parsha="chukat"):
        return build._division_path(_span(unit, label, (1, 1), (1, 2)), parsha)

    def test_a_triennial_division_is_a_path_of_cycle_year_and_aliyah(self):
        self.assertEqual(self.path("aliyah.triennial.1", "1.1"), "triennial/1/1")
        self.assertEqual(self.path("aliyah.triennial.chukat.C.2", "c.2.1"), "triennial/c/2/1")
        self.assertEqual(self.path("aliyah.triennial.behar.IL1.1", "il1.1.1", "behar"),
                         "triennial/il1/1/1")
        self.assertEqual(self.path("aliyah.triennial.combined.1", "combined.1.3", "a_b"),
                         "triennial/combined/1/3")

    def test_the_parshah_a_pair_file_repeats_is_not_repeated(self):
        self.assertEqual(self.path("aliyah.triennial.nitzavim.1", "1.2", "nitzavim"),
                         "triennial/1/2")

    def test_a_maftir_is_named_maftir(self):
        self.assertEqual(self.path("maftir.triennial.chukat.G.1", "g.1.maftir"), "triennial/g/1/maftir")
        self.assertEqual(self.path("maftir.annual", "מפטיר"), "maftir_annual/maftir")

    def test_other_divisions_keep_their_unit_and_number(self):
        self.assertEqual(self.path("aliyah.annual", "3"), "aliyah_annual/3")

    def test_a_label_with_no_ascii_name_is_refused(self):
        with self.assertRaises(ValueError):
            self.path("maftir.annual", "שביעי")


class TestMilestoneUrn(unittest.TestCase):
    """A division's URN is under its owner's parshah when it has one, else under the file's."""

    def corresp(self, span, urn_base):
        return etree.fromstring(
            build._milestone(span, urn_base).replace("tei:", "")
        ).get("corresp")

    def test_a_division_without_an_owner_is_under_the_file(self):
        span = _span("aliyah.triennial.behar.IL3.2", "il3.2.7", (1, 1), (1, 2))
        self.assertEqual(self.corresp(span, f"{build.URN_PREFIX}:parsha/behar"),
                         f"{build.URN_PREFIX}:parsha/behar/triennial/il3/2/7")

    def test_a_division_with_an_owner_is_under_its_owner(self):
        span = _span("aliyah.triennial.behar.IL3.2", "il3.2.7", (1, 1), (1, 2), owner="behar")
        self.assertEqual(self.corresp(span, f"{build.URN_PREFIX}:parsha/behar_bechukotai"),
                         f"{build.URN_PREFIX}:parsha/behar/triennial/il3/2/7")


class TestPairFile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "numverses.json").write_text(
            json.dumps({name: [0] + [17] * 30 for name in
                        ("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy")}),
            encoding="utf-8",
        )

        self.tazria = Parsha(
            slug="tazria", hebrew_name="תזריע", book="leviticus",
            start=_ref(12, 1), end=_ref(13, 17),
            spans=[_span(UNIT_ALIYAH, "1", (12, 1), (13, 17))],
        )
        self.metzora = Parsha(
            slug="metzora", hebrew_name="מצֹרע", book="leviticus",
            start=_ref(14, 1), end=_ref(15, 17),
            spans=[_span(UNIT_ALIYAH, "1", (14, 1), (15, 17))],
        )
        self.pair = CombinedParsha(
            slug=PAIR, hebrew_name="תזריע–מצֹרע", book="leviticus",
            members=("tazria", "metzora"), start=_ref(12, 1), end=_ref(15, 17),
            spans=[
                # Runs from Tazria into Metzora, which is why the pair needs its own file.
                _span(UNIT_ALIYAH_COMBINED, "1", (12, 1), (14, 4)),
                _span(UNIT_ALIYAH_COMBINED, "2", (14, 5), (15, 17)),
            ],
        )
        self.divisions = {
            "tazria": {("A", 3): [_span(
                triennial_unit(3, variation="A", owner="tazria"), "A.3.1",
                (13, 1), (13, 17), owner="tazria",
            )]},
            "metzora": {("A", 3): [_span(
                triennial_unit(3, variation="A", owner="metzora"), "A.3.1",
                (14, 1), (14, 9), owner="metzora",
            )]},
            PAIR: {("combined", 1): [_span(
                triennial_unit(1, variation="combined"), "combined.1.1", (12, 1), (12, 9),
            )]},
        }
        name, document = build.pair_file(
            self.pair, [self.tazria, self.metzora], self.divisions, PATTERNS, self.root
        )
        self.name = name
        self.tree = etree.fromstring(document.encode("utf-8"))
        self.milestones = self.tree.iter(f"{TEI}milestone")

    def _by_unit(self) -> dict[str, list]:
        found: dict[str, list] = {}
        for milestone in self.tree.iter(f"{TEI}milestone"):
            found.setdefault(milestone.get("unit"), []).append(milestone)
        return found

    def test_the_file_is_named_and_addressed_for_the_pair(self):
        self.assertEqual(self.name, f"parashat_{PAIR}")
        div = self.tree.find(f".//{TEI}body/{TEI}div")
        self.assertEqual(
            div.get("corresp"), f"urn:x-opensiddur:text:bible:parsha/{PAIR}"
        )

    def test_each_parshah_keeps_its_own_urn(self):
        by_unit = self._by_unit()
        self.assertEqual(
            [m.get("corresp") for m in by_unit["parsha.annual"]],
            ["urn:x-opensiddur:text:bible:parsha/tazria",
             "urn:x-opensiddur:text:bible:parsha/metzora"],
        )
        # The pair's own URN is on the file's div, which covers exactly the same text, so the
        # marker does not claim it a second time.
        self.assertIsNone(by_unit["parsha.combined"][0].get("corresp"))
        # Both parshiyot have a first aliyah, so the two must not land on one URN.
        self.assertEqual(
            [m.get("corresp") for m in by_unit["aliyah.annual"]],
            ["urn:x-opensiddur:text:bible:parsha/tazria/aliyah_annual/1",
             "urn:x-opensiddur:text:bible:parsha/metzora/aliyah_annual/1"],
        )

    def test_a_variation_is_conditioned_on_the_patterns_that_select_it(self):
        conditionals = self.tree.findall(f".//{J}conditional")
        self.assertEqual(len(conditionals), 2)  # one per single's variation A
        strings = [
            element.text for element in conditionals[0].iter(f"{TEI}string")
        ]
        self.assertEqual(strings, ["TTS"])
        feature = conditionals[0].find(f".//{TEI}f")
        self.assertEqual(feature.get("name"), "triennial-pattern-tazria-metzora")
        self.assertEqual(
            len(self.tree.findall(f".//{J}endConditional")), len(conditionals)
        )

    def test_the_combined_divisions_are_unconditioned(self):
        """A volume carries the pair both ways, so its combined reading is always present."""
        # Each conditional wraps exactly the marker that follows it.
        conditioned = {
            next(conditional.itersiblings()).get("unit")
            for conditional in self.tree.findall(f".//{J}conditional")
        }
        by_unit = self._by_unit()
        self.assertIn("aliyah.combined", by_unit)
        self.assertIn("aliyah.triennial.combined.1", by_unit)
        self.assertNotIn("aliyah.combined", conditioned)
        self.assertNotIn("aliyah.triennial.combined.1", conditioned)

    def test_each_parshahs_variation_has_a_unit_space_of_its_own(self):
        by_unit = self._by_unit()
        self.assertIn("aliyah.triennial.tazria.A.3", by_unit)
        self.assertIn("aliyah.triennial.metzora.A.3", by_unit)

    def test_the_text_is_transcluded_once_end_to_end(self):
        targets = [
            element.get("target").rsplit(":", 1)[1]
            for element in self.tree.iter(f"{J}transclude")
        ]
        ranges = []
        for target in targets:
            start, _, end = target.partition("-")
            _, chapter, verse = start.split("/")
            end_chapter, end_verse = end.split("/")
            ranges.append(((int(chapter), int(verse)), (int(end_chapter), int(end_verse))))
        self.assertEqual(ranges[0][0], (12, 1))
        self.assertEqual(ranges[-1][1], (15, 17))
        for earlier, later in zip(ranges, ranges[1:]):
            self.assertGreater(later[0], earlier[1], "the text is emitted more than once")


def _passage(book: str, start, end, **kwargs) -> Passage:
    return Passage(
        key="test",
        spans=[ReadingSpan(
            unit="haftarah", label="1",
            start=VerseRef(book, *start), end=VerseRef(book, *end), **kwargs,
        )],
    )


class TestHaftarahFile(unittest.TestCase):
    """The annual haftarah and the triennial ones are alternatives for the same Shabbat."""

    ANNUAL = [_passage("isaiah", (42, 5), (43, 10))]

    def _tree(self, slug: str, triennial_passages=None):
        _, document = build.haftarah_file(slug, self.ANNUAL, triennial_passages)
        return etree.fromstring(document.encode("utf-8"))

    def _features(self, conditional) -> list[str]:
        """The reading-cycle features a conditional tests for, in order."""
        return [
            f.get("name") for f in conditional.iter(f"{TEI}f")
            if f.getparent().get("type") == "opensiddur:reading-cycle"
        ]

    def test_a_parshah_with_no_triennial_haftarah_is_unconditioned(self):
        """Devarim, Vaetchanan and Vezot Haberakhah keep the annual reading in every year."""
        tree = self._tree("devarim")
        self.assertEqual(tree.findall(f".//{J}conditional"), [])

    def test_each_year_becomes_a_headed_division_of_its_own(self):
        tree = self._tree("bereshit", {
            1: _passage("isaiah", (42, 5), (42, 21)),
            2: _passage("isaiah", (40, 25), (40, 31)),
            3: _passage("kings_2", (2, 1), (2, 13)),
        })
        divisions = [
            div for div in tree.iter(f"{TEI}div")
            if (div.get("n") or "").startswith("triennial_")
        ]
        self.assertEqual(
            [div.get("corresp") for div in divisions],
            [f"urn:x-opensiddur:text:bible:haftarah/bereshit/triennial/{year}"
             for year in (1, 2, 3)],
        )
        self.assertEqual(
            [div.find(f"{J}transclude").get("target") for div in divisions],
            ["urn:x-opensiddur:text:bible:isaiah/42/5-42/21",
             "urn:x-opensiddur:text:bible:isaiah/40/25-40/31",
             "urn:x-opensiddur:text:bible:kings_2/2/1-2/13"],
        )

    def test_a_triennial_reading_turns_on_one_decisive_feature(self):
        """Two tests would be undefined where one is false, and undefined keeps the text."""
        tree = self._tree("bereshit", {1: _passage("isaiah", (42, 5), (42, 21))})
        conditional = tree.findall(f".//{J}conditional")[-1]
        self.assertEqual(self._features(conditional), ["triennial-year-1"])
        self.assertEqual(
            [b.get("value") for b in conditional.iter(f"{TEI}binary")], ["true"]
        )

    def test_a_year_is_selected_independently_of_the_others(self):
        """A volume for a whole cycle turns on all three, so they cannot be one year number."""
        tree = self._tree("bereshit", {
            year: _passage("isaiah", (40, year), (40, year)) for year in (1, 2, 3)
        })
        triennial = tree.findall(f".//{J}conditional")[1:]
        self.assertEqual(
            [self._features(c) for c in triennial],
            [["triennial-year-1"], ["triennial-year-2"], ["triennial-year-3"]],
        )

    def test_the_annual_reading_stands_in_for_the_years_that_have_none(self):
        """Tazria is read alone in years 1 and 2 only, so year 3 falls back to the annual."""
        tree = self._tree("tazria", {
            1: _passage("isaiah", (46, 3), (46, 13)),
            2: _passage("jeremiah", (30, 1), (30, 9)),
        })
        annual = tree.findall(f".//{J}conditional")[0]
        self.assertEqual(annual.find(f"{J}any").tag, f"{J}any")
        self.assertEqual(self._features(annual), ["annual", "triennial-year-3"])

    def test_a_parshah_with_every_year_yields_the_annual_only_to_the_annual_feature(self):
        tree = self._tree("bereshit", {
            year: _passage("isaiah", (40, year), (40, year)) for year in (1, 2, 3)
        })
        annual = tree.findall(f".//{J}conditional")[0]
        self.assertEqual(self._features(annual), ["annual"])

    def test_every_conditional_is_closed(self):
        tree = self._tree("bereshit", {
            year: _passage("isaiah", (40, year), (40, year)) for year in (1, 2, 3)
        })
        opened = [c.get(f"{XML}id") for c in tree.findall(f".//{J}conditional")]
        closed = [
            c.get("target").lstrip("#") for c in tree.findall(f".//{J}endConditional")
        ]
        self.assertEqual(len(opened), 4)  # the annual one, and one per year
        self.assertEqual(sorted(opened), sorted(closed))

    def test_a_boundary_inside_a_verse_is_transcluded_and_said(self):
        """Emor's third-year haftarah runs from Nachum 2:2b to 2:3a.

        The transclusion now stops where the reading stops, and the instruction beside it
        stays: a volume whose text comes from a project that marks no half-verses falls back
        on the whole verse, and there the printed instruction is all a reader has.
        """
        tree = self._tree("emor", {
            3: _passage("nahum", (2, 2, "b"), (2, 3, "a")),
        })
        division = tree.findall(f".//{TEI}div[@n='triennial_3']")[0]
        self.assertEqual(
            [child.tag for child in division][1:],
            [f"{TEI}milestone", f"{TEI}note", f"{J}transclude", f"{TEI}note"],
        )
        self.assertEqual(
            division.find(f"{J}transclude").get("target"),
            "urn:x-opensiddur:text:bible:nahum/2/2/b-2/3/a",
        )

    def test_a_range_from_a_half_verse_to_a_whole_verse_is_stated_absolutely(self):
        """A relative range end always lands at the start's depth, so it cannot say this."""
        tree = self._tree("emor", {3: _passage("nahum", (2, 2, "b"), (2, 5))})
        division = tree.findall(f".//{TEI}div[@n='triennial_3']")[0]
        self.assertEqual(
            division.find(f"{J}transclude").get("target"),
            "urn:x-opensiddur:text:bible:nahum/2/2/b-/2/5",
        )


class TestCitation(unittest.TestCase):
    """build._citation/_citation_range: the "<book> <chapter>:<verse>-..." string a haftarah
    or festival reading's citation milestone carries (see TestPassageCitationMilestones)."""

    def test_a_single_verse_span_has_no_dash(self):
        span = ReadingSpan(
            unit="haftarah", label="1",
            start=VerseRef("isaiah", 42, 5), end=VerseRef("isaiah", 42, 5),
        )
        self.assertEqual(build._citation([span]), "ישעיהו 42:5")

    def test_a_multi_verse_span_gives_a_range(self):
        span = ReadingSpan(
            unit="haftarah", label="1",
            start=VerseRef("isaiah", 42, 5), end=VerseRef("isaiah", 43, 10),
        )
        self.assertEqual(build._citation([span]), "ישעיהו 42:5–43:10")

    def test_a_second_span_in_the_same_book_does_not_repeat_the_name(self):
        spans = [
            ReadingSpan(
                unit="haftarah", label="1",
                start=VerseRef("jeremiah", 34, 8), end=VerseRef("jeremiah", 34, 22),
            ),
            ReadingSpan(
                unit="haftarah", label="2",
                start=VerseRef("jeremiah", 33, 25), end=VerseRef("jeremiah", 33, 26),
            ),
        ]
        self.assertEqual(build._citation(spans), "ירמיהו 34:8–34:22; 33:25–33:26")

    def test_a_span_in_a_different_book_restates_the_name(self):
        spans = [
            ReadingSpan(
                unit="haftarah", label="1",
                start=VerseRef("kings_1", 18, 46), end=VerseRef("kings_1", 18, 46),
            ),
            ReadingSpan(
                unit="haftarah", label="2",
                start=VerseRef("malachi", 3, 4), end=VerseRef("malachi", 3, 24),
            ),
        ]
        self.assertEqual(build._citation(spans), "מלכים א 18:46; מלאכי 3:4–3:24")

    def test_a_torah_book_is_named_too(self):
        """Festival aliyot cite a Torah book, not only the haftarah's prophetic ones."""
        self.assertEqual(
            build._citation_range("genesis", VerseRef("genesis", 22, 1), VerseRef("genesis", 22, 24)),
            "בראשית 22:1–22:24",
        )


class TestPassageContiguity(unittest.TestCase):
    """build._is_contiguous decides whether a passage's next span picks up exactly where
    the one before it left off, or whether the reading jumps."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "numverses.json").write_text(
            json.dumps({"Jeremiah": [0] + [30] * 52, "Isaiah": [0] + [30] * 66}),
            encoding="utf-8",
        )

    def test_the_next_verse_of_the_same_book_is_contiguous(self):
        prev = ReadingSpan(
            unit="haftarah", label="1",
            start=VerseRef("isaiah", 42, 1), end=VerseRef("isaiah", 42, 5),
        )
        following = ReadingSpan(
            unit="haftarah", label="2",
            start=VerseRef("isaiah", 42, 6), end=VerseRef("isaiah", 42, 9),
        )
        self.assertTrue(build._is_contiguous(prev, following, self.root))

    def test_a_chapter_boundary_is_still_contiguous(self):
        prev = ReadingSpan(
            unit="haftarah", label="1",
            start=VerseRef("isaiah", 42, 1), end=VerseRef("isaiah", 42, 30),
        )
        following = ReadingSpan(
            unit="haftarah", label="2",
            start=VerseRef("isaiah", 43, 1), end=VerseRef("isaiah", 43, 5),
        )
        self.assertTrue(build._is_contiguous(prev, following, self.root))

    def test_a_backward_jump_is_not_contiguous(self):
        """Mishpatim's haftarah: Jeremiah 34:8-22, then back to 33:25-26."""
        prev = ReadingSpan(
            unit="haftarah", label="1",
            start=VerseRef("jeremiah", 34, 8), end=VerseRef("jeremiah", 34, 22),
        )
        following = ReadingSpan(
            unit="haftarah", label="2",
            start=VerseRef("jeremiah", 33, 25), end=VerseRef("jeremiah", 33, 26),
        )
        self.assertFalse(build._is_contiguous(prev, following, self.root))

    def test_a_skip_ahead_is_not_contiguous(self):
        prev = ReadingSpan(
            unit="haftarah", label="1",
            start=VerseRef("isaiah", 42, 1), end=VerseRef("isaiah", 42, 5),
        )
        following = ReadingSpan(
            unit="haftarah", label="2",
            start=VerseRef("isaiah", 42, 10), end=VerseRef("isaiah", 42, 15),
        )
        self.assertFalse(build._is_contiguous(prev, following, self.root))

    def test_a_change_of_book_is_not_contiguous(self):
        prev = ReadingSpan(
            unit="haftarah", label="1",
            start=VerseRef("isaiah", 42, 1), end=VerseRef("isaiah", 42, 5),
        )
        following = ReadingSpan(
            unit="haftarah", label="2",
            start=VerseRef("jeremiah", 1, 1), end=VerseRef("jeremiah", 1, 5),
        )
        self.assertFalse(build._is_contiguous(prev, following, self.root))


class TestPassageCitationMilestones(unittest.TestCase):
    """_passage_xml (via haftarah_file) opens a passage with a citation, and states one
    again at any span that does not pick up where the one before it left off."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "numverses.json").write_text(
            json.dumps({"Jeremiah": [0] + [30] * 52}), encoding="utf-8",
        )

    def _citations(self, passages) -> list[str]:
        _, document = build.haftarah_file("mishpatim", passages, None, self.root)
        tree = etree.fromstring(document.encode("utf-8"))
        return [m.get("n") for m in tree.iter(f"{TEI}milestone") if m.get("unit") == "citation"]

    def test_a_continuous_passage_gets_one_citation(self):
        passage = _passage("isaiah", (42, 5), (43, 10))
        self.assertEqual(self._citations([passage]), ["ישעיהו 42:5–43:10"])

    def test_a_discontinuous_passage_gets_a_second_citation_at_the_jump(self):
        passage = Passage(
            key="mishpatim",
            spans=[
                ReadingSpan(
                    unit="haftarah", label="1",
                    start=VerseRef("jeremiah", 34, 8), end=VerseRef("jeremiah", 34, 22),
                ),
                ReadingSpan(
                    unit="haftarah", label="2",
                    start=VerseRef("jeremiah", 33, 25), end=VerseRef("jeremiah", 33, 26),
                ),
            ],
        )
        self.assertEqual(
            self._citations([passage]),
            ["ירמיהו 34:8–34:22; 33:25–33:26", "ירמיהו 33:25–33:26"],
        )

    def test_a_contiguous_two_span_passage_gets_only_the_opening_citation(self):
        passage = Passage(
            key="test",
            spans=[
                ReadingSpan(
                    unit="haftarah", label="1",
                    start=VerseRef("jeremiah", 1, 1), end=VerseRef("jeremiah", 1, 5),
                ),
                ReadingSpan(
                    unit="haftarah", label="2",
                    start=VerseRef("jeremiah", 1, 6), end=VerseRef("jeremiah", 1, 10),
                ),
            ],
        )
        self.assertEqual(self._citations([passage]), ["ירמיהו 1:1–1:5; 1:6–1:10"])


class TestBookFile(unittest.TestCase):
    def test_a_pair_is_transcluded_once_by_the_pairs_urn(self):
        parshiyot = [
            Parsha(slug=slug, hebrew_name=slug, book="leviticus", start=_ref(1, 1))
            for slug in ("vayikra", "tazria", "metzora", "emor")
        ]
        _, document = build.book_file("leviticus", parshiyot)
        targets = [
            element.get("target")
            for element in etree.fromstring(document.encode("utf-8")).iter(f"{J}transclude")
        ]
        self.assertEqual(
            [target.rsplit("/", 1)[1] for target in targets],
            ["vayikra", PAIR, "emor"],
        )


class TestIndexFile(unittest.TestCase):
    def test_has_a_title_page_before_the_body(self):
        _, document = build.index_file({})
        root = etree.fromstring(document.encode("utf-8"))
        text = root.find(f"{TEI}text")
        front = text.find(f"{TEI}front")
        self.assertIsNotNone(front)
        self.assertEqual(list(text).index(front), 0)

        doc_title = front.find(f"{TEI}titlePage/{TEI}docTitle")
        self.assertIsNotNone(doc_title)

        main = doc_title.find(f'{TEI}titlePart[@type="main"]')
        self.assertEqual(main.get(f"{XML}lang"), "he")
        self.assertEqual(main.text, "חֻמָּשׁ")

        alt = doc_title.find(f'{TEI}titlePart[@type="alt"]')
        self.assertEqual(alt.get(f"{XML}lang"), "en")
        self.assertEqual(alt.text, "Humash")

    def test_the_source_points_at_the_tanakh_of_miqra(self):
        _, document = build.index_file({})
        root = etree.fromstring(document.encode("utf-8"))
        ptr = root.find(f'.//{TEI}bibl[@{XML}id="source_mam"]/{TEI}ptr')
        self.assertEqual(ptr.get("target"), f"{build.URN_PREFIX}:tanakh@{build.MIQRA_PROJECT}")

    def _body(self, sections: dict) -> object:
        _, document = build.index_file(sections)
        root = etree.fromstring(document.encode("utf-8"))
        return root.find(f"{TEI}text/{TEI}body/{TEI}div")

    def test_the_books_stand_directly_under_the_volume(self):
        body = self._body({})
        targets = [t.get("target") for t in body.findall(f"{J}transclude")]
        self.assertEqual(len(targets), 5)
        self.assertTrue(all("bible:chumash/" in target for target in targets))

    def test_each_group_becomes_a_headed_section(self):
        body = self._body({
            "haftarot": [f"{build.URN_PREFIX}:haftarah/bereshit"],
            "megillot": [f"{build.URN_PREFIX}:megillah/esther"],
            "readings": [f"{build.URN_PREFIX}:reading/pesach_i"],
        })
        sections = body.findall(f"{TEI}div")
        self.assertEqual(
            [section.get("n") for section in sections], ["haftarot", "megillot", "readings"]
        )
        self.assertEqual(
            [section.find(f"{TEI}head").text for section in sections],
            [title for _, title in build.SECTIONS],
        )

    def test_a_section_holds_its_own_readings(self):
        body = self._body({"megillot": [f"{build.URN_PREFIX}:megillah/esther"]})
        section = body.find(f'{TEI}div[@n="megillot"]')
        self.assertEqual(
            [t.get("target") for t in section.findall(f"{J}transclude")],
            [f"{build.URN_PREFIX}:megillah/esther"],
        )

    def test_an_empty_group_gets_no_section(self):
        body = self._body({"haftarot": [], "megillot": [], "readings": []})
        self.assertEqual(body.findall(f"{TEI}div"), [])


class TestMaftirMilestoneTitle(unittest.TestCase):
    """Regression: Sukkot Chol HaMoed's per-day maftir labels ("maftir_day1", etc., after
    readings.festival_readings normalizes them) used to have no entry in ALIYAH_TITLES and
    so fell back to the raw label, which is Latin text with no place inside a Hebrew RTL
    milestone (it prints mirrored, as `readings.py`'s TRIENNIAL_YEARS comment warns).
    """

    def test_ordinary_maftir_is_unchanged(self):
        span = _span(UNIT_MAFTIR, "maftir", (1, 1), (1, 1))
        self.assertEqual(build._milestone_title(span), "מַפְטִיר")

    def test_a_days_maftir_gets_a_hebrew_day_qualified_title(self):
        span = _span(UNIT_MAFTIR, "maftir_day1", (1, 1), (1, 1))
        title = build._milestone_title(span)
        self.assertNotIn("day", title.lower())
        self.assertNotIn("1", title)
        self.assertIn("מַפְטִיר", title)

    def test_each_day_gets_a_distinct_title(self):
        titles = {
            build._milestone_title(_span(UNIT_MAFTIR, f"maftir_day{day}", (1, 1), (1, 1)))
            for day in (1, 2, 3, 4, 5)
        }
        self.assertEqual(len(titles), 5)


class TestCycleQualifier(unittest.TestCase):
    """A triennial division of a single inside a pair belongs to one shape of the cycle.

    The volume declares no cycle, so every shape is kept and the division name alone does not
    tell them apart: in Behar the year-one fourth aliyah opens at 25:11 under one shape and at
    25:14 under another. The qualifier names the shape by the years that read the pair apart,
    which identifies it because the set of those years and the pattern determine one another.
    """

    #: pattern -> the years it reads the pair apart, one per shape a cycle can take.
    EXPECTED = {
        "STT": "א׳",
        "TST": "ב׳",
        "TTS": "ג׳",
        "STS": "א׳ וְג׳",
        "SST": "א׳ וּב׳",
        "TSS": "ב׳ וְג׳",
        "SSS": "בְּכָל הַשָּׁנִים",
    }

    def test_each_pattern_names_the_years_read_apart(self):
        for pattern, expected in self.EXPECTED.items():
            with self.subTest(pattern):
                self.assertEqual(expected, build._shape_name(pattern))

    def test_every_shape_gets_a_distinct_name(self):
        """Two divisions of one pair must never carry the same label."""
        self.assertEqual(
            len(self.EXPECTED), len({build._shape_name(p) for p in self.EXPECTED})
        )

    def test_no_latin_digit_reaches_the_margin(self):
        """A digit set in right-to-left text prints mirrored; see TRIENNIAL_YEARS."""
        for pattern in self.EXPECTED:
            with self.subTest(pattern):
                self.assertFalse(
                    any(c.isascii() and c.isalnum() for c in build._shape_name(pattern))
                )

    #: Every shape that reads Behar–Bechukotai apart in year one, and so has a year-one
    #: division at all. Behar's fourth aliyah opens at 25:11 under three of them and at 25:14
    #: under the fourth.
    YEAR_ONE = {"STT", "STS", "SST", "SSS"}

    def test_a_year_read_apart_alone_is_said_so_rather_than_spelled_out(self):
        self.assertEqual(
            "נִפְרָדוֹת א׳ בִּלְבַד", build._cycle_qualifier({"STT"}, 1, self.YEAR_ONE)
        )

    def test_every_other_shape_is_named_against_it(self):
        """Three shapes named in three words rather than in a clause apiece."""
        self.assertEqual(
            "נִפְרָדוֹת א׳ וְעוֹד",
            build._cycle_qualifier({"STS", "SST", "SSS"}, 1, self.YEAR_ONE),
        )

    def test_the_two_namings_stay_distinct(self):
        """They are opposites, so a reader must never see one where the other belongs."""
        self.assertNotEqual(
            build._cycle_qualifier({"STT"}, 1, self.YEAR_ONE),
            build._cycle_qualifier({"STS", "SST", "SSS"}, 1, self.YEAR_ONE),
        )

    def test_a_group_that_is_neither_is_listed(self):
        self.assertEqual(
            "נִפְרָדוֹת א׳ וְג׳; א׳ וּב׳",
            build._cycle_qualifier({"STS", "SST"}, 1, self.YEAR_ONE),
        )

    def test_a_conditioned_triennial_marker_names_its_cycle(self):
        qualifier = build._cycle_qualifier({"STS"}, 1, self.YEAR_ONE)
        self.assertEqual(
            "א׳ רְבִיעִי (נִפְרָדוֹת א׳ וְג׳)", build._triennial_title("D.1.4", qualifier)
        )

    def test_shapes_that_divide_alike_are_named_together(self):
        """So the label is identical and the exporter sets one marker, not three.

        Behar's year-one fourth aliyah opens at 25:11 under three shapes of the cycle. A reader
        has no use for the distinction between them there; they need it only against the fourth
        shape, which opens the same aliyah three verses later.
        """
        qualifier = build._cycle_qualifier({"STS", "SST", "SSS"}, 1, {"STS", "SST", "SSS", "TSS"})
        self.assertEqual(
            "נִפְרָדוֹת א׳ וְג׳; א׳ וּב׳; בְּכָל הַשָּׁנִים", qualifier
        )

    def test_the_label_uses_only_characters_the_hebrew_font_sets(self):
        """A character the font lacks is set as a blank, not as a fallback glyph.

        Frank Ruehl CLM has no middle dot, which separated the shapes until a build turned up
        530 "Missing character" warnings and a row of gaps where the separators should be.
        """
        allowed = set(" ׳;()") | {chr(c) for c in range(0x0590, 0x0600)}
        for patterns in ({"STS"}, {"STT"}, {"STS", "SST", "SSS"}):
            with self.subTest(sorted(patterns)):
                qualifier = build._cycle_qualifier(patterns, 1, self.YEAR_ONE)
                stray = {c for c in qualifier if c not in allowed}
                self.assertEqual(set(), stray, f"not in the Hebrew font: {stray}")

    def test_the_shape_list_does_not_depend_on_pattern_order(self):
        """Two markers of one division must come out byte-identical to be deduplicated."""
        self.assertEqual(
            build._cycle_qualifier({"SSS", "STS", "SST"}, 1, {"STS", "SST", "SSS", "TSS"}),
            build._cycle_qualifier({"STS", "SST", "SSS"}, 1, {"STS", "SST", "SSS", "TSS"}),
        )

    def test_an_unconditioned_triennial_marker_is_unchanged(self):
        """A parshah always read alone has one division, so there is nothing to tell apart."""
        self.assertEqual("א׳ רְבִיעִי", build._triennial_title("1.4"))

    def test_the_combined_reading_keeps_its_own_suffix(self):
        """Its divisions are unconditioned — the pair read together divides one way."""
        title = build._triennial_title(f"{VARIATION_COMBINED}.1.4")
        self.assertEqual(f"א׳ רְבִיעִי ({build.COMBINED_SUFFIX})", title)


class TestHaftarahOrder(unittest.TestCase):
    """Haftarot follow the order the parshiyot are read, not the order of their slugs.

    The parshiyot here are synthetic, so this holds whatever MAM and hebcal say.
    """

    def _parshiyot(self, *slugs):
        return [
            Parsha(slug=slug, hebrew_name=slug, book="leviticus", start=_ref(1, 1))
            for slug in slugs
        ]

    def test_reading_order_is_kept_rather_than_alphabetical(self):
        parshiyot = self._parshiyot("vayikra", "tzav", "shmini", "emor")
        available = {slug: [] for slug in ("emor", "shmini", "tzav", "vayikra")}
        self.assertEqual(
            build.haftarah_order(parshiyot, available),
            ["vayikra", "tzav", "shmini", "emor"],
        )

    def test_a_pair_follows_both_of_its_members(self):
        parshiyot = self._parshiyot("vayikra", "tazria", "metzora", "emor")
        available = {slug: [] for slug in ("vayikra", "tazria", "metzora", PAIR, "emor")}
        self.assertEqual(
            build.haftarah_order(parshiyot, available),
            ["vayikra", "tazria", "metzora", PAIR, "emor"],
        )

    def test_a_parshah_with_no_haftarah_is_skipped(self):
        parshiyot = self._parshiyot("vayikra", "tzav", "shmini")
        self.assertEqual(
            build.haftarah_order(parshiyot, {"vayikra": [], "shmini": []}),
            ["vayikra", "shmini"],
        )

    def test_a_haftarah_belonging_to_no_parshah_is_kept_at_the_end(self):
        parshiyot = self._parshiyot("vayikra", "tzav")
        order = build.haftarah_order(parshiyot, {"tzav": [], "vayikra": [], "unknown": []})
        self.assertEqual(order, ["vayikra", "tzav", "unknown"])


class TestMegillahFile(unittest.TestCase):
    """A megillah is read whole, but must still name the verses it is made of.

    Asking for the book's own URN would take whichever project stands first in priority order
    and claims that book, whether or not that project has the text — and one that carries only
    the title exists. The verse counts here are synthetic.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "numverses.json").write_text(
            json.dumps({"Esther": [0, 22, 23, 15], "Ruth": [0, 22, 23, 18, 22]}),
            encoding="utf-8",
        )

    def _targets(self, book: str, hebrew: str, holiday: str) -> list[str]:
        _, document = build.megillah_file(book, hebrew, holiday, self.root)
        return [
            element.get("target")
            for element in etree.fromstring(document.encode("utf-8")).iter(f"{J}transclude")
        ]

    def test_the_whole_book_is_transcluded_as_a_verse_range(self):
        targets = self._targets("esther", "אֶסְתֵּר", "purim")
        self.assertEqual(targets[0], f"{build.URN_PREFIX}:esther/1/1-3/15")

    def test_the_books_own_urn_is_not_used(self):
        targets = self._targets("esther", "אֶסְתֵּר", "purim")
        self.assertNotIn(f"{build.URN_PREFIX}:esther", targets)


    def test_esther_is_read_on_the_day_celebrated_as_purim(self):
        esther = next(row for row in build.MEGILLOT if row[0] == "esther")
        _, document = build.megillah_file(*esther, self.root)
        names = {f.get("name") for f in etree.fromstring(document.encode("utf-8")).iter(f"{TEI}f")}
        self.assertEqual(names, {"purim-observed"})

    def test_the_range_ends_on_the_last_verse_of_the_last_chapter(self):
        targets = self._targets("ruth", "רוּת", "shavuot")
        self.assertEqual(targets[0], f"{build.URN_PREFIX}:ruth/1/1-4/22")


class TestVocalizedNames(unittest.TestCase):
    """Titles are pointed. The shared table's names are the form to match source text
    against; a heading wants vowels."""

    def test_every_pointed_name_has_the_same_consonants_as_the_shared_table(self):
        for slug, pointed in names.SLUG_TO_VOCALIZED.items():
            with self.subTest(slug=slug):
                self.assertEqual(
                    normalize_hebrew(pointed),
                    normalize_hebrew(names.SLUG_TO_HEBREW[slug]),
                    f"{pointed!r} is not {names.SLUG_TO_HEBREW[slug]!r} with vowels",
                )

    def test_every_parshah_and_pair_is_pointed(self):
        for slug in names.SLUG_TO_HEBREW:
            with self.subTest(slug=slug):
                self.assertIn(slug, names.SLUG_TO_VOCALIZED)

    def test_a_pair_joins_its_members_pointed_names(self):
        self.assertEqual(
            names.SLUG_TO_VOCALIZED["matot_masei"],
            f"{names.SLUG_TO_VOCALIZED['matot']}–{names.SLUG_TO_VOCALIZED['masei']}",
        )

    def test_an_unknown_slug_falls_back_to_itself(self):
        self.assertEqual(names.vocalized_name("no_such_parshah"), "no_such_parshah")

    def test_every_pointed_book_name_has_the_same_consonants_as_the_table(self):
        from opensiddur.importer.humash.refs import (
            SLUG_TO_HEBREW_BOOK, SLUG_TO_VOCALIZED_BOOK,
        )
        for slug, pointed in SLUG_TO_VOCALIZED_BOOK.items():
            with self.subTest(slug=slug):
                self.assertEqual(
                    normalize_hebrew(pointed), normalize_hebrew(SLUG_TO_HEBREW_BOOK[slug])
                )

    def test_every_book_is_pointed(self):
        from opensiddur.importer.humash.refs import (
            SLUG_TO_HEBREW_BOOK, SLUG_TO_VOCALIZED_BOOK,
        )
        self.assertEqual(set(SLUG_TO_VOCALIZED_BOOK), set(SLUG_TO_HEBREW_BOOK))

    def test_a_book_heading_is_pointed(self):
        from opensiddur.importer.humash.refs import SLUG_TO_VOCALIZED_BOOK
        parshiyot = [
            Parsha(slug="vayikra", hebrew_name="ויקרא", book="leviticus", start=_ref(1, 1))
        ]
        _, document = build.book_file("leviticus", parshiyot)
        heads = [
            element.text
            for element in etree.fromstring(document.encode("utf-8")).iter(f"{TEI}head")
        ]
        self.assertIn(SLUG_TO_VOCALIZED_BOOK["leviticus"], heads)

    def test_a_parshah_heading_is_pointed(self):
        parsha = Parsha(
            slug="tazria", hebrew_name="תזריע", book="leviticus",
            start=_ref(12, 1), end=_ref(13, 17),
            spans=[_span(UNIT_ALIYAH, "1", (12, 1), (13, 17))],
        )
        _, document = build.parsha_file(parsha, {}, None)
        heads = [
            element.text
            for element in etree.fromstring(document.encode("utf-8")).iter(f"{TEI}head")
        ]
        self.assertIn(names.SLUG_TO_VOCALIZED["tazria"], heads)


class TestFestivalHaftarahHeading(unittest.TestCase):
    """A festival's haftarah is a headed division, not a continuation of the maftir."""

    def _heads(self, reading: dict) -> list[str]:
        _, document = build.festival_file("pesach_i", reading, None)
        return [
            element.text
            for element in etree.fromstring(document.encode("utf-8")).iter(f"{TEI}head")
        ]

    def _reading(self, rite, title) -> dict:
        span = _span(UNIT_ALIYAH, "1", (12, 21), (12, 28))
        passage = Passage(
            key="Pesach I",
            spans=[ReadingSpan(
                unit="haftarah", label="1",
                start=VerseRef("joshua", 5, 2), end=VerseRef("joshua", 6, 1),
            )],
            rite=rite,
            title=title,
        )
        return {"name": "Pesach I", "aliyot": [span], "haftarot": [passage]}

    def test_a_single_rite_haftarah_is_still_headed(self):
        self.assertIn(build.HAFTARAH_TITLE, self._heads(self._reading(None, None)))

    def test_a_rite_heading_sits_under_the_haftarah_heading(self):
        heads = self._heads(self._reading("ashkenaz", "מִנְהַג אַשְׁכְּנַז"))
        self.assertIn(build.HAFTARAH_TITLE, heads)
        self.assertIn("מִנְהַג אַשְׁכְּנַז", heads)
        self.assertLess(heads.index(build.HAFTARAH_TITLE), heads.index("מִנְהַג אַשְׁכְּנַז"))

    def test_a_reading_with_no_haftarah_gets_no_haftarah_heading(self):
        reading = {"name": "Pesach I", "aliyot": [_span(UNIT_ALIYAH, "1", (12, 21), (12, 28))],
                   "haftarot": []}
        self.assertNotIn(build.HAFTARAH_TITLE, self._heads(reading))


class TestParshaUrnIsClaimedOnce(unittest.TestCase):
    """A text URN names one stretch of text, so it may be mapped in only one place.

    The file's own div and the parshah milestone cover exactly the same text in a file
    holding one parshah. Naming it on both makes the reference database reject the file —
    and, because indexing abandons a file on the first error, silently drops every other URN
    in it along with the duplicate.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "numverses.json").write_text(
            json.dumps({name: [0] + [40] * 30 for name in
                        ("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy")}),
            encoding="utf-8",
        )

    def _milestones(self, document: str) -> list:
        return list(etree.fromstring(document.encode("utf-8")).iter(f"{TEI}milestone"))

    def _parsha(self, slug: str, hebrew: str) -> Parsha:
        return Parsha(
            slug=slug, hebrew_name=hebrew, book="leviticus",
            start=_ref(12, 1), end=_ref(13, 17),
            spans=[
                _span(UNIT_PARSHA, slug, (12, 1), (13, 17)),
                _span(UNIT_ALIYAH, "1", (12, 1), (13, 17)),
            ],
        )

    def test_a_parshah_read_alone_does_not_name_itself_twice(self):
        _, document = build.parsha_file(self._parsha("tazria", "תזריע"), {}, self.root)
        root = etree.fromstring(document.encode("utf-8"))
        div = root.find(f"{TEI}text/{TEI}body/{TEI}div")
        parsha_urn = div.get("corresp")
        claimed = [
            element.get("corresp")
            for element in root.iter()
            if element.get("corresp") == parsha_urn
        ]
        self.assertEqual(len(claimed), 1, f"{parsha_urn} is claimed {len(claimed)} times")

    def test_the_marker_is_still_emitted(self):
        _, document = build.parsha_file(self._parsha("tazria", "תזריע"), {}, self.root)
        units = [m.get("unit") for m in self._milestones(document)]
        self.assertIn(UNIT_PARSHA, units)

    def test_no_urn_in_a_pair_file_is_claimed_twice(self):
        """In a pair's file the members' URNs differ from the pair's, so they are kept.

        pair_file marks each member itself, so the members carry only their aliyot here.
        """
        tazria = Parsha(
            slug="tazria", hebrew_name="תזריע", book="leviticus",
            start=_ref(12, 1), end=_ref(13, 17),
            spans=[_span(UNIT_ALIYAH, "1", (12, 1), (13, 17))],
        )
        metzora = Parsha(
            slug="metzora", hebrew_name="מצֹרע", book="leviticus",
            start=_ref(14, 1), end=_ref(15, 33),
            spans=[_span(UNIT_ALIYAH, "1", (14, 1), (15, 33))],
        )
        pair = CombinedParsha(
            slug=PAIR, hebrew_name="תזריע–מצֹרע", book="leviticus",
            members=("tazria", "metzora"), start=_ref(12, 1), end=_ref(15, 33),
            spans=[_span(UNIT_ALIYAH_COMBINED, "1", (12, 1), (15, 33))],
        )
        _, document = build.pair_file(pair, [tazria, metzora], {}, {}, self.root)
        claimed = [
            element.get("corresp")
            for element in etree.fromstring(document.encode("utf-8")).iter()
            if element.get("corresp", "").startswith("urn:x-opensiddur:text:")
        ]
        self.assertEqual(len(claimed), len(set(claimed)), sorted(claimed))
        self.assertIn(f"{build.URN_PREFIX}:parsha/tazria", claimed)
