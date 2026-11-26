"""Synthetic service direction and conditional-label regressions."""
import unittest

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_2.morning import (
    XML,
    T,
    conditional,
    instruction,
    transclude,
)


class TestMorningServiceHelpers(unittest.TestCase):
    def test_edition_qualified_range_stays_one_target(self):
        parent=etree.Element(T+'div')
        target='urn:x-opensiddur:text:bible:numbers/6/24-/6/26'
        node=transclude(parent,target,project='example-book-1965-he')
        self.assertEqual(node.get('target'),target+'@example-book-1965-he')
        self.assertIsNone(node.get('targetEnd'))

    def test_bilingual_condition_label_is_one_note_before_expression(self):
        parent=etree.Element(T+'div')
        node=conditional(parent,'selected','shabbat',label={'he':'בשבת','en':'On Shabbat'})
        self.assertEqual([etree.QName(n).localname for n in node],['note','all'])
        self.assertEqual([n.get(XML+'lang')for n in node[0]],['he','en'])

    def test_printed_page_number_is_not_retained_as_navigation_text(self):
        parent=etree.Element(T+'div')
        target='urn:x-opensiddur:text:prayer:elohai_neshamah@example-book-1965-he'
        item={'source':{'text':'The next prayer (P. 5.) follows here.','language':'en','witnesses':['he'],'scan':'s30'},
              'documentary_navigation':{'target_by_language':{'he':target}}}
        instruction(parent,item,'he',expanded=False)
        refs=list(parent.iter(T+'ref'))
        self.assertEqual(len(refs),1)
        self.assertEqual(refs[0].get('type'),'page')
        self.assertEqual(refs[0].get('target'),target)
        self.assertIsNone(refs[0].text)
        self.assertEqual(refs[0].getparent().get('type'),'optional-page-reference')
        self.assertNotIn('5',''.join(parent.itertext()))
        self.assertIn('follows here.',''.join(parent.itertext()))
