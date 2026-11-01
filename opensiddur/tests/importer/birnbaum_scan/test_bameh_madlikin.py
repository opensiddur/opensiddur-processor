"""Synthetic reference-boundary and occasion checks for the closing study."""
import unittest
from lxml import etree
from .test_tachanun_conditions import evaluate, fragment, NS
from .test_kabbalat_shabbat import date_values
from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.common import AGG, PROJECT_HE
from opensiddur.importer.birnbaum_scan.build.bameh_madlikin import (
    chapter_body, units, shared, MISHNAH, TALMUD, ROOT,
)


class TestBamehMadlikin(unittest.TestCase):
    def test_page_turn_does_not_split_mishnah_address(self):
        doc=fragment(chapter_body('en', ['First.', 'Across {pb:254}the page.']))
        self.assertEqual([m.get('corresp') for m in doc.findall('.//tei:milestone',NS)],
                         [MISHNAH+'/1',None,MISHNAH+'/2',None])
        paragraphs=doc.findall('.//tei:p',NS)
        self.assertEqual(len(paragraphs),2)
        self.assertEqual(''.join(paragraphs[1].itertext()),'2. Across the page.')
        self.assertIsNotNone(paragraphs[1].find('tei:pb',NS))

    def test_omission_lives_in_caller_and_ends_before_following_study(self):
        self.assertIsNone(fragment(chapter_body('en',['Sample.'])).find('.//j:conditional',NS))
        study=fragment(units(PROJECT_HE)[0]['body'])
        conditional=study.find('.//j:conditional',NS)
        # A known festival on either Friday or Shabbat omits the chapter;
        # no known date leaves the decision open.
        expr='<j:all>'+''.join(etree.tostring(c,encoding='unicode') for c in conditional if c.tag!='{'+NS['tei']+'}note')+'</j:all>'
        for vals,expected in [({},TriState.UNDEFINED),
                ({**date_values(2,10,True),(AGG,'yom-tov'):False},TriState.TRUE),
                ({**date_values(7,3,True),(AGG,'yom-tov'):False},TriState.FALSE),
                ({**date_values(3,7,False),(AGG,'yom-tov'):True},TriState.FALSE)]:
            self.assertEqual(evaluate(expr,vals),expected)
        xml=etree.tostring(study,encoding='unicode')
        self.assertLess(xml.index('target="#qabbalat_bameh_festival"'),xml.index('target="'+TALMUD+'"'))
        self.assertIn('target="'+ROOT+'/study_kaddish"',xml)

    def test_shared_metadata_does_not_mutate_old_text_or_claim_variant_printing(self):
        sample=[dict(name='kaddish_derabbanan_yehe_shelama',body='Earlier wording.',printings=((48,48),)),
                dict(name='kaddish_derabbanan_al_yisrael',body='Shared wording.')]
        result=shared('en',sample)
        self.assertEqual(result[0],sample[0])
        self.assertEqual(result[1]['body'],sample[1]['body'])
        self.assertEqual(result[1]['printings'],((256,256),))
        self.assertNotIn('printings',sample[1])
