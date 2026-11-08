"""Edition wiring contracts with invented words, temporary sources and mocked I/O."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_1 import profile, PROJECTS, EXPANDED
from opensiddur.importer.marmorstein_rosh_hashanah_1.build import build, unit_text
from opensiddur.importer.marmorstein_rosh_hashanah_1.download import download, regenerate
from opensiddur.importer.marmorstein_rosh_hashanah_1.verify import report
from opensiddur.importer.scan.review import review, reading_hash
from opensiddur.importer.util.internet_archive import write_if_changed

T = '{http://www.tei-c.org/ns/1.0}'
J = '{http://jewishliturgy.org/ns/jlptei/2}'
BASE = 'urn:x-opensiddur:text:prayer:'


class EditionWiringTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.book = profile(self.directory/'sources', self.directory/'cache')
        self.source = self.book.source_directory
        self.source.mkdir(parents=True)
        self.projects = self.directory/'project'
        def fragment(scan, text):
            return {'scan': scan, 'printed_page': '7', 'text': text}
        self.readings = {'units': [
            {'stem': 'first', 'urn': BASE+'invented', 'title': {'he': 'דוגמה', 'en': 'Example'},
             'languages': {'he': [{'fragments': [fragment('s1', 'אב יי'), fragment('s2', 'גד')]}],
                           'en': [{'fragments': [fragment('s3', 'אב Invented words.')]}]}},
            {'stem': 'second', 'urn': BASE+'another', 'title': {'he': 'אחר', 'en': 'Another'},
             'languages': {'he': [{'fragments': [fragment('s4', 'דה')]}]}}
        ], 'navigation': {'return': {'raw': 'Read page 7.', 'printed_page': '7',
             'scan': {'he': 's2', 'en': 's3'}, 'clauses': [
                 {'text': 'Stand. '}, {'before': 'Read page ', 'after': '.',
                  'target': BASE+'invented@{project}', 'replacement': 'Read now:',
                  'expansion': [{'target': BASE+'invented'}]}]}},
            'source_order': [{'unit': 'first'}, {'navigation': 'return'}, {'unit': 'second'}],
            'expanded_order': [{'navigation': 'return'}, {'unit': 'second'}]}
        self.save('readings', self.readings)
        registry = Mock()
        registry.records = {BASE+'invented': {}, BASE+'another': {}}
        registry.resolve.side_effect = lambda urn: urn
        self.registry = patch('opensiddur.importer.marmorstein_rosh_hashanah_1.build.load_registry',
                              return_value=(registry, []))
        self.registry.start()
        self.addCleanup(self.registry.stop)
        self.validation = patch('opensiddur.importer.marmorstein_rosh_hashanah_1.build.validate',
                                return_value=(True, []))
        self.validator = self.validation.start()
        self.addCleanup(self.validation.stop)

    def save(self, name, value):
        (self.source/(name+'.json')).write_text(json.dumps(value, ensure_ascii=False))

    def generate(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return build(self.source, self.projects, **kwargs)

    def test_sparse_translation_and_shared_expanded_order(self):
        stale = self.projects/PROJECTS['en']/'second.xml'
        stale.parent.mkdir(parents=True)
        stale.write_text('An obsolete translation must not survive regeneration.')
        self.generate(draft=True)
        self.assertFalse((self.projects/PROJECTS['en']/'second.xml').exists())
        primary = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        pages = primary.findall('.//'+T+'pb')
        self.assertEqual([p.get('n') for p in pages], ['7', '7'])
        self.assertNotEqual(pages[0].get('facs'), pages[1].get('facs'))
        self.assertEqual(primary.find('.//'+J+'divineName').text, 'יי')
        expanded = etree.parse(str(self.projects/EXPANDED/'index.xml'))
        targets = [e.get('target') for e in expanded.findall('.//'+J+'transclude')]
        self.assertEqual(targets, [BASE+'invented', BASE+'another'])
        self.assertFalse(expanded.findall('.//'+T+'ref[@type="page"]'))
        self.assertIn('Stand.', ''.join(expanded.getroot().itertext()))
        original = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        reference = original.find('.//'+T+'ref[@type="page"]')
        self.assertEqual(reference.get('target'), BASE+'invented@'+PROJECTS['he'])

    def test_unreviewed_or_stale_text_cannot_replace_a_reviewed_build(self):
        with self.assertRaisesRegex(ValueError, 'review pending'):
            self.generate()
        reviews = {}
        def accepted(text):
            entry = review(text, text, primary_model='first-reader', independent_model='second-reader', evidence='scan')
            entry['final_sha256'] = reading_hash(text)
            return entry
        for unit in self.readings['units']:
            for lang in unit['languages']:
                reviews[unit['stem']+'/'+lang] = accepted(unit_text(unit, lang))
        for lang in ('he', 'en'):
            reviews['navigation/return/'+lang] = accepted('Read page 7.')
        self.save('reviews', reviews)
        self.generate()
        path = self.projects/PROJECTS['he']/'first.xml'
        before = path.read_bytes()
        self.readings['units'][0]['languages']['he'][0]['fragments'][0]['text'] = 'changed'
        self.save('readings', self.readings)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.generate()
        self.assertEqual(path.read_bytes(), before)

    def test_all_schema_checks_finish_before_any_output_is_written(self):
        self.validator.side_effect = [(True, []), (False, ['synthetic schema failure'])]
        with self.assertRaisesRegex(ValueError, 'synthetic schema failure'):
            self.generate(draft=True)
        self.assertFalse(self.projects.exists())

    def test_front_matter_retains_its_language_and_scan_links(self):
        self.save('front', {'pages': [
            {'scan': 's5', 'kind': 'title', 'language': 'en',
             'paragraphs': ['Invented title', 'Arranged by Example', 'Translated by Another',
                            'Imaginary Press', 'Imaginary City']},
            {'scan': 's6', 'kind': 'copyright', 'language': 'en', 'paragraphs': ['Invented imprint']},
            {'scan': 's7', 'kind': 'preface', 'language': 'en', 'head': 'Preface', 'paragraphs': ['Invented preface']},
            {'scan': 's8', 'kind': 'blank', 'language': None, 'paragraphs': []}]})
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        front = root.find('.//'+T+'front')
        self.assertEqual(len(front.findall('.//'+T+'pb')), 3)
        self.assertEqual(front.find(T+'titlePage').get('{http://www.w3.org/XML/1998/namespace}lang'), 'en')
        self.assertIn('Invented preface', ''.join(front.itertext()))
        self.assertTrue(all('/page/n' in p.get('facs') for p in front.findall('.//'+T+'pb')))

    def test_printed_citation_precedes_its_prayer_without_a_duplicate_page_break(self):
        self.readings['units'][0]['languages']['en'][0]['corresp'] = BASE+'invented/1'
        self.readings['units'][0]['citations'] = {'en': [
            {'scan': 's3', 'printed_page': '7', 'text': '(Invented source.)'}]}
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['en']/'first.xml'))
        body = root.find('.//'+T+'body')
        citation = body.find('.//'+T+'note[@type="description"]')
        self.assertEqual(citation.text, '(Invented source.)')
        self.assertEqual(citation.getprevious().tag, T+'milestone')
        self.assertEqual(len(body.findall('.//'+T+'pb')), 1)

    def test_download_inventory_does_not_promote_machine_labels(self):
        scan = '<book><pageData><page leafNum="0"><pageNumber>7</pageNumber></page></pageData></book>'
        ocr = '<DOCUMENT><OBJECT><LINE><WORD>Invented</WORD><WORD>OCR</WORD></LINE></OBJECT></DOCUMENT>'
        metadata = Mock()
        metadata.model_dump_json.return_value = '{"identifier":"invented"}'
        metadata.find_suffix.side_effect = lambda suffix: suffix if suffix in ('_scandata.xml', '_djvu.xml') else None
        def downloaded(archive, identifier, item, destination):
            write_if_changed(destination, scan if item == '_scandata.xml' else ocr)
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_1.download.fetch_metadata', return_value=metadata), \
             patch('opensiddur.importer.marmorstein_rosh_hashanah_1.download.download_file', side_effect=downloaded):
            result = download(self.book, Mock())
            self.assertEqual(result['pages'][0]['machine_page_candidate'], '7')
            self.assertIsNone(result['pages'][0]['printed_page'])
            self.assertEqual((self.source/'ia/ocr/s1.txt').read_text(), 'Invented OCR\n')
            before = {p: p.stat().st_mtime_ns for p in self.source.rglob('*') if p.is_file()}
            download(self.book, Mock())
            self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})
        self.assertEqual(regenerate(self.book), result)

    def test_excerpt_coverage_cannot_certify_a_full_leaf(self):
        self.save('pages', {'pages': [{'scan_page': n, 'evidence': 'image'} for n in range(1, 5)]})
        self.save('page_completion', {'s1': {'status': 'complete', 'evidence': 'image', 'independent_model': 'second'}})
        result = report(self.source)
        self.assertFalse(result['complete'])
        self.assertEqual(result['leaves_fully_transcribed_and_reviewed'], 0)
        self.assertEqual(result['leaves_with_transcribed_excerpts'], 4)
