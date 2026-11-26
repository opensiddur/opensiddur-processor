"""Synthetic tests of Amidah selection and the common post-Amidah return point."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.shabbat_amidah import (
    KADDISH,
    READER,
    ROOT,
    SERVICE,
    SHABBAT_AMIDAH,
    extend_service,
)

from .test_tachanun_conditions import NS, evaluate, fragment


class TestShabbatAmidah(unittest.TestCase):
    def test_festival_sabbath_uses_festival_amidah(self):
        for shabbat,festival in ((True,False),(True,True),(False,True)):
            with self.subTest(shabbat=shabbat,festival=festival):
                values={('opensiddur:holiday-aggregate','shabbat'):shabbat,
                        ('opensiddur:holiday-aggregate','yom-tov'):festival}
                self.assertEqual(evaluate(SHABBAT_AMIDAH,values),
                                 TriState.TRUE if shabbat and not festival else TriState.FALSE)

    def test_chol_hamoed_sabbath_uses_shabbat_amidah(self):
        values={('opensiddur:holiday-aggregate','shabbat'):True,
                ('opensiddur:holiday-aggregate','yom-tov'):False,
                ('opensiddur:holiday-aggregate','chol-hamoed'):True}
        self.assertEqual(evaluate(SHABBAT_AMIDAH,values),TriState.TRUE)

    def test_repetition_requires_minyan(self):
        for minyan,repetition in ((True,True),(False,True),(True,False),(False,False)):
            values={('opensiddur:quorum','minyan'):minyan,
                    ('opensiddur:recitation','repetition'):repetition}
            self.assertEqual(evaluate(READER,values),TriState.TRUE if minyan and repetition else TriState.FALSE)
        self.assertEqual(evaluate(READER,{}),TriState.UNDEFINED)

    def test_kaddish_is_outside_amidah_gate_and_before_service_end(self):
        end='<j:endDeclare target="#shabbat_shacharit_service"/>'
        original={'urn':SERVICE,'body':'<tei:div>Earlier service.'+end+'</tei:div>','pages':(299,349)}
        result=extend_service([original],'he')[0]
        tree=fragment(result['body'])
        division=tree[0]
        nodes=list(division)
        amidah=division.find('j:transclude[@target="'+ROOT+'"]',NS)
        kaddish=division.find('j:transclude[@target="'+KADDISH+'"]',NS)
        close=division.find('j:endConditional',NS)
        self.assertLess(nodes.index(amidah),nodes.index(close))
        self.assertLess(nodes.index(close),nodes.index(kaddish))
        self.assertLess(nodes.index(kaddish),nodes.index(division.find('j:endDeclare',NS)))
        self.assertNotIn(KADDISH,original['body'])
        self.assertEqual(result['pages'],(299,361))
