"""The printed recitation choices and independent Hashmonaim reference units."""
import unicodedata
import unittest

from lxml import etree

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import hanukkah_purim as r
from opensiddur.importer.birnbaum_scan.build.festival_data import ROWS as FESTIVAL

from .test_tachanun_conditions import NS, evaluate, fragment


class TestHanukkahPurim(unittest.TestCase):
    def test_first_night_only_and_unspecified(self):
        self.assertEqual(evaluate(r.FIRST_NIGHT,{}),TriState.UNDEFINED)
        for day in range(9):
            self.assertEqual(evaluate(r.FIRST_NIGHT,{('opensiddur:holiday','hanukkah'):day}),TriState.TRUE if day==1 else TriState.FALSE)

    def test_asher_heni_omitted_only_in_morning(self):
        unit=next(u for u in r.units(r.PROJECT_HE) if u['urn']==r.PURIM)
        node=fragment(unit['body'])
        condition=node.xpath('.//j:conditional[contains(@xml:id,"asher_heni")]',namespaces=NS)[0]
        expression=''.join(etree.tostring(c,encoding='unicode') for c in condition if c.tag!='{'+NS['tei']+'}note')
        for settings,want in [({},TriState.UNDEFINED),({(r.SERVICE,'shaharit'):True},TriState.FALSE),({(r.SERVICE,'shaharit'):False},TriState.TRUE)]:
            self.assertEqual(evaluate(expression,settings),want)
        # Shoshanat is outside that scope and remains in both services.
        refs=node.xpath('.//j:transclude/@target',namespaces=NS)
        self.assertEqual(refs[-1],r.SHOSHANAT)

    def test_76_numbered_verses_with_independent_paragraphs(self):
        paragraph_counts=[]
        for lang in ('he','en'):
            doc=fragment(r.hashmonaim(lang))
            verses=doc.xpath('.//tei:milestone[@unit="verse"][@corresp]',namespaces=NS)
            self.assertEqual([v.get('corresp') for v in verses],[r.HASHMONAIM+'/'+str(i) for i in range(1,77)])
            self.assertEqual(sum(v.get('n') is not None for v in verses),76 if lang=='he' else 0)
            paragraph_counts.append(len(doc.xpath('.//tei:p',namespaces=NS)))
            quotations=doc.xpath('.//tei:seg[@source]',namespaces=NS)
            self.assertEqual(len(quotations),2)
            self.assertNotIn('It is better' if lang=='en' else 'עַתָּה',''.join(quotations[-1].itertext()))
        self.assertEqual(paragraph_counts,[13,14])

    def test_shared_blessings_are_exact_in_both_languages(self):
        rows={row['key']:row for row in r.ROWS}
        original=next(x for x in FESTIVAL if x['key']=='shehecheyanu')
        for lang in ('he','en'):
            for key in ('shehecheyanu','purim_shehecheyanu'):
                self.assertEqual(unicodedata.normalize('NFKD',rows[key][lang]),unicodedata.normalize('NFKD',original[lang]))
            self.assertEqual(rows['miracles'][lang],rows['purim_miracles'][lang])

    def test_maoz_sixth_stanza_not_invented_in_english(self):
        sixth=next(row for row in r.ROWS if row['key']=='maoz_6')
        self.assertEqual(sixth['en'],'')
        self.assertEqual(sixth['en_page'],712)
        bare=''.join(c for c in sixth['he'] if not unicodedata.combining(c))
        self.assertIn('וקרב יום הישועה',bare)
        self.assertNotIn('לנו',bare)
        self.assertNotIn('דם',bare)
