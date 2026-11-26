"""The electronic book's calendar (html/assets/calendar.js) derives what the compiler derives.

The JavaScript is a port of calendar/compute.py, of the derivation graph and of the settings
stack in derived_settings.py. Both are run, live, over the same synthetic dates, times and
places, and must agree exactly: there are no expected values here to go stale, only the
compiler's own answers.

The sweeps are sampled, to keep the suite quick. Set $OPENSIDDUR_CALENDAR_SWEEP to `full`
for every day of several years at every place, which takes some minutes.
"""

import json
import logging
import os
import unittest
from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import hdate
import tzfpy
from pyluach import dates as pyluach_dates
from pyluach import parshios

from opensiddur.exporter import derived_settings
from opensiddur.exporter.calendar.compute import (
    _ISRAEL_ZONES,
    ALWAYS_YOM_TOV,
    HOLIDAY_FEATURES,
    TORAH_FEATURES,
)
from opensiddur.exporter.client_settings import is_reader_supplied
from opensiddur.exporter.condition_eval import value_from_json, value_to_json
from opensiddur.exporter.derivation_graph import (
    DERIVATION_SPECS,
    READ_FEATURES,
    topological_derivation_order,
)
from opensiddur.exporter.derived_settings import (
    STATIC_DEFAULTS,
    SettingChangeTrigger,
    recalculate_derived_settings,
)
from opensiddur.exporter.linear import ConditionalSettingEntry, LinearData
from opensiddur.tests.exporter.js_engine import require_node, run_js

FULL = os.environ.get("OPENSIDDUR_CALENDAR_SWEEP") == "full"

SCRIPTS = ("calendar.js",)

#: Long enough for a full sweep under Node.
TIMEOUT = 600 if FULL else 60

GREGORIAN = "opensiddur:gregorian-date"
TIME = "opensiddur:time"
LOCATION = "opensiddur:location"
ISRAEL = "opensiddur:israel"
HEBREW_DATE = "opensiddur:hebrew-date"

#: Places to test at, each with the zone the device gives with it. Reykjavik is far enough
#: north that some zmanim do not happen at all for part of the year.
PLACES = {
    "jerusalem": (31.778, 35.235, "Asia/Jerusalem"),
    "new-york": (40.71, -74.01, "America/New_York"),
    "london": (51.507, -0.128, "Europe/London"),
    "melbourne": (-37.814, 144.963, "Australia/Melbourne"),
    "buenos-aires": (-34.604, -58.382, "America/Argentina/Buenos_Aires"),
    "reykjavik": (64.147, -21.94, "Atlantic/Reykjavik"),
}

#: The zmanim the derivations compare against, by hdate's names.
ZMANIM = {
    "alot": "alot_hashachar",
    "netz": "netz_hachama",
    "sofZmanTfilla": "sof_zman_tfilla_gra",
    "minchaGedola": "mincha_gedola",
    "plag": "plag_hamincha",
    "shkia": "shkia",
    "tzet": "tset_hakohavim",
}

EPOCH = datetime(1970, 1, 1)


def _wall_micros(moment: datetime) -> int:
    """A time as its wall clock reads it, in microseconds from the epoch."""
    return (moment.replace(tzinfo=None) - EPOCH) // timedelta(microseconds=1)


def _jdn(gdate: date) -> int:
    return int(pyluach_dates.GregorianDate(gdate.year, gdate.month, gdate.day).jd + 0.5)


def _days(start: date, end: date, step: int = 1):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=step)


def _canonical(value) -> str:
    """JSON with its types intact, so that true and 1 are told apart."""
    return json.dumps(value, sort_keys=True)


# ── The Python reference ────────────────────────────────────────────────────

def python_derive(entries: list[dict]) -> dict:
    """What the compiler derives from explicit settings, as an electronic book is compiled."""
    linear_data = LinearData(defer_reader_settings=True)
    for index, entry in enumerate(entries):
        linear_data.conditional_settings.append(ConditionalSettingEntry(
            declare_id=f"entry-{index}",
            fs_type=entry["fs"],
            feature_name=entry["feature"],
            value=value_from_json(entry["value"]),
            source=entry.get("source", "declared"),
        ))
    previous = logging.root.manager.disable
    logging.disable(logging.WARNING)
    try:
        recalculate_derived_settings(linear_data, trigger=SettingChangeTrigger.INIT)
    finally:
        logging.disable(previous)
    settings: dict = {}
    for entry in linear_data.conditional_settings:
        settings.setdefault(entry.fs_type, {})[entry.feature_name] = value_to_json(entry.value)
    return settings


def moment_entries(gdate: date | None, clock: time | None, place: str | None,
                   is_israel="derive") -> list[dict]:
    """The settings of a moment at a place: a date, a time, coordinates with their zone."""
    out = []
    if gdate is not None:
        out += [{"fs": GREGORIAN, "feature": f, "value": v}
                for f, v in (("year", gdate.year), ("month", gdate.month), ("day", gdate.day))]
    if clock is not None:
        out += [{"fs": TIME, "feature": "hour", "value": clock.hour},
                {"fs": TIME, "feature": "minute", "value": clock.minute}]
        if clock.second:
            out.append({"fs": TIME, "feature": "second", "value": clock.second})
    if place is not None:
        latitude, longitude, zone = PLACES[place]
        out += [{"fs": LOCATION, "feature": "latitude", "value": latitude},
                {"fs": LOCATION, "feature": "longitude", "value": longitude},
                {"fs": LOCATION, "feature": "timezone", "value": zone}]
    if is_israel != "derive":
        out.append({"fs": ISRAEL, "feature": "is-israel", "value": is_israel})
    return out


def hdate_zmanim(gdate: date, place: str) -> hdate.Zmanim:
    latitude, longitude, zone = PLACES[place]
    return hdate.Zmanim(gdate, location=hdate.Location("", latitude, longitude, ZoneInfo(zone), 0))


# ── The tests ───────────────────────────────────────────────────────────────

class TestReferenceAssumptions(unittest.TestCase):
    """What the port takes for granted about the Python side."""

    def test_hdate_uses_the_noaa_equations(self):
        """The port has NOAA's equations. With astral installed, hdate would use astral's."""
        from hdate import zmanim
        self.assertFalse(zmanim._USE_ASTRAL)

    def test_each_place_is_in_its_zone(self):
        """The device gives the zone with the place; the compiler looks it up. They agree here."""
        for name, (latitude, longitude, zone) in PLACES.items():
            with self.subTest(place=name):
                self.assertEqual(tzfpy.get_tz(longitude, latitude), zone)


class TestConstants(unittest.TestCase):
    def setUp(self):
        self.node = require_node(self)

    def test_the_derivations_are_the_compilers(self):
        js = run_js(self.node, """
            return OSCal.SPECS.map(function (s) {
              return {fs: s.fsType, inputs: s.inputs, name: s.name};
            });""", scripts=SCRIPTS, timeout=TIMEOUT)
        python = [{"fs": s.fs_type, "inputs": sorted(map(list, s.required_inputs)),
                   "name": s.compute.__name__} for s in DERIVATION_SPECS]
        self.assertEqual([{**s, "inputs": sorted(s["inputs"])} for s in js], python)

    def test_the_derivations_run_in_the_compilers_order(self):
        js = run_js(self.node, "return OSCal.ORDER.map(function (s) { return s.name; });",
                    scripts=SCRIPTS, timeout=TIMEOUT)
        self.assertEqual(js, [s.compute.__name__ for s in topological_derivation_order()])

    def test_feature_lists(self):
        js = run_js(self.node, """return {holiday: OSCal.HOLIDAY_FEATURES,
            torah: OSCal.TORAH_FEATURES, alwaysYomTov: OSCal.ALWAYS_YOM_TOV,
            israelZones: OSCal.ISRAEL_ZONES};""", scripts=SCRIPTS, timeout=TIMEOUT)
        self.assertEqual(js["holiday"], list(HOLIDAY_FEATURES))
        self.assertEqual(js["torah"], list(TORAH_FEATURES))
        self.assertEqual(js["alwaysYomTov"], list(ALWAYS_YOM_TOV))
        self.assertEqual(sorted(js["israelZones"]), sorted(_ISRAEL_ZONES))

    def test_static_defaults_of_the_calendar(self):
        """The device pushes the compiler's fixed defaults that are not the reader's."""
        js = run_js(self.node, "return OSCal.STATIC_DEFAULTS;", scripts=SCRIPTS, timeout=TIMEOUT)
        self.assertEqual(js, {fs: values for fs, values in STATIC_DEFAULTS.items()
                              if not is_reader_supplied(fs)})


class TestFeaturesTheDerivationsRead(unittest.TestCase):
    """The device lays a pinned value over what it derives without it, unless a derivation reads
    it (condition.js, Resolver). That holds only if OSCal.READ_FEATURES has every one they do.
    """

    def setUp(self):
        self.node = require_node(self)

    def test_every_feature_read_is_listed(self):
        read: set[tuple[str, str]] = set()
        real = derived_settings._get_setting_from_linear_data

        def recording(linear_data, fs_type, feature_name):
            read.add((fs_type, feature_name))
            return real(linear_data, fs_type, feature_name)

        friday = date(2026, 4, 3)
        hebrew_date = [{"fs": HEBREW_DATE, "feature": f, "value": v}
                       for f, v in (("year", 5786), ("month", 1), ("day", 15))]
        flags = [{"fs": "opensiddur:quorum", "feature": "minyan", "value": True},
                 {"fs": "opensiddur:reading-cycle", "feature": "triennial", "value": True},
                 {"fs": "opensiddur:holiday-aggregate", "feature": "yom-tov", "value": False}]
        cases = [moment_entries(friday, clock, place, locale) + extra
                 for clock in (None, time(9), time(19, 30))
                 for place in ("jerusalem", "new-york", None)
                 for locale in ("derive", None)
                 for extra in ([], hebrew_date, flags)]
        with patch.object(derived_settings, "_get_setting_from_linear_data", recording):
            for case in cases:
                python_derive(case)
        listed = run_js(self.node, "return OSCal.READ_FEATURES;", scripts=SCRIPTS)
        listed = {(fs, name) for fs, names in listed.items() for name in names}
        # The compiler pins the same list, so that what the device derives from has its whole.
        self.assertEqual(listed, set(READ_FEATURES))
        # Between sunset and nightfall, a derivation that gives a feature on one day only reads
        # what the feature is on the other (derived_settings._compute_across_twilight): the
        # festivals a day that is not yom tov cannot be. A pinned value for one of them is
        # explicit, and prevails whatever the merge reads, so laying it over is still exact.
        merged = {("opensiddur:holiday", name) for name in ALWAYS_YOM_TOV}
        self.assertLessEqual(read - merged, listed, sorted(read - merged - listed))


class TestCalendarArithmetic(unittest.TestCase):
    def setUp(self):
        self.node = require_node(self)

    def test_gregorian_to_hebrew(self):
        start, end = (date(1800, 1, 1), date(2240, 12, 31)) if FULL else \
                     (date(1990, 1, 1), date(2060, 12, 31))
        days = list(_days(start, end))
        js = run_js(self.node, """
            var out = [];
            for (var i = 0; i < args.count; i++) {
              var jdn = OSCal.gregorianToJdn(args.year, args.month, args.day) + i;
              var g = OSCal.jdnToGregorian(jdn), h = OSCal.hebrewFromJdn(jdn);
              out.push([jdn, g.year, g.month, g.day, h.year, h.month, h.day,
                        OSCal.hebrew(h.year, h.month, h.day).jdn, OSCal.weekday(jdn)]);
            }
            return out;""",
            {"year": start.year, "month": start.month, "day": start.day, "count": len(days)},
            scripts=SCRIPTS, timeout=TIMEOUT)
        self.assertEqual(len(js), len(days))
        for gdate, row in zip(days, js):
            g = pyluach_dates.GregorianDate(gdate.year, gdate.month, gdate.day)
            h = g.to_heb()
            expected = [_jdn(gdate), gdate.year, gdate.month, gdate.day, h.year, h.month, h.day,
                        _jdn(gdate), h.weekday()]
            if row != expected:
                self.fail(f"{gdate}: JavaScript {row}, Python {expected}")

    def test_weekly_readings(self):
        years = range(5600, 5901) if FULL else range(5770, 5811)
        js = run_js(self.node, """
            var out = {};
            args.forEach(function (year) {
              out[year + "i"] = OSCal.parshaTable(year, true);
              out[year + "d"] = OSCal.parshaTable(year, false);
            });
            return out;""", list(years), scripts=SCRIPTS, timeout=TIMEOUT)
        for year in years:
            for israel in (True, False):
                with self.subTest(year=year, israel=israel):
                    table = parshios.parshatable(year, israel=israel)
                    expected = {str(int(shabbos.jd + 0.5)): reading
                                for shabbos, reading in table.items()}
                    self.assertEqual(js[f"{year}{'i' if israel else 'd'}"], expected)

    def test_days_of_the_calendar(self):
        """Which days are which, as the compiler's calendar library names them."""
        start, end = (date(1990, 9, 1), date(2050, 9, 1)) if FULL else \
                     (date(2022, 9, 1), date(2030, 9, 1))
        days = list(_days(start, end))
        js = run_js(self.node, """
            var first = OSCal.gregorianToJdn(args.year, args.month, args.day);
            var out = [];
            for (var i = 0; i < args.count; i++) {
              var h = OSCal.hebrewFromJdn(first + i);
              out.push([true, false].map(function (israel) {
                return {names: OSCal.calendarDays(h, israel).map(function (d) { return d.name; }),
                        yomTov: OSCal.isYomTov(first + i, israel), omer: OSCal.omerDay(h)};
              }));
            }
            return out;""",
            {"year": start.year, "month": start.month, "day": start.day, "count": len(days)},
            scripts=SCRIPTS, timeout=TIMEOUT)
        self.assertEqual(len(js), len(days))
        for gdate, row in zip(days, js):
            for israel, found in zip((True, False), row):
                info = hdate.HDateInfo(gdate, diaspora=not israel)
                expected = {"names": [h.name for h in info.holidays
                                      if h.name not in _UNREAD_HOLIDAYS],
                            "yomTov": info.is_yom_tov, "omer": info.omer.total_days}
                if found != expected:
                    self.fail(f"{gdate} {'Israel' if israel else 'diaspora'}: "
                              f"JavaScript {found}, Python {expected}")

    def test_zmanim(self):
        start, end = (date(2020, 1, 1), date(2035, 12, 31)) if FULL else \
                     (date(2026, 1, 1), date(2027, 12, 31))
        days = list(_days(start, end, 1 if FULL else 3))
        cases = [[_jdn(d), place] for d in days for place in PLACES]
        js = run_js(self.node, """
            return args.cases.map(function (c) {
              var p = args.places[c[1]];
              return OSCal.zmanim(c[0], {latitude: p[0], longitude: p[1]}, p[2]);
            });""", {"cases": cases, "places": PLACES}, scripts=SCRIPTS, timeout=TIMEOUT)
        self.assertEqual(len(js), len(cases))
        for (jdn, place), found in zip(cases, js):
            gdate = date.fromordinal(jdn - 1721425)
            z = hdate_zmanim(gdate, place)
            expected = {key: _wall_micros(getattr(z, name).local) for key, name in ZMANIM.items()}
            if found != expected:
                self.fail(f"{gdate} at {place}: JavaScript {found}, Python {expected}")


#: Names hdate gives that no derivation reads, and the port therefore does not know.
_UNREAD_HOLIDAYS = frozenset({
    "erev_rosh_hashana", "erev_yom_kippur", "erev_sukkot", "erev_pesach", "erev_shavuot",
    "rosh_chodesh", "family_day", "memorial_day_unknown", "rabin_memorial_day",
    "zeev_zhabotinsky_day",
})


class TestDerivations(unittest.TestCase):
    """The whole of a derivation, settings stack and all, from the same explicit settings."""

    def setUp(self):
        self.node = require_node(self)

    def agree(self, cases: list[tuple[str, list[dict]]]):
        js = run_js(self.node, "return args.map(function (e) { return OSCal.derive(e); });",
                    [case for _, case in cases], scripts=SCRIPTS, timeout=TIMEOUT)
        self.assertEqual(len(js), len(cases))
        for (name, case), found in zip(cases, js):
            expected = python_derive(case)
            if _canonical(found) != _canonical(expected):
                differences = {
                    f"{fs}/{feature}": (found.get(fs, {}).get(feature, "<unset>"),
                                        expected.get(fs, {}).get(feature, "<unset>"))
                    for fs in set(found) | set(expected)
                    for feature in set(found.get(fs, {})) | set(expected.get(fs, {}))
                    if _canonical(found.get(fs, {}).get(feature))
                    != _canonical(expected.get(fs, {}).get(feature))
                }
                self.fail(f"{name}: (JavaScript, Python) differ on {differences}")

    def test_dates(self):
        """Days through three years, each at a place, a time and a locale in turn."""
        clocks = (None, time(7, 0), time(12, 0), time(21, 30))
        locales = ("derive", None, True, False)
        places = list(PLACES)
        cases = []
        step = 1 if FULL else 5
        for index, gdate in enumerate(_days(date(2024, 10, 1), date(2027, 10, 1), step)):
            for turn in range(4 if FULL else 1):
                place = places[(index + turn) % len(places)]
                clock = clocks[(index // len(places) + turn) % len(clocks)]
                locale = locales[(index // (len(places) * len(clocks)) + turn) % len(locales)]
                cases.append((f"{gdate} {clock} {place} is-israel={locale}",
                              moment_entries(gdate, clock, place, locale)))
        self.agree(cases)

    def test_moments_at_the_boundaries(self):
        """A minute either side of each zman, and the minute it falls in."""
        dates = (
            date(2026, 4, 1),    # erev Pesah
            date(2026, 4, 3),    # Friday of Pesah
            date(2026, 9, 11),   # Friday, erev Rosh Hashanah
            date(2026, 9, 20),   # erev Yom Kippur
            date(2026, 10, 2),   # Friday, Hoshana Rabba
            date(2026, 12, 4),   # Friday, erev Hanukkah, and the diaspora's rain
            date(2027, 3, 23),   # Purim
            date(2026, 6, 20),   # a Shabbat near the solstice
        )
        places = list(PLACES)
        cases = []
        for index, gdate in enumerate(dates):
            at = places if FULL else (places[index % 6], places[(index + 3) % 6])
            for place in at:
                z = hdate_zmanim(gdate, place)
                for name in ZMANIM.values():
                    local = getattr(z, name).local
                    for shift in (-60, 0, 60):
                        moment = (local + timedelta(seconds=shift)).replace(second=0, microsecond=0)
                        cases.append((f"{gdate} {name}{shift:+d}s at {place}",
                                      moment_entries(moment.date(), moment.time(), place)))
        self.agree(cases)

    def test_settings_that_are_not_a_moment(self):
        """Dates without a place, Hebrew dates, undefined inputs, and settings given outright."""
        friday = date(2026, 4, 3)
        hebrew_date = [{"fs": HEBREW_DATE, "feature": f, "value": v}
                       for f, v in (("year", 5786), ("month", 1), ("day", 15))]
        cases = [
            ("a date alone", moment_entries(friday, None, None)),
            ("a date and a time without a place", moment_entries(friday, time(20), None)),
            ("a place without a date", moment_entries(None, time(9), "london")),
            ("a Hebrew date alone", hebrew_date),
            ("a Hebrew date with a place",
             moment_entries(None, None, "new-york") + hebrew_date),
            ("a Hebrew date declared after a civil date, in the evening",
             moment_entries(date(2026, 1, 1), time(21), "new-york") + hebrew_date),
            ("a civil date declared after a Hebrew date",
             hebrew_date + moment_entries(date(2026, 1, 1), time(9), "jerusalem")),
            ("a partial Hebrew date after a civil date",
             moment_entries(date(2026, 1, 1), time(9), "jerusalem")
             + [{"fs": HEBREW_DATE, "feature": "day", "value": 20}]),
            ("a Hebrew date that does not exist",
             moment_entries(date(2026, 1, 1), time(9), "jerusalem")
             + [{"fs": HEBREW_DATE, "feature": f, "value": v}
                for f, v in (("year", 5786), ("month", 13), ("day", 1))]),
            ("a civil date that does not exist", moment_entries(date(2026, 2, 1), None, "london")
             + [{"fs": GREGORIAN, "feature": "day", "value": 30}]),
            ("an undefined year", moment_entries(friday, time(9), "london")
             + [{"fs": GREGORIAN, "feature": "year", "value": None}]),
            ("an undefined latitude", moment_entries(friday, time(9), "london")
             + [{"fs": LOCATION, "feature": "latitude", "value": None}]),
            ("a declared number", moment_entries(friday, time(9), "london")
             + [{"fs": GREGORIAN, "feature": "day", "value": {"num": 2}}]),
            ("a holiday given outright", moment_entries(friday, time(9), "london")
             + [{"fs": "opensiddur:holiday", "feature": "pesah", "value": 7}]),
            ("Purim in a walled city", moment_entries(date(2027, 3, 24), time(9), "jerusalem")
             + [{"fs": "opensiddur:purim-observance", "feature": "day", "value": 15}]),
            ("Purim, the day unknown", moment_entries(date(2027, 3, 23), time(9), "new-york")
             + [{"fs": "opensiddur:purim-observance", "feature": "day", "value": None}]),
            ("a triennial volume", moment_entries(date(2026, 3, 14), time(9), "new-york")
             + [{"fs": "opensiddur:reading-cycle", "feature": "triennial", "value": True}]),
            ("a minyan", [{"fs": "opensiddur:quorum", "feature": "minyan", "value": True}]),
            ("not yom tov, and no date",
             [{"fs": "opensiddur:holiday-aggregate", "feature": "yom-tov", "value": False}]),
            ("Ma'ariv, and no date",
             [{"fs": "opensiddur:service-time", "feature": "maariv", "value": True}]),
            ("Friday at bein hashmashot",
             moment_entries(friday, _between_sunset_and_nightfall(friday, "jerusalem"),
                            "jerusalem")),
            ("a seder at bein hashmashot, locale unknown",
             moment_entries(date(2026, 4, 1), _between_sunset_and_nightfall(
                 date(2026, 4, 1), "new-york"), "new-york", None)),
            ("a Hebrew date at bein hashmashot",
             moment_entries(friday, _between_sunset_and_nightfall(friday, "jerusalem"),
                            "jerusalem") + hebrew_date),
            ("a clock change, the hour skipped",
             moment_entries(date(2026, 3, 8), time(2, 30), "new-york")),
            ("a clock change, the hour repeated",
             moment_entries(date(2026, 11, 1), time(1, 30), "new-york")),
            ("seconds", moment_entries(friday, time(19, 2, 30), "jerusalem")),
            ("a zone by another of its names",
             [e if e["feature"] != "timezone" else {**e, "value": "Israel"}
              for e in moment_entries(friday, time(9), "jerusalem")]),
            ("init and declared",
             [{**e, "source": "init"} for e in moment_entries(friday, time(9), "london")]
             + [{"fs": TIME, "feature": "hour", "value": 22}]),
        ]
        self.agree(cases)


class TestPlaceWithoutAZone(unittest.TestCase):
    """The device gives the zone with the place. Without one it knows, the place is unknown.

    The compiler would look the zone up from the coordinates; the device cannot, and reading
    the clock as UTC would derive the wrong hour. So nothing that needs the place is derived.
    """

    def setUp(self):
        self.node = require_node(self)

    def test_no_place_without_a_zone(self):
        friday = date(2026, 4, 3)
        cases = {
            "no zone": [e for e in moment_entries(friday, time(9), "london")
                        if e["feature"] != "timezone"],
            "an unknown zone": [e if e["feature"] != "timezone" else {**e, "value": "Mars/Olympus"}
                                for e in moment_entries(friday, time(9), "london")],
        }
        js = run_js(self.node, "return args.map(function (e) { return OSCal.derive(e); });",
                    list(cases.values()), scripts=SCRIPTS)
        expected = run_js(self.node, "return OSCal.derive(args);",
                          moment_entries(friday, time(9), None), scripts=SCRIPTS)
        for name, found in zip(cases, js):
            with self.subTest(name):
                for fs in ("opensiddur:hebrew-date", "opensiddur:hebrew-time",
                           "opensiddur:service-time", ISRAEL):
                    self.assertEqual(found.get(fs), expected.get(fs), fs)


def _between_sunset_and_nightfall(gdate: date, place: str) -> time:
    z = hdate_zmanim(gdate, place)
    middle = z.shkia.local + (z.tset_hakohavim.local - z.shkia.local) / 2
    return middle.time().replace(microsecond=0)


if __name__ == "__main__":
    unittest.main()
