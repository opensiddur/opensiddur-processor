"""Tests for the MAM aliyah parse.

The conversion logic is tested against synthetic MAM-parsed plus files rather than the real
ones, so that the tests do not change meaning when the source data is updated.
"""

import json
import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.humash import aliyot
from opensiddur.importer.humash.names import slug_for_hebrew
from opensiddur.common.versification import NUMBERING_COMMON, NUMBERING_MASORAH
from opensiddur.importer.humash.refs import (
    canonical_ref,
    UNIT_ALIYAH,
    UNIT_ALIYAH_COMBINED,
    UNIT_MAFTIR,
    UNIT_MAFTIR_COMBINED,
    UNIT_WEEKDAY,
    UNIT_WEEKDAY_COMBINED,
    ReadingSpan,
    VerseRef,
    verses_in_chapter,
)
from opensiddur.importer.miqra_al_pi_hamasorah.miqra_plus import PlusFormatError
from opensiddur.tests.importer.miqra_al_pi_hamasorah.support import book39, write_source

HEBREW_NUMERALS = {
    1: "א", 2: "ב", 3: "ג", 4: "ד", 5: "ה", 6: "ו", 7: "ז", 8: "ח", 9: "ט", 10: "י",
    11: "יא", 12: "יב", 13: "יג", 14: "יד", 15: "טו", 16: "טז", 17: "יז", 19: "יט", 20: "כ",
    22: "כב", 25: "כה", 26: "כו", 31: "לא", 32: "לב",
}


TORAH_FILES = (
    ("A1-Genesis.json", "בראשית"),
    ("A2-Exodus.json", "שמות"),
    ("A3-Levit.json", "ויקרא"),
    ("A4-Numbers.json", "במדבר"),
    ("A5-Deuter.json", "דברים"),
)


def _row(book: str, chapter: int, verse: int, documented: bool = False, **params: str):
    """One verse label (column D) carrying an aliyah marker, as MAM-parsed plus has it."""
    # א, the label MAM prints in the margin, is in every marker; the parse does not read it.
    params = {"א": params.get("ב1") or params.get("ב2") or params.get("ב3") or params["ב0"], **params}
    label = {
        "tmpl_name": "מ:פסוק",
        "tmpl_params": {
            "1": book,
            "2": HEBREW_NUMERALS[chapter],
            "3": HEBREW_NUMERALS[verse],
            "עלייה": {"tmpl_name": "מ:עלייה", "tmpl_params": params},
        },
    }
    if documented:
        label = {"tmpl_name": "נוסח", "tmpl_params": {"1": label, "2": "תחילת סדר"}}
    return book, chapter, verse, label


def _write_torah(root: Path, rows) -> None:
    """A synthetic MAM-parsed plus download holding ``rows``: the five Torah files, MAM's
    licence and a manifest."""
    files = {}
    for file_name, book in TORAH_FILES:
        chapters: dict[str, dict[str, list]] = {}
        for row_book, chapter, verse, label in rows:
            if row_book == book:
                chapters.setdefault(str(chapter), {})[str(verse)] = [["__"], [label], ["text"]]
        files[file_name] = [book39(f"ספר {book}", chapters)]
    write_source(root, files)


def _write_verse_counts(root: Path) -> None:
    """A synthetic numverses.json, so the tests do not depend on the downloaded data.

    Index 0 is a placeholder because hebcal numbers chapters from 1. Only the chapters the
    tests reach need to be right.
    """
    genesis = [0] + [31, 25, 24, 26, 32, 22, 24, 22, 29, 32] + [30] * 40
    directory = root / "hebcal_leyning"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "numverses.json").write_text(
        json.dumps({
            "Genesis": genesis,
            "Exodus": [0] + [22] * 40,
            "Leviticus": [0] + [17] * 27,
            "Numbers": [0] + [23] * 36,
            "Deuteronomy": [0] + [22] * 34,
        }),
        encoding="utf-8",
    )


class TestParseParshiyot(unittest.TestCase):
    """Parse a synthetic MAM-parsed plus Torah holding two short parshiyot of Genesis."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        _write_verse_counts(self.root)

    def _write(self, rows) -> None:
        _write_torah(self.root, rows)

    def _parse(self):
        return aliyot.parse_parshiyot(self.root)

    def test_shabbat_aliyot_end_where_the_next_one_starts(self):
        self._write([
            _row("בראשית", 1, 1, ב0="בראשית", ב1="ראשון"),
            _row("בראשית", 2, 4, ב0="בראשית", ב1="שני"),
            _row("בראשית", 6, 9, ב0="נֹח", ב1="ראשון"),
        ])
        parshiyot = self._parse()
        self.assertEqual([p.slug for p in parshiyot], ["bereshit", "noach"])
        bereshit = parshiyot[0]
        first, second = bereshit.spans_in(UNIT_ALIYAH)
        self.assertEqual(first.start, VerseRef("genesis", 1, 1))
        self.assertEqual(first.end, VerseRef("genesis", 2, 3))
        self.assertEqual(second.start, VerseRef("genesis", 2, 4))
        # The last aliyah runs to the end of the parshah, which ends before Noach begins.
        self.assertEqual(second.end, VerseRef("genesis", 6, 8))
        self.assertEqual(bereshit.end, VerseRef("genesis", 6, 8))

    def test_a_span_ending_at_a_chapter_boundary_uses_that_chapters_verse_count(self):
        """Closing a span means stepping back a verse, which may cross into the chapter before."""
        self._write([
            _row("בראשית", 1, 1, ב0="בראשית", ב1="ראשון"),
            _row("בראשית", 2, 1, ב0="בראשית", ב1="שני"),
            _row("בראשית", 6, 9, ב0="נֹח", ב1="ראשון"),
        ])
        first = self._parse()[0].spans_in(UNIT_ALIYAH)[0]
        # Genesis 1 has 31 verses in the fixture, so stepping back from 2:1 lands on 1:31.
        self.assertEqual(first.end, VerseRef("genesis", 1, 31))

    def test_maftir_overlaps_the_seventh_aliyah_instead_of_ending_it(self):
        """The maftir re-reads the close of the parshah, so both run to the same last verse."""
        self._write([
            _row("בראשית", 5, 25, ב0="בראשית", ב1="שביעי"),
            _row("בראשית", 6, 5, ב0="בראשית", ב3="מפטיר"),
            _row("בראשית", 6, 9, ב0="נֹח", ב1="ראשון"),
        ])
        bereshit = self._parse()[0]
        seventh = bereshit.spans_in(UNIT_ALIYAH)[0]
        maftir = bereshit.spans_in(UNIT_MAFTIR)[0]
        self.assertEqual(seventh.start, VerseRef("genesis", 5, 25))
        self.assertEqual(seventh.end, VerseRef("genesis", 6, 8))
        self.assertEqual(maftir.start, VerseRef("genesis", 6, 5))
        self.assertEqual(maftir.end, VerseRef("genesis", 6, 8))
        # The maftir begins inside the seventh aliyah and does not shorten it.
        self.assertGreater(maftir.start, seventh.start)
        self.assertEqual(maftir.end, seventh.end)

    def test_weekday_reading_stops_at_the_end_marker(self):
        """ע"כ ישראל closes the weekday reading rather than opening a fourth aliyah."""
        self._write([
            _row("בראשית", 1, 1, ב0="בראשית", ב1="ראשון", ב2="כהן"),
            _row("בראשית", 1, 6, ב0="בראשית", ב2="לוי"),
            _row("בראשית", 1, 9, ב0="בראשית", ב2="ישראל"),
            _row("בראשית", 1, 14, ב0="בראשית", ב2='ע"כ ישראל'),
            _row("בראשית", 6, 9, ב0="נֹח", ב1="ראשון"),
        ])
        weekday = self._parse()[0].spans_in(UNIT_WEEKDAY)
        self.assertEqual([span.label for span in weekday], ["1", "2", "3"])
        self.assertEqual(weekday[0].start, VerseRef("genesis", 1, 1))
        self.assertEqual(weekday[0].end, VerseRef("genesis", 1, 5))
        self.assertEqual(weekday[2].start, VerseRef("genesis", 1, 9))
        # Ends at 1:13, the verse before the marker — not at the end of the parshah.
        self.assertEqual(weekday[2].end, VerseRef("genesis", 1, 13))

    def test_weekday_and_shabbat_aliyot_do_not_truncate_each_other(self):
        """The two schemes are closed independently, so a weekday start stays inside aliyah 1."""
        self._write([
            _row("בראשית", 1, 1, ב0="בראשית", ב1="ראשון", ב2="כהן"),
            _row("בראשית", 1, 6, ב0="בראשית", ב2="לוי"),
            _row("בראשית", 2, 4, ב0="בראשית", ב1="שני"),
            _row("בראשית", 6, 9, ב0="נֹח", ב1="ראשון"),
        ])
        bereshit = self._parse()[0]
        first_aliyah = bereshit.spans_in(UNIT_ALIYAH)[0]
        self.assertEqual(first_aliyah.end, VerseRef("genesis", 2, 3))
        self.assertEqual(bereshit.spans_in(UNIT_WEEKDAY)[0].end, VerseRef("genesis", 1, 5))

    def test_a_label_wrapped_in_a_documentation_note_is_read(self):
        """MAM documents some labels (נוסח around the מ:פסוק); their markers count too."""
        self._write([
            _row("בראשית", 1, 1, ב0="בראשית", ב1="ראשון"),
            _row("בראשית", 2, 4, documented=True, ב0="בראשית", ב1="שני"),
            _row("בראשית", 6, 9, ב0="נֹח", ב1="ראשון"),
        ])
        second = self._parse()[0].spans_in(UNIT_ALIYAH)[1]
        self.assertEqual(second.start, VerseRef("genesis", 2, 4))

    def test_a_torah_file_that_is_not_the_one_the_manifest_lists_is_refused(self):
        """The download is read through the converter's load_source, with its checks."""
        self._write([_row("בראשית", 1, 1, ב0="בראשית", ב1="ראשון")])
        path = self.root / "miqra_al_pi_hamasorah" / "plus" / "A1-Genesis.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(PlusFormatError, "is not the file"):
            self._parse()

    def test_pointing_and_maqaf_survive_the_name_lookup(self):
        """MAM points its names and writes לך־לך with a maqaf; neither may change the slug."""
        self.assertEqual(slug_for_hebrew("נֹח"), "noach")
        self.assertEqual(slug_for_hebrew("נח"), "noach")
        self.assertEqual(slug_for_hebrew("לך־לך"), "lech_lecha")
        self.assertEqual(slug_for_hebrew("בחֻקֹתי"), "bechukotai")

    def test_unknown_parsha_name_is_rejected_rather_than_guessed(self):
        with self.assertRaises(KeyError):
            slug_for_hebrew("פרשה שאינה קיימת")


class TestParseCombined(unittest.TestCase):
    """The ``ג`` parameters, which divide the week the two parshiyot are read together.

    The fixture is a synthetic Tazria-Metzora: Tazria runs Leviticus 12:1-13:17 and Metzora
    14:1-15:17, and the combined reading deliberately has one aliyah that runs from one into
    the other, which is the case the single parshiyot's divisions cannot express.
    """

    PAIR = "תזריע–מצֹרע"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        _write_verse_counts(self.root)
        rows = [
            _row("ויקרא", 12, 1, ב0="תזריע", ב1="ראשון", ב2="כהן",
                 ג0=self.PAIR, ג1="ראשון", ג2="כהן"),
            _row("ויקרא", 12, 5, ב0="תזריע", ב2="לוי", ג0=self.PAIR, ג2="לוי"),
            _row("ויקרא", 13, 1, ב0="תזריע", ב1="שני", ג0=self.PAIR, ג1="שני"),
            _row("ויקרא", 13, 5, ב0="תזריע", ג0=self.PAIR, ג2='ע"כ ישראל'),
            # No ג1 here: the combined second aliyah carries on past where Metzora begins.
            _row("ויקרא", 14, 1, ב0="מצֹרע", ב1="ראשון", ג0=self.PAIR),
            _row("ויקרא", 14, 5, ב0="מצֹרע", ב1="שני", ג0=self.PAIR, ג1="שלישי"),
            _row("ויקרא", 14, 9, ב0="מצֹרע", ב3="מפטיר", ג0=self.PAIR, ג3="מפטיר"),
            _row("ויקרא", 16, 1, ב0="אחרי מות", ב1="ראשון"),
        ]
        _write_torah(self.root, rows)
        self.parshiyot, self.combined = aliyot.parse_readings(self.root)

    def test_a_pair_covers_both_parshiyot_end_to_end(self):
        self.assertEqual([pair.slug for pair in self.combined], ["tazria_metzora"])
        pair = self.combined[0]
        self.assertEqual(pair.members, ("tazria", "metzora"))
        self.assertEqual(pair.start, VerseRef("leviticus", 12, 1))
        # Metzora's own end, not the last marker's parshah: the pair runs to Achrei Mot.
        self.assertEqual(pair.end, VerseRef("leviticus", 15, 17))

    def test_a_combined_aliyah_may_run_from_one_parshah_into_the_other(self):
        combined = self.combined[0].spans_in(UNIT_ALIYAH_COMBINED)
        self.assertEqual([span.label for span in combined], ["1", "2", "3"])
        self.assertEqual(combined[1].start, VerseRef("leviticus", 13, 1))
        # Metzora begins at 14:1, and this aliyah is not cut there.
        self.assertEqual(combined[1].end, VerseRef("leviticus", 14, 4))
        self.assertEqual(combined[2].end, VerseRef("leviticus", 15, 17))

    def test_the_singles_keep_their_own_divisions(self):
        tazria, metzora = self.parshiyot[0], self.parshiyot[1]
        self.assertEqual([p.slug for p in self.parshiyot[:2]], ["tazria", "metzora"])
        second = tazria.spans_in(UNIT_ALIYAH)[1]
        self.assertEqual(second.start, VerseRef("leviticus", 13, 1))
        # Where the combined aliyah carries on, Tazria's own ends with Tazria.
        self.assertEqual(second.end, VerseRef("leviticus", 13, 17))
        self.assertEqual(metzora.spans_in(UNIT_MAFTIR)[0].start, VerseRef("leviticus", 14, 9))

    def test_the_combined_maftir_runs_to_the_end_of_the_pair(self):
        maftir = self.combined[0].spans_in(UNIT_MAFTIR_COMBINED)
        self.assertEqual(len(maftir), 1)
        self.assertEqual(maftir[0].start, VerseRef("leviticus", 14, 9))
        self.assertEqual(maftir[0].end, VerseRef("leviticus", 15, 17))

    def test_the_combined_weekday_reading_has_its_own_end_marker(self):
        """The pair's ע"כ ישראל is its own, and does not move the singles' weekday reading."""
        combined = self.combined[0].spans_in(UNIT_WEEKDAY_COMBINED)
        self.assertEqual([span.label for span in combined], ["1", "2"])
        self.assertEqual(combined[1].end, VerseRef("leviticus", 13, 4))
        single = self.parshiyot[0].spans_in(UNIT_WEEKDAY)
        self.assertEqual(single[1].end, VerseRef("leviticus", 13, 17))


class TestReadingSpan(unittest.TestCase):
    def test_a_span_may_not_cross_books(self):
        with self.assertRaises(ValueError):
            ReadingSpan(UNIT_ALIYAH, "1", VerseRef("genesis", 50, 1), VerseRef("exodus", 1, 1))

    def test_a_span_may_not_end_before_it_starts(self):
        with self.assertRaises(ValueError):
            ReadingSpan(UNIT_ALIYAH, "1", VerseRef("genesis", 2, 1), VerseRef("genesis", 1, 1))

    def test_range_urn_is_unsuffixed_and_abbreviates_the_end(self):
        start, end = VerseRef("genesis", 1, 1), VerseRef("genesis", 6, 8)
        self.assertEqual(
            start.range_urn(end), "urn:x-opensiddur:text:bible:genesis/1/1-6/8"
        )

    def test_range_urn_refuses_to_cross_books(self):
        with self.assertRaises(ValueError):
            VerseRef("genesis", 50, 26).range_urn(VerseRef("exodus", 1, 1))


class TestCanonicalVerseCounts(unittest.TestCase):
    """Verse counts follow the canonical division of the bible URN space, not hebcal's."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        _write_verse_counts(self.root)

    def test_a_divergent_chapter_is_counted_canonically(self):
        """The canonical count comes from a table, so it needs no source file at all — and it
        is finer than hebcal's, which follows the printed editions."""
        self.assertEqual(verses_in_chapter("exodus", 20, self.root), 26)
        self.assertEqual(verses_in_chapter("deuteronomy", 5, self.root), 33)

    def test_an_ordinary_chapter_comes_from_the_source(self):
        self.assertEqual(verses_in_chapter("genesis", 1, self.root), 31)


class TestCanonicalRefs(unittest.TestCase):
    """References stated in an edition's numbering are converted as they are read."""

    def test_a_mam_reference_below_the_decalogue_is_unchanged(self):
        self.assertEqual(
            canonical_ref(NUMBERING_MASORAH, VerseRef("exodus", 20, 1)),
            VerseRef("exodus", 20, 1),
        )

    def test_a_mam_reference_after_the_decalogue_shifts(self):
        """MAM reads the four short commandments as one verse where canonical has four, so
        everything after them is numbered lower in MAM."""
        self.assertEqual(
            canonical_ref(NUMBERING_MASORAH, VerseRef("exodus", 20, 22)),
            VerseRef("exodus", 20, 26),
        )

    def test_a_merged_verse_opens_at_its_first_canonical_verse(self):
        start = canonical_ref(NUMBERING_MASORAH, VerseRef("exodus", 20, 12))
        end = canonical_ref(NUMBERING_MASORAH, VerseRef("exodus", 20, 12), at_end=True)
        self.assertEqual((start.verse, end.verse), (13, 16))

    def test_a_common_reference_is_converted_too(self):
        """hebcal follows the printed editions, which split אנכי but merge the four."""
        self.assertEqual(
            canonical_ref(NUMBERING_COMMON, VerseRef("exodus", 20, 23)),
            VerseRef("exodus", 20, 26),
        )


if __name__ == "__main__":
    unittest.main()
