"""Bein hashmashot: between sunset and nightfall the day has something of both days.

Every feature derived from the date is worked out for the day that is ending and for the one
that is beginning (derived_settings._compute_across_twilight). One on which they agree keeps
its value; one on which they differ holds both, as a TwilightValue, and a condition on it is
decided only if it comes out the same on both days (condition_eval.evaluate_condition).
"""

import unittest
from datetime import date, datetime, timedelta

import hdate
from lxml import etree

from opensiddur.exporter.calendar.compute import SettingSnapshot
from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.condition_eval import (
    TriState,
    evaluate_condition,
    parse_condition_element,
)
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.derived_settings import get_active_setting_entry
from opensiddur.exporter.linear import TwilightValue, get_linear_data, reset_linear_data

NEW_YORK = {"latitude": 40.71, "longitude": -74.01}
J = "http://jewishliturgy.org/ns/jlptei/2"
TEI = "http://www.tei-c.org/ns/1.0"


def _moment(day: date, between: str) -> datetime:
    """A local time on `day` in New York: in the middle of twilight, before it or after it."""
    probe = SettingSnapshot(get_setting=lambda fs_type, feature: (
        {"latitude": NEW_YORK["latitude"], "longitude": NEW_YORK["longitude"]}.get(feature)
        if fs_type == "opensiddur:location" else None))
    zmanim = hdate.Zmanim(day, location=probe.location())
    sunset, nightfall = zmanim.shkia.local, zmanim.tset_hakohavim.local
    return {"twilight": sunset + (nightfall - sunset) / 2,
            "afternoon": sunset - timedelta(hours=1),
            "night": nightfall + timedelta(hours=1)}[between]


class _Lookup:
    def __init__(self, linear_data):
        self.linear_data = linear_data

    def get_active_setting(self, fs_type, feature_name):
        entry = get_active_setting_entry(self.linear_data, fs_type, feature_name)
        return None if entry is None else entry.value


class TwilightCase(unittest.TestCase):

    def setUp(self):
        reset_linear_data()
        self.addCleanup(reset_linear_data)

    def at(self, day: date, between: str = "twilight"):
        moment = _moment(day, between)
        self.linear_data = get_linear_data()
        CompilerProcessor.load_init_settings(self.linear_data, yaml_to_declaration_entries({
            "opensiddur:gregorian-date": {"year": day.year, "month": day.month, "day": day.day},
            "opensiddur:location": NEW_YORK,
            "opensiddur:time": {"hour": moment.hour, "minute": moment.minute},
        }))

    def value(self, fs_type, feature):
        entry = get_active_setting_entry(self.linear_data, f"opensiddur:{fs_type}", feature)
        return None if entry is None else entry.value

    def both(self, fs_type, feature):
        value = self.value(fs_type, feature)
        self.assertIsInstance(value, TwilightValue, f"{fs_type}/{feature} is {value!r}")
        return value.ending, value.starting

    def condition(self, xml: str) -> TriState:
        element = etree.fromstring(
            f'<j:conditional xmlns:j="{J}" xmlns:tei="{TEI}" xml:id="c">{xml}</j:conditional>')
        return evaluate_condition(parse_condition_element(element), _Lookup(self.linear_data))


class TestFridayTwilight(TwilightCase):
    FRIDAY = date(2026, 10, 16)

    def test_the_day_of_the_week_and_shabbat_hold_both_days(self):
        self.at(self.FRIDAY)
        self.assertEqual((6, 7), self.both("day-of-week", "hebrew-day"))
        self.assertEqual((False, True), self.both("holiday-aggregate", "shabbat"))
        self.assertIs(True, self.value("day-of-week", "bayn-hashmashot"))
        self.assertEqual(6, self.value("day-of-week", "secular-day"))

    def test_a_condition_is_decided_only_if_it_holds_the_same_on_both_days(self):
        self.at(self.FRIDAY)
        day = '<tei:fs type="opensiddur:day-of-week"><tei:f name="hebrew-day">{}</tei:f></tei:fs>'
        self.assertEqual(TriState.UNDEFINED, self.condition(day.format('<tei:numeric value="7"/>')))
        self.assertEqual(TriState.FALSE, self.condition(day.format('<tei:numeric value="3"/>')))
        self.assertEqual(TriState.TRUE,
                         self.condition(day.format('<tei:numeric value="6" max="7"/>')))
        either = (f'<j:any>{day.format("<tei:numeric value=\'6\'/>")}'
                  f'{day.format("<tei:numeric value=\'7\'/>")}</j:any>')
        self.assertEqual(TriState.TRUE, self.condition(either))

    def test_before_sunset_and_after_nightfall_there_is_one_day(self):
        for between, expected in (("afternoon", 6), ("night", 7)):
            with self.subTest(between=between):
                reset_linear_data()
                self.at(self.FRIDAY, between)
                self.assertEqual(expected, self.value("day-of-week", "hebrew-day"))
                self.assertFalse(any(isinstance(entry.value, TwilightValue)
                                     for entry in self.linear_data.conditional_settings))


class TestAnOrdinaryTwilight(TwilightCase):

    def test_only_what_changes_with_the_day_holds_both(self):
        self.at(date(2026, 10, 20))  # a Tuesday, 9 Cheshvan: no festival either side
        self.assertEqual((3, 4), self.both("day-of-week", "hebrew-day"))
        self.assertEqual((9, 10), self.both("hebrew-date", "day"))
        self.assertEqual(8, self.value("hebrew-date", "month"))
        holidays = [entry for entry in self.linear_data.conditional_settings
                    if entry.fs_type == "opensiddur:holiday"]
        self.assertTrue(holidays)
        self.assertFalse(any(isinstance(entry.value, TwilightValue) for entry in holidays))


class TestBoundaries(TwilightCase):

    def test_the_eve_of_rosh_hodesh(self):
        self.at(date(2026, 10, 10))  # 29 Tishrei, the evening that begins 30 Tishrei
        self.assertEqual((29, 30), self.both("hebrew-date", "day"))
        self.assertEqual((0, 1), self.both("holiday", "rosh-hodesh"))

    def test_a_month_boundary(self):
        self.at(date(2026, 10, 11))  # 30 Tishrei, the evening that begins 1 Cheshvan
        self.assertEqual((7, 8), self.both("hebrew-date", "month"))
        self.assertEqual((30, 1), self.both("hebrew-date", "day"))
        self.assertEqual((1, 2), self.both("holiday", "rosh-hodesh"))

    def test_the_eve_of_rosh_hashanah_crosses_the_year(self):
        self.at(date(2026, 9, 11))  # 29 Elul 5786; 5787 is a leap year, 5786 is not
        self.assertEqual((5786, 5787), self.both("hebrew-date", "year"))
        self.assertEqual((False, True), self.both("hebrew-date", "leap-year"))
        self.assertEqual((0, 1), self.both("holiday", "rosh-hashana"))


class TestADeclaredHebrewDate(TwilightCase):

    def test_a_hebrew_date_declared_last_says_which_day_it_is(self):
        """The declaration settles the day, so nothing is worked out for a second one."""
        moment = _moment(date(2026, 4, 2), "twilight")  # 15 Nisan 5786 is 2 April 2026
        self.linear_data = get_linear_data()
        CompilerProcessor.load_init_settings(self.linear_data, yaml_to_declaration_entries({
            "opensiddur:gregorian-date": {"year": 2026, "month": 1, "day": 1},
            "opensiddur:location": NEW_YORK,
            "opensiddur:time": {"hour": moment.hour, "minute": moment.minute},
            "opensiddur:hebrew-date": {"year": 5786, "month": 1, "day": 15},
        }))
        self.assertIs(True, self.value("day-of-week", "bayn-hashmashot"))
        self.assertEqual(15, self.value("hebrew-date", "day"))
        self.assertEqual(1, self.value("holiday", "pesah"))
        self.assertFalse(any(isinstance(entry.value, TwilightValue)
                             for entry in self.linear_data.conditional_settings))


class TestTheDevice(unittest.TestCase):
    """An electronic compile pins a two-day value for the reader's device to read."""

    def test_a_two_day_value_round_trips_through_json(self):
        from opensiddur.exporter.condition_eval import value_from_json, value_to_json
        from opensiddur.exporter.linear import NumericValue, Undefined
        value = TwilightValue(ending=NumericValue(value=6), starting=Undefined)
        encoded = value_to_json(value)
        self.assertEqual({"twilight": [{"num": 6}, None]}, encoded)
        self.assertEqual(value, value_from_json(encoded))


    def test_an_electronic_compile_pins_both_days(self):
        import json
        import tempfile
        from pathlib import Path
        reset_linear_data()
        self.addCleanup(reset_linear_data)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "proj").mkdir()
            (base / "proj" / "doc.xml").write_text(
                f'<tei:TEI xmlns:tei="{TEI}" xmlns:j="{J}" xml:lang="en"><tei:text><tei:body>'
                '<j:conditional xml:id="c"><tei:fs type="opensiddur:holiday-aggregate">'
                '<tei:f name="shabbat"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>'
                '<tei:p>on Shabbat</tei:p><j:endConditional target="#c"/>'
                '</tei:body></tei:text></tei:TEI>')
            linear_data = get_linear_data()
            linear_data.xml_cache.base_path = base
            linear_data.defer_reader_settings = True
            moment = _moment(date(2026, 10, 16), "twilight")
            CompilerProcessor.load_init_settings(linear_data, yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2026, "month": 10, "day": 16},
                "opensiddur:location": NEW_YORK,
                "opensiddur:time": {"hour": moment.hour, "minute": moment.minute},
            }))
            root = CompilerProcessor("proj", "doc.xml").process()
        pinned = root.find(".//{http://jewishliturgy.org/ns/processing}pinned")
        self.assertIsNotNone(pinned)
        self.assertEqual({"twilight": [False, True]},
                         json.loads(pinned.text)["opensiddur:holiday-aggregate"]["shabbat"])


if __name__ == "__main__":
    unittest.main()
