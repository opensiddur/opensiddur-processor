"""Synthetic dates and passage boundaries for the service conclusion."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import conclusion as rules

from .test_tachanun_conditions import NS, evaluate, fragment, settings


class TestConclusionConditions(unittest.TestCase):
    def test_psalm27_boundaries(self):
        for israel in (True, False):
            for month, day, expected in ((5,29,False),(5,30,True),(6,1,True),
                    (6,29,True),(7,1,True),(7,21,True),(7,22,not israel),(7,23,False),(8,1,False)):
                with self.subTest(israel=israel, month=month, day=day):
                    self.assertEqual(evaluate(rules.ELUL_SEASON, settings(month=month,day=day,israel=israel)),
                                     TriState.TRUE if expected else TriState.FALSE)

    def test_unknown_location_matters_only_on_22_tishrei(self):
        for day, expected in ((21,TriState.TRUE),(22,TriState.UNDEFINED),(23,TriState.FALSE)):
            self.assertEqual(evaluate(rules.ELUL_SEASON,settings(month=7,day=day)),expected)

    def test_psalm20_omission_dates_and_ordinary_day(self):
        for month,day,omitted in ((2,10,False),(12,14,True),(12,15,True),(13,14,True),
                                 (13,15,True),(5,9,True),(1,14,True),(7,9,True)):
            values=settings(month=month,day=day)
            values['opensiddur:holiday-aggregate','chol-hamoed']=False
            self.assertEqual(evaluate(rules.PSALM20_OCCASION,values),
                             TriState.FALSE if omitted else TriState.TRUE)
        for fs,name in (('opensiddur:holiday','rosh-hodesh'),('opensiddur:holiday','hanukkah'),
                        ('opensiddur:holiday-aggregate','chol-hamoed')):
            self.assertEqual(evaluate(rules.PSALM20_OCCASION,{(fs,name):1}),TriState.FALSE)

    def test_minimum_quorum_and_mourning_are_independent(self):
        for value,expected in ((False,TriState.FALSE),(True,TriState.TRUE),(None,TriState.UNDEFINED)):
            self.assertEqual(evaluate(rules.MINYAN,{('opensiddur:quorum','minyan'):value}),expected)
            self.assertEqual(evaluate(rules.MOURNING,{('opensiddur:override','house-of-mourning'):value}),expected)


class TestConclusionPassages(unittest.TestCase):
    def test_repeat_closes_correspondence_and_keeps_edition_anchor(self):
        bible=rules.BIBLE+'psalms/1/1'
        xml=rules.rows_xml([('first',None,'א','First'),('repeat','psalms/1/1','ב','Repeat'),
                           ('last',None,'{reader}ג','{reader}Last')],
                          urn=rules.ROOT+'/test',lang='en',seen={bible},sigil='test')
        tree=fragment(xml)
        self.assertEqual(tree.xpath('count(.//tei:milestone[@corresp])',namespaces=NS),3)
        self.assertEqual(tree.xpath('string(.//tei:seg/@source)',namespaces=NS),bible)
        self.assertEqual(tree.xpath('string(.//tei:seg/@xml:id)',namespaces=NS),'ref_repeat')
        self.assertEqual(tree.xpath('.//tei:seg/preceding-sibling::*[1]',namespaces=NS)[0].get('corresp'), rules.ROOT+'/test/repeat')
        self.assertEqual(tree.xpath('string(.//tei:note)',namespaces=NS),'Reader')

    def test_targum_has_own_reference_and_language(self):
        xml=rules.rows_xml([('targum_test','isaiah/6/3','ארמית','Translation')],
                          urn=rules.ROOT+'/test',lang='he',seen=set(),sigil='test')
        tree=fragment(xml)
        self.assertEqual(tree.xpath('string(.//tei:milestone/@corresp)',namespaces=NS),rules.ROOT+'/test/targum_test')
        self.assertEqual(tree.xpath('string(.//tei:seg/@xml:lang)',namespaces=NS),'arc')


class TestDailyPsalmSection(unittest.TestCase):
    def test_section_transcludes_occurrences_and_gates_them_in_the_caller(self):
        days = (('alpha', 'Alpha', 'א', 'first', 1, 139),
                ('beta', 'Beta', 'ב', 'second', 2, 139))
        tree = fragment(rules.shir_shel_yom_body('en', days=days))
        self.assertEqual(tree.xpath('.//j:transclude/@target', namespaces=NS),
                         [rules.PSALMS + '/alpha', rules.PSALMS + '/beta'])
        conditions = tree.xpath('.//j:conditional', namespaces=NS)
        self.assertEqual(len(conditions), 2)
        from lxml import etree
        for weekday in (1, 2, 3):
            values = settings(weekday=weekday)
            for index, node in enumerate(conditions, 1):
                expression = ''.join(etree.tostring(child, encoding='unicode')
                                     for child in node if child.tag != '{'+NS['tei']+'}note')
                self.assertEqual(evaluate(expression, values),
                                 TriState.TRUE if weekday == index else TriState.FALSE)
        self.assertFalse(tree.xpath('.//tei:p', namespaces=NS))
        self.assertEqual(tree.xpath('.//j:endConditional/@target', namespaces=NS),
                         ['#day_alpha', '#day_beta'])
