"""Tests for reading the triennial cycle out of the hebcal data.

These use a synthetic triennial.json rather than the downloaded one, so that they keep their
meaning when hebcal updates its data. The fixture keeps hebcal's shape: a parshah that always
divides the same way holds "years", one that is sometimes read combined with its partner holds
"variations" keyed by variation and cycle year, and the pair itself holds both the combined
division and the table saying which variation each cycle pattern selects.
"""

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from opensiddur.importer.humash import readings
from opensiddur.importer.humash.readings import (
    festival_readings,
    triennial,
    triennial_haftarot,
    triennial_patterns,
)
from opensiddur.importer.humash.refs import UNIT_ALIYAH, UNIT_MAFTIR


def _aliyot(chapter: int) -> dict[str, list[str]]:
    """A whole year's aliyot inside one chapter, so the fixture stays short."""
    return {
        str(index): [f"{chapter}:{index}", f"{chapter}:{index}"] for index in range(1, 8)
    } | {"M": [f"{chapter}:7", f"{chapter}:7"]}


TRIENNIAL_FIXTURE = {
    "Bereshit": {"book": 1, "years": {f"Y.{year}": _aliyot(year) for year in (1, 2, 3)}},
    "Tazria": {
        "book": 3,
        "variations": {
            "A.3": _aliyot(11),
            "B.2": _aliyot(12),
            # An alias: variation C's third year divides exactly as A's does.
            "C.3": "A.3",
        },
    },
    "Metzora": {"book": 3, "variations": {"A.3": _aliyot(21)}},
    "Tazria-Metzora": {
        "book": 3,
        "years": {f"Y.{year}": _aliyot(year) for year in (1, 2, 3)},
        "patterns": {"TTS": "A", "TST": "B", "STT": "C"},
    },
    # Hyphenated, but one parshah rather than a pair, so it has no patterns to read.
    "Lech-Lecha": {"book": 1, "years": {"Y.1": _aliyot(4)}},
}


class TestTriennial(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "triennial.json").write_text(
            json.dumps(TRIENNIAL_FIXTURE), encoding="utf-8"
        )
        # triennial() caches by file name and root, so each test gets a fresh directory.
        self.divisions = triennial(self.root)

    def test_a_parshah_with_no_variation_is_keyed_by_cycle_year_alone(self):
        self.assertEqual(
            sorted(self.divisions["bereshit"]), [(None, 1), (None, 2), (None, 3)]
        )
        spans = self.divisions["bereshit"][(None, 2)]
        self.assertEqual([span.unit for span in spans][:1], ["aliyah.triennial.2"])
        self.assertEqual(spans[-1].unit, "maftir.triennial.2")

    def test_a_variation_is_keyed_by_variation_and_year(self):
        """The twelve that are sometimes doubled were skipped entirely before."""
        self.assertEqual(
            sorted(self.divisions["tazria"]), [("A", 3), ("B", 2), ("C", 3)]
        )

    def test_an_aliased_variation_resolves_to_the_division_it_names(self):
        aliased = self.divisions["tazria"][("C", 3)]
        named = self.divisions["tazria"][("A", 3)]
        self.assertEqual(
            [(str(span.start), str(span.end)) for span in aliased],
            [(str(span.start), str(span.end)) for span in named],
        )

    def test_a_variation_names_its_parshah_in_its_unit_space(self):
        """Both parshiyot of a pair share a file, and their variations may cover one verse."""
        tazria = self.divisions["tazria"][("A", 3)][0]
        metzora = self.divisions["metzora"][("A", 3)][0]
        self.assertEqual(tazria.unit, "aliyah.triennial.tazria.A.3")
        self.assertEqual(metzora.unit, "aliyah.triennial.metzora.A.3")
        self.assertEqual(tazria.owner, "tazria")

    def test_the_combined_reading_is_keyed_by_the_pairs_slug(self):
        pair = self.divisions["tazria_metzora"]
        self.assertEqual(
            sorted(pair), [("combined", 1), ("combined", 2), ("combined", 3)]
        )
        span = pair[("combined", 1)][0]
        self.assertEqual(span.unit, "aliyah.triennial.combined.1")
        # The combined reading owns the file it is emitted in, so it names no owner.
        self.assertIsNone(span.owner)


class TestTriennialPatterns(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "triennial.json").write_text(
            json.dumps(TRIENNIAL_FIXTURE), encoding="utf-8"
        )
        self.patterns = triennial_patterns(self.root)

    def test_patterns_are_read_from_the_pair(self):
        self.assertEqual(
            self.patterns["tazria_metzora"], {"TTS": "A", "TST": "B", "STT": "C"}
        )

    def test_a_hyphenated_single_parshah_is_not_taken_for_a_pair(self):
        self.assertNotIn("lech_lecha", self.patterns)


# A synthetic triennial-haft.json in hebcal's shape: a year is one reading object, or a list of
# them where the reading is discontinuous. Every quirk the real file has is represented once.
TRIENNIAL_HAFT_FIXTURE = {
    "Bereshit": {
        "1": {"k": "Isaiah", "b": "42:5", "e": "42:21", "note": "creation"},
        "2": {"k": "Isaiah", "b": "40:25", "e": "40:31"},
        # Discontinuous, and closing with the verse the pairing turns on — which lies inside
        # the piece before it and is not read a second time.
        "3": [
            {"k": "II Kings", "b": "2:1", "e": "2:13"},
            {"k": "II Kings", "b": "2:14", "e": "2:18"},
            {"k": "II Kings", "b": "2:15", "e": "2:16"},
        ],
    },
    # Read alone only in the first two years of a cycle, so it has no third.
    "Tazria": {
        "1": {"k": "Isaiah", "b": "46:3", "e": "46:13"},
        # A boundary inside a verse, and a stray space of the kind the real file has.
        "2": {"k": "Jeremiah", "b": "30:1b", "e": " 30:9a"},
    },
    # Runs backwards, which the haftarot really do and which is not an anchor verse.
    "Noach": {"1": [{"k": "Isaiah", "b": "54:1", "e": "54:10"},
                    {"k": "Isaiah", "b": "53:1", "e": "53:2"}]},
    # In the file but not a parshah, so it has nowhere to go.
    "Tish'a B'Av": {"1": {"k": "Jeremiah", "b": "8:13", "e": "8:23"}},
}


class TestTriennialHaftarot(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "triennial-haft.json").write_text(
            json.dumps(TRIENNIAL_HAFT_FIXTURE), encoding="utf-8"
        )
        self.haftarot = triennial_haftarot(self.root)

    def _spans(self, slug: str, year: int) -> list[tuple[str, str]]:
        return [
            (str(span.start), str(span.end))
            for span in self.haftarot[slug][year].spans
        ]

    def test_each_year_is_keyed_by_plain_cycle_year(self):
        self.assertEqual(sorted(self.haftarot["bereshit"]), [1, 2, 3])

    def test_a_single_reading_object_becomes_one_span(self):
        self.assertEqual(self._spans("bereshit", 1), [("isaiah 42:5", "isaiah 42:21")])

    def test_a_list_of_readings_becomes_a_span_each(self):
        """A list year was dropped entirely before, losing 36 of the 150 readings."""
        self.assertEqual(
            self._spans("bereshit", 3),
            [("kings_2 2:1", "kings_2 2:13"), ("kings_2 2:14", "kings_2 2:18")],
        )

    def test_a_piece_inside_an_earlier_one_is_not_read_again(self):
        self.assertNotIn(("kings_2 2:15", "kings_2 2:16"), self._spans("bereshit", 3))

    def test_a_piece_that_runs_backwards_is_kept(self):
        self.assertEqual(
            self._spans("noach", 1),
            [("isaiah 54:1", "isaiah 54:10"), ("isaiah 53:1", "isaiah 53:2")],
        )

    def test_a_half_verse_boundary_is_kept_on_the_reference(self):
        """The Tanakh projects mark the etnachta, so "30:1b" names a point a URN can reach."""
        span = self.haftarot["tazria"][2].spans[0]
        self.assertEqual((str(span.start), str(span.end)), ("jeremiah 30:1b", "jeremiah 30:9a"))
        self.assertEqual((span.start_half, span.end_half), ("b", "a"))
        self.assertEqual(
            span.start.urn, "urn:x-opensiddur:text:bible:jeremiah/30/1/b"
        )

    def test_a_parshah_read_alone_in_two_years_has_only_those(self):
        self.assertEqual(sorted(self.haftarot["tazria"]), [1, 2])

    def test_an_occasion_that_is_not_a_parshah_is_dropped(self):
        self.assertNotIn("tisha_bav", self.haftarot)
        self.assertEqual(sorted(self.haftarot), ["bereshit", "noach", "tazria"])


HOLIDAY_READINGS_FIXTURE = {
    # Ordinary festival: one maftir, keyed "M".
    "Pesach I": {
        "fullkriyah": {
            "1": {"k": 2, "b": "12:21", "e": "12:28"},
            "M": {"k": 4, "b": "28:16", "e": "28:25"},
        },
    },
    # Sukkot's Chol HaMoed Shabbat: the maftir varies by which intermediate day it is,
    # keyed "M-day1".."M-day5" rather than a plain "M" (real hebcal shape).
    "Sukkot Shabbat Chol ha-Moed": {
        "fullkriyah": {
            "1": {"k": 2, "b": "33:12", "e": "33:16"},
            "M-day1": {"k": 4, "b": "29:17", "e": "29:22"},
            "M-day2": {"k": 4, "b": "29:20", "e": "29:25"},
            "M-day5": {"k": 4, "b": "29:29", "e": "29:34"},
        },
    },
    # A pointer rather than a reading: hebcal names the occasion and says which reading it
    # takes. Real examples are every Rosh Chodesh of a named month, the fast days, and the
    # Israel names for the chol ha-moed days.
    "Pesach III (CH''M)": {"alias": True, "il": True, "key": "Pesach I"},
}


class TestFestivalReadingsMaftir(unittest.TestCase):
    """Regression: Sukkot Chol HaMoed's per-day maftir keys ("M-day1"..) used to fall
    through to UNIT_ALIYAH with the raw, untranslated key kept as the label, which then
    surfaced as backwards-looking raw English ("M-day1") inside an all-Hebrew RTL milestone.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "holiday-readings.json").write_text(
            json.dumps(HOLIDAY_READINGS_FIXTURE), encoding="utf-8"
        )
        self.festivals = festival_readings(self.root)

    def _span(self, occasion: str, label: str):
        spans = self.festivals[occasion]["aliyot"]
        matches = [span for span in spans if span.label == label]
        self.assertEqual(len(matches), 1, f"expected exactly one span labeled {label!r}")
        return matches[0]

    def test_ordinary_single_maftir_is_normalized_to_maftir(self):
        span = self._span("pesach_i", "maftir")
        self.assertEqual(span.unit, UNIT_MAFTIR)

    def test_sukkot_chol_hamoed_day_maftirs_are_recognized_as_maftir(self):
        for day in (1, 2, 5):
            span = self._span("sukkot_shabbat_chol_hamoed", f"maftir_day{day}")
            self.assertEqual(span.unit, UNIT_MAFTIR)

    def test_sukkot_chol_hamoed_day_maftirs_are_not_left_as_raw_source_keys(self):
        labels = {span.label for span in self.festivals["sukkot_shabbat_chol_hamoed"]["aliyot"]}
        self.assertNotIn("M-day1", labels)
        self.assertNotIn("M-day2", labels)
        self.assertNotIn("M-day5", labels)

    def test_sukkot_chol_hamoed_non_maftir_aliyah_is_unaffected(self):
        span = self._span("sukkot_shabbat_chol_hamoed", "1")
        self.assertEqual(span.unit, UNIT_ALIYAH)


class TestHebcalCorrections(unittest.TestCase):
    """The table that repairs references hebcal names to verses that do not exist.

    The data here is synthetic and shaped like the real file, so these keep their meaning
    whether or not hebcal has fixed anything.
    """

    NAME = "triennial-haft.json"

    def setUp(self):
        self.corrections = {
            self.NAME: {("Ki Teitzei", "3", 1, "b"): ("4:20", "48:20")},
        }
        patcher = unittest.mock.patch.object(
            readings, "HEBCAL_CORRECTIONS", self.corrections
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _data(self, value: str) -> dict:
        return {"Ki Teitzei": {"3": [
            {"k": "Isaiah", "b": "48:12", "e": "48:21"},
            {"k": "Isaiah", "b": value, "e": "48:20"},
        ]}}

    def test_the_bad_reference_is_replaced(self):
        data = readings._apply_corrections(self.NAME, self._data("4:20"))
        self.assertEqual(data["Ki Teitzei"]["3"][1]["b"], "48:20")

    def test_a_value_already_corrected_upstream_is_left_alone(self):
        with self.assertNoLogs(readings.logger, "WARNING"):
            data = readings._apply_corrections(self.NAME, self._data("48:20"))
        self.assertEqual(data["Ki Teitzei"]["3"][1]["b"], "48:20")

    def test_an_unrecognized_value_is_kept_and_warned_about(self):
        with self.assertLogs(readings.logger, "WARNING"):
            data = readings._apply_corrections(self.NAME, self._data("49:20"))
        self.assertEqual(data["Ki Teitzei"]["3"][1]["b"], "49:20")

    def test_a_path_that_no_longer_exists_is_warned_about(self):
        with self.assertLogs(readings.logger, "WARNING"):
            readings._apply_corrections(self.NAME, {"Ki Teitzei": {}})

    def test_a_file_with_no_corrections_is_untouched(self):
        data = {"Ki Teitzei": {"3": []}}
        self.assertEqual(readings._apply_corrections("aliyot.json", data), data)


class TestFestivalAliases(unittest.TestCase):
    """An aliased occasion is not a reading of its own.

    Following the pointer would print the same text under another heading; which occasion
    falls on which day is the calendar's business, not a division of the text.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "holiday-readings.json").write_text(
            json.dumps(HOLIDAY_READINGS_FIXTURE), encoding="utf-8"
        )
        self.festivals = festival_readings(self.root)

    def test_an_alias_gets_no_reading_of_its_own(self):
        self.assertNotIn("pesach_iii_(chm)", self.festivals)

    def test_the_reading_it_points_at_is_still_there(self):
        self.assertIn("pesach_i", self.festivals)
        self.assertTrue(self.festivals["pesach_i"]["aliyot"])

    def test_no_reading_is_left_without_content_by_the_alias_rule(self):
        for slug, reading in self.festivals.items():
            with self.subTest(slug=slug):
                self.assertTrue(reading["aliyot"] or reading["haftarot"])
