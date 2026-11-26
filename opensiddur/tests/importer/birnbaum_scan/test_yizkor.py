"""Memorial-service calendar, independent selections, and scan boundaries."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import yizkor as y

from .test_tachanun_conditions import NS, evaluate, fragment


class TestYizkor(unittest.TestCase):
    def test_calendar_boundaries(self):
        names=('pesah','shavuot','sukkot','shmini-atzeret','yom-kippur')
        for israel in (False,True):
            for name in names:
                for day in range(9):
                    values={('opensiddur:israel','is-israel'):israel}
                    values.update({('opensiddur:holiday',n):day if name==n else 0 for n in names})
                    expected=day==dict(pesah=7 if israel else 8,shavuot=1 if israel else 2,
                        sukkot=-1,**{'shmini-atzeret':1,'yom-kippur':1})[name]
                    with self.subTest(israel=israel,name=name,day=day):
                        self.assertEqual(evaluate(y.OCCASION,values),TriState.TRUE if expected else TriState.FALSE)
        self.assertEqual(evaluate(y.OCCASION,{}),TriState.UNDEFINED)

    def test_independent_family_selections(self):
        for selector in y.SELECTORS.values():
            self.assertEqual(evaluate(selector,{}),TriState.UNDEFINED)
        for chosen in ('father','mother','husband','wife','el-male-man','el-male-woman'):
            values={('opensiddur:yizkor',key.replace('_','-')):key.replace('_','-')==chosen for key in y.SELECTORS}
            for key,selector in y.SELECTORS.items():
                self.assertEqual(evaluate(selector,values),TriState.TRUE if key.replace('_','-')==chosen else TriState.FALSE)
        all_true={('opensiddur:yizkor',key.replace('_','-')):True for key in y.SELECTORS}
        self.assertTrue(all(evaluate(s,all_true)==TriState.TRUE for s in y.SELECTORS.values()))

    def test_occasion_is_in_caller_only(self):
        units={u['urn']:u['body'] for u in y.units(y.PROJECT_HE)}
        self.assertIn('opensiddur:holiday',units[y.ROOT])
        self.assertNotIn('opensiddur:holiday',units[y.SERVICE])
        self.assertEqual(units[y.SERVICE].count(y.RUBRIC),1)
        self.assertNotIn(y.RUBRIC,units[y.ROOT])

    def test_biblical_sources_and_printed_scope(self):
        for lang in ('he','en'):
            prayers={p['urn']:fragment(p['body']) for p in y.prayers(lang)}
            for key,source in y.BIBLICAL.items():
                self.assertEqual(prayers[y.URNS[key]].xpath('.//tei:seg/@source',namespaces=NS),[source])
            for unit in y.units(y.PROJECT_HE):
                self.assertNotIn('kaddish',unit['body'])
            self.assertEqual(len(prayers),32)
        text={r['key']:r for r in y.ROWS}
        self.assertIn('בַּעֲבוּר',text['el_male_man']['he'])
        self.assertNotIn('charity',text['el_male_man']['en'])
        self.assertIn('מֹשֶׁה',text['av_harachamim']['he'])

    def test_torah_service_return_point(self):
        from opensiddur.importer.birnbaum_scan.build import build_he as b
        units=b.units(y.PROJECT_HE,b.HE_UNIT_PAGES,b.BY_NAME,b.unit_body())
        service=next(u['body'] for u in units if u['urn']==y.SIDDUR+'shabbat/shacharit/torah')
        targets=fragment(service).xpath('.//j:transclude/@target',namespaces=NS)
        self.assertEqual(targets.count(y.ROOT),1)
        self.assertEqual(targets[targets.index(y.ROOT)+1],y.SIDDUR+'shabbat/shacharit/torah/ashrei')
