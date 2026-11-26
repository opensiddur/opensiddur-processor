"""Synthetic service direction and conditional-label regressions."""
import unittest

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_2.morning import (
    MORNING_URN,
    XML,
    T,
    conditional,
    documentary_documents,
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

    def test_unpaired_tallit_ending_precedes_shared_prayer_boundary(self):
        root=etree.Element(T+'TEI')
        entry=etree.SubElement(etree.SubElement(etree.SubElement(root,T+'text'),T+'body'),T+'div')
        tallit=etree.SubElement(entry,T+'div')
        tallit.set(XML+'id','morning_tallit')
        etree.SubElement(tallit,T+'p').text='untranslated ending'
        for key in ['preliminaries','blessings']:
            node=etree.SubElement(entry,T+'div')
            node.set(XML+'id','morning_'+key)
            etree.SubElement(node,T+'head').text=key
        etree.SubElement(entry,'{http://jewishliturgy.org/ns/jlptei/2}endDeclare',target='#morning_printings')
        result,service=documentary_documents(root,'en')
        self.assertIs(result,root)
        self.assertIs(entry[0],tallit)
        self.assertEqual(entry[1].get('target'),MORNING_URN+'/prayers@prayerbook_for_the_new_year_second_day-marmorstein-1965-en')
        self.assertEqual(etree.QName(entry[2]).localname,'endDeclare')
        self.assertEqual([n.get(XML+'id') for n in service.findall('.//'+T+'body/'+T+'div/'+T+'div')],['morning_preliminaries','morning_blessings'])

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
