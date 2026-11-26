"""Synthetic reading spans verify blessing boundaries and scroll precedence."""
import unittest

from opensiddur.importer.humash.refs import (
    UNIT_ALIYAH,
    UNIT_MAFTIR,
    ReadingSpan,
    VerseRef,
)
from opensiddur.importer.siddur_expanded.readings import SHABBAT, Entry, slots
from opensiddur.importer.siddur_expanded.xml import (
    NS,
    TEXT,
    Author,
    parse_fragment,
    transclude,
)


class Source:
    def source(self,urn):return transclude(TEXT+urn)

class TestReadingSlots(unittest.TestCase):
    def test_each_aliyah_has_its_own_bounded_text_between_blessings(self):
        spans=[ReadingSpan(UNIT_ALIYAH,str(i),VerseRef('genesis',i,1),VerseRef('genesis',i,5)) for i in [1,2,3]]
        entry=Entry('synthetic','Synthetic reading',SHABBAT,torah=spans)
        tree=parse_fragment(slots([entry],Author(),Source(),'morning')['torah'])
        targets=tree.xpath('.//j:transclude/@target',namespaces=NS)
        for i in range(3):
            self.assertEqual(targets[4*i:4*i+4],[TEXT+'siddur:chol/shacharit/torah/barekhu',TEXT+'siddur:chol/shacharit/torah/asher_bachar',TEXT+f'bible:genesis/{i+1}/1-{i+1}/5',TEXT+'prayer:birkhot_hatorah/asher_natan'])
    def test_maftir_and_haftarah_do_not_enter_main_torah_slot(self):
        entry=Entry('synthetic','Synthetic reading',SHABBAT,torah=[ReadingSpan(UNIT_ALIYAH,'1',VerseRef('genesis',1,1),VerseRef('genesis',1,5))],maftir=[ReadingSpan(UNIT_MAFTIR,'M',VerseRef('numbers',28,9),VerseRef('numbers',28,10))],haftarah=TEXT+'bible:haftarah/synthetic')
        result=slots([entry],Author(),Source(),'morning')
        self.assertNotIn('numbers/28',result['torah'])
        self.assertIn('numbers/28/9-28/10',result['maftir'])
        self.assertNotIn('haftarah/synthetic',result['maftir'])
        self.assertIn('haftarah/synthetic',result['haftarah'])
    def test_third_scroll_combines_sixth_and_seventh_weekly_aliyot(self):
        spans=[ReadingSpan(UNIT_ALIYAH,str(i),VerseRef('genesis',i,1),VerseRef('genesis',i,5)) for i in range(1,8)]
        entry=Entry('weekly_synthetic','Synthetic weekly reading',SHABBAT,kind='weekly',torah=spans,haftarah=TEXT+'bible:haftarah/synthetic')
        result=slots([entry],Author(),Source(),'morning')
        self.assertIn(TEXT+'bible:genesis/6/1-7/5',result['torah'])
        self.assertIn('shabbat-shkalim',result['torah'])
        self.assertIn('rosh-hodesh',result['torah'])
        self.assertIn('hanukkah',result['torah'])
    def test_combined_readings_resolve_existing_haftarah_units(self):
        from opensiddur.importer.siddur_expanded.readings import weekly_haftarah_slug
        available={'pekudei','nitzavim','vayeilech','achrei_mot_kedoshim','kedoshim'}
        self.assertEqual(weekly_haftarah_slug('vayakhel_pekudei',available),'pekudei')
        self.assertEqual(weekly_haftarah_slug('nitzavim_vayeilech',available),'nitzavim')
        self.assertEqual(weekly_haftarah_slug('achrei_mot_kedoshim',available),'achrei_mot_kedoshim')
        with self.assertRaisesRegex(ValueError,'Missing weekly haftarah'):
            weekly_haftarah_slug('unavailable',available)
    def test_machar_chodesh_does_not_displace_consolation_in_av(self):
        from opensiddur.exporter.condition_eval import (
            TriState,
            evaluate_condition,
            parse_condition_element,
        )
        from opensiddur.importer.siddur_expanded.readings import festival_cases
        condition=parse_condition_element(parse_fragment('<j:conditional>'+festival_cases()['Shabbat Machar Chodesh']+'</j:conditional>')[0])
        class Lookup:
            month=5
            def get_active_setting(self,fs,name):
                if fs=='opensiddur:holiday-aggregate':return name=='shabbat'
                if fs=='opensiddur:torah-reading':return name=='shabbat-mahar-hodesh'
                if fs=='opensiddur:holiday':return 0
                if fs=='opensiddur:hebrew-date' and name=='month':return self.month
        lookup=Lookup()
        self.assertEqual(evaluate_condition(condition,lookup),TriState.FALSE)
        lookup.month=8
        self.assertEqual(evaluate_condition(condition,lookup),TriState.TRUE)
    def test_scroll_arrangements_have_complete_aliyot_and_blessings(self):
        from opensiddur.exporter.condition_eval import (
            TriState,
            evaluate_condition,
            parse_condition_element,
        )
        spans=[ReadingSpan(UNIT_ALIYAH,str(i),VerseRef('genesis',i,1),VerseRef('genesis',i,5)) for i in range(1,8)]
        entry=Entry('weekly_synthetic','Synthetic weekly reading',SHABBAT,kind='weekly',torah=spans,haftarah=TEXT+'bible:haftarah/synthetic')
        root=parse_fragment(slots([entry],Author(),Source(),'morning')['torah'])
        class Lookup:
            three=False
            def get_active_setting(self,fs,name):
                if fs=='opensiddur:holiday-aggregate':return name=='shabbat'
                if fs=='opensiddur:holiday':return int(self.three)
                return False
        lookup=Lookup()
        for three in [False,True]:
            lookup.three=three;stack=[];targets=[]
            for element in root:
                if element.tag=='{http://jewishliturgy.org/ns/jlptei/2}conditional':stack.append(evaluate_condition(parse_condition_element(element),lookup))
                elif element.tag=='{http://jewishliturgy.org/ns/jlptei/2}endConditional':stack.pop()
                elif element.tag=='{http://jewishliturgy.org/ns/jlptei/2}transclude' and all(v==TriState.TRUE for v in stack):targets.append(element.get('target'))
            readings=[t for t in targets if 'bible:genesis' in t]
            expected=[TEXT+f'bible:genesis/{i}/1-{i}/5' for i in range(1,6)]
            expected += [TEXT+'bible:genesis/6/1-7/5'] if three else [TEXT+'bible:genesis/6/1-6/5',TEXT+'bible:genesis/7/1-7/5']
            self.assertEqual(readings,expected)
            self.assertEqual(len(targets),4*len(expected))


class TestSukkotShabbatMaftir(unittest.TestCase):
    """Which day's maftir Shabbat Chol HaMoed Sukkot reads, in the Diaspora and in Israel.

    hebcal numbers the five maftirs by the day of Chol HaMoed, which begins on the third day of
    Sukkot in the Diaspora and on the second in Israel. The dates are the three days of Sukkot
    a Shabbat of Chol HaMoed can fall on, derived through the calendar as a volume would be.
    """

    PLACES = {'diaspora': (40.71, -74.01), 'israel': (31.78, 35.22)}

    def _read(self, year, month, day, place):
        from lxml import etree

        from opensiddur.exporter.calendar.compute import (
            FS_GREGORIAN,
            FS_LOCATION,
            SettingSnapshot,
            compute_holiday,
            compute_israel,
        )
        from opensiddur.exporter.condition_eval import (
            TriState,
            evaluate_condition,
            parse_condition_element,
        )
        from opensiddur.importer.siddur_expanded.readings import day_maftir_condition

        declared = {(FS_GREGORIAN, 'year'): year, (FS_GREGORIAN, 'month'): month,
                    (FS_GREGORIAN, 'day'): day}
        if place is not None:
            declared[(FS_LOCATION, 'latitude')], declared[(FS_LOCATION, 'longitude')] = place
        snapshot = SettingSnapshot(get_setting=lambda fs, f: declared.get((fs, f)))
        active = {('opensiddur:holiday', 'sukkot'): (compute_holiday(snapshot) or {}).get('sukkot'),
                  ('opensiddur:israel', 'is-israel'): (compute_israel(snapshot) or {}).get('is-israel')}

        class Lookup:
            def get_active_setting(self, fs, f):
                return active.get((fs, f))

        read = []
        for offset in range(1, 6):
            conditional = etree.fromstring(
                f'<j:conditional xmlns:j="{NS["j"]}" xmlns:tei="{NS["tei"]}">'
                f'{day_maftir_condition(offset)}</j:conditional>')
            if evaluate_condition(parse_condition_element(conditional), Lookup()) != TriState.FALSE:
                read.append(offset)
        return read

    def test_each_place_reads_its_own_days_maftir(self):
        shabbatot = {
            (2024, 10, 19): {'diaspora': [1], 'israel': [2]},  # 17 Tishrei 5785, day 3
            (2025, 10, 11): {'diaspora': [3], 'israel': [4]},  # 19 Tishrei 5786, day 5
            (2019, 10, 19): {'diaspora': [4], 'israel': [5]},  # 20 Tishrei 5780, day 6
        }
        for date, expected in shabbatot.items():
            for place, coordinates in self.PLACES.items():
                with self.subTest(date=date, place=place):
                    self.assertEqual(self._read(*date, coordinates), expected[place])

    def test_without_a_place_every_maftir_is_kept(self):
        self.assertEqual(self._read(2025, 10, 11, None), [1, 2, 3, 4, 5])
