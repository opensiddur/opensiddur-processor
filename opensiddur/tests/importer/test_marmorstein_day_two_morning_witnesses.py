"""Synthetic tests for independent source ranges in a new physical volume."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_2 import IDENTIFIER, PROJECTS
from opensiddur.importer.marmorstein_rosh_hashanah_2.morning_witnesses import (
    main,
    retain_range_provenance,
    witness_document,
)
from opensiddur.importer.scan.authoring import TEI

T = '{'+TEI+'}'
NS = {'t': TEI}


class MorningWitnessTests(unittest.TestCase):
    def unit(self):
        base = 'urn:x-opensiddur:text:bible:psalms/33'
        return {'stem': 'example', 'urn': base, 'title': {'en': 'Example'},
                'languages': {'en': [
                    {'paragraph': 1, 'corresp': base+'/1', 'fragments': [
                        {'scan': 's8', 'printed_page': '1', 'text': 'First verse.',
                         'page_start': False}]},
                    {'paragraph': 1, 'corresp': base+'/2', 'fragments': [
                        {'scan': 's9', 'printed_page': '1', 'text': 'Second verse.',
                         'page_start': True}]}]}}

    def test_each_verse_carries_its_actual_scan_despite_repeated_labels(self):
        unit = self.unit()
        before = copy.deepcopy(unit)
        root = witness_document(unit, 'en')
        self.assertEqual(unit, before)
        for number, leaf in [(1, 7), (2, 8)]:
            marker = root.find('.//'+T+'milestone[@corresp="'+unit['urn']+'/'+str(number)+'"]')
            page = marker.getnext()
            self.assertEqual(page.tag, T+'pb')
            self.assertEqual(page.get('n'), '1')
            self.assertEqual(page.get('facs'),
                             f'https://archive.org/download/{IDENTIFIER}/page/n{leaf}.jpg')
        self.assertTrue(root.find('.//'+T+'idno').text.endswith('@'+PROJECTS['en']))
        self.assertEqual(root.find('.//'+T+'sourceDesc/'+T+'bibl/'+T+'ptr').get('target'),
                         '/'+PROJECTS['en']+'/index#day_two_source_bibl')
        self.assertEqual(' '.join(''.join(root.find(T+'text').itertext()).split()),
                         'First verse. Second verse.')
        self.assertEqual(root.find('.//'+T+'biblScope').attrib,
                         {'unit': 'pages', 'from': '1', 'to': '1'})

    def test_provenance_keeps_the_marker_tail_and_is_idempotent(self):
        root = etree.fromstring(f'<p xmlns="{TEI}"><milestone unit="verse" '
                               'corresp="example"/>Words <hi>inside</hi> after.</p>')
        before = ''.join(root.itertext())
        pages = {'example': {'scan': 's8', 'printed_page': '1'}}
        retain_range_provenance(root, pages)
        self.assertEqual(''.join(root.itertext()), before)
        self.assertIsNone(root[0].tail)
        self.assertEqual(root[1].tail, 'Words ')
        once = etree.tostring(root)
        retain_range_provenance(root, pages)
        self.assertEqual(etree.tostring(root), once)

    def test_literal_source_cannot_silently_reuse_other_printed_words(self):
        for control in ('reuse', 'canonical', 'transclude', 'repeat'):
            with self.subTest(control=control):
                unit = self.unit()
                if control == 'reuse':
                    unit['reuse'] = {'en': unit['urn']}
                else:
                    unit['languages']['en'][0][control] = unit['urn']
                with self.assertRaisesRegex(ValueError, 'own source words'):
                    witness_document(unit, 'en')

    def test_nested_quotation_and_option_ranges_keep_the_fragment_page(self):
        for in_option in (False, True):
            with self.subTest(in_option=in_option):
                unit = self.unit()
                unit['urn'] = 'urn:x-opensiddur:text:prayer:example'
                fragment = unit['languages']['en'][1]['fragments'][0]
                fragment['text'] = 'Second quotation.'
                verse = unit['urn']+'/quote/psalms/33/1'
                quote = {'text': 'quotation',
                         'source_reference': 'urn:x-opensiddur:text:bible:psalms/33/1',
                         'chapter_corresp': unit['urn']+'/quote/psalms/33',
                         'source_reference_corresp': verse}
                if in_option:
                    fragment['alternatives'] = [{
                        'printed': 'quotation', 'readings': [
                            {'text': 'quotation', 'quotations': [quote]}, 'variant']}]
                else:
                    fragment['quotations'] = [quote]
                root = witness_document(unit, 'en')
                marker = root.find('.//'+T+'milestone[@corresp="'+verse+'"]')
                self.assertEqual(marker.getnext().get('facs'),
                                 f'https://archive.org/download/{IDENTIFIER}/page/n8.jpg')

    def test_context_quote_does_not_steal_a_later_canonical_verse_source(self):
        unit = self.unit()
        unit['urn'] = 'urn:x-opensiddur:text:prayer:example'
        verse = 'urn:x-opensiddur:text:bible:psalms/33/1'
        first = unit['languages']['en'][0]
        first.update(corresp=unit['urn']+'/lead', source=verse,
                     source_reference=verse,
                     chapter_corresp=unit['urn']+'/lead/quote/psalms/33',
                     source_reference_corresp=unit['urn']+'/lead/quote/psalms/33/1')
        unit['languages']['en'][1]['corresp'] = verse
        root = witness_document(unit, 'en')
        marker = root.find('.//'+T+'milestone[@corresp="'+verse+'"]')
        self.assertEqual(marker.getnext().get('facs'),
                         f'https://archive.org/download/{IDENTIFIER}/page/n8.jpg')

    def test_nested_half_verse_does_not_bind_an_unmapped_parent_verse(self):
        unit = self.unit()
        unit['urn'] = 'urn:x-opensiddur:text:prayer:example'
        verse = 'urn:x-opensiddur:text:bible:psalms/33/1'
        first = unit['languages']['en'][0]
        first['corresp'] = unit['urn']+'/lead'
        first['fragments'][0]['quotations'] = [{
            'text': 'First', 'source_reference': verse,
            'source_reference_part': {'unit': 'half-verse', 'n': 'a',
                                      'corresp': verse+'/a'}}]
        unit['languages']['en'][1]['corresp'] = verse
        root = witness_document(unit, 'en')
        whole = root.find('.//'+T+'milestone[@corresp="'+verse+'"]')
        half = root.find('.//'+T+'milestone[@corresp="'+verse+'/a"]')
        self.assertTrue(half.getnext().get('facs').endswith('/page/n7.jpg'))
        self.assertTrue(whole.getnext().get('facs').endswith('/page/n8.jpg'))

    def test_recipe_must_hash_readings_and_the_approval_record(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_2 import BOOK
        for missing in ('readings.json', 'approval.json'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp)/BOOK
                source.mkdir()
                (source/'readings.json').write_text('{}')
                (source/'approval.json').write_text(json.dumps({
                    'status': 'approved_source_only', 'working_readings_sha256': None}))
                recipe = {
                    'readings': 'readings.json', 'source_approval': 'approval.json',
                    'input_sha256': {name: hashlib.sha256((source/name).read_bytes()).hexdigest()
                                     for name in ('readings.json', 'approval.json') if name != missing},
                    'units': [], 'protected_files': []}
                (source/'recipe.json').write_text(json.dumps(recipe))
                with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.'
                           'morning_witnesses.write_documents') as write:
                    with self.assertRaisesRegex(ValueError, 'bind both'):
                        main(['--draft', '--source-root', tmp, '--recipe', 'recipe.json',
                              '--project-directory', str(Path(tmp)/'projects')])
                    write.assert_not_called()
