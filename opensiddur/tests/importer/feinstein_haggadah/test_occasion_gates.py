"""The occasions the haggadah's running order gates its parts on (opensiddur-processor#228).

The seder is for the seder nights, and the search for and burning of leaven for the eve of
Pesah. The gates are read off the index and pre-seder bodies the builder emits, and decided
against what the calendar derives for dates of known character -- no project data is read.
"""

import unittest

from lxml import etree

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.feinstein_haggadah.sections import INDEX_CHILDREN
from opensiddur.importer.feinstein_haggadah.tei_builder import section_body
from opensiddur.tests.importer.occasion_support import JERUSALEM, NEW_YORK, CalendarDay

J = "http://jewishliturgy.org/ns/jlptei/2"
TEI = "http://www.tei-c.org/ns/1.0"
NS = {"j": J, "tei": TEI}

TRUE, FALSE = TriState.TRUE, TriState.FALSE


def _gate(slug: str, cond_id: str, lang: str = "he") -> etree.ElementBase:
    body = section_body(slug, None, lang=lang, child_slugs=INDEX_CHILDREN[slug])
    root = etree.fromstring(f'<root xmlns:j="{J}" xmlns:tei="{TEI}">{body}</root>')
    return root.xpath(f".//j:conditional[@xml:id='cond_{cond_id}']", namespaces=NS)[0]


class TestTheGates(unittest.TestCase):

    def test_each_gate_governs_its_section_and_says_nothing_to_the_reader(self):
        for slug, cond_id, child in (("index", "index_seder", "seder"),
                                     ("pre_seder", "pre_seder_bediqat_chametz", "bediqat_chametz"),
                                     ("pre_seder", "pre_seder_biur_chametz", "biur_chametz")):
            for lang in ("he", "en"):
                with self.subTest(cond_id=cond_id, lang=lang):
                    gate = _gate(slug, cond_id, lang)
                    self.assertIsNone(gate.find("tei:note", NS))
                    self.assertIsNone(gate.get("type"))
                    transclude = gate.getnext()
                    self.assertEqual(transclude.tag, f"{{{J}}}transclude")
                    self.assertTrue(transclude.get("target").endswith(":" + child))
                    self.assertEqual(transclude.getnext().get("target"), f"#cond_{cond_id}")


class TestTheGatesAgainstTheCalendar(unittest.TestCase):

    def _assert(self, cond_id: str, slug: str, cases):
        gate = _gate(slug, cond_id)
        for label, day, expected in cases:
            with self.subTest(label):
                self.assertEqual(day.decide(gate), expected)

    def test_the_seder_is_for_the_seder_nights(self):
        self._assert("index_seder", "index", (
            ("first seder, New York", CalendarDay(date=(2026, 4, 1), place=NEW_YORK,
                                                 time=(20, 30)), TRUE),
            ("first seder, Jerusalem", CalendarDay(date=(2026, 4, 1), place=JERUSALEM,
                                                  time=(20, 30)), TRUE),
            ("second seder, New York", CalendarDay(date=(2026, 4, 2), place=NEW_YORK,
                                                  time=(20, 30)), TRUE),
            ("no second seder in Jerusalem", CalendarDay(date=(2026, 4, 2), place=JERUSALEM,
                                                        time=(20, 30)), FALSE),
            ("the day of the first seder, with no time", CalendarDay(date=(2026, 4, 1)), TRUE),
            ("the day before it", CalendarDay(date=(2026, 3, 31)), FALSE),
            ("the third day of Pesah", CalendarDay(date=(2026, 4, 4), place=NEW_YORK), FALSE),
            ("an ordinary day", CalendarDay(date=(2026, 11, 16)), FALSE),
        ))

    def test_leaven_is_searched_for_on_the_night_of_the_fourteenth(self):
        self._assert("pre_seder_bediqat_chametz", "pre_seder", (
            # 14 Nisan 5786 is a Wednesday: searched Tuesday night.
            ("the night of the fourteenth", CalendarDay(date=(2026, 3, 31), place=NEW_YORK,
                                                       time=(20, 30)), TRUE),
            ("the fourteenth", CalendarDay(date=(2026, 4, 1)), TRUE),
            ("the thirteenth", CalendarDay(date=(2026, 3, 31)), FALSE),
            # 14 Nisan 5785 was a Sabbath: searched on the Thursday night before it.
            ("Thursday night when the fourteenth is a Sabbath",
             CalendarDay(date=(2025, 4, 10), place=NEW_YORK, time=(20, 30)), TRUE),
            ("a Sabbath fourteenth", CalendarDay(date=(2025, 4, 12)), FALSE),
            ("the first day of Pesah", CalendarDay(date=(2026, 4, 2)), FALSE),
        ))

    def test_leaven_is_nullified_on_the_fourteenth(self):
        """Burned on the Friday when the 14th is a Sabbath, but the final nullification --
        which is what the section prints -- is said on the Sabbath morning itself."""
        self._assert("pre_seder_biur_chametz", "pre_seder", (
            ("the fourteenth", CalendarDay(date=(2026, 4, 1)), TRUE),
            ("the thirteenth", CalendarDay(date=(2026, 3, 31)), FALSE),
            ("Friday the thirteenth", CalendarDay(date=(2025, 4, 11)), TRUE),
            ("a Sabbath fourteenth", CalendarDay(date=(2025, 4, 12)), TRUE),
            ("the first day of Pesah", CalendarDay(date=(2026, 4, 2)), FALSE),
        ))

if __name__ == "__main__":
    unittest.main()
