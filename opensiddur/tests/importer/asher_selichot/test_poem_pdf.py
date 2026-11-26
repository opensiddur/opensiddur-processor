"""The full book may contain short stanza anchors before the target poem."""
import unittest

from lxml import etree

from opensiddur.importer.asher_selichot.check_pdf import ENGLISH, HEBREW, check


class PoemPdfTest(unittest.TestCase):
    def fixture(self):
        tree = etree.Element('document')
        page = etree.SubElement(tree, 'page')
        earlier = etree.SubElement(page, 'line', text='יוצר Omnipotent King, who The hope of Israel')
        for i, char in enumerate('יוצר'):
            etree.SubElement(earlier, 'char', c=char, x=str(250-i), y='30')
        page = etree.SubElement(tree, 'page')
        for i, (he, en) in enumerate(zip(HEBREW, ENGLISH)):
            line = etree.SubElement(page, 'line', text=he+' '+en)
            for n, char in enumerate(he):
                etree.SubElement(line, 'char', c=char, x=str(250-n), y=str(100+i*20))
            for n, char in enumerate(en):
                etree.SubElement(line, 'char', c=char, x=str(400+n), y=str(100+i*20))
        etree.SubElement(page, 'line', text='Appease thy anger and pardon our sins. '
            'Wherever the word Say “Omnipotent King,” (Hearken,')
        return tree

    def test_complete_book_ignores_matching_anchor_before_poem(self):
        self.assertEqual([0]*8, check(self.fixture(), expanded=False, complete=True))

    def test_actual_poem_misalignment_is_still_rejected(self):
        tree = self.fixture()
        line = tree.findall('page')[1].findall('line')[4]
        for char in line.findall('char'):
            if float(char.get('x')) > 324:
                char.set('y', str(float(char.get('y'))+50))
        with self.assertRaisesRegex(ValueError, 'Stanza alignment failed'):
            check(tree, expanded=False, complete=True)
