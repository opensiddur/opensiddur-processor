import unittest
from lxml import etree
from opensiddur.importer.scan.authoring import TEI, J
from opensiddur.importer.scan.navigation import append_instruction


class NavigationTest(unittest.TestCase):
    def clauses(self):
        return [{'text': 'Stand. '},
                {'before': 'Continue on page ', 'after': '.',
                 'target': 'urn:x-opensiddur:text:prayer:invented@edition-he',
                 'replacement': 'With the congregation:',
                 'expansion': [{'target': 'urn:x-opensiddur:text:prayer:invented'}]},
                {'text': ' Bow afterwards.'}]

    def test_documentary_navigation_is_independently_removable(self):
        root = etree.Element('root')
        append_instruction(root, self.clauses())
        segment = root.find(f'.//{{{TEI}}}seg')
        self.assertEqual(segment.get('type'), 'optional-page-reference')
        self.assertEqual(segment.find(f'{{{TEI}}}ref').get('target'), self.clauses()[1]['target'])
        self.assertEqual(root[0].text, 'Stand. ')
        self.assertEqual(segment.tail, ' Bow afterwards.')

    def test_expanded_references_insert_text_between_actions(self):
        root = etree.Element('root')
        append_instruction(root, self.clauses(), expanded=True)
        self.assertEqual([e.tag for e in root], [f'{{{TEI}}}note', f'{{{J}}}transclude', f'{{{TEI}}}note'])
        self.assertEqual(''.join(root[0].itertext()), 'Stand. With the congregation:')
        self.assertEqual(root[1].get('target'), 'urn:x-opensiddur:text:prayer:invented')
        self.assertEqual(''.join(root[2].itertext()), ' Bow afterwards.')
        self.assertIsNone(root.find(f'.//{{{TEI}}}ref'))

    def test_expansion_is_mandatory_and_edition_independent(self):
        for value in ([], [{'target': 'urn:x-opensiddur:text:prayer:invented@edition-he'}]):
            clauses = self.clauses()
            clauses[1]['expansion'] = value
            with self.assertRaises(ValueError):
                append_instruction(etree.Element('root'), clauses, expanded=True)

    def test_documentary_reference_requires_edition(self):
        clauses = self.clauses()
        clauses[1]['target'] = 'urn:x-opensiddur:text:prayer:invented'
        with self.assertRaises(ValueError):
            append_instruction(etree.Element('root'), clauses)
