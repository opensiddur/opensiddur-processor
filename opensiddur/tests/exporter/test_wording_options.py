"""Named alternate wordings select at their actual declaration scope."""
import tempfile
import unittest
from pathlib import Path

from lxml import etree
import yaml

from opensiddur.common.xslt import xslt_transform_string
from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.inline_compiler import InlineCompilerProcessor
from opensiddur.exporter.linear import LinearData
from opensiddur.exporter.refdb import ReferenceDatabase
from opensiddur.exporter.settings import load_settings
from opensiddur.exporter.html.html import XSLT_FILE as HTML_XSLT
from opensiddur.exporter.html.css import xslt_parameters
from opensiddur.exporter.html.markers import prepare
from opensiddur.exporter.typography import TypographyConfig
from opensiddur.tests.exporter.stylesheet_helpers import transform

T = 'http://www.tei-c.org/ns/1.0'
J = 'http://jewishliturgy.org/ns/jlptei/2'
C = 'urn:x-opensiddur:condition:prayer:example/'
CHOICE = (f'<tei:choice><j:option corresp="{C}first">FIRSTTOKEN</j:option>'
          f'<j:option corresp="{C}second">SECONDTOKEN</j:option></tei:choice>')


def declaration(first, second, name='selection'):
    values = ''.join(f'<tei:f name="{C}{key}"><tei:binary value="{str(value).lower()}"/>'
                     '</tei:f>' for key, value in [('first', first), ('second', second)]
                     if value is not None)
    return f'<j:declare xml:id="{name}"><tei:fs type="opensiddur:variant">{values}</tei:fs></j:declare>'


class WordingOptionTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        (self.base/'x').mkdir()
        self.db = ReferenceDatabase(self.base/'reference.db')
        self.addCleanup(self.db.close)

    def compile(self, kind, body, *, initial=None, electronic=False, start='passage', end='passage'):
        xml = (f'<tei:TEI xmlns:tei="{T}" xmlns:j="{J}" xml:lang="en">'
               f'<tei:text><tei:body><tei:div xml:id="passage">{body}'
               '</tei:div></tei:body></tei:text></tei:TEI>')
        file = self.base/'x/test.xml'
        file.write_text(xml)
        data = LinearData(defer_reader_settings=electronic)
        data.xml_cache.base_path = self.base
        if initial is not None:
            settings = self.base/'settings.yaml'
            settings.write_text(yaml.safe_dump({'priority': {'transclusion': ['x']},
                'declarations': {'opensiddur:variant': initial}}))
            load_settings(settings, data, self.base)
        self.last_data = data
        if kind == 'base':
            result = CompilerProcessor('x', 'test.xml', linear_data=data, reference_database=self.db).process()
        else:
            cls = InlineCompilerProcessor if kind == 'inline' else ExternalCompilerProcessor
            result = cls('x', 'test.xml', f'//*[@xml:id="{start}"]', f'//*[@xml:id="{end}"]',
                         linear_data=data, reference_database=self.db).process()
        self.assertEqual(file.read_text(), xml)  # compilation cannot edit the witness
        if isinstance(result, list):
            root = etree.Element('result')
            root.extend(result)
            result = root
        return result

    def test_known_wording_is_selected_by_all_processors(self):
        for first, second, wanted, unwanted in [(True, False, 'FIRSTTOKEN', 'SECONDTOKEN'),
                                                 (False, True, 'SECONDTOKEN', 'FIRSTTOKEN')]:
            for kind in ['base', 'external', 'inline']:
                with self.subTest(kind=kind, first=first):
                    body = declaration(first, second)+'<tei:p>before '+CHOICE+' after</tei:p><j:endDeclare target="#selection"/>'
                    text = ''.join(self.compile(kind, body).itertext())
                    self.assertIn(wanted, text)
                    self.assertNotIn(unwanted, text)
                    self.assertIn('before', text)
                    self.assertIn('after', text)

    def test_scope_closes_without_changing_the_next_occurrence(self):
        body = ('<tei:p>'+CHOICE+'</tei:p>'+declaration(False, True)+
                '<tei:p>'+CHOICE+'</tei:p><j:endDeclare target="#selection"/><tei:p>'+CHOICE+'</tei:p>')
        initial = {C+'first': True, C+'second': False}
        for kind in ['base', 'external', 'inline']:
            with self.subTest(kind=kind):
                text = ''.join(self.compile(kind, body, initial=initial).itertext())
                self.assertEqual(text.count('FIRSTTOKEN'), 2)
                self.assertEqual(text.count('SECONDTOKEN'), 1)
                self.assertFalse(self.last_data.conditional_scope_stack)

    def test_unknown_options_keep_the_existing_display_and_inline_fallback(self):
        for choice in [CHOICE, CHOICE.replace(f' corresp="{C}first"', '').replace(f' corresp="{C}second"', '')]:
            for kind in ['base', 'external', 'inline']:
                with self.subTest(kind=kind, choice=choice):
                    text = ''.join(self.compile(kind, '<tei:p>'+choice+'</tei:p>').itertext())
                    self.assertIn('FIRSTTOKEN', text)
                    self.assertEqual('SECONDTOKEN' in text, kind != 'inline')

    def test_false_first_option_does_not_override_the_remaining_unknown_option(self):
        for kind in ['base', 'external', 'inline']:
            with self.subTest(kind=kind):
                body = declaration(False, None)+'<tei:p>'+CHOICE+'</tei:p><j:endDeclare target="#selection"/>'
                text = ''.join(self.compile(kind, body).itertext())
                self.assertNotIn('FIRSTTOKEN', text)
                self.assertIn('SECONDTOKEN', text)

    def test_contradictory_or_empty_selection_fails_and_restores_state(self):
        for first, second, message in [(True, True, 'More than one'), (False, False, 'No alternate')]:
            for kind in ['base', 'external', 'inline']:
                with self.subTest(kind=kind, first=first):
                    body = declaration(first, second)+'<tei:p>'+CHOICE+'</tei:p><j:endDeclare target="#selection"/>'
                    with self.assertRaisesRegex(ValueError, message):
                        self.compile(kind, body)
                    self.assertFalse(self.last_data.conditional_settings)
                    self.assertFalse(self.last_data.processing_context)

    def test_explicit_range_inside_an_option_still_addresses_that_option(self):
        choice = CHOICE.replace('FIRSTTOKEN', '<tei:seg xml:id="literal">FIRSTTOKEN</tei:seg>')
        body = declaration(False, True)+'<tei:p>'+choice+'</tei:p><j:endDeclare target="#selection"/>'
        for kind in ['external', 'inline']:
            with self.subTest(kind=kind):
                text = ''.join(self.compile(kind, body, start='literal', end='literal').itertext())
                self.assertIn('FIRSTTOKEN', text)
                self.assertNotIn('SECONDTOKEN', text)

    def test_out_of_range_choices_do_not_validate_unrelated_wordings(self):
        body = (declaration(True, True)+'<tei:p>'+CHOICE+'</tei:p>'
                '<j:endDeclare target="#selection"/><tei:p xml:id="literal">ONLYTOKEN</tei:p>')
        for kind in ['external', 'inline']:
            with self.subTest(kind=kind):
                text = ''.join(self.compile(kind, body, start='literal', end='literal').itertext())
                self.assertEqual(text.strip(), 'ONLYTOKEN')

    def test_electronic_local_declarations_select_but_reader_defaults_stay_open(self):
        initial = {C+'first': False, C+'second': True}
        text = ''.join(self.compile('base', '<tei:p>'+CHOICE+'</tei:p>', initial=initial, electronic=True).itertext())
        self.assertIn('FIRSTTOKEN', text)
        self.assertIn('SECONDTOKEN', text)
        body = declaration(False, True)+'<tei:p>'+CHOICE+'</tei:p><j:endDeclare target="#selection"/>'
        text = ''.join(self.compile('base', body, electronic=True).itertext())
        self.assertNotIn('FIRSTTOKEN', text)
        self.assertIn('SECONDTOKEN', text)

    def test_inline_selected_wording_keeps_divine_name_and_text_order(self):
        choice = CHOICE.replace('SECONDTOKEN', '<j:divineName xml:lang="he">יְיָ</j:divineName>')
        body = declaration(False, True)+'<tei:p>prefix '+choice+' suffix</tei:p><j:endDeclare target="#selection"/>'
        result = self.compile('inline', body)
        self.assertEqual(''.join(result.itertext()), 'prefix יְיָ suffix')
        names = result.findall('.//{'+J+'}divineName')
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0].get('{http://www.w3.org/XML/1998/namespace}lang'), 'he')
        self.assertFalse(result.findall('.//{'+T+'}p'))

    def test_inline_name_does_not_leak_outside_an_explicit_range(self):
        body = ('<tei:p><j:divineName>BEFORE</j:divineName>'
                '<tei:seg xml:id="literal">kept</tei:seg>'
                '<j:divineName>AFTER</j:divineName></tei:p>')
        result = self.compile('inline', body, start='literal', end='literal')
        self.assertEqual(''.join(result.itertext()), 'kept')
        self.assertFalse(result.findall('.//{'+J+'}divineName'))

    def test_pdf_and_html_emit_only_the_selected_wording(self):
        body = declaration(False, True)+'<tei:p>'+CHOICE+'</tei:p><j:endDeclare target="#selection"/>'
        compiled = self.compile('base', body)
        tex = transform(etree.tostring(compiled, encoding='unicode'))
        self.assertIn('SECONDTOKEN', tex)
        self.assertNotIn('FIRSTTOKEN', tex)
        prepare(compiled)
        html = etree.fromstring(xslt_transform_string(HTML_XSLT, etree.tostring(compiled, encoding='unicode'),
                               xslt_params=xslt_parameters(TypographyConfig())))
        text = ''.join(html.itertext())
        self.assertIn('SECONDTOKEN', text)
        self.assertNotIn('FIRSTTOKEN', text)
        self.assertFalse(html.xpath('//*[contains(concat(" ",@class," ")," option-alt ")]'))
