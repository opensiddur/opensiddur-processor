"""Festival gates, service return points, and diplomatic-text structure."""
import unittest
from lxml import etree
from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import festival as f
from .test_tachanun_conditions import evaluate,fragment,NS

class TestFestival(unittest.TestCase):
    def test_candle_shehecheyanu_boundaries(self):
        for israel in (False,True):
            for name,days in [('pesah',8),('shavuot',2),('sukkot',7),('shmini-atzeret',2)]:
                for day in range(1,days+1):
                    values={('opensiddur:israel','is-israel'):israel}
                    values.update({('opensiddur:holiday',n):day if n==name else 0 for n in ('pesah','shavuot','sukkot','shmini-atzeret')})
                    with self.subTest(israel=israel,name=name,day=day):
                        self.assertEqual(evaluate(f.FIRST_NIGHTS,values),TriState.TRUE if day<= (1 if israel else 2) else TriState.FALSE)
        self.assertEqual(evaluate(f.FIRST_NIGHTS,{}),TriState.UNDEFINED)

    def test_sukkah_has_no_calendar_invented_presence(self):
        self.assertEqual(evaluate(f.IN_SUKKAH,{}),TriState.UNDEFINED)
        for present in (False,True):
            self.assertEqual(evaluate(f.IN_SUKKAH,{('opensiddur:practice','in-sukkah'):present}),TriState.TRUE if present else TriState.FALSE)

    def test_service_integrations_and_kaddish_outside(self):
        from opensiddur.importer.birnbaum_scan.build import build_he
        built={u['urn']:fragment(u['body']) for u in build_he.units(f.PROJECT_HE,build_he.HE_UNIT_PAGES,build_he.BY_NAME,build_he.unit_body())}
        for name in ('shacharit','arvit','minchah'):
            service=built[f.SIDDUR+'shabbat/'+name]
            self.assertEqual(len(service.xpath('.//j:transclude[@target=$urn]',namespaces=NS,urn=f.AMIDAH)),1)
        amidah=built[f.AMIDAH]
        self.assertFalse(any('kaddish' in t for t in amidah.xpath('.//@target')))
        self.assertFalse(amidah.xpath('.//j:conditional//tei:f[@name="yom-tov"]',namespaces=NS))
        self.assertEqual(evaluate(f.REGALIM,{('opensiddur:holiday-aggregate','yom-tov'):False,('opensiddur:holiday-aggregate','shabbat'):True,('opensiddur:holiday','pesah'):4}),TriState.FALSE)

    def test_priestly_blessing_is_shacharit_repetition(self):
        amidah=fragment(next(u['body'] for u in f.units(f.PROJECT_HE) if u['urn']==f.AMIDAH))
        gate=amidah.xpath('.//j:conditional[@xml:id="festival_kohanim"]/j:all',namespaces=NS)[0]
        expression=etree.tostring(gate,encoding='unicode')
        for morning in (False,True):
            for minyan in (False,True):
                values={('opensiddur:service-time','shaharit'):morning,('opensiddur:quorum','minyan'):minyan,('opensiddur:recitation','repetition'):True}
                self.assertEqual(evaluate(expression,values),TriState.TRUE if morning and minyan else TriState.FALSE)

    def test_optional_parentheses_are_functional(self):
        for lang in ('he','en'):
            for p in f.prayers(lang):
                self.assertNotIn('(', ''.join(fragment(p['body']).xpath('.//tei:seg/text()|.//tei:p/text()',namespaces=NS)))
        # This translation deliberately lacks the Hebrew second b'ahavah.
        texts={p['name']:p['body'] for p in f.prayers('en')}
        self.assertNotIn('j:conditional',texts['festival_miqra_text'])

    def test_shared_passages_do_not_inherit_weekday_rubrics(self):
        from opensiddur.importer.birnbaum_scan.build import build_he,build_en
        for module in (build_he,build_en):
            for urn in dict.fromkeys(f.REUSE.values()):
                owners=[p for p in module.PRAYERS if 'corresp="'+urn+'"' in p['body']]
                self.assertEqual(len(owners),1,urn)
                self.assertNotIn('<j:conditional',owners[0]['body'],urn)
