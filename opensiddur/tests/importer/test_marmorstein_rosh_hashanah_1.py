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
