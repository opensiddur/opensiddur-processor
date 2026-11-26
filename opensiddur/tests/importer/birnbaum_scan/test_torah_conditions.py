"""Synthetic calendar and personal-setting cases for the Torah service."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import torah
from opensiddur.importer.birnbaum_scan.build.common import PERSON, feature

from .test_tachanun_conditions import evaluate, settings


def reading_settings(weekday=3, minyan=True):
    values = settings(weekday=weekday)
    values['opensiddur:quorum', 'minyan'] = minyan
    for name in ('purim', 'shushan-purim', 'purim-observed', 'tzom-tammuz'):
        values['opensiddur:holiday', name] = 0
    for name in ('chol-hamoed', 'minor-fast'):
        values['opensiddur:holiday-aggregate', name] = False
    return values


class TestTorahConditions(unittest.TestCase):
    def test_monday_and_thursday_and_ordinary_nonreading_day(self):
        for weekday in range(1, 7):
            with self.subTest(weekday=weekday):
                self.assertEqual(evaluate(torah.READING_OCCASION, reading_settings(weekday)),
                    TriState.TRUE if weekday in (2, 5) else TriState.FALSE)

    def test_each_printed_special_occasion_has_reading_without_tachanun(self):
        cases = [('opensiddur:holiday', name, 1) for name in
                 ('rosh-hodesh', 'hanukkah', 'purim-observed', 'tzom-tammuz')]
        cases += [('opensiddur:holiday-aggregate', name, True) for name in
                  ('chol-hamoed', 'minor-fast')]
        for fs, name, value in cases:
            with self.subTest(name=name):
                values = reading_settings()
                values[fs, name] = value
                values['opensiddur:override', 'omit-tahanun'] = True
                self.assertEqual(evaluate(torah.READING_OCCASION, values), TriState.TRUE)

    def test_the_torah_is_read_on_the_day_purim_is_celebrated_only(self):
        # The 14th where Purim is the 15th, and the 15th where it is the 14th.
        for name in ('purim', 'shushan-purim'):
            with self.subTest(name=name):
                values = reading_settings()
                values['opensiddur:holiday', name] = 1
                self.assertEqual(evaluate(torah.READING_OCCASION, values), TriState.FALSE)

    def test_no_minyan_is_decisive_even_without_date(self):
        self.assertEqual(evaluate(torah.READING_OCCASION,
            {('opensiddur:quorum', 'minyan'): False}), TriState.FALSE)

    def test_unknown_minyan_preserves_rubric_only_on_reading_day(self):
        self.assertEqual(evaluate(torah.READING_OCCASION, reading_settings(2, None)), TriState.UNDEFINED)
        self.assertEqual(evaluate(torah.READING_OCCASION, reading_settings(3, None)), TriState.FALSE)

    def test_supplications_follow_tachanun_without_suppressing_reading(self):
        for override in ('omit-tahanun', 'house-of-mourning', 'brit-milah'):
            with self.subTest(override=override):
                values = reading_settings(2)
                values['opensiddur:override', override] = True
                self.assertEqual(evaluate(torah.occasion(long=True), values), TriState.FALSE)
                self.assertEqual(evaluate(torah.READING_OCCASION, values), TriState.TRUE)

    def test_gomel_personal_setting_has_three_states(self):
        expression = feature(PERSON, 'birkat-hagomel')
        for value, expected in ((True, TriState.TRUE), (False, TriState.FALSE), (None, TriState.UNDEFINED)):
            with self.subTest(value=value):
                self.assertEqual(evaluate(expression, {(PERSON, 'birkat-hagomel'): value}), expected)
