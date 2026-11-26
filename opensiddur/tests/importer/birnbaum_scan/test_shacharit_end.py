"""Synthetic passage boundaries and service transclusion structure."""
import unittest

from lxml import etree

from opensiddur.importer.birnbaum_scan.build import shacharit_end as end

from .test_tachanun_conditions import NS, fragment


class TestFinalReadings(unittest.TestCase):
    def test_commandment_paragraphs_do_not_replace_verse_boundaries(self):
        rows = ((41, '', 'פתיחה', 'Opening'),
                (42, 'א', 'ראשון', 'First'),
                (43, None, 'המשך', 'Continued'),
                (44, 'ב', 'שני', 'Second'))
        for lang in ('he', 'en'):
            with self.subTest(lang=lang):
                tree = fragment(end.decalogue_body(lang, rows=rows))
                self.assertEqual(tree.xpath('.//tei:milestone[@corresp]/@corresp', namespaces=NS),
                    [end.BIBLE+f'exodus/20/{n}' for n in range(41,45)])
                paras = tree.xpath('.//tei:p[tei:milestone]', namespaces=NS)
                self.assertEqual(len(paras), 3)
                self.assertEqual(paras[1][0].tag, '{'+NS['tei']+'}milestone')
                self.assertEqual(paras[1][1].tag, '{'+NS['tei']+'}label')
                self.assertEqual(len(paras[1].xpath('.//tei:milestone[@corresp]', namespaces=NS)), 2)
                self.assertEqual(paras[1][-1].get('unit'), 'verse')
                self.assertIsNone(paras[1][-1].get('corresp'))
                self.assertFalse(tree.xpath('.//tei:seg[@corresp]', namespaces=NS))

    def test_principle_quotation_preserves_source_and_bounded_correspondence(self):
        rows = (('א', 'דברים {quote}פסוק{/quote}', 'Words {quote}verse{/quote}'),)
        tree = fragment(end.principles_body('en', rows=rows))
        self.assertEqual(tree.xpath('string(.//tei:seg/@source)', namespaces=NS), end.BIBLE+'psalms/33/15')
        self.assertEqual(tree.xpath('string(.//tei:milestone[@corresp]/@corresp)', namespaces=NS), end.PRINCIPLES_URN+'/1')
        para = tree.xpath('.//tei:p', namespaces=NS)[0]
        self.assertEqual(para[0].tag, '{'+NS['tei']+'}milestone')
        self.assertEqual(para[1].tag, '{'+NS['tei']+'}label')
        self.assertIsNone(para[-1].get('corresp'))
        self.assertNotIn('{quote}', etree.tostring(tree, encoding='unicode'))


class TestServiceWrapper(unittest.TestCase):
    def test_ordered_addressable_wrapper_reuses_supplied_units(self):
        targets = ('urn:x-opensiddur:text:siddur:all/shacharit/example',
                   'urn:x-opensiddur:text:siddur:chol/shacharit/example')
        for lang in ('he','en'):
            tree = fragment(end.service_body(lang, parts=targets))
            self.assertEqual(tree[0].get('corresp'), end.SERVICE)
            self.assertEqual(tree.xpath('.//j:transclude/@target', namespaces=NS), list(targets))
            self.assertEqual(len(tree.xpath('.//tei:head', namespaces=NS)), 1)
            self.assertEqual(tree.xpath('string(.//tei:head/@resp)', namespaces=NS), end.EDITOR)
            self.assertFalse(tree.xpath('.//tei:p', namespaces=NS))

            self.assertEqual(tree.xpath('.//j:declare/@xml:id', namespaces=NS), ['weekday_service'])
            self.assertEqual(tree.xpath('.//j:endDeclare/@target', namespaces=NS), ['#weekday_service'])
            for feature in ('shabbat', 'yom-tov'):
                self.assertEqual(tree.xpath(f'string(.//tei:f[@name="{feature}"]/tei:binary/@value)', namespaces=NS), 'false')
