"""Geometry and text measurement on synthetic PDFs' extracted glyph trees."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from lxml import etree

from opensiddur.importer.scan import pdf


def page(tree, height=800):
    return etree.SubElement(tree, 'page', height=str(height))


def line(parent, text, x, y, *, size=12, step=5, name='fixture'):
    row = etree.SubElement(parent, 'line', text=text)
    font = etree.SubElement(row, 'font', size=str(size), name=name)
    for i, c in enumerate(text):
        left = x+i*step
        etree.SubElement(font,'char',c=c,x=str(left),y=str(y),
                         quad=f'{left} {y} {left+4} {y} {left} {y+10} {left+4} {y+10}')
    return row


class PdfMeasurementTests(unittest.TestCase):
    def test_mirrored_gutters_pointing_and_geometric_word_gaps(self):
        tree = etree.Element('document')
        first = page(tree)
        line(first, 'בא', 80, 120)  # Glyph order by increasing x, reads אב.
        line(first, 'ab', 110, 120)
        line(first, 'cd', 140, 120)
        line(first, 'tiny', 110, 150, size=8)
        second = page(tree)
        line(second, 'הדג', 105, 180)
        line(second, 'tail', 130, 180)
        he, en, headings = pdf.glyph_rows(tree,gutters=(100,120),heading='אב')
        self.assertEqual(he,[(1,120,'אב'),(2,180,'גדה')])
        self.assertEqual(en,[(1,120,'ab cd'),(1,150,'tiny'),(2,180,'tail')])
        self.assertEqual(headings,[(1,120)])
        self.assertNotIn('tiny',[r[2] for r in pdf.glyph_rows(tree,minimum_font_size=10,gutters=(100,120))[1]])
        line(second, 'בא2', 30, 220)
        self.assertEqual(pdf.glyph_rows(tree,gutters=(100,120),heading='אב')[2],[(1,120)])

    def test_body_excludes_small_notes_and_joins_hyphenation_across_page_header(self):
        tree=etree.Element('document'); first=page(tree)
        line(first,'a mer-',120,120)
        line(first,'5',150,120,size=8)
        line(first,'apparatus',120,300,size=9)
        second=page(tree)
        line(second,'2',170,40)
        line(second,'cy.',130,120)
        self.assertEqual(pdf.body_text(tree,gutters=(100,120),minimum_font_size=10,header_bottom=80),'a mercy.')
        self.assertEqual(pdf.strip_numeric_markers('word 12, more 4 text.'),'word, more text.')

    def test_normalization_can_be_supplied_by_caller(self):
        tree=etree.Element('document');line(page(tree),'\ue049',150,100)
        normalize=lambda form,text:text.replace('\ue049','Th')
        self.assertEqual(pdf.glyph_rows(tree,gutters=(100,),normalize=normalize)[1][0][2],'Th')
        self.assertEqual(pdf.body_text(tree,gutters=(100,),minimum_font_size=10,header_bottom=80,normalize=normalize),'Th')

    def test_latin_apparatus_groups_fragments_without_reordering_glyphs(self):
        tree=etree.Element('document');p=page(tree)
        line(p,'AB',50,700,size=9)
        line(p,'CD',70,700,size=9)
        line(p,'א.',90,700,size=9)
        line(p,'XYZ',50,720,size=9)
        line(p,'BODY',50,100,size=12)
        runs=pdf.latin_note_runs(tree,maximum_font_size=10)
        self.assertEqual(len(runs),1)
        chars=next(iter(runs.values()))
        self.assertEqual(''.join(c.get('c')for c in chars),'ABCD')
        self.assertEqual([float(c.get('x'))for c in chars],[50,55,70,75])

    def test_outline_hierarchy_and_optional_top(self):
        a=SimpleNamespace(title='Service A',top=700)
        b=SimpleNamespace(title='Song',top=None)
        c=SimpleNamespace(title='Service B',top=600)
        reader=Mock(outline=[a,[b],c]);reader.get_destination_page_number.side_effect=[2,2,4]
        self.assertEqual(pdf.outline_rows(reader),[(0,'Service A',3,700),(1,'Song',3,None),(0,'Service B',5,600)])

    def test_bookmarks_require_unique_top_level_parent_and_its_own_child(self):
        rows=[(0,'Service A',3,700),(1,'Song',3,600),(0,'Service B',5,700),(1,'Song',5,600)]
        self.assertEqual(pdf.day_bookmarks(rows,['Service A','Service B'],child_caption='Song'),[rows[0],rows[2]])
        for broken in [rows+[rows[0]],rows[1:],rows[:1]+rows[2:],[(1,*rows[0][1:])]+rows[1:]]:
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                pdf.day_bookmarks(broken,['Service A','Service B'],child_caption='Song')

    def test_contents_uses_profile_columns_labels_and_current_destinations(self):
        tree=etree.Element('document');line(page(tree),'front',10,100)
        odd=page(tree);line(odd,'Contents',10,100);line(odd,'5',130,200)
        even=page(tree);line(even,'3rd',110,100);line(even,'10',110,200)
        line(page(tree),'Body',10,100)
        rows=[(0,'A',4,700),(1,'B',5,700)]
        labels=['i','ii','iii','5','10']
        # Page 2's number column is 120, page 3's is100; the ordinal at110
        # deliberately belongs to the non-number column on page 2 instead.
        ordinal=even.find('line');ordinal.getparent().remove(ordinal);line(odd,'3rd',110,100)
        pdf.check_contents(tree,rows,labels,number_columns=(100,120),caption='Contents')
        with self.assertRaisesRegex(ValueError,'TOC pages differ'):
            pdf.check_contents(tree,rows,['i','ii','iii','6','10'],number_columns=(100,120),caption='Contents')
        broken=copy.deepcopy(tree)
        chars=broken.findall('page')[2].findall('.//char')
        digits=[c for c in chars if c.get('c').isdigit()]
        digits[0].set('x','120');digits[1].set('x','110')
        with self.assertRaisesRegex(ValueError,'Reversed TOC'):
            pdf.check_contents(broken,rows,labels,number_columns=(100,120),caption='Contents')

    def test_section_clipping_preserves_page_slots_and_source_owned_notes(self):
        tree=etree.Element('document')
        line(page(tree),'title',10,100)
        first=page(tree);line(first,'before',10,90);line(first,'inside',10,150)
        line(first,'prior note',10,180,size=9)
        end=page(tree);line(end,'before end',10,100);line(end,'following',10,250)
        line(end,'trailing note',10,700,size=9);line(end,'trailing note body',10,730,size=12)
        etree.SubElement(end,'line',text='no glyphs')
        result=pdf.slice_day(tree,(0,'A',2,700),(0,'B',3,600),True,
                             ('trailing note',),('prior note',),title_pages=1,
                             maximum_note_size=10,boundary_tolerance=2)
        self.assertEqual(len(result.findall('page')),3)
        self.assertEqual([l.get('text')for l in result.findall('.//line')],
                         ['title','inside','before end','trailing note'])
        self.assertEqual(len(tree.findall('.//line')),9)  # Input unchanged.
        remaining=pdf.slice_day(tree,(0,'A',2,700),title_pages=0,
                                maximum_note_size=10,boundary_tolerance=2)
        self.assertFalse(remaining.findall('page')[0].findall('.//line'))
        self.assertIn('following',[l.get('text')for l in remaining.findall('.//line')])
