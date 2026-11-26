"""Importer boundaries must resolve without swallowing unaddressed material."""
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.exporter.inline_compiler import InlineCompilerProcessor
from opensiddur.exporter.linear import LinearData
from opensiddur.exporter.refdb import ReferenceDatabase, find_end_of_mapping
from opensiddur.importer.birnbaum_scan.build.milestones import Correspondences, marked

BIBLE = 'urn:x-opensiddur:text:bible:psalms/1/'
PRAYER = 'urn:x-opensiddur:text:siddur:test/'


def resolve(tmp_path, body, urn):
    project = tmp_path / 'test'
    project.mkdir(exist_ok=True)
    path = project / 'test.xml'
    path.write_text('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">'
                    '<tei:text><tei:body>' + body + '</tei:body></tei:text></tei:TEI>')
    tree = etree.parse(str(path))
    node = tree.xpath('//*[@corresp=$urn]', urn=urn)[0]
    end, tail = find_end_of_mapping(node)
    data = LinearData()
    data.xml_cache.base_path = tmp_path
    with ReferenceDatabase(tmp_path / 'refs.db') as db:
        result = InlineCompilerProcessor(
            'test', 'test.xml', tree.getpath(node), end,
            include_tail_after_end=tail, linear_data=data,
            reference_database=db).process()
    return ' '.join(''.join(result.itertext()).split())


class TestMilestoneRanges(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp_path = Path(directory.name)

    def test_consecutive_verses_cross_paragraphs_without_absorbing_following_text(self):
        marks = Correspondences()
        body = ('<tei:p>' + marks.start(BIBLE + '1') + 'First.</tei:p><tei:p>'
                + marks.start(BIBLE + '2') + 'Second.' + marks.close()
                + 'Outside.</tei:p>')
        self.assertEqual(resolve(self.tmp_path, body, BIBLE + '1'), 'First.')
        self.assertEqual(resolve(self.tmp_path, body, BIBLE + '2'), 'Second.')


    def test_mixed_units_and_source_only_repeat_are_bounded(self):
        marks = Correspondences()
        body = ('<tei:p>' + marks.start(BIBLE + '1') + 'Verse.'
                + marks.start(PRAYER + 'part') + 'Prayer.' + marks.close()
                + '<tei:seg source="' + BIBLE + '1">Repeated.</tei:seg>'
                + 'Rubric.' + marks.start(BIBLE + '2') + 'Next.'
                + marks.close() + '</tei:p>')
        self.assertEqual(resolve(self.tmp_path, body, BIBLE + '1'), 'Verse.')
        self.assertEqual(resolve(self.tmp_path, body, PRAYER + 'part'), 'Prayer.')
        self.assertEqual(resolve(self.tmp_path, body, BIBLE + '2'), 'Next.')


    def test_bounded_passage_preserves_nested_markup_and_tail(self):
        body = '<tei:p>' + marked(PRAYER + 'part',
            'Before <tei:seg>inside</tei:seg> after.') + 'Outside.</tei:p>'
        self.assertEqual(resolve(self.tmp_path, body, PRAYER + 'part'), 'Before inside after.')


    def test_instruction_at_range_end_does_not_swallow_following_prayers(self):
        marks = Correspondences()
        body = ('<tei:p>' + marks.start(PRAYER + 'first') + 'Call '
                + '<tei:note type="instruction">name the reader</tei:note>.'
                + marks.start(PRAYER + 'second') + 'Following prayer.'
                + marks.close() + '</tei:p>')
        result = resolve(self.tmp_path, body, PRAYER + 'first')
        self.assertIn('Call', result)
        self.assertIn('name the reader', result)
        self.assertTrue(result.endswith('.'))
        self.assertNotIn('Following prayer', result)
