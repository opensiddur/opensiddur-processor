"""Synthetic checks for Sabbath/festival Torah-service selection."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.shabbat_torah import (
    AV_HARACHAMIM,
    AV_OMISSIONS,
    FESTIVAL_HAFTARAH,
    KADDISH,
    MEVARCHIM,
    ROOT,
    SERVICE,
    TORAH,
    extend_service,
)

from .test_tachanun_conditions import NS, evaluate, fragment

AGG='opensiddur:holiday-aggregate'
HOL='opensiddur:holiday'

class TestShabbatTorah(unittest.TestCase):
    def test_chol_hamoed_haftarah(self):
        for sukkot,expected in ((0,TriState.FALSE),(3,TriState.TRUE)):
            with self.subTest(sukkot=sukkot):
                self.assertEqual(evaluate(FESTIVAL_HAFTARAH,{
                    (AGG,'shabbat'):True,(AGG,'yom-tov'):False,
                    (AGG,'chol-hamoed'):True,(HOL,'sukkot'):sukkot}),expected)

    def test_yom_tov_always_selects_festival_ending(self):
        self.assertEqual(evaluate(FESTIVAL_HAFTARAH,{(AGG,'yom-tov'):True}),TriState.TRUE)
        self.assertEqual(evaluate(FESTIVAL_HAFTARAH,{}),TriState.UNDEFINED)

    def test_memorial_special_sabbaths_and_hazon(self):
        values={(AGG,'shabbat'):True,(AGG,'yom-tov'):False,(AGG,'chol-hamoed'):False}
        values.update({(TORAH,name):False for name in AV_OMISSIONS})
        self.assertEqual(evaluate(AV_HARACHAMIM,values),TriState.TRUE)
        for name in AV_OMISSIONS:
            with self.subTest(name=name):
                self.assertEqual(evaluate(AV_HARACHAMIM,values|{(TORAH,name):True}),TriState.FALSE)
        self.assertEqual(evaluate(AV_HARACHAMIM,values|{(TORAH,'shabbat-hazon'):True}),TriState.TRUE)
        self.assertEqual(evaluate(AV_HARACHAMIM,{}),TriState.UNDEFINED)

    def test_upcoming_mevarchim_does_not_make_weekday_month_blessing(self):
        self.assertEqual(evaluate(MEVARCHIM,{(AGG,'shabbat'):False,(TORAH,'shabbat-mevarchim'):True}),TriState.FALSE)

    def test_kaddish_follows_torah_as_sibling(self):
        end='<j:endDeclare target="#shabbat_shacharit_service"/>'
        original={'urn':SERVICE,'body':'<tei:div>Earlier.'+end+'</tei:div>','pages':(299,361)}
        result=extend_service([original],'he')[0]
        tree=fragment(result['body'])[0]
        self.assertEqual([e.get('target') for e in tree.findall('j:transclude',NS)],[ROOT,KADDISH])
        self.assertEqual(result['pages'],(299,389))
        self.assertNotIn(ROOT,original['body'])
