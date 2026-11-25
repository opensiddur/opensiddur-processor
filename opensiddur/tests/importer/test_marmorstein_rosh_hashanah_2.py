"""Startup orchestration uses synthetic front matter and isolated project roots."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_2 import BOOK, PROJECTS
from opensiddur.importer.marmorstein_rosh_hashanah_2.build import main


class OpeningBuildTests(unittest.TestCase):
    def test_draft_build_preserves_existing_edition_files_and_separates_languages(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base/'sources'/BOOK
            source.mkdir(parents=True)
            reading = {'pages': [
                {'scan_page': 2, 'language': 'he', 'kind': 'title',
                 'lines': ['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז']},
                {'scan_page': 3, 'language': 'en', 'kind': 'title',
                 'lines': ['Synthetic title', 'Subtitle', 'Author', 'Press', 'Place']},
            ]}
            (source/'primary_opening_s1_s4.json').write_text(
                json.dumps(reading), encoding='utf-8')
            for project in PROJECTS.values():
                root = base/'projects'/project
                root.mkdir(parents=True)
                (root/'index.xml').write_text('existing index', encoding='utf-8')
                (root/'shared_prayer.xml').write_text('existing witness', encoding='utf-8')
            with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.build.validate',
                       return_value=(True, [])) as validator:
                self.assertEqual(main(['--draft', '--source-root', str(base/'sources'),
                                       '--project-directory', str(base/'projects')]), 0)
            self.assertEqual(validator.call_count, 2)
            for lang, project in PROJECTS.items():
                root = base/'projects'/project
                self.assertEqual((root/'index.xml').read_text(encoding='utf-8'), 'existing index')
                self.assertEqual((root/'shared_prayer.xml').read_text(encoding='utf-8'), 'existing witness')
                document = etree.parse(str(root/'day_two.xml'))
                ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
                self.assertEqual(document.xpath('string(/tei:TEI/@xml:lang)', namespaces=ns), lang)
                markers = document.xpath('//tei:pb/@facs', namespaces=ns)
                self.assertEqual(len(markers), 1)
                self.assertIn('/page/n1_' if lang == 'he' else '/page/n2_', markers[0])
                edition = document.xpath('string(//tei:edition)', namespaces=ns)
                self.assertIn('DRAFT', edition)
