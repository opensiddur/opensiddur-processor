"""Festival Musaf choices and scan-specific variants."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import festival_musaf as f

from .test_tachanun_conditions import NS, evaluate, fragment


class TestFestivalMusaf(unittest.TestCase):
    def test_tal_only_first_day_repetition_with_minyan(self):
        for day in range(1,9):
            for repeat in (False,True):
                for minyan in (False,True):
                    values={('opensiddur:holiday','pesah'):day,
                        ('opensiddur:quorum','minyan'):minyan,('opensiddur:recitation','repetition'):repeat}
                    self.assertEqual(evaluate(f.TAL_OCCASION,values),TriState.TRUE if day==1 and repeat and minyan else TriState.FALSE)
    def test_customs_remain_unknown(self):
        self.assertEqual(evaluate(f.REPEAT,{}),TriState.UNDEFINED)
        values={('opensiddur:quorum','minyan'):True,('opensiddur:recitation','repetition'):True}
        self.assertEqual(evaluate(f.DUCHEN,values),TriState.UNDEFINED)
        values[('opensiddur:quorum','minyan')]=False
        self.assertEqual(evaluate(f.DUCHEN,values),TriState.FALSE)
    def test_shared_passages_match_both_readings(self):
        import unicodedata

        from opensiddur.importer.birnbaum_scan.build import build_en, build_he
        def norm(v):return ' '.join(unicodedata.normalize('NFC',v).split())
        for lang,build in [('he',build_he),('en',build_en)]:
            index={p['urn']:p for p in build.PRAYERS}
            for r in f.ROWS:
                if r['key'] not in f.REUSE:continue
                with self.subTest(lang=lang,key=r['key']):
                    doc=fragment(index[f.URNS[r['key']]]['body'])
                    self.assertEqual(norm(''.join(doc.itertext())),norm(r[lang]))
    def test_complete_rows_and_ceremony(self):
        rows={r['key']:r for r in f.ROWS}
        self.assertEqual(len(rows),119)
        self.assertEqual(rows['savri']['en'],'')
        self.assertIn('בְּמַאֲדִירֶֽיהָ',rows['tal_4']['he'])
        self.assertIn('הַגָּֽשֶׁם',rows['rain']['he'])
        units={u['urn']:u['body'] for u in f.units(f.PROJECT_HE)}
        self.assertNotIn('opensiddur:holiday',units[f.TAL])
        self.assertNotIn('kaddish',units[f.AMIDAH])
        targets=fragment(units[f.AMIDAH]).xpath('.//j:transclude/@target',namespaces=NS)
        self.assertLess(targets.index(f.KOHANIM+'/avodah'),targets.index(f.AMIDAH+'/hodaah'))
        self.assertLess(targets.index(f.AMIDAH+'/hodaah'),targets.index(f.KOHANIM))
        self.assertLess(targets.index(f.KOHANIM),targets.index(f.URNS['sim_shalom']))
    def test_offerings_israel_and_diaspora(self):
        from lxml import etree as E
        unit=next(u for u in f.units(f.PROJECT_HE) if u['urn']==f.AMIDAH+'/offerings')
        doc=fragment(unit['body'])
        for israel in (False,True):
            for day in range(2,8):
                values={('opensiddur:israel','is-israel'):israel,('opensiddur:holiday','sukkot'):day}
                chosen=[]
                for node in doc.xpath('.//j:conditional',namespaces=NS):
                    key=node.get('{http://www.w3.org/XML/1998/namespace}id')
                    if 'israel_sukkot_' not in key and 'diaspora_sukkot_' not in key:continue
                    expr=node.xpath('./j:all',namespaces=NS)[0]
                    if evaluate(E.tostring(expr,encoding='unicode'),values)==TriState.TRUE:chosen.append(key)
                expected=[] if not israel and day==2 else ['festival_musaf_'+('israel' if israel else 'diaspora')+'_sukkot_'+str(day)]
                self.assertEqual(chosen,expected)
    def test_shabbat_chol_hamoed_major_kedushah(self):
        for shabbat in (False,True):
            values={('opensiddur:date','shabbat'):shabbat}
            # Aggregate names are deliberately explicit, so this checks the actual
            # selector rather than a date chosen without knowing its weekday.
            values={(f.AGG,'shabbat'):shabbat,(f.AGG,'yom-tov'):False,(f.AGG,'chol-hamoed'):True}
            self.assertEqual(evaluate(f.MAJOR,values),TriState.TRUE if shabbat else TriState.FALSE)
