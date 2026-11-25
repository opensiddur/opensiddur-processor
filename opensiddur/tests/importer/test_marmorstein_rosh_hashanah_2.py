"""Draft orchestration and front-matter semantics, using invented source data."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_2 import BOOK, PROJECTS
from opensiddur.importer.marmorstein_rosh_hashanah_2.build import main

NS = {'tei': 'http://www.tei-c.org/ns/1.0', 'j': 'http://jewishliturgy.org/ns/jlptei/2'}


class OpeningBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base/'sources'/BOOK
        self.source.mkdir(parents=True)
        reading = {'pages': [
            {'scan_page': 1, 'language': 'en', 'kind': 'cover',
             'lines': ['Invented series', 'XY', 'סמל', 'Volume Z'], 'line_languages': {'2': 'he'}},
            {'scan_page': 2, 'language': 'he', 'kind': 'title',
             'lines': ['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז', 'ח', 'ט']},
            {'scan_page': 3, 'language': 'en', 'kind': 'title',
             'lines': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']},
            {'scan_page': 4, 'language': 'en', 'kind': 'copyright',
             'lines': ['Invented copyright', 'Test Town']},
        ]}
        resolved = self.source/'front_resolved.json'
        resolved.write_text(json.dumps(reading), encoding='utf-8')
        batch = self.source/'batches/front_matter_s1_s4'
        batch.mkdir(parents=True)
        (batch/'checklist.json').write_text(json.dumps({'gates': {'adjudication': {
            'resolved_sha256': hashlib.sha256(resolved.read_bytes()).hexdigest()}}}), encoding='utf-8')
        layouts = {'2': {'main': [0], 'sub': [1], 'bylines': [[2, 3], [4, 5]], 'imprint': [6, 7, 8]},
                   '3': {'main': [0, 1, 2], 'bylines': [[3, 4]], 'imprint': [5, 6, 7]}}
        (self.source/'front_layout.json').write_text(json.dumps(layouts), encoding='utf-8')
        for project in PROJECTS.values():
            root = self.base/'projects'/project
            root.mkdir(parents=True)
            (root/'index.xml').write_text('existing index', encoding='utf-8')
            (root/'shared_prayer.xml').write_text('existing witness', encoding='utf-8')

    def run_builder(self, *extra):
        return main(['--draft', '--source-root', str(self.base/'sources'),
                     '--project-directory', str(self.base/'projects'), *extra])

    def test_preservation_multilingual_paratext_and_explicit_layout(self):
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.build.validate',
                   return_value=(True, [])) as validator:
            self.assertEqual(self.run_builder(), 0)
        self.assertEqual(validator.call_count, 2)
        for lang, project in PROJECTS.items():
            root = self.base/'projects'/project
            self.assertEqual((root/'index.xml').read_text(encoding='utf-8'), 'existing index')
            self.assertEqual((root/'shared_prayer.xml').read_text(encoding='utf-8'), 'existing witness')
            document = etree.parse(str(root/'day_two.xml'))
            self.assertEqual(document.xpath('string(/tei:TEI/@xml:lang)', namespaces=NS), lang)
            front = document.find('tei:text/tei:front', NS)
            self.assertEqual(len(front), 16)
            for offset in range(0, 16, 4):
                pb, gate, content, end = list(front)[offset:offset+4]
                self.assertEqual(etree.QName(pb).localname, 'pb')
                self.assertEqual(etree.QName(gate).localname, 'conditional')
                self.assertEqual(gate.xpath('string(tei:fs/@type)', namespaces=NS), 'opensiddur:paratext')
                self.assertEqual(gate.xpath('string(tei:fs/tei:f/@name)', namespaces=NS), 'title-page')
                self.assertEqual(end.get('target'), '#'+gate.get('{http://www.w3.org/XML/1998/namespace}id'))
            self.assertEqual(len(set(document.xpath('//@xml:id', namespaces=NS))),
                             len(document.xpath('//@xml:id', namespaces=NS)))
            self.assertEqual(document.xpath('//tei:titlePage/@xml:lang', namespaces=NS), ['he', 'en', 'en'])
            self.assertEqual(document.xpath('string(//tei:foreign/@xml:lang)', namespaces=NS), 'he')
            self.assertEqual(document.xpath('string(//tei:foreign)', namespaces=NS), 'סמל')
            self.assertEqual(document.xpath('count(//tei:titlePage[@xml:id="day_two_s3"]/tei:docTitle/tei:titlePart[@type="main"]/tei:lb)', namespaces=NS), 2)
            self.assertEqual(document.xpath('count(//tei:titlePage[@xml:id="day_two_s3"]/tei:byline/tei:lb)', namespaces=NS), 1)
            self.assertEqual(document.xpath('string(//tei:titlePage[@xml:id="day_two_s4"]/tei:docImprint)', namespaces=NS), 'Invented copyrightTest Town')

    def test_stale_adjudication_cannot_rewrite_documents(self):
        with (self.source/'front_resolved.json').open('a', encoding='utf-8') as stream:
            stream.write(' ')
        with self.assertRaisesRegex(ValueError, 'Stale front-matter adjudication'):
            self.run_builder()
        self.assertFalse(any((self.base/'projects').glob('*/day_two.xml')))

    def test_explicit_bibliography_update_preserves_all_existing_index_content(self):
        original = ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:teiHeader>'
                    '<tei:fileDesc><tei:sourceDesc><tei:bibl xml:id="original">Original book</tei:bibl>'
                    '</tei:sourceDesc></tei:fileDesc></tei:teiHeader><tei:text><tei:body>'
                    '<tei:p>Retained prayer</tei:p></tei:body></tei:text></tei:TEI>')
        for project in PROJECTS.values():
            (self.base/'projects'/project/'index.xml').write_text(original, encoding='utf-8')
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.build.validate',
                   return_value=(True, [])) as validator:
            self.assertEqual(self.run_builder('--update-bibliography'), 0)
        self.assertEqual(validator.call_count, 4)
        parser = etree.XMLParser(remove_blank_text=True)
        for project in PROJECTS.values():
            after = etree.parse(str(self.base/'projects'/project/'index.xml'), parser).getroot()
            added = after.xpath('//tei:bibl[@xml:id="day_two_source_bibl"]', namespaces=NS)
            self.assertEqual(len(added), 1)
            added[0].getparent().remove(added[0])
            self.assertEqual(etree.tostring(after, method='c14n'),
                             etree.tostring(etree.fromstring(original, parser), method='c14n'))
