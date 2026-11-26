"""Numbered-day structure across reordered facsimiles and Hebrew-only rubrics."""
import json
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.asher_selichot.build import TEI, XML, J, poem
from opensiddur.importer.asher_selichot.second_day import (
    numbered_documents,
    printed_unit,
)
from opensiddur.importer.scan.reverse import streams
from opensiddur.tests.importer.asher_selichot import test_second_day as fixtures


class ThirdDayTest(unittest.TestCase):
    def test_reordered_source_pages_and_closed_day_specific_expansions(self):
        opening={'id':'opening_instruction','kind':'rubric','fragments':[fixtures.SecondDayTest.fragment('s60','Say אשרי','Say Happy.') ]}
        readings=[opening]+[{'id':'part_'+str(n),'kind':'prose','fragments':[fixtures.SecondDayTest.fragment('s'+str(n),'טקסט׃')]} for n in [62,66,64,68]]
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)
            (source/'third-day.json').write_text(json.dumps({'heading':{'he':'סליחות ליום שלישי','en':'THIRD DAY'},'units':readings}))
            docs=list(numbered_documents(source,'third'))
        self.assertEqual(['third_day.xml']*2,[d[1] for d in docs])
        for project,_name,root in docs:
            self.assertEqual('urn:x-opensiddur:text:siddur:selichot/third_day',root.find(f'.//{{{TEI}}}body/{{{TEI}}}div').get('corresp'))
            ids=[n.get(XML+'id') for n in root.findall(f'.//{{{J}}}conditional')]
            self.assertEqual(['third_opening_instruction_printed','third_opening_instruction_expanded'],ids)
            self.assertEqual(['#'+id for id in ids],[n.get('target') for n in root.findall(f'.//{{{J}}}endConditional')])
            expected=['n61.jpg','n65.jpg','n63.jpg','n67.jpg'] if project.endswith('-he') else ['n62.jpg','n66.jpg','n64.jpg','n68.jpg']
            self.assertEqual(expected,[n.get('facs').split('/')[-1].replace('_medium','') for n in root.findall(f'.//{{{TEI}}}pb')][-4:])

    def test_hebrew_only_rubric_keeps_its_own_language(self):
        root=etree.Element('{'+TEI+'}div');root.set(XML+'lang','he')
        reading={'kind':'rubric','fragments':[fixtures.SecondDayTest.fragment('s66','כרחם אב · יי שמעה')]}
        unit=printed_unit(root,reading,'he','urn:x-opensiddur:text:siddur:fixture')
        self.assertEqual('he',unit.find(f'{{{TEI}}}note').get(XML+'lang'))
        self.assertEqual({('s66','he'):'כרחם אב · יי שמעה'},streams(root,include_notes=True))

    def test_english_running_header_is_not_a_pizmon_heading(self):
        root=poem('en','fixture',{'running_header':'PROPITIATORY PRAYERS FOR THE FIRST DAY.','rubric':'Repeat the refrain.','stanzas':['Opening.'], 'cues':{}, 'conclusion':'Say the prayer.'})
        self.assertIsNone(root.find(f'.//{{{TEI}}}head'))
        self.assertNotIn('PROPITIATORY PRAYERS',' '.join(root.itertext()))

    def test_third_day_kaddish_restores_its_own_calendar_scope(self):
        from opensiddur.importer.asher_selichot.second_day import conclusion
        root=etree.Element('{'+TEI+'}div')
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)
            (source/'first-day-continuation.json').write_text(json.dumps({'sections':{'closing':[{'id':'reader_kaddish'}]}}))
            conclusion(root,source,'third')
        declaration=root.find('{'+J+'}declare')
        self.assertEqual('third_day_kaddish',declaration.get(XML+'id'))
        self.assertEqual(['first_day','aseret-ymei-tshuva'],[n.get('name') for n in declaration.findall('.//{'+TEI+'}f')])
        self.assertEqual(['false','false'],[n.get('value') for n in declaration.findall('.//{'+TEI+'}binary')])
        self.assertEqual('urn:x-opensiddur:text:prayer:kaddish/shalem',root.find('{'+J+'}transclude').get('target'))
        self.assertEqual('#third_day_kaddish',root[-1].get('target'))

    def test_third_day_bookmark_must_be_above_its_pizmon(self):
        from opensiddur.importer.asher_selichot.check_book_pdf import day_bookmarks
        captions=('FIRST DAY','SECOND DAY','THIRD DAY')
        rows=[(0,'FIRST DAY',7,650),(1,'פזמון',22,600),(0,'SECOND DAY',37,600),(1,'פזמון',41,600),(0,'THIRD DAY',42,600),(1,'פזמון',47,600)]
        self.assertEqual(rows[::2],day_bookmarks(rows,captions))
        with self.assertRaisesRegex(ValueError,'top-level bookmark'):
            day_bookmarks(rows[:4]+[(1,*rows[4][1:]),rows[5]],captions)

    def test_contents_rejects_stale_pages_despite_correct_bookmarks(self):
        from opensiddur.importer.asher_selichot.check_book_pdf import check_contents
        tree=etree.Element('document');page=etree.SubElement(tree,'page')
        etree.SubElement(page,'line',text='Contents')
        line=etree.SubElement(page,'line',text='64')
        for x,char in enumerate('64'):etree.SubElement(line,'char',c=char,x=str(490+x*5),y='200')
        with self.assertRaisesRegex(ValueError,'TOC pages differ'):
            check_contents(tree,[(0,'THIRD DAY',2,600)],['62','63'])
        line[-1].set('c','3')
        check_contents(tree,[(0,'THIRD DAY',2,600)],['62','63'])
