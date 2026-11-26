"""Omitting optional words or verses must not leave typographic gaps."""
import re
import unittest
import tempfile
from pathlib import Path
from lxml import etree

from opensiddur.exporter.compiler import CompilerProcessor, close_up_whitespace
from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.inline_compiler import InlineCompilerProcessor
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.exporter.refdb import ReferenceDatabase
from opensiddur.exporter.html.markers import prepare
from opensiddur.tests.exporter.stylesheet_helpers import transform

T = "http://www.tei-c.org/ns/1.0"
J = "http://jewishliturgy.org/ns/jlptei/2"
P = "http://jewishliturgy.org/ns/processing"
NS = {"t": T, "j": J}


class OptionalPoetryLayoutTests(unittest.TestCase):
    def tex_body(self, lines):
        root = f'''<tei:TEI xmlns:tei="{T}" xmlns:p="{P}" xml:lang="en">
          <tei:text><tei:body><tei:lg>{lines}</tei:lg></tei:body></tei:text>
        </tei:TEI>'''
        return transform(root).split(r"\begin{document}", 1)[1]

    def test_removed_verses_do_not_add_line_breaks(self):
        body = self.tex_body('''<tei:l>first</tei:l><tei:l>
          <tei:milestone unit="stanza" corresp="urn:x-opensiddur:text:poem:example/2"/>
          </tei:l><tei:l> </tei:l><tei:l>last</tei:l>''')
        self.assertEqual(body.count(r"\leavevmode\\{}"), 1)
        self.assertIn("first", body)
        self.assertIn("last", body)

    def test_silent_container_keeps_page_label(self):
        body = self.tex_body('''<tei:l>first</tei:l><tei:l>
          <tei:anchor type="page-label" n="source_page_2"/>
          </tei:l><tei:l>last</tei:l>''')
        self.assertIn(r"\label{source_page_2}", body)
        self.assertEqual(body.count(r"\leavevmode\\{}"), 1)

    def test_final_split_fragment_still_closes_its_line(self):
        body = self.tex_body('''<tei:l p:part="first">first</tei:l>
          <tei:l p:part="last"><tei:milestone unit="stanza"/></tei:l>
          <tei:l>last</tei:l>''')
        self.assertEqual(body.count(r"\leavevmode\\{}"), 1)

    def test_explicit_blank_line_is_retained(self):
        body = self.tex_body('''<tei:l>first</tei:l>
          <tei:l><tei:lb/></tei:l><tei:l>last</tei:l>''')
        self.assertGreater(body.count(r"\leavevmode\\{}"), 1)

    def test_unrelated_documentary_punctuation_spacing_is_retained(self):
        for language, text in [("en", "Lord ; and . . . then"),
                               ("fr", "mot : suite"), ("en", "word\u00a0: next")]:
            with self.subTest(language=language):
                root = etree.fromstring(f'<p xmlns="{T}" xml:lang="{language}">{text}</p>')
                close_up_whitespace(root)
                self.assertEqual(root.text, text)

    def test_rubric_and_marked_scope_lines_keep_their_breaks(self):
        for marker in [
                '<tei:note type="instruction">Rubric</tei:note>',
                '<j:conditional xmlns:j="'+J+'" xml:id="x" type="marked"/>',
                '<j:endConditional xmlns:j="'+J+'" target="#x"/>']:
            with self.subTest(marker=marker):
                body = self.tex_body('<tei:l>first</tei:l><tei:l>'+marker+
                                     '</tei:l><tei:l>last</tei:l>')
                if 'Rubric' in marker:
                    self.assertIn(r"\instructionnote", body)
                    self.assertLess(body.index('Rubric'), body.index(r"\leavevmode"))
                else:
                    self.assertEqual(body.count(r"\leavevmode\\{}"), 2)

    def marked_insert(self, language="en", after=":"):
        return etree.fromstring(f'''<t:p xmlns:t="{T}" xmlns:j="{J}" xml:lang="{language}">
          word <j:conditional xml:id="optional" type="marked">
          <j:all><t:fs type="opensiddur:rite"><t:f name="ashkenaz">
          <t:binary value="true"/></t:f></t:fs></j:all></j:conditional>insert<j:endConditional target="#optional"/>{after}</t:p>''')

    def test_electronic_separator_shares_condition_but_stays_outside_brackets(self):
        root = self.marked_insert()
        book = prepare(root)
        starts = root.findall(f"{{{J}}}conditional")
        self.assertEqual(len(starts), 2)
        self.assertIsNone(starts[0].get("type"))
        self.assertEqual(starts[1].get("type"), "marked")
        self.assertEqual(book.scopes[0], book.scopes[1])
        self.assertEqual(book.features[0].scopes, 1)
        spaces = root.xpath('.//t:seg[@p:scopes]', namespaces={**NS, 'p': P})
        self.assertEqual(len(spaces), 1)
        self.assertEqual(spaces[0].text, ' ')
        self.assertFalse((root.text or "").endswith(" "))
        self.assertEqual("".join(root.itertext()).count("word"), 1)

    def test_no_extra_scope_for_normal_separator_or_french_colon(self):
        for root in [self.marked_insert(after=" next"), self.marked_insert(language="fr")]:
            with self.subTest(xml=etree.tostring(root)):
                book = prepare(root)
                self.assertEqual(len(book.scopes), 1)


class OptionalInsertCompilationTests(unittest.TestCase):
    def test_omission_junction_only_in_all_three_compilers(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "synthetic").mkdir()
            database = ReferenceDatabase(base / "references.db")
            self.addCleanup(database.close)
            for processor in (CompilerProcessor, ExternalCompilerProcessor, InlineCompilerProcessor):
                for value in (False, True, None):
                    for before, after, language, omitted in [
                            ("word ", ": next", "en", "word: next"),
                            ("word\n   ", ": next", "en", "word: next"),
                            ("word ", " ; next", "en", "word ; next"),
                            ("word ", ". . . next", "en", "word . . . next"),
                            ("mot ", ": suite", "fr", "mot : suite"),
                            ("word\u00a0", ": next", "en", "word\u00a0: next")]:
                        with self.subTest(processor=processor.__name__, value=value,
                                          before=before, after=after, language=language):
                            reset_linear_data()
                            data = get_linear_data()
                            data.xml_cache.base_path = base
                            declared = "" if value is None else (
                                '<j:declare xml:id="d"><t:fs type="opensiddur:rite">'
                                '<t:f name="ashkenaz"><t:binary value="'+str(value).lower()+
                                '"/></t:f></t:fs></j:declare>')
                            finish = '' if value is None else '<j:endDeclare target="#d"/>'
                            xml = f'<t:p xmlns:t="{T}" xmlns:j="{J}" xml:lang="{language}">'+declared+before+(
                                '<j:conditional xml:id="c" type="marked"><t:fs type="opensiddur:rite">'
                                '<t:f name="ashkenaz"><t:binary value="true"/></t:f></t:fs>'
                                '</j:conditional>insert<j:endConditional target="#c"/>')+after+finish+'</t:p>'
                            (base / "synthetic" / "text.xml").write_text(xml)
                            kwargs = {"from_start": None, "to_end": None} if processor is InlineCompilerProcessor else {}
                            result = processor("synthetic", "text.xml", reference_database=database,
                                               **kwargs).process()
                            roots = result if isinstance(result, list) else [result]
                            for root in roots:
                                close_up_whitespace(root)
                            text = ''.join(''.join(root.itertext()) for root in roots)
                            text = text.replace('\n', ' ')
                            # Normalise only the soft source line-wrap for comparison.
                            text = re.sub(r'[ \t]+', ' ', text)
                            if value is False:
                                self.assertEqual(text, omitted)
                            else:
                                self.assertIn('insert'+after, text)
                                self.assertIn(before.replace('\u00a0', ' ').rstrip(' \n')+' ', text.replace('\u00a0', ' '))
                            self.assertEqual(data.conditional_scope_stack, [])
