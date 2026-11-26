"""Reverse-check documentary streams without any edition-dependent fixtures."""
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from lxml import etree

from opensiddur.importer.scan import reverse


def xml(body):
    return etree.fromstring(('<TEI xmlns="http://www.tei-c.org/ns/1.0" '
        'xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="en">'
        '<teiHeader>not body</teiHeader><text><body>'+body+'</body></text>'
        '<standOff>not body either</standOff></TEI>').encode())


class ReverseTests(unittest.TestCase):
    def test_language_boundaries_notes_and_printed_choices(self):
        root=xml('<p>before scan</p><pb facs="https://example/page/n2.jpg"/>'
                 '<p>one <choice><abbr>short</abbr><expan>editorial expansion</expan></choice>'
                 ' two<note>note <foreign xml:lang="he">אב</foreign> end</note>'
                 ' three <foreign xml:lang="he">גד</foreign> four</p>'
                 '<pb facs="https://example/page/n4_medium.jpg"/><p>next</p>')
        root[1][0].insert(2,etree.Comment('not text'))
        self.assertEqual(reverse.streams(root),{('s3','en'):'one short two three four',
                                               ('s3','he'):'גד',('s5','en'):'next'})
        with_notes=reverse.streams(root,include_notes=True)
        self.assertEqual(with_notes[('s3','en')],'one short two note end three four')
        self.assertEqual(with_notes[('s3','he')],'אב גד')
        self.assertNotIn('editorial',str(with_notes))

    def test_missing_facs_and_service_transclusions_are_rejected(self):
        for body in ['<pb n="1"/>','<j:transclude target="urn:test:text"/>']:
            with self.subTest(body=body),self.assertRaises(ValueError):reverse.streams(xml(body))

    def test_compare_whitespace_differences_and_coverage_mismatch(self):
        expected={('s1','he'):'אב גד'}
        self.assertEqual(reverse.check({('s1','he'):'אב\n גד'},expected),{})
        diffs=reverse.check({('s1','he'):'אב הו'},expected)
        self.assertIn('-גד',diffs[('s1','he')]);self.assertIn('+הו',diffs[('s1','he')])
        with self.assertRaisesRegex(ValueError,'coverage differs'):reverse.check({},expected)

    def test_cli_merges_files_in_source_order_and_returns_difference_status(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);files=[]
            for i,text in enumerate(['first','second']):
                p=root/f'{i}.xml';p.write_bytes(etree.tostring(xml('<pb facs="https://example/n0.jpg"/><p>'+text+'</p>')));files.append(str(p))
            readings=root/'readings.json';readings.write_text(json.dumps({'s1':{'en':'first second'}}))
            with redirect_stdout(io.StringIO()) as log:
                self.assertFalse(reverse.main(files+['--readings',str(readings)]))
            self.assertIn('1 source-page/language streams checked; 0 differ',log.getvalue())
            readings.write_text(json.dumps({'s1':{'en':'wrong'}}))
            with redirect_stdout(io.StringIO()):
                self.assertTrue(reverse.main(files+['--readings',str(readings),'--include-notes']))
