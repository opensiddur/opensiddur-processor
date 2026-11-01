"""Meal choices, wedding order and reusable closing prayers."""
import unittest
from lxml import etree
from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import concluding_prayers as r
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_EN
from .test_tachanun_conditions import evaluate, fragment, NS

class TestConcludingPrayers(unittest.TestCase):
    def test_wedding_wine_order(self):
        for project in (r.PROJECT_HE,PROJECT_EN):
            units={u['urn']:fragment(u['body']) for u in r.units(project)}
            ceremony=units[r.SEVEN].xpath('.//j:transclude/@target',namespaces=NS)
            meal=units[r.SEVEN+'/after_meal'].xpath('.//j:transclude/@target',namespaces=NS)
            self.assertEqual(ceremony[0],r.PRAYER+'borei_peri_hagafen')
            self.assertEqual(meal,ceremony[1:]+ceremony[:1])
            self.assertFalse(units[r.SEVEN].xpath('.//j:conditional',namespaces=NS))

    def test_personal_choices_remain_maybe_when_unknown(self):
        for expr in (r.context('guest'),r.context('zimmun'),r.context('meein-shalosh-food','wine')):
            self.assertEqual(evaluate(expr,{}),TriState.UNDEFINED)
        for chosen in ('wine','fruit','cake','cake_wine'):
            values={('opensiddur:meal-context','meein-shalosh-food'):chosen}
            for option in ('wine','fruit','cake','cake_wine'):
                self.assertEqual(evaluate(r.context('meein-shalosh-food',option),values),TriState.TRUE if chosen==option else TriState.FALSE)

    def test_migdol_is_a_day_choice_not_current_service(self):
        self.assertNotIn('service',r.MUSAF)
        self.assertEqual(evaluate(r.MUSAF,{('opensiddur:day-of-week','hebrew-day'):7}),TriState.TRUE)
        self.assertEqual(evaluate(r.MUSAF,{('opensiddur:holiday','rosh-hodesh'):1}),TriState.TRUE)

    def test_bible_and_conditional_boundaries(self):
        for lang in ('he','en'):
            prayers={p['urn']:fragment(p['body']) for p in r.prayers(lang)}
            psalm=prayers[r.BIBLE+'psalms/137']
            self.assertEqual(psalm.xpath('.//tei:milestone[@corresp]/@corresp',namespaces=NS),[r.BIBLE+'psalms/137/'+str(i) for i in range(1,10)])
            for key in ('zimmun_leader','zimmun_response','harachaman_self','harachaman_hosts'):
                node=prayers[r.URNS[key]]
                for n in node.xpath('.//tei:note',namespaces=NS):n.getparent().remove(n)
                self.assertNotIn('(',''.join(node.itertext()))
            self.assertFalse(any(n.xpath('.//tei:seg[@corresp]',namespaces=NS) for n in prayers.values()))
            israel=prayers[r.URNS['israel_3']]
            self.assertEqual(israel.xpath('.//tei:seg/@source',namespaces=NS),[r.BIBLE+'deuteronomy/30/4',r.BIBLE+'deuteronomy/30/5'])

    def test_printed_one_sided_alternatives_are_not_translated(self):
        self.assertTrue(all(not r.BY_KEY['meein_begin_'+k]['en'] for k in ('wine','fruit','cake','cake_wine')))
        he=next(u['body'] for u in r.units(r.PROJECT_HE) if u['urn']==r.ABRIDGED)
        en=next(u['body'] for u in r.units(PROJECT_EN) if u['urn']==r.ABRIDGED)
        self.assertIn('meein-shalosh-food',he)
        self.assertNotIn('meein-shalosh-food',en)  # empty facing anchors, no empty brackets

    def test_final_scan_numbers_have_direct_evidence(self):
        from opensiddur.importer.birnbaum_siddur.correspondence import resolve_printed_pages
        rows=[dict(scan_page=n,printed_page_wikisource=None,printed_page_ia=None) for n in (811,813,815)]
        self.assertEqual(resolve_printed_pages(rows),[])
        self.assertEqual([x['printed_page'] for x in rows],['786','788','790'])
        self.assertTrue(all(x['printed_page_source']=='direct_scan_reading' for x in rows))
