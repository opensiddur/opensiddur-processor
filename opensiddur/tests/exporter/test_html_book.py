"""The electronic book: html.xslt's rendering, and html.py's assembly of the page."""

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tzfpy
from lxml import etree
from pydantic import ValidationError

from opensiddur.common.xslt import xslt_transform_string
from opensiddur.exporter.constants import JLPTEI_NAMESPACE, PROCESSING_NAMESPACE, TEI_NS
from opensiddur.exporter.cli_common import SettingsError
from opensiddur.exporter.html.css import typography_css, xslt_parameters
from opensiddur.exporter.client_settings import is_reader_supplied
from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.derived_settings import STATIC_DEFAULTS
from opensiddur.exporter.html.html import (
    XSLT_FILE,
    always_basic,
    basic_controls,
    build_book,
    celebrated_purim,
    columns,
    feature_words,
    read_basic_settings,
    read_places,
    settings_catalogue,
    scope_css,
)
from opensiddur.exporter.html.markers import BookConditions, Feature, prepare
from opensiddur.exporter.settings import ElectronicSettings, SettingsYaml
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.exporter.page_references import resolve_page_references
from opensiddur.exporter import typography as typography_module
from opensiddur.exporter.typography import TypographyConfig
from opensiddur.tests.exporter.js_engine import require_node, run_js
from opensiddur.tests.exporter.registry_helpers import unchecked_registry

J = JLPTEI_NAMESPACE
P = PROCESSING_NAMESPACE
H = "http://www.w3.org/1999/xhtml"
NS = {"h": H}


def _cond(xml_id: str, name: str, value: str = "true", rubric: str = "",
          fs: str = "opensiddur:override", marked: bool = False) -> str:
    note = f'<tei:note type="instruction">{rubric}</tei:note>' if rubric else ""
    kind = ' type="marked"' if marked else ""
    return (f'<j:conditional xml:id="{xml_id}"{kind}>{note}<tei:fs type="{fs}"><tei:f name="{name}">'
            f'<tei:binary value="{value}"/></tei:f></tei:fs></j:conditional>')


def _compiled(body: str, *, electronic: bool = True, lang: str = "en", credits: str = "") -> bytes:
    destination = ' p:destination="electronic"' if electronic else ""
    return f'''<tei:TEI xmlns:tei="{TEI_NS}" xmlns:j="{J}" xmlns:p="{P}" xml:lang="{lang}"
    p:project="proj" p:file_name="index.xml"{destination}>
  <tei:teiHeader><tei:fileDesc><tei:titleStmt><tei:title>Header Title</tei:title>{credits}
  </tei:titleStmt></tei:fileDesc></tei:teiHeader>
  <tei:text><tei:body>{body}</tei:body></tei:text>
</tei:TEI>'''.encode()


def _render(body: str, **params) -> etree.ElementBase:
    root = etree.fromstring(_compiled(body))
    resolve_page_references(root, every_occurrence=True)
    prepare(root)
    return etree.fromstring(xslt_transform_string(
        XSLT_FILE, etree.tostring(root, encoding="unicode"),
        xslt_params={**xslt_parameters(TypographyConfig()), **params}))


def _classes(element) -> list[str]:
    return (element.get("class") or "").split()


class TestConditionalRendering(unittest.TestCase):

    def test_liturgical_psalm_owns_title_and_suppresses_repeated_chapter_numbers(self):
        main=_render('''<tei:div type="psalm" n="23">
            <tei:head xml:lang="he">תהלים כג</tei:head><tei:head xml:lang="en">Psalm 23</tei:head>
            <tei:div type="book"><tei:head corresp="urn:fixture:psalm-title">PSALMS<tei:anchor corresp="urn:fixture:title-child"/></tei:head>
            <tei:p><tei:milestone unit="chapter" n="23" corresp="urn:fixture:chapter"/>
            <tei:milestone unit="verse" n="1"/>Prayer text</tei:p></tei:div></tei:div>''')
        self.assertEqual(main.xpath('//h:h2/text()',namespaces=NS),['תהלים כג','Psalm 23'])
        self.assertFalse(main.xpath('//*[contains(concat(" ",@class," ")," ch ")]',namespaces=NS))
        self.assertTrue(main.xpath('//*[@id="urn:fixture:chapter"]'))
        self.assertTrue(main.xpath('//*[@id="urn:fixture:psalm-title"]'))
        self.assertTrue(main.xpath('//*[@id="urn:fixture:title-child"]'))
        self.assertIn('Prayer text',''.join(main.itertext()))
        self.assertTrue(main.xpath('//h:span[@class="v"][text()="1"]',namespaces=NS))

    def test_bible_chapter_number_remains_outside_a_liturgical_psalm(self):
        main=_render('''<tei:div type="book"><tei:p>
            <tei:milestone unit="chapter" n="23"/>Bible text</tei:p></tei:div>''')
        self.assertEqual(main.xpath('//h:span[@class="ch"]/text()',namespaces=NS),['23'])

    def test_psalm_display_title_keeps_nested_heading_anchors(self):
        main=_render('''<tei:head xml:lang="he" p:psalm-title="תהלים קטו">תהלים 115
            <tei:anchor corresp="urn:fixture:psalm-heading"/></tei:head>''')
        self.assertEqual(main.xpath('//h:h2/text()',namespaces=NS),['תהלים קטו'])
        self.assertTrue(main.xpath('//*[@id="urn:fixture:psalm-heading"]'))

    def test_block_scope(self):
        main = _render(_cond("a", "wedding", rubric="At a wedding:")
                       + "<tei:p>verse</tei:p><j:endConditional target=\"#a\"/>")
        opener, governed, closer = main.xpath("//h:section[@class='body']/*", namespaces=NS)
        self.assertEqual(opener.tag, f"{{{H}}}div")
        self.assertEqual(_classes(opener), ["cm", "cm-open", "m0", "cm-block"])
        self.assertEqual(opener.xpath("string(h:span[@class='rubric'])", namespaces=NS),
                         "At a wedding:")
        self.assertEqual(governed.tag, f"{{{H}}}p")
        self.assertEqual(_classes(governed), ["c0"])
        self.assertEqual(_classes(closer), ["cm", "cm-close", "m0", "cm-block"])
        self.assertEqual(closer.xpath("string(h:span[@class='cm-br'])", namespaces=NS), "")

    def test_inline_scope_is_bracketed(self):
        """A scope the book itself brackets keeps its brackets."""
        main = _render("<tei:p>before " + _cond("a", "wedding", marked=True)
                       + "inside<j:endConditional target=\"#a\"/> after</tei:p>")
        paragraph = main.find(f".//{{{H}}}p")
        opener, words, closer = paragraph
        self.assertEqual(opener.tag, f"{{{H}}}span")
        self.assertEqual(_classes(opener),
                         ["cm", "cm-open", "m0", "cm-inline", "cm-norubric", "cm-marked"])
        self.assertEqual(_classes(closer), ["cm", "cm-close", "m0", "cm-inline", "cm-marked"])
        self.assertEqual(opener.findtext(f"{{{H}}}span"), "[")
        self.assertEqual((words.text, _classes(words)), ("inside", ["c0"]))
        self.assertEqual(closer.findtext(f"{{{H}}}span"), "]")
        self.assertEqual("".join(paragraph.itertext()), "before [inside] after")

    def test_brackets_follow_the_settings(self):
        main = _render("<tei:p>" + _cond("a", "wedding", marked=True) + "x<j:endConditional target=\"#a\"/></tei:p>",
                       **{"inline-open": "⟨", "inline-close": "⟩"})
        self.assertEqual("".join(main.find(f".//{{{H}}}p").itertext()), "⟨x⟩")

    def test_block_brackets_instead_of_a_rule(self):
        main = _render(_cond("a", "wedding", marked=True) + "<tei:p>x</tei:p><j:endConditional target=\"#a\"/>",
                       block="brackets")
        closer = main.xpath("//h:div[contains(@class, 'cm-close')]", namespaces=NS)[0]
        self.assertEqual("".join(closer.itertext()), "]")

    def test_an_unmarked_scope_with_no_rubric_is_silent(self):
        """A direction to the device, such as an occasion's gate: what it governs is shown or
        hidden, with nothing around it."""
        main = _render(_cond("a", "wedding") + "<tei:p>x</tei:p><j:endConditional target=\"#a\"/>")
        markers = main.xpath("//*[contains(@class, 'cm ')]", namespaces=NS)
        self.assertEqual([("cm-silent" in _classes(m)) for m in markers], [True, True])
        self.assertEqual(_classes(main.xpath("//h:p", namespaces=NS)[0]), ["c0"])

    def test_a_marked_scope_with_a_rubric_keeps_its_rule(self):
        main = _render(_cond("a", "wedding", rubric="At a wedding:", marked=True)
                       + "<tei:p>verse</tei:p><j:endConditional target=\"#a\"/>")
        opener = main.xpath("//h:section[@class='body']/*", namespaces=NS)[0]
        self.assertEqual(_classes(opener), ["cm", "cm-open", "m0", "cm-block", "cm-marked"])

    def test_silent_scopes_are_marked(self):
        main = _render('<tei:div>' + _cond("a", "wedding")
                       + '<tei:milestone unit="aliyah.annual" n="first"/>'
                       + '<j:endConditional target="#a"/><tei:p>x</tei:p></tei:div>')
        markers = main.xpath("//*[contains(@class, 'cm ')]", namespaces=NS)
        self.assertEqual([("cm-silent" in _classes(m)) for m in markers], [True, True])
        self.assertEqual(_classes(main.xpath("//h:span[@class='aliyah c0']", namespaces=NS)[0]),
                         ["aliyah", "c0"])

    def test_conditions_are_not_text(self):
        main = _render(_cond("a", "wedding") + "<tei:p>x</tei:p><j:endConditional target=\"#a\"/>")
        self.assertNotIn("wedding", etree.tostring(main, encoding="unicode").replace('class="', ""))


class TestStructure(unittest.TestCase):

    def test_heading_levels(self):
        main = _render('<tei:div><tei:head p:heading-level="3">Three</tei:head></tei:div>'
                       '<tei:div><tei:head p:heading-level="9">Deep</tei:head></tei:div>'
                       '<tei:div><tei:head>Plain</tei:head></tei:div>')
        self.assertEqual([h.tag.split("}")[1] for h in main.iter(f"{{{H}}}h3", f"{{{H}}}h6",
                                                                  f"{{{H}}}h2")],
                         ["h3", "h6", "h2"])

    def test_only_the_first_copy_of_a_urn_is_its_id(self):
        main = _render('<tei:div corresp="urn:x:a"><tei:p>one</tei:p></tei:div>'
                       '<tei:div corresp="urn:x:a"><tei:p>two</tei:p></tei:div>')
        self.assertEqual(len(main.xpath("//*[@id='urn:x:a']")), 1)
        self.assertEqual(main.xpath("string(//*[@id='urn:x:a'])"), "one")

    def test_parallel_columns(self):
        main = _render('<p:parallel column-order="primary_first">'
                       '<p:parallelItem role="primary" xml:lang="he"><tei:p>א</tei:p></p:parallelItem>'
                       '<p:parallelItem role="parallel" xml:lang="en"><tei:p>a</tei:p></p:parallelItem>'
                       '</p:parallel>')
        row = main.xpath("//h:div[contains(@class, 'par')]", namespaces=NS)[0]
        self.assertEqual(_classes(row), ["par", "par-primary_first"])
        primary, parallel = row
        self.assertEqual((primary.get("lang"), primary.get("dir")), ("he", "rtl"))
        self.assertEqual((parallel.get("lang"), parallel.get("dir")), ("en", "ltr"))
        self.assertEqual(_classes(primary), ["col", "col-primary"])

    def test_a_column_with_no_words_is_marked(self):
        main = _render('<p:parallel column-order="primary_first">'
                       '<p:parallelItem role="primary" xml:lang="he"><tei:p>א</tei:p></p:parallelItem>'
                       '<p:parallelItem role="parallel" xml:lang="en"><tei:pb n="3"/></p:parallelItem>'
                       '</p:parallel>')
        primary, parallel = main.xpath("//h:div[contains(@class, 'par')]", namespaces=NS)[0]
        self.assertEqual(_classes(primary), ["col", "col-primary"])
        self.assertEqual(_classes(parallel), ["col", "col-parallel", "col-empty"])

    def test_notes_open_from_numbered_marks(self):
        main = _render('<tei:p>a<tei:note type="commentary">first</tei:note> b'
                       '<tei:note>second</tei:note></tei:p>')
        buttons = main.xpath("//h:button", namespaces=NS)
        self.assertEqual([b.text for b in buttons], ["1", "2"])
        for button in buttons:
            target = main.xpath(f"//*[@id='{button.get('popovertarget')}']")[0]
            self.assertIn("popover", target.attrib)
        self.assertIn("note-commentary", main.xpath("string(//*[@id='note-1']/@class)"))

    def test_verse_numbers(self):
        main = _render('<tei:p><tei:milestone unit="verse" n="3" corresp="urn:x:v3"/>words</tei:p>')
        verse = main.xpath("//h:span[@class='v']", namespaces=NS)[0]
        self.assertEqual((verse.text, verse.get("id")), ("3", "urn:x:v3"))

    def test_alternatives(self):
        main = _render('<tei:p><tei:choice><j:option>one</j:option><j:option>two</j:option>'
                       '</tei:choice></tei:p>')
        self.assertEqual(
            [(o.text, _classes(o)) for o in main.xpath("//h:span[contains(@class, 'option')]", namespaces=NS)],
            [("one", ["option"]), ("two", ["option", "option-alt"])])

    def test_reading_forms_carry_their_role_classes(self):
        """css.py styles each form by these classes (styles.abbreviation and the rest)."""
        main = _render('<tei:p><tei:choice><tei:expan>expanded</tei:expan></tei:choice>'
                       '<tei:choice><tei:sic>printed</tei:sic></tei:choice>'
                       '<tei:choice><tei:abbr>abbr.</tei:abbr></tei:choice>'
                       '<tei:choice><tei:corr>corrected</tei:corr></tei:choice></tei:p>')
        for name, text in (("expan", "expanded"), ("sic", "printed"), ("abbr", "abbr."),
                           ("corr", "corrected")):
            with self.subTest(name=name):
                self.assertEqual(
                    main.xpath(f"string(//h:span[@class='{name}'])", namespaces=NS), text)

    def test_a_link_carries_the_reference_class(self):
        main = _render('<tei:p><tei:ref target="https://example.org/">a link</tei:ref></tei:p>')
        link = main.xpath("//h:a[@href='https://example.org/']", namespaces=NS)[0]
        self.assertEqual(_classes(link), ["ref"])

    def test_unknown_elements_keep_their_words(self):
        main = _render('<tei:p><tei:unknownThing>kept</tei:unknownThing></tei:p>')
        self.assertEqual(main.xpath("string(//h:span[@class='tei-unknownThing'])", namespaces=NS),
                         "kept")


URN = "urn:x-opensiddur:text:prayer:grace"
PAGE_REF = f'<tei:ref type="page" target="{URN}@proj"/>'


# Its feature names are made up for the test.
@unchecked_registry()
class TestPageReferences(unittest.TestCase):
    """Where print gives a page number, the electronic book links to the passage."""

    def test_reference_links_to_an_anchor_in_its_destination(self):
        main = _render(f'<tei:p>Grace continues on page {PAGE_REF}.</tei:p>'
                       f'<tei:div corresp="{URN}"><tei:p>Blessed</tei:p></tei:div>')
        link, = main.xpath("//h:a", namespaces=NS)
        self.assertEqual(_classes(link), ["page-ref"])
        self.assertEqual(link.text, "→")
        self.assertEqual(link.get("aria-label"), "Go to the passage")
        label = link.get("href")[1:]
        self.assertTrue(label.startswith("os-page-"))
        anchor, = main.xpath("//*[@id=$label]", label=label)
        self.assertEqual(_classes(anchor), ["page-label"])
        self.assertEqual(anchor.getparent().get("id"), URN)

    def test_references_to_one_destination_share_its_anchor(self):
        main = _render(f'<tei:p>See {PAGE_REF} and {PAGE_REF}.</tei:p>'
                       f'<tei:div corresp="{URN}"><tei:p>Blessed</tei:p></tei:div>')
        hrefs = {link.get("href") for link in main.xpath("//h:a", namespaces=NS)}
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(len(main.xpath("//*[@class='page-label']")), 1)

    def test_the_symbol_is_a_parameter(self):
        main = _render(f'<tei:p>See {PAGE_REF}.</tei:p><tei:div corresp="{URN}"/>',
                       **{"page-ref-text": "here"})
        self.assertEqual(main.xpath("string(//h:a)", namespaces=NS), "here")

    def test_a_description_is_set_as_a_rubric_and_takes_no_note_number(self):
        main = _render('<tei:p><tei:note type="description">Reader:</tei:note>Body'
                       '<tei:note>A comment.</tei:note></tei:p>')
        rubric = main.xpath("//h:span[@class='rubric'] | //h:p[@class='rubric']", namespaces=NS)
        self.assertEqual(["Reader:"], ["".join(r.itertext()) for r in rubric])
        self.assertEqual(1, len(main.xpath("//*[contains(@class, 'note-anchor')]", namespaces=NS)))

    def test_optional_reference_to_an_absent_passage_is_removed(self):
        main = _render('<tei:p>Before.<tei:note type="instruction">'
                       f'<tei:seg type="optional-page-reference">Grace: page {PAGE_REF}.</tei:seg>'
                       '</tei:note> After.</tei:p>')
        self.assertFalse(main.xpath("//h:a", namespaces=NS))
        self.assertNotIn("Grace", "".join(main.itertext()))
        self.assertIn("After.", "".join(main.itertext()))

    def test_the_first_occurrence_owns_the_id_and_every_occurrence_is_marked(self):
        main = _render(f'<tei:p>See {PAGE_REF}.</tei:p>'
                       + _cond("a", "wedding") + f'<tei:div corresp="{URN}"><tei:p>One</tei:p></tei:div>'
                       + '<j:endConditional target="#a"/>'
                       + _cond("b", "wedding", "false")
                       + f'<tei:div corresp="{URN}"><tei:p>Other</tei:p></tei:div>'
                       + '<j:endConditional target="#b"/>')
        label = main.xpath("string(//h:a/@href)", namespaces=NS)[1:]
        first, repeat = main.xpath("//*[@data-page-label=$label]", label=label)
        self.assertEqual(first.get("id"), label)
        self.assertIsNone(repeat.get("id"))
        self.assertEqual(len(main.xpath("//*[@id=$label]", label=label)), 1)

    def test_optional_reference_records_where_its_destination_occurs(self):
        root = etree.fromstring(_compiled(
            '<tei:p><tei:note type="instruction"><tei:seg type="optional-page-reference">'
            f'Hallel: page {PAGE_REF}.</tei:seg></tei:note></tei:p>'
            + _cond("a", "hallel") + f'<tei:div corresp="{URN}"><tei:p>One</tei:p></tei:div>'
            + '<j:endConditional target="#a"/>'
            + _cond("b", "wedding")
            + f'<tei:div corresp="{URN}"><tei:p>Other</tei:p></tei:div>'
            + '<j:endConditional target="#b"/>'))
        resolve_page_references(root, every_occurrence=True)
        book = prepare(root)
        # One page reference, whose destination occurs under scope 0 and under scope 1.
        self.assertEqual(book.optional_references, [[[[0], [1]]]])
        main = etree.fromstring(xslt_transform_string(
            XSLT_FILE, etree.tostring(root, encoding="unicode"),
            xslt_params=xslt_parameters(TypographyConfig())))
        seg, = main.xpath("//h:span[contains(@class, 'seg-optional-page-reference')]",
                          namespaces=NS)
        self.assertIn("oref0", _classes(seg))

    def test_optional_reference_that_always_reaches_is_not_numbered(self):
        root = etree.fromstring(_compiled(
            '<tei:p><tei:note type="instruction"><tei:seg type="optional-page-reference">'
            f'Hallel: page {PAGE_REF}.</tei:seg></tei:note></tei:p>'
            + _cond("a", "hallel") + f'<tei:div corresp="{URN}"><tei:p>One</tei:p></tei:div>'
            + '<j:endConditional target="#a"/>'
            + f'<tei:div corresp="{URN}"><tei:p>Unconditional</tei:p></tei:div>'))
        resolve_page_references(root, every_occurrence=True)
        self.assertEqual(prepare(root).optional_references, [])

    def test_optional_reference_in_a_conditional_rubric(self):
        rubric = (f'<tei:seg type="optional-page-reference">Hallel: page {PAGE_REF}.</tei:seg>')
        main = _render(_cond("a", "wedding", rubric=rubric) + '<tei:p>Text</tei:p>'
                       + '<j:endConditional target="#a"/>'
                       + f'<tei:div corresp="{URN}"><tei:p>Hallel</tei:p></tei:div>')
        self.assertEqual(len(main.xpath("//h:a[@class='page-ref']", namespaces=NS)), 1)

    def test_required_reference_to_an_absent_passage_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "destination absent"):
            _render(f"<tei:p>Grace continues on page {PAGE_REF}.</tei:p>")


class TestBlocksInText(unittest.TestCase):
    """A block inside running text must not close the paragraph around it."""

    def _no_block_inside_p(self, main):
        blocks = main.xpath("//h:p//*[self::h:div or self::h:ul or self::h:li or self::h:section"
                            " or self::h:p or starts-with(local-name(), 'h') and"
                            " string-length(local-name()) = 2]", namespaces=NS)
        self.assertEqual(blocks, [])

    def test_a_list_in_a_paragraph(self):
        main = _render("<tei:p>a<tei:list><tei:item>i</tei:item></tei:list>b</tei:p>")
        self._no_block_inside_p(main)
        self.assertEqual(_classes(main.xpath("//h:span[contains(@class, 'list')]", namespaces=NS)[0]),
                         ["list"])

    def test_verse_in_a_note(self):
        main = _render("<tei:p>a<tei:note><tei:lg><tei:l>line</tei:l></tei:lg></tei:note>b</tei:p>")
        self._no_block_inside_p(main)

    def test_an_epigraph_of_paragraphs(self):
        """tei:epigraph holds tei:p, and a <p> cannot hold one."""
        main = _render("<tei:epigraph><tei:p>One.</tei:p><tei:p>Two.</tei:p></tei:epigraph>")
        self._no_block_inside_p(main)
        epigraph = main.xpath("//h:div[contains(@class, 'epigraph')]", namespaces=NS)
        self.assertEqual(1, len(epigraph))
        self.assertEqual(2, len(epigraph[0].xpath("h:p", namespaces=NS)))


class TestLabelsReachEveryElement(unittest.TestCase):

    def test_a_line_break_in_a_scope(self):
        main = _render("<tei:p>one " + _cond("a", "wedding") + "two<tei:lb/>three"
                       "<j:endConditional target=\"#a\"/> four</tei:p>")
        self.assertEqual(_classes(main.find(f".//{{{H}}}br")), ["c0"])

    def test_an_alternative_in_a_scope(self):
        main = _render("<tei:p><tei:choice><j:option>one</j:option>"
                       + _cond("a", "wedding") + "<j:option>two</j:option>"
                       "<j:endConditional target=\"#a\"/></tei:choice></tei:p>")
        governed = main.xpath("//h:span[contains(@class, 'c0')]", namespaces=NS)
        self.assertEqual([("".join(g.itertext()), _classes(g)) for g in governed],
                         [("two", ["option", "option-alt", "c0"])])
        self.assertEqual(len(main.xpath("//*[contains(@class, 'm0')]")), 2)

    def test_a_rubric_after_a_commentary_note_still_announces_the_scope(self):
        """As in the TeX and the Python silence test: any rubric of the scope's own counts."""
        main = _render('<j:conditional xml:id="a"><tei:note type="commentary">c</tei:note>'
                       '<tei:note type="instruction">Say:</tei:note><tei:fs type="t:x">'
                       '<tei:f name="a"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>'
                       '<tei:p>x</tei:p><j:endConditional target="#a"/>')
        opener = main.xpath("//*[contains(@class, 'cm-open')]", namespaces=NS)[0]
        self.assertNotIn("cm-norubric", _classes(opener))

    def test_a_scope_that_opens_with_a_description_is_announced_by_it(self):
        main = _render('<j:conditional xml:id="a"><tei:fs type="t:x">'
                       '<tei:f name="a"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>'
                       '<tei:note type="description">Reader:</tei:note>'
                       '<tei:p>x</tei:p><j:endConditional target="#a"/>')
        opener = main.xpath("//*[contains(@class, 'cm-open')]", namespaces=NS)[0]
        self.assertNotIn("cm-norubric", _classes(opener))


class TestCss(unittest.TestCase):

    def setUp(self):
        # Whether this machine has the fonts named is not what these tests are about.
        fontconfig = patch.object(typography_module, "_installed_font_families", return_value=None)
        fontconfig.start()
        self.addCleanup(fontconfig.stop)

    def test_font_chains(self):
        css = typography_css(TypographyConfig.model_validate(
            {"fonts": {"hebrew": ["Ezra SIL", 'Odd "Name"']}}))
        self.assertIn('--font-hebrew: "Ezra SIL", "Odd \\"Name\\"", serif;', css)

    def test_lengths_css_lacks_are_converted(self):
        css = typography_css(TypographyConfig.model_validate(
            {"markers": {"conditional": {"rule_thickness": "2bp"}}}))
        self.assertIn("--cond-rule-thickness: 2.0075pt;", css)

    def test_hidden_numbers(self):
        css = typography_css(TypographyConfig.model_validate(
            {"markers": {"verse_numbers": "hidden"}}))
        self.assertIn(".v { display: none; }", css)
        self.assertNotIn(".ch { display: none; }", css)

    def test_the_base_styles_keep_no_typography_default(self):
        """Every variable the settings write is written for every book, so the base
        styles give none a value of their own that could disagree with typography.py."""
        from opensiddur.exporter.html.html import ASSETS

        root = typography_css(TypographyConfig()).split("}", 1)[0]
        written = set(re.findall(r"(--[a-z-]+):", root))
        self.assertTrue(written)
        reader = (ASSETS / "reader.css").read_text(encoding="utf-8")
        for variable in written:
            with self.subTest(variable=variable):
                self.assertNotIn(variable + ":", reader)
                self.assertRegex(reader, rf"var\({re.escape(variable)}(?:\)|,)")


class TestSettingsCatalogue(unittest.TestCase):
    """Which settings reach the top of a book's panel, decided when it is built."""

    CONTROLS = [
        {"id": "both", "label": "Both", "features": [["t:x", "a"], ["t:x", "b"]],
         "options": [{"label": "On", "set": {"t:x": {"a": True, "b": True}}}]},
        {"id": "unread", "label": "Unread", "features": [["t:y", "z"]],
         "options": [{"label": "On", "set": {"t:y": {"z": True}}}]},
    ]

    @staticmethod
    def _book(chars: dict[str, int]) -> BookConditions:
        """One scope per feature, each reading its feature as true."""
        features = [Feature("t:x", name, [True], cids=[i]) for i, name in enumerate(chars)]
        expressions = [{"cond": {"fs": "t:x", "f": [{"name": name, "v": True}]}, "pinned": {}}
                       for name in chars]
        book = BookConditions(expressions=expressions, scopes=list(range(len(chars))),
                              features=features, scope_chars=list(chars.values()))
        book.conditional_chars = sum(book.scope_chars)
        return book

    @staticmethod
    def _names(entries):
        return [entry.get("label") or entry["name"] for entry in entries]

    def test_a_control_takes_the_text_of_all_its_features(self):
        book = self._book({"a": 30, "b": 30, "c": 50})
        self.assertEqual(self._names(settings_catalogue(book, self.CONTROLS)), ["Both", "c"])

    def test_a_feature_a_control_covers_is_not_offered_alone(self):
        book = self._book({"a": 10, "c": 50})
        self.assertNotIn("a", self._names(settings_catalogue(book, self.CONTROLS)))

    def test_a_control_the_book_has_no_use_for_is_left_out(self):
        book = self._book({"c": 50})
        self.assertEqual(self._names(settings_catalogue(book, self.CONTROLS)), ["c"])

    def test_at_most_six(self):
        book = self._book({name: 10 for name in "cdefghij"})
        self.assertEqual(len(settings_catalogue(book, [])), 6)

    def test_options_that_change_nothing_are_dropped(self):
        controls = [{"id": "c", "label": "C", "features": [["t:x", "a"], ["t:y", "z"]],
                     "options": [{"label": "Useful", "set": {"t:x": {"a": False}}},
                                 {"label": "Idle", "set": {"t:y": {"z": True}}}]}]
        entry = settings_catalogue(self._book({"a": 10}), controls)[0]
        self.assertEqual([option["label"] for option in entry["options"]], ["Useful"])

    def test_a_control_with_nothing_useful_is_dropped(self):
        controls = [{"id": "c", "label": "C", "features": [["t:x", "a"]],
                     "options": [{"label": "Idle", "set": {"t:y": {"z": True}}}]}]
        self.assertEqual(self._names(settings_catalogue(self._book({"a": 10}), controls)), ["a"])

    def test_the_books_default_is_still_an_option(self):
        """An option that repeats the book's default stays, so the reader can name it."""
        controls = [{"id": "c", "label": "C", "features": [["t:x", "a"]],
                     "options": [{"label": "Default", "set": {"t:x": {"a": True}}},
                                 {"label": "Other", "set": {"t:x": {"a": False}}}]}]
        entry = settings_catalogue(self._book({"a": 10}), controls)[0]
        self.assertEqual([option["label"] for option in entry["options"]], ["Default", "Other"])

    def test_too_little_text_stays_in_advanced(self):
        book = self._book({"c": 1000, "d": 9})
        self.assertEqual(self._names(settings_catalogue(book, [])), ["c"])

    def test_a_top_feature_is_at_the_top_however_little_it_decides(self):
        book = self._book({"c": 1000, "d": 9})
        self.assertEqual(self._names(settings_catalogue(book, [], frozenset({("t:x", "d")}))),
                         ["c", "d"])

    def test_a_top_feature_does_not_count_towards_the_limit(self):
        book = self._book({**{name: 100 for name in "cdefgh"}, "i": 1})
        names = self._names(settings_catalogue(book, [], frozenset({("t:x", "i")})))
        self.assertEqual(names, list("cdefgh") + ["i"])

    def test_a_top_feature_that_ranks_is_listed_once(self):
        book = self._book({"c": 1000, "d": 9})
        self.assertEqual(self._names(settings_catalogue(book, [], frozenset({("t:x", "c")}))),
                         ["c"])

    def test_a_top_feature_the_book_does_not_read_is_left_out(self):
        book = self._book({"c": 1000})
        self.assertEqual(self._names(settings_catalogue(book, [], frozenset({("t:x", "z")}))),
                         ["c"])

    def test_a_control_that_sets_a_top_feature_is_at_the_top(self):
        book = self._book({"a": 1, "c": 1000})
        self.assertEqual(
            self._names(settings_catalogue(book, self.CONTROLS, frozenset({("t:x", "a")}))),
            ["c", "Both"])

    def test_top_features_are_read_from_the_spec(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "basic.yaml"
            spec.write_text("controls: []\n"
                            "features:\n"
                            "  t:x:\n"
                            "    a: {label: A, top: true}\n"
                            "    b: {label: B}\n", encoding="utf-8")
            self.assertEqual(always_basic(spec), {("t:x", "a")})

    def test_a_top_control(self):
        controls = [{**self.CONTROLS[0], "top": True}]
        book = self._book({"a": 1, "c": 1000})
        self.assertEqual(self._names(settings_catalogue(book, controls)), ["c", "Both"])


class TestBasicSettingsSpec(unittest.TestCase):
    """basic_settings.yaml names features the compiler really produces."""

    @classmethod
    def setUpClass(cls):
        reset_linear_data()
        linear_data = get_linear_data()
        CompilerProcessor.load_init_settings(linear_data, yaml_to_declaration_entries({
            "opensiddur:gregorian-date": {"year": 2026, "month": 4, "day": 6},
            "opensiddur:location": {"latitude": 31.78, "longitude": 35.22},
            "opensiddur:time": {"hour": 9, "minute": 0}}))
        cls.calendar = {(e.fs_type, e.feature_name) for e in linear_data.conditional_settings}
        cls.calendar |= {(fs, name) for fs, features in STATIC_DEFAULTS.items() for name in features}
        reset_linear_data()

    def _check(self, fs, name):
        if not is_reader_supplied(fs) or fs in STATIC_DEFAULTS:
            self.assertIn((fs, name), self.calendar, f"{fs} {name} is not a feature the compiler sets")
        self.assertRegex(fs, r"^[a-z]+:[a-z-]+$")

    def test_controls(self):
        controls = basic_controls()
        self.assertEqual(len({c["id"] for c in controls}), len(controls))
        for control in controls:
            with self.subTest(control=control["id"]):
                self.assertLessEqual(
                    set(control), {"id", "label", "note", "top", "when", "options", "features"})
                self.assertIsInstance(control.get("top", False), bool)
                self.assertIn(control.get("when"), (None, "no-date", "no-place"))
                self.assertTrue(control["options"])
                for option in control["options"]:
                    for fs, features in option["set"].items():
                        for name, value in features.items():
                            self._check(fs, name)
                            self.assertIsInstance(value, (bool, int, str))

    def test_feature_words(self):
        for (fs, name), words in feature_words().items():
            with self.subTest(feature=(fs, name)):
                self._check(fs, name)
                self.assertTrue(words["label"])

    def test_feature_spec_keys(self):
        for fs, features in read_basic_settings()["features"].items():
            for name, spec in features.items():
                with self.subTest(feature=(fs, name)):
                    self.assertLessEqual(set(spec), {"label", "values", "top"})
                    self.assertIsInstance(spec.get("top", False), bool)


SETTINGS = """\
book:
  project: proj
  file_name: index.xml
  title: The Settings Title
priority:
  transclusion: [proj]
typography:
  markers:
    conditional:
      inline_open: "⟨"
      inline_close: "⟩"
declarations:
  opensiddur:override:
    wedding: true
  opensiddur:israel:
    is-israel: true
"""

#: A credit as the compiler merges it into the compiled document's titleStmt.
SOME_ONE = ('<tei:respStmt><tei:resp key="trc">Transcribed by</tei:resp>'
            '<tei:name ref="urn:x-opensiddur:contributor:opensiddur.org/some-one">Some One</tei:name>'
            '</tei:respStmt>')

INDEX = f"""<tei:TEI xmlns:tei="{TEI_NS}" xml:lang="en"><tei:teiHeader><tei:fileDesc>
  <tei:titleStmt><tei:title>I</tei:title><tei:respStmt><tei:resp key="trc">Transcribed by</tei:resp>
  <tei:name ref="urn:x-opensiddur:contributor:opensiddur.org/only-in-the-source">Only In The Source</tei:name>
  </tei:respStmt></tei:titleStmt>
  <tei:publicationStmt><tei:availability><tei:licence target="http://creativecommons.org/publicdomain/zero/1.0/">CC0</tei:licence>
  </tei:availability></tei:publicationStmt>
  <tei:sourceDesc><tei:bibl><tei:author>A. Writer</tei:author><tei:title>Prayers &amp; Hymns</tei:title>
  <tei:publisher>The Press</tei:publisher><tei:pubPlace>London</tei:pubPlace><tei:date>1912</tei:date>
  <tei:idno type="url">https://example.org/book</tei:idno></tei:bibl></tei:sourceDesc></tei:fileDesc></tei:teiHeader>
  <tei:text><tei:body><tei:p>x</tei:p></tei:body></tei:text></tei:TEI>"""

BODY = (
    _cond("a", "wedding", rubric="At a wedding:") + "<tei:p>wedding words</tei:p>"
    "<j:endConditional target=\"#a\"/>"
    + _cond("b", "wedding", value="false") + "<tei:p>ordinary words</tei:p>"
    "<j:endConditional target=\"#b\"/>"
    + _cond("c", "minyan", fs="opensiddur:quorum") + "<tei:p>minyan words</tei:p>"
    "<j:endConditional target=\"#c\"/>"
    + '<j:conditional xml:id="d"><tei:fs type="t:x"><tei:f name="s"><tei:string>&lt;/script&gt;'
      '</tei:string></tei:f></tei:fs></j:conditional><tei:p>odd</tei:p>'
      '<j:endConditional target="#d"/>'
    + "<tei:p>" + _cond("e", "wedding") + "inline<j:endConditional target=\"#e\"/></tei:p>"
)


def _parallels(*rows) -> etree.ElementBase:
    body = "".join(
        f'<p:parallel><p:parallelItem role="primary" xml:lang="{primary}"><tei:p>x</tei:p>'
        f'</p:parallelItem><p:parallelItem role="parallel" xml:lang="{parallel}"><tei:p>y</tei:p>'
        f'</p:parallelItem></p:parallel>' for primary, parallel in rows)
    return etree.fromstring(_compiled(body))


class TestColumns(unittest.TestCase):
    """The parallel text's columns, which the reader can show one at a time."""

    def test_hebrew_and_its_translation(self):
        self.assertEqual(columns(_parallels(("he", "en"), ("he", "en"), ("arc-Hebr", "en"))), {
            "primary": {"lang": "he", "label": "Hebrew"},
            "parallel": {"lang": "en", "label": "Translation"}})

    def test_the_hebrew_column_is_named_wherever_it_is(self):
        self.assertEqual(columns(_parallels(("en", "he")))["parallel"]["label"], "Hebrew")
        self.assertEqual(columns(_parallels(("en", "he")))["primary"]["label"], "Translation")

    def test_neither_hebrew_names_the_primary_by_its_language(self):
        self.assertEqual(columns(_parallels(("yi", "en"))), {
            "primary": {"lang": "yi", "label": "Yiddish"},
            "parallel": {"lang": "en", "label": "Translation"}})

    def test_no_parallel_text_has_no_columns(self):
        self.assertIsNone(columns(etree.fromstring(_compiled("<tei:p>only</tei:p>"))))


class TestElectronicSettings(unittest.TestCase):
    """A settings file's `electronic` section: how the adaptive book starts."""

    def test_defaults(self):
        self.assertEqual(ElectronicSettings().model_dump(),
                         {"day": "now", "columns": "both", "psalm_titles": "printed"})

    def test_values(self):
        self.assertEqual(ElectronicSettings.model_validate({"day": "none"}).day, "none")
        self.assertEqual(
            ElectronicSettings.model_validate({"psalm_titles": "uniform"}).psalm_titles, "uniform")
        for bad in ({"day": "tomorrow"}, {"columns": "hebrew"}, {"days": "now"},
                    {"psalm_titles": "numbered"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                ElectronicSettings.model_validate(bad)


class TestPlaces(unittest.TestCase):
    """The places the settings panel offers."""

    def test_each_zone_is_the_one_its_coordinates_are_in(self):
        """The device reads the clock in the zone given; the compiler would look it up."""
        for place in read_places():
            with self.subTest(place=place["name"]):
                self.assertEqual(tzfpy.get_tz(place["longitude"], place["latitude"]),
                                 place["timezone"])

    def test_names_are_unique(self):
        names = [place["name"] for place in read_places()]
        self.assertEqual(len(names), len(set(names)))


class TestBuildBook(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)
        (self.base / "proj").mkdir()
        (self.base / "proj" / "index.xml").write_text(INDEX, encoding="utf-8")
        self.settings = self.base / "settings.yaml"
        self.settings.write_text(SETTINGS, encoding="utf-8")
        self.compiled = self.base / "compiled.xml"

    def _build(self, *, electronic=True, settings=True) -> str:
        self.compiled.write_bytes(_compiled(BODY, electronic=electronic, credits=SOME_ONE))
        return build_book(self.compiled, self.settings if settings else None, self.base)

    @staticmethod
    def _between(page: str, start: str, end: str) -> str:
        return page.split(start, 1)[1].split(end, 1)[0]

    def _book(self, page: str) -> dict:
        return json.loads(self._between(page, '<script type="application/json" id="os-book">',
                                        "</script>"))

    def test_page_is_self_contained(self):
        page = self._build()
        self.assertNotRegex(page, r'<(script|link)[^>]*\b(src|href)=')
        self.assertIn("OSCond", page)
        self.assertIn('<main xmlns="http://www.w3.org/1999/xhtml" class="os-book"', page)

    def test_page_references_link_within_the_page(self):
        self.compiled.write_bytes(_compiled(
            f'<tei:p>Grace continues on page {PAGE_REF}.</tei:p>'
            f'<tei:div corresp="{URN}"><tei:p>Blessed</tei:p></tei:div>'))
        page = build_book(self.compiled, self.settings, self.base)
        href, = re.findall(r'<a [^>]*href="#([^"]+)"', page)
        self.assertIn(f'id="{href}"', page)

    def test_title_from_the_settings(self):
        self.assertIn("<title>The Settings Title</title>", self._build())

    def test_a_broken_settings_file_is_an_error(self):
        """The same policy as the PDF stage's: not a book in the default settings."""
        for text, error in ((":\n: not yaml", SettingsError),
                            ("typography:\n  page:\n    paper: tabloid\n", ValidationError),
                            ("electronic:\n  colums: both\n", ValidationError)):
            with self.subTest(text):
                self.settings.write_text(text, encoding="utf-8")
                with self.assertRaises(error):
                    self._build()

    def test_title_from_the_header_without_settings(self):
        self.assertIn("<title>Header Title</title>", self._build(settings=False))

    def test_defaults_are_the_readers_declarations_and_static_defaults(self):
        defaults = self._book(self._build())["defaults"]
        self.assertIs(defaults["opensiddur:override"]["wedding"], True)
        self.assertIs(defaults["opensiddur:override"]["brit-milah"], False)
        self.assertNotIn("opensiddur:israel", defaults)

    def test_without_scripts_the_page_is_the_printed_book(self):
        """The settings file says it is a wedding: the not-a-wedding passage is hidden, the
        wedding passage drops its rubric and its rule, and the minyan is undecided."""
        page = self._build()
        css = self._between(page, '<style id="os-cond-default">', "</style>").strip()
        self.assertEqual(css.splitlines(), [
            ".c1,.m1{display:none}",
            ".m0.cm-close,.m0 > .rubric,.m0 .cm-br,.m4.cm-close,.m4 > .rubric,.m4 .cm-br"
            "{display:none}",
        ])

    def test_the_panel_is_decided_when_the_book_is_built(self):
        spec = self.base / "basic.yaml"
        spec.write_text(
            "controls:\n"
            "  - id: celebration\n"
            "    label: Celebration\n"
            "    note: A note.\n"
            "    options:\n"
            "      - {label: A wedding, set: {opensiddur:override: {wedding: true}}}\n"
            "      - {label: No wedding, set: {opensiddur:override: {wedding: false}}}\n"
            "features:\n"
            "  opensiddur:quorum:\n"
            "    minyan: {label: Ten present, values: {true: Yes, false: No}}\n",
            encoding="utf-8")
        self.compiled.write_bytes(_compiled(BODY))
        book = self._book(build_book(self.compiled, self.settings, self.base, spec))
        minyan = next(f for f in book["features"] if f["name"] == "minyan")
        self.assertEqual((minyan["kind"], minyan["calendar"], minyan["label"]),
                         ("binary", False, "Ten present"))
        self.assertEqual(
            [(e["type"], e.get("label") or e.get("name")) for e in book["basic"]],
            [("control", "Celebration"), ("feature", "minyan"), ("feature", "s")])
        celebration = book["basic"][0]
        self.assertEqual(celebration["note"], "A note.")
        self.assertEqual([o["label"] for o in celebration["options"]], ["A wedding", "No wedding"])

    def test_script_text_cannot_close_the_script(self):
        page = self._build()
        data = self._between(page, '<script type="application/json" id="os-book">', "</script>")
        self.assertNotIn("<", data)
        self.assertIn("\\u003c/script>", data)
        self.assertEqual(self._book(page)["expressions"][3]["cond"]["f"][0]["v"], "</script>")

    def test_bracket_settings_reach_the_text(self):
        self.assertRegex(self._build(), r'<span class="cm-br" aria-hidden="true">⟨</span>')

    def test_colophon(self):
        page = self._build()
        about = self._between(page, '<footer class="os-about">', "</footer>")
        self.assertIn("<strong>Transcriptionist:</strong> Some One", about)
        self.assertIn('href="http://creativecommons.org/publicdomain/zero/1.0/"', about)

    def test_colophon_credits_whom_the_compiled_document_credits(self):
        """As the PDF does: a credit the compiler did not carry into the book is not the
        book's, even though a file the book refers to names it."""
        about = self._between(self._build(), '<footer class="os-about">', "</footer>")
        self.assertNotIn("Only In The Source", about)

    def test_colophon_cites_the_sources(self):
        about = self._between(self._build(), '<footer class="os-about">', "</footer>")
        self.assertIn('<h2>Sources</h2><ul class="os-sources">', about)
        self.assertIn("<li>A. Writer. <cite>Prayers &amp; Hymns</cite>. London, The Press, 1912. "
                      '<a href="https://example.org/book">https://example.org/book</a>.</li>',
                      about)

    def test_edition_colophons_follow_the_colophon(self):
        front = ('<tei:front><j:conditional xml:id="cc1"><tei:fs type="opensiddur:paratext">'
                 '<tei:f name="include"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>'
                 '<tei:div type="colophon" subtype="notes"><tei:p>First published in 1842.</tei:p>'
                 '</tei:div><j:endConditional target="#cc1"/></tei:front>')
        self.compiled.write_bytes(_compiled(BODY, credits=SOME_ONE).replace(
            b"<tei:text><tei:body>", b"<tei:text>" + front.encode() + b"<tei:body>"))
        page = build_book(self.compiled, self.settings, self.base)
        about = self._between(page, '<footer class="os-about">', "</footer>")
        main = page.split('<footer class="os-about">', 1)[0]
        self.assertNotIn("First published in 1842.", main)
        self.assertIn("First published in 1842.", about)
        self.assertLess(about.index("GNU Lesser General Public License"), about.index("First published in 1842."))
        self.assertNotIn("@@COLOPHON", page)

    def test_colophon_has_the_software_notice(self):
        about = self._between(self._build(), '<footer class="os-about">', "</footer>")
        self.assertIn("GNU Lesser General Public License", about)
        self.assertIn("Meir S. List", about)

    def test_scripts_are_labelled_and_the_calendar_comes_first(self):
        page = self._build()
        self.assertEqual(page.count("// @license magnet:"), 3)
        self.assertEqual(page.count("// @license-end"), 3)
        self.assertLess(page.index("root.OSCal ="), page.index("root.OSCond ="))
        self.assertLess(page.index("root.OSCond ="), page.index("var storageKey"))

    def test_columns_reach_the_book_and_no_script_page_shows_both(self):
        self.assertIsNone(self._book(self._build())["columns"])
        self.compiled.write_bytes(_compiled(
            '<p:parallel><p:parallelItem role="primary" xml:lang="he"><tei:p>א</tei:p>'
            '</p:parallelItem><p:parallelItem role="parallel" xml:lang="en"><tei:p>a</tei:p>'
            '</p:parallelItem></p:parallel>'))
        page = build_book(self.compiled, self.settings, self.base)
        self.assertEqual(self._book(page)["columns"]["primary"]["label"], "Hebrew")
        self.assertNotIn("data-columns", re.search(r"<html[^>]*>", page).group(0))

    def test_the_book_starts_as_its_settings_file_says(self):
        self.assertEqual(self._book(self._build())["start"], {"day": "now", "columns": "both"})
        self.settings.write_text(SETTINGS + "electronic:\n  day: none\n  columns: primary\n",
                                 encoding="utf-8")
        self.assertEqual(self._book(self._build())["start"],
                         {"day": "none", "columns": "primary"})

    def test_psalms_are_retitled_only_when_the_settings_ask(self):
        with patch("opensiddur.exporter.html.html.normalize_psalm_titles") as normalize:
            self._build()
            normalize.assert_not_called()
            self.settings.write_text(SETTINGS + "electronic:\n  psalm_titles: uniform\n",
                                     encoding="utf-8")
            book = self._book(self._build())
            normalize.assert_called_once()
        self.assertEqual(book["start"], {"day": "now", "columns": "both"})

    def test_places_only_where_the_day_matters(self):
        self.assertEqual(self._book(self._build())["places"], [])
        self.compiled.write_bytes(_compiled(
            _cond("h", "shabbat", fs="opensiddur:holiday-aggregate") + "<tei:p>Shabbat</tei:p>"
            '<j:endConditional target="#h"/>'))
        book = self._book(build_book(self.compiled, self.settings, self.base))
        self.assertEqual(book["calendarScopes"], 1)
        self.assertEqual(book["places"], read_places())

    def test_book_id_is_stable(self):
        self.assertEqual(self._book(self._build())["id"], self._book(self._build())["id"])

    def test_a_print_compile_is_warned_about(self):
        with self.assertLogs("opensiddur.exporter.html.html", level="WARNING") as logs:
            self._build(electronic=False)
        self.assertIn("--destination electronic", logs.output[0])

    def test_the_device_writes_the_same_rules(self):
        node = require_node(self)
        page = self._build()
        book = self._book(page)
        css = self._between(page, '<style id="os-cond-default">', "</style>").strip()
        result = run_js(node, "return OSCond.scopeCss(args, {}, args.defaults);", book)
        self.assertEqual(result["css"].strip(), css)

    def test_large_books_keep_late_selectors_in_bounded_rules(self):
        from opensiddur.exporter.condition_eval import TriState
        node = require_node(self)
        # More selectors than Chromium accepts in one rule: the late scope
        # must still hide, both initially and after changing reader settings.
        count = 40000
        expression = {"cond": {"fs": "opensiddur:override", "f": [
            {"name": "wedding", "v": True}]}, "pinned": {}}
        book = BookConditions(expressions=[expression], scopes=[0] * count)
        expected = scope_css(book, [TriState.FALSE])
        actual = run_js(node, "return OSCond.scopeCss(args, "
                        "{'opensiddur:override': {wedding: false}}, {}).css;",
                        {"expressions": [expression], "scopes": [0] * count})
        self.assertEqual(actual, expected)
        self.assertIn(".c39999", actual)
        rules = actual.strip().splitlines()
        self.assertGreater(len(rules), 1)
        self.assertTrue(all(len(rule.split("{")[0].split(",")) <= 256
                            for rule in rules))

    def test_a_row_none_of_whose_text_shows_goes_whole(self):
        """The row's two columns are each a wedding's; the settings file says it is a wedding,
        then not: the row is hidden whole, on the device as without scripts."""
        node = require_node(self)
        self.compiled.write_bytes(_compiled(
            '<p:parallel><p:parallelItem role="primary" xml:lang="he">'
            + _cond("w1", "wedding") + '<tei:p>א</tei:p><j:endConditional target="#w1"/>'
            '</p:parallelItem><p:parallelItem role="parallel" xml:lang="en">'
            + _cond("w2", "wedding") + '<tei:p>a</tei:p><j:endConditional target="#w2"/>'
            '</p:parallelItem></p:parallel>'))
        page = build_book(self.compiled, self.settings, self.base)
        book = self._book(page)
        self.assertEqual(len(book["rows"]), 1)
        self.assertIn('class="par r0"', page)
        css = self._between(page, '<style id="os-cond-default">', "</style>")
        self.assertNotIn(".r0", css, "a wedding: the row shows")
        not_a_wedding = {"opensiddur:override": {"wedding": False}}
        result = run_js(node, "return OSCond.scopeCss(args.book, args.reader, args.book.defaults);",
                        {"book": book, "reader": not_a_wedding})
        self.assertIn(".r0", result["css"])

    def test_optional_reference_goes_when_every_destination_does(self):
        """The destination occurs at a wedding and at a circumcision. The settings file says
        it is a wedding, and not a circumcision."""
        self.compiled.write_bytes(_compiled(
            '<tei:p><tei:note type="instruction"><tei:seg type="optional-page-reference">'
            f'Grace: page {PAGE_REF}.</tei:seg></tei:note></tei:p>'
            + _cond("a", "wedding", value="false")
            + f'<tei:div corresp="{URN}"><tei:p>One</tei:p></tei:div>'
            + '<j:endConditional target="#a"/>'
            + _cond("b", "brit-milah")
            + f'<tei:div corresp="{URN}"><tei:p>Other</tei:p></tei:div>'
            + '<j:endConditional target="#b"/>'))
        page = build_book(self.compiled, self.settings, self.base)
        css = self._between(page, '<style id="os-cond-default">', "</style>").strip()
        self.assertIn(".oref0", css.split("{")[0].split(","))
        node = require_node(self)
        book = self._book(page)
        device = run_js(node, "return OSCond.scopeCss(args, {}, args.defaults).css;", book)
        self.assertEqual(device.strip(), css)
        milah = run_js(node, "return OSCond.scopeCss(args, {'opensiddur:override': "
                             "{'brit-milah': true}}, args.defaults).css;", book)
        self.assertNotIn(".oref0", milah)

    def test_sections_shown(self):
        node = require_node(self)
        book = {"scopes": [0, 1, 1], "sections": [None, [[0]], [[0], [1]], [[0, 2]]]}
        result = run_js(node, "return OSCond.sectionsShown(args, ['false', 'true']);", book)
        # Scope 0 is false, scopes 1 and 2 true: a section shows if one of its sets is clear.
        self.assertEqual(result, [True, False, True, False])

    def test_the_device_follows_the_reader(self):
        node = require_node(self)
        book = self._book(self._build())
        result = run_js(
            node,
            "return OSCond.scopeCss(args, {'opensiddur:quorum': {minyan: false},"
            " 'opensiddur:override': {wedding: false}}, args.defaults).css;",
            book)
        hidden = re.findall(r"^(.*)\{display:none\}$", result, re.MULTILINE)[0].split(",")
        self.assertEqual(sorted(hidden), [".c0", ".c2", ".c4", ".m0", ".m2", ".m4"])



class TestTheDayCelebratedAsPurim(unittest.TestCase):
    """A kind of day cannot say which of 14 and 15 Adar is celebrated as Purim; the volume
    can, and its book's Purim choices say what it does."""

    KINDS = [
        {"label": "Purim", "set": {"opensiddur:holiday": {"purim": 1, "shushan-purim": 0}}},
        {"label": "Shushan Purim", "set": {"opensiddur:holiday": {"purim": 0, "shushan-purim": 1}}},
        {"label": "Ordinary", "set": {"opensiddur:holiday": {"purim": 0, "purim-observed": 0}}},
    ]

    def _observed(self, purim_day):
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "basic.yaml"
            (Path(tmp) / "kinds.json").write_text(json.dumps(self.KINDS), encoding="utf-8")
            spec.write_text("controls:\n  - id: kind\n    label: Kind\n"
                            "    options_from: kinds.json\n", encoding="utf-8")
            options = basic_controls(spec, purim_day)[0]["options"]
        return [option["set"]["opensiddur:holiday"].get("purim-observed") for option in options]

    def test_purim_is_celebrated_on_the_fourteenth(self):
        self.assertEqual(self._observed(14), [1, 0, 0])

    def test_purim_is_celebrated_on_the_fifteenth(self):
        self.assertEqual(self._observed(15), [0, 1, 0])

    def test_an_undefined_day_settles_nothing(self):
        self.assertEqual(self._observed(None), [None, None, 0])

    def test_the_volume_says_which_day(self):
        def settings(declarations):
            return SettingsYaml.model_validate({"declarations": declarations})

        self.assertEqual(celebrated_purim(SettingsYaml()), 14)
        self.assertEqual(celebrated_purim(
            settings({"opensiddur:purim-observance": {"day": 15}})), 15)
        self.assertIsNone(celebrated_purim(
            settings({"opensiddur:purim-observance": {"day": None}})))

if __name__ == "__main__":
    unittest.main()


# Its feature names are made up for the test.
@unchecked_registry()
class TestNotesAndDirection(unittest.TestCase):
    """Notes the compiler sets inside anchors and milestones, numbering, and direction."""

    def test_a_note_inside_an_anchor_is_shown(self):
        main = _render('<tei:p>word<tei:anchor xml:id="a"><tei:note>a remark</tei:note>'
                       '</tei:anchor> more</tei:p>')
        self.assertIn("a remark", "".join(main.itertext()))
        self.assertEqual(main.xpath("string((//*[@class='note-ref'])[1])"), "1")

    def test_a_note_inside_a_verse_milestone_is_shown(self):
        main = _render('<tei:p><tei:milestone unit="verse" n="1"><tei:note>on the verse</tei:note>'
                       '</tei:milestone>text</tei:p>')
        self.assertIn("on the verse", "".join(main.itertext()))

    def test_a_notes_number_counts_only_notes_in_the_text(self):
        document = f'''<tei:TEI xmlns:tei="{TEI_NS}" xmlns:j="{J}" xmlns:p="{P}" xml:lang="en"
            p:project="proj" p:file_name="index.xml" p:destination="electronic">
          <tei:teiHeader><tei:fileDesc><tei:titleStmt><tei:title>T</tei:title></tei:titleStmt>
          <tei:sourceDesc><tei:bibl>b<tei:note>a header note</tei:note></tei:bibl></tei:sourceDesc>
          </tei:fileDesc></tei:teiHeader>
          <tei:text><tei:body><tei:p>word<tei:note>the first note</tei:note></tei:p></tei:body></tei:text>
        </tei:TEI>'''
        root = etree.fromstring(document.encode())
        prepare(root)
        main = etree.fromstring(xslt_transform_string(
            XSLT_FILE, etree.tostring(root, encoding="unicode"),
            xslt_params=xslt_parameters(TypographyConfig())))
        self.assertEqual(main.xpath("string((//*[@class='note-ref'])[1])"), "1")

    def test_a_transliteration_is_left_to_right(self):
        main = _render('<tei:p><tei:foreign xml:lang="he-Latn">Shema</tei:foreign></tei:p>')
        transliteration = main.xpath("//*[@lang='he-Latn']")[0]
        self.assertNotEqual(transliteration.get("dir"), "rtl")

    def test_a_note_beside_a_rubric_is_shown_and_numbered(self):
        main = _render('<tei:p>a<tei:note>n-one</tei:note></tei:p>'
                       + _cond("c", "x", rubric="Say:").replace(
                           '</tei:note>', '</tei:note><tei:note>n-two</tei:note>', 1)
                       + '<tei:p>said</tei:p><j:endConditional target="#c"/>'
                         '<tei:p>b<tei:note>n-three</tei:note></tei:p>')
        text = "".join(main.itertext())
        self.assertIn("n-two", text)
        self.assertEqual(main.xpath("//*[@class='note-ref']/text()"), ["1", "2", "3"])

    def test_hebrew_is_right_to_left(self):
        main = _render('<tei:p><tei:foreign xml:lang="he">שמע</tei:foreign></tei:p>')
        self.assertEqual(main.xpath("//*[@lang='he']")[0].get("dir"), "rtl")
