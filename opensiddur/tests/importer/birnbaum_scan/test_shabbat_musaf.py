"""Musaf's calendar selection differs from the Sabbath Shacharit Amidah."""
import unittest
from collections import defaultdict

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.shabbat_musaf import (
    LEAP,
    OCCASION,
    PROJECT_HE,
    RC,
    ROOT,
    units,
)

from .test_tachanun_conditions import NS, evaluate, fragment


class TestShabbatMusaf(unittest.TestCase):
    def test_chol_hamoed_and_festivals_require_the_festival_musaf(self):
        for shabbat, festival, intermediate in (
                (True, False, False), (True, True, False),
                (True, False, True), (False, False, False)):
            with self.subTest(shabbat=shabbat, festival=festival, intermediate=intermediate):
                values = {('opensiddur:holiday-aggregate', 'shabbat'): shabbat,
                          ('opensiddur:holiday-aggregate', 'yom-tov'): festival,
                          ('opensiddur:holiday-aggregate', 'chol-hamoed'): intermediate}
                expected = shabbat and not (festival or intermediate)
                self.assertEqual(evaluate(OCCASION, values),
                                 TriState.TRUE if expected else TriState.FALSE)

    def test_both_days_of_rosh_chodesh_select_the_alternative(self):
        for day in (0, 1, 2):
            with self.subTest(day=day):
                self.assertEqual(evaluate(RC, {('opensiddur:holiday', 'rosh-hodesh'): day}),
                                 TriState.TRUE if day else TriState.FALSE)
        self.assertEqual(evaluate(RC, {}), TriState.UNDEFINED)

    def test_leap_year_addition_remains_optional_without_a_year(self):
        for leap in (True, False):
            self.assertEqual(evaluate(LEAP, {('opensiddur:hebrew-date', 'leap-year'): leap}),
                             TriState.TRUE if leap else TriState.FALSE)
        self.assertEqual(evaluate(LEAP, {}), TriState.UNDEFINED)

    def test_common_conclusion_is_outside_amidah_and_its_calendar_gate(self):
        fake = defaultdict(lambda: {'urn': 'urn:x-opensiddur:text:prayer:synthetic'})
        built = {u['urn']: u for u in units(PROJECT_HE, fake)}
        amidah = fragment(built[ROOT+'/amidah']['body'])
        targets = amidah.xpath('//@target')
        self.assertIn('urn:x-opensiddur:text:prayer:amidah/avodah/retzeh', targets)
        self.assertIn('urn:x-opensiddur:text:prayer:amidah/avodah/vetechezeinah', targets)
        self.assertFalse(any('yaaleh' in t or 'kaddish' in t for t in targets))
        service = fragment(built[ROOT]['body'])[0]
        nodes = list(service)
        close = service.find('j:endConditional', NS)
        kaddish = service.find('j:transclude[@target="'+ROOT+'/kaddish"]', NS)
        self.assertLess(nodes.index(close), nodes.index(kaddish))
        self.assertIn(ROOT+'/adon_olam', service.xpath('.//@target'))
        self.assertFalse(any('kiddush' in t for t in service.xpath('.//@target')))
        self.assertEqual(service.find('.//tei:f[@name="musaf"]/tei:binary', NS).get('value'), 'true')
