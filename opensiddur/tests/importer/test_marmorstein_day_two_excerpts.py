"""Draft excerpt invariants with invented text and source inputs."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_2 import BOOK, PROJECTS
from opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers import main

NS = {'t': 'http://www.tei-c.org/ns/1.0', 'j': 'http://jewishliturgy.org/ns/jlptei/2'}


class ExcerptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.source = self.base/'sources'/BOOK
        self.recipe_path = self.source/'batches/maariv_s5_s24/draft_units.json'
        self.recipe_path.parent.mkdir(parents=True)
        (self.source/'reading.txt').write_text('Invented reading', encoding='utf-8')
        self.recipe = {'input_sha256': {'reading.txt': hashlib.sha256(
            (self.source/'reading.txt').read_bytes()).hexdigest()}, 'units': [{
                'file': 'invented_prayer', 'urn': 'urn:x-opensiddur:text:prayer:invented',
                'verse_urn': 'urn:x-opensiddur:text:bible:psalms/7/2',
                'chapter': '7', 'verse': '2', 'titles': {'he': 'בדיקה', 'en': 'Test'},
                'he': {'scan_page': 23, 'printed_page': '9', 'citation': 'תהלים ז:ב',
                       'content': ['אב ', {'divine_name': 'יְיָ'}, ' ', {'large_letter': 'ג'}]}}]}
        for project in PROJECTS.values():
            path = self.base/'projects'/project
            path.mkdir(parents=True)
            (path/'index.xml').write_text('Keep accepted index', encoding='utf-8')

    def run_builder(self):
        self.recipe_path.write_text(json.dumps(self.recipe), encoding='utf-8')
        return main(['--draft', '--source-root', str(self.base/'sources'),
                     '--project-directory', str(self.base/'projects')])

    def test_exact_scope_semantics_and_absent_translation_cleanup(self):
        stale = self.base/'projects'/PROJECTS['en']/'invented_prayer.xml'
        stale.write_text('Previously generated counterpart', encoding='utf-8')
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers.validate',
                   return_value=(True, [])):
            self.run_builder()
        self.assertFalse(stale.exists())
        root = etree.parse(str(self.base/'projects'/PROJECTS['he']/'invented_prayer.xml'))
        self.assertEqual(root.xpath('string(//t:body/t:div/t:pb/@n)', namespaces=NS), '9')
        self.assertIn('/page/n22', root.xpath('string(//t:pb/@facs)', namespaces=NS))
        self.assertEqual(root.xpath('string(//t:sourceDesc//t:ptr/@target)', namespaces=NS),
                         f'/{PROJECTS["he"]}/index#day_two_source_bibl')
        self.assertEqual(root.xpath('string(//j:divineName)', namespaces=NS), 'יְיָ')
        self.assertEqual(root.xpath('string(//t:c)', namespaces=NS), 'ג')
        paragraph = root.find('.//t:body/t:div/t:p', NS)
        self.assertEqual(''.join(paragraph.find('t:seg', NS).itertext()), 'אב יְיָ ג')
        self.assertEqual(root.xpath('//t:milestone[@unit="chapter"]/@corresp', namespaces=NS), [])
        self.assertEqual(root.xpath('//t:milestone[@unit="verse"]/@corresp', namespaces=NS),
                         ['urn:x-opensiddur:text:bible:psalms/7/2'])
        self.assertEqual([node.get('unit') for node in list(paragraph)[-2:]], ['verse', 'chapter'])
        self.assertNotIn('תהלים', ''.join(paragraph.itertext()))
        for project in PROJECTS.values():
            self.assertEqual((self.base/'projects'/project/'index.xml').read_text(encoding='utf-8'),
                             'Keep accepted index')

    def test_stale_reading_cannot_write_or_remove_any_witness(self):
        path = self.base/'projects'/PROJECTS['en']/'invented_prayer.xml'
        path.write_text('Retain until inputs current', encoding='utf-8')
        (self.source/'reading.txt').write_text('Changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Stale excerpt input'):
            self.run_builder()
        self.assertEqual(path.read_text(encoding='utf-8'), 'Retain until inputs current')
        self.assertFalse((self.base/'projects'/PROJECTS['he']/'invented_prayer.xml').exists())

    def test_paired_witnesses_share_scope_with_independent_words_and_scan_links(self):
        self.recipe['units'][0]['en'] = {
            'scan_page': 24, 'printed_page': '9', 'citation': 'Psalms 7:2',
            'content': ['An invented translation.']}
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers.validate',
                   return_value=(True, [])):
            self.run_builder()
        documents = [etree.parse(str(self.base/'projects'/PROJECTS[lang]/'invented_prayer.xml'))
                     for lang in ['he', 'en']]
        for xpath in ['//t:body/t:div/@corresp', '//t:milestone[@unit="verse"]/@corresp']:
            self.assertEqual(documents[0].xpath(xpath, namespaces=NS),
                             documents[1].xpath(xpath, namespaces=NS))
        self.assertIn('/page/n23', documents[1].xpath('string(//t:pb/@facs)', namespaces=NS))
        self.assertEqual(documents[1].xpath('string(//t:body//t:seg)', namespaces=NS),
                         'An invented translation.')
        self.assertEqual(documents[1].xpath('string(//t:note//t:ref)', namespaces=NS), 'Psalms 7:2')

    def test_empty_provenance_cannot_bypass_guard(self):
        self.recipe['input_sha256'] = {}
        with self.assertRaisesRegex(ValueError, 'at least one source input'):
            self.run_builder()

    def test_schema_failure_does_not_remove_missing_counterpart(self):
        path = self.base/'projects'/PROJECTS['en']/'invented_prayer.xml'
        path.write_text('Retained on failed validation', encoding='utf-8')
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers.validate',
                   return_value=(False, ['invented failure'])):
            with self.assertRaisesRegex(ValueError, 'invented failure'):
                self.run_builder()
        self.assertTrue(path.exists())

    def test_forbid_index_overwrite_and_duplicate_files(self):
        self.recipe['units'][0]['file'] = 'index'
        with self.assertRaisesRegex(ValueError, 'non-index'):
            self.run_builder()
        self.recipe['units'][0]['file'] = 'valid_name'
        self.recipe['units'].append(self.recipe['units'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.run_builder()
