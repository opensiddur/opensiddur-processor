"""Unit tests for calendar compute adapters."""

import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

import hdate
from pyluach import dates as pyluach_dates
from pyluach import parshios

from opensiddur.exporter.calendar.compute import (
    AGGREGATE_FEATURES,
    FS_GREGORIAN,
    FS_HEBREW_DATE,
    FS_ISRAEL,
    FS_LOCATION,
    FS_PURIM_OBSERVANCE,
    FS_QUORUM,
    FS_TIME,
    HOLIDAY_FEATURES,
    SettingSnapshot,
    _datetime_from_snapshot,
    _map_hdate_holidays,
    compute_day_of_week,
    compute_hebrew_date,
    compute_hebrew_time,
    compute_holiday,
    compute_holiday_aggregate,
    compute_israel,
    compute_location,
    compute_quorum,
    compute_service_time,
    compute_torah_reading,
)
from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.derivation_graph import (
    DERIVATION_SPECS,
    DerivationSpec,
    topological_derivation_order,
)
from opensiddur.exporter.derived_settings import (
    SettingChangeTrigger,
    get_active_setting_entry,
    recalculate_derived_settings,
)
from opensiddur.exporter.linear import (
    NumericValue,
    Undefined,
    get_linear_data,
    reset_linear_data,
)


def _date_only(found: dict) -> dict:
    """The year, month and day. compute_hebrew_date also reports whether the year leaps."""
    return {key: found[key] for key in ("year", "month", "day")}


def _snapshot(data: dict[tuple[str, str], object]) -> SettingSnapshot:
    return SettingSnapshot(
        get_setting=lambda fs_type, feature_name: data.get((fs_type, feature_name)),
    )


class TestRoshHodesh(unittest.TestCase):
    @staticmethod
    def _snap(year, month, day, *, israel=True, hour=None):
        data = {
            (FS_GREGORIAN, "year"): year,
            (FS_GREGORIAN, "month"): month,
            (FS_GREGORIAN, "day"): day,
            (FS_LOCATION, "latitude"): 31.78 if israel else 40.71,
            (FS_LOCATION, "longitude"): 35.22 if israel else -74.01,
            (FS_LOCATION, "timezone"): "Asia/Jerusalem" if israel else "America/New_York",
        }
        if hour is not None:
            data[(FS_TIME, "hour")] = hour
            data[(FS_TIME, "minute")] = 0
        return _snapshot(data)

    def test_shemini_atzeret_and_simchat_torah_day_numbers(self):
        for israel in (True, False):
            for day in (21, 22, 23, 24):
                heb = pyluach_dates.HebrewDate(5786, 7, day)
                greg = heb.to_greg()
                expected = 1 if day == 22 else 2 if day == 23 and not israel else 0
                with self.subTest(israel=israel,day=day):
                    found = compute_holiday(self._snap(greg.year, greg.month, greg.day, israel=israel))
                    self.assertEqual(found["shmini-atzeret"], expected)

    def test_hanukkah_all_eight_days_and_rosh_hodesh_overlap(self):
        # 5784 has a short Kislev; 5786 has a full Kislev.
        for year in (5784, 5786):
            start = pyluach_dates.HebrewDate(year, 9, 25)
            for offset in range(-1, 9):
                heb = start.add(days=offset) if offset >= 0 else start.subtract(days=1)
                greg = heb.to_greg()
                for israel in (True, False):
                    with self.subTest(year=year, offset=offset, israel=israel):
                        found = compute_holiday(self._snap(greg.year, greg.month, greg.day, israel=israel))
                        self.assertEqual(found["hanukkah"], offset + 1 if 0 <= offset < 8 else 0)
                        if heb.day in (1, 30):
                            self.assertGreater(found["rosh-hodesh"], 0)

    def test_every_rosh_hodesh_in_5786(self):
        # Issue #125: all 17 days, with the bounding Rosh Hashanah dates.
        cases = (
            (2025, 9, 23, 0),
            (2025, 10, 22, 1), (2025, 10, 23, 2),
            (2025, 11, 21, 1),
            (2025, 12, 20, 1), (2025, 12, 21, 2),
            (2026, 1, 19, 1),
            (2026, 2, 17, 1), (2026, 2, 18, 2),
            (2026, 3, 19, 1),
            (2026, 4, 17, 1), (2026, 4, 18, 2),
            (2026, 5, 17, 1),
            (2026, 6, 15, 1), (2026, 6, 16, 2),
            (2026, 7, 15, 1),
            (2026, 8, 13, 1), (2026, 8, 14, 2),
            (2026, 9, 12, 0),
        )
        for year, month, day, expected in cases:
            for israel in (True, False):
                with self.subTest(date=(year, month, day), israel=israel):
                    found = compute_holiday(self._snap(year, month, day, israel=israel))
                    self.assertEqual(found["rosh-hodesh"], expected)

    def test_ordinary_days_and_rosh_hashana(self):
        for month, day, rosh_hashana in ((4, 16, 0), (4, 19, 0), (9, 12, 1), (9, 13, 2)):
            with self.subTest(month=month, day=day):
                found = compute_holiday(self._snap(2026, month, day))
                self.assertEqual(found["rosh-hodesh"], 0)
                self.assertEqual(found["rosh-hashana"], rosh_hashana)

    def test_leap_adars_and_variable_month_lengths(self):
        cases = (
            (5784, 11, 30, 1), (5784, 12, 1, 2),  # Adar I
            (5784, 12, 30, 1), (5784, 13, 1, 2),  # Adar II
            (5784, 9, 1, 1), (5784, 10, 1, 1),  # Both preceding months short
            (5785, 8, 30, 1), (5785, 9, 1, 2),
            (5785, 9, 30, 1), (5785, 10, 1, 2),  # Both preceding months long
        )
        for year, month, day, expected in cases:
            with self.subTest(hebrew=(year, month, day)):
                gregorian = pyluach_dates.HebrewDate(year, month, day).to_pydate()
                found = compute_holiday(self._snap(gregorian.year, gregorian.month, gregorian.day))
                self.assertEqual(found["rosh-hodesh"], expected)

    def test_nightfall_enters_advances_and_leaves_rosh_hodesh(self):
        for day, daytime, nighttime in ((16, 0, 1), (17, 1, 2), (18, 2, 0)):
            for hour, expected in ((12, daytime), (23, nighttime)):
                with self.subTest(day=day, hour=hour):
                    found = compute_holiday(self._snap(2026, 4, day, hour=hour))
                    self.assertEqual(found["rosh-hodesh"], expected)

    def test_weekly_torah_flags(self):
        for date, rosh_hodesh, mahar_hodesh in (
            ((2025, 12, 20), True, True),  # Day 1 on Shabbat; day 2 tomorrow
            ((2026, 4, 18), True, False),  # Day 2 on Shabbat
            ((2026, 5, 16), False, True),  # One-day Rosh Hodesh tomorrow
            ((2026, 9, 12), False, False),  # Rosh Hashanah on Shabbat
        ):
            shabbat = pyluach_dates.GregorianDate(*date).to_pydate()
            for days_before in range(7):
                current = shabbat - timedelta(days=days_before)
                with self.subTest(date=current):
                    found = compute_torah_reading(self._snap(current.year, current.month, current.day))
                    self.assertEqual(found["shabbat-rosh-hodesh"], rosh_hodesh)
                    self.assertEqual(found["shabbat-mahar-hodesh"], mahar_hodesh)


class TestSettingSnapshot(unittest.TestCase):
    def test_get_int_coercions(self):
        snap = _snapshot({
            (FS_GREGORIAN, "year"): NumericValue(value=2024),
            (FS_GREGORIAN, "month"): True,
            (FS_GREGORIAN, "day"): 3.0,
        })
        self.assertEqual(snap.get_int(FS_GREGORIAN, "year"), 2024)
        self.assertEqual(snap.get_int(FS_GREGORIAN, "month"), 1)
        self.assertEqual(snap.get_int(FS_GREGORIAN, "day"), 3)

    def test_get_int_narrows_a_fractional_numeric_value(self):
        snap = _snapshot({(FS_GREGORIAN, "day"): NumericValue(value=3.7)})
        self.assertEqual(snap.get_int(FS_GREGORIAN, "day"), 3)

    def test_invalid_gregorian_and_time(self):
        snap = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 2,
            (FS_GREGORIAN, "day"): 30,
        })
        self.assertIsNone(snap.gregorian_date())
        snap2 = _snapshot({
            (FS_TIME, "hour"): 25,
            (FS_TIME, "minute"): 0,
        })
        self.assertIsNone(snap2.time_of_day())

    def test_time_defaults_second_to_zero(self):
        snap = _snapshot({
            (FS_TIME, "hour"): 10,
            (FS_TIME, "minute"): 30,
        })
        self.assertEqual(snap.time_of_day().second, 0)

    def test_israel_and_diaspora(self):
        jerusalem = _snapshot({
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
        })
        self.assertTrue(jerusalem.in_israel())
        nyc = _snapshot({
            (FS_LOCATION, "latitude"): 40.71,
            (FS_LOCATION, "longitude"): -74.01,
        })
        self.assertFalse(nyc.in_israel())
        explicit = _snapshot({(FS_ISRAEL, "is-israel"): True})
        self.assertTrue(explicit.in_israel())
        # Nothing is assumed where nothing is said.
        self.assertIsNone(_snapshot({}).in_israel())

    def test_israel_stops_at_the_border(self):
        for name, lat, lon, israel in (
            ("Eilat", 29.56, 34.95, True),
            ("Metula", 33.28, 35.58, True),
            ("Katzrin", 32.99, 35.69, True),
            ("Hebron", 31.53, 35.10, True),
            ("Amman", 31.95, 35.93, False),
            ("Aqaba", 29.53, 35.00, False),
            ("Tyre", 33.27, 35.20, False),
            ("Quneitra", 33.13, 35.82, False),
        ):
            with self.subTest(place=name):
                snap = _snapshot({(FS_LOCATION, "latitude"): lat, (FS_LOCATION, "longitude"): lon})
                self.assertEqual(snap.in_israel(), israel)
                self.assertEqual(compute_israel(snap), {"is-israel": israel})

    def test_declared_undefined_is_unknown_not_true(self):
        snap = _snapshot({
            (FS_ISRAEL, "is-israel"): Undefined,
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
            (FS_GREGORIAN, "year"): Undefined,
        })
        # Declared unknown: the coordinates are not consulted behind the volume's back.
        self.assertIsNone(snap.in_israel())
        self.assertIsNone(snap.get_bool(FS_ISRAEL, "is-israel"))
        self.assertIsNone(snap.get_int(FS_GREGORIAN, "year"))
        self.assertIsNone(snap.get_float(FS_GREGORIAN, "year"))

    def test_get_bool_reads_strings_as_words(self):
        for raw, expected in (("false", False), ("False", False), ("0", False),
                              ("true", True), (" TRUE ", True), ("1", True), ("maybe", None),
                              (NumericValue(value=0), False), (NumericValue(value=1), True)):
            with self.subTest(raw=raw):
                snap = _snapshot({(FS_ISRAEL, "is-israel"): raw})
                self.assertEqual(snap.get_bool(FS_ISRAEL, "is-israel"), expected)


class TestComputeFunctions(unittest.TestCase):
    def test_hebrew_date_requires_location(self):
        snap = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 10,
            (FS_GREGORIAN, "day"): 3,
        })
        self.assertIsNone(compute_hebrew_date(snap))

    def test_hebrew_date_from_gregorian(self):
        snap = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 10,
            (FS_GREGORIAN, "day"): 3,
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
        })
        result = compute_hebrew_date(snap)
        self.assertEqual(_date_only(result), {"year": 5785, "month": 7, "day": 1})
        # 5785 has twelve months; 5784 had thirteen.
        self.assertFalse(result["leap-year"])

    def test_hebrew_from_explicit_date(self):
        snap = _snapshot({
            (FS_HEBREW_DATE, "year"): 5784,
            (FS_HEBREW_DATE, "month"): 99,
            (FS_HEBREW_DATE, "day"): 1,
        })
        self.assertIsNone(compute_holiday(snap))

    def test_hebrew_time_day_and_night(self):
        base = {
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 10,
            (FS_GREGORIAN, "day"): 3,
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
        }
        morning = _snapshot({**base, (FS_TIME, "hour"): 5, (FS_TIME, "minute"): 0, (FS_TIME, "second"): 0})
        noon = _snapshot({**base, (FS_TIME, "hour"): 12, (FS_TIME, "minute"): 0, (FS_TIME, "second"): 0})
        evening = _snapshot({**base, (FS_TIME, "hour"): 20, (FS_TIME, "minute"): 0, (FS_TIME, "second"): 0})
        self.assertIn("variable-hour", compute_hebrew_time(morning))
        self.assertIn("variable-hour", compute_hebrew_time(noon))
        night = compute_hebrew_time(evening)
        self.assertGreaterEqual(night["variable-hour"], 12)

    def test_day_of_week_bayn_hashmashot(self):
        snap = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 10,
            (FS_GREGORIAN, "day"): 3,
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
            (FS_TIME, "hour"): 18,
            (FS_TIME, "minute"): 30,
            (FS_TIME, "second"): 0,
        })
        result = compute_day_of_week(snap)
        self.assertEqual(result["secular-day"], 5)
        self.assertIn("hebrew-day", result)
        self.assertIn("bayn-hashmashot", result)

    def test_compute_israel(self):
        self.assertEqual(
            compute_israel(_snapshot({
                (FS_LOCATION, "latitude"): 31.78,
                (FS_LOCATION, "longitude"): 35.22,
            })),
            {"is-israel": True},
        )
        self.assertIsNone(compute_israel(_snapshot({})))

    def test_service_time(self):
        snap = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 4,
            (FS_GREGORIAN, "day"): 15,
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
            (FS_TIME, "hour"): 8,
            (FS_TIME, "minute"): 0,
            (FS_TIME, "second"): 0,
        })
        result = compute_service_time(snap)
        self.assertIsNotNone(result)
        self.assertIn("shaharit", result)
        self.assertIn("minha", result)
        self.assertIn("slihot", result)

    def test_service_time_slihot_runs_from_nightfall_to_the_end_of_shaharit(self):
        """Selichot may be said from nightfall -- the first night's are at midnight -- until
        the end of the time for Shacharit (about 9:40 in Jerusalem at the end of September)."""
        def slihot_at(hour):
            return compute_service_time(_snapshot({
                (FS_GREGORIAN, "year"): 2024,
                (FS_GREGORIAN, "month"): 9,
                (FS_GREGORIAN, "day"): 25,
                (FS_LOCATION, "latitude"): 31.78,
                (FS_LOCATION, "longitude"): 35.22,
                (FS_TIME, "hour"): hour,
                (FS_TIME, "minute"): 0,
                (FS_TIME, "second"): 0,
            }))["slihot"]

        self.assertTrue(slihot_at(0))
        self.assertTrue(slihot_at(5))
        self.assertTrue(slihot_at(8))
        self.assertFalse(slihot_at(11))
        self.assertFalse(slihot_at(15))
        self.assertTrue(slihot_at(23))

    def test_service_time_yom_kippur_neila(self):
        snap = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 10,
            (FS_GREGORIAN, "day"): 12,
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
            # Neila runs from plag hamincha (16:59 in Jerusalem this day) until nightfall
            # (18:28), at which point Yom Kippur is over and the date has rolled to the next
            # day. Times are local to opensiddur:location.
            (FS_TIME, "hour"): 17,
            (FS_TIME, "minute"): 30,
            (FS_TIME, "second"): 0,
        })
        result = compute_service_time(snap)
        self.assertTrue(result["neila"])

    def test_service_time_after_nightfall_is_the_next_day(self):
        """Nightfall in Jerusalem is 18:28, so by 19:00 Yom Kippur is over and there is no neila."""
        snap = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 10,
            (FS_GREGORIAN, "day"): 12,
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
            (FS_TIME, "hour"): 19,
            (FS_TIME, "minute"): 0,
            (FS_TIME, "second"): 0,
        })
        self.assertFalse(compute_service_time(snap)["neila"])
        self.assertEqual(compute_holiday(snap)["yom-kippur"], 0)

    def test_torah_reading_special_shabbatot(self):
        snap = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 9,
            (FS_GREGORIAN, "day"): 21,
        })
        result = compute_torah_reading(snap)
        self.assertIn("diaspora-parsha", result)
        self.assertIn("shabbat-shuva", result)
        # 18 Elul: an ordinary Shabbat, so no special reading is selected.
        self.assertFalse(result["shabbat-shuva"])

    def test_triennial_pattern_describes_the_whole_cycle(self):
        """One character per year of the cycle: T where the pair was read together, S apart."""
        snap = _snapshot({
            (FS_GREGORIAN, "year"): 2025,
            (FS_GREGORIAN, "month"): 11,
            (FS_GREGORIAN, "day"): 1,
        })
        result = compute_torah_reading(snap)
        # 5786 opens a cycle. Vayakhel and Pekudei are read together in its first and third
        # years and apart in its second, so only that year's variation of each is read.
        self.assertEqual(result["triennial-pattern-vayakhel-pekudei"], "TST")
        # A pair that always falls together over a cycle needs no variation at all.
        self.assertEqual(result["triennial-pattern-matot-masei"], "TTT")
        self.assertEqual(len(result["triennial-pattern-behar-bechukotai"]), 3)

    def test_triennial_pattern_follows_the_israel_reckoning(self):
        """Israel and the diaspora fall a week apart after a festival on Shabbat."""
        date = {
            (FS_GREGORIAN, "year"): 2025,
            (FS_GREGORIAN, "month"): 11,
            (FS_GREGORIAN, "day"): 1,
        }
        diaspora = compute_torah_reading(_snapshot({**date, (FS_ISRAEL, "is-israel"): False}))
        israel = compute_torah_reading(_snapshot({**date, (FS_ISRAEL, "is-israel"): True}))
        self.assertEqual(diaspora["triennial-pattern-chukat-balak"], "TTS")
        # Chukat and Balak are never combined in Israel.
        self.assertEqual(israel["triennial-pattern-chukat-balak"], "SSS")

    def test_omer_counts_total_days_across_week_boundaries(self):
        from pyluach.dates import HebrewDate
        first = HebrewDate(5786, 1, 16)
        for israel in (False, True):
            for offset in range(-1, 50):
                heb = first.add(days=offset)
                greg = heb.to_greg()
                snapshot = _snapshot({
                    (FS_GREGORIAN, "year"): greg.year,
                    (FS_GREGORIAN, "month"): greg.month,
                    (FS_GREGORIAN, "day"): greg.day,
                    (FS_ISRAEL, "is-israel"): israel,
                    (FS_HEBREW_DATE, "year"): heb.year,
                    (FS_HEBREW_DATE, "month"): heb.month,
                    (FS_HEBREW_DATE, "day"): heb.day,
                })
                with self.subTest(offset=offset, israel=israel):
                    self.assertEqual(compute_holiday(snapshot)["omer"],
                                     offset + 1 if 0 <= offset < 49 else 0)

    def test_holiday_multiday_pesach_and_sukkot(self):
        pesach_ii = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 4,
            (FS_GREGORIAN, "day"): 24,
            (FS_LOCATION, "latitude"): 40.71,
            (FS_LOCATION, "longitude"): -74.01,
        })
        self.assertEqual(compute_holiday(pesach_ii)["pesah"], 2)
        self.assertGreater(compute_holiday(pesach_ii)["omer"], 0)

        sukkot = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 10,
            (FS_GREGORIAN, "day"): 17,
            (FS_LOCATION, "latitude"): 40.71,
            (FS_LOCATION, "longitude"): -74.01,
        })
        self.assertEqual(compute_holiday(sukkot)["sukkot"], 1)

        simchat = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 10,
            (FS_GREGORIAN, "day"): 25,
            (FS_LOCATION, "latitude"): 40.71,
            (FS_LOCATION, "longitude"): -74.01,
        })
        self.assertEqual(compute_holiday(simchat)["shmini-atzeret"], 2)

    def test_holiday_aggregate_chol_hamoed_and_aseret(self):
        chol = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 4,
            (FS_GREGORIAN, "day"): 25,
            (FS_LOCATION, "latitude"): 40.71,
            (FS_LOCATION, "longitude"): -74.01,
        })
        agg = compute_holiday_aggregate(chol)
        self.assertTrue(agg["chol-hamoed"])
        self.assertTrue(agg["regalim"])

        aseret = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 10,
            (FS_GREGORIAN, "day"): 5,
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
        })
        self.assertTrue(compute_holiday_aggregate(aseret)["aseret-ymei-tshuva"])

    def test_map_hdate_holidays_named_branches(self):
        heb = pyluach_dates.HebrewDate(5784, 9, 25)
        for name, feature, expected in (
            ("pesach_vii", "pesah", 7),
            ("pesach_viii", "pesah", 8),
            ("shavuot", "shavuot", 1),
            ("shavuot_ii", "shavuot", 2),
            ("rosh_hashana_ii", "rosh-hashana", 2),
            ("yom_kippur", "yom-kippur", 1),
            ("sukkot_ii", "sukkot", 2),
            ("hoshana_raba", "sukkot", 7),
            ("shmini_atzeret", "shmini-atzeret", 1),
            ("chanuka", "hanukkah", 1),
            ("purim", "purim", 1),
            ("shushan_purim", "shushan-purim", 1),
            ("tzom_tammuz", "tzom-tammuz", 1),
            ("tzom_gedalia", "tzom-gedalia", 1),
            ("asara_btevet", "asara-btevet", 1),
            ("taanit_esther", "taanit-esther", 1),
            ("tisha_bav", "tisha-bav", 1),
            ("tu_bav", "tu-bav", 1),
            ("tu_bshvat", "tu-bishvat", 1),
            ("yom_hashoah", "yom-hashoah", 1),
            ("yom_hazikaron", "yom-hazikaron", 1),
            ("yom_haatzmaut", "yom-haatzmaut", 1),
            ("yom_yerushalayim", "yom-yerushalayim", 1),
            ("lag_bomer", "lag-baomer", 1),
            ("hol_hamoed_pesach", "pesah", 3),
            ("hol_hamoed_sukkot", "sukkot", 3),
        ):
            holiday = MagicMock()
            holiday.name = name
            hi = MagicMock()
            hi.holidays = [holiday]
            hi.omer = None
            mapped = _map_hdate_holidays(hi, heb)
            if name.startswith("hol_hamoed_pesach"):
                self.assertEqual(mapped[feature], heb.day - 14)
            elif name == "chanuka":
                self.assertEqual(mapped[feature], heb.day - 24)
            elif name.startswith("hol_hamoed_sukkot"):
                self.assertEqual(mapped[feature], heb.day - 14)
            else:
                self.assertEqual(mapped[feature], expected)

        hi_omer = MagicMock()
        hi_omer.holidays = []
        hi_omer.omer = MagicMock(total_days=5, day=5)
        self.assertEqual(_map_hdate_holidays(hi_omer, heb)["omer"], 5)

        rh = pyluach_dates.HebrewDate(5785, 1, 1)
        hi_rh = MagicMock()
        hi_rh.holidays = []
        hi_rh.omer = None
        self.assertEqual(_map_hdate_holidays(hi_rh, rh)["rosh-hodesh"], 1)


class TestDerivedSettingsCleanup(unittest.TestCase):
    def test_stale_derived_removed_when_inputs_lost(self):
        reset_linear_data()
        ld = get_linear_data()
        CompilerProcessor.load_init_settings(
            ld,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
                "opensiddur:location": {"latitude": 31.78, "longitude": 35.22},
            }),
        )
        self.assertIsNotNone(get_active_setting_entry(ld, "opensiddur:hebrew-date", "year"))
        ld.conditional_settings = [
            e for e in ld.conditional_settings
            if not (e.fs_type == "opensiddur:location" and e.source == "init")
        ]
        recalculate_derived_settings(ld, trigger=SettingChangeTrigger.END_DECLARE, declare_id="x")
        self.assertIsNone(get_active_setting_entry(ld, "opensiddur:hebrew-date", "year"))


class TestDerivationGraph(unittest.TestCase):
    def test_topological_order_covers_all_specs(self):
        ordered = topological_derivation_order()
        self.assertCountEqual(ordered, DERIVATION_SPECS)

    def test_circular_dependency_raises(self):
        cyclic = (
            DerivationSpec("a:fs", frozenset({("b:fs", "x")}), lambda s: None),
            DerivationSpec("b:fs", frozenset({("a:fs", "x")}), lambda s: None),
        )
        with patch("opensiddur.exporter.derivation_graph.DERIVATION_SPECS", cyclic), patch(
            "opensiddur.exporter.derivation_graph.DERIVED_FS_TYPES",
            frozenset({"a:fs", "b:fs"}),
        ):
            with self.assertRaises(RuntimeError):
                topological_derivation_order()


if __name__ == "__main__":
    unittest.main()


class TestNightfallRollover(unittest.TestCase):
    """The Hebrew day begins in the evening.

    Times throughout these tests are local wall clock readings at the location given, which is
    New York unless stated otherwise: a New York seder at 8:30pm is simply hour 20, minute 30.
    """

    @staticmethod
    def _snap(year, month, day, hour=None, lat=40.71, lon=-74.01):
        data = {
            (FS_GREGORIAN, "year"): year,
            (FS_GREGORIAN, "month"): month,
            (FS_GREGORIAN, "day"): day,
            (FS_LOCATION, "latitude"): lat,
            (FS_LOCATION, "longitude"): lon,
        }
        if hour is not None:
            data[(FS_TIME, "hour")] = hour
            data[(FS_TIME, "minute")] = 0
        return _snapshot(data)

    def test_no_rollover_without_a_time(self):
        """A bare date cannot know whether it is yet evening, so it must not roll."""
        snap = self._snap(2025, 4, 12)
        self.assertEqual(compute_hebrew_date(snap), compute_hebrew_date(self._snap(2025, 4, 12, 10)))

    def test_seder_nights_are_pesah_one_and_two(self):
        """The seders begin after nightfall on the evenings of 12 and 13 April 2025."""
        self.assertEqual(compute_holiday(self._snap(2025, 4, 12, 21))["pesah"], 1)
        self.assertEqual(compute_holiday(self._snap(2025, 4, 13, 21))["pesah"], 2)

    def test_friday_evening_is_shabbat_and_saturday_evening_is_not(self):
        # Nightfall in Jerusalem on these dates is 19:21 and 19:23 local.
        jerusalem = {"lat": 31.78, "lon": 35.22}
        friday_night = compute_holiday_aggregate(self._snap(2025, 4, 11, 20, **jerusalem))
        saturday_night = compute_holiday_aggregate(self._snap(2025, 4, 12, 20, **jerusalem))
        self.assertTrue(friday_night["shabbat"])
        self.assertFalse(friday_night["motzaei-shabbat"])
        self.assertFalse(saturday_night["shabbat"])
        self.assertTrue(saturday_night["motzaei-shabbat"])

    def test_hebrew_day_uses_pyluach_weekday_numbering(self):
        """Saturday is 7. pyluach already numbers Sunday=1..Saturday=7."""
        self.assertEqual(compute_day_of_week(self._snap(2024, 4, 20))["hebrew-day"], 7)


class TestLocalTime(unittest.TestCase):
    """opensiddur:time is a wall clock reading at opensiddur:location, not UTC."""

    @staticmethod
    def _snap(overrides=None):
        """A New York seder, 8:30pm on 1 April 2026 — the case reported in the issue."""
        data = {
            (FS_GREGORIAN, "year"): 2026,
            (FS_GREGORIAN, "month"): 4,
            (FS_GREGORIAN, "day"): 1,
            (FS_TIME, "hour"): 20,
            (FS_TIME, "minute"): 30,
            (FS_LOCATION, "latitude"): 40.71,
            (FS_LOCATION, "longitude"): -74.01,
        }
        data.update(overrides or {})
        return _snapshot(data)

    _JERUSALEM = {(FS_LOCATION, "latitude"): 31.78, (FS_LOCATION, "longitude"): 35.22}

    def test_new_york_seder_at_half_past_eight_is_pesah(self):
        """The reported case: nightfall in New York is 19:36, so 20:30 is already 15 Nisan.

        Read as UTC this is 20:30Z against a 23:36Z nightfall, and the day does not roll.
        """
        snap = self._snap()
        self.assertEqual(_date_only(compute_hebrew_date(snap)),
                         {"year": 5786, "month": 1, "day": 15})
        self.assertEqual(compute_holiday(snap)["pesah"], 1)

    def test_explicit_timezone_overrides_the_coordinates(self):
        snap = self._snap({(FS_LOCATION, "timezone"): "UTC"})
        self.assertEqual(_date_only(compute_hebrew_date(snap)),
                         {"year": 5786, "month": 1, "day": 14})
        self.assertEqual(compute_holiday(snap)["pesah"], 0)

    def test_unknown_timezone_name_falls_back_to_the_coordinates(self):
        snap = self._snap({(FS_LOCATION, "timezone"): "Mars/Olympus_Mons"})
        self.assertEqual(str(snap.timezone()), "America/New_York")

    def test_coordinates_declared_in_jlptei_arrive_as_numeric_values(self):
        """A j:declare puts NumericValue on the stack where YAML puts a plain number."""
        snap = self._snap({
            (FS_LOCATION, "latitude"): NumericValue(value=41),
            (FS_LOCATION, "longitude"): NumericValue(value=-74),
        })
        self.assertEqual(str(snap.timezone()), "America/New_York")
        self.assertEqual(snap.location().latitude, 41.0)
        self.assertEqual(compute_israel(snap), {"is-israel": False})

    def test_fractional_coordinates_declared_in_jlptei(self):
        """Whole degrees are not precise enough: 111 km can cross the Israel boundary."""
        snap = self._snap({
            (FS_LOCATION, "latitude"): NumericValue(value=31.78),
            (FS_LOCATION, "longitude"): NumericValue(value=35.22),
        })
        self.assertEqual(snap.location().latitude, 31.78)
        self.assertEqual(str(snap.timezone()), "Asia/Jerusalem")
        self.assertEqual(compute_israel(snap), {"is-israel": True})

    def test_timezone_is_utc_without_a_location(self):
        snap = _snapshot({(FS_GREGORIAN, "year"): 2026})
        self.assertEqual(snap.timezone().utcoffset(None), timedelta(0))

    def test_compute_location_derives_the_zone_from_the_coordinates(self):
        # Longitude is negative here, so a swapped argument order would not land in New York.
        self.assertEqual(compute_location(self._snap()), {"timezone": "America/New_York"})
        self.assertEqual(compute_location(self._snap(self._JERUSALEM)), {"timezone": "Asia/Jerusalem"})
        tel_aviv = self._snap({(FS_LOCATION, "latitude"): 32.08, (FS_LOCATION, "longitude"): 34.78})
        self.assertEqual(compute_location(tel_aviv), {"timezone": "Asia/Jerusalem"})
        self.assertIsNone(compute_location(_snapshot({})))

    def test_daylight_saving_is_honoured(self):
        """The same wall clock reading is a different instant either side of a transition."""
        summer = self._snap(self._JERUSALEM | {(FS_GREGORIAN, "month"): 7})
        winter = self._snap(self._JERUSALEM | {(FS_GREGORIAN, "month"): 1})
        self.assertEqual(_datetime_from_snapshot(summer).utcoffset(), timedelta(hours=3))
        self.assertEqual(_datetime_from_snapshot(winter).utcoffset(), timedelta(hours=2))


class TestEruvTavshilin(unittest.TestCase):
    @staticmethod
    def _snap(year, month, day):
        return _snapshot({
            (FS_GREGORIAN, "year"): year,
            (FS_GREGORIAN, "month"): month,
            (FS_GREGORIAN, "day"): day,
            (FS_LOCATION, "latitude"): 40.71,
            (FS_LOCATION, "longitude"): -74.01,
            (FS_TIME, "hour"): 10,
            (FS_TIME, "minute"): 0,
        })

    def test_true_when_a_festival_runs_into_shabbat(self):
        # Rosh Hashana 5785 fell on Thursday 3 and Friday 4 October 2024.
        for day in (1, 2, 3, 4):
            with self.subTest(day=day):
                self.assertTrue(compute_holiday_aggregate(self._snap(2024, 10, day))["eruv-tavshilin"])

    def test_false_once_shabbat_has_arrived(self):
        self.assertFalse(compute_holiday_aggregate(self._snap(2024, 10, 5))["eruv-tavshilin"])

    def test_false_when_no_festival_abuts_shabbat(self):
        # Pesah 5785 began on a Sunday, so nothing runs into Shabbat.
        self.assertFalse(compute_holiday_aggregate(self._snap(2025, 4, 10))["eruv-tavshilin"])


class TestQuorumDerivation(unittest.TestCase):
    def test_minyan_implies_zimmun(self):
        self.assertEqual(compute_quorum(_snapshot({(FS_QUORUM, "minyan"): True})), {"zimmun": True})

    def test_nothing_is_derived_without_a_minyan(self):
        """Quorum features stay undefined so that unset conditions are retained, not dropped."""
        self.assertIsNone(compute_quorum(_snapshot({})))
        self.assertIsNone(compute_quorum(_snapshot({(FS_QUORUM, "minyan"): False})))


class TestSpecialShabbatot(unittest.TestCase):
    """The special Shabbatot that select a Torah reading or haftarah of their own.

    Each is defined by the Hebrew date, not by which parshah happens to be read that week, so
    they are computed as "the Shabbat on or before <fixed date>" rather than matched by name.
    """

    def _reading(self, year: int, month: int, day: int) -> dict:
        return compute_torah_reading(_snapshot({
            (FS_GREGORIAN, "year"): year,
            (FS_GREGORIAN, "month"): month,
            (FS_GREGORIAN, "day"): day,
        }))

    def _assert_only(self, gregorian: tuple[int, int, int], *expected: str):
        """Assert exactly `expected` special-Shabbat flags are set on that date."""
        result = self._reading(*gregorian)
        actual = {
            name for name, value in result.items()
            if name.startswith("shabbat-") and value is True
        }
        self.assertEqual(actual, set(expected))

    def test_mevarchim_precedes_first_day_of_rosh_hodesh(self):
        for day, expected in [((2025, 12, 13), True),  # Kislev 23
                              ((2025, 12, 20), False), # Kislev 30, first RH day
                              ((2025, 2, 22), True),  # Shevat 24, RH Fri/Sat
                              ((2025, 3, 1), False),
                              ((2025, 3, 29), True),  # single-day RH Sunday
                              ((2023, 9, 9), False),  # never announce Tishrei
                              ((2023, 9, 16), False)]:
            with self.subTest(day=day):
                self.assertEqual(self._reading(*day)["shabbat-mevarchim"], expected)

    def test_four_parshiyot_in_a_leap_year(self):
        """5784 is a leap year, so these hang off Adar II rather than Adar."""
        self._assert_only((2024, 3, 9), "shabbat-shkalim", "shabbat-mahar-hodesh", "shabbat-mevarchim")
        self._assert_only((2024, 3, 23), "shabbat-zachor")
        self._assert_only((2024, 3, 30), "shabbat-parah")
        self._assert_only((2024, 4, 6), "shabbat-hahodesh", "shabbat-mevarchim")

    def test_four_parshiyot_in_an_ordinary_year(self):
        """5785 is not a leap year, so the same readings hang off Adar."""
        # 1 Adar: Rosh Hodesh Adar is itself Shabbat, so it is also Shabbat Shekalim.
        self._assert_only((2025, 3, 1), "shabbat-shkalim", "shabbat-rosh-hodesh")
        # 8 Adar: Purim falls on the Friday, so Zachor is the Shabbat six days before.
        self._assert_only((2025, 3, 8), "shabbat-zachor")
        self._assert_only((2025, 3, 22), "shabbat-parah")
        # 29 Adar, the last Shabbat before 1 Nisan — which is therefore also Mahar Hodesh.
        self._assert_only((2025, 3, 29), "shabbat-hahodesh", "shabbat-mahar-hodesh", "shabbat-mevarchim")

    def test_shabbat_hagadol_shuva_hazon_and_nahamu(self):
        self._assert_only((2024, 4, 20), "shabbat-hagadol")
        self._assert_only((2024, 10, 5), "shabbat-shuva")
        self._assert_only((2024, 8, 10), "shabbat-hazon")
        self._assert_only((2024, 8, 17), "shabbat-nahamu")

    def test_erev_pesah_on_shabbat_is_shabbat_hagadol(self):
        """In 5785 Erev Pesah is itself Shabbat; ha-Gadol is that day, not the week before."""
        self._assert_only((2025, 4, 12), "shabbat-hagadol")
        self.assertFalse(self._reading(2025, 4, 5)["shabbat-hagadol"])

    def test_shabbat_shira_is_defined_by_the_parshah(self):
        """Shirat ha-Yam is in Beshalach, so this one really does follow the reading."""
        self._assert_only((2024, 1, 27), "shabbat-shira")
        self.assertEqual(self._reading(2024, 1, 27)["diaspora-parsha"], "beshalach")

    def test_shekalim_is_not_matched_by_parshah_name(self):
        """No parshah is called Shekalim; matching on the name left this permanently false."""
        self.assertTrue(self._reading(2024, 3, 9)["shabbat-shkalim"])
        self.assertNotIn("shekalim", self._reading(2024, 3, 9)["diaspora-parsha"])

    def test_a_weekday_selects_the_coming_shabbat(self):
        """A volume compiled midweek must still choose that week's reading."""
        for day in range(1, 7):  # Mon 2024-04-01 through Shabbat ha-Hodesh on the 6th
            with self.subTest(day=day):
                self.assertTrue(self._reading(2024, 4, day)["shabbat-hahodesh"])
        # The following Sunday belongs to the next week and so to the next reading.
        self.assertFalse(self._reading(2024, 4, 7)["shabbat-hahodesh"])

    def test_each_special_shabbat_occurs_once_a_year(self):
        """Sweep whole Hebrew years, leap and ordinary, and count the Shabbatot."""
        names = (
            "shabbat-shkalim", "shabbat-zachor", "shabbat-parah", "shabbat-hahodesh",
            "shabbat-hagadol", "shabbat-hazon", "shabbat-nahamu", "shabbat-shuva",
            "shabbat-shira",
        )
        for hebrew_year in (5784, 5785, 5786, 5787):
            counts = {name: 0 for name in names}
            day = pyluach_dates.HebrewDate(hebrew_year, 7, 1).to_pydate()
            end = pyluach_dates.HebrewDate(hebrew_year + 1, 7, 1).to_pydate()
            while day < end:
                if day.weekday() == 5:  # Saturday
                    result = self._reading(day.year, day.month, day.day)
                    for name in names:
                        counts[name] += bool(result[name])
                day += timedelta(days=1)
            for name in names:
                with self.subTest(hebrew_year=hebrew_year, feature=name):
                    self.assertEqual(counts[name], 1)

    def test_rosh_hodesh_and_mahar_hodesh(self):
        """Both carry their own haftarah, and Mahar Hodesh looks at the following day."""
        rosh_hodesh = self._reading(2025, 3, 1)  # 1 Adar 5785, a Shabbat
        self.assertTrue(rosh_hodesh["shabbat-rosh-hodesh"])
        self.assertFalse(rosh_hodesh["shabbat-mahar-hodesh"])
        # 29 Adar I 5784: Rosh Hodesh Adar II falls the next day.
        mahar_hodesh = self._reading(2024, 3, 9)
        self.assertTrue(mahar_hodesh["shabbat-mahar-hodesh"])
        self.assertFalse(mahar_hodesh["shabbat-rosh-hodesh"])

    def test_triennial_year_cycles_one_to_three(self):
        """The cycle is anchored on 5756, the first year of the modern triennial reading."""
        self.assertEqual(self._reading(2023, 11, 4)["triennial-year"], 2)  # 5784
        self.assertEqual(self._reading(2024, 11, 2)["triennial-year"], 3)  # 5785
        self.assertEqual(self._reading(2025, 11, 1)["triennial-year"], 1)  # 5786
        self.assertEqual(self._reading(2026, 11, 7)["triennial-year"], 2)  # 5787

    def test_triennial_year_turns_over_at_simhat_torah(self):
        """Early Tishrei still reads the outgoing cycle, though the Hebrew year has advanced."""
        # 5785 is cycle year 3, but its first Shabbatot belong to 5784's cycle year 2.
        self.assertEqual(self._reading(2024, 10, 5)["triennial-year"], 2)   # 3 Tishrei, Shuva
        self.assertEqual(self._reading(2024, 10, 12)["triennial-year"], 2)  # 10 Tishrei
        self.assertEqual(self._reading(2024, 10, 19)["triennial-year"], 2)  # 17 Tishrei
        # 24 Tishrei: the first Shabbat past Simhat Torah, which reads Bereshit.
        self.assertEqual(self._reading(2024, 10, 26)["triennial-year"], 3)

    def test_triennial_year_is_continuous_across_every_turnover(self):
        """Sweep Shabbatot with a parshah and assert the cycle advances once per year, in order.

        A turnover keyed to the Hebrew year rather than to Simhat Torah puts the step three
        weeks early, which this catches as a cycle year changing on a Shabbat that reads a
        parshah belonging to the outgoing year.
        """
        previous = None
        day = pyluach_dates.HebrewDate(5784, 7, 1).to_pydate()
        end = pyluach_dates.HebrewDate(5795, 7, 1).to_pydate()
        transitions = 0
        while day < end:
            if day.weekday() == 5:  # Saturday
                g = pyluach_dates.GregorianDate(day.year, day.month, day.day)
                # Festival Shabbatot have no weekly parshah and so select no triennial reading.
                if parshios.getparsha_string(g, israel=False):
                    reading = self._reading(day.year, day.month, day.day)
                    current = reading["triennial-year"]
                    self.assertIn(current, (1, 2, 3))
                    if previous is not None and current != previous:
                        with self.subTest(date=day.isoformat()):
                            # Bereshit is the first parshah of a cycle year, and the step is +1.
                            # pyluach transliterates it "Bereishis".
                            self.assertEqual(current, (previous % 3) + 1)
                            self.assertEqual(reading["diaspora-parsha"], "bereishis")
                        transitions += 1
                    previous = current
            day += timedelta(days=1)
        self.assertEqual(transitions, 11)


class TestRainSeasons(unittest.TestCase):
    """The two rain seasons, which are not the same season.

    Dates are given as the source states the rule: geshem from Shmini Atzeret to the first
    day of Pesach everywhere; tal umatar from 7 Marcheshvan in Israel but only from
    4 December in the diaspora -- 5 December in the year before a Gregorian leap year.
    """

    JERUSALEM = {(FS_LOCATION, "latitude"): 31.78, (FS_LOCATION, "longitude"): 35.22}
    NEW_YORK = {(FS_LOCATION, "latitude"): 40.71, (FS_LOCATION, "longitude"): -74.01}

    def seasons(self, year, month, day, place):
        snapshot = _snapshot({
            (FS_GREGORIAN, "year"): year,
            (FS_GREGORIAN, "month"): month,
            (FS_GREGORIAN, "day"): day,
            **place,
        })
        found = compute_holiday_aggregate(snapshot)
        return found.get("geshem"), found.get("tal-umatar")

    def test_geshem_runs_from_shmini_atzeret_and_is_the_same_everywhere(self):
        # 25 October 2024 is after Shmini Atzeret and before 7 Marcheshvan.
        for place, name in ((self.JERUSALEM, "Israel"), (self.NEW_YORK, "diaspora")):
            with self.subTest(place=name):
                geshem, _ = self.seasons(2024, 10, 25, place)
                self.assertTrue(geshem)

    def test_geshem_ends_at_pesach(self):
        for place, name in ((self.JERUSALEM, "Israel"), (self.NEW_YORK, "diaspora")):
            with self.subTest(place=name):
                geshem, _ = self.seasons(2025, 5, 1, place)
                self.assertFalse(geshem)

    def test_israel_asks_for_rain_from_the_seventh_of_marcheshvan(self):
        # 8 November 2024 is 7 Marcheshvan 5785.
        self.assertTrue(self.seasons(2024, 11, 8, self.JERUSALEM)[1])

    def test_the_diaspora_is_still_asking_for_dew_then(self):
        # The petition follows the agricultural year of the place asking, so the diaspora
        # waits until December however far into the Hebrew winter it is.
        self.assertFalse(self.seasons(2024, 11, 8, self.NEW_YORK)[1])

    def test_the_diaspora_begins_in_december(self):
        self.assertFalse(self.seasons(2024, 12, 3, self.NEW_YORK)[1])
        self.assertTrue(self.seasons(2024, 12, 5, self.NEW_YORK)[1])

    def test_the_year_before_a_leap_year_slips_a_day(self):
        # 2024 is a Gregorian leap year, so the winter opening in December 2023 begins on
        # the evening of the fifth rather than of the fourth.
        self.assertFalse(self.seasons(2023, 12, 5, self.NEW_YORK)[1])
        self.assertTrue(self.seasons(2023, 12, 6, self.NEW_YORK)[1])
        # December 2024 looks ahead to 2025, which is not a leap year.
        self.assertTrue(self.seasons(2024, 12, 5, self.NEW_YORK)[1])

    def test_the_diaspora_begins_at_maariv_on_the_fourth(self):
        """A date with no time is its daytime; the petition begins that evening."""
        def at(day, hour):
            return compute_holiday_aggregate(_snapshot({
                (FS_GREGORIAN, "year"): 2025, (FS_GREGORIAN, "month"): 12,
                (FS_GREGORIAN, "day"): day, (FS_TIME, "hour"): hour, (FS_TIME, "minute"): 0,
                **self.NEW_YORK,
            }))["tal-umatar"]
        self.assertFalse(at(3, 21))   # the evening of the third: not yet
        self.assertFalse(at(4, 12))   # Minhah on the fourth: not yet
        self.assertTrue(at(4, 21))    # Ma'ariv on the fourth: from now
        self.assertFalse(self.seasons(2025, 12, 4, self.NEW_YORK)[1])

    def test_both_seasons_end_at_pesach(self):
        for place, name in ((self.JERUSALEM, "Israel"), (self.NEW_YORK, "diaspora")):
            with self.subTest(place=name):
                self.assertTrue(self.seasons(2025, 1, 15, place)[1])
                self.assertFalse(self.seasons(2025, 5, 1, place)[1])

    def test_the_season_is_left_undefined_rather_than_guessed(self):
        # Without a location there is no telling which rule applies, and an omitted
        # feature evaluates as undefined -- which keeps the text and leaves the marker for
        # a later stage. Guessing would print the wrong season silently.
        snapshot = _snapshot({
            (FS_GREGORIAN, "year"): 2024,
            (FS_GREGORIAN, "month"): 11,
            (FS_GREGORIAN, "day"): 8,
            (FS_HEBREW_DATE, "year"): 5785,
            (FS_HEBREW_DATE, "month"): 8,
            (FS_HEBREW_DATE, "day"): 7,
        })
        found = compute_holiday_aggregate(snapshot)
        self.assertTrue(found["geshem"])          # needs no location
        self.assertIs(found["tal-umatar"], Undefined)  # does



class TestTorahServiceCalendar(unittest.TestCase):
    def test_tammuz_fast_uses_observed_date_and_minor_fast_aggregate(self):
        for year, month, day, fast in ((2026, 7, 2, True), (2026, 7, 3, False),
                                       (2022, 7, 16, False), (2022, 7, 17, True)):
            for israel in (True, False):
                with self.subTest(date=(year, month, day), israel=israel):
                    snap = TestRoshHodesh._snap(year, month, day, israel=israel)
                    self.assertEqual(compute_holiday(snap)["tzom-tammuz"], int(fast))
                    self.assertEqual(compute_holiday_aggregate(snap)["minor-fast"], fast)

    def test_chol_hamoed_boundaries_depend_on_location_and_festival(self):
        for month, last in ((1, 20), (7, 21)):
            for day in (15, 16, 17, 20, 21, 22):
                for israel in (True, False):
                    with self.subTest(month=month, day=day, israel=israel):
                        civil = pyluach_dates.HebrewDate(5786, month, day).to_greg()
                        snap = TestRoshHodesh._snap(civil.year, civil.month, civil.day, israel=israel)
                        expected = (16 if israel else 17) <= day <= last
                        self.assertEqual(compute_holiday_aggregate(snap)["chol-hamoed"], expected)

    def test_gedaliah_fast_uses_library_name_and_observed_date(self):
        for year, month, day, fast in ((2025, 9, 25, True), (2024, 10, 5, False),
                                       (2024, 10, 6, True), (2024, 10, 7, False)):
            with self.subTest(date=(year, month, day)):
                snap = TestRoshHodesh._snap(year, month, day)
                self.assertEqual(compute_holiday(snap)["tzom-gedalia"], int(fast))
                self.assertEqual(compute_holiday_aggregate(snap)["minor-fast"], fast)


def _civil(hebrew_year, month, day, *, israel=True, hour=None, minute=0):
    """A snapshot for a Hebrew date, given as its civil date at Jerusalem or New York."""
    civil = pyluach_dates.HebrewDate(hebrew_year, month, day).to_greg()
    snap = TestRoshHodesh._snap(civil.year, civil.month, civil.day, israel=israel, hour=hour)
    if hour is not None and minute:
        data = {key: snap.get(*key) for key in (
            (FS_GREGORIAN, "year"), (FS_GREGORIAN, "month"), (FS_GREGORIAN, "day"),
            (FS_LOCATION, "latitude"), (FS_LOCATION, "longitude"), (FS_LOCATION, "timezone"),
            (FS_TIME, "hour"))}
        data[(FS_TIME, "minute")] = minute
        snap = _snapshot(data)
    return snap


class TestHolidayCoverage(unittest.TestCase):
    """Every holiday feature is computed on some day, under the name the spec gives it."""

    def test_every_holiday_feature_occurs(self):
        seen = set()
        day = pyluach_dates.HebrewDate(5784, 7, 1).to_greg().to_pydate()
        last = pyluach_dates.HebrewDate(5787, 7, 1).to_greg().to_pydate()
        while day < last:
            for israel in (True, False):
                found = compute_holiday(TestRoshHodesh._snap(day.year, day.month, day.day,
                                                             israel=israel))
                seen.update(name for name, value in found.items() if value)
            day += timedelta(days=1)
        self.assertEqual(set(HOLIDAY_FEATURES) - seen, set())

    def test_days_hdate_names_differently(self):
        self.assertEqual(compute_holiday(_civil(5785, 2, 18))["lag-baomer"], 1)
        self.assertEqual(compute_holiday(_civil(5785, 11, 15))["tu-bishvat"], 1)
        self.assertEqual(compute_holiday(_civil(5785, 2, 28))["yom-yerushalayim"], 1)

    def test_days_hdate_does_not_know(self):
        self.assertEqual(compute_holiday(_civil(5785, 2, 14))["pesah-sheini"], 1)
        self.assertEqual(compute_holiday(_civil(5785, 8, 29))["sigd"], 1)
        # A leap year's first Adar, and only a leap year's.
        self.assertEqual(compute_holiday(_civil(5784, 12, 14))["purim-katan"], 1)
        self.assertEqual(compute_holiday(_civil(5784, 12, 15))["shushan-purim-katan"], 1)
        self.assertEqual(compute_holiday(_civil(5785, 12, 14))["purim-katan"], 0)

    def test_fast_of_the_firstborn_moves_to_thursday_from_shabbat(self):
        self.assertEqual(compute_holiday(_civil(5786, 1, 14))["taanit-bchorot"], 1)
        # 14 Nisan 5785 is Shabbat.
        self.assertEqual(pyluach_dates.HebrewDate(5785, 1, 14).weekday(), 7)
        self.assertEqual(compute_holiday(_civil(5785, 1, 14))["taanit-bchorot"], 0)
        self.assertEqual(compute_holiday(_civil(5785, 1, 12))["taanit-bchorot"], 1)

    def test_purim_meshulash_numbers_its_three_days(self):
        # Shushan Purim 5785 is Shabbat.
        for day, expected in ((13, 0), (14, 1), (15, 2), (16, 3), (17, 0)):
            with self.subTest(day=day):
                self.assertEqual(compute_holiday(_civil(5785, 12, day))["purim-meshulash"],
                                 expected)
        self.assertEqual(compute_holiday(_civil(5786, 12, 15))["purim-meshulash"], 0)


def _celebrating(snap, day):
    """The same snapshot, for a community that celebrates Purim on `day` (None: unknown)."""
    def get_setting(fs_type, feature_name):
        if (fs_type, feature_name) == (FS_PURIM_OBSERVANCE, "day"):
            return day
        return snap.get(fs_type, feature_name)
    return SettingSnapshot(get_setting=get_setting)


class TestPurimObserved(unittest.TestCase):
    """`purim-observed` is the day this community celebrates as Purim."""

    def _observed(self, hebrew_year, month, day, celebrated):
        found = compute_holiday(_celebrating(_civil(hebrew_year, month, day), celebrated))
        return found["purim-observed"]

    def test_the_fourteenth_is_purim_where_purim_is_celebrated_on_it(self):
        self.assertEqual(self._observed(5786, 12, 14, 14), 1)
        self.assertEqual(self._observed(5786, 12, 15, 14), 0)

    def test_the_fifteenth_is_purim_in_a_walled_city(self):
        self.assertEqual(self._observed(5786, 12, 14, 15), 0)
        self.assertEqual(self._observed(5786, 12, 15, 15), 1)

    def test_a_leap_year_celebrates_in_the_second_adar(self):
        self.assertEqual(self._observed(5787, 13, 14, 14), 1)
        self.assertEqual(self._observed(5787, 12, 14, 14), 0)
        self.assertEqual(self._observed(5787, 13, 15, 15), 1)

    def test_an_unknown_day_leaves_either_day_of_purim_undecided(self):
        self.assertIs(self._observed(5786, 12, 14, None), Undefined)
        self.assertIs(self._observed(5786, 12, 15, None), Undefined)

    def test_any_other_day_is_not_purim_wherever_it_is_celebrated(self):
        for celebrated in (14, 15, None):
            with self.subTest(celebrated=celebrated):
                self.assertEqual(self._observed(5786, 12, 13, celebrated), 0)
                self.assertEqual(self._observed(5786, 12, 16, celebrated), 0)

    def test_the_days_themselves_do_not_depend_on_where_purim_is_celebrated(self):
        for celebrated in (14, 15):
            with self.subTest(celebrated=celebrated):
                found = compute_holiday(_celebrating(_civil(5786, 12, 15), celebrated))
                self.assertEqual((found["purim"], found["shushan-purim"]), (0, 1))


class TestAggregateDefinitions(unittest.TestCase):
    def test_tisha_bav_is_not_a_minor_fast(self):
        self.assertFalse(compute_holiday_aggregate(_civil(5785, 5, 9))["minor-fast"])
        self.assertTrue(compute_holiday_aggregate(_civil(5785, 4, 17))["minor-fast"])

    def test_regalim_include_shemini_atzeret_and_simhat_torah(self):
        for israel, days in ((True, (22,)), (False, (22, 23))):
            for day in days:
                with self.subTest(israel=israel, day=day):
                    self.assertTrue(compute_holiday_aggregate(
                        _civil(5786, 7, day, israel=israel))["regalim"])

    def test_the_day_before_and_after_a_festival(self):
        erev_pesah = compute_holiday_aggregate(_civil(5786, 1, 14, israel=False))
        self.assertTrue(erev_pesah["day-before-holiday"])
        self.assertFalse(erev_pesah["day-after-holiday"])
        # Isru hag follows the last festival day, which is a day later outside Israel.
        self.assertTrue(compute_holiday_aggregate(_civil(5786, 1, 22))["day-after-holiday"])
        self.assertFalse(compute_holiday_aggregate(
            _civil(5786, 1, 22, israel=False))["day-after-holiday"])
        self.assertTrue(compute_holiday_aggregate(
            _civil(5786, 1, 23, israel=False))["day-after-holiday"])
        # A festival day is neither, even between two of them.
        second_day = compute_holiday_aggregate(_civil(5786, 1, 16, israel=False))
        self.assertFalse(second_day["day-before-holiday"])
        self.assertFalse(second_day["day-after-holiday"])
        ordinary = compute_holiday_aggregate(_civil(5786, 2, 4))
        self.assertFalse(ordinary["day-before-holiday"])
        self.assertFalse(ordinary["day-after-holiday"])

    def test_isru_hag_follows_only_a_pilgrimage_festival(self):
        for label, args, israel in (
            ("after Yom Kippur", (5786, 7, 11), True),
            ("first day of chol hamoed, Israel", (5786, 1, 16), True),
            ("first day of chol hamoed, diaspora", (5786, 1, 17), False),
        ):
            with self.subTest(day=label):
                self.assertFalse(compute_holiday_aggregate(
                    _civil(*args, israel=israel))["day-after-holiday"])
        for label, args, israel in (
            ("after Shavuot, Israel", (5786, 3, 7), True),
            ("after Simhat Torah, diaspora", (5786, 7, 24), False),
        ):
            with self.subTest(day=label):
                self.assertTrue(compute_holiday_aggregate(
                    _civil(*args, israel=israel))["day-after-holiday"])

    def test_aggregate_features_are_the_listed_ones(self):
        found = compute_holiday_aggregate(_civil(5786, 2, 4))
        self.assertEqual(set(found), set(AGGREGATE_FEATURES))

    def test_musaf_days(self):
        def musaf(snap):
            return compute_service_time(snap)["musaf"]
        for label, args in (("Yom Kippur", (5786, 7, 10)), ("Rosh Hodesh", (5786, 8, 1)),
                            ("Shemini Atzeret", (5786, 7, 22)), ("Hol ha-Moed", (5786, 7, 17))):
            with self.subTest(day=label):
                self.assertTrue(musaf(_civil(*args, hour=10)))
        # A weekday that is none of them.
        self.assertFalse(musaf(_civil(5786, 8, 4, hour=10)))


class TestUnknownLocale(unittest.TestCase):
    """Without a locale only what Israel and the diaspora agree on is derived."""

    @staticmethod
    def _undated_place(hebrew_year, month, day):
        civil = pyluach_dates.HebrewDate(hebrew_year, month, day).to_greg()
        return _snapshot({
            (FS_GREGORIAN, "year"): civil.year,
            (FS_GREGORIAN, "month"): civil.month,
            (FS_GREGORIAN, "day"): civil.day,
            (FS_HEBREW_DATE, "year"): hebrew_year,
            (FS_HEBREW_DATE, "month"): month,
            (FS_HEBREW_DATE, "day"): day,
        })

    def test_holidays_that_agree_are_kept(self):
        found = compute_holiday(self._undated_place(5786, 9, 25))
        self.assertEqual(found["hanukkah"], 1)
        self.assertEqual(found["pesah"], 0)

    def test_holidays_that_differ_are_undefined(self):
        # The eighth of Pesah is a festival day only outside Israel.
        found = compute_holiday(self._undated_place(5786, 1, 22))
        self.assertIs(found["pesah"], Undefined)
        aggregate = compute_holiday_aggregate(self._undated_place(5786, 1, 22))
        self.assertIs(aggregate["yom-tov"], Undefined)
        self.assertIs(aggregate["regalim"], Undefined)  # true in the diaspora, false in Israel
        self.assertFalse(aggregate["shabbat"])

    def test_musaf_on_a_diaspora_second_day_is_undefined(self):
        civil = pyluach_dates.HebrewDate(5785, 1, 22).to_greg()
        found = compute_service_time(_snapshot({
            (FS_GREGORIAN, "year"): civil.year,
            (FS_GREGORIAN, "month"): civil.month,
            (FS_GREGORIAN, "day"): civil.day,
            (FS_TIME, "hour"): 10,
            (FS_TIME, "minute"): 0,
            (FS_LOCATION, "latitude"): 40.71,
            (FS_LOCATION, "longitude"): -74.01,
            (FS_ISRAEL, "is-israel"): Undefined,
        }))
        self.assertIs(found["musaf"], Undefined)
        self.assertTrue(found["shaharit"])

    def test_declared_undefined_israel_is_not_israel(self):
        civil = pyluach_dates.HebrewDate(5785, 1, 22).to_greg()
        found = compute_holiday(_snapshot({
            (FS_GREGORIAN, "year"): civil.year,
            (FS_GREGORIAN, "month"): civil.month,
            (FS_GREGORIAN, "day"): civil.day,
            (FS_LOCATION, "latitude"): 40.71,
            (FS_LOCATION, "longitude"): -74.01,
            (FS_ISRAEL, "is-israel"): Undefined,
        }))
        self.assertIs(found["pesah"], Undefined)


class TestTimeOfDayEdges(unittest.TestCase):
    def test_before_sunrise_is_a_night_hour(self):
        evening = compute_hebrew_time(_civil(5786, 2, 4, hour=23))
        small_hours = compute_hebrew_time(_civil(5786, 2, 5, hour=3))
        self.assertGreaterEqual(small_hours["variable-hour"], 12)
        self.assertGreater(small_hours["variable-hour"], evening["variable-hour"])

    def test_part_is_of_the_variable_hour(self):
        """Halfway through a variable hour is 540 parts, however long the hour is."""
        civil = pyluach_dates.HebrewDate(5786, 3, 20).to_greg().to_pydate()  # a long summer day
        snap = TestRoshHodesh._snap(civil.year, civil.month, civil.day)
        zmanim = hdate.Zmanim(civil, location=snap.location())
        sunrise, sunset = zmanim.netz_hachama.local, zmanim.shkia.local
        middle_of_fourth = sunrise + (sunset - sunrise) * (3.5 / 12)
        found = compute_hebrew_time(_snapshot({
            (FS_GREGORIAN, "year"): civil.year,
            (FS_GREGORIAN, "month"): civil.month,
            (FS_GREGORIAN, "day"): civil.day,
            (FS_LOCATION, "latitude"): 31.78,
            (FS_LOCATION, "longitude"): 35.22,
            (FS_LOCATION, "timezone"): "Asia/Jerusalem",
            (FS_TIME, "hour"): middle_of_fourth.hour,
            (FS_TIME, "minute"): middle_of_fourth.minute,
            (FS_TIME, "second"): middle_of_fourth.second,
        }))
        self.assertEqual(found["variable-hour"], 3)
        self.assertAlmostEqual(found["part"], 540, delta=3)

    def test_motzaei_shabbat_lasts_until_dawn(self):
        # 8 Iyar 5786 is Shabbat; the small hours after it are civil Sunday.
        self.assertEqual(pyluach_dates.HebrewDate(5786, 2, 8).weekday(), 7)
        self.assertTrue(compute_holiday_aggregate(_civil(5786, 2, 8, hour=21))["motzaei-shabbat"])
        self.assertTrue(compute_holiday_aggregate(_civil(5786, 2, 9, hour=1))["motzaei-shabbat"])
        self.assertFalse(compute_holiday_aggregate(_civil(5786, 2, 9, hour=10))["motzaei-shabbat"])

    def test_saturday_night_reads_the_coming_week(self):
        saturday = compute_torah_reading(_civil(5786, 2, 8, hour=12))
        saturday_night = compute_torah_reading(_civil(5786, 2, 8, hour=22))
        sunday = compute_torah_reading(_civil(5786, 2, 9, hour=12))
        self.assertNotEqual(saturday["israel-parsha"], saturday_night["israel-parsha"])
        self.assertEqual(saturday_night["israel-parsha"], sunday["israel-parsha"])
