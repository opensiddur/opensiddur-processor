"""Edition wiring contracts with invented words, temporary sources and mocked I/O."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from lxml import etree
import yaml

from opensiddur.importer.marmorstein_rosh_hashanah_1 import profile, PROJECTS, EXPANDED
from opensiddur.importer.marmorstein_rosh_hashanah_1.build import build, unit_text, unit_review_text, words
from opensiddur.importer.marmorstein_rosh_hashanah_1.download import download, regenerate
from opensiddur.importer.marmorstein_rosh_hashanah_1.verify import report
from opensiddur.importer.scan.review import review, reading_hash
from opensiddur.importer.scan.authoring import printed_text
from opensiddur.importer.util.internet_archive import write_if_changed
from opensiddur.exporter.refdb import find_end_of_mapping
from opensiddur.exporter.condition_eval import TriState, evaluate_condition, parse_condition_element

T = '{http://www.tei-c.org/ns/1.0}'
J = '{http://jewishliturgy.org/ns/jlptei/2}'
BASE = 'urn:x-opensiddur:text:prayer:'


class EditionWiringTest(unittest.TestCase):
    def test_full_and_abbreviated_names_preserve_points_and_separate_prefixes(self):
        parent = etree.Element(T+'p')
        text = 'וְיְהוָה לַייָ יְהוָה'
        words(parent, text, 'he')
        self.assertEqual(''.join(parent.itertext()), text)
        self.assertEqual([e.text for e in parent.findall(J+'divineName')], ['יְהוָה', 'ייָ', 'יְהוָה'])
        self.assertEqual(parent.text, 'וְ')

    def test_maqaf_and_sof_pasuq_bound_names_without_consuming_punctuation(self):
        parent = etree.Element(T+'p')
        text = 'טוֹב־יְיָ לַייָ־לַייָ׃ חַיֵּינוּ'
        words(parent, text, 'he')
        self.assertEqual(''.join(parent.itertext()), text)
        self.assertEqual([e.text for e in parent.findall(J+'divineName')], ['יְיָ', 'ייָ', 'ייָ'])

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
        self.registry_mock = registry
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
        settings = yaml.safe_load((self.projects.parent/'settings'/EXPANDED/'undated.yaml').read_text())
        self.assertEqual(settings['annotations'], list(PROJECTS.values()))
        self.assertIn('Stand.', ''.join(expanded.getroot().itertext()))
        original = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        reference = original.find('.//'+T+'ref[@type="page"]')
        self.assertEqual(reference.get('target'), BASE+'invented@'+PROJECTS['he'])

    def test_expanded_bilingual_directive_is_one_note_with_two_languages(self):
        self.readings['documentary_instructions'] = {
            'he': {'text': 'עמוד', 'language': 'he', 'scan': 's1', 'printed_page': '7'},
            'en': {'text': 'Stand.', 'language': 'en', 'scan': 's3', 'printed_page': '7'}}
        self.readings['expanded_order'] = [
            {'instruction': ['he', 'en']}, {'unit': 'first'}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/EXPANDED/'index.xml'))
        notes = root.findall('.//'+T+'body//'+T+'note[@type="instruction"]')
        self.assertEqual(len(notes), 1)
        self.assertEqual([part.get('{http://www.w3.org/XML/1998/namespace}lang')
                          for part in notes[0]], ['he', 'en'])
        self.assertEqual([''.join(part.itertext()) for part in notes[0]], ['עמוד', 'Stand.'])
        self.assertEqual(notes[0].getnext().get('target'), BASE+'invented')

    def test_mid_page_direction_keeps_its_link_without_an_extra_page_break(self):
        self.readings['navigation']['return']['page_start'] = False
        self.save('readings', self.readings)
        self.generate(draft=True)
        index = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        self.assertFalse(index.findall('.//'+T+'body//'+T+'pb'))
        link = index.find('.//'+T+'ref[@type="page"]')
        self.assertEqual(link.get('target'), BASE+'invented@'+PROJECTS['he'])
        self.assertEqual(link.getparent().get('type'), 'optional-page-reference')

    def test_unreviewed_or_stale_text_cannot_replace_a_reviewed_build(self):
        with self.assertRaisesRegex(ValueError, 'review pending'):
            self.generate()
        speaker = {'abbr': 'קו״ח', 'expan': 'קהל וחזן'}
        self.readings['units'][0]['languages']['he'][0]['speaker'] = speaker
        self.save('readings', self.readings)
        reviews = {}
        def accepted(text):
            entry = review(text, text, primary_model='first-reader', independent_model='second-reader', evidence='scan')
            entry['final_sha256'] = reading_hash(text)
            return entry
        for unit in self.readings['units']:
            for lang in unit['languages']:
                reviews[unit['stem']+'/'+lang] = accepted(unit_review_text(unit, lang))
        for lang in ('he', 'en'):
            reviews['navigation/return/'+lang] = accepted('Read page 7.')
        self.save('reviews', reviews)
        self.generate()
        path = self.projects/PROJECTS['he']/'first.xml'
        before = path.read_bytes()
        note = etree.parse(str(path)).find('.//'+T+'note[@type="description"]')
        self.assertEqual(note.get('corresp'), 'urn:x-opensiddur:instruction:role/reader_and_congregation')
        self.readings['units'][0]['languages']['he'][0]['fragments'][0]['text'] = 'changed'
        self.save('readings', self.readings)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.generate()
        self.assertEqual(path.read_bytes(), before)
        self.readings['units'][0]['languages']['he'][0]['fragments'][0]['text'] = 'אב יי'
        for field, changed in [('abbr', 'קו׳'), ('expan', 'קהל')]:
            with self.subTest(field=field):
                original = speaker[field]
                speaker[field] = changed
                self.save('readings', self.readings)
                with self.assertRaisesRegex(ValueError, 'stale'):
                    self.generate()
                self.assertEqual(path.read_bytes(), before)
                speaker[field] = original

    def test_unknown_speaker_expansion_fails_even_in_draft(self):
        self.readings['units'][0]['languages']['he'][0]['speaker'] = {
            'abbr': 'x', 'expan': 'unknown'}
        self.save('readings', self.readings)
        with self.assertRaisesRegex(ValueError, 'Unknown speaker expansion: unknown'):
            self.generate(draft=True)

    def test_a_literal_speaker_label_keeps_its_language_and_reviewed_role(self):
        unit = self.readings['units'][0]
        speaker = {'label': 'פֿאָרבעטער:', 'language': 'yi', 'role': 'reader'}
        unit['languages']['he'][0]['speaker'] = speaker
        original = unit_review_text(unit, 'he')
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        note = root.find('.//'+T+'note[@type="description"]')
        self.assertEqual(note.get('{http://www.w3.org/XML/1998/namespace}lang'), 'yi')
        self.assertEqual(note.text, speaker['label'])
        self.assertTrue(note.get('corresp').endswith('/reader'))
        self.assertIsNone(note.find(T+'choice'))
        speaker['role'] = 'congregation'
        self.assertNotEqual(unit_review_text(unit, 'he'), original)

    def test_quoted_scripture_keeps_both_scopes_across_a_page_boundary(self):
        verse = 'urn:x-opensiddur:text:bible:exodus/15/11'
        unit = self.readings['units'][0]
        unit['languages']['he'] = [{
            'corresp': BASE+'invented/1', 'source': verse, 'source_reference': verse,
            'fragments': [{'scan': 's1', 'text': 'אב־'}, {'scan': 's2', 'text': 'גד'}]},
            {'corresp': BASE+'invented/2', 'fragments': [{'scan': 's2', 'text': 'הו'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        ns = {'t': T[1:-1], 'tei': T[1:-1]}
        self.assertEqual(len(root.xpath('//t:milestone[@corresp=$urn]', namespaces=ns, urn=verse)), 1)
        self.assertEqual(root.xpath('//t:milestone[@unit="chapter"]/@n', namespaces=ns), ['15'])
        first = root.find('.//'+T+'milestone[@corresp="'+BASE+'invented/1"]')
        end, _ = find_end_of_mapping(first)
        last = root.xpath(end, namespaces=ns)[0]
        node, scope = first, ''
        while True:
            scope += printed_text(node)+(node.tail or '')
            if node is last:
                break
            node = node.getnext()
        self.assertEqual(scope.strip(), 'אב־גד')
        self.assertEqual(last.getnext().get('corresp'), BASE+'invented/2')
        scripture = root.find('.//'+T+'milestone[@corresp="'+verse+'"]')
        self.assertEqual(scripture.getnext().tag, T+'seg')
        self.assertIsNone(scripture.getparent().get('source'))
        self.assertEqual(printed_text(root.find('.//'+T+'body')).strip(), 'אב־גד הו')

    def test_reprinted_verses_keep_context_without_redefining_scripture(self):
        unit = self.readings['units'][0]
        unit['languages']['he'] = [
            {'corresp': BASE+'invented/'+str(i), 'reference_unit': 'verse',
             'source': 'urn:x-opensiddur:text:bible:psalms/92/'+str(i),
             'fragments': [{'scan': 's1', 'text': word}]}
            for i, word in [(1, 'אב'), (2, 'גד')]] + [
            {'corresp': BASE+'invented/3', 'fragments': [{'scan': 's2', 'text': 'הו'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        ns = {'t': T[1:-1]}
        self.assertEqual(root.xpath('//t:milestone[@unit="chapter"]/@n', namespaces=ns), ['92'])
        self.assertFalse(root.xpath('//t:milestone[starts-with(@corresp,"urn:x-opensiddur:text:bible:")]', namespaces=ns))
        self.assertEqual(root.xpath('//t:milestone[@unit="verse"]/@n', namespaces=ns), ['1', '2'])
        marker = root.find('.//'+T+'milestone[@corresp="'+BASE+'invented/3"]')
        self.assertEqual(marker.getprevious().get('unit'), 'chapter')
        self.assertIsNone(marker.getprevious().get('corresp'))
        self.assertEqual(root.xpath('//t:seg/@source', namespaces=ns), [
            'urn:x-opensiddur:text:bible:psalms/92/1', 'urn:x-opensiddur:text:bible:psalms/92/2'])

    def test_citation_on_a_later_leaf_targets_its_passage(self):
        unit = self.readings['units'][0]
        unit['citations'] = {'he': [{'scan': 's2', 'text': '(Example 2.)',
                                    'target': BASE+'invented',
                                    'reference': 'urn:x-opensiddur:text:bible:psalms/115/18'}]}
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        note = root.find('.//'+T+'standOff/'+T+'note')
        self.assertEqual(note.get('target'), BASE+'invented')
        self.assertEqual(note.find('.//'+T+'ref').text, 'Example 2.')
        unit['citations']['he'][0]['scan'] = 's4'
        self.save('readings', self.readings)
        with self.assertRaisesRegex(ValueError, 'Citation scan is outside the passage'):
            self.generate(draft=True)

    def test_passage_speaker_stays_outside_both_adjacent_reusable_parts(self):
        unit = self.readings['units'][0]
        unit['languages']['he'] = [
            {'corresp': BASE+'invented/1', 'fragments': [{'scan': 's1', 'text': 'אב'}]},
            {'corresp': BASE+'invented/2', 'fragments': [{'scan': 's1', 'text': 'גד'}],
             'speaker': {'label': 'חזן', 'role': 'reader'}, 'speaker_before_reference': True}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        p = root.find('.//'+T+'body//'+T+'p')
        note = p.find(T+'note')
        before, after = note.getprevious(), note.getnext()
        self.assertEqual(before.tag, T+'milestone')
        self.assertIsNone(before.get('corresp'))
        self.assertEqual(after.get('corresp'), BASE+'invented/2')
        self.assertEqual(after.tail.strip(), 'גד')

    def test_partial_chapter_uses_a_range_in_the_documentary_spine(self):
        chapter = 'urn:x-opensiddur:text:bible:deuteronomy/6'
        unit = self.readings['units'][0]
        unit.update(urn=chapter, map_root=False, start=chapter+'/5', end=chapter+'/6')
        self.registry_mock.records[chapter.rsplit('/', 1)[0]] = {}
        unit['languages'] = {'he': [
            {'corresp': chapter+'/5', 'fragments': [{'scan': 's1', 'text': 'אב'}]},
            {'corresp': chapter+'/6', 'fragments': [{'scan': 's2', 'text': 'גד'}]}]}
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        self.assertFalse(root.findall('.//'+T+'milestone[@unit="chapter"][@corresp]'))
        self.assertEqual(root.find('.//'+T+'publicationStmt/'+T+'idno').text,
                         chapter+'/5-/6/6@'+PROJECTS['he'])
        index = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        inclusion = index.find('.//'+J+'transclude')
        self.assertEqual(inclusion.get('target'), chapter+'/5-/6/6@'+PROJECTS['he'])
        self.assertIsNone(inclusion.get('targetEnd'))

    def test_enlarged_source_letters_retain_points_and_divine_names(self):
        unit = self.readings['units'][0]
        text = 'שְׁמַ֖ע יִשְׂרָאֵ֑ל יְהוָ֥ה אֶחָֽד:'
        unit['languages']['he'] = [{'fragments': [
            {'scan': 's1', 'text': text, 'enlarged_letters': ['ע', 'ד']}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        self.assertEqual([e.text for e in root.findall('.//'+T+'c')], ['ע', 'ד'])
        self.assertEqual(printed_text(root.find('.//'+T+'body')).strip(), text)
        self.assertEqual(root.find('.//'+J+'divineName').text, 'יְהוָ֥ה')

    def test_source_rubrics_belong_to_their_condition_or_language_witness(self):
        unit = self.readings['units'][0]
        unit['conditions'] = [{'type': 'opensiddur:quorum', 'features': {'minyan': False}}]
        unit['instructions'] = [
            {'text': 'יחיד אומר', 'language': 'he', 'type': 'instruction',
             'placement': 'condition', 'witnesses': ['he']},
            {'text': 'בלחש', 'language': 'he', 'type': 'description', 'witnesses': ['he']}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        he = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        condition = he.find('.//'+J+'conditional')
        self.assertEqual(condition[0].tag, T+'note')
        self.assertEqual(condition[0].text, 'יחיד אומר')
        self.assertEqual(he.find('.//'+T+'body/'+T+'div/'+T+'note').text, 'בלחש')
        en = etree.parse(str(self.projects/PROJECTS['en']/'first.xml'))
        self.assertFalse(en.findall('.//'+T+'body//'+T+'note'))
        self.assertNotIn('בלחש', unit_review_text(unit, 'en'))

    def test_language_specific_headings_keep_their_own_scan_boundary(self):
        self.readings['documentary_instructions'] = {
            'he_head': {'scan': 's1', 'printed_page': '12', 'language': 'he',
                        'witnesses': ['he'], 'text': 'מעריב'},
            'en_head': {'scan': 's2', 'printed_page': '12', 'language': 'en',
                        'witnesses': ['en'], 'text': 'Evening prayer'}}
        self.readings['source_order'] = [{'section': 'evening',
            'heading': {'he': 'he_head', 'en': 'en_head'}, 'order': [{'unit': 'first'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        for lang, scan, heading in [('he', 'n0', 'מעריב'), ('en', 'n1', 'Evening prayer')]:
            root = etree.parse(str(self.projects/PROJECTS[lang]/'index.xml'))
            self.assertEqual(root.find('.//'+T+'body//'+T+'head').text, heading)
            self.assertTrue(root.find('.//'+T+'body//'+T+'pb').get('facs').endswith('/'+scan+'.jpg'))

    def test_unnumbered_appendix_heading_starts_its_scan_before_the_heading(self):
        self.readings['documentary_instructions'] = {'appendix': {
            'scan': 's4', 'language': 'he', 'witnesses': ['he'], 'text': 'שיר של יום.'}}
        self.readings['source_order'] = [{'section': 'appendix', 'heading': 'appendix',
            'witnesses': ['he'], 'order': [{'unit': 'second'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        heading = root.find('.//'+T+'body//'+T+'head')
        boundary = heading.getprevious()
        self.assertEqual(boundary.tag, T+'pb')
        self.assertTrue(boundary.get('facs').endswith('/n3.jpg'))
        self.assertIsNone(boundary.get('n'))

    def test_expanded_coverage_note_is_encoding_metadata(self):
        self.readings['expanded_coverage_note'] = 'Daily psalm placement remains unassembled.'
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/EXPANDED/'index.xml'))
        notes = root.findall('.//'+T+'sourceDesc/'+T+'bibl/'+T+'note')
        note = next(n for n in notes if n.text == self.readings['expanded_coverage_note'])
        self.assertEqual(note.get('type'), 'encoding')

    def test_documentary_condition_does_not_gate_the_reusable_verse(self):
        self.readings['documentary_instructions'] = {'sabbath': {
            'text': '(On Sabbath)', 'language': 'en', 'witnesses': ['he'],
            'scan': 's1', 'printed_page': '7'}}
        self.readings['source_order'] = [{'section': 'sabbath', 'heading': None,
            'corresp': BASE+'another',
            'conditions': [{'type': 'opensiddur:holiday-aggregate', 'features': {'shabbat': True}}],
            'condition_instruction': {'he': 'sabbath'}, 'order': [{'unit': 'first'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        index = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        condition = index.find('.//'+J+'conditional')
        self.assertEqual(condition[0].text, '(On Sabbath)')
        self.assertIsNotNone(index.find('.//'+J+'endConditional'))
        verse = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        self.assertFalse(verse.findall('.//'+J+'conditional'))

    def test_inline_sabbath_insertions_end_before_the_following_words(self):
        unit = self.readings['units'][0]
        unit['languages']['he'] = [
            {'fragments': [{'scan': 's1', 'text': 'Before'}]},
            {'conditions': [{'type': 'opensiddur:holiday-aggregate', 'features': {'shabbat': True}}],
             'condition_instruction': 'On Sabbath:',
             'condition_instruction_language': 'en',
             'fragments': [{'scan': 's1', 'text': 'Sabbath'}, {'scan': 's2', 'text': 'continuation'}]},
            {'fragments': [{'scan': 's2', 'text': 'After'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        paragraphs = root.findall('.//'+T+'body//'+T+'p')
        self.assertEqual(len(paragraphs), 1)
        paragraph = paragraphs[0]
        condition = paragraph.find(J+'conditional')
        end = paragraph.find(J+'endConditional')
        self.assertEqual(end.get('target'), '#'+condition.get('{http://www.w3.org/XML/1998/namespace}id'))
        self.assertEqual(condition.find(T+'note').text, 'On Sabbath:')
        self.assertEqual(condition.find(T+'note').get('{http://www.w3.org/XML/1998/namespace}lang'), 'en')
        self.assertIn('Before', paragraph[0].tail)
        self.assertIn('Sabbath', condition.tail)
        self.assertIn('continuation', paragraph[paragraph.index(end)-1].tail)
        self.assertIn('After', end.tail)
        original = unit_review_text(unit, 'he')
        unit['languages']['he'][1]['condition_instruction'] = 'A different instruction'
        self.assertNotEqual(unit_review_text(unit, 'he'), original)

    def test_marked_inline_condition_keeps_source_brackets_out_of_prayer_words(self):
        unit = self.readings['units'][0]
        unit['languages']['he'] = [
            {'fragments': [{'scan': 's1', 'text': 'Before'}]},
            {'marked': True,
             'conditions': [{'type': 'opensiddur:holiday-aggregate', 'features': {'shabbat': True}}],
             'fragments': [{'scan': 's1', 'text': '(and)', 'join_next': True}]},
            {'fragments': [{'scan': 's1', 'text': 'after'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        self.assertEqual(root.find('.//'+J+'conditional').get('type'), 'marked')
        self.assertEqual(printed_text(root.find('.//'+T+'body')).strip(), 'Before andafter')
        self.assertEqual(json.loads((self.source/'readings.json').read_text())['units'][0]['languages']['he'][1]['fragments'][0]['text'], '(and)')
        unit['languages']['he'][1].pop('conditions')
        self.save('readings', self.readings)
        with self.assertRaisesRegex(ValueError, 'Marked source condition'):
            self.generate(draft=True)

    def test_recipient_instruction_is_not_part_of_the_reusable_words(self):
        unit = self.readings['units'][0]
        unit['languages']['he'] = [{'corresp': BASE+'invented/1',
            'instructions': [{'text': 'To a recipient', 'language': 'en'}],
            'fragments': [{'scan': 's1', 'text': 'Words'}]}]
        before = unit_review_text(unit, 'he')
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        note = root.find('.//'+T+'body//'+T+'note')
        self.assertEqual(note.get('type'), 'instruction')
        self.assertIsNone(note.get('rend'))
        self.assertEqual(note.getnext().get('corresp'), BASE+'invented/1')
        unit['languages']['he'][0]['instructions'][0]['text'] = 'Another recipient'
        self.assertNotEqual(before, unit_review_text(unit, 'he'))

    def test_abbreviation_interpretations_in_prayer_words_are_hash_bound(self):
        unit = self.readings['units'][0]
        fragment = {'scan': 's1', 'text': 'A. words',
                    'abbreviations': [{'abbr': 'A.', 'expan': 'Expanded'}]}
        unit['languages']['he'] = [{'fragments': [fragment]}]
        original = unit_review_text(unit, 'he')
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        self.assertEqual(root.find('.//'+T+'body//'+T+'choice/'+T+'expan').text, 'Expanded')
        fragment['abbreviations'][0]['expan'] = 'Changed'
        self.assertNotEqual(original, unit_review_text(unit, 'he'))
        fragment.clear()
        fragment.update(scan='s1', text='A.', expansion='Expanded')
        original = unit_review_text(unit, 'he')
        fragment['expansion'] = 'Changed'
        self.assertNotEqual(original, unit_review_text(unit, 'he'))

    def test_midverse_performance_direction_retains_its_source_anchor(self):
        unit = self.readings['units'][0]
        fragments = [{'scan': 's1', 'text': 'First words',
                      'instructions': [{'text': 'Quietly', 'language': 'en'}]},
                     {'scan': 's1', 'text': 'Last words',
                      'instructions': [{'text': 'Aloud', 'language': 'en'}]}]
        unit['languages']['he'] = [{'corresp': 'urn:x-opensiddur:text:bible:genesis/1/31/b',
            'source': 'urn:x-opensiddur:text:bible:genesis/1/31/b', 'fragments': fragments}]
        before = unit_review_text(unit, 'he')
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        p = root.find('.//'+T+'body//'+T+'p')
        notes = p.findall(T+'note')
        self.assertEqual([n.text for n in notes], ['Quietly', 'Aloud'])
        self.assertTrue(all(n.get('type') == 'description' and n.get('rend') is None for n in notes))
        self.assertEqual([n.getnext().text for n in notes], [None, 'Last words'])
        self.assertEqual(len(p.findall(T+'milestone[@corresp]')), 1)
        fragments[1]['instructions'][0]['text'] = 'In another manner'
        self.assertNotEqual(before, unit_review_text(unit, 'he'))

    def test_shared_speaker_abbreviations_preserve_both_source_word_orders(self):
        unit = self.readings['units'][0]
        unit['languages']['he'] = [{'speaker': {'abbr': 'חו״ק', 'expan': 'חזן וקהל'},
            'fragments': [{'scan': 's1', 'text': 'Words'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        n = root.find('.//'+T+'body//'+T+'note')
        self.assertEqual(n.get('corresp'), 'urn:x-opensiddur:instruction:role/reader_and_congregation')
        self.assertEqual(n.find(T+'choice/'+T+'expan').text, 'חזן וקהל')

    def test_edition_numbering_is_outside_both_adjacent_reference_scopes(self):
        unit = self.readings['units'][0]
        unit['languages']['he'] = [
            {'corresp': BASE+'invented/1', 'reference_unit': 'mishnah',
             'fragments': [{'scan': 's1', 'text': 'First'}]},
            {'corresp': BASE+'invented/2', 'reference_unit': 'mishnah', 'edition_label': 'ב',
             'fragments': [{'scan': 's1', 'text': 'Second'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        label = root.find('.//'+T+'body//'+T+'label')
        self.assertEqual(label.text, 'ב')
        self.assertEqual(label.getprevious().get('unit'), 'mishnah')
        self.assertIsNone(label.getprevious().get('corresp'))
        self.assertEqual(label.getnext().get('corresp'), BASE+'invented/2')
        self.assertEqual(len(root.findall('.//'+T+'body//'+T+'p')), 1)

    def test_referenced_numbering_travels_with_its_own_mishnah(self):
        unit = self.readings['units'][0]
        unit['languages']['he'] = [
            {'corresp': BASE+'invented/'+str(i), 'reference_unit': 'mishnah',
             'edition_label': label, 'edition_label_in_reference': True,
             'fragments': [{'scan': 's1', 'text': word}]}
            for i, label, word in [(1, 'א', 'First'), (2, 'ב', 'Second')]]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        for i, label in enumerate(root.findall('.//'+T+'body//'+T+'label'), 1):
            self.assertEqual(label.getprevious().get('corresp'), BASE+'invented/'+str(i))
        self.assertEqual(len(root.findall('.//'+T+'body//'+T+'p')), 1)

    def test_missing_language_does_not_leave_an_empty_conditional_section(self):
        self.readings['documentary_instructions'] = {}
        self.readings['source_order'] = [{'section': 'only_hebrew', 'heading': None,
            'conditions': [{'type': 'opensiddur:holiday-aggregate', 'features': {'shabbat': True}}],
            'order': [{'unit': 'second'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        he = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        en = etree.parse(str(self.projects/PROJECTS['en']/'index.xml'))
        self.assertEqual(len(he.findall('.//'+J+'conditional')), 1)
        self.assertFalse(en.findall('.//'+J+'conditional'))
        self.assertFalse(en.findall('.//'+J+'transclude'))

    def test_untranslated_service_file_and_reference_are_absent_in_english(self):
        self.readings['documentary_instructions'] = {}
        self.readings['source_order'] = [{'section': 'offerings', 'file': 'offerings',
            'corresp': BASE+'another', 'heading': None, 'witnesses': ['he'],
            'titles': {'he': 'קרבנות', 'en': 'Offerings'}, 'order': [{'unit': 'second'}]}]
        self.save('readings', self.readings)
        stale = self.projects/PROJECTS['en']/'offerings.xml'
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text('An obsolete English service must not survive.')
        self.generate(draft=True)
        self.assertTrue((self.projects/PROJECTS['he']/'offerings.xml').exists())
        self.assertFalse(stale.exists())
        he = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        en = etree.parse(str(self.projects/PROJECTS['en']/'index.xml'))
        self.assertEqual(he.find('.//'+J+'transclude').get('target'), BASE+'another@'+PROJECTS['he'])
        self.assertFalse(en.findall('.//'+J+'transclude'))

    def test_uncertain_character_keeps_exact_words_and_the_language_span(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_1.build import rubric_words, instruction_review_text
        rubric = {'text': 'ז שבת wordז ז', 'language_spans': [
            {'text': 'שבת', 'language': 'he'}],
            'uncertain_characters': [{'word': 'wordז', 'character': 'ז'}]}
        note = etree.Element(T+'note')
        rubric_words(note, rubric, 'de-Hebr')
        self.assertEqual(''.join(note.itertext()), rubric['text'])
        self.assertEqual(note.find(T+'foreign').get('{http://www.w3.org/XML/1998/namespace}lang'), 'he')
        marked = note.findall(T+'c')
        self.assertEqual(len(marked), 1)
        self.assertEqual(marked[0].text, 'ז')
        self.assertEqual(marked[0].get('cert'), 'low')
        plain = dict(rubric)
        plain.pop('uncertain_characters')
        self.assertNotEqual(reading_hash(instruction_review_text(rubric)),
                            reading_hash(instruction_review_text(plain)))

    def test_documentary_ranges_preserve_a_missing_translation_between_neighbors(self):
        self.readings['source_order'] = [
            {'reference': {'target': BASE+'invented/1', 'targetEnd': BASE+'invented/2'}},
            {'reference': {'target': BASE+'invented/3'}, 'witnesses': ['he']},
            {'reference': {'target': BASE+'invented/4'}}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        for lang, project in PROJECTS.items():
            root = etree.parse(str(self.projects/project/'index.xml'))
            transclusions = root.findall('.//'+J+'transclude')
            expected = ['1', '3', '4'] if lang == 'he' else ['1', '4']
            self.assertEqual([node.get('target') for node in transclusions],
                             [BASE+'invented/'+verse+'@'+project for verse in expected])
            self.assertEqual(transclusions[0].get('targetEnd'),
                             BASE+'invented/2')
        # Edition qualification belongs to the generated witnesses, not the
        # shared canonical assembly data.
        self.assertNotIn('@', self.readings['source_order'][0]['reference']['target'])

    def test_verse_range_includes_a_refrain_on_its_continuation_line(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_1.build import unit_document
        bible = 'urn:x-opensiddur:text:bible:psalms/136'
        unit = {'stem': 'example', 'urn': bible, 'title': {'en': 'Example'},
                'poetry': {'en': True}, 'languages': {'en': [
                    {'corresp': bible+'/26', 'paragraph': 1,
                     'fragments': [{'scan': 's1', 'text': 'Lead'}]},
                    {'paragraph': 2, 'fragments': [
                        {'scan': 's1', 'text': 'Response', 'text_type': 'refrain'}]}]}}
        root = unit_document(unit, 'en', draft=True)
        lines = root.findall('.//'+T+'l')
        marker = lines[0].find(T+'milestone[@unit="verse"]')
        response = lines[1].find(T+'seg[@type="refrain"]')
        self.assertEqual(''.join(response.itertext()).strip(), 'Response')
        end, include_tail = find_end_of_mapping(marker)
        self.assertIs(root.xpath(end, namespaces={'tei': T[1:-1]})[0], response)
        self.assertTrue(include_tail)
        self.assertEqual(lines[1].find(T+'milestone').get('unit'), 'verse')
        reviewed = reading_hash(unit_review_text(unit, 'en'))
        unit['languages']['en'][1]['fragments'][0].pop('text_type')
        self.assertNotEqual(reviewed, reading_hash(unit_review_text(unit, 'en')))

    def test_verses_can_cross_and_share_printed_poetry_lines(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_1.build import unit_document
        bible = 'urn:x-opensiddur:text:bible:exodus/15'
        unit = {'stem': 'example', 'urn': bible, 'title': {'en': 'Example'},
                'poetry': {'en': True}, 'languages': {'en': [
                    {'corresp': bible+'/1', 'fragments': [
                        {'scan': 's1', 'line': 1, 'text': 'First'},
                        {'scan': 's1', 'line': 2, 'text': 'continuation'}]},
                    {'corresp': bible+'/2', 'fragments': [
                        {'scan': 's1', 'line': 2, 'text': 'Second'},
                        {'scan': 's2', 'line': 3, 'text': 'ending'}]}]}}
        root = unit_document(unit, 'en', draft=True)
        lines = root.findall('.//'+T+'l')
        self.assertEqual([' '.join(''.join(n.itertext()).split()) for n in lines],
                         ['First', 'continuation Second', 'ending'])
        self.assertEqual(len(lines[0].findall(T+'milestone[@unit="verse"]')), 1)
        self.assertEqual(lines[1].find(T+'milestone').get('corresp'), bible+'/2')
        self.assertTrue(lines[2].find(T+'pb').get('facs').endswith('/page/n1.jpg'))
        self.assertIsNone(lines[2].find(T+'milestone').get('corresp'))

    def test_biblical_quote_scope_ends_before_unmapped_prayer_words(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_1.build import unit_document
        verse = 'urn:x-opensiddur:text:bible:psalms/35/10'
        unit = {'stem': 'example', 'urn': BASE+'example', 'title': {'en': 'Example'},
                'languages': {'en': [
                    {'corresp': verse, 'end_reference': True,
                     'fragments': [{'scan': 's1', 'text': 'Quoted verse.'}]},
                    {'fragments': [{'scan': 's1', 'text': 'Unrelated prayer words.'}]}]}}
        root = unit_document(unit, 'en', draft=True)
        marker = root.find('.//'+T+'milestone[@corresp="'+verse+'"]')
        terminator = marker.getnext()
        self.assertEqual(terminator.get('unit'), 'verse')
        self.assertIsNone(terminator.get('corresp'))
        self.assertEqual(marker.tail.strip(), 'Quoted verse.')
        chapter_end = terminator.getnext()
        self.assertEqual(chapter_end.get('unit'), 'chapter')
        self.assertEqual(chapter_end.tail.strip(), 'Unrelated prayer words.')

    def test_uncertain_combining_point_stays_bound_to_the_reviewed_prayer_reading(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_1.build import unit_document
        word = 'הָֽלְכוּ'
        fragment = {'scan': 's1', 'text': word,
                    'uncertain_characters': [{'word': word, 'character': 'ֽ'}]}
        unit = {'stem': 'example', 'urn': BASE+'example', 'title': {'he': 'Example'},
                'languages': {'he': [{'fragments': [fragment]}]}}
        root = unit_document(unit, 'he', draft=True)
        point = root.find('.//'+T+'body//'+T+'c')
        self.assertEqual(point.text, 'ֽ')
        self.assertEqual(point.get('cert'), 'low')
        self.assertEqual(''.join(root.find('.//'+T+'body').itertext()).strip(), word)
        reviewed = reading_hash(unit_review_text(unit, 'he'))
        fragment.pop('uncertain_characters')
        self.assertNotEqual(reviewed, reading_hash(unit_review_text(unit, 'he')))

    def test_prayer_title_keeps_its_language_inside_a_hebrew_script_german_rubric(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_1.build import instruction_review_text
        rubric = {'text': 'Before תפילה after', 'language': 'de-Hebr',
                  'language_spans': [{'text': 'תפילה', 'language': 'he'}]}
        self.readings['documentary_instructions'] = {'custom': dict(rubric,
            witnesses=['he'], scan='s1', printed_page='1')}
        self.readings['source_order'] = [{'instruction': 'custom'}]
        self.readings['expanded_order'] = [{'section': 'custom',
            'conditions': [{'type': 'opensiddur:holiday-aggregate', 'features': {'shabbat': True}}],
            'condition_rubrics': {'de-Hebr': rubric}, 'order': [{'unit': 'first'}]}]
        before = instruction_review_text(rubric)
        self.save('readings', self.readings)
        self.generate(draft=True)
        for project in [PROJECTS['he'], EXPANDED]:
            root = etree.parse(str(self.projects/project/'index.xml'))
            foreign = root.find('.//'+T+'foreign[@{http://www.w3.org/XML/1998/namespace}lang="he"]')
            self.assertEqual(foreign.text, 'תפילה')
        rubric['language_spans'][0]['language'] = 'arc'
        self.assertNotEqual(before, instruction_review_text(rubric))

    def test_service_file_keeps_bilingual_heading_after_untranslated_material(self):
        self.readings['documentary_instructions'] = {
            lang: {'text': 'Service heading', 'kind': 'heading', 'language': lang,
                   'witnesses': [lang], 'scan': 's1', 'printed_page': '1'}
            for lang in ['he', 'en']}
        self.readings['source_order'] = [{'unit': 'second'},
            {'section': 'service', 'file': 'service', 'corresp': BASE+'another',
             'heading': {'he': 'he', 'en': 'en'}, 'order': [{'unit': 'first'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        for project in PROJECTS.values():
            index = etree.parse(str(self.projects/project/'index.xml'))
            self.assertFalse(index.findall('.//'+T+'body//'+T+'head'))
            targets = [x.get('target') for x in index.findall('.//'+J+'transclude')]
            self.assertEqual(targets[-1], BASE+'another@'+project)
            service = etree.parse(str(self.projects/project/'service.xml'))
            self.assertEqual(service.find('.//'+T+'body//'+T+'head').text, 'Service heading')
            self.assertEqual(service.find('.//'+J+'transclude').get('target'), BASE+'invented@'+project)

    def test_documentary_occurrence_retains_the_canonical_prayer_identity(self):
        unit = self.readings['units'][0]
        unit['publication_context'] = BASE+'another'
        self.save('readings', self.readings)
        self.generate(draft=True)
        doc = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        context = doc.find('.//'+T+'body/'+T+'div')
        self.assertEqual(context.get('corresp'), BASE+'another')
        self.assertEqual(context.find(T+'div').get('corresp'), BASE+'invented')
        index = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        self.assertEqual(index.find('.//'+J+'transclude').get('target'), BASE+'another@'+PROJECTS['he'])
        expanded = etree.parse(str(self.projects/EXPANDED/'index.xml'))
        self.assertEqual(expanded.find('.//'+J+'transclude').get('target'), BASE+'invented')

    def test_reused_occurrence_does_not_declare_the_canonical_prayer_twice(self):
        unit = self.readings['units'][0]
        unit['publication_context'] = BASE+'another'
        unit['reuse'] = {'he': BASE+'invented'}
        self.save('readings', self.readings)
        self.generate(draft=True)
        doc = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        self.assertFalse(doc.findall('.//*[@corresp="'+BASE+'invented"]'))
        self.assertEqual(doc.find('.//'+J+'transclude').get('target'), BASE+'invented@'+PROJECTS['he'])
        self.assertEqual(doc.find('.//'+T+'body/'+T+'div').get('corresp'), BASE+'another')

    def test_poetic_lines_are_independent_of_the_translation_paragraph(self):
        unit = self.readings['units'][0]
        unit['poetry'] = {'he': True}
        unit['languages']['he'] = [
            {'paragraph': n, 'corresp': BASE+'invented/'+str(n), 'reference_unit': 'stanza',
             'fragments': [{'scan': 's1', 'text': text}]}
            for n, text in [(1, 'First couplet'), (2, 'Second couplet')]]
        self.save('readings', self.readings)
        self.generate(draft=True)
        he = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        self.assertEqual(len(he.findall('.//'+T+'body//'+T+'lg')), 1)
        self.assertEqual(len(he.findall('.//'+T+'body//'+T+'l')), 2)
        self.assertFalse(he.findall('.//'+T+'body//'+T+'p'))
        self.assertEqual(len(he.findall('.//'+T+'milestone[@corresp]')), 2)
        en = etree.parse(str(self.projects/PROJECTS['en']/'first.xml'))
        self.assertFalse(en.findall('.//'+T+'body//'+T+'lg'))
        self.assertEqual(len(en.findall('.//'+T+'body//'+T+'p')), 1)

    def test_regeneration_keeps_documentary_previews_independent_of_device_day(self):
        self.generate(draft=True)
        for variant in ('documentary', 'with_translation'):
            path = self.projects.parent/'settings'/PROJECTS['he']/(variant+'.yaml')
            settings = yaml.safe_load(path.read_text())
            self.assertEqual(settings['electronic']['day'], 'none')

    def test_rubric_abbreviation_and_expansion_are_both_reviewed(self):
        unit = self.readings['units'][0]
        unit['instructions'] = [{'language': 'he', 'text': 'הש״ץ מנגן.',
                                 'abbreviations': [{'abbr': 'הש״ץ', 'expan': 'השליח ציבור'}]}]
        original = unit_review_text(unit, 'he')
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        self.assertEqual(root.find('.//'+T+'note/'+T+'choice/'+T+'abbr').text, 'הש״ץ')
        self.assertEqual(root.find('.//'+T+'note/'+T+'choice/'+T+'expan').text, 'השליח ציבור')
        unit['instructions'][0]['abbreviations'][0]['expan'] = 'אחר'
        self.assertNotEqual(unit_review_text(unit, 'he'), original)

    def test_page_turn_after_maqaf_does_not_add_a_word_break(self):
        self.readings['units'][0]['languages']['he'] = [{'fragments': [
            {'scan': 's1', 'text': 'אב־'}, {'scan': 's2', 'text': 'גד'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        paragraph = root.find('.//'+T+'body/'+T+'div/'+T+'p')
        self.assertEqual(printed_text(paragraph).strip(), 'אב־גד')
        self.assertEqual(len(paragraph.findall(T+'pb')), 2)

    def test_refrain_cue_is_outside_the_reusable_stanza_and_language_is_preserved(self):
        unit = self.readings['units'][0]
        unit['languages']['he'] = [{
            'corresp': BASE+'invented/1', 'reference_unit': 'stanza',
            'language': 'arc', 'fragments': [{'scan': 's1', 'text': 'אב'}],
            'repeat_cue': {'text': 'לכה', 'target': BASE+'invented/1'}}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        paragraph = root.find('.//'+T+'body/'+T+'div/'+T+'p')
        self.assertEqual(paragraph.get('{http://www.w3.org/XML/1998/namespace}lang'), 'arc')
        start = paragraph.find(T+'milestone[@corresp]')
        end, include_tail = find_end_of_mapping(start)
        self.assertIs(root.xpath(end, namespaces={'tei': T[1:-1]})[0], start)
        self.assertTrue(include_tail)
        self.assertIsNone(start.getnext().get('corresp'))
        cue = paragraph.find(T+'note[@type="instruction"]/'+T+'ref')
        self.assertEqual(cue.text, 'לכה')
        self.assertEqual(cue.get('target'), BASE+'invented/1@'+PROJECTS['he'])
        self.assertIn('לכה ['+BASE+'invented/1]', unit_review_text(unit, 'he'))

    def test_expanded_combined_role_is_not_reduced_to_congregation(self):
        self.readings['expanded_order'] = [
            {'section': 'joint_response', 'role': 'reader_and_congregation',
             'order': [{'unit': 'first'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/EXPANDED/'index.xml'))
        note = root.find('.//'+T+'note[@corresp="urn:x-opensiddur:instruction:role/reader_and_congregation"]')
        self.assertEqual(note.text, 'קהל וחזן')

    def test_preliminary_service_conditions_end_before_the_morning_section(self):
        self.readings['expanded_order'] = [
            {'section': 'preliminary', 'heads': {'he': 'הכנה', 'en': 'Preparation'},
             'conditions': [{'type': 'opensiddur:service-time', 'features': {'minha': True}},
                            {'type': 'opensiddur:holiday', 'features': {'rosh-hashana': 0}}],
             'condition_rubrics': {'he': 'במניין:', 'en': 'With a minyan:'},
             'declarations': [{'type': 'opensiddur:recitation', 'features': {'silent': True}}],
             'order': [{'unit': 'first'}, {'unit': 'first'}]},
            {'section': 'morning', 'heads': {'he': 'שחרית', 'en': 'Morning'},
             'conditions': [{'type': 'opensiddur:service-time', 'features': {'shaharit': True}}],
             'order': [{'unit': 'second'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/EXPANDED/'index.xml'))
        preliminary = root.find('.//'+T+'div[@{http://www.w3.org/XML/1998/namespace}id="section_preliminary"]')
        morning = preliminary.getnext()
        self.assertEqual(preliminary[-1].tag, J+'endConditional')
        self.assertEqual(preliminary[-1].get('target'), '#section_preliminary_condition')
        self.assertEqual(morning.get('{http://www.w3.org/XML/1998/namespace}id'), 'section_morning')
        self.assertEqual([t.get('target') for t in preliminary.findall('.//'+J+'transclude')],
                         [BASE+'invented']*2)
        self.assertEqual(morning.find('.//'+J+'transclude').get('target'), BASE+'another')
        self.assertEqual(preliminary.find('.//'+T+'numeric').get('value'), '0')
        conditional = preliminary.find(J+'conditional')
        self.assertEqual(len(conditional.findall(T+'note')), 1)
        self.assertEqual(conditional[0].tag, T+'note')
        self.assertEqual(len(conditional[0].findall(T+'foreign')), 2)
        content = preliminary.find(T+'div')
        self.assertEqual(content[-1].tag, J+'endDeclare')
        self.assertEqual(content[-1].get('target'), '#section_preliminary_settings')

    def test_reusable_unit_requires_both_repetition_and_minyan(self):
        unit = self.readings['units'][0]
        unit['conditions'] = [
            {'type': 'opensiddur:recitation', 'features': {'repetition': True}},
            {'type': 'opensiddur:quorum', 'features': {'minyan': True}}]
        unit['instructions'] = [{'language': 'he', 'text': 'בחזרת התפלה'}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        div = root.find('.//'+T+'body/'+T+'div')
        condition = parse_condition_element(div[0])
        self.assertEqual(div[1].tag, T+'note')
        self.assertEqual(div[-1].get('target'), '#first_condition')
        self.assertEqual(div[-1].tag, J+'endConditional')
        for repetition, minyan, expected in [
                (True, True, TriState.TRUE), (False, True, TriState.FALSE),
                (True, False, TriState.FALSE), (None, None, TriState.UNDEFINED)]:
            with self.subTest(repetition=repetition, minyan=minyan):
                settings = {('opensiddur:recitation', 'repetition'): repetition,
                            ('opensiddur:quorum', 'minyan'): minyan}
                processor = Mock()
                processor.get_active_setting.side_effect = lambda kind, feature: settings.get((kind, feature))
                self.assertEqual(evaluate_condition(condition, processor), expected)

    def test_person_gender_uses_registered_symbol_and_selects_one_alternative(self):
        self.readings['units'][0]['conditions'] = [
            {'type': 'opensiddur:person', 'features': {'gender': 'female'}}]
        self.readings['units'][0]['instructions'] = [
            {'language': 'en', 'placement': 'condition', 'text': 'Women say:'}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        scope = root.find('.//'+J+'conditional')
        self.assertEqual(scope.find('.//'+T+'symbol').get('value'), 'female')
        self.assertIsNone(scope.find('.//'+T+'numeric'))
        condition = parse_condition_element(scope)
        for gender, expected in [('female', TriState.TRUE), ('male', TriState.FALSE),
                                 (None, TriState.UNDEFINED)]:
            processor = Mock()
            processor.get_active_setting.return_value = gender
            with self.subTest(gender=gender):
                self.assertEqual(evaluate_condition(condition, processor), expected)

    def test_scripture_scope_ends_before_liturgy_and_repetition_reuses_the_witness(self):
        bible = 'urn:x-opensiddur:text:bible:psalms/'
        self.readings['units'][0]['languages']['he'] = [
            {'corresp': bible+'5/8', 'fragments': [{'scan': 's1', 'text': 'first'}]},
            {'corresp': bible+'39/13/shimah', 'fragments': [{'scan': 's1', 'text': 'clause'}]},
            {'corresp': BASE+'another', 'fragments': [{'scan': 's1', 'text': 'other liturgy'}]},
            {'repeat': bible+'5/8', 'fragments': [{'scan': 's1', 'text': 'first'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        chapters = root.findall('.//'+T+'milestone[@unit="chapter"][@corresp]')
        self.assertEqual(chapters, [])  # An excerpt must not resolve as its entire Psalm.
        self.assertEqual([x.get('n') for x in root.findall('.//'+T+'milestone[@unit="chapter"]') if x.get('n')], ['5', '39'])
        clause = root.find('.//'+T+'milestone[@unit="verse-part"]')
        self.assertEqual(clause.get('n'), 'shimah')
        end, include_tail = find_end_of_mapping(clause)
        self.assertIs(root.xpath(end, namespaces={'tei': T[1:-1]})[0], clause)
        self.assertTrue(include_tail)
        self.assertEqual(len(root.findall('.//'+T+'milestone[@corresp="'+bible+'5/8"]')), 1)
        repeat = root.find('.//'+J+'transclude[@type="inline"]')
        self.assertEqual(repeat.get('target'), bible+'5/8@'+PROJECTS['he'])

    def test_repeated_scripture_has_addressable_chapter_and_verse_context(self):
        chapter = BASE+'another/quoted_isaiah_6'
        verse = chapter+'/3'
        self.registry_mock.records.update({chapter: {}, verse: {}})
        self.readings['units'][0]['languages']['he'] = [{
            'corresp': verse, 'source': 'urn:x-opensiddur:text:bible:isaiah/6/3',
            'reference_unit': 'verse', 'chapter_corresp': chapter,
            'fragments': [{'scan': 's1', 'text': 'quotation'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        self.assertEqual(root.find('.//'+T+'milestone[@unit="chapter"][@n]').get('corresp'), chapter)
        self.assertEqual(root.find('.//'+T+'milestone[@unit="verse"][@n]').get('corresp'), verse)
        self.assertFalse(root.findall('.//*[@corresp="urn:x-opensiddur:text:bible:isaiah/6"]'))

    def test_bounded_scripture_context_does_not_end_its_enclosing_prayer_part(self):
        chapter = BASE+'another/quoted_isaiah_6'
        verse = chapter+'/3'
        self.registry_mock.records.update({chapter: {}, verse: {}})
        self.readings['units'][0]['languages']['he'] = [
            {'corresp': BASE+'another', 'fragments': [{'scan': 's1', 'text': 'prefix'}]},
            {'source_reference': 'urn:x-opensiddur:text:bible:isaiah/6/3',
             'source_reference_corresp': verse, 'chapter_corresp': chapter,
             'source': 'urn:x-opensiddur:text:bible:isaiah/6/3',
             'fragments': [{'scan': 's1', 'text': 'quotation'}]},
            {'fragments': [{'scan': 's1', 'text': 'suffix'}], 'end_reference': True},
            {'fragments': [{'scan': 's1', 'text': 'unrelated'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        prayer = root.find('.//'+T+'milestone[@corresp="'+BASE+'another"]')
        quote = root.find('.//'+T+'milestone[@corresp="'+verse+'"]')
        quote_end = quote.getnext().getnext()
        self.assertEqual(quote_end.get('unit'), 'verse')
        self.assertIsNone(quote_end.get('corresp'))
        end, include_tail = find_end_of_mapping(prayer)
        endpoint = root.xpath(end, namespaces={'tei': T[1:-1]})[0]
        self.assertTrue(include_tail)
        self.assertEqual(endpoint.get('unit'), 'chapter')
        self.assertIsNone(endpoint.get('corresp'))
        self.assertEqual(endpoint.tail.strip(), 'suffix')
        self.assertEqual(endpoint.getnext().get('unit'), 'prayer-part')
        self.assertEqual(endpoint.getnext().tail.strip(), 'unrelated')

    def test_quote_context_cannot_truncate_its_enclosing_prayer_part(self):
        chapter = BASE+'another/quoted_isaiah_6'
        self.registry_mock.records.update({chapter: {}, chapter+'/3': {}, BASE+'invented/part': {}})
        self.readings['units'][0]['languages']['he'] = [
            {'corresp': BASE+'invented/part', 'fragments': [{'scan': 's1', 'text': 'prefix'}]},
            {'source_reference': 'urn:x-opensiddur:text:bible:isaiah/6/3',
             'source_reference_corresp': chapter+'/3', 'chapter_corresp': chapter,
             'fragments': [{'scan': 's1', 'text': 'quotation'}]}]
        self.save('readings', self.readings)
        with self.assertRaisesRegex(ValueError, 'deeper than its enclosing prayer-part'):
            self.generate(draft=True)

    def test_editorial_commentary_can_target_a_local_variant_anchor(self):
        unit = self.readings['units'][0]
        unit['citations'] = {'he': [{'scan': 's1', 'text': 'Editorial variant note.',
                                    'note_type': 'commentary', 'target': '#variant_here'}]}
        unit['languages']['he'] = [
            {'fragments': [{'scan': 's1', 'text': 'prefix'}]},
            {'anchor': 'variant_here', 'fragments': [{'scan': 's1', 'text': '(variant)'}]},
            {'fragments': [{'scan': 's1', 'text': 'suffix'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        anchor = root.find('.//'+T+'anchor')
        self.assertEqual(anchor.get('{http://www.w3.org/XML/1998/namespace}id'), 'variant_here')
        self.assertIn('(variant)', anchor.tail)
        note = root.find('.//'+T+'standOff/'+T+'note')
        self.assertEqual(note.get('target'), '#variant_here')

    def test_complete_chapter_remains_addressable_inside_a_composite_prayer(self):
        bible = 'urn:x-opensiddur:text:bible:psalms/'
        unit = self.readings['units'][0]
        unit['complete_chapters'] = [bible+'117']
        unit['languages']['he'] = [
            {'corresp': bible+'117/1', 'fragments': [{'scan': 's1', 'text': 'first'}]},
            {'corresp': bible+'117/2', 'fragments': [{'scan': 's1', 'text': 'second'}]},
            {'corresp': BASE+'another', 'fragments': [{'scan': 's1', 'text': 'other liturgy'}]}]
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        chapter = root.find('.//'+T+'milestone[@unit="chapter"][@corresp]')
        self.assertEqual(chapter.get('corresp'), bible+'117')
        end, _ = find_end_of_mapping(chapter)
        self.assertIsNone(root.xpath(end, namespaces={'tei': T[1:-1]})[0].get('corresp'))

    def test_liturgical_identity_retains_its_scripture_source_and_scan_boundary(self):
        segments = self.readings['units'][0]['languages']['he']
        segments[0].update(corresp=BASE+'invented', source=BASE+'another', source_type='adaptation')
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        marker = root.find('.//'+T+'milestone')
        self.assertEqual(marker.get('unit'), 'prayer-part')
        self.assertEqual(marker.get('corresp'), BASE+'invented')
        spans = root.findall('.//'+T+'seg')
        self.assertEqual([s.get('source') for s in spans], [BASE+'another']*2)
        self.assertEqual([s.get('type') for s in spans], ['adaptation']*2)
        self.assertEqual(spans[1].getprevious().tag, T+'pb')

    def test_correction_layer_preserves_the_reviewed_printed_reading_and_rejects_stale_context(self):
        fragment = self.readings['units'][0]['languages']['en'][0]['fragments'][0]
        fragment['text'] = 'Before wrdos after.'
        self.save('readings', self.readings)
        self.save('corrections', {'corrections': [
            {'id': 'invented_typo', 'file': PROJECTS['en']+'/first.xml',
             'sic': 'wrdos', 'corr': 'words', 'before': 'Before ', 'after': ' after.'}]})
        self.generate(draft=True)
        path = self.projects/PROJECTS['en']/'first.xml'
        root = etree.parse(str(path))
        body = root.find('.//'+T+'body')
        self.assertEqual(' '.join(printed_text(body).split()), fragment['text'])
        choice = body.find('.//'+T+'choice')
        self.assertEqual(choice.find(T+'sic').text, 'wrdos')
        self.assertEqual(choice.find(T+'corr').text, 'words')
        before = path.read_bytes()
        fragment['text'] = 'Changed context wrdos after.'
        self.save('readings', self.readings)
        with self.assertRaisesRegex(ValueError, '0 places match'):
            self.generate(draft=True)
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

    def test_printed_citation_is_a_standoff_note_targeting_the_passage(self):
        self.readings['units'][0]['languages']['en'][0]['corresp'] = BASE+'invented/1'
        self.readings['units'][0]['citations'] = {'en': [
            {'scan': 's3', 'printed_page': '7', 'text': '(Invented source.)'}]}
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['en']/'first.xml'))
        body = root.find('.//'+T+'body')
        citation = root.find('.//'+T+'standOff/'+T+'note[@type="citation"]')
        self.assertEqual(citation.find(T+'p').text, 'Invented source.')
        self.assertEqual(citation.get('target'), BASE+'invented')
        self.assertNotIn('(Invented source.)', ''.join(body.itertext()))
        self.assertEqual(len(body.findall('.//'+T+'pb')), 1)

    def test_variant_note_follows_its_calendar_context(self):
        self.readings['units'][0]['citations'] = {'he': [{
            'scan': 's1', 'text': 'Alternate wording', 'note_type': 'commentary',
            'conditions': [{'type': 'opensiddur:holiday-aggregate',
                            'features': {'shabbat': True}}]}]}
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        note = root.find('.//'+T+'standOff/'+T+'note')
        self.assertEqual(note[0].tag, J+'condition')
        self.assertEqual(note.find(T+'p').text, 'Alternate wording')
        condition = parse_condition_element(note[0])
        for shabbat, expected in [(True, TriState.TRUE), (False, TriState.FALSE),
                                   (None, TriState.UNDEFINED)]:
            with self.subTest(shabbat=shabbat):
                processor = Mock()
                processor.get_active_setting.return_value = shabbat
                self.assertEqual(evaluate_condition(condition, processor), expected)

    def test_citation_can_target_a_later_verse_in_a_composite_prayer(self):
        self.readings['units'][0]['languages']['he'].append(
            {'corresp': BASE+'another', 'fragments': [{'scan': 's1', 'text': 'וז'}]})
        self.readings['units'][0]['citations'] = {'he': [
            {'scan': 's1', 'text': '(Psalm number)', 'target': BASE+'another'}]}
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        note = root.find('.//'+T+'standOff/'+T+'note[@type="citation"]')
        self.assertEqual(note.get('target'), BASE+'another')
        self.assertEqual(note.find(T+'p').text, 'Psalm number')

    def test_source_acrostic_is_commentary_outside_recited_words(self):
        self.readings['units'][0]['citations'] = {'he': [
            {'scan': 's1', 'text': 'אבג״יתץ', 'note_type': 'commentary',
             'text_type': 'acrostic', 'target': BASE+'invented'}]}
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        note = root.find('.//'+T+'standOff/'+T+'note[@type="commentary"]')
        self.assertEqual(note.find(T+'p/'+T+'seg[@type="acrostic"]').text, 'אבג״יתץ')
        self.assertNotIn('אבג״יתץ', ''.join(root.find('.//'+T+'body').itertext()))

    def test_documentary_page_retains_heading_rubric_and_edition_target(self):
        unit = self.readings['units'][0]
        unit.update(map_root=False,
                    head={'he': 'תפלה'},
                    instructions=[{'language': 'en', 'text': 'Enter here.'}])
        self.save('readings', self.readings)
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'first.xml'))
        div = root.find('.//'+T+'body/'+T+'div')
        self.assertIsNone(div.get('corresp'))
        self.assertEqual([e.tag for e in list(div)[:3]], [T+'pb', T+'head', T+'note'])
        self.assertEqual(div.find(T+'head').text, 'תפלה')
        self.assertEqual(div.find(T+'note').text, 'Enter here.')
        self.assertIn('תפלה Enter here.', unit_review_text(unit, 'he'))
        index = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        self.assertEqual(index.find('.//'+J+'transclude').get('target'), unit['urn']+'@'+PROJECTS['he'])
        self.assertFalse(index.findall('.//'+T+'body/'+T+'div/'+T+'head'))
        expanded = etree.parse(str(self.projects/EXPANDED/'index.xml'))
        self.assertIsNone(expanded.find('.//'+T+'titlePage'))
        self.assertNotIn('pilot', ''.join(expanded.find('.//'+T+'front').itertext()).lower())

    def test_cover_and_hebrew_title_retain_language_and_distinct_imprint_fields(self):
        self.save('front', {'pages': [
            {'scan': 's1', 'kind': 'cover', 'language': 'en', 'head': 'Invented cover',
             'paragraphs': ['AB', 'שם "מחבר"', 'Invented volume'], 'paragraph_languages': {'1': 'he'}},
            {'scan': 's2', 'kind': 'title', 'language': 'he',
             'paragraphs': ['כותרת', 'משנה', 'עורך', 'מתרגם', 'מוציא לאור', 'עיר', 'שנה'],
             'title_layout': {'main': 0, 'sub': 1, 'bylines': [2, 3], 'publisher': 4, 'place': 5, 'date': 6}}]})
        self.generate(draft=True)
        root = etree.parse(str(self.projects/PROJECTS['he']/'index.xml'))
        front = root.find('.//'+T+'front')
        signature = front.find(T+'div').findall(T+'p')[1]
        self.assertEqual(signature.get('{http://www.w3.org/XML/1998/namespace}lang'), 'he')
        self.assertEqual(signature.find(T+'foreign').text, 'שם "מחבר"')
        title = front.find(T+'titlePage')
        self.assertEqual(title.get('{http://www.w3.org/XML/1998/namespace}lang'), 'he')
        self.assertEqual(title.find('.//'+T+'titlePart[@type="sub"]').text, 'משנה')
        self.assertEqual(title.find('.//'+T+'pubPlace').text, 'עיר')
        self.assertEqual(title.find('.//'+T+'docDate').text, 'שנה')
        self.assertEqual(len(front.findall('.//'+T+'pb')), 2)

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

    def test_crop_names_and_out_of_inventory_reads_do_not_inflate_leaf_count(self):
        self.save('pages', {'pages': [{'scan_page': n} for n in range(1, 5)]})
        independent = self.source/'independent'
        independent.mkdir()
        (independent/'reader.json').write_text(json.dumps({'reviewer': {'model': 'second'},
            'pages': [{'scan': s} for s in ['s1.jpg', 's1', 's2', 's1-detail.png', 's5']]}))
        result = report(self.source)
        self.assertEqual(result['leaves_independently_read'], 2)
