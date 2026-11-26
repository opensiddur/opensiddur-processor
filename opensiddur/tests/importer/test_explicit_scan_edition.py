"""Edition injection must preserve both provenance and unrelated witnesses."""
import copy
import unittest

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_1 import build
from opensiddur.importer.scan.authoring import TEI, XML, element


class ExplicitScanEditionTests(unittest.TestCase):
    def unit(self):
        return {'stem': 'example', 'urn': 'urn:x-opensiddur:text:prayer:example',
                'title': {'en': 'Synthetic witness'}, 'languages': {'en': [
                    {'paragraph': 1, 'fragments': [
                        {'scan': 's7', 'printed_page': '1', 'text': 'Opening'},
                        {'scan': 's8', 'printed_page': '1', 'text': 'Ending'}]}]}}

    def header(self, lang, project, title, urn, *, draft):
        root = etree.Element('{'+TEI+'}TEI', attrib={XML+'lang': lang})
        desc = element(element(root, 'teiHeader'), 'fileDesc')
        element(element(desc, 'titleStmt'), 'title', title)
        element(element(desc, 'publicationStmt'), 'idno', urn+'@'+project)
        element(element(desc, 'sourceDesc'), 'bibl', 'Second synthetic source')
        return root, element(element(root, 'text'), 'body')

    def test_other_edition_retains_unique_scans_without_mutating_defaults(self):
        unit = self.unit()
        before = etree.tostring(build.unit_document(unit, 'en', True))
        root = build.unit_document(copy.deepcopy(unit), 'en', True,
                                   projects={'en': 'another-edition-2000-en'},
                                   identifier='another-archive-item',
                                   document_factory=self.header)
        pages = root.findall('.//{'+TEI+'}pb')
        self.assertEqual([p.get('n') for p in pages], ['1', '1'])
        self.assertEqual([p.get('facs') for p in pages], [
            'https://archive.org/download/another-archive-item/page/n6.jpg',
            'https://archive.org/download/another-archive-item/page/n7.jpg'])
        self.assertTrue(root.find('.//{'+TEI+'}idno').text.endswith(
            '@another-edition-2000-en'))
        self.assertEqual(before, etree.tostring(build.unit_document(unit, 'en', True)))

    def test_reused_text_targets_the_selected_edition(self):
        unit = self.unit()
        unit['reuse'] = {'en': 'urn:x-opensiddur:text:prayer:earlier'}
        root = build.unit_document(unit, 'en', True,
                                   projects={'en': 'another-edition-2000-en'},
                                   identifier='another-archive-item',
                                   document_factory=self.header)
        target = root.find('.//{http://jewishliturgy.org/ns/jlptei/2}transclude')
        self.assertEqual(target.get('target'),
                         'urn:x-opensiddur:text:prayer:earlier@another-edition-2000-en')
        self.assertNotIn('mahzor-lyom-rishon', etree.tostring(root).decode())

    def test_conditional_and_deferred_boundaries_use_the_new_source(self):
        for deferred in (False, True):
            with self.subTest(deferred=deferred):
                unit = self.unit()
                conditional = {
                    'conditions': [{'type': 'opensiddur:rite',
                                    'features': {'frankfurt': True}}],
                    'fragments': [{'scan': 's8', 'printed_page': '2',
                                   'text': 'Conditional'}]}
                if deferred:
                    conditional.update(marked=True, fragments=[
                        {'scan': 's7', 'text': '(Optional', 'page_start': False},
                        {'scan': 's8', 'printed_page': '2', 'text': 'clause)',
                         'page_start': False}])
                unit['languages']['en'] = [
                    {'fragments': [{'scan': 's7', 'printed_page': '1', 'text': 'Start'}]},
                    conditional]
                if deferred:
                    unit['languages']['en'].append({
                        'deferred_page_boundary': True, 'fragments': [
                            {'scan': 's8', 'printed_page': '2', 'text': 'Continuation',
                             'page_start': False}]})
                root = build.unit_document(unit, 'en', True,
                                           projects={'en': 'another-edition-2000-en'},
                                           identifier='another-archive-item',
                                           document_factory=self.header)
                pages = root.findall('.//{'+TEI+'}pb')
                self.assertEqual(len(pages), 2)
                self.assertEqual(pages[-1].get('facs'),
                                 'https://archive.org/download/another-archive-item/page/n7.jpg')

    def test_paginated_commentary_keeps_its_own_edition_source(self):
        unit = self.unit()
        target = unit['urn']
        unit['citations'] = {'en': [{'scan': 's7', 'target': target,
                                    'note_type': 'commentary', 'text': 'FirstSecond'}]}
        unit['source_encoding'] = {'en': {'commentary_pages': [{
            'target': target, 'fragments': [
                {'scan': 's7', 'printed_page': '1', 'text': 'First'},
                {'scan': 's8', 'printed_page': '1', 'text': 'Second'}]}]}}
        root = build.unit_document(unit, 'en', True,
                                   projects={'en': 'another-edition-2000-en'},
                                   identifier='another-archive-item',
                                   document_factory=self.header)
        note = root.find('.//{'+TEI+'}note[@type="commentary"]')
        self.assertEqual(''.join(note.itertext()), 'FirstSecond')
        self.assertEqual([p.get('facs') for p in note.findall('.//{'+TEI+'}pb')], [
            'https://archive.org/download/another-archive-item/page/n6.jpg',
            'https://archive.org/download/another-archive-item/page/n7.jpg'])
