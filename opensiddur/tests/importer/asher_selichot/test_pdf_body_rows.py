"""Apparatus and counters must not interrupt rendered body-word checks."""
import unittest

from lxml import etree

from opensiddur.importer.asher_selichot.check_fast_pdf import body_text, glyph_rows


class BodyRowsTests(unittest.TestCase):
    def test_body_word_across_counter_and_apparatus(self):
        tree=etree.Element('document')
        for lines in [[('merciful and gra-',11,640,350),('5',8,640,498),('A source footnote.',9,670,350)],[('584',11,74,550),('cious',11,109,350)]]:
            page=etree.SubElement(tree,'page')
            for text,size,y,x in lines:
                line=etree.SubElement(page,'line');font=etree.SubElement(line,'font',size=str(size))
                for i,c in enumerate(text):etree.SubElement(font,'char',c=c,x=str(x+i*5),y=str(y),quad=f'{x+i*5} {y} {x+i*5+5} {y} {x+i*5} {y+10} {x+i*5+5} {y+10}')
        ordinary=' '.join(r[2]for r in glyph_rows(tree)[1]);self.assertIn('A source footnote.',ordinary)
        self.assertEqual(body_text(tree),'merciful and gracious')
