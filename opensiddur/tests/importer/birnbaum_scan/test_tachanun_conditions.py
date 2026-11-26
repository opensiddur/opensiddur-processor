"""Calendar boundaries and independence of the three post-Amidah sections."""
import unittest
from unittest.mock import Mock

from lxml import etree

from opensiddur.exporter.condition_eval import (
    TriState,
    evaluate_condition,
    parse_condition_element,
)
from opensiddur.importer.birnbaum_scan.build import tachanun_conditions as rules
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_HE, cond
from opensiddur.importer.birnbaum_scan.build.tachanun import kaddish_body

NS = {'tei': 'http://www.tei-c.org/ns/1.0', 'j': 'http://jewishliturgy.org/ns/jlptei/2'}


def fragment(xml):
    return etree.fromstring(('<root xmlns:tei="%s" xmlns:j="%s">%s</root>' %
                            (NS['tei'], NS['j'], xml)).encode())


def settings(month=2, day=10, weekday=2, israel=None, **overrides):
    result = {('opensiddur:hebrew-date', 'month'): month,
              ('opensiddur:hebrew-date', 'day'): day,
              ('opensiddur:day-of-week', 'hebrew-day'): weekday}
    # In these synthetic scenarios no named holiday occurs unless specified.
    result.update({('opensiddur:holiday', key): 0 for key in
                   ('rosh-hodesh', 'hanukkah', 'lag-baomer', 'tisha-bav')})
    result.update({('opensiddur:override', key): overrides.get(key, False) for key in
                   ('omit-tahanun', 'house-of-mourning', 'brit-milah')})
    if israel is not None:
        result['opensiddur:israel', 'is-israel'] = israel
    return result


def evaluate(expression, values):
    processor = Mock()
    processor.get_active_setting.side_effect = lambda fs, f: values.get((fs, f))
    node = parse_condition_element(fragment(cond('test', fs=expression))[0])
    return evaluate_condition(node, processor)


class TestTachanunCalendar(unittest.TestCase):
    def test_weekday_selects_exactly_one_form_even_without_location(self):
        for day in (1, 2, 3, 4, 5, 6):
            with self.subTest(day=day):
                values = settings(weekday=day)
                self.assertEqual(evaluate(rules.occasion(long=True), values),
                                 TriState.TRUE if day in (2, 5) else TriState.FALSE)
                self.assertEqual(evaluate(rules.occasion(), values),
                                 TriState.FALSE if day in (2, 5) else TriState.TRUE)

    def test_tishrei_resumption_depends_on_location(self):
        for israel, resume in ((True, 24), (False, 25)):
            for day in (8, 9, 23, 24, 25, 26):
                with self.subTest(israel=israel, day=day):
                    self.assertEqual(evaluate(rules.TACHANUN_OMITTED,
                                             settings(month=7, day=day, israel=israel)),
                                     TriState.TRUE if 9 <= day < resume else TriState.FALSE)

    def test_unknown_location_only_keeps_the_disputed_day_undecided(self):
        self.assertEqual(evaluate(rules.TACHANUN_OMITTED, settings(month=7, day=24)), TriState.UNDEFINED)
        for day, expected in ((23, TriState.TRUE), (25, TriState.FALSE)):
            self.assertEqual(evaluate(rules.TACHANUN_OMITTED, settings(month=7, day=day)), expected)

    def test_nisan_omits_tachanun_but_not_the_torah_introduction(self):
        values = settings(month=1, day=10)
        self.assertEqual(evaluate(rules.occasion(long=True), values), TriState.FALSE)
        self.assertEqual(evaluate(rules.EL_EREKH_OCCASION, values), TriState.TRUE)
        self.assertEqual(evaluate(rules.EL_EREKH_OCCASION, settings(month=1, day=14)), TriState.FALSE)

    def test_sivan_and_both_adars_have_the_printed_boundaries(self):
        for month, day, omitted in ((3, 8, True), (3, 9, False),
                                    (12, 13, False), (12, 14, True), (12, 15, True), (12, 16, False),
                                    (13, 13, False), (13, 14, True), (13, 15, True), (13, 16, False)):
            with self.subTest(month=month, day=day):
                self.assertEqual(evaluate(rules.TACHANUN_OMITTED, settings(month, day)),
                                 TriState.TRUE if omitted else TriState.FALSE)

    def test_personal_omission_is_decisive_with_unknown_date(self):
        for key in ('omit-tahanun', 'house-of-mourning', 'brit-milah'):
            values = {('opensiddur:override', key): True}
            for long in (True, False):
                self.assertEqual(evaluate(rules.occasion(long=long), values), TriState.FALSE)

    def test_kaddish_depends_on_minyan_and_not_tachanun(self):
        conditional = fragment(kaddish_body(PROJECT_HE)).find('.//j:conditional', NS)
        node = parse_condition_element(conditional)
        for has_minyan, expected in ((True, TriState.TRUE), (False, TriState.FALSE), (None, TriState.UNDEFINED)):
            processor = Mock()
            values = settings(month=1, **{'house-of-mourning': True})
            values['opensiddur:quorum', 'minyan'] = has_minyan
            processor.get_active_setting.side_effect = lambda fs, f, values=values: values.get((fs, f))
            self.assertEqual(evaluate_condition(node, processor), expected)
