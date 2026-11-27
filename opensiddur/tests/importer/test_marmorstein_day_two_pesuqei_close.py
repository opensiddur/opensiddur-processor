"""Synthetic checks for extending a service without replacing its earlier text."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_2 import PROJECTS
from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei_close import (
    SERVICE_URN,
    append_sequence,
    build_documents,
    check_existing_providers,
)
from opensiddur.importer.scan.authoring import TEI, XML, J

T = '{'+TEI+'}'
TARGET = 'urn:x-opensiddur:text:bible:psalms/150/6'


class TestClosingPesuqei(unittest.TestCase):
    def template(self, expanded=False):
        attrs = ('xml:id="second_day_pesuqei_dezimrah"' if expanded
                 else 'corresp="'+SERVICE_URN+'"')
        return etree.fromstring(f'''<tei:TEI xmlns:tei="{TEI}" xmlns:j="{J}">
          <tei:text><tei:body><tei:div xml:id="morning_blessings">
          <tei:head>Morning Prayer</tei:head><tei:div {attrs}>
          <j:transclude target="urn:x-opensiddur:text:prayer:earlier"/>
          </tei:div></tei:div></tei:body></tei:text></tei:TEI>''')

    def test_expanded_repeat_and_missing_translation_remain_locally_scoped(self):
        root = self.template(True)
        before = etree.tostring(root)
        units = {'normal': {'urn': TARGET, 'languages': {'he': [], 'en': []}},
                 'repeat': {'urn': 'urn:x-opensiddur:text:siddur:example/repeat',
                            'languages': {'he': []}}}
        order = [{'key': 'normal', 'expanded_target': TARGET},
                 {'key': 'repeat', 'expanded_target': TARGET, 'hebrew_only_repeat': True}]
        result = append_sequence(root, units, order, lang='he', expanded=True)
        self.assertEqual(etree.tostring(root), before)
        calls = result.findall('.//{'+J+'}transclude')
        self.assertEqual([n.get('target') for n in calls],
                         ['urn:x-opensiddur:text:prayer:earlier', TARGET, TARGET])
        self.assertEqual(calls[-1].getprevious().find('.//'+T+'binary').get('value'), 'false')
        self.assertEqual(calls[-1].getnext().get('target'),
                         '#'+calls[-1].getprevious().get(XML+'id'))
        self.assertEqual(len(result.findall('.//'+T+'head')), 1)
        with self.assertRaisesRegex(ValueError, 'already present'):
            append_sequence(result, units, order, lang='he', expanded=True)

    def test_documentary_omission_and_source_only_instruction(self):
        units = {'first': {'urn': TARGET, 'languages': {'he': [], 'en': []}},
                 'untranslated': {'urn': TARGET+'/extra', 'languages': {'he': []}}}
        instruction = {'text': 'Remain standing.', 'language': 'en',
                       'witnesses': ['he'], 'facs': 'https://example.org/leaf/4'}
        order = [{'key': 'first', 'expanded_target': TARGET, 'instructions': [instruction]},
                 {'key': 'untranslated', 'expanded_target': TARGET+'/extra'}]
        en = append_sequence(self.template(), units, order, lang='en')
        self.assertEqual(len(en.findall('.//{'+J+'}transclude')), 2)
        self.assertFalse(en.findall('.//'+T+'note'))
        he = append_sequence(self.template(), units, order, lang='he')
        note = he.find('.//'+T+'note')
        self.assertEqual(note.get(XML+'lang'), 'en')
        self.assertEqual(note.get('facs'), instruction['facs'])
        self.assertIsNone(note.get('rend'))
        self.assertEqual(he.findall('.//{'+J+'}transclude')[-1].get('target'),
                         TARGET+'/extra@'+PROJECTS['he'])

    def test_expanded_repetition_uses_explicit_unqualified_calls(self):
        units = {'song': {'urn': TARGET, 'languages': {'he': [], 'en': []}}}
        order = [{'key': 'song', 'expanded_target': TARGET,
                  'expanded_calls': [TARGET, TARGET]}]
        result = append_sequence(self.template(True), units, order, lang='he', expanded=True)
        self.assertEqual([n.get('target') for n in result.findall('.//{'+J+'}transclude')][-2:],
                         [TARGET, TARGET])
        repeated = result.findall('.//{'+J+'}transclude')[-2:]
        self.assertNotEqual(repeated[0].getparent().get(XML+'id'),
                            repeated[1].getparent().get(XML+'id'))
        order[0]['expanded_calls'] = [TARGET+'@a_project']
        with self.assertRaisesRegex(ValueError, 'unqualified'):
            append_sequence(self.template(True), units, order, lang='he', expanded=True)

    def test_missing_or_duplicated_parent_and_wrong_ancestry_fail(self):
        units = {'a': {'urn': TARGET, 'languages': {'he': []}}}
        order = [{'key': 'a', 'expanded_target': TARGET}]
        for root in [etree.Element(T+'TEI'),
                     etree.fromstring(f'<tei:div xmlns:tei="{TEI}" xml:id="second_day_pesuqei_dezimrah"/>')]:
            with self.assertRaises(ValueError):
                append_sequence(root, units, order, lang='he', expanded=True)

    def test_untranslated_expanded_unit_requires_explicit_policy(self):
        units = {'solo': {'urn': TARGET, 'languages': {'he': []}}}
        order = [{'key': 'solo', 'expanded_target': TARGET}]
        with self.assertRaisesRegex(ValueError, 'explicit policy'):
            append_sequence(self.template(True), units, order, lang='he', expanded=True)
        order[0]['untranslated'] = True
        result = append_sequence(self.template(True), units, order, lang='he', expanded=True)
        self.assertEqual(result.findall('.//{'+J+'}transclude')[-1].get('target'), TARGET)

    def test_duplicate_parent_and_wrong_ancestry_are_distinct_errors(self):
        units = {'solo': {'urn': TARGET, 'languages': {'he': [], 'en': []}}}
        order = [{'key': 'solo', 'expanded_target': TARGET}]
        root = self.template(True)
        section = root.find('.//'+T+'div[@'+XML+'id="second_day_pesuqei_dezimrah"]')
        section.getparent().append(etree.fromstring(etree.tostring(section)))
        with self.assertRaisesRegex(ValueError, 'unique'):
            append_sequence(root, units, order, lang='he', expanded=True)
        root = self.template(True)
        root.find('.//'+T+'div').set(XML+'id', 'another_service')
        with self.assertRaisesRegex(ValueError, 'beneath Shacharit'):
            append_sequence(root, units, order, lang='he', expanded=True)

    def test_existing_or_new_english_cannot_fill_an_untranslated_scope(self):
        recipe = {'order': [{'expanded_target': TARGET, 'untranslated': True}],
                  'earlier_untranslated_targets': []}
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            for project in PROJECTS.values():
                (directory/project).mkdir()
            en_path = directory/PROJECTS['en']/'older.xml'
            en_path.write_text(f'<div corresp="{TARGET}"/>')
            with self.assertRaisesRegex(ValueError, 'Existing English'):
                check_existing_providers(directory, [], recipe)
            en_path.unlink()
            generated = [(PROJECTS['en']+'/new.xml',
                          etree.fromstring(f'<div corresp="{TARGET}"/>'))]
            with self.assertRaisesRegex(ValueError, 'translation gap'):
                check_existing_providers(directory, generated, recipe)
            recipe['order'] = []
            recipe['earlier_untranslated_targets'] = [TARGET]
            with self.assertRaisesRegex(ValueError, 'earlier translation gap'):
                check_existing_providers(directory, generated, recipe)


class TestClosingBuildGates(unittest.TestCase):
    def inputs(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_2 import EXPANDED
        templates = []
        for project, language, expanded in [(PROJECTS['he'], 'he', False),
                                             (PROJECTS['en'], 'en', False),
                                             (EXPANDED, 'he', True)]:
            parent = TestClosingPesuqei().template(expanded)
            parent.set(XML+'lang', language)
            header = etree.Element(T+'teiHeader')
            desc = etree.SubElement(header, T+'fileDesc')
            pub = etree.SubElement(desc, T+'publicationStmt')
            urn = etree.SubElement(pub, T+'idno', type='urn')
            urn.text = 'urn:x-opensiddur:text:siddur:example@'+project
            parent.insert(0, header)
            raw = etree.tostring(parent, encoding='unicode')
            templates.append({'path': project+('/second_day_morning.xml' if expanded
                                               else '/pesuqei_service.xml'),
                              'xml': raw, 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                              'baseline_commit': 'a'*40})
        units = {'sample': {'stem': 'sample', 'urn': TARGET,
                            'languages': {'he': [], 'en': []}}}
        recipe = {'order': [{'key': 'sample', 'expanded_target': TARGET}],
                  'protected_files': {}, 'spine_templates': templates}
        return recipe, units

    def render(self, unit, language):
        return etree.fromstring(f'<tei:div xmlns:tei="{TEI}" corresp="{unit["urn"]}"/>')

    def test_changed_baseline_and_protected_output_prevent_build(self):
        recipe, units = self.inputs()
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei_close.witness_document',
                   side_effect=self.render):
            self.assertEqual(len(build_documents(recipe, units)), 5)
            recipe['protected_files'] = {PROJECTS['he']+'/sample.xml': 'a'*64}
            with self.assertRaisesRegex(ValueError, 'protected'):
                build_documents(recipe, units)
            recipe['protected_files'] = {}
            recipe['spine_templates'][0]['sha256'] = 'b'*64
            with self.assertRaisesRegex(ValueError, 'template'):
                build_documents(recipe, units)

    def test_missing_english_endpoint_cannot_use_an_unrelated_provider(self):
        recipe, units = self.inputs()
        def render(unit, language):
            urn = TARGET if language == 'he' else TARGET+'/other'
            return etree.fromstring(f'<tei:div xmlns:tei="{TEI}" corresp="{urn}"/>')
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei_close.witness_document',
                   side_effect=render):
            with self.assertRaisesRegex(ValueError, 'Documentary call lacks source'):
                build_documents(recipe, units)

    def test_unrelated_documentary_target_is_rejected(self):
        recipe, units = self.inputs()
        recipe['order'][0]['documentary_target'] = TARGET+'/another'
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei_close.witness_document',
                   side_effect=self.render):
            with self.assertRaisesRegex(ValueError, 'Documentary call lacks source'):
                build_documents(recipe, units)

    def test_untranslated_multi_call_policy_cannot_bypass_provider_checks(self):
        recipe, units = self.inputs()
        units['sample']['languages'].pop('en')
        recipe['order'][0].update(untranslated=True, expanded_calls=[TARGET])
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei_close.witness_document',
                   side_effect=self.render):
            with self.assertRaisesRegex(ValueError, 'one explicit non-repeat'):
                build_documents(recipe, units)

    def test_chapter_is_not_an_implicit_verse_provider(self):
        from opensiddur.exporter.refdb import ReferenceDatabase
        from opensiddur.exporter.urn import UrnResolver, coarsen
        chapter = TARGET.rsplit('/', 1)[0]
        with tempfile.TemporaryDirectory() as folder:
            with ReferenceDatabase(Path(folder)/'test.sqlite') as database:
                node = etree.fromstring(f'<tei:div xmlns:tei="{TEI}" corresp="{chapter}"/>')
                database.add_urn_mapping('synthetic', 'chapter.xml', node)
                resolver = UrnResolver(database)
                self.assertEqual(len(resolver.resolve(chapter+'@synthetic')), 1)
                self.assertEqual(resolver.resolve(TARGET+'@synthetic'), [])
                self.assertIsNone(coarsen(TARGET))

    def test_new_witnesses_cannot_compete_for_one_canonical_identity(self):
        recipe = {'order': [], 'earlier_untranslated_targets': []}
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            for project in PROJECTS.values():
                (directory/project).mkdir()
            docs = [(PROJECTS['he']+'/'+stem+'.xml',
                     etree.fromstring(f'<div corresp="{TARGET}"/>'))
                    for stem in ['first', 'second']]
            with self.assertRaisesRegex(ValueError, 'Two new witnesses'):
                check_existing_providers(directory, docs, recipe)

    def test_new_english_cannot_fill_an_earlier_hebrew_only_occurrence(self):
        recipe = {'order': [], 'earlier_untranslated_targets': []}
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            for project in PROJECTS.values():
                (directory/project).mkdir()
            (directory/PROJECTS['he']/'earlier.xml').write_text(f'<div corresp="{TARGET}"/>')
            docs = [(PROJECTS['en']+'/later.xml',
                     etree.fromstring(f'<div corresp="{TARGET}"/>'))]
            with self.assertRaisesRegex(ValueError, 'earlier Hebrew-only occurrence'):
                check_existing_providers(directory, docs, recipe)
