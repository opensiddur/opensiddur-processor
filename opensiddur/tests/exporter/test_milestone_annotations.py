"""Milestone apparatus follows the addressed words, in the same parallel row."""
import unittest

from lxml import etree

from opensiddur.exporter.milestone_annotations import place_milestone_annotations

NS = {"tei": "http://www.tei-c.org/ns/1.0"}
URN = "urn:x-opensiddur:text:prayer:demo/"


class TestMilestonePlacement(unittest.TestCase):
    def test_scope_crosses_paragraph_and_ignores_other_units_and_note_text(self):
        root = etree.fromstring(f'''<root xmlns:tei="{NS['tei']}">
          <tei:p><tei:milestone unit="verse" corresp="{URN}1"><tei:note>APPARATUS</tei:note></tei:milestone>First
          <tei:milestone unit="edition-verse" n="2"/>continued</tei:p>
          <tei:p>Last <tei:hi>words</tei:hi><tei:note>INLINE NOTE</tei:note>
          <tei:milestone unit="verse"/>Unrelated</tei:p></root>''')
        place_milestone_annotations([root])
        text = ' '.join(''.join(root.itertext()).split())
        self.assertIn('Last wordsAPPARATUSINLINE NOTE', text)
        self.assertFalse(root.xpath('.//tei:milestone/tei:note', namespaces=NS))

    def test_final_scope_and_multiple_notes_preserve_tail(self):
        root = etree.fromstring(f'''<root xmlns:tei="{NS['tei']}"><tei:p><tei:milestone unit="verse" corresp="{URN}1"><tei:note>ONE</tei:note><tei:note>TWO</tei:note></tei:milestone>Last words. </tei:p></root>''')
        place_milestone_annotations([root])
        self.assertEqual(''.join(root.itertext()), 'Last words.ONETWO ')

    def test_overlapping_scopes_end_before_containing_milestone(self):
        root = etree.fromstring(f'''<root xmlns:tei="{NS['tei']}"><tei:p>
          <tei:milestone unit="chapter" corresp="{URN}1"><tei:note>CHAPTER NOTE</tei:note></tei:milestone>
          <tei:milestone unit="verse" corresp="{URN}1/1"><tei:note>VERSE NOTE</tei:note></tei:milestone>Addressed words.
          <tei:milestone unit="chapter" corresp="{URN}2"/>Other chapter.</tei:p></root>''')
        place_milestone_annotations([root])
        text = ' '.join(''.join(root.itertext()).split())
        self.assertEqual(text, 'Addressed words.CHAPTER NOTEVERSE NOTE Other chapter.')
        self.assertFalse(root.xpath('.//tei:milestone/tei:note', namespaces=NS))
