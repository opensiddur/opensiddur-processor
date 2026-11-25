"""Regression coverage for independently optional source additions."""
import copy
from pathlib import Path
import tempfile
import unittest

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_1 import build as b, PROJECTS
from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.linear import LinearData
from opensiddur.exporter.refdb import ReferenceDatabase

ROOT = 'urn:x-opensiddur:text:poem:hymn_of_divine_unity_for_the_fourth_day_paytan'
OUTER = ROOT.replace(':text:', ':condition:')+'/additional_couplet'
INNER = OUTER+'/divine_name'
NS = {'t': b.TEI, 'j': b.J}


class SourceEncodingTests(unittest.TestCase):
    def unit(self):
        return {
            'stem': 'example', 'urn': ROOT, 'title': {'he': 'דוגמה'},
            'poetry': {'he': True},
            'languages': {'he': [
                {'paragraph': 1, 'corresp': ROOT+'/1', 'reference_unit': 'stanza',
                 'end_reference': True,
                 'fragments': [{'scan': 's1', 'printed_page': '1',
                                'text': '(אָב (יְיָ) גַּד)',
                                'optional_spans': [{'printed': '(אָב (יְיָ) גַּד)',
                                                    'text': 'אָב (יְיָ) גַּד',
                                                    'condition': OUTER}]}]},
                {'paragraph': 2, 'corresp': ROOT+'/2', 'reference_unit': 'stanza',
                 'fragments': [{'scan': 's1', 'printed_page': '1', 'text': 'סוֹף'}]}]},
            'source_encoding': {'he': {
                'reference_terminators_outside_container': True,
                'interpretations': [{'stem': 'example', 'kind': 'optional',
                                     'xml_id': 'example_optional', 'condition': OUTER,
                                     'inner_condition': INNER, 'missing_opener': False}]}}
        }

    def compile(self, document, features, target=ROOT, annotations=False):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            project = PROJECTS['he']
            path = directory/project
            path.mkdir()
            (path/'example.xml').write_bytes(etree.tostring(document))
            database = ReferenceDatabase(directory/'references.db')
            self.addCleanup(database.close)
            database.sync_project(project, directory)
            root, body = b.document('he', project, 'QA', ROOT, draft=True)
            idno = root.find('.//{'+b.TEI+'}publicationStmt/{'+b.TEI+'}idno')
            idno.getparent().remove(idno)
            declaration = b.element(body, 'j:declare')
            declaration.set(b.XML+'id', 'settings')
            b.feature_structures(declaration, [{'type': 'opensiddur:variant',
                                                'features': features}])
            b.element(body, 'j:transclude', type='external', target=target+'@'+project)
            b.element(body, 'j:endDeclare', target='#settings')
            (path/'caller.xml').write_bytes(etree.tostring(root))
            data = LinearData()
            data.xml_cache.base_path = directory
            if annotations:
                data.annotation_projects = [project]
            return ExternalCompilerProcessor(project, 'caller.xml', linear_data=data,
                                             reference_database=database).process()[0]

    def words(self, root):
        return ' '.join(''.join(root.find('.//{'+b.TEI+'}body').itertext()).split())

    def test_outer_omission_does_not_swallow_next_stanza(self):
        document = b.unit_document(self.unit(), 'he', True)
        result = self.compile(document, {OUTER: False, INNER: True})
        self.assertEqual(self.words(result), 'סוֹף')

    def test_inner_divine_name_is_independently_optional(self):
        document = b.unit_document(self.unit(), 'he', True)
        result = self.compile(document, {OUTER: True, INNER: False})
        self.assertEqual(self.words(result), 'אָב גַּד סוֹף')
        result = self.compile(document, {OUTER: True, INNER: True})
        self.assertEqual(self.words(result), 'אָב יְיָ גַּד סוֹף')

    def test_false_part_still_resolves_without_neighbor(self):
        document = b.unit_document(self.unit(), 'he', True)
        result = self.compile(document, {OUTER: False, INNER: True}, target=ROOT+'/1')
        self.assertEqual(self.words(result), '')
        terminators = document.xpath('//t:milestone[@unit="stanza"][not(@corresp)]',
                                     namespaces=NS)
        self.assertTrue(terminators)
        self.assertTrue(all(element.getparent().tag == '{'+b.TEI+'}lg'
                            for element in terminators))

    def test_interpretation_change_invalidates_review_payload(self):
        unit = self.unit()
        before = b.unit_review_text(unit, 'he')
        changed = copy.deepcopy(unit)
        changed['source_encoding']['he']['interpretations'][0]['inner_condition'] += '_changed'
        self.assertNotEqual(before, b.unit_review_text(changed, 'he'))
        self.assertEqual(unit['languages'], changed['languages'])

    def test_unknown_encoding_directive_is_rejected(self):
        unit = self.unit()
        unit['source_encoding']['he']['misspelled_directive'] = True
        with self.assertRaisesRegex(ValueError, 'source interpretation'):
            b.unit_document(unit, 'he', True)

    def test_malformed_interpretations_fail_closed(self):
        for change in [{'stem': 'different'}, {'kind': 'unknown'},
                       {'inner_conditions': INNER}]:
            with self.subTest(change=change):
                unit = self.unit()
                unit['source_encoding']['he']['interpretations'][0].update(change)
                with self.assertRaises(ValueError):
                    b.unit_document(unit, 'he', True)

    def test_nested_name_must_be_inside_its_outer_scope(self):
        unit = self.unit()
        fragment = unit['languages']['he'][0]['fragments'][0]
        fragment.update(text='יְיָ (אָב)')
        fragment['optional_spans'][0].update(printed='(אָב)', text='אָב')
        with self.assertRaisesRegex(ValueError, 'inside its outer scope'):
            b.unit_document(unit, 'he', True)

    def test_nested_scope_rejects_two_divine_names(self):
        unit = self.unit()
        fragment = unit['languages']['he'][0]['fragments'][0]
        fragment.update(text='(אָב (יְיָ) וְ(יְיָ) גַּד)')
        fragment['optional_spans'][0].update(printed=fragment['text'],
                                             text=fragment['text'][1:-1])
        with self.assertRaisesRegex(ValueError, 'inside its outer scope'):
            b.unit_document(unit, 'he', True)

    def test_footnote_removal_cannot_change_a_word(self):
        unit = self.unit()
        unit['source_encoding']['he']['remove_prayer_footnote_marker'] = {
            'printed': 'אָב*', 'text': 'גַּד'}
        with self.assertRaisesRegex(ValueError, 'Only the printed footnote'):
            b.unit_document(unit, 'he', True)

    def test_missing_opener_note_keeps_and_drops_with_its_words(self):
        unit = self.unit()
        fragment = unit['languages']['he'][0]['fragments'][0]
        fragment.update(text='אָב גַּד)')
        fragment['optional_spans'][0].update(printed=fragment['text'], text='אָב גַּד')
        rule = unit['source_encoding']['he']['interpretations'][0]
        rule.pop('inner_condition')
        rule.update(missing_opener=True, whole_line=True, text=fragment['text'])
        document = b.unit_document(unit, 'he', True)
        self.assertEqual(len(document.xpath('//t:choice[t:sic and t:corr]',
                                            namespaces=NS)), 1)
        for included in (True, False):
            with self.subTest(included=included):
                result = self.compile(document, {OUTER: included}, annotations=True)
                notes = result.xpath('//t:note[@type="commentary"]', namespaces=NS)
                self.assertEqual(len(notes), int(included))

    def test_alternate_colon_and_annotation_are_not_prayer_words(self):
        unit = self.unit()
        fragment = unit['languages']['he'][0]['fragments'][0]
        choices = [{'text': 'אָב', 'corresp': OUTER+'/main'},
                   {'text': 'גַּד', 'corresp': OUTER+'/alternate'}]
        fragment.clear()
        fragment.update(scan='s1', printed_page='1', text='אָב (נ״א גַּד:)',
                        alternatives=[{'printed': 'אָב (נ״א גַּד:)',
                                       'readings': choices, 'xml_id': 'source_alternate'}])
        unit['source_encoding']['he']['interpretations'] = [{
            'stem': 'example', 'kind': 'alternate', 'xml_id': 'source_alternate',
            'choices': choices, 'printed_annotation': '(נ״א גַּד:)',
            'colon_after_choice': True}]
        document = b.unit_document(unit, 'he', True)
        choice = document.xpath('//t:choice[j:option]', namespaces=NS)[0]
        self.assertTrue(choice.tail.startswith(':'))
        self.assertEqual(len(document.xpath('//t:standOff[@type="notes"]',
                                            namespaces=NS)), 1)
        result = self.compile(document, {OUTER+'/main': False,
                                         OUTER+'/alternate': True})
        self.assertEqual(self.words(result), 'גַּד: סוֹף')

    def test_quotation_cannot_discard_existing_semantics(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_1.source_encoding import apply_source_encoding
        for problem in ('chapter', 'span', 'prefix'):
            with self.subTest(problem=problem):
                root, body = b.document('he', PROJECTS['he'], 'QA', ROOT, draft=True)
                paragraph = b.element(body, 'p')
                if problem == 'prefix':
                    paragraph.text = 'outside words'
                b.element(paragraph, 'milestone', unit='chapter',
                          **({'corresp': ROOT+'/other'} if problem == 'chapter' else {}))
                b.element(paragraph, 'seg', 'words', source=ROOT,
                          **({'type': 'example'} if problem == 'span' else {}))
                unit = {'stem': 'example', 'source_encoding': {'he': {
                    'continuous_quotation_chapter': {
                        'n': '1', 'paragraphs': 1, 'corresp': ROOT+'/quotation'}}}}
                with self.assertRaises(ValueError):
                    apply_source_encoding(root, unit, 'he')
