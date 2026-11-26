"""Synthetic calendar precedence and service-extension boundaries."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.shabbat_shema import (
    FESTIVAL_WEEKDAY,
    ROOT,
    SERVICE,
    SHABBAT,
    extend_service,
)

from .test_tachanun_conditions import evaluate


class TestShabbatShema(unittest.TestCase):
    def test_sabbath_text_wins_on_a_festival_sabbath(self):
        for shabbat,festival in ((True,True),(True,False),(False,True),(False,False)):
            with self.subTest(shabbat=shabbat,festival=festival):
                values={('opensiddur:holiday-aggregate','shabbat'):shabbat,
                        ('opensiddur:holiday-aggregate','yom-tov'):festival}
                self.assertEqual(evaluate(SHABBAT,values),TriState.TRUE if shabbat else TriState.FALSE)
                self.assertEqual(evaluate(FESTIVAL_WEEKDAY,values),TriState.TRUE if festival and not shabbat else TriState.FALSE)

    def test_unknown_calendar_keeps_both_instructions_visible(self):
        self.assertEqual(evaluate(SHABBAT,{}),TriState.UNDEFINED)
        self.assertEqual(evaluate(FESTIVAL_WEEKDAY,{}),TriState.UNDEFINED)
        self.assertEqual(evaluate(FESTIVAL_WEEKDAY,{('opensiddur:holiday-aggregate','shabbat'):True}),TriState.FALSE)

    def test_extension_is_inside_existing_service_scope(self):
        end='<j:endDeclare target="#shabbat_shacharit_service"/>'
        original={'urn':SERVICE,'body':'<tei:div>Prior content.'+end+'</tei:div>','pages':(299,335)}
        untouched={'urn':'urn:x-opensiddur:text:siddur:synthetic','body':'Other content.','pages':(1,1)}
        result=extend_service([original,untouched])
        self.assertIn('target="'+ROOT+'"/>'+end,result[0]['body'])
        self.assertEqual(result[1],untouched)
        self.assertNotIn(ROOT,original['body'])
        self.assertEqual(result[0]['pages'],(299,349))
