"""Unequal printed refrain positions and the penitential service context."""
import copy
import unittest

from lxml import etree

from opensiddur.importer.asher_selichot import penitential_second_day as day
from opensiddur.importer.asher_selichot.build import TEI, XML
from opensiddur.importer.scan.reverse import streams


class PenitentialSecondDayTests(unittest.TestCase):
    def test_internal_hebrew_cue_has_no_invented_english_counterpart(self):
        fragment={'he':{'scan':'s226','printed_page':'112','text':'עֲרֹבָה׃ בין כסה בְּתַחֲנוּנִים׃ בין כסה'},
                  'en':{'scan':'s227','printed_page':'112','text':'Be surety. With supplications. (Between, &c.)'},
                  'notes':{'he':[],'en':[{'anchor':'surety.','text':'A printed note.'}]}}
        reading={'fragments':[fragment],'stanzas':[{'fragments':[fragment]}],
                 'refrain':{'he':'בֵּין כֶּסֶה׃','en':'Between the days.'}}
        before=copy.deepcopy(reading)
        for lang,count in [('he',2),('en',1)]:
            root=etree.Element('{'+TEI+'}body');root.set(XML+'lang',lang)
            day.pizmon(root,reading,lang,'urn:example')
            choices=root.findall('.//{'+TEI+'}choice')
            self.assertEqual(len(choices),count)
            for choice in choices:choice.remove(choice.find('{'+TEI+'}expan'))
            self.assertEqual(' '.join(streams(root,include_notes=False).values()).strip(),fragment[lang]['text'])
            self.assertEqual(len(root.findall('.//{'+TEI+'}note')),0 if lang=='he' else 1)
        self.assertEqual(reading,before)

    def test_continued_opening_retains_both_scan_identities(self):
        a={'he':{'scan':'s224','printed_page':'111','text':'בֵּין כֶּסֶה'},'en':{'scan':'s225','printed_page':'111','text':'Between the days'},'notes':{'he':[],'en':[]}}
        b={'he':{'scan':'s226','printed_page':'112','text':'נִרְאֶה אוֹר׃'},'en':{'scan':'s227','printed_page':'112','text':'we see light.'},'notes':{'he':[],'en':[]}}
        reading={'fragments':[a,b],'stanzas':[{'fragments':[a,b]}],'refrain':{'he':'בֵּין כֶּסֶה נִרְאֶה אוֹר׃','en':'Between the days we see light.'}}
        for lang in ['he','en']:
            root=etree.Element('{'+TEI+'}body');root.set(XML+'lang',lang)
            day.pizmon(root,reading,lang,'urn:example')
            self.assertEqual(set(streams(root)),{(a[lang]['scan'],lang),(b[lang]['scan'],lang)})
            self.assertEqual(len(root.findall('.//{'+TEI+'}milestone[@corresp]')),1)
            if lang=='he':
                lines=root.findall('.//{'+TEI+'}l')
                self.assertEqual(len(lines),1)
                self.assertEqual(lines[0].find('.//{'+TEI+'}pb').get('facs'),'https://archive.org/download/selichothdavidasher1912/page/n225_medium.jpg')

    def test_supplied_kaddish_uses_ten_days_and_restores_scope(self):
        root=etree.Element('{'+TEI+'}div');day.full_kaddish(root)
        self.assertEqual([n.get('value') for n in root.findall('.//{'+TEI+'}binary')],['false','true'])
        self.assertEqual(root[-1].get('target'),'#'+root[0].get(XML+'id'))
        self.assertEqual(root[1].get('target'),day.PRAYER+'kaddish/shalem')

    def test_page_52_petitions_use_one_shared_inline_alignment(self):
        root=etree.Element('{'+TEI+'}div')
        reading={'id':'verses_after_example','expansion_targets':['mercy','father','daniel']}
        day.expanded_rubric(root,reading,'en')
        self.assertEqual([n.get('target') for n in root.findall('.//{'+day.J+'}transclude')],reading['expansion_targets'])
        self.assertTrue(all(n.get('type')=='inline' for n in root.findall('.//{'+day.J+'}transclude')))
        self.assertEqual(root.find('.//{'+TEI+'}milestone').get('corresp'),day.PENITENTIAL_SECOND_DAY+'/verses_after_example/expanded')

    def test_contents_ordinal_is_not_a_page_number(self):
        from opensiddur.importer.asher_selichot.check_book_pdf import check_contents
        tree=etree.Element('document');page=etree.SubElement(tree,'page')
        etree.SubElement(page,'line',text='Contents')
        line=etree.SubElement(page,'line',text='Prayers for the 2nd penitential day')
        etree.SubElement(line,'char',c='2',x='300',y='100')
        number=etree.SubElement(page,'line',text='115')
        for c,x in zip('115',[486,491,496]):etree.SubElement(number,'char',c=c,x=str(x),y='100')
        check_contents(tree,[(0,'service',1,None)],['115'])
        number[0].set('c','9')
        with self.assertRaises(ValueError):check_contents(tree,[(0,'service',1,None)],['115'])

    def test_contents_continuation_page_is_checked(self):
        from opensiddur.importer.asher_selichot.check_book_pdf import check_contents
        tree=etree.Element('document')
        pages=[etree.SubElement(tree,'page') for _ in range(4)]
        etree.SubElement(pages[0],'line',text='Contents')
        for number,page in enumerate(pages[:2],1):
            line=etree.SubElement(page,'line',text=str(number))
            etree.SubElement(line,'char',c=str(number),x=str(490 if number==1 else 526),y='100')
        ordinal=etree.SubElement(pages[1],'line',text='3rd penitential day')
        etree.SubElement(ordinal,'char',c='3',x='480',y='80')
        rows=[(0,'service',3,None),(1,'pizmon',4,None)]
        labels=['i','ii','1','2']
        check_contents(tree,rows,labels)
        pages[1].find('.//char').set('c','9')
        with self.assertRaises(ValueError):check_contents(tree,rows,labels)

    def test_previous_service_note_is_excluded_from_following_service(self):
        from opensiddur.importer.asher_selichot.check_book_pdf import slice_day
        tree=etree.Element('document');page=etree.SubElement(tree,'page',height='800')
        for text,y,size in [('new service',300,12),('earlier note',700,9),('new note',720,9)]:
            line=etree.SubElement(page,'line',text=text)
            font=etree.SubElement(line,'font',size=str(size))
            etree.SubElement(font,'char',c=text[0],x='100',y=str(y))
        clipped=slice_day(tree,(0,'new service',1,500),prior_note_texts=('earlier note',))
        self.assertEqual([l.get('text')for l in clipped.findall('.//line')],['new service','new note'])

    def test_previous_service_note_below_next_heading_is_retained(self):
        from opensiddur.importer.asher_selichot.check_book_pdf import slice_day
        tree=etree.Element('document');page=etree.SubElement(tree,'page',height='800')
        for text,y,size in [('last prayer',100,12),('next service',200,12),('earlier note',700,9),('other note',720,9)]:
            line=etree.SubElement(page,'line',text=text)
            font=etree.SubElement(line,'font',size=str(size))
            etree.SubElement(font,'char',c='x',x='400',y=str(y))
        result=slice_day(tree,(0,'old',1,750),(0,'new',1,600),trailing_note_texts=('earlier note',))
        self.assertEqual([n.get('text') for n in result.findall('.//line')],['last prayer','earlier note'])
