"""The "Kind of day" choices are what the calendar shows to be certain of each kind of day."""

import json
import unittest
from datetime import date

from opensiddur.exporter.html import kinds_of_day
from opensiddur.exporter.html.kinds_of_day import (
    EXCLUDED,
    ISRAEL,
    OUTPUT,
    Kind,
    _derive,
    certain,
    generate,
)

H = "opensiddur:holiday"
A = "opensiddur:holiday-aggregate"


class TestCertain(unittest.TestCase):

    def test_only_what_every_day_shares(self):
        days = [{(H, "pesah"): 1, (H, "omer"): 0}, {(H, "pesah"): 1, (H, "omer"): 1}]
        self.assertEqual(certain(days), {H: {"pesah": 1}})

    def test_excluded_features_are_left_to_others(self):
        days = [{(A, "shabbat"): True, (A, "yom-tov"): True}]
        self.assertIn((A, "shabbat"), EXCLUDED)
        self.assertEqual(certain(days), {A: {"yom-tov": True}})


class TestGenerate(unittest.TestCase):

    DAYS = {
        "israel": [{(H, "pesah"): 1}, {(H, "pesah"): 2}],
        "outside": [{(H, "pesah"): 1}, {(H, "pesah"): 2}],
    }

    def test_a_day_kept_only_outside_israel_is_sampled_only_there(self):
        kinds = (Kind("Second", lambda d: d[(H, "pesah")] == 2, outside_israel_only=True),)
        original = kinds_of_day.KINDS
        kinds_of_day.KINDS = kinds
        try:
            self.assertEqual(generate(self.DAYS), [{"label": "Second", "set": {H: {"pesah": 2}}}])
        finally:
            kinds_of_day.KINDS = original

    def test_a_kind_no_day_is_is_an_error(self):
        original = kinds_of_day.KINDS
        kinds_of_day.KINDS = (Kind("Never", lambda d: False),)
        try:
            with self.assertRaises(ValueError):
                generate(self.DAYS)
        finally:
            kinds_of_day.KINDS = original


class TestTheDayCelebratedAsPurim(unittest.TestCase):
    """The volume says which day is celebrated as Purim; the kind of day cannot."""

    def test_it_is_left_open_on_purim_and_on_shushan_purim(self):
        # 14 and 15 Adar 5786.
        for day in (date(2026, 3, 3), date(2026, 3, 4)):
            with self.subTest(day=day):
                self.assertNotIn((H, "purim-observed"), _derive(day, ISRAEL))

    def test_it_is_settled_on_any_other_day(self):
        self.assertEqual(_derive(date(2026, 3, 10), ISRAEL)[(H, "purim-observed")], 0)


class TestCommittedFile(unittest.TestCase):
    """kinds_of_day.json is what the generator writes, so a change to the kinds or to the
    calendar cannot leave the book's choices stale. Regenerate with
    `python -m opensiddur.exporter.html.kinds_of_day`."""

    def test_up_to_date(self):
        self.assertEqual(json.loads(OUTPUT.read_text(encoding="utf-8")), generate())


if __name__ == "__main__":
    unittest.main()
