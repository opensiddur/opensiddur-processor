"""Calendar choices and source boundaries for Birnbaum's Sukkot rites."""
import unittest
from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import sukkot_rites as r
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_EN
from .test_tachanun_conditions import evaluate, fragment, NS

class TestSukkotRites(unittest.TestCase):
    def test_all_four_printed_hoshana_schedules(self):
        expected={2:(1,2,5,3,6,8),3:(1,2,5,6,8,4),5:(1,2,8,5,6,4),7:(8,1,5,2,6,4)}
        for first,days in expected.items():
            for offset,want in enumerate(days):
                settings={('opensiddur:hebrew-date','month'):7,('opensiddur:hebrew-date','day'):15+offset,
                    ('opensiddur:day-of-week','hebrew-day'):(first-1+offset)%7+1}
                actual=[n for n in range(1,7) if evaluate(r.hoshana_day(n),settings)==TriState.TRUE]
                self.assertEqual(actual,[] if want==8 else [want],(first,offset))
    def test_rabbah_includes_all_daily_hoshanot(self):
        settings={('opensiddur:hebrew-date','month'):7,('opensiddur:hebrew-date','day'):21}
        self.assertEqual([n for n in range(1,7) if evaluate(r.hoshana_day(n),settings)==TriState.TRUE],[1,2,3,4,5,6])
    def test_personal_first_use_unknown_yes_no(self):
        self.assertEqual(evaluate(r.FIRST_USE,{}),TriState.UNDEFINED)
        for selected in (False,True):
            self.assertEqual(evaluate(r.FIRST_USE,{('opensiddur:practice','lulav-first-use'):selected}),TriState.TRUE if selected else TriState.FALSE)
    def test_simchat_torah_in_both_locations(self):
        for israel in (True,False):
            for day in (21,22,23,24):
                settings={('opensiddur:hebrew-date','month'):7,('opensiddur:hebrew-date','day'):day,('opensiddur:israel','is-israel'):israel}
                self.assertEqual(evaluate(r.SIMCHAT_TORAH,settings),TriState.TRUE if day==(22 if israel else 23) else TriState.FALSE)
    def test_hoshanot_english_is_apparatus_not_invented_translation(self):
        for row in r.ROWS:
            if row['group']=='hoshanot':self.assertEqual(row['en'],'')
    def test_biblical_anthologies_are_bounded(self):
        prayers={p['urn']:fragment(p['body']) for p in r.prayers('he')}
        for key,count in [('hoshanot_lekha',3),('hoshanot_hoshiah_et_ammekha',3),('hoshanot_hoshiah_et_ammekha_repeat',3),('hoshanot_hoshiah_et_ammekha_rabbah',3),('lulav_lulav_intent',3)]:
            doc=prayers[r.URNS[key]]
            self.assertEqual(len(doc.xpath('.//tei:milestone[@unit="verse"][@corresp]',namespaces=NS)),count)
            self.assertEqual(len(doc.xpath('.//tei:milestone[@unit="verse"][not(@corresp)]',namespaces=NS)),count)
    def test_reusable_sections_have_no_whole_occasion_gate(self):
        units={u['urn']:u['body'] for u in r.units(r.PROJECT_HE)}
        for urn in (r.GESHEM,r.HAKAFOT):self.assertNotIn('j:conditional',units[urn])
        self.assertIn('lulav-first-use',units[r.LULAV])
        self.assertNotIn('opensiddur:hebrew-date',units[r.LULAV])

    def test_printed_occasion_rubrics_are_not_duplicated(self):
        for project in (r.PROJECT_HE,PROJECT_EN):
            units={u['urn']:u['body'] for u in r.units(project)}
            combined=units[r.ROOT+'/rites']+units[r.GESHEM]+units[r.HOSHANOT]
            self.assertEqual(combined.count('Chanted on the eighth day of Sukkoth during Musaf'),1)
            self.assertEqual(combined.count('On Sukkoth after Musaf'),1)
