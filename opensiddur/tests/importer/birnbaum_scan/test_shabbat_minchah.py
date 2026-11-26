"""Season boundaries for the winter Sabbath Psalm collection."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.shabbat_minchah import WINTER

from .test_tachanun_conditions import evaluate


class TestWinterPsalms(unittest.TestCase):
    def test_israel_and_diaspora_start_after_simchat_torah(self):
        for israel,day,expected in ((True,22,False),(True,23,True),(False,23,False),(False,24,True)):
            with self.subTest(israel=israel,day=day):
                self.assertEqual(evaluate(WINTER,{
                    ('opensiddur:israel','is-israel'):israel,
                    ('opensiddur:hebrew-date','month'):7,
                    ('opensiddur:hebrew-date','day'):day}),
                    TriState.TRUE if expected else TriState.FALSE)

    def test_both_adars_and_pesach_boundary(self):
        for month,day,expected in ((12,14,True),(13,29,True),(1,14,True),(1,15,False),(6,1,False)):
            with self.subTest(month=month,day=day):
                self.assertEqual(evaluate(WINTER,{
                    ('opensiddur:israel','is-israel'):False,
                    ('opensiddur:hebrew-date','month'):month,
                    ('opensiddur:hebrew-date','day'):day}),
                    TriState.TRUE if expected else TriState.FALSE)

    def test_unspecified_season_stays_maybe(self):
        self.assertEqual(evaluate(WINTER,{}),TriState.UNDEFINED)
