"""Synthetic service order and contextual scope checks; no real source fixtures."""
import unittest
from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_2.evening import (
    documentary_documents, render_sequence, settings,
)

NS = {'t': 'http://www.tei-c.org/ns/1.0', 'j': 'http://jewishliturgy.org/ns/jlptei/2'}


class EveningSequenceTests(unittest.TestCase):
    def setUp(self):
        self.root = etree.Element('{http://www.tei-c.org/ns/1.0}div')
        self.units = {'invented': {'urn': 'urn:x-opensiddur:text:prayer:invented',
                                  'he': {'paragraphs': [['Words']]}}}

    def render(self, sequence, *, lang='he', expanded=False):
        render_sequence(self.root, sequence, lang, expanded=expanded, units=self.units)

    def test_missing_documentary_translation_has_no_placeholder_but_expansion_shares_order(self):
        sequence = [{'kind': 'module', 'file': 'invented'}]
        self.render(sequence, lang='en')
        self.assertEqual(len(self.root), 0)
        self.render(sequence, expanded=True)
        self.assertEqual(self.root[0].get('target'), self.units['invented']['urn'])
        self.assertNotIn('@', self.root[0].get('target'))

    def test_motzaei_scope_stops_before_following_blessing(self):
        self.render([{'kind': 'condition', 'id': 'boundary',
                      'expressions': [{'type': 'opensiddur:holiday-aggregate',
                                       'feature': 'motzaei-shabbat', 'value': True}],
                      'items': [{'kind': 'module', 'file': 'invented'}]},
                     {'kind': 'module', 'file': 'invented'}], expanded=True)
        self.assertEqual([etree.QName(n).localname for n in self.root],
                         ['conditional', 'transclude', 'endConditional', 'transclude'])
        self.assertEqual(self.root[2].get('target'), '#boundary')
        self.assertEqual(self.root.xpath('string(//t:binary/@value)', namespaces=NS), 'true')

    def test_documentary_direction_expands_only_at_its_occurrence(self):
        direction = {'kind': 'direction', 'readings': {
            'he': {'text': 'Source direction.', 'language': 'he', 'scan_page': 23}},
            'targets': ['urn:x-opensiddur:text:prayer:invented']}
        self.render([direction])
        self.assertEqual(len(self.root), 1)
        self.assertEqual(self.root[0].get('type'), 'instruction')
        self.root.clear()
        self.render([direction], expanded=True)
        self.assertEqual(self.root[0].get('type'), 'description')
        self.assertEqual(etree.QName(self.root[1]).localname, 'transclude')

    def test_scripture_range_transclusion_uses_exact_end(self):
        self.units['invented']['he']['verses'] = [
            {'verse_urn': 'urn:x-opensiddur:text:bible:psalms/7/2'},
            {'verse_urn': 'urn:x-opensiddur:text:bible:psalms/7/3'}]
        self.render([{'kind': 'module', 'file': 'invented'}], expanded=True)
        self.assertEqual(self.root[0].get('targetEnd'),
                         'urn:x-opensiddur:text:bible:psalms/7/3')

    def test_holiday_day_is_numeric_while_service_selection_is_boolean(self):
        settings(self.root, [{'type': 'opensiddur:holiday', 'feature': 'rosh-hashana', 'value': 2},
                             {'type': 'opensiddur:service-time', 'feature': 'maariv', 'value': True}])
        self.assertEqual(self.root.xpath('//t:numeric/@value', namespaces=NS), ['2'])
        self.assertEqual(self.root.xpath('//t:binary/@value', namespaces=NS), ['true'])

    def test_evening_heading_cannot_be_paired_with_untranslated_entrance(self):
        recipe = {'titles': {'he': 'בדיקה', 'en': 'Test'}, 'sequence': [
            {'kind': 'section', 'id': 'entrance', 'headings': {'he': 'כניסה'},
             'items': [{'kind': 'module', 'file': 'invented'}]},
            {'kind': 'section', 'id': 'service', 'headings': {'he': 'ערבית', 'en': 'Evening'},
             'items': []}]}
        wrapper, service = documentary_documents(recipe, self.units, 'en')
        self.assertFalse(wrapper.xpath('//t:body//t:head', namespaces=NS))
        self.assertEqual(service.xpath('//t:body//t:head/text()', namespaces=NS), ['Evening'])
        self.assertIn('/service@', wrapper.xpath('string(//j:transclude/@target)', namespaces=NS))
        recipe['sequence'].append({'kind': 'section'})
        with self.assertRaisesRegex(ValueError, 'entrance and service'):
            documentary_documents(recipe, self.units, 'en')

    def test_condition_label_is_inside_scope_and_empty_counterpart_is_absent(self):
        sequence = [{'kind': 'condition', 'id': 'optional', 'expressions': [],
                     'rubrics': {'he': {'text': 'When selected:', 'language': 'he'}},
                     'items': [{'kind': 'module', 'file': 'invented'}]}]
        self.render(sequence, lang='en')
        self.assertEqual(len(self.root), 0)
        self.render(sequence)
        self.assertEqual(self.root[0][0].tag, '{http://www.tei-c.org/ns/1.0}note')
        self.assertEqual(self.root[0][0].text, 'When selected:')

    def test_identical_facing_english_rubric_is_expanded_once(self):
        self.render([{'kind': 'note', 'rubric_kind': 'description', 'readings': {
            'he': {'text': 'Reader:', 'language': 'en', 'scan_page': 12},
            'en': {'text': 'Reader:', 'language': 'en', 'scan_page': 13}}}], expanded=True)
        self.assertEqual(len(self.root), 1)
        self.assertEqual(self.root[0].get('type'), 'description')

    def test_joint_role_keeps_its_abbreviation_and_expansion(self):
        self.render([{'kind': 'note', 'readings': {'he': {
            'text': 'קו״ח', 'language': 'he', 'role': 'reader_and_congregation',
            'expansion': 'קהל וחזן'}}}])
        self.assertTrue(self.root[0].get('corresp').endswith('/reader_and_congregation'))
        self.assertEqual(self.root.xpath('string(//t:abbr)', namespaces=NS), 'קו״ח')

