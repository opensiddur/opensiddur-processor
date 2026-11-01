"""Rosh Hashanah prayer selection and preservation of biblical boundaries."""
import unittest
from lxml import etree as E
from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import rosh_hashanah as r
from .test_tachanun_conditions import evaluate, fragment, NS

class TestRoshHashanah(unittest.TestCase):
    def test_tashlikh_postponed_only_when_day_one_is_shabbat(self):
        for day,weekday,expected in [(1,7,False),(2,1,True),(1,2,True),(2,3,False),(3,4,False)]:
            settings={('opensiddur:hebrew-date','month'):7,('opensiddur:hebrew-date','day'):day,
                ('opensiddur:day-of-week','hebrew-day'):weekday,(r.AGG,'shabbat'):weekday==7}
            self.assertEqual(evaluate(r.TASHLIKH_DAY,settings),TriState.TRUE if expected else TriState.FALSE)
    def test_reader_never_appears_at_maariv_or_without_minyan(self):
        from opensiddur.importer.birnbaum_scan.build.shabbat_amidah import RECITATION
        for service,minyan,rep,expected in [('minha',True,True,True),('maariv',True,True,False),('minha',False,True,False),('minha',True,False,False)]:
            settings={(r.SERVICE,service):True,(r.SERVICE,'minha'):service=='minha',
                ('opensiddur:quorum','minyan'):minyan,(RECITATION,'repetition'):rep}
            self.assertEqual(evaluate(r.READER,settings),TriState.TRUE if expected else TriState.FALSE)
    def test_kapparot_custom_defaults_to_maybe_and_selects_one(self):
        for value in ('money','rooster','hen'):
            self.assertEqual(evaluate(r.object_condition(value),{}),TriState.UNDEFINED)
            for selected in ('money','rooster','hen'):
                self.assertEqual(evaluate(r.object_condition(value),{('opensiddur:practice',r.KAPPAROT_OBJECT):selected}),TriState.TRUE if value==selected else TriState.FALSE)
    def test_calendar_gates_are_in_callers(self):
        units={u['urn']:u['body'] for u in r.units(r.PROJECT_HE)}
        self.assertNotIn('j:conditional',units[r.TASHLIKH])
        self.assertNotIn('opensiddur:hebrew-date',units[r.KAPPAROT])
        self.assertIn('opensiddur:hebrew-date',units[r.ROOT+'/tashlikh'])
        self.assertIn('opensiddur:hebrew-date',units[r.SIDDUR+'yom_kippur/kapparot'])
    def test_biblical_milestones_complete_and_closed(self):
        expected={'micah':3,'min_hametzar':5,'psalm33':22,'psalm130':8,'vayekhulu':4,'benei_adam':10}
        for lang in ('he','en'):
            prayers={p['urn']:fragment(p['body']) for p in r.prayers(lang)}
            for key,count in expected.items():
                doc=prayers[r.URNS[key]]
                self.assertEqual(len(doc.xpath('.//tei:milestone[@unit="verse"][@corresp]',namespaces=NS)),count)
                self.assertEqual(len(doc.xpath('.//tei:milestone[@unit="verse"][not(@corresp)]',namespaces=NS)),count)
                self.assertEqual(len(doc.xpath('.//tei:seg[starts-with(@source,"urn:x-opensiddur:text:bible:")]',namespaces=NS)),count-(key=='benei_adam'))
    def test_printed_alternatives_do_not_add_duplicate_parentheses(self):
        keys=('vattitten_lanu','kadsheinu','kiddush','yk_candle_blessing','vattodienu','modim_derabbanan','fire','havdalah')
        for lang in ('he','en'):
            prayers={p['urn']:p['body'] for p in r.prayers(lang)}
            for k in keys:
                self.assertNotIn('(',prayers[r.URNS[k]])
                self.assertNotIn(')',prayers[r.URNS[k]])
        u={u['urn']:u['body'] for u in r.units(r.PROJECT_HE)}
        self.assertIn('יִנָּתֵן לִצְדָקָה',u[r.KAPPAROT+'/money'])
        self.assertNotIn('לְמִיתָה',u[r.KAPPAROT+'/money'])
