"""Shared prayer fragments retain exact text and bounded transclusion ranges."""
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.birnbaum_scan.build.shared_passages import split_paragraph
from opensiddur.tests.importer.birnbaum_scan.test_milestones import resolve

URN = 'urn:x-opensiddur:text:prayer:synthetic'


class TestSharedParagraph(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def test_parentheses_stay_outside_reusable_fragments(self):
        body = f'<tei:div corresp="{URN}"><tei:p>(Opening. Closing.)</tei:p></tei:div>'
        split = split_paragraph(body, URN, 'Closing.')
        self.assertEqual(resolve(self.directory, split, URN+'/opening'), 'Opening.')
        self.assertEqual(resolve(self.directory, split, URN+'/seal'), 'Closing.')
        tree = etree.fromstring(('<r xmlns:tei="http://www.tei-c.org/ns/1.0">'+split+'</r>').encode())
        self.assertEqual(''.join(tree.itertext()), '(Opening. Closing.)')

    def test_markup_and_trailing_content_are_preserved(self):
        body = (f'<tei:div corresp="{URN}"><tei:p>First <tei:seg>quoted</tei:seg> text. '
                'End.</tei:p><tei:p>Unrelated.</tei:p></tei:div>')
        split = split_paragraph(body, URN, 'End.')
        self.assertEqual(resolve(self.directory, split, URN+'/opening'), 'First quoted text.')
        self.assertEqual(resolve(self.directory, split, URN+'/seal'), 'End.')
        self.assertIn('<tei:seg>quoted</tei:seg>', split)
        self.assertIn('<tei:p>Unrelated.</tei:p>', split)

    def test_missing_and_ambiguous_boundaries_fail(self):
        for content, boundary in (('No match.', 'Closing.'), ('Repeat. Repeat.', 'Repeat.')):
            with self.subTest(content=content), self.assertRaises(ValueError):
                split_paragraph(f'<tei:div corresp="{URN}"><tei:p>{content}</tei:p></tei:div>',URN,boundary)
        with self.assertRaises(ValueError):
            split_paragraph('<tei:div><tei:p>Text.</tei:p></tei:div>',URN,'Text.')


class TestDetachedDivision(unittest.TestCase):
    def test_occurrence_condition_stays_with_caller(self):
        from opensiddur.importer.birnbaum_scan.build.shared_passages import (
            detach_division,
        )
        leaf = f'<tei:div corresp="{URN}"><tei:p>Shared words.</tei:p></tei:div>'
        prayer = dict(name='caller',urn=URN+'/caller',title='Caller',first=1,last=3,
            body='<j:conditional xml:id="occasion"/>'+leaf+'<j:endConditional target="#occasion"/>')
        detached = detach_division(prayer,URN,'shared')
        self.assertEqual(detached['body'],leaf)
        self.assertNotIn('conditional',detached['body'])
        self.assertIn('<j:transclude type="external" target="'+URN+'"/>',prayer['body'])
        self.assertIn('target="#occasion"',prayer['body'])
