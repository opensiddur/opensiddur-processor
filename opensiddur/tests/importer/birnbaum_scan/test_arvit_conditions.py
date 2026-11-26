"""Synthetic boundaries for the evening Havdalah insertion and opening."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.arvit import (
    AFTER_FESTIVAL,
    AFTER_MINCHA,
    HAVDALAH,
    SATURDAY_NIGHT,
)

from .test_tachanun_conditions import evaluate, settings


class TestArvitConditions(unittest.TestCase):
    def test_post_festival_dates_follow_location(self):
        for month, israel_day, diaspora_day in (
            (1, 16, 17), (1, 22, 23), (3, 7, 8), (7, 16, 17), (7, 23, 24)
        ):
            for israel in (True, False):
                day = israel_day if israel else diaspora_day
                for offset in (-1, 0, 1):
                    with self.subTest(month=month, day=day + offset, israel=israel):
                        self.assertEqual(
                            evaluate(AFTER_FESTIVAL, settings(month, day + offset, israel=israel)),
                            TriState.TRUE if offset == 0 else TriState.FALSE,
                        )

    def test_rosh_hashanah_and_yom_kippur_end_on_same_dates_everywhere(self):
        for israel in (True, False, None):
            for day in (3, 11):
                with self.subTest(israel=israel, day=day):
                    self.assertEqual(evaluate(AFTER_FESTIVAL, settings(7, day, israel=israel)), TriState.TRUE)

    def test_unknown_location_preserves_the_havdalah_choice(self):
        for month, day in ((1, 16), (1, 17), (3, 7), (3, 8), (7, 23), (7, 24)):
            with self.subTest(month=month, day=day):
                self.assertEqual(evaluate(HAVDALAH, settings(month, day)), TriState.UNDEFINED)
        self.assertEqual(evaluate(HAVDALAH, settings()), TriState.FALSE)
        self.assertEqual(evaluate(HAVDALAH, settings(weekday=1)), TriState.TRUE)

    def test_optional_opening_stays_undecided_without_service_context(self):
        opening = '<j:none>' + AFTER_MINCHA + SATURDAY_NIGHT + '</j:none>'
        values = settings()
        self.assertEqual(evaluate(opening, values), TriState.UNDEFINED)
        for after_mincha in (True, False):
            values['opensiddur:service-context', 'immediately-after-minha'] = after_mincha
            self.assertEqual(evaluate(opening, values), TriState.FALSE if after_mincha else TriState.TRUE)
        self.assertEqual(evaluate(opening, settings(weekday=1)), TriState.FALSE)
