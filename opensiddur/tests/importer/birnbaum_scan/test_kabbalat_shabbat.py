"""Synthetic checks for festival boundaries and reusable correspondence ranges."""
import unittest
from lxml import etree
from .test_tachanun_conditions import evaluate, fragment, NS
from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.common import AGG, PROJECT_HE
from opensiddur.importer.birnbaum_scan.build.kabbalat_shabbat import (
    FULL, FESTIVAL, PRESENT_MOURNERS, shared, psalm_body, units, ROOT, BIBLE, ANA,
)


def date_values(month, day, israel=None):
    values={('opensiddur:hebrew-date','month'):month,('opensiddur:hebrew-date','day'):day}
    if israel is not None: values['opensiddur:israel','is-israel']=israel
    return values


class TestKabbalatOccasion(unittest.TestCase):
    def test_friday_festival_uses_incoming_shabbat_date_and_location(self):
        for month,day,israel,full in ((2,10,True,True),(1,22,True,False),
              (1,22,False,True),(1,23,False,False),(3,7,True,False),
              (3,7,False,True),(3,8,False,False),(7,23,True,False),
              (7,24,False,False),(7,3,True,False),(7,11,True,False)):
            with self.subTest(month=month,day=day,israel=israel):
                self.assertEqual(evaluate(FULL,date_values(month,day,israel)),
                                 TriState.TRUE if full else TriState.FALSE)

    def test_unknown_calendar_and_mourners_remain_maybe(self):
        for expression in (FULL,FESTIVAL,PRESENT_MOURNERS):
            self.assertEqual(evaluate(expression,{}),TriState.UNDEFINED)
        self.assertEqual(evaluate(FULL,date_values(1,22)),TriState.UNDEFINED)
        self.assertEqual(evaluate(FULL,date_values(2,10)),TriState.TRUE)

    def test_whole_service_condition_is_only_in_caller(self):
        files={x['name']:fragment(x['body']) for x in units(PROJECT_HE)}
        gate=files['shabbat_qabbalat_service'].find('.//j:conditional',NS)
        self.assertIsNotNone(gate.find('.//tei:f[@name="yom-tov"]',NS))
        self.assertIsNone(files['qabbalat_shabbat'].find('.//tei:f[@name="yom-tov"]',NS))
        # The Friday exception ends before Psalm 92, not after the whole service.
        text=etree.tostring(files['qabbalat_shabbat']).decode()
        self.assertLess(text.index('target="#qabbalat_friday_festival"'),text.index('target="'+BIBLE+'psalms/92"'))


class TestKabbalatCorrespondences(unittest.TestCase):
    def test_earlier_excerpt_keeps_text_and_gets_local_source_reference(self):
        source=BIBLE+'psalms/29/11'
        urn='urn:x-opensiddur:text:siddur:synthetic/collection'
        body='<tei:p><tei:milestone unit="verse" corresp="'+source+'"/>Earlier wording.<tei:milestone unit="verse"/></tei:p>'
        result=shared('en',[dict(name='torah_vetiggaleh',urn=urn,body=body)])[0]['body']
        root=fragment(result)
        self.assertEqual(''.join(root.itertext()),'Earlier wording.')
        self.assertEqual(root.find('.//tei:seg',NS).get('source'),source)
        self.assertEqual(root.find('.//tei:milestone',NS).get('corresp'),urn+'/psalms_29_11')

    def test_shared_poem_has_independent_stanza_ranges(self):
        body='<tei:lg>'+''.join('<tei:l>Line '+str(i)+'</tei:l>' for i in range(7))+'</tei:lg>'
        result=fragment(shared('he',[dict(name='poem_anna_bekhoach',body=body)])[0]['body'])
        self.assertEqual([m.get('corresp') for m in result.findall('.//tei:milestone[@corresp]',NS)],
                         [ANA+'/'+str(i) for i in range(1,8)])
        for line in result.findall('.//tei:l',NS):
            self.assertIsNone(line[-1].get('corresp'))

    def test_paragraph_inside_verse_preserves_one_biblical_address(self):
        result=fragment(psalm_body(95,'en','First.\nSecond {p}paragraph.'))
        self.assertEqual([m.get('corresp') for m in result.findall('.//tei:milestone',NS)],
                         [BIBLE+'psalms/95/1',BIBLE+'psalms/95/2',None])
        self.assertEqual(len(result.findall('.//tei:p',NS)),3)
