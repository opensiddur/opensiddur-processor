import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.inline_compiler import InlineCompilerProcessor
from opensiddur.exporter.linear import LinearData
from opensiddur.exporter.settings import SettingsYaml
from opensiddur.tests.exporter.stylesheet_helpers import transform

TEI='http://www.tei-c.org/ns/1.0'
class AbbreviationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        project = self.root/'x'
        project.mkdir()
        (project/'test.xml').write_text(f'''<tei:TEI xmlns:tei="{TEI}" xml:lang="en">
<tei:text><tei:body><tei:div xml:id="passage"><tei:p>Before
<tei:choice><tei:abbr>cue</tei:abbr><tei:expan>expanded wording</tei:expan></tei:choice>
after.</tei:p></tei:div></tei:body></tei:text></tei:TEI>''')
    def data(self,form):
        data=LinearData(abbreviation_reading=form);data.xml_cache.base_path=self.root;return data
    def test_settings_default_and_invalid_form(self):
        self.assertEqual('abbreviated',SettingsYaml(priority={}).readings.abbreviations)
        with self.assertRaises(ValueError):SettingsYaml(priority={},readings={'abbreviations':'both'})
    def test_all_processors_select_one_form(self):
        for form,wanted,unwanted in [('abbreviated','cue','expanded wording'),('expanded','expanded wording','cue')]:
            for kind in ['base','external','inline']:
                with self.subTest(form=form,kind=kind):
                    data=self.data(form)
                    if kind=='base':result=CompilerProcessor('x','test.xml',linear_data=data).process()
                    elif kind=='inline':result=InlineCompilerProcessor('x','test.xml','//*[@xml:id="passage"]','//*[@xml:id="passage"]',linear_data=data).process()
                    else:result=ExternalCompilerProcessor('x','test.xml',linear_data=data).process()[0]
                    text=''.join(result.itertext());self.assertEqual(1,text.count(wanted));self.assertNotIn(unwanted,text)
                    self.assertIn('Before',text);self.assertIn('after.',text)
    def test_pdf_stylesheet_emits_the_selected_form(self):
        for form in ['abbreviated','expanded']:
            compiled=CompilerProcessor('x','test.xml',linear_data=self.data(form)).process()
            tex=transform(etree.tostring(compiled,encoding='unicode'))
            self.assertIn('cue' if form=='abbreviated' else 'expanded wording',tex)
            self.assertNotIn('expanded wording' if form=='abbreviated' else 'cue',tex)
    def test_kri_ktiv_unchanged(self):
        root=etree.fromstring(f'<choice xmlns="{TEI}" xmlns:j="http://jewishliturgy.org/ns/jlptei/2"><j:read>read</j:read><j:written>written</j:written></choice>')
        p=CompilerProcessor('x','test.xml',linear_data=self.data('expanded'))
        self.assertEqual(2,len(list(p._reading_children(root))))
