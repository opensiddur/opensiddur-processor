"""Draft excerpt invariants with invented text and source inputs."""
import hashlib
import copy
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

    def test_prayer_parts_follow_paragraphs_and_terminate_quotation_scope(self):
        unit = self.recipe['units'][0]
        unit['he'] = {'scan_page': 23, 'printed_page': '9', 'parts': [
            {'urn': unit['urn']+'/opening', 'content': ['First ']},
            {'urn': unit['urn']+'/quote', 'content': [{'quotation': {
                'chapter': '7', 'verse': '2',
                'urn': 'urn:x-opensiddur:text:bible:psalms/7/2',
                'content': ['Quotation ', {'divine_name': 'יְיָ'}]}}, ' following.']},
            {'urn': unit['urn']+'/seal', 'new_paragraph': True, 'content': ['Seal.']}]}
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers.validate',
                   return_value=(True, [])):
            self.run_builder()
        root = etree.parse(str(self.base/'projects'/PROJECTS['he']/'invented_prayer.xml'))
        paragraphs = root.xpath('//t:body//t:p', namespaces=NS)
        self.assertEqual(len(paragraphs), 2)
        self.assertEqual(''.join(paragraphs[0].itertext()), 'First Quotation יְיָ following.')
        quote = paragraphs[0].find('t:seg', NS)
        self.assertIn('/page/n22', quote.get('facs'))
        self.assertEqual(quote.getnext().get('unit'), 'verse')
        self.assertIsNone(quote.getnext().get('corresp'))
        self.assertEqual(quote.getnext().getnext().get('unit'), 'chapter')
        self.assertEqual(quote.getnext().getnext().tail, ' following.')
        self.assertEqual(paragraphs[-1][-1].get('unit'), 'prayer-part')
        self.assertIsNone(paragraphs[-1][-1].get('corresp'))

    def test_paragraph_continuation_keeps_the_existing_prayer_part_scope(self):
        unit = self.recipe['units'][0]
        unit['he'] = {'scan_page': 23, 'printed_page': '9', 'parts': [
            {'urn': unit['urn']+'/opening', 'content': ['First paragraph.']},
            {'new_paragraph': True, 'content': ['Its continuation.']}]}
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers.validate',
                   return_value=(True, [])):
            self.run_builder()
        root = etree.parse(str(self.base/'projects'/PROJECTS['he']/'invented_prayer.xml'))
        self.assertEqual(root.xpath('//t:milestone[@unit="prayer-part"]/@corresp',
                                    namespaces=NS), [unit['urn']+'/opening'])
        self.assertEqual(len(root.xpath('//t:body//t:p', namespaces=NS)), 2)

    def test_prayer_quotation_source_tracks_a_preceding_page_break(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers import prayer_document
        unit = self.recipe['units'][0]
        witness = {'scan_page': 23, 'printed_page': '9', 'parts': [
            {'urn': unit['urn']+'/a', 'content': ['Before ',
             {'page_break': {'scan_page': 25, 'printed_page': '10'}}]},
            {'urn': unit['urn']+'/b', 'content': [{'quotation': {
                'urn': 'urn:x-opensiddur:text:bible:psalms/7/2',
                'chapter': '7', 'verse': '2', 'content': ['After']}}]}]}
        root = prayer_document(unit, 'he', witness)
        self.assertIn('/page/n24', root.xpath('string(//t:seg/@facs)', namespaces=NS))
        witness['parts'][1]['content'][0]['quotation']['verse'] = '3'
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            prayer_document(unit, 'he', witness)

    def test_prayer_rejects_empty_and_duplicate_parts_before_writes(self):
        unit = self.recipe['units'][0]
        for parts in [[], [{'urn': unit['urn']+'/a', 'content': ['a']},
                           {'urn': unit['urn']+'/a', 'content': ['b']}]]:
            with self.subTest(parts=parts):
                unit['he'] = {'scan_page': 23, 'printed_page': '9', 'parts': parts}
                with self.assertRaises(ValueError):
                    self.run_builder()
                self.assertFalse((self.base/'projects'/PROJECTS['he']/'invented_prayer.xml').exists())

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

    def test_range_keeps_language_page_boundaries_inside_their_own_verses(self):
        unit = self.recipe['units'][0]
        unit['urn'] = 'urn:x-opensiddur:text:bible:psalms/7/2-/7/3'
        del unit['verse']
        del unit['verse_urn']
        for lang, scan, printed_end, contents in [
            ('he', 23, '10', [['אב־', {'page_break': {
                'scan_page': 25, 'printed_page': '10'}}, 'גד'], ['הו']]),
            ('en', 24, '11', [['An opening.'], ['Tell ', {'page_break': {
                'scan_page': 28, 'printed_page': '11'}}, 'it.']]),
        ]:
            unit[lang] = {'scan_page': scan, 'printed_page': '9',
                          'printed_page_end': printed_end, 'verses': [
                              {'verse': str(number),
                               'verse_urn': f'urn:x-opensiddur:text:bible:psalms/7/{number}',
                               'content': content}
                              for number, content in zip([2, 3], contents)]}
        alternate = self.source/'ranges.json'
        alternate.write_text(json.dumps(self.recipe), encoding='utf-8')
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers.validate',
                   return_value=(True, [])):
            main(['--draft', '--source-root', str(self.base/'sources'),
                  '--project-directory', str(self.base/'projects'), '--recipe', 'ranges.json'])
        docs = [etree.parse(str(self.base/'projects'/PROJECTS[lang]/'invented_prayer.xml'))
                for lang in ['he', 'en']]
        for doc in docs:
            self.assertEqual(doc.xpath('//t:body/t:div/@corresp', namespaces=NS), [])
            self.assertEqual(doc.xpath('//t:milestone[@unit="chapter"]/@corresp', namespaces=NS), [])
            self.assertEqual(doc.xpath('//t:milestone[@unit="verse"]/@corresp', namespaces=NS),
                             ['urn:x-opensiddur:text:bible:psalms/7/2',
                              'urn:x-opensiddur:text:bible:psalms/7/3'])
            self.assertEqual(doc.xpath('//t:note', namespaces=NS), [])
        self.assertEqual(docs[0].xpath('string(//t:body//t:p)', namespaces=NS), 'אב־גד הו')
        self.assertEqual(docs[1].xpath('string(//t:body//t:p)', namespaces=NS), 'An opening. Tell it.')
        for doc, verse, leaf, last_page in [(docs[0], '2', 'n24', '10'),
                                           (docs[1], '3', 'n27', '11')]:
            self.assertEqual(doc.xpath('string(//t:seg[t:pb]/@source)', namespaces=NS),
                             f'urn:x-opensiddur:text:bible:psalms/7/{verse}')
            self.assertIn(leaf, doc.xpath('string(//t:seg/t:pb/@facs)', namespaces=NS))
            self.assertEqual(doc.xpath('string(//t:biblScope/@to)', namespaces=NS), last_page)
        self.assertIn('n22', docs[0].xpath('string((//t:body//t:seg)[1]/@facs)', namespaces=NS))
        self.assertIn('n24', docs[0].xpath('string((//t:body//t:seg)[2]/@facs)', namespaces=NS))
        self.assertIn('n23', docs[1].xpath('string((//t:body//t:seg)[2]/@facs)', namespaces=NS))

    def test_range_citation_targets_its_first_printed_verse(self):
        unit = self.recipe['units'][0]
        first = unit.pop('verse_urn')
        unit.pop('verse')
        unit['he'].pop('content')
        unit['he']['verses'] = [
            {'verse': '2', 'verse_urn': first, 'content': ['אב']},
            {'verse': '3', 'verse_urn': first[:-1]+'3', 'content': ['גד']}]
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers.validate',
                   return_value=(True, [])):
            self.run_builder()
        doc = etree.parse(str(self.base/'projects'/PROJECTS['he']/'invented_prayer.xml'))
        self.assertEqual(doc.xpath('//t:note/@target', namespaces=NS), [first])
        self.assertEqual(doc.xpath('//t:note//t:ref/@target', namespaces=NS), [first])
        self.assertEqual(doc.xpath('string(//t:note//t:ref)', namespaces=NS), 'תהלים ז:ב')
        self.assertEqual(doc.xpath('string(//t:body//t:p)', namespaces=NS), 'אב גד')

    def test_verse_beginning_after_page_break_retains_new_source(self):
        unit = self.recipe['units'][0]
        unit['he']['verses'] = [{
            'verse': '2', 'verse_urn': unit['verse_urn'],
            'content': [' ', {'page_break': {'scan_page': 25, 'printed_page': '10'}},
                        '', {'page_break': {'scan_page': 27, 'printed_page': '11'}}, 'אב']}]
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers.validate',
                   return_value=(True, [])):
            self.run_builder()
        doc = etree.parse(str(self.base/'projects'/PROJECTS['he']/'invented_prayer.xml'))
        self.assertIn('n26', doc.xpath('string(//t:body//t:seg/@facs)', namespaces=NS))
        self.assertEqual(len(doc.xpath('//t:body//t:seg/t:pb', namespaces=NS)), 2)

    def test_invalid_ranges_cannot_remove_or_replace_any_witness(self):
        original = copy.deepcopy(self.recipe)
        for failure in ['empty', 'duplicate', 'bad_page']:
            with self.subTest(failure=failure):
                self.recipe = copy.deepcopy(original)
                unit = self.recipe['units'][0]
                verse = {'verse': '2', 'verse_urn': unit['verse_urn'], 'content': ['אב']}
                unit['he']['verses'] = [verse]
                if failure == 'empty':
                    unit['he']['verses'] = []
                elif failure == 'duplicate':
                    unit['he']['verses'].append(copy.deepcopy(verse))
                else:
                    verse['content'].append({'page_break': {
                        'scan_page': 0, 'printed_page': '10'}})
                stale = self.base/'projects'/PROJECTS['en']/'invented_prayer.xml'
                stale.write_text('Retain existing witness', encoding='utf-8')
                with self.assertRaises(ValueError):
                    self.run_builder()
                self.assertEqual(stale.read_text(encoding='utf-8'), 'Retain existing witness')
                self.assertFalse((self.base/'projects'/PROJECTS['he']/'invented_prayer.xml').exists())

    def test_partial_range_translation_does_not_invent_a_missing_verse(self):
        unit = self.recipe['units'][0]
        verses = [{'verse': str(n), 'verse_urn': f'urn:x-opensiddur:text:bible:psalms/7/{n}',
                   'content': [f'Invented verse {n}.']} for n in [2, 3]]
        unit['he']['verses'] = verses
        unit['en'] = {'scan_page': 24, 'printed_page': '9', 'verses': [verses[1]]}
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers.validate',
                   return_value=(True, [])):
            self.run_builder()
        english = etree.parse(str(self.base/'projects'/PROJECTS['en']/'invented_prayer.xml'))
        self.assertEqual(english.xpath('//t:milestone[@unit="verse"]/@corresp', namespaces=NS),
                         ['urn:x-opensiddur:text:bible:psalms/7/3'])
        self.assertEqual(english.xpath('string(//t:body//t:seg)', namespaces=NS), 'Invented verse 3.')

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
