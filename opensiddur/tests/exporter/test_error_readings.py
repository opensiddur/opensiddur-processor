"""readings.errors chooses between an edition's misprint (tei:sic) and its correction (tei:corr)."""
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.inline_compiler import InlineCompilerProcessor
from opensiddur.exporter.linear import LinearData
from opensiddur.exporter.settings import SettingsYaml
from opensiddur.importer.scan import reverse
from opensiddur.tests.exporter.stylesheet_helpers import transform

TEI = 'http://www.tei-c.org/ns/1.0'


class ErrorReadingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        project = self.root / 'x'
        project.mkdir()
        (project / 'test.xml').write_text(f'''<tei:TEI xmlns:tei="{TEI}" xml:lang="en">
<tei:text><tei:body><tei:div xml:id="passage"><tei:p>Before
<tei:choice><tei:sic>oppessors</tei:sic><tei:corr>oppressors</tei:corr></tei:choice>
and <tei:choice><tei:abbr>(When, <tei:choice><tei:sic>&amp;c.</tei:sic><tei:corr>&amp;c.)</tei:corr></tei:choice></tei:abbr><tei:expan>When we call.</tei:expan></tei:choice>
after.</tei:p></tei:div></tei:body></tei:text></tei:TEI>''')

    def data(self, errors, abbreviations='abbreviated'):
        data = LinearData(error_reading=errors, abbreviation_reading=abbreviations)
        data.xml_cache.base_path = self.root
        return data

    def compile(self, kind, data):
        if kind == 'base':
            return CompilerProcessor('x', 'test.xml', linear_data=data).process()
        if kind == 'inline':
            return InlineCompilerProcessor('x', 'test.xml', '//*[@xml:id="passage"]', '//*[@xml:id="passage"]',
                                           linear_data=data).process()
        return ExternalCompilerProcessor('x', 'test.xml', linear_data=data).process()[0]

    def test_settings_default_to_the_correction_and_refuse_other_forms(self):
        self.assertEqual('corrected', SettingsYaml(priority={}).readings.errors)
        self.assertEqual('printed', SettingsYaml(priority={}, readings={'errors': 'printed'}).readings.errors)
        with self.assertRaises(ValueError):
            SettingsYaml(priority={}, readings={'errors': 'both'})

    def test_all_processors_select_one_form(self):
        for errors, wanted, unwanted in [('corrected', 'oppressors', 'oppessors'), ('printed', 'oppessors', 'oppressors')]:
            for kind in ['base', 'external', 'inline']:
                with self.subTest(errors=errors, kind=kind):
                    text = ''.join(self.compile(kind, self.data(errors)).itertext())
                    self.assertEqual(1, text.count(wanted))
                    self.assertNotIn(unwanted, text)
                    self.assertIn('Before', text)
                    self.assertIn('after.', text)

    def test_a_misprint_inside_an_abbreviation_is_read_with_it(self):
        for errors, cue in [('corrected', '(When, &c.)'), ('printed', '(When, &c.\n')]:
            with self.subTest(errors=errors):
                text = ''.join(self.compile('base', self.data(errors)).itertext())
                self.assertIn(cue, text)
        expanded = ''.join(self.compile('base', self.data('printed', 'expanded')).itertext())
        self.assertIn('When we call.', expanded)
        self.assertNotIn('&c.', expanded)

    def test_pdf_stylesheet_emits_the_selected_form(self):
        for errors, wanted, unwanted in [('corrected', 'oppressors', 'oppessors'), ('printed', 'oppessors', 'oppressors')]:
            with self.subTest(errors=errors):
                compiled = self.compile('base', self.data(errors))
                tex = transform(etree.tostring(compiled, encoding='unicode'))
                self.assertIn(wanted, tex)
                self.assertNotIn(unwanted, tex)

    def test_pdf_stylesheet_reads_an_uncompiled_choice_corrected(self):
        tex = transform((self.root / 'x' / 'test.xml').read_text())
        self.assertIn('oppressors', tex)
        self.assertNotIn('oppessors', tex)

    def test_the_reverse_check_reads_what_was_printed(self):
        root = etree.fromstring(f'''<TEI xmlns="{TEI}" xml:lang="en"><text><body>
<pb facs="https://example/page/n2.jpg"/><p>the <choice><sic>oppessors</sic><corr>oppressors</corr></choice> fled</p>
</body></text></TEI>''')
        self.assertEqual({('s3', 'en'): 'the oppessors fled'}, reverse.streams(root))

if __name__ == '__main__':
    unittest.main()
