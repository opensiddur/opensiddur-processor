"""Rosh Hodesh Musaf gates and separation from other Amidah additions."""
import unittest
from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.rosh_hodesh_musaf import ROOT,AMIDAH,URNS,PROJECT_HE,units,LEAP,READER
from .test_tachanun_conditions import evaluate,fragment,NS


class TestRoshHodeshMusaf(unittest.TestCase):
    def setUp(self):
        self.built={u['urn']:fragment(u['body']) for u in units(PROJECT_HE)}

    def test_occasion_is_on_caller_not_reusable_amidah(self):
        caller=self.built[ROOT]
        gate=caller.xpath('.//j:conditional[@xml:id="rosh_chodesh_musaf_occasion"]',namespaces=NS)[0]
        from lxml import etree
        expression=etree.tostring(gate.find('j:all',NS),encoding='unicode')
        for day in (0,1,2):
            for shabbat in (False,True):
                with self.subTest(day=day,shabbat=shabbat):
                    result=evaluate(expression,{('opensiddur:holiday','rosh-hodesh'):day,('opensiddur:holiday-aggregate','shabbat'):shabbat})
                    self.assertEqual(result,TriState.TRUE if day and not shabbat else TriState.FALSE)
        self.assertEqual(evaluate(expression,{}),TriState.UNDEFINED)
        self.assertFalse(self.built[AMIDAH].xpath('.//tei:f[@name="rosh-hodesh"]',namespaces=NS))

    def test_leap_and_reader_three_way_selection(self):
        self.assertEqual(evaluate(LEAP,{}),TriState.UNDEFINED)
        for leap in (False,True):
            self.assertEqual(evaluate(LEAP,{('opensiddur:hebrew-date','leap-year'):leap}),TriState.TRUE if leap else TriState.FALSE)
        # Lack of a minyan must suppress Reader-only passages even if repetition is requested.
        self.assertEqual(evaluate(READER,{('opensiddur:quorum','minyan'):False,('opensiddur:recitation','repetition'):True}),TriState.FALSE)

    def test_no_unprinted_ten_days_yaaleh_or_kaddish(self):
        targets=self.built[AMIDAH].xpath('.//@target')
        for unwanted in ('yaaleh','kaddish','zokhrenu','ukhetov','besefer'):
            self.assertFalse(any(unwanted in t for t in targets),unwanted)
        self.assertIn(URNS['retzeh'],targets)
        self.assertIn(URNS['vetechezeinah'],targets)
        self.assertIn(URNS['sim_shalom'],targets)
        self.assertEqual(self.built[ROOT].find('.//tei:f[@name="musaf"]/tei:binary',NS).get('value'),'true')

    def test_nineteen_blessing_commentary_excludes_musaf(self):
        from opensiddur.importer.birnbaum_scan.build.notes import WEEKDAY_AMIDAH_NOTE, note
        from lxml import etree
        synthetic = dict(kind='commentary', target='urn:test', condition=WEEKDAY_AMIDAH_NOTE, paras=[dict(text='Example.')])
        encoded = fragment(note(synthetic))
        condition = encoded.find('.//j:condition', NS)
        expression = etree.tostring(condition[0], encoding='unicode')
        self.assertEqual(evaluate(expression, {('opensiddur:service-time', 'musaf'): True}), TriState.FALSE)
        weekday = {('opensiddur:service-time', 'musaf'): False, ('opensiddur:holiday-aggregate', 'shabbat'): False, ('opensiddur:holiday-aggregate', 'yom-tov'): False}
        self.assertEqual(evaluate(expression, weekday), TriState.TRUE)
        for day in ('shabbat', 'yom-tov'):
            self.assertEqual(evaluate(expression, weekday | {('opensiddur:holiday-aggregate', day): True}), TriState.FALSE)

    def test_modim_ordinal_survives_regeneration_as_conditional(self):
        from opensiddur.importer.birnbaum_scan.build.notes import amidah_note, note
        synthetic = dict(kind='commentary', target='urn:test', lemma='מודים דרבנן', paras=[dict(text='The eighteenth benediction.')])
        encoded = fragment(note(amidah_note(synthetic)))
        self.assertEqual(len(encoded.findall('.//j:conditional', NS)), 1)
        self.assertEqual(encoded.find('.//j:endConditional', NS).get('target'), '#modim_eighteenth')
