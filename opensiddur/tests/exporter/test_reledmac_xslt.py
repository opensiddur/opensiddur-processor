"""Tests for the reledmac/reledpar XSLT (`opensiddur/exporter/tex/reledmac.xslt`).

These tests live one level above the LaTeX engine: they call the XSLT
transformation directly and assert structural properties of the emitted
``.tex`` text. The actual ``lualatex`` invocation is mocked everywhere it
might be triggered, since CI doesn't have a TeXLive install.

Two invariants are critical for reledpar to align verses across page
breaks:

1. Both streams of a ``p:parallel`` block must emit the **same number of**
   ``\\pstart`` (and ``\\pend``) markers, in document order.
2. Each ``tei:milestone[@unit='verse']`` must produce a fresh ``\\pstart``
   so reledpar can pair the Nth verse on each side.

Editorial/instructional notes must come out as well-formed
``\\edtext{...}{...}`` constructs so reledmac places them in the apparatus,
not as floating ``\\footnote``s.
"""

import re
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.tests.exporter.stylesheet_helpers import stylesheet_parameters, transform
from opensiddur.exporter.marker_reconstruct import reconstruct_markered_document


def _transform(xml: str, **params) -> str:
    """Transform ``xml`` with the reledmac XSLT, with the parameters tex/latex.py would
    give it at the default settings; see stylesheet_helpers.transform."""
    return transform(xml, **params)


class TestPreamble(unittest.TestCase):
    """The LuaLaTeX preamble must declare the engine, polyglossia, and
    reledmac (plus reledpar when there's any parallel block)."""

    def test_preamble_loads_reledmac_and_polyglossia(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\documentclass", out)
        self.assertIn(r"\usepackage{polyglossia}", out)
        self.assertIn(r"\usepackage{reledmac}", out)
        self.assertIn(r"\Xnonumber[B]", out)
        self.assertIn(r"\newcommand{\OSInterlinearNotemark}", out)
        # No parallel content → no reledpar package.
        self.assertNotIn(r"\usepackage{reledpar}", out)
        self.assertIn(r"\setotherlanguage{hebrew}", out)

    def test_bibliography_url_breaks_are_enabled_after_biblatex(self):
        out = _transform('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">'
                         '<tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text></tei:TEI>')
        self.assertLess(out.index(r"\usepackage[backend=bibtex]{biblatex}"),
                        out.index(r"\usepackage{xurl}"))
        self.assertLess(out.index(r"\usepackage{xurl}"),
                        out.index(r"\usepackage{hyperref}"))

    def test_preamble_declares_running_head_mark_classes(self):
        """Every heading level, plus book and chapter, needs a mark class for the
        running heads to read; the `Alt` family carries the second parallel
        column. Declared unconditionally so the preamble stays deterministic."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        for mark_class in (
            "OSheadA", "OSheadB", "OSheadC", "OSheadD", "OSheadAny",
            "OSbook", "OSchapter",
            "OSheadAAlt", "OSheadBAlt", "OSheadCAlt", "OSheadDAlt",
            "OSheadAnyAlt", "OSbookAlt",
        ):
            with self.subTest(mark_class=mark_class):
                self.assertIn(r"\NewMarkClass{%s}" % mark_class, out)
        self.assertIn(r"\newcommand{\OSHFIfNonEmpty}", out)
        self.assertIn(r"\newcommand{\OSHebrewNumber}", out)

    def test_document_title_comes_from_the_tei_header(self):
        """The header is dropped from the output but is still readable here, and
        it is where {document-title} gets its text."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:teiHeader><tei:fileDesc><tei:titleStmt>
            <tei:title type="main">A Book of Prayer</tei:title>
          </tei:titleStmt></tei:fileDesc></tei:teiHeader>
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(
            r"\newcommand{\OSDocumentTitle}{{\textdir TLT\foreignlanguage{english}{"
            r"A Book of Prayer}}",
            out,
        )

    def test_document_title_is_empty_without_one(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        self.assertIn(r"\newcommand{\OSDocumentTitle}{}", _transform(xml))

    def test_page_style_preamble_is_emitted_after_hyperref(self):
        """fancyhdr must load after hyperref, and nothing is emitted when no
        running head is configured."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        self.assertNotIn("fancyhdr", _transform(xml, **{"page-style-preamble": ""}))

        out = _transform(xml, **{"page-style-preamble": r"\usepackage{fancyhdr}"})
        self.assertIn(r"\usepackage{fancyhdr}", out)
        self.assertLess(out.index(r"\usepackage{hyperref}"), out.index("fancyhdr"))
        self.assertLess(out.index("fancyhdr"), out.index(r"\begin{document}"))

    def test_pdf_viewer_settings_follow_hyperref(self):
        """The binding and initial view are \\hypersetup keys, which are undefined
        until hyperref is loaded."""
        out = _transform('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">'
                         '<tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text></tei:TEI>')
        viewer = out.index(r"\hypersetup{pdfdirection=R2L,pdfpagelayout=TwoPageRight}")
        self.assertLess(out.index(r"\usepackage{hyperref}"), viewer)
        self.assertLess(viewer, out.index(r"\begin{document}"))

    def test_preamble_loads_reledpar_when_parallel(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:p>Hello</tei:p></p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\usepackage{reledpar}", out)

    def test_documentclass_options_are_passed_through_verbatim(self):
        """The class options are built in Python; the stylesheet only places them."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, **{"documentclass-options": "12pt,a5paper,oneside"})
        self.assertIn(r"\documentclass[12pt,a5paper,oneside]{book}", out)

    def test_the_typography_preamble_follows_the_packages_it_configures(self):
        """After the packages and the stylesheet's own definitions, which it may use; and
        before the bibliography, which is not typography and may redefine what it defines."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(
            xml,
            **{
                "typography-preamble": "\\OSTYPOGRAPHY\n",
                "additional-preamble": "\\OSBIBLIOGRAPHY\n",
            },
        )
        self.assertLess(out.index(r"\usepackage{reledmac}"), out.index(r"\OSTYPOGRAPHY"))
        self.assertLess(out.index(r"\newcommand{\OSMeasure}"), out.index(r"\OSTYPOGRAPHY"))
        self.assertLess(out.index(r"\newcommand{\OSPstartSkip}"), out.index(r"\OSTYPOGRAPHY"))
        self.assertLess(out.index(r"\OSTYPOGRAPHY"), out.index(r"\OSBIBLIOGRAPHY"))
        self.assertLess(out.index(r"\OSTYPOGRAPHY"), out.index(r"\begin{document}"))

    def test_the_typography_parameters_are_required(self):
        """The stylesheet keeps no default of its own to fall back on (#249)."""
        from opensiddur.common.xslt import xslt_transform_string
        from opensiddur.exporter.tex.latex import XSLT_FILE

        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        params = stylesheet_parameters(xml)
        del params["typography-preamble"]
        with self.assertRaisesRegex(Exception, "required parameter typography-preamble"):
            xslt_transform_string(XSLT_FILE, xml, xslt_params=params)

    def test_preamble_bookmarks_four_levels_deep(self):
        """The deeper heading levels (index > section > haftarah > rite) must reach the PDF
        outline. The book class stops the table of contents at subsection and hyperref
        follows it, which silently drops anything deeper.
        """
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\setcounter{tocdepth}{4}", out)
        self.assertIn("bookmarksdepth=4", out)

    def test_a_fourth_level_head_gets_its_own_macro_and_outline_entry(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div><tei:head>Humash</tei:head>
              <tei:div><tei:head>Haftarot</tei:head>
                <tei:div><tei:head>Bereshit</tei:head>
                  <tei:div><tei:head>Ashkenaz</tei:head><tei:p>Hi</tei:p></tei:div>
                </tei:div>
              </tei:div>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\OSheadD{", out)
        self.assertIn(r"\addcontentsline{toc}{paragraph}", out)

    def test_a_fifth_level_head_stays_at_the_fourth(self):
        """Nesting deeper than the macros go must not fall off the end of the sequence."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div><tei:head>One</tei:head>
              <tei:div><tei:head>Two</tei:head>
                <tei:div><tei:head>Three</tei:head>
                  <tei:div><tei:head>Four</tei:head>
                    <tei:div><tei:head>Five</tei:head><tei:p>Hi</tei:p></tei:div>
                  </tei:div>
                </tei:div>
              </tei:div>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn("english}{Five}", out)
        self.assertNotIn("OSheadE", out)

    def test_a_third_level_head_is_added_to_the_outline(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div><tei:head>Humash</tei:head>
              <tei:div><tei:head>Genesis</tei:head>
                <tei:div><tei:head>Bereshit</tei:head><tei:p>Hi</tei:p></tei:div>
              </tei:div>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\addcontentsline{toc}{subsubsection}", out)

    def test_a_direction_switch_is_gobbled_whole_in_pdf_strings(self):
        """\textdir takes three letter tokens (TLT). A one-argument gobble leaves "LT" in
        the bookmark, in front of every non-Hebrew title."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\def\textdir#1#2#3{}", out)


class TestSingleStreamMapping(unittest.TestCase):
    """Single-language documents (no p:parallel) must still produce a valid
    \\beginnumbering...\\endnumbering block. When there is no parallel alignment
    requirement, verses should flow inline (paragraph-like), not one line per verse."""

    XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
             xml:lang="en">
      <tei:text><tei:body>
        <tei:p>
          <tei:milestone unit="chapter" n="1"/>
          <tei:milestone unit="verse" n="1"/>In the beginning.
          <tei:milestone unit="verse" n="2"/>And the earth.
          <tei:milestone unit="verse" n="3"/>Let there be light.
        </tei:p>
      </tei:body></tei:text>
    </tei:TEI>"""

    def test_emits_single_numbering_block(self):
        out = _transform(self.XML)
        self.assertEqual(out.count(r"\beginnumbering"), 1)
        self.assertEqual(out.count(r"\endnumbering"), 1)

    def test_verses_flow_inline_in_single_stream(self):
        out = _transform(self.XML)
        # The fixture has one tei:p containing 3 verse milestones, so we expect
        # one verse-paragraph-level \\pstart/\\pend pair (not 1 per verse).
        #
        # The chapter milestone is not in a div[@type='book'], so it emits nothing
        # and does not open a pstart of its own.
        self.assertEqual(out.count(r"\pstart\relax \vno{"), 1)
        self.assertEqual(out.count(r"\pend"), 1)

    def test_chapter_milestone_is_not_a_section(self):
        """Chapter milestones must never become LaTeX sections: the book class would
        auto-number them ("0.1") and the heading is unwanted in liturgical texts."""
        out = _transform(self.XML)
        self.assertNotIn(r"\eledsection", out)
        self.assertNotIn(r"\eledchapter", out)
        self.assertNotIn(r"\eledsubsection", out)

    def test_chapter_milestone_outside_a_book_renders_nothing(self):
        out = _transform(self.XML)
        # \chno is always *defined* in the preamble; assert it is never *used*.
        body = out.split(r"\begin{document}", 1)[1]
        self.assertNotIn(r"\chno", body)

    def test_chapter_milestone_inside_a_book_emits_inline_number(self):
        """In a Bible export the chapter exists only as a milestone, so it must stay
        visible — as an inline marker, not a heading."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>
            <tei:div type="book">
              <tei:p>
                <tei:milestone unit="chapter" n="1"/>
                <tei:milestone unit="verse" n="1"/>In the beginning.
              </tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        # Chapter numbers are forced LTR to avoid digit reversal in RTL contexts.
        self.assertIn(r"\chno{{\textdir TLT\foreignlanguage{english}{1}}}", out)
        self.assertNotIn(r"\eledsection", out)

    def test_chapter_number_forces_ltr_digits_in_hebrew_context(self):
        """Digits inside Hebrew RTL contexts can render reversed unless forced LTR."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div type="book">
              <tei:p>
                <tei:milestone unit="chapter" n="12"/>
                <tei:milestone unit="verse" n="1"/>טקסט
              </tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\chno{{\textdir TLT\foreignlanguage{english}{12}}}", out)

    def test_chapter_milestone_inside_a_parallel_column_still_emits_its_number(self):
        """The book div now lives *inside* each column, not around the p:parallel.

        Chapter numbers are gated on ancestor::tei:div[@type='book'], so the compiler
        reproducing that div inside each p:parallelItem (stamped p:part when the div is
        split across rows) is what keeps the gate satisfied in parallel mode. If the div
        were hoisted away to flatten the blocks instead, \\chno would silently vanish.
        """
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">
                <tei:div type="book" p:part="first">
                  <tei:p>
                    <tei:milestone unit="chapter" n="3"/>
                    <tei:milestone unit="verse" n="1"/>טקסט
                  </tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div type="book" p:part="first">
                  <tei:p>
                    <tei:milestone unit="chapter" n="3"/>
                    <tei:milestone unit="verse" n="1"/>Text
                  </tei:p>
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, layout="pairs")
        self.assertIn(r"\chno{{\textdir TLT\foreignlanguage{english}{3}}}", out)
        # ...and it is genuinely the two-column path, not the linear fallback.
        self.assertIn(r"\begin{pairs}", out)
        self.assertIn(r"\Columns", out)

    def test_verse_numbers_appear_as_superscripts(self):
        out = _transform(self.XML)
        # The \vno{} command renders as a superscript prefix.
        self.assertIn(r"\vno{1}", out)
        self.assertIn(r"\vno{2}", out)
        self.assertIn(r"\vno{3}", out)


class TestHebrewVerseNumbers(unittest.TestCase):
    def test_hebrew_labels_keep_logical_order_and_decimal_labels_stay_ltr(self):
        passage = '<tei:p>' + ''.join(
            f'<tei:milestone unit="verse" n="{n}"/>Text '
            for n in ('יא', 'טו', 'עו', '12', '76')) + '</tei:p>'
        for parallel in (False, True):
            with self.subTest(parallel=parallel):
                body = passage
                if parallel:
                    body = ('<p:parallel><p:parallelItem role="primary" xml:lang="he">'
                            + passage + '</p:parallelItem>'
                            '<p:parallelItem role="parallel" xml:lang="en">'
                            + passage + '</p:parallelItem></p:parallel>')
                xml = ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" '
                       'xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">'
                       '<tei:text><tei:body>' + body + '</tei:body></tei:text></tei:TEI>')
                out = _transform(xml, layout="pairs")
                for n in ('יא', 'טו', 'עו'):
                    self.assertIn(r"\vno{\texthebrew{" + n + '}}', out)
                    self.assertNotIn(r"\vno{" + n + '}', out)
                for n in ('12', '76'):
                    self.assertIn(r"\vno{" + n + '}', out)
                self.assertIn(r"\textdir TLT\foreignlanguage{english}{#1}", out)


class TestParallelMapping(unittest.TestCase):
    """Parallel blocks must produce two synchronized streams, both wrapped
    in \\beginnumbering...\\endnumbering, surrounded by
    \\begin{pages}/\\end{pages} (or \\begin{pairs}) and ended with the
    matching reledpar typesetter command."""

    XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
             xmlns:p="http://jewishliturgy.org/ns/processing"
             xml:lang="he">
      <tei:text><tei:body>
        <p:parallel column-order="primary_first">
          <p:parallelItem role="primary" xml:lang="he">
            <tei:p>
              <tei:milestone unit="chapter" n="1"/>
              <tei:milestone unit="verse" n="1"/>בראשית.
              <tei:milestone unit="verse" n="2"/>והארץ.
              <tei:milestone unit="verse" n="3"/>ויאמר.
            </tei:p>
          </p:parallelItem>
          <p:parallelItem role="parallel" xml:lang="en">
            <tei:p>
              <tei:milestone unit="chapter" n="1"/>
              <tei:milestone unit="verse" n="1"/>In the beginning.
              <tei:milestone unit="verse" n="2"/>And the earth.
              <tei:milestone unit="verse" n="3"/>Let there be light.
            </tei:p>
          </p:parallelItem>
        </p:parallel>
      </tei:body></tei:text>
    </tei:TEI>"""

    def test_emits_pages_environment_for_facing_pages(self):
        out = _transform(self.XML, layout="pages")
        self.assertIn(r"\begin{pages}", out)
        self.assertIn(r"\end{pages}", out)
        self.assertIn(r"\Pages", out)
        self.assertIn(r"\begin{Leftside}", out)
        self.assertIn(r"\begin{Rightside}", out)

    def test_defaults_to_columns_like_the_settings_model(self):
        """The stylesheet's own default is ParallelTypographyConfig's, so a caller that
        passes no layout gets what a settings file that names none gets."""
        out = _transform(self.XML)
        self.assertIn(r"\begin{pairs}", out)
        self.assertNotIn(r"\begin{pages}", out)

    def test_the_blank_page_before_a_spread_carries_no_running_head(self):
        r"""\Pages inserts a blank recto to start its spread on a verso, in \prevpgstyle
        when that is defined and in the running-head style otherwise."""
        self.assertIn(r"\def\prevpgstyle{empty}", _transform(self.XML, layout="pages"))
        self.assertNotIn(r"\prevpgstyle", _transform(self.XML, layout="pairs"))

    def test_facing_pages_build_their_rows_left_to_right(self):
        r"""\Pages builds a Hebrew page's rows right to left, which puts the left margin's
        line numbers over the first word of every line. \ledstrutL/R open every row it
        builds, and only \Pages uses them."""
        pages = _transform(self.XML, layout="pages")
        self.assertIn(r"\renewcommand*{\ledstrutL}{\textdir TLT\relax}", pages)
        self.assertIn(r"\renewcommand*{\ledstrutR}{\textdir TLT\relax}", pages)
        self.assertNotIn(r"\ledstrut", _transform(self.XML, layout="pairs"))

    def test_empty_parallel_block_is_skipped(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:p/></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:p/></p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, layout="pages")
        self.assertNotIn(r"\begin{pages}", out)

    def test_parallel_inside_transclude_is_still_grouped(self):
        """The compiled XML can wrap p:parallel blocks in p:transclude; the TeX stage
        must expand the wrapper so parallel blocks still become a reledpar environment."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:transclude target="urn:x-opensiddur:test" type="external">
              <p:parallel column-order="primary_first">
                <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
                <p:parallelItem role="parallel" xml:lang="en"><tei:p>Hello</tei:p></p:parallelItem>
              </p:parallel>
            </p:transclude>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, layout="pairs")
        self.assertIn(r"\begin{pairs}", out)
        self.assertIn(r"\begin{Leftside}", out)
        self.assertIn(r"\begin{Rightside}", out)

    def test_nested_transclude_parallels_are_grouped_into_one_pages_run(self):
        """Wrapper expansion must recurse.

        Parallel blocks end at every external transclusion, so a transcluded document that
        itself transcludes nests p:transclude wrappers. A single-level expansion leaves the
        inner wrapper in the flow, where it groups as 'inline' and splits the \\Pages run.
        """
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:transclude target="urn:outer" type="external">
              <p:parallel column-order="primary_first">
                <p:parallelItem role="primary" xml:lang="he"><tei:p>אחד</tei:p></p:parallelItem>
                <p:parallelItem role="parallel" xml:lang="en"><tei:p>One</tei:p></p:parallelItem>
              </p:parallel>
              <p:transclude target="urn:inner" type="external">
                <p:parallel column-order="primary_first">
                  <p:parallelItem role="primary" xml:lang="he"><tei:p>שנים</tei:p></p:parallelItem>
                  <p:parallelItem role="parallel" xml:lang="en"><tei:p>Two</tei:p></p:parallelItem>
                </p:parallel>
              </p:transclude>
              <p:parallel column-order="primary_first">
                <p:parallelItem role="primary" xml:lang="he"><tei:p>שלשה</tei:p></p:parallelItem>
                <p:parallelItem role="parallel" xml:lang="en"><tei:p>Three</tei:p></p:parallelItem>
              </p:parallel>
            </p:transclude>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, layout="pages")
        self.assertEqual(out.count(r"\begin{pages}"), 1,
                         "all three blocks belong to a single \\Pages run")
        self.assertIn("Two", out, "the nested transclusion's content must be typeset")

    def test_english_column_not_wrapped_in_hebrew_env(self):
        """The English stream must not inherit the Hebrew stream's RTL environment.

        Regression for the reported symptom: nested parallels were flattened into the Hebrew
        column by the mode="leaves" safety net, so Latin text rendered reversed.
        """
        out = _transform(self.XML, layout="pairs")
        right = re.search(r"\\begin\{Rightside\}(.*?)\\end\{Rightside\}", out, re.DOTALL)
        self.assertIsNotNone(right)
        self.assertIn("In the beginning", right.group(1))
        self.assertNotIn(r"\begin{hebrew}", right.group(1))

    def test_second_column_records_into_the_alt_mark_classes(self):
        """A running head must be able to name either language's heading, so the
        two columns cannot share one set of mark classes."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing"
                 xml:lang="he">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">
                <tei:div type="book"><tei:head>בראשית</tei:head><tei:p>טקסט</tei:p></tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div type="book"><tei:head>GENESIS</tei:head><tei:p>Text</tei:p></tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\InsertMark{OSbook}{\texthebrew{בראשית}}", out)
        self.assertIn(
            r"\InsertMark{OSbookAlt}{{\textdir TLT\foreignlanguage{english}{GENESIS}}}", out
        )
        self.assertIn(r"\InsertMark{OSheadAAlt}{", out)

    def test_chapter_milestone_records_a_mark_without_opening_a_pstart(self):
        """reledpar pairs the two sides by \\pstart count, so a mark must never
        open one of its own."""
        out = _transform(self.XML)
        self.assertIn(
            r"\InsertMark{OSchapter}{{\textdir TLT\foreignlanguage{english}{1}}}", out
        )
        self.assertNotIn(r"}}\pstart", out)

    def test_chapter_number_mark_forces_ltr_digits(self):
        """A slot declaring Hebrew forces RTL, and \\textdir forces a direction
        rather than running the bidi algorithm, so bare digits are laid out
        right to left and chapter 50 reads "05"."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div type="book"><tei:head>בראשית</tei:head>
              <tei:p><tei:milestone unit="chapter" n="50"/>טקסט</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(
            r"\InsertMark{OSchapter}{{\textdir TLT\foreignlanguage{english}{50}}}", out
        )

    def test_pairs_layout_uses_columns_typesetter(self):
        out = _transform(self.XML, layout="pairs")
        self.assertIn(r"\begin{pairs}", out)
        self.assertIn(r"\Columns", out)
        self.assertNotIn(r"\begin{pages}", out)
        self.assertNotIn(r"\Pages", out)

    def test_pairs_layout_line_numbers_on_outer_column_margins(self):
        """Leftside is the physical left column; Rightside is the physical right column.
        Both margins {right} regresses Hebrew numbers into the gutter."""
        out = _transform(self.XML, layout="pairs")
        self.assertIn(r"\linenummarginColumns{left}", out)
        self.assertIn(r"\linenummarginColumnsR{right}", out)

    def test_both_series_are_numbered_by_page(self):
        r"""\lineation sets the main series only. reledpar keeps a separate \bypage@R
        which defaults to false, so without \lineationR the right column numbers by
        section and runs on unbroken -- measured at 320 by page 11 of the Amidah."""
        for layout in ("pairs", "pages"):
            out = _transform(self.XML, layout=layout)
            self.assertIn(r"\lineation{page}", out, layout)
            self.assertIn(r"\lineationR{page}", out, layout)

    def test_lineation_is_declared_before_numbering_opens(self):
        r"""Both abort with \led@err@LineationInNumbered if called once numbering is open,
        so they have to stay in the preamble."""
        out = _transform(self.XML, layout="pairs")
        self.assertLess(out.index(r"\lineationR{page}"), out.index(r"\begin{document}"))

    def test_line_numbers_lap_outward_in_either_direction(self):
        r"""A lap is built in horizontal mode and so takes the prevailing \textdir; in the
        Hebrew column that plants the number inside the measure instead of outside it. A
        zero-width box sits in the same place either way."""
        out = _transform(self.XML, layout="pairs")
        self.assertIn(
            r"\renewcommand*{\leftlinenum}{\hbox dir TLT to \z@"
            r"{\hss\ledlinenum\kern\linenumsep}}", out)
        self.assertIn(
            r"\renewcommand*{\rightlinenum}{\hbox dir TLT to \z@"
            r"{\kern\linenumsep\ledlinenum\hss}}", out)
        self.assertIn(r"\renewcommand*{\leftlinenumR}", out)
        self.assertIn(r"\renewcommand*{\rightlinenumR}", out)

    def test_lines_may_stretch_rather_than_overrun_the_measure(self):
        r"""At a parallel column's measure TeX often prefers an overfull line, which sticks
        out into the margin the numbers occupy. 73 lines did so in the Amidah."""
        self.assertIn(r"\setlength{\emergencystretch}{3em}", _transform(self.XML))

    def test_pairs_layout_forces_ltr_for_columns_assembly(self):
        r"""Avoid RTL \pardir flipping the visual order of the two-column row."""
        out = _transform(self.XML, layout="pairs")
        self.assertIn(r"\let\OSreledparColumnsOrig\Columns", out)
        self.assertIn(r"\pardir TLT\relax\textdir TLT\relax\OSreledparColumnsOrig", out)

    def test_each_side_has_its_own_numbering(self):
        out = _transform(self.XML)
        # One \beginnumbering per side, one \endnumbering per side.
        self.assertEqual(out.count(r"\beginnumbering"), 2)
        self.assertEqual(out.count(r"\endnumbering"), 2)

    def test_pstart_counts_match_across_streams(self):
        """The two streams must emit the SAME number of \\pstart markers,
        else reledpar can't pair them by position."""
        out = _transform(self.XML)
        # Block-level pstart/pend: one per side (one parallel block).
        self.assertEqual(out.count(r"\pstart"), 2)
        self.assertEqual(out.count(r"\pend"), 2)

    def test_pstart_pair_count_matches_verse_count_per_side(self):
        """Within each side's numbering block, we use one block-level \\pstart,
        while verse numbers remain inline via \\vno{n}."""
        out = _transform(self.XML)
        left_match = re.search(
            r"\\begin\{Leftside\}(.*?)\\end\{Leftside\}", out, re.DOTALL
        )
        right_match = re.search(
            r"\\begin\{Rightside\}(.*?)\\end\{Rightside\}", out, re.DOTALL
        )
        self.assertIsNotNone(left_match)
        self.assertIsNotNone(right_match)
        self.assertEqual(left_match.group(1).count(r"\pstart"), 1)
        self.assertEqual(right_match.group(1).count(r"\pstart"), 1)
        for n in ("1", "2", "3"):
            self.assertIn(rf"\vno{{{n}}}", left_match.group(1))
            self.assertIn(rf"\vno{{{n}}}", right_match.group(1))

    def test_column_order_swaps_streams(self):
        """primary_last puts the parallel (English) stream on the left."""
        xml = self.XML.replace('column-order="primary_first"', 'column-order="primary_last"')
        out = _transform(xml)
        left_match = re.search(
            r"\\begin\{Leftside\}(.*?)\\end\{Leftside\}", out, re.DOTALL
        )
        self.assertIsNotNone(left_match)
        # Hebrew text should now be on the right, English on the left.
        self.assertIn("In the beginning", left_match.group(1))
        self.assertNotIn("בראשית", left_match.group(1))

    def test_hebrew_stream_is_wrapped_in_polyglossia_block(self):
        """Hebrew streams need to be inside a hebrew environment so direction
        and font are picked up everywhere inside numbering."""
        out = _transform(self.XML)
        # Look at the Leftside (which is Hebrew when column-order=primary_first
        # and the primary lang=he).
        left_match = re.search(
            r"\\begin\{Leftside\}(.*?)\\end\{Leftside\}", out, re.DOTALL
        )
        self.assertIsNotNone(left_match)
        self.assertIn(r"\begin{hebrew}", left_match.group(1))
        self.assertIn(r"\end{hebrew}", left_match.group(1))

    def test_parallel_row_after_marker_reconstruct(self):
        """After marker reconstruction, the XSLT must still emit a pages-based
        parallel wrapper with two numbering streams (one per side). This test
        belongs with the XSLT structural invariants, not with reconstruction
        mechanics.
        """
        tei_ns = "http://www.tei-c.org/ns/1.0"
        p_ns = "http://jewishliturgy.org/ns/processing"
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="{tei_ns}" xmlns:p="{p_ns}">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:p>Hello</tei:p></p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        root = etree.fromstring(xml.encode("utf-8"))
        reconstruct_markered_document(root)
        out = _transform(etree.tostring(root, encoding="unicode"), layout="pages")

        self.assertIn(r"\begin{pages}", out)
        self.assertIn(r"\Pages", out)
        self.assertEqual(out.count(r"\beginnumbering"), 2)
        self.assertEqual(out.count(r"\endnumbering"), 2)
        self.assertIn("שלום", out)
        self.assertIn("Hello", out)


class TestNotesMapping(unittest.TestCase):
    """Body ``tei:note`` elements (materialized by the compiler) become reledmac
    apparatus footnotes via ``\\edtext{...}{\\Bfootnote{...}}``. ``tei:standOff``
    is not expanded at the TeX stage. Instructional notes use ``\\instructionnote``.
    """

    def test_default_note_is_b_series_apparatus(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>Body<tei:note>commentary</tei:note>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        # \edtext{\OSInterlinearNotemark}{... \Bfootnote{\OSFootnotemark ...}}: interlinear
        # serial mark + B-series footnote at page bottom (not an endnote after \pend).
        self.assertIn(r"\leavevmode{\OSRTLfalse\edtext{\OSInterlinearNotemark{1}}{\Bfootnote{\OSFootnotemark{1}\notenote{", out)
        self.assertIn("commentary", out)
        self.assertNotIn(r"\footnote{", out)

    def test_an_anchor_emits_the_note_the_compiler_put_inside_it(self):
        """A standoff note reaches the text as a child of the anchor it targets.

        The template for tei:anchor used to be empty, on the premise that an anchor
        carries no text of its own. It does not, but the compiler puts the note it is
        the target of inside it, so an empty template built the note and then dropped
        it: no mark, and an apparatus one note short, with nothing anywhere saying so.
        """
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>Body<tei:anchor xml:id="a1"
              ><tei:note>from the apparatus</tei:note></tei:anchor>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn("from the apparatus", out)
        self.assertIn(r"\Bfootnote{", out)

    def test_notes_can_be_collected_as_endnotes(self):
        """The apparatus series is the same; only where it is printed changes."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>Body<tei:note>commentary</tei:note>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, **{"notes-placement": "endnote"})
        self.assertIn(r"\Bendnote{", out)
        self.assertNotIn(r"\Bfootnote{", out)
        # Collected as the document is typeset, so they have to be printed out.
        self.assertIn(r"\doendnotes{B}", out)
        self.assertLess(out.index(r"\doendnotes{B}"), out.index(r"\end{document}"))

    def test_notes_can_be_dropped_entirely(self):
        """Anchor and all: a mark pointing at a note that is not printed would
        be worse than no note."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>Body<tei:note>commentary</tei:note>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, **{"notes-placement": "none"})
        self.assertNotIn("commentary", out)
        self.assertNotIn(r"\Bfootnote", out)
        # The macro is still defined in the preamble, which costs nothing; what
        # must be gone is every call to it.
        body = out[out.index(r"\begin{document}"):]
        self.assertNotIn(r"\OSInterlinearNotemark", body)

    def test_note_marks_can_be_drawn_from_another_series(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>A<tei:note>one</tei:note>
            B<tei:note>two</tei:note>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        alpha = _transform(xml, **{"notes-mark": "alpha"})
        self.assertIn(r"\OSInterlinearNotemark{a}", alpha)
        self.assertIn(r"\OSInterlinearNotemark{b}", alpha)

        roman = _transform(xml, **{"notes-mark": "roman"})
        self.assertIn(r"\OSInterlinearNotemark{i}", roman)
        self.assertIn(r"\OSInterlinearNotemark{ii}", roman)

        symbol = _transform(xml, **{"notes-mark": "symbol"})
        self.assertIn(r"\OSInterlinearNotemark{\textasteriskcentered}", symbol)
        self.assertIn(r"\OSInterlinearNotemark{\textdagger}", symbol)

    def test_the_symbol_series_repeats_once_it_runs_out(self):
        """Six symbols, then the same symbols doubled — how a printed apparatus
        has always done it."""
        notes = "".join(
            f'<tei:note>n{i}</tei:note>' for i in range(1, 9)
        )
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>Body{notes}
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, **{"notes-mark": "symbol"})
        self.assertIn(r"\OSInterlinearNotemark{\textparagraph}", out)
        self.assertIn(
            r"\OSInterlinearNotemark{\textasteriskcentered\textasteriskcentered}", out
        )

    def test_instruction_note_is_inline(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>Body<tei:note type="instruction">stand</tei:note>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\instructionnote{", out)
        self.assertIn("stand", out)

    def test_a_description_is_set_as_a_rubric_and_takes_no_note_number(self):
        """A description is set exactly as an instruction is (JLPTEI-3, *Kinds of rubric*)."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/><tei:note type="description">Reader:</tei:note>Body
            <tei:note>A comment.</tei:note>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\instructionnote{", out)
        self.assertIn("Reader:", out)
        self.assertNotIn(r"\OSInterlinearNotemark{2}", out)
        self.assertIn(r"\OSInterlinearNotemark{1}", out)

    def test_a_cross_direction_instruction_is_not_put_in_a_fixed_width_box(self):
        r"""An \hbox to \linewidth cannot break, so a rubric wider than it overhangs
        instead of wrapping. \linewidth inside reledpar's parallel setting is the page
        rather than the column, so the box was twice the width it had to fit in and every
        long rubric ran off the paper in a two-column compile. Ordinary text flow is
        measured by whatever column it lands in."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div>
              <tei:note type="instruction" xml:lang="en">Between Rosh Hashanah and Yom Kippur substitute:</tei:note>
              <tei:p>שלום</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        definitions = [
            line for line in out.splitlines()
            if r"\newcommand{\OSInstruction" in line
        ]
        self.assertEqual(2, len(definitions))
        for definition in definitions:
            self.assertNotIn(r"\hbox to \linewidth", definition)
            self.assertNotIn(r"\parbox", definition)

    def test_a_cross_direction_instruction_still_gets_its_own_line(self):
        """Why the macros exist at all: an English rubric and the Hebrew it introduces run
        from opposite margins, so sharing a line would read as one jumbled line."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div>
              <tei:note type="instruction" xml:lang="en">Between Sukkoth and Pesah add:</tei:note>
              <tei:p>שלום</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\OSInstructionBlock{", out)
        definition = [
            line for line in out.splitlines()
            if r"\newcommand{\OSInstructionBlock}" in line
        ][0]
        self.assertIn(r"\newline", definition)

    def test_an_instruction_running_with_the_text_needs_no_line_of_its_own(self):
        """Same direction, so it can share the line and keeps the plain inline macro."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>
            <tei:div>
              <tei:note type="instruction" xml:lang="en">Stand.</tei:note>
              <tei:p>Blessed art thou.</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\instructionnote{", out)
        self.assertNotIn(r"\OSInstructionBlock{", out)

    def test_a_rubric_inheriting_its_language_is_still_set_in_that_direction(self):
        r"""A rubric written in the language around it carries no @xml:lang of its own, as
        every Hebrew rubric in the Heidenheim haggadah does not. Pairing the two columns
        copies the note out of its tree to stamp it, which severs the ancestors the
        inherited language was read from, so it fell to the LTR branch and was typeset left
        to right -- `בזימון` reading backwards on the page. The language pairing records on
        the note is what survives that copy."""
        out = _transform(self._rubric_in_parallel("he", "בזימון"))
        self.assertIn(r"\textdir TRT\foreignlanguage{hebrew}{בזימון}", out)
        self.assertNotIn(r"\foreignlanguage{english}{בזימון}", out)

    def test_a_rubric_is_placed_by_its_direction_not_by_being_hebrew(self):
        r"""The same reason f:is-rtl-lang exists: Yiddish is written in the same script and
        reverses the same way. Testing the language for `he` alone also put this rubric's
        direction at odds with the macro chosen for it, which asks f:is-rtl-lang -- so it
        both shared the line with the Hebrew and ran against it."""
        out = _transform(self._rubric_in_parallel("yi", "רבותי"))
        self.assertIn(r"\textdir TRT\foreignlanguage{hebrew}{רבותי}", out)
        self.assertNotIn(r"\foreignlanguage{english}{רבותי}", out)

    @staticmethod
    def _rubric_in_parallel(lang: str, rubric: str) -> str:
        """One Hebrew-script column facing an English one, the rubric taking its language
        from the column rather than stating one."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="{lang}">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="{lang}">
                <tei:div>
                  <tei:note type="instruction">{rubric}</tei:note>
                  <tei:p>שלום</tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div><tei:p>Hello</tei:p></tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""

    def test_body_editorial_note_emits_apparatus(self):
        """Compiler inlines editorial tei:note in the body; XSLT maps it to B-series."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:p>
              <tei:milestone unit="verse" n="1"/>
              Hebrew text<tei:note xml:lang="en">English annotation</tei:note> more
            </tei:p>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\leavevmode{\OSRTLfalse\edtext{\OSInterlinearNotemark{1}}{\Bfootnote{\OSFootnotemark{1}\notenote{", out)
        self.assertIn("English annotation", out)
        self.assertIn(r"{{\textdir TLT\foreignlanguage{english}{", out)

    def test_standoff_not_resolved_at_tex_stage(self):
        """tei:standOff is not expanded here; only body notes become apparatus."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:p>
              <tei:milestone unit="verse" n="1"/>
              Hebrew text<tei:anchor xml:id="note-ref-1"/> more text
            </tei:p>
          </tei:body></tei:text>
          <tei:standOff type="notes" xml:lang="en">
            <tei:note target="#note-ref-1">StandOff only.</tei:note>
          </tei:standOff>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertNotIn("StandOff only.", out)
        self.assertNotIn(r"\leavevmode{\OSRTLfalse\edtext", out)

    def test_inline_note_with_standoff_duplicate_emits_once(self):
        """Body note plus matching tei:standOff (compiler leaves both) must not double TeX."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:p>
              <tei:milestone unit="verse" n="1"/>
              Hebrew<tei:note xml:lang="en">Transcription uncertain.</tei:note><tei:anchor xml:id="a1"/>after
            </tei:p>
          </tei:body></tei:text>
          <tei:standOff type="notes" xml:lang="en">
            <tei:note target="#a1">Transcription uncertain.</tei:note>
          </tei:standOff>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertEqual(out.count("Transcription uncertain."), 1)
        self.assertEqual(out.count(r"\leavevmode{\OSRTLfalse\edtext{\OSInterlinearNotemark{1}"), 1)

    def test_two_body_editorial_notes_distinct_serials(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:p>
              <tei:milestone unit="verse" n="1"/>
              A<tei:note xml:lang="en">First</tei:note> B<tei:note xml:lang="en">Second</tei:note>
            </tei:p>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\OSInterlinearNotemark{1}", out)
        self.assertIn(r"\OSInterlinearNotemark{2}", out)
        self.assertEqual(out.count("First"), 1)
        self.assertEqual(out.count("Second"), 1)

    def test_parallel_body_note_per_column(self):
        """Each parallel stream numbers its own editorial notes from 1."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:p>
                <tei:milestone unit="verse" n="1"/>א<tei:note xml:lang="en">Heb note</tei:note>
              </tei:p></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:p>
                <tei:milestone unit="verse" n="1"/>A<tei:note>Eng note</tei:note>
              </tei:p></p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        left = re.search(r"\\begin\{Leftside\}(.*?)\\end\{Leftside\}", out, re.DOTALL)
        right = re.search(r"\\begin\{Rightside\}(.*?)\\end\{Rightside\}", out, re.DOTALL)
        self.assertIsNotNone(left)
        self.assertIsNotNone(right)
        self.assertIn(r"\OSInterlinearNotemark{1}", left.group(1))
        self.assertIn("Heb note", left.group(1))
        # Editorial serials count preceding notes in document order (Leftside before Rightside).
        self.assertIn(r"\OSInterlinearNotemark{2}", right.group(1))
        self.assertIn("Eng note", right.group(1))

    def test_note_language_forces_direction(self):
        """Notes must force their own direction based on the in-scope xml:lang.

        In practice we do this by wrapping note content with polyglossia
        helpers: \textenglish{...} and \texthebrew{...}.
        """
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace">
          <tei:text><tei:body>
            <tei:p xml:lang="he">
              עברית<tei:note xml:lang="en">English note</tei:note>
              <tei:note type="instruction" xml:lang="en">Inline English instruction</tei:note>
            </tei:p>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"{{\textdir TLT\foreignlanguage{english}{English note}}}", out)
        self.assertIn(r"{{\textdir TLT\foreignlanguage{english}{Inline English instruction}}}", out)

    def test_hebrew_note_wraps_embedded_latin_siglum(self):
        """MAM apparatus notes are Hebrew prose that embeds Latin manuscript
        sigla, e.g. "פטרבורג-EVR-II-B-8". \\textdir TRT forces the whole note
        into strict RTL, which has no per-run bidi detection, so an embedded
        Latin token renders back-to-front unless it gets its own explicit LTR
        override — same as digits already get in \\vno/\\chno."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace">
          <tei:text><tei:body>
            <tei:p>
              <tei:milestone unit="verse" n="1"/>טקסט<tei:note xml:lang="he">פטרבורג-EVR-II-B-8 ומ""ג</tei:note>
            </tei:p>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"{{\textdir TLT\foreignlanguage{english}{EVR-II-B-8}}}", out)
        # The hyphen joining the Hebrew word to the siglum stays outside the
        # wrap; only the Latin/digit token itself is switched to LTR.
        self.assertIn("פטרבורג-{{\\textdir TLT\\foreignlanguage{english}{EVR-II-B-8}}}", out)

    def test_pure_hebrew_note_has_no_spurious_latin_wrap(self):
        """Hebrew abbreviation punctuation (ASCII gershayim, e.g. מ""ג) must
        not be mistaken for a Latin run: it contains no [A-Za-z0-9], so it
        should pass through unwrapped."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace">
          <tei:text><tei:body>
            <tei:p>
              <tei:milestone unit="verse" n="1"/>טקסט<tei:note xml:lang="he">וכך מ""ג ודותן</tei:note>
            </tei:p>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertNotIn(r"\textdir TLT", out.split(r"\notenote{", 1)[1])

    def test_english_context_latin_text_not_double_wrapped(self):
        """Latin text already in an LTR (English) context must go through
        plain escaping, not the Hebrew-context bidi wrapper — that would be
        redundant with note-content's own English-note wrap."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
          <tei:text><tei:body>
            <tei:p>
              <tei:milestone unit="verse" n="1"/>Manuscript EVR-II-B-8 is cited here.
            </tei:p>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertNotIn(r"\textdir TLT\foreignlanguage{english}{EVR-II-B-8", out)
        self.assertIn("EVR-II-B-8", out)


class TestSourceWhitespaceIsNotAParagraphBreak(unittest.TestCase):
    r"""Pretty-printing whitespace must never come out as a blank line.

    The stylesheet separates paragraphs with an explicit ``\par`` or ``\newline``,
    never with a blank line, so a blank line in a numbered stream is always an
    accident of how the source happens to be indented. It is not a harmless one:
    a note that annotates the block after it is emitted as
    ``\leavevmode{...\edtext{\OSInterlinearNotemark{n}}...}``, which has already
    opened the paragraph, so a ``\par`` behind it spends a row on the mark alone
    and starts the text on the next line. In a parallel block the facing column
    discards the same whitespace in vertical mode and does not spend that row, so
    the two columns drift apart by a line as well.

    The indentation in these fixtures is the thing under test; do not tidy it.
    """

    @staticmethod
    def _document_body(tex: str) -> str:
        return tex.split(r"\begin{document}", 1)[1]

    def _transform_body(self, body: str, **params) -> str:
        return _transform(
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                     xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
              <tei:text><tei:body>{body}</tei:body></tei:text>
            </tei:TEI>""",
            **params,
        )

    def test_a_note_anchor_is_not_separated_from_the_text_it_annotates(self):
        """The note is a preceding sibling of the paragraph it annotates, which is
        how a standoff note targeting a whole block is compiled in."""
        out = self._transform_body(
            """<tei:div><tei:note>Psalm 34:4.</tei:note>
            <tei:p>
            Exalt the Lord with me, and let us extol his name together.
            </tei:p></tei:div>"""
        )
        body = self._document_body(out)
        self.assertNotRegex(body, r"\}\}\}\}[ \t]*\n[ \t]*\n")
        # Exactly one newline between the closed anchor and the text: a space, not a \par.
        self.assertRegex(body, r"\\notenote\{.*?\}{4,}\nExalt the Lord with me")

    def test_a_note_anchor_is_not_separated_from_the_instruction_it_precedes(self):
        """Same shape, but a rubric follows. In the text's own language the rubric
        is the inline ``\\instructionnote``, so nothing else would end the line."""
        out = self._transform_body(
            """<tei:div><tei:note>On the institution of the reading.</tei:note>

            <tei:note type="instruction">The Torah is read on Mondays and Thursdays.</tei:note>
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertIn(r"\instructionnote{", body)
        self.assertNotRegex(body, r"\n[ \t]*\n[ \t]*\\instructionnote")
        self.assertRegex(body, r"\\notenote\{.*?\}{4,}\n\\instructionnote\{")

    def test_no_blank_line_survives_anywhere_in_a_stream(self):
        """The guard for the whole class, not just the note case."""
        out = self._transform_body(
            """<tei:div>
              <tei:head>A Heading</tei:head>
              <tei:note>A comment on what follows.</tei:note>
              <tei:p>
                First paragraph.
              </tei:p>

              <tei:note type="instruction">Reader and Congregation:</tei:note>

              <tei:p>
                Second paragraph.
              </tei:p>
            </tei:div>"""
        )
        stream = self._document_body(out)
        stream = stream.split(r"\beginnumbering", 1)[1].split(r"\endnumbering", 1)[0]
        self.assertIsNone(re.search(r"\n[ \t]*\n", stream))

    def test_whitespace_between_two_inline_leaves_stays_one_space(self):
        """The guard against over-fixing: a newline between two leaves is a space
        in TeX, and often the only thing separating two words. Collapsing a run of
        newlines must keep one, not drop them all."""
        out = self._transform_body(
            """<tei:p><tei:hi rend="italic">word</tei:hi>
            <tei:hi rend="italic">next</tei:hi></tei:p>"""
        )
        body = self._document_body(out)
        self.assertNotIn("wordnext", body)
        self.assertNotIn(r"}\OSHighlightItalic{next", body)
        # A single-newline run is left exactly as it was: the space survives.
        self.assertRegex(body, r"word\}\n[ \t]*\\OSHighlightItalic\{next")

    def test_the_postamble_keeps_its_blank_lines(self):
        """Why the collapse is scoped to a numbered stream and not applied to the
        whole document: the embedded bibliography ends every record with a blank line, and the
        licence block sets its paragraphs with them."""
        out = self._transform_body(
            "<tei:p>Text</tei:p>",
            **{"additional-postamble": "first\n\nsecond\n"},
        )
        self.assertIn("first\n\nsecond", out)


class TestSectionSeparator(unittest.TestCase):
    """A milestone[@rend='****'] separates sections that carry no heading."""

    XML = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:p>Before</tei:p>
            <tei:milestone unit="section" rend="****"/>
            <tei:p>After</tei:p>
          </tei:body></tei:text>
        </tei:TEI>"""

    def test_the_separator_goes_through_a_macro(self):
        """Through a macro, so a settings file can change the mark and its
        appearance without the stylesheet knowing what either is."""
        out = _transform(self.XML)
        body = out[out.index(r"\begin{document}"):]
        self.assertIn(r"\OSSectionSeparator", body)

    def test_the_default_macro_prints_what_it_always_printed(self):
        out = _transform(self.XML)
        self.assertIn(
            r"\newcommand{\OSSectionSeparator}{\OSSectionSeparatorStyle{* * * *}}", out
        )
        self.assertIn(
            r"\newcommand{\OSSectionSeparatorStyle}[1]{\begin{center}#1\end{center}}", out
        )


class TestApparatusCatchwordDirection(unittest.TestCase):
    r"""A Hebrew catchword inside an English note must be wrapped, or it renders reversed.

    `note-content` forces a direction on the whole note: an English commentary note is set
    inside `\textdir TLT`. A Hebrew run left bare inside that is laid out left to right, so
    `אהליך` came out as `דילהא` at the head of every lemma-keyed note in Birnbaum's
    apparatus — forty-seven of them.

    `tei:foreign[@xml:lang='he']` already had the wrapper. The catchword missed it because
    it is a quotation of the text rather than a foreign phrase, and so is a `tei:label`.

    Nothing else in the pass could see it: the note validates, `refdb` indexes it, the
    registry is clean, and `pdftotext` reorders an RTL run on output, so even reading the
    extracted text of the PDF shows it the right way round. It was found by looking at the
    rendered page.
    """

    def _note(self, label_lang="he", note_lang="en"):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="{note_lang}">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>text
            <tei:note type="commentary" xml:lang="{note_lang}"><tei:p>
              <tei:label xml:lang="{label_lang}">אהליך</tei:label> is glossed.
            </tei:p></tei:note>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""

    def test_a_hebrew_catchword_is_wrapped(self):
        out = _transform(self._note())
        self.assertIn(r"\texthebrew{אהליך}", out)

    def test_the_note_around_it_still_runs_left_to_right(self):
        out = _transform(self._note())
        self.assertIn(r"\textdir TLT", out)

    def test_a_yiddish_catchword_is_wrapped_too(self):
        """Matched on direction, not on `he`: Yiddish is the same script and the same
        problem."""
        out = _transform(self._note(label_lang="yi"))
        self.assertIn(r"\texthebrew{", out)

    def test_a_latin_catchword_is_not_wrapped(self):
        out = _transform(self._note(label_lang="en"))
        self.assertNotIn(r"\texthebrew{", out)


class TestInlineFormatting(unittest.TestCase):
    """Inline formatting elements that survived the compiler should map to
    appropriate LaTeX commands while staying inside the verse's \\pstart."""

    def test_small_caps(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>The <tei:hi rend="small-caps">Lord</tei:hi> said.
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\OSHighlightSmallCaps{Lord}", out)

    def test_kri_ktiv_choice(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>
            <tei:choice>
              <j:read>read</j:read>
              <j:written>written</j:written>
            </tei:choice>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\OSQere{read}", out)
        self.assertIn(r"(\OSKetiv{written})", out)

    def test_special_characters_are_tex_escaped(self):
        """LaTeX-special characters in body text must be escaped to avoid
        compilation failures in lualatex."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>50% of $5 &amp; #1
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"50\% of \$5 \& \#1", out)

    def test_lb_emits_leavevmode_linebreak(self):
        """tei:lb can appear at the start of a paragraph; we must ensure TeX is in
        horizontal mode before emitting \\\\ to avoid 'There's no line here to end.'"""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/><tei:lb/>Line 2
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\leavevmode\\{}", out)


class TestConditionalRendering(unittest.TestCase):
    """Only a conditional whose condition could not be decided reaches this stage.

    A decided condition is resolved away by the compiler, so a marker in the input means
    "say this only if ...", and the passage it governs has to be visibly delimited or the
    reader cannot tell how far it runs.
    """

    CONDITION = (
        '<tei:fs type="opensiddur:holiday-aggregate">'
        '<tei:f name="shabbat"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    )

    @staticmethod
    def _document_body(tex: str) -> str:
        """Just the typeset material: the preamble always defines every macro."""
        return tex.split(r"\begin{document}", 1)[1]

    def _transform_body(self, body: str) -> str:
        return _transform(
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                     xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
              <tei:text><tei:body>{body}</tei:body></tei:text>
            </tei:TEI>"""
        )

    def test_pinned_values_are_not_text(self):
        """An electronic-book compile records known values on a retained conditional, in
        p:pinned. They are data for the reader's device, never words on a page."""
        out = self._transform_body(
            f"""<tei:p>before <j:conditional xmlns:p="http://jewishliturgy.org/ns/processing"
              xml:id="c">{self.CONDITION}<p:pinned>{{"opensiddur:service-time":
              {{"maariv": true}}}}</p:pinned></j:conditional>conditional<j:endConditional
              target="#c"/> after</tei:p>"""
        )
        body = self._document_body(out)
        self.assertNotIn("service-time", body)
        self.assertNotIn("maariv", body)
        self.assertIn("conditional", body)

    def test_inline_conditional_is_bracketed(self):
        """A passage the book itself brackets is bracketed when undecided."""
        out = self._transform_body(
            f"""<tei:p><tei:milestone unit="verse" n="1"/>before <j:conditional
              xml:id="c" type="marked">{self.CONDITION}</j:conditional>conditional<j:endConditional
              target="#c"/> after</tei:p>"""
        )
        body = self._document_body(out)
        self.assertIn(r"\OSCondStartInline{}", body)
        self.assertIn(r"\OSCondEndInline{}", body)
        self.assertNotIn(r"\OSCondStartBlock", body)
        for word in ("before", "conditional", "after"):
            with self.subTest(word):
                self.assertIn(word, body)

    def test_a_block_that_opens_with_a_description_takes_no_opening_rule(self):
        """The description announces the passage, as the scope's own rubric would."""
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c">{self.CONDITION}</j:conditional>
              <tei:note type="description">Mourners’ Kaddish.</tei:note>
              <tei:p><tei:milestone unit="verse" n="1"/>conditional paragraph</tei:p>
              <j:endConditional target="#c"/>
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertNotIn(r"\OSCondStartBlock", body)
        self.assertIn(r"\OSCondEndBlock{}", body)
        self.assertIn("Mourners’ Kaddish.", body)

    def test_an_annotation_before_the_description_does_not_hide_it(self):
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c">{self.CONDITION}</j:conditional><tei:note
                type="commentary">A remark.</tei:note><tei:note type="description">Reader:</tei:note>
              <tei:p><tei:milestone unit="verse" n="1"/>conditional paragraph</tei:p>
              <j:endConditional target="#c"/>
            </tei:div>"""
        )
        self.assertNotIn(r"\OSCondStartBlock", self._document_body(out))

    def test_block_conditional_gets_rules(self):
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c" type="marked">{self.CONDITION}</j:conditional>
              <tei:p><tei:milestone unit="verse" n="1"/>conditional paragraph</tei:p>
              <j:endConditional target="#c"/>
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertIn(r"\OSCondStartBlock{}", body)
        self.assertIn(r"\OSCondEndBlock{}", body)
        self.assertNotIn(r"\OSCondStartInline", body)

    def test_conditional_note_is_emitted(self):
        """The note explains the condition the reader has to judge for themselves."""
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c">
                <tei:note type="instruction">On Shabbat add:</tei:note>{self.CONDITION}
              </j:conditional>
              <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>
              <j:endConditional target="#c"/>
            </tei:div>"""
        )
        self.assertIn("On Shabbat add:", out)

    def test_conditional_around_inline_content_outside_a_paragraph_is_bracketed(self):
        """A milestone-structured text has no tei:p, but its runs are still inline.

        The rule is for content set off as a block; used inside a line of text it is a
        full-measure box, which breaks the line.
        """
        out = self._transform_body(
            f"""<tei:div>
              <tei:milestone unit="verse" n="1"/>before <j:conditional
                xml:id="c" type="marked">{self.CONDITION}</j:conditional>conditional<j:endConditional
                target="#c"/> after
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertIn(r"\OSCondStartInline{}", body)
        self.assertIn(r"\OSCondEndInline{}", body)
        self.assertNotIn(r"\OSCondStartBlock", body)
        self.assertNotIn(r"\OSCondEndBlock", body)

    def test_unmarked_block_conditional_without_a_note_is_silent(self):
        """A direction to the processor -- an occasion's gate around a section -- prints the
        section with nothing around it."""
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c">{self.CONDITION}</j:conditional>
              <tei:p><tei:milestone unit="verse" n="1"/>conditional paragraph</tei:p>
              <j:endConditional target="#c"/>
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertNotIn(r"\OSCond", body)
        self.assertIn("conditional paragraph", body)

    def test_unmarked_inline_conditional_without_a_note_is_silent(self):
        out = self._transform_body(
            f"""<tei:p><tei:milestone unit="verse" n="1"/>before <j:conditional
              xml:id="c">{self.CONDITION}</j:conditional>conditional<j:endConditional
              target="#c"/> after</tei:p>"""
        )
        body = self._document_body(out)
        self.assertNotIn(r"\OSCond", body)
        self.assertRegex(body, r"before\s+conditional\s+after")

    def test_a_noted_unmarked_block_has_its_note_and_a_closing_rule(self):
        """The instruction announces the passage; a rule shows where it ends."""
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c">
                <tei:note type="instruction">On Shabbat add:</tei:note>{self.CONDITION}
              </j:conditional>
              <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>
              <j:endConditional target="#c"/>
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertNotIn(r"\OSCondStartBlock", body)
        self.assertIn(r"\OSCondEndBlock{}", body)
        self.assertEqual(1, body.count("On Shabbat add:"))

    def test_a_noted_marked_block_has_both_rules_and_its_note(self):
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c" type="marked">
                <tei:note type="instruction">On Shabbat add:</tei:note>{self.CONDITION}
              </j:conditional>
              <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>
              <j:endConditional target="#c"/>
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertIn(r"\OSCondStartBlock{}", body)
        self.assertIn(r"\OSCondEndBlock{}", body)
        self.assertEqual(1, body.count("On Shabbat add:"))
        self.assertLess(body.index(r"\OSCondStartBlock"), body.index("On Shabbat add:"))

    def test_a_noted_marked_inline_scope_has_its_note_once_and_both_brackets(self):
        out = self._transform_body(
            f"""<tei:div>
              <tei:milestone unit="verse" n="1"/>before <j:conditional xml:id="c" type="marked"
                ><tei:note type="instruction">On Shabbat:</tei:note>{self.CONDITION}</j:conditional
                >conditional<j:endConditional target="#c"/> after
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertEqual(1, body.count("On Shabbat:"))
        self.assertIn(r"\OSCondStartInline{}", body)
        self.assertIn(r"\OSCondEndInline{}", body)

    def test_a_scope_that_opens_with_its_rubric_keeps_its_delimiters(self):
        """The rubric sits inside the scope it governs, as JLPTEI-3.md has it, and announces
        it; the reader still needs to see where the passage ends."""
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c">{self.CONDITION}</j:conditional>
              <tei:note type="instruction">On Shabbat add:</tei:note>
              <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>
              <j:endConditional target="#c"/>
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertIn(r"\OSCondEndBlock{}", body)
        self.assertIn("On Shabbat add:", body)

    def test_a_closer_marked_silent_is_silent_without_its_opener(self):
        """A gate around parallel columns closes in the stream after them, apart from its
        opener; latex.py marks the closer for that reason."""
        out = self._transform_body(
            """<tei:div xmlns:p="http://jewishliturgy.org/ns/processing">
              <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>
              <j:endConditional target="#elsewhere" p:silent="true"/>
              <j:endConditional target="#elsewhere-too"/>
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertEqual(1, body.count(r"\OSCondEnd"))

    def test_a_scope_marked_not_silent_beforehand_keeps_its_delimiters(self):
        """latex.py's decision stands over the stylesheet's own test."""
        out = self._transform_body(
            f"""<tei:div xmlns:p="http://jewishliturgy.org/ns/processing">
              <j:conditional xml:id="c" p:silent="false">{self.CONDITION}</j:conditional>
              <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>
              <j:endConditional target="#c" p:silent="false"/>
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertIn(r"\OSCondStartBlock{}", body)
        self.assertIn(r"\OSCondEndBlock{}", body)

    def test_conditional_around_aliyah_markers_only_is_silent(self):
        """\\OSaliyah brackets its own label, so a delimiter would double the brackets."""
        out = self._transform_body(
            f"""<tei:div>
              <tei:milestone unit="aliyah.annual" n="first"/>
              <j:conditional xml:id="c">{self.CONDITION}</j:conditional>
              <tei:milestone unit="aliyah.triennial.1" n="year one first"/>
              <j:endConditional target="#c"/>
              <tei:milestone unit="verse" n="1"/>verse text
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertNotIn(r"\OSCond", body)
        self.assertIn(r"\OSaliyah{first}", body)
        self.assertIn(r"\OSaliyah{year one first}", body)

    def test_silenced_conditional_keeps_its_labels_on_one_line(self):
        """The point of silencing: no full-measure box between the labels."""
        out = self._transform_body(
            f"""<tei:div>
              <tei:milestone unit="aliyah.annual" n="first"/>
              <j:conditional xml:id="c1">{self.CONDITION}</j:conditional>
              <tei:milestone unit="aliyah.triennial.1" n="year one"/>
              <j:endConditional target="#c1"/>
              <j:conditional xml:id="c2">{self.CONDITION}</j:conditional>
              <tei:milestone unit="maftir.annual" n="maftir"/>
              <j:endConditional target="#c2"/>
              <tei:milestone unit="verse" n="1"/>verse text
            </tei:div>"""
        )
        body = self._document_body(out)
        labels = re.findall(r"\\OSaliyah\{([^}]*)\}", body)
        self.assertEqual(["first", "year one", "maftir"], labels)
        self.assertEqual(1, body.count(r"\pstart"))

    def test_silencing_a_conditional_leaves_no_blank_line(self):
        """A blank line is \\par, and reledmac does not want one inside a \\pstart.

        Dropping a delimiter puts the whitespace that surrounded it back to back, which
        is exactly how a blank line appears.
        """
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c1">{self.CONDITION}</j:conditional>
              <tei:milestone unit="aliyah.triennial.1" n="year one"/>
              <j:endConditional target="#c1"/>
              <j:conditional xml:id="c2">{self.CONDITION}</j:conditional>
              <tei:milestone unit="aliyah.triennial.2" n="year two"/>
              <j:endConditional target="#c2"/>
              <tei:milestone unit="verse" n="1"/>verse text
            </tei:div>"""
        )
        stream = self._document_body(out).split(r"\pstart", 1)[1].split(r"\pend", 1)[0]
        self.assertIsNone(
            re.search(r"\n[ \t]*\n", stream),
            f"blank line inside \\pstart: {stream!r}",
        )

    def test_a_silent_milestone_between_markers_leaves_no_blank_line(self):
        """A qualified parsha unit sets nothing -- the div's heading names the parshah.

        Being invisible, it must not hold apart the whitespace around it: two whitespace
        leaves meeting in the output are a blank line, and a blank line is a \\par.
        """
        out = self._transform_body(
            """<tei:div>
              <tei:head>בְּחֻקֹּתַי</tei:head>
              <tei:milestone unit="aliyah.triennial.2" n="year two fifth"/>
              <tei:milestone unit="parsha.annual" n="בְּחֻקֹּתַי"/>
              <tei:milestone unit="aliyah.annual" n="first"/>
              <tei:milestone unit="verse" n="3"/>verse text
            </tei:div>"""
        )
        body = self._document_body(out)
        # The head occupies a \pstart of its own; the labels are in the one after it.
        stream = body.split(r"\pstart")[-1].split(r"\pend", 1)[0]
        self.assertIsNone(
            re.search(r"\n[ \t]*\n", stream),
            f"blank line inside \\pstart: {stream!r}",
        )
        self.assertEqual(
            ["year two fifth", "first"], re.findall(r"\\OSaliyah\{([^}]*)\}", stream)
        )

    def test_a_silent_milestone_does_not_break_a_run_of_labels(self):
        """It sets nothing, so the labels either side are adjacent and still duplicates."""
        out = self._transform_body(
            """<tei:div>
              <tei:milestone unit="aliyah.triennial.1" n="first"/>
              <tei:milestone unit="edition-verse" n="14"/>
              <tei:milestone unit="aliyah.triennial.2" n="first"/>
              <tei:milestone unit="verse" n="1"/>verse text
            </tei:div>"""
        )
        labels = re.findall(r"\\OSaliyah\{([^}]*)\}", self._document_body(out))
        self.assertEqual(["first"], labels)

    def test_conditional_around_markers_with_a_note_stays_visible(self):
        """The note is what tells the reader; the bracket beside it is redundant."""
        out = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c">
                <tei:note type="instruction">In the triennial cycle:</tei:note>{self.CONDITION}
              </j:conditional>
              <tei:milestone unit="aliyah.triennial.1" n="year one first"/>
              <j:endConditional target="#c"/>
              <tei:milestone unit="verse" n="1"/>verse text
            </tei:div>"""
        )
        body = self._document_body(out)
        self.assertIn("In the triennial cycle:", body)
        # A conditional that announces itself needs no bracket: the instruction says which
        # passage this is and on what it depends, and the bracket reads as stray
        # punctuation beside it.
        self.assertNotIn(r"\OSCondStartInline{}", body)

    def test_instruction_does_not_hide_inline_addition_boundary(self):
        out = self._transform_body(
            f"""<tei:p>Always before
              <j:conditional xml:id="c">
                <tei:note type="instruction">During the Ten Days of Repentance, add:</tei:note>{self.CONDITION}
              </j:conditional>EXTRA<j:endConditional target="#c"/> always after</tei:p>"""
        )
        body = self._document_body(out)
        self.assertIn(r"\OSCondStartInline{}EXTRA\OSCondEndInline{} always after", body)
        self.assertEqual(body.count("During the Ten Days of Repentance, add:"), 1)
        self.assertLess(body.index("During the Ten Days"), body.index(r"\OSCondStartInline{}"))

    def test_parallel_instruction_preserves_both_addition_brackets(self):
        out = self._transform_body(
            f"""<p:parallel xmlns:p="http://jewishliturgy.org/ns/processing">
              <p:parallelItem role="primary" xml:lang="he"><tei:p>לפני
                <j:conditional xml:id="c"><tei:note type="instruction" xml:lang="en">During the Ten Days, add:</tei:note>{self.CONDITION}</j:conditional>לעלא<j:endConditional target="#c"/> אחרי
              </tei:p></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:p>Translation</tei:p></p:parallelItem>
            </p:parallel>"""
        )
        body = self._document_body(out)
        self.assertIn(r"\OSCondStartInline{}לעלא\OSCondEndInline{} אחרי", body)
        self.assertEqual(body.count("During the Ten Days, add:"), 1)
        self.assertLess(body.index("During the Ten Days"), body.index(r"\OSCondStartInline{}"))

    def test_conditional_macros_are_defined(self):
        out = self._transform_body(
            """<tei:p><tei:milestone unit="verse" n="1"/>x</tei:p>"""
        )
        for macro in (
            r"\newcommand{\OSCondStartInline}",
            r"\newcommand{\OSCondEndInline}",
            r"\newcommand{\OSCondStartBlock}",
            r"\newcommand{\OSCondEndBlock}",
        ):
            with self.subTest(macro):
                self.assertIn(macro, out)


class TestRepeatedAliyahLabels(unittest.TestCase):
    """The combined parshiyot reach the same triennial aliyah under several patterns.

    The conditions differ, so the compiled TEI rightly carries a marker for each; they all
    print the same label, and the reader needs to see it once.
    """

    CONDITION = TestConditionalRendering.CONDITION

    def _labels(self, body: str) -> list[str]:
        out = _transform(
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                     xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
              <tei:text><tei:body>{body}</tei:body></tei:text>
            </tei:TEI>"""
        )
        return re.findall(
            r"\\OSaliyah\{([^}]*)\}", out.split(r"\begin{document}", 1)[1]
        )

    def test_repeated_label_at_one_point_is_shown_once(self):
        labels = self._labels(
            f"""<tei:div>
              <j:conditional xml:id="c1">{self.CONDITION}</j:conditional>
              <tei:milestone unit="aliyah.triennial.a.1" n="year one first"/>
              <j:endConditional target="#c1"/>
              <j:conditional xml:id="c2">{self.CONDITION}</j:conditional>
              <tei:milestone unit="aliyah.triennial.b.1" n="year one first"/>
              <j:endConditional target="#c2"/>
              <tei:milestone unit="verse" n="1"/>verse text
            </tei:div>"""
        )
        self.assertEqual(["year one first"], labels)

    def test_different_labels_at_one_point_are_all_shown(self):
        labels = self._labels(
            """<tei:div>
              <tei:milestone unit="aliyah.annual" n="first"/>
              <tei:milestone unit="aliyah.weekday" n="kohen"/>
              <tei:milestone unit="aliyah.triennial.1" n="year one first"/>
              <tei:milestone unit="verse" n="1"/>verse text
            </tei:div>"""
        )
        self.assertEqual(["first", "kohen", "year one first"], labels)

    def test_the_same_label_at_two_points_is_shown_at_each(self):
        """Two divisions genuinely named alike are not duplicates of one another."""
        labels = self._labels(
            """<tei:div>
              <tei:milestone unit="aliyah.annual" n="first"/>
              <tei:milestone unit="verse" n="1"/>first verse
              <tei:milestone unit="aliyah.triennial.1" n="first"/>
              <tei:milestone unit="verse" n="2"/>second verse
            </tei:div>"""
        )
        self.assertEqual(["first", "first"], labels)


class TestOptionRendering(unittest.TestCase):
    """Alternate wordings: nothing here has chosen between them, so all are shown."""

    def test_all_options_are_rendered(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>
            <tei:choice>
              <j:option xml:lang="he">first</j:option>
              <j:option xml:lang="yi">second</j:option>
            </tei:choice>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn("first", out)
        # The later wordings are bracketed; each is set as text, in its own direction.
        self.assertRegex(out, r"first.*\(.*second.*\)")

    def test_a_note_anchored_inside_a_reading_is_a_note_not_text(self):
        """A note on an anchor inside j:written is set as a note, not spliced into the word."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="he">
          <tei:text><tei:body><tei:p>
            <tei:choice><j:written>כשה<tei:anchor xml:id="r"><tei:note>a remark</tei:note></tei:anchor>סכל</j:written><j:read>כשהסכל</j:read></tei:choice>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml).split("\\begin{document}")[1]
        self.assertNotIn("כשהa remark", out)
        self.assertIn("\\OSInterlinearNotemark{1}", out)

    def test_markup_inside_a_reading_is_kept(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="en">
          <tei:text><tei:body><tei:p>
            <tei:choice><j:read>a <tei:hi rend="small-caps">Lord</tei:hi></j:read><j:written>b</j:written></tei:choice>
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        self.assertIn("\\OSHighlightSmallCaps{", _transform(xml))


class TestStructuralElements(unittest.TestCase):
    """tei:standOff and tei:pb should be skipped; head should produce a styled
    heading macro instead of inlining the title in the body."""

    def test_standoff_notes_are_skipped(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:p>Body</tei:p>
            <tei:standOff type="notes">
              <tei:note>Should not appear</tei:note>
            </tei:standOff>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn("Body", out)
        self.assertNotIn("Should not appear", out)

    def test_div_head_emits_heading_inside_its_own_pstart(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div>
              <tei:head>Genesis</tei:head>
              <tei:p><tei:milestone unit="verse" n="1"/>In the beginning.</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        # Top-level head → \OSheadA (LTR wrapper when not Hebrew), and the heading must
        # sit alone in a skipnumbering pstart so it is a real, unnumbered heading.
        # The running-head marks precede it inside the same pstart.
        self.assertIn(
            "\\pstart\\relax \\skipnumbering\n"
            r"\InsertMark{OSheadA}{{\textdir TLT\foreignlanguage{english}{Genesis}}}"
            r"\InsertMark{OSheadAny}{{\textdir TLT\foreignlanguage{english}{Genesis}}}"
            r"\OSheadA{{\textdir TLT\foreignlanguage{english}{Genesis}}}",
            out,
        )
        self.assertNotIn(r"\eledchapter", out)
        self.assertNotIn(r"\eledsubsection", out)

    def test_book_div_head_also_records_the_book_mark(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div type="book">
              <tei:head>Genesis</tei:head>
              <tei:p>In the beginning.</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\InsertMark{OSbook}{{\textdir TLT\foreignlanguage{english}{Genesis}}}", out)

    def test_non_book_div_head_records_no_book_mark(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div type="section">
              <tei:head>A Section</tei:head>
              <tei:p>Text.</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\InsertMark{OSheadA}{{\textdir TLT\foreignlanguage{english}{A Section}}}", out)
        self.assertNotIn(r"\InsertMark{OSbook}", out)

    def test_heading_marks_follow_the_heading_level(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div><tei:head>Outer</tei:head>
              <tei:div><tei:head>Inner</tei:head><tei:p>Text.</tei:p></tei:div>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\InsertMark{OSheadA}{{\textdir TLT\foreignlanguage{english}{Outer}}}", out)
        self.assertIn(r"\InsertMark{OSheadB}{{\textdir TLT\foreignlanguage{english}{Inner}}}", out)
        # Every heading also records into the any-level class, which backs
        # the {section-title} code.
        self.assertIn(r"\InsertMark{OSheadAny}{{\textdir TLT\foreignlanguage{english}{Inner}}}", out)

    def test_mixed_script_heading_mark_carries_per_run_direction(self):
        """A running head can be placed in a slot of either direction, so the
        mark cannot assume one: Hebrew runs need \\texthebrew (direction *and*
        font) and Latin runs need an explicit LTR wrapper."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>
            <tei:div type="book">
              <tei:head><tei:foreign xml:lang="he">רות</tei:foreign><tei:lb/>RUTH</tei:head>
              <tei:p>Text.</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\InsertMark{OSbook}{\texthebrew{רות}", out)
        self.assertIn(r"{\textdir TLT\foreignlanguage{english}{RUTH}}", out)

    def test_a_hyphenated_hebrew_heading_stays_one_run(self):
        """A paired parsha name is written with an en-dash, which is outside the
        Hebrew block. Splitting on it would make the dash its own LTR embedding
        and let a neighbouring chapter number reorder into the middle of the
        name."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div><tei:head>\u05ea\u05b7\u05d6\u05b0\u05e8\u05b4\u05d9\u05e2\u05b7\u2013\u05de\u05b0\u05e6\u05b9\u05e8\u05b8\u05e2</tei:head>
              <tei:p>\u05d8\u05e7\u05e1\u05d8</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(
            "\\InsertMark{OSheadA}{\\texthebrew{"
            "\u05ea\u05b7\u05d6\u05b0\u05e8\u05b4\u05d9\u05e2\u05b7\u2013"
            "\u05de\u05b0\u05e6\u05b9\u05e8\u05b8\u05e2}}",
            out,
        )
        self.assertNotIn("foreignlanguage{english}{\u2013", out)

    def test_div_head_emits_pdf_bookmark(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div>
              <tei:head>Genesis</tei:head>
              <tei:p>In the beginning.</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(
            r"\phantomsection\addcontentsline{toc}{section}"
            r"{{\textdir TLT\foreignlanguage{english}{Genesis}}}",
            out,
        )

    def test_heading_level_counts_only_headed_ancestors(self):
        """Transclusion interposes headless container divs, so heading level must follow
        headed ancestors rather than raw nesting depth."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div>
              <tei:div>
                <tei:head>Outer</tei:head>
                <tei:div>
                  <tei:head>Inner</tei:head>
                  <tei:p>Text.</tei:p>
                </tei:div>
              </tei:div>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        # Two headless container divs above "Outer" must not push it below level 1.
        self.assertIn(r"\OSheadA{{\textdir TLT\foreignlanguage{english}{Outer}}}", out)
        self.assertIn(r"\OSheadB{{\textdir TLT\foreignlanguage{english}{Inner}}}", out)
        self.assertIn(r"\addcontentsline{toc}{subsection}", out)

    def test_head_markup_is_rendered_not_flattened(self):
        """A mixed-language title (JPS book heads look like this) must keep its Hebrew run
        in a \\texthebrew wrapper — flattened into the surrounding LTR heading the Hebrew
        renders reversed. The line break becomes a horizontal separator, since only the
        first line of a heading carries the centering glue."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>
            <tei:div type="book">
              <tei:head><tei:foreign xml:lang="he">רות</tei:foreign><tei:lb/>RUTH</tei:head>
              <tei:p>And it came to pass.</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(
            r"\OSheadA{{\textdir TLT\foreignlanguage{english}{"
            r"\texthebrew{\OSForeign{רות}}\quad RUTH}}",
            out,
        )
        # ...but a line break in body text is still a line break. Scoped to the typeset
        # material: the preamble defines macros that legitimately use \quad themselves.
        body = out.split(r"\begin{document}", 1)[1]
        self.assertNotIn(r"\quad", body.split(r"\OSheadA", 1)[0])
        # The contents entry takes the flattened title — \addcontentsline cannot carry
        # markup — with each run wrapped for its direction, so the Hebrew stays Hebrew on
        # a contents page whichever way that page runs. hyperref strips both wrappers, so
        # the PDF outline still reads "רותRUTH".
        self.assertIn(
            r"\addcontentsline{toc}{section}"
            r"{\texthebrew{רות}{\textdir TLT\foreignlanguage{english}{RUTH}}}",
            out,
        )

    def test_english_head_in_hebrew_document_uses_ltr_wrapper(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div type="book">
              <tei:head xml:lang="en">Genesis</tei:head>
              <tei:p><tei:milestone unit="verse" n="1"/>בְּרֵאשִׁית</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(
            r"\OSheadA{{\textdir TLT\foreignlanguage{english}{Genesis}}}",
            out,
        )

    def test_hebrew_head_in_hebrew_document_has_no_ltr_wrapper(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div type="book">
              <tei:head>בראשית</tei:head>
              <tei:p><tei:milestone unit="verse" n="1"/>בְּרֵאשִׁית</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\OSheadA{בראשית}", out)
        self.assertNotIn(
            r"\OSheadA{{\textdir TLT\foreignlanguage{english}{בראשית}}}",
            out,
        )

    def test_digits_embedded_in_a_hebrew_head_are_forced_ltr(self):
        """A Hebrew heading was never expected to carry a number before, so digits in it
        went out unwrapped and would render reversed (e.g. "42:5" as "5:24")."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div type="book">
              <tei:head>ישעיהו 42:5</tei:head>
              <tei:p><tei:milestone unit="verse" n="1"/>בְּרֵאשִׁית</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        # "42" and "5" must wrap as a single LTR run, not two side by side: two separate
        # embeds with only a colon between them can have their *relative* order swapped by
        # the bidi algorithm (this is what previously rendered "42:5" as "43:10-42:5" in a
        # citation — see TestCitationMilestone.test_a_multi_number_range_stays_in_order).
        self.assertIn(
            r"\OSheadA{ישעיהו {{\textdir TLT\foreignlanguage{english}{42:5}}}}",
            out,
        )


class TestFrontMatter(unittest.TestCase):
    """``tei:front`` is set before the body, with title pages on pages of their own
    outside the reledmac line numbering and the rest as ordinary text."""

    TITLE_PAGE_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
      <tei:text>
        <tei:front>
          <tei:pb n="i"/>
          <tei:titlePage>
            <tei:docTitle>
              <tei:titlePart type="main">THE HOLY SCRIPTURES</tei:titlePart>
              <tei:titlePart type="sub">ACCORDING TO THE MASORETIC TEXT</tei:titlePart>
              <tei:titlePart type="alt" xml:lang="he">תורה נביאים וכתובים</tei:titlePart>
            </tei:docTitle>
            <tei:byline><tei:docAuthor>Max L. Margolis</tei:docAuthor></tei:byline>
            <tei:docEdition>Third Impression</tei:docEdition>
            <tei:docImprint>
              <tei:pubPlace>PHILADELPHIA</tei:pubPlace>
              <tei:publisher>THE JEWISH PUBLICATION SOCIETY OF AMERICA</tei:publisher>
              <tei:docDate>5677-1917</tei:docDate>
            </tei:docImprint>
          </tei:titlePage>
          <tei:head>PREFACE</tei:head>
          <tei:p>The sacred task of translating.</tei:p>
        </tei:front>
        <tei:body><tei:p>In the beginning.</tei:p></tei:body>
      </tei:text>
    </tei:TEI>"""

    def test_title_page_carries_no_running_head(self):
        """A title page is not part of the running-head scheme. The titlepage
        environment sets this itself, but `plain` is redefined for running heads,
        so do not leave the guarantee to a class internal."""
        out = _transform(self.TITLE_PAGE_XML)
        self.assertIn("\\begin{titlepage}\n\\thispagestyle{empty}", out)

    def test_front_matter_is_set_before_the_body(self):
        out = _transform(self.TITLE_PAGE_XML)
        self.assertLess(out.index("The sacred task"), out.index("In the beginning."))

    def test_front_matter_switches_page_numbering(self):
        """book-class front matter is numbered in roman and the body restarts at 1."""
        out = _transform(self.TITLE_PAGE_XML)
        self.assertLess(out.index(r"\frontmatter"), out.index(r"\mainmatter"))
        self.assertLess(out.index(r"\mainmatter"), out.index("In the beginning."))

    def test_title_page_is_its_own_page(self):
        out = _transform(self.TITLE_PAGE_XML)
        self.assertIn(r"\begin{titlepage}", out)
        self.assertIn(r"\end{titlepage}", out)

    def test_title_page_carries_no_line_numbering(self):
        """reledmac numbering inside a titlepage would number a transcribed page of
        the source as if it were edited text."""
        out = _transform(self.TITLE_PAGE_XML)
        page = out.split(r"\begin{titlepage}", 1)[1].split(r"\end{titlepage}", 1)[0]
        self.assertNotIn(r"\beginnumbering", page)
        self.assertNotIn(r"\pstart", page)

    def test_title_page_parts_use_their_own_macros(self):
        out = _transform(self.TITLE_PAGE_XML)
        self.assertIn(r"\OSTitleMain{THE HOLY SCRIPTURES}", out)
        self.assertIn(r"\OSTitleSub{ACCORDING TO THE MASORETIC TEXT}", out)
        # A Hebrew line on a Latin title page needs \texthebrew, or it renders reversed.
        self.assertIn(r"\OSTitleAlt{\texthebrew{תורה נביאים וכתובים}}", out)
        self.assertIn(r"\OSByline{Max L. Margolis}", out)
        self.assertIn(r"\OSDocEdition{Third Impression}", out)
        self.assertIn(r"\OSImprintLine{PHILADELPHIA}", out)
        self.assertIn(r"\OSImprintLine{5677-1917}", out)

    def test_prose_front_matter_is_a_numbered_stream(self):
        out = _transform(self.TITLE_PAGE_XML)
        front = out.split(r"\end{titlepage}", 1)[1].split(r"\mainmatter", 1)[0]
        self.assertIn(r"\beginnumbering", front)
        self.assertIn(r"\OSheadA{", front)

    def test_a_note_on_the_title_page_is_a_latex_footnote(self):
        r"""The title page is outside \beginnumbering, where \edtext ends the run."""
        xml = self.TITLE_PAGE_XML.replace(
            "<tei:docEdition>Third Impression</tei:docEdition>",
            "<tei:docEdition>Third Impression<tei:note>A later printing.</tei:note>"
            "</tei:docEdition>",
        ).replace(
            "<tei:p>The sacred task of translating.</tei:p>",
            "<tei:p>The sacred task<tei:note>Second note.</tei:note> of translating.</tei:p>",
        )
        out = _transform(xml)
        page = out.split(r"\begin{titlepage}", 1)[1].split(r"\end{titlepage}", 1)[0]
        self.assertNotIn(r"\edtext", page)
        self.assertIn(r"\begingroup\renewcommand{\thefootnote}{1}\footnote{\notenote{", page)
        self.assertIn("A later printing.", page)
        # The serial counts the title-page note, so the next note is the second.
        front = out.split(r"\end{titlepage}", 1)[1]
        self.assertIn(r"\OSInterlinearNotemark{2}", front)

    def test_a_title_page_note_is_not_part_of_the_document_title(self):
        xml = self.TITLE_PAGE_XML.replace(
            '<tei:titlePart type="main">THE HOLY SCRIPTURES</tei:titlePart>',
            '<tei:titlePart type="main">THE HOLY SCRIPTURES<tei:note>A remark.</tei:note>'
            "</tei:titlePart>",
        )
        out = _transform(xml)
        title = out.split(r"\newcommand{\OSDocumentTitle}{", 1)[1].split("\n", 1)[0]
        self.assertIn("THE HOLY SCRIPTURES", title)
        self.assertNotIn("A remark.", title)

    def test_a_title_page_note_is_dropped_when_notes_are_off(self):
        xml = self.TITLE_PAGE_XML.replace(
            "<tei:docEdition>Third Impression</tei:docEdition>",
            "<tei:docEdition>Third Impression<tei:note>A later printing.</tei:note>"
            "</tei:docEdition>",
        )
        out = _transform(xml, **{"notes-placement": "none"})
        self.assertNotIn("A later printing.", out)

    def test_hebrew_title_page_is_wrapped_for_direction(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text>
            <tei:front>
              <tei:titlePage>
                <tei:docTitle>
                  <tei:titlePart type="main">ההגדה לליל שמורים</tei:titlePart>
                </tei:docTitle>
                <tei:docImprint xml:lang="de">
                  <tei:pubPlace>Roedelheim,</tei:pubPlace>
                </tei:docImprint>
              </tei:titlePage>
            </tei:front>
            <tei:body><tei:p>טקסט</tei:p></tei:body>
          </tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        page = out.split(r"\begin{titlepage}", 1)[1].split(r"\end{titlepage}", 1)[0]
        self.assertIn(r"\begin{hebrew}", page)
        # The Hebrew title needs no wrapper; the German imprint on the same page does,
        # or its Latin text would be laid out right to left.
        self.assertIn(r"\OSTitleMain{ההגדה לליל שמורים}", page)
        self.assertIn(
            r"\OSImprintLine{{\textdir TLT\foreignlanguage{english}{Roedelheim,}}}", page
        )

    def test_imprint_parts_stay_inline_in_a_running_imprint(self):
        """A publisher named mid-sentence must not be broken onto a line of its own."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text>
            <tei:front>
              <tei:titlePage type="copyright">
                <tei:docImprint>Copyright, 1917, By <tei:publisher>The Jewish Publication Society of America</tei:publisher></tei:docImprint>
              </tei:titlePage>
            </tei:front>
            <tei:body><tei:p>In the beginning.</tei:p></tei:body>
          </tei:text>
        </tei:TEI>"""
        # \OSImprintLine is always *defined* in the preamble; assert it is never *used*.
        body = _transform(xml).split(r"\begin{document}", 1)[1]
        self.assertIn(
            r"\OSDocImprint{Copyright, 1917, By The Jewish Publication Society of America}",
            body,
        )
        self.assertNotIn(r"\OSImprintLine", body)

    FRONT_IN_ANOTHER_LANGUAGE = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
      <tei:text>
        <tei:front>
          <tei:div xml:lang="en">
            <tei:head>INTRODUCTION</tei:head>
            <tei:p>The Siddur is the most popular book in Jewish life.</tei:p>
          </tei:div>
          <tei:div xml:lang="he">
            <tei:p>פתח דבר</tei:p>
          </tei:div>
        </tei:front>
        <tei:body><tei:p>בראשית</tei:p></tei:body>
      </tei:text>
    </tei:TEI>"""

    def test_front_prose_is_set_in_its_own_language_not_the_root_s(self):
        """A book's front matter is routinely in a language its body is not: Birnbaum's
        introduction is English in a Hebrew-rooted project. Set under the root language,
        every line of it came out reversed."""
        out = _transform(self.FRONT_IN_ANOTHER_LANGUAGE)
        front = out.split(r"\frontmatter", 1)[1].split(r"\mainmatter", 1)[0]
        english = front.split("INTRODUCTION", 1)[0]
        self.assertNotIn(r"\begin{hebrew}", english)

    def test_front_prose_of_each_language_gets_its_own_numbered_stream(self):
        """Grouping by language keeps adjacent same-language prose in one stream and
        starts a new one where the language changes."""
        out = _transform(self.FRONT_IN_ANOTHER_LANGUAGE)
        front = out.split(r"\frontmatter", 1)[1].split(r"\mainmatter", 1)[0]
        self.assertEqual(2, front.count(r"\beginnumbering"))
        self.assertIn(r"\begin{hebrew}", front)

    def test_document_without_front_matter_is_unchanged(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body><tei:p>In the beginning.</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertNotIn(r"\frontmatter", out)
        self.assertNotIn(r"\mainmatter", out)
        self.assertNotIn(r"\begin{titlepage}", out)

    def test_title_page_in_the_body_is_not_flattened_into_the_text(self):
        """The leaves pass must never pull title page parts into a numbered stream."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>
            <tei:div>
              <tei:titlePage><tei:docTitle><tei:titlePart>Stray</tei:titlePart></tei:docTitle></tei:titlePage>
              <tei:p>In the beginning.</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        body = out.split(r"\begin{document}", 1)[1]
        self.assertNotIn("Stray", body)


class TestTableOfContents(unittest.TestCase):
    """``table-of-contents`` optionally prints a TOC page (\\tableofcontents), reusing the
    \\addcontentsline entries the heading template already writes for PDF bookmarks."""

    NESTED_HEADS_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
      <tei:text><tei:body>
        <tei:div><tei:head>Section One</tei:head>
          <tei:div><tei:head>Subsection</tei:head><tei:p>Hi</tei:p></tei:div>
        </tei:div>
      </tei:body></tei:text>
    </tei:TEI>"""

    def test_table_of_contents_omitted_by_default(self):
        out = _transform(self.NESTED_HEADS_XML)
        self.assertNotIn(r"\tableofcontents", out)

    def test_table_of_contents_printed_when_enabled(self):
        out = _transform(self.NESTED_HEADS_XML, **{"table-of-contents": True})
        self.assertIn(r"\tableofcontents", out)

    def test_table_of_contents_comes_after_frontmatter_and_before_mainmatter(self):
        out = _transform(self.NESTED_HEADS_XML, **{"table-of-contents": True})
        self.assertLess(out.index(r"\frontmatter"), out.index(r"\tableofcontents"))
        self.assertLess(out.index(r"\tableofcontents"), out.index(r"\mainmatter"))

    def test_addcontentsline_entries_still_present_when_enabled(self):
        """The TOC page must not replace the existing bookmark plumbing."""
        out = _transform(self.NESTED_HEADS_XML, **{"table-of-contents": True})
        self.assertIn(r"\addcontentsline{toc}{section}", out)
        self.assertIn(r"\addcontentsline{toc}{subsection}", out)

    def test_hebrew_entries_are_wrapped_for_the_contents_page(self):
        """A contents entry is typeset in the table of contents, whose direction is the
        document class's and not the heading's. A Hebrew title left bare there is laid
        out left to right, one character at a time, so every line of a Hebrew contents
        page reads backwards. Each run takes its own wrapper instead."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div><tei:head>בְּדִיקַת חָמֵץ</tei:head><tei:p>שלום</tei:p></tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, **{"table-of-contents": True})
        self.assertIn(
            r"\addcontentsline{toc}{section}{\texthebrew{בְּדִיקַת חָמֵץ}}",
            out,
        )

    def test_hebrew_entries_reach_the_pdf_outline_unwrapped(self):
        """\\texthebrew is markup, and a PDF string carries none: hyperref must strip it
        the way it already strips the direction and language switches, or the outline
        entry reads "\\texthebrewבדיקת חמץ"."""
        out = _transform(self.NESTED_HEADS_XML, **{"table-of-contents": True})
        disabled = out.split(r"\pdfstringdefDisableCommands{", 1)[1].split("\n}", 1)[0]
        self.assertIn(r"\def\texthebrew#1{#1}", disabled)

    def test_frontmatter_emitted_even_without_tei_front(self):
        """A document with no tei:front still needs \\frontmatter/\\mainmatter so the TOC
        gets roman-numeral front-matter pagination."""
        out = _transform(self.NESTED_HEADS_XML, **{"table-of-contents": True})
        self.assertIn(r"\frontmatter", out)
        self.assertIn(r"\mainmatter", out)

    def test_document_without_table_of_contents_has_no_frontmatter_switch(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body><tei:p>In the beginning.</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertNotIn(r"\frontmatter", out)
        self.assertNotIn(r"\mainmatter", out)

    def test_table_of_contents_depth_is_scoped_locally(self):
        """A custom depth must not leak into the global tocdepth that drives bookmarks."""
        out = _transform(
            self.NESTED_HEADS_XML,
            **{"table-of-contents": True, "table-of-contents-depth": 2},
        )
        self.assertIn(r"{\setcounter{tocdepth}{2}", out)
        self.assertIn("\\tableofcontents}\n\\mainmatter", out)
        # The preamble's global tocdepth (drives bookmarksdepth) is unaffected.
        self.assertIn(r"\setcounter{tocdepth}{4}", out)
        self.assertIn("bookmarksdepth=4", out)

    def test_table_of_contents_depth_defaults_to_four(self):
        out = _transform(self.NESTED_HEADS_XML, **{"table-of-contents": True})
        self.assertIn(r"{\setcounter{tocdepth}{4}", out)
        self.assertIn("\\tableofcontents}\n\\mainmatter", out)


class TestParshaMilestones(unittest.TestCase):
    """A parsha is a division containing the chapters and verses that follow it, so its
    milestone legitimately sits between paragraphs rather than inside one. It used to be
    rendered only when a \\pstart happened to be open, which meant every boundary in the
    JPS 1917 Torah — all of them between paragraphs — was silently dropped."""

    def _transform_book(self, body: str) -> str:
        """A div[@type='book'], which is what makes chapter milestones render too."""
        return _transform(
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
              <tei:text><tei:body>
                <tei:div type="book">{body}</tei:div>
              </tei:body></tei:text>
            </tei:TEI>"""
        )

    @staticmethod
    def _document_body(tex: str) -> str:
        """Just the typeset material: the preamble always defines every macro."""
        return tex.split(r"\begin{document}", 1)[1]

    BETWEEN_PARAGRAPHS = """
        <tei:p><tei:milestone unit="verse" n="8"/>But Noah found grace.</tei:p>
        <tei:milestone unit="parsha" n="Noach"/>
        <tei:p><tei:milestone unit="verse" n="9"/>These are the generations.</tei:p>"""

    def test_a_milestone_between_paragraphs_is_rendered(self):
        body = self._document_body(self._transform_book(self.BETWEEN_PARAGRAPHS))
        self.assertIn(r"\OSParsha{Noach}", body)

    def test_a_milestone_inside_a_paragraph_is_still_rendered(self):
        """The shape that happened to work before must keep working."""
        body = self._document_body(self._transform_book(
            """<tei:p><tei:milestone unit="verse" n="8"/>But Noah found grace.</tei:p>
               <tei:p><tei:milestone unit="verse" n="9"/><tei:milestone unit="parsha"
                 n="Noach"/>These are the generations.</tei:p>"""
        ))
        self.assertIn(r"\OSParsha{Noach}", body)

    def test_a_milestone_before_the_first_paragraph_is_rendered(self):
        body = self._document_body(self._transform_book(
            """<tei:head>GENESIS</tei:head>
               <tei:milestone unit="parsha" n="Bereshit"/>
               <tei:p><tei:milestone unit="verse" n="1"/>In the beginning.</tei:p>"""
        ))
        self.assertIn(r"\OSParsha{Bereshit}", body)

    def test_the_name_runs_in_with_the_verse_it_opens(self):
        """The pstart opened for the boundary is the one the following verse uses, so the
        name shares a line with the parsha's first verse instead of standing alone."""
        body = self._document_body(self._transform_book(self.BETWEEN_PARAGRAPHS))
        after = body.split(r"\OSParsha{Noach}", 1)[1]
        block = after.split(r"\pend", 1)[0]
        self.assertIn(r"\vno{9}", block)
        self.assertNotIn(r"\pstart", block)

    def test_a_boundary_is_announced_only_once(self):
        """The B-series footnote this used to emit alongside would repeat the name on the
        same page. The apparatus form is available by \\renewcommand instead."""
        body = self._document_body(self._transform_book(self.BETWEEN_PARAGRAPHS))
        self.assertNotIn(r"\Bfootnote", body)
        self.assertEqual(1, body.count("Noach"))

    def test_the_parsha_macro_is_defined_in_the_preamble(self):
        out = self._transform_book(self.BETWEEN_PARAGRAPHS)
        preamble = out.split(r"\begin{document}", 1)[0]
        self.assertIn(r"\newcommand{\OSParsha}", preamble)

    def test_a_hebrew_name_gets_a_direction_wrapper(self):
        """Parsha names are Hebrew in an otherwise LTR stream and would render reversed."""
        body = self._document_body(self._transform_book(
            """<tei:p><tei:milestone unit="verse" n="8"/>But Noah found grace.</tei:p>
               <tei:milestone unit="parsha" n="נֹח"/>
               <tei:p><tei:milestone unit="verse" n="9"/>These are the generations.</tei:p>"""
        ))
        self.assertIn("\\OSParsha{\\texthebrew{נֹח}}", body)

class TestEditionColophons(unittest.TestCase):
    """A digital edition's colophon divisions are set after the book's own colophon and
    before the last page."""

    XML = """<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en"><tei:text>
      <tei:front><tei:div type="preface"><tei:p>A printed preface.</tei:p></tei:div>
        <tei:div type="colophon" subtype="notes"><tei:p>First published in 1842.</tei:p></tei:div>
      </tei:front>
      <tei:body><tei:p>In the beginning.</tei:p></tei:body></tei:text></tei:TEI>"""

    def test_after_the_colophon_and_before_the_last_page(self):
        from opensiddur.exporter.cli_common import relocate_colophons

        root = etree.fromstring(self.XML)
        relocate_colophons(root)
        out = _transform(etree.tostring(root, encoding="unicode"),
                         **{"additional-postamble": "OSPOSTAMBLE", "back-notice": "OSBACKNOTICE"})
        preface, body = out.index("A printed preface."), out.index("In the beginning.")
        postamble, colophon, back = (out.index("OSPOSTAMBLE"), out.index("First published in 1842."),
                                     out.index("OSBACKNOTICE"))
        self.assertLess(preface, body)
        self.assertLess(body, postamble)
        self.assertLess(postamble, colophon)
        self.assertLess(colophon, back)
        self.assertNotIn("\\backmatter", out[body:postamble])

    def test_notes_in_a_colophon_are_footnotes_even_as_endnotes(self):
        """The colophon is set after the endnotes are printed, so an endnote there would be
        lost."""
        from opensiddur.exporter.cli_common import relocate_colophons

        xml = self.XML.replace("First published in 1842.",
                               "First published in 1842.<tei:note>A remark.</tei:note>")
        root = etree.fromstring(xml)
        relocate_colophons(root)
        out = _transform(etree.tostring(root, encoding="unicode"), **{"notes-placement": "endnote"})
        self.assertIn("\\Bfootnote", out[out.index("First published in 1842."):])


if __name__ == "__main__":
    unittest.main()


class TestReadingDivisions(unittest.TestCase):
    """Aliyah, maftir and parshah markers, as the humash emits them.

    These divisions overlap on purpose, so their markers are inline rather than breaks: a
    maftir opens inside the seventh aliyah, and a marker that ended a paragraph would assert
    a break that is not there — besides desynchronising a reledpar pairing, which counts
    \\pstart markers on each side.
    """

    @staticmethod
    def _body(tex: str) -> str:
        return tex.split(r"\begin{document}", 1)[1]

    def _transform_body(self, body: str, **params) -> str:
        return _transform(
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                     xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
              <tei:text><tei:body>{body}</tei:body></tei:text>
            </tei:TEI>""",
            **params,
        )

    def test_aliyah_marker_is_emitted_inline(self):
        out = self._transform_body(
            """<tei:p><tei:milestone unit="verse" n="1"/>text one
               <tei:milestone unit="aliyah.annual" n="שני"/>text two</tei:p>"""
        )
        body = self._body(out)
        self.assertIn(r"\OSaliyah{", body)
        for word in ("text one", "text two"):
            with self.subTest(word):
                self.assertIn(word, body)

    def test_maftir_and_weekday_and_triennial_all_get_markers(self):
        for unit in ("maftir.annual", "aliyah.weekday", "aliyah.triennial.2"):
            with self.subTest(unit=unit):
                out = self._transform_body(
                    f"""<tei:p><tei:milestone unit="verse" n="1"/>text
                        <tei:milestone unit="{unit}" n="X"/>more</tei:p>"""
                )
                self.assertIn(r"\OSaliyah{X}", self._body(out))

    def test_a_marker_does_not_break_the_paragraph(self):
        """The maftir begins inside the seventh aliyah, so it must not close its pstart."""
        out = self._transform_body(
            """<tei:p><tei:milestone unit="verse" n="1"/>before
               <tei:milestone unit="maftir.annual" n="מפטיר"/>after</tei:p>"""
        )
        body = self._body(out)
        marker = body.index(r"\OSaliyah{")
        # No paragraph is closed and reopened around the marker.
        self.assertNotIn(r"\pend", body[max(0, marker - 120):marker])

    def test_markers_keep_pstart_counts_equal_for_parallel_text(self):
        """reledpar pairs columns by \\pstart count, so a marker on one side only must not
        add or remove one."""
        without = self._transform_body(
            """<tei:p><tei:milestone unit="verse" n="1"/>a</tei:p>"""
        )
        with_marker = self._transform_body(
            """<tei:p><tei:milestone unit="verse" n="1"/><tei:milestone
               unit="aliyah.annual" n="ראשון"/>a</tei:p>"""
        )
        self.assertEqual(
            self._body(without).count(r"\pstart"), self._body(with_marker).count(r"\pstart")
        )
        self.assertEqual(
            self._body(without).count(r"\pend"), self._body(with_marker).count(r"\pend")
        )

    def test_silenced_markers_keep_pstart_counts_equal_for_parallel_text(self):
        """Dropping a marker must not drop the \\pstart it would have opened.

        A conditional and an aliyah marker each open a \\pstart when none is open, so
        silencing the one and deduplicating the other could cost a column a \\pstart that
        the facing column still has, and reledpar pairs the columns by counting them.
        """
        condition = TestConditionalRendering.CONDITION
        without = self._transform_body(
            """<tei:div><tei:milestone unit="verse" n="1"/>a</tei:div>"""
        )
        with_markers = self._transform_body(
            f"""<tei:div>
              <j:conditional xml:id="c1">{condition}</j:conditional>
              <tei:milestone unit="aliyah.triennial.1" n="first"/>
              <j:endConditional target="#c1"/>
              <j:conditional xml:id="c2">{condition}</j:conditional>
              <tei:milestone unit="aliyah.triennial.2" n="first"/>
              <j:endConditional target="#c2"/>
              <tei:milestone unit="verse" n="1"/>a
            </tei:div>"""
        )
        for macro in (r"\pstart", r"\pend"):
            with self.subTest(macro):
                self.assertEqual(
                    self._body(without).count(macro),
                    self._body(with_markers).count(macro),
                )

    def test_a_qualified_parsha_unit_is_left_to_the_heading(self):
        """The humash gives every parshah a tei:head, so printing the milestone too would
        name it twice."""
        out = self._transform_body(
            """<tei:div><tei:head>בראשית</tei:head>
               <tei:p><tei:milestone unit="verse" n="1"/><tei:milestone
                 unit="parsha.annual" n="בראשית"/>text</tei:p></tei:div>"""
        )
        body = self._body(out)
        self.assertNotIn("Parsha:", body)
        self.assertIn("text", body)

    def test_an_unqualified_parsha_unit_still_gets_its_name_rendered(self):
        """wlc and jps1917 mark parshiyot inside a book with no heading of their own."""
        out = self._transform_body(
            """<tei:div type="book"><tei:head>Genesis</tei:head>
               <tei:p><tei:milestone unit="verse" n="1"/>text
               <tei:milestone unit="parsha" n="נח"/>more</tei:p></tei:div>"""
        )
        self.assertIn("\\OSParsha{\\texthebrew{נח}}", self._body(out))

    def test_the_aliyah_macro_is_defined_in_the_preamble(self):
        out = self._transform_body("""<tei:p>text</tei:p>""")
        self.assertIn(r"\newcommand{\OSaliyah}", out.split(r"\begin{document}", 1)[0])


class TestCitationMilestone(unittest.TestCase):
    """A tei:milestone[@unit='citation'] is how the humash states a haftarah/festival
    reading's scriptural source, or where it resumes after a jump (build._citation)."""

    @staticmethod
    def _body(tex: str) -> str:
        return tex.split(r"\begin{document}", 1)[1]

    def _transform_body(self, body: str, **params) -> str:
        return _transform(
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                     xmlns:p="http://jewishliturgy.org/ns/processing">
              <tei:text><tei:body>{body}</tei:body></tei:text>
            </tei:TEI>""",
            **params,
        )

    def test_citation_is_rendered_in_its_own_pstart(self):
        out = self._transform_body(
            """<tei:head>הַפְטָרַת בְּרֵאשִׁית</tei:head>
               <tei:milestone unit="citation" n="ישעיהו מב:ה–מג:י"/>
               <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>"""
        )
        body = self._body(out)
        self.assertIn(r"\OScitation{", body)
        before = body.split(r"\OScitation{", 1)[0]
        self.assertTrue(before.rstrip().endswith(r"\pstart\relax \skipnumbering"))

    def test_the_citation_macro_is_defined_in_the_preamble(self):
        out = self._transform_body("""<tei:p>text</tei:p>""")
        self.assertIn(r"\newcommand{\OScitation}", out.split(r"\begin{document}", 1)[0])

    def test_digits_in_the_citation_are_forced_ltr(self):
        out = self._transform_body(
            """<tei:milestone unit="citation" n="ישעיהו 42:5-43:10"/>
               <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>"""
        )
        body = self._body(out)
        self.assertIn(r"{\textdir TLT\foreignlanguage{english}{42:5-43:10}}", body)

    def test_a_multi_number_range_stays_in_order(self):
        """Two colon/dash-joined number groups sitting side by side in RTL text, with no
        strong character between them to anchor on, do not reliably keep their relative
        order if wrapped as separate LTR embeds: "42:5-43:10" can come out as "43:10-42:5".
        The whole range must go in one embedding instead — see f:emit-bidi-text."""
        out = self._transform_body(
            """<tei:milestone unit="citation" n="ירמיהו 34:8–34:22; 33:25–33:26"/>
               <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>"""
        )
        body = self._body(out)
        self.assertIn(
            r"{\textdir TLT\foreignlanguage{english}{34:8–34:22; 33:25–33:26}}", body,
        )

    def test_a_book_change_still_gets_its_own_wrap(self):
        """A Hebrew book name between two ranges is a strong character, so it is safe to
        end one LTR run and start a fresh one there rather than merging across it."""
        out = self._transform_body(
            """<tei:milestone unit="citation" n="מלכים א 18:46; מלאכי 3:4–3:24"/>
               <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>"""
        )
        body = self._body(out)
        self.assertIn(r"{\textdir TLT\foreignlanguage{english}{18:46}}", body)
        self.assertIn(r"{\textdir TLT\foreignlanguage{english}{3:4–3:24}}", body)

    def test_a_citation_does_not_break_the_reading(self):
        """The reading's own transcluded text still follows in the numbered stream."""
        out = self._transform_body(
            """<tei:milestone unit="citation" n="ישעיהו 42:5-43:10"/>
               <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>"""
        )
        self.assertIn(r"\vno{1}", self._body(out))

    def test_markers_keep_pstart_counts_equal_for_parallel_text(self):
        """A citation exists only on the Hebrew source's milestones, so it must not add or
        remove a \\pstart on either side, or reledpar's column-pairing desyncs."""
        without = _transform(
            """<?xml version="1.0" encoding="UTF-8"?>
            <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                     xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
              <tei:text><tei:body>
                <p:parallel column-order="primary_first">
                  <p:parallelItem role="primary" xml:lang="he">
                    <tei:p><tei:milestone unit="verse" n="1"/>שלום</tei:p>
                  </p:parallelItem>
                  <p:parallelItem role="parallel" xml:lang="en">
                    <tei:p><tei:milestone unit="verse" n="1"/>Hello</tei:p>
                  </p:parallelItem>
                </p:parallel>
              </tei:body></tei:text>
            </tei:TEI>"""
        )
        with_citation = _transform(
            """<?xml version="1.0" encoding="UTF-8"?>
            <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                     xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
              <tei:text><tei:body>
                <p:parallel column-order="primary_first">
                  <p:parallelItem role="primary" xml:lang="he">
                    <tei:p><tei:milestone unit="citation" n="ישעיהו א:א"/>
                      <tei:milestone unit="verse" n="1"/>שלום</tei:p>
                  </p:parallelItem>
                  <p:parallelItem role="parallel" xml:lang="en">
                    <tei:p><tei:milestone unit="verse" n="1"/>Hello</tei:p>
                  </p:parallelItem>
                </p:parallel>
              </tei:body></tei:text>
            </tei:TEI>"""
        )
        self.assertEqual(without.count(r"\pstart"), with_citation.count(r"\pstart"))
        self.assertEqual(without.count(r"\pend"), with_citation.count(r"\pend"))


class TestEmptyNumberedStreams(unittest.TestCase):
    """Structural remnants between transclusions must not start numbering.

    The full Birnbaum index leaves standalone runs with XML leaves but no
    printed paragraphs. reledmac rejects numbering around such a run.
    """

    def test_structural_only_streams_do_not_start_numbering(self):
        for content in (
            '<tei:div>\n  </tei:div>',
            '<tei:p/>',
            '<tei:p><tei:milestone unit="prayer"/></tei:p>',
            '<tei:p><tei:milestone unit="edition-verse" n="14"/></tei:p>',
        ):
            for lang in ('he', 'en'):
                with self.subTest(content=content, lang=lang):
                    out = _transform(f'''<tei:TEI
                        xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="{lang}">
                        <tei:text><tei:body>{content}</tei:body></tei:text>
                        </tei:TEI>''').split(r'\begin{document}')[1]
                    self.assertNotIn(r'\beginnumbering', out)
                    self.assertNotIn(r'\endnumbering', out)

    def test_separator_only_stream_keeps_the_separator_without_numbering(self):
        out = _transform('''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
            <tei:text><tei:body><tei:milestone unit="section" rend="****"/>
            </tei:body></tei:text></tei:TEI>''').split(r'\begin{document}')[1]
        self.assertIn(r'\OSSectionSeparator', out)
        self.assertNotIn(r'\beginnumbering', out)

    def test_structural_div_between_transclusions_keeps_both_parallel_texts(self):
        block = '''<p:transclude><p:parallel column-order="primary_first">
            <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
            <p:parallelItem role="parallel" xml:lang="en"><tei:p>Hello</tei:p></p:parallelItem>
            </p:parallel></p:transclude>'''
        out = _transform(f'''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
            xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
            <tei:text><tei:body>{block}<tei:div p:part="last">\n  </tei:div>{block}
            </tei:body></tei:text></tei:TEI>''').split(r'\begin{document}')[1]
        sections = re.findall(r'\\beginnumbering(.*?)\\endnumbering', out, re.S)
        self.assertEqual(len(sections), 4)
        for section in sections:
            self.assertIn(r'\pstart', section)
        self.assertEqual(out.count('שלום'), 2)
        self.assertEqual(out.count('Hello'), 2)


class TestUnrenderedMilestones(unittest.TestCase):
    """A milestone the stylesheet does not set must not open a paragraph of its own.

    reledmac cannot typeset an empty \pstart: it fails with "You can't use \lastbox in
    vertical mode" and produces no PDF at all. A paragraph holding only such a milestone —
    which is what a range boundary falling inside an edition's own verse produces — used to
    make exactly that.
    """

    XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
      <tei:text><tei:body>
        <tei:p><tei:milestone unit="verse" n="17"/>text</tei:p>
        <tei:p><tei:milestone unit="edition-verse" n="14"/></tei:p>
      </tei:body></tei:text>
    </tei:TEI>"""

    def test_no_empty_paragraph_is_emitted(self):
        out = _transform(self.XML)
        self.assertNotIn(r"\pstart\relax \pend", out)
        self.assertNotIn("\\pstart\n\\pend", out)

    def test_the_verse_before_it_is_still_set(self):
        out = _transform(self.XML)
        self.assertIn(r"\vno{17}", out)
        self.assertIn("text", out)

    def test_an_edition_verse_prints_nothing(self):
        self.assertNotIn("14", _transform(self.XML).split("begin{document}")[1])



class TestMultilingualBookmarks(unittest.TestCase):
    """A work that names a section in two languages gets one outline entry, not two.

    Two encodings say the same thing: a division with two ``tei:head``, and two projects
    compiled side by side. Both are governed by ``typography.bookmarks.from``.
    """

    @staticmethod
    def _outline_entry(out: str) -> str:
        r"""The bookmark as a PDF reader sees it.

        f:emit-bidi-mark wraps each run against the slot it sits in, Hebrew in
        \texthebrew and everything else in \textdir TLT, so a contents entry reads
        \texthebrew{ברך}{\textdir TLT\foreignlanguage{english}{ · Grace}}. The preamble's
        \pdfstringdefDisableCommands strips exactly those commands when hyperref builds
        the PDF string, so undoing them here makes an assertion mean what the reader will
        see rather than what the TeX happens to look like.
        """
        marker = "}{"
        after = out.split("\\addcontentsline{toc}{", 1)[1]
        after = after.split(marker, 1)[1] if marker in after else after
        # The title is the balanced brace group that starts here.
        depth, end = 0, len(after)
        for i, ch in enumerate(after):
            if ch == "{":
                depth += 1
            elif ch == "}":
                if depth == 0:
                    end = i
                    break
                depth -= 1
        title = after[:end]
        return (title.replace("{\\textdir TLT\\foreignlanguage{english}{", "")
                     .replace("\\texthebrew", "")
                     .replace("{", "").replace("}", "").strip())

    PARALLEL = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">
                <tei:div corresp="urn:x-opensiddur:text:haggadah:barech">
                  <tei:head>ברך</tei:head>
                  <tei:p>שלום</tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div corresp="urn:x-opensiddur:text:haggadah:barech">
                  <tei:head>Grace after Meals</tei:head>
                  <tei:p>Hello</tei:p>
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""

    def test_parallel_columns_emit_one_bookmark_not_two(self):
        """Both columns used to write to the .toc, so every heading appeared twice and
        out of document order, the columns reaching the .toc at different points."""
        out = _transform(self.PARALLEL)
        self.assertEqual(1, out.count(r"\addcontentsline"))

    def test_parallel_bookmark_combines_both_titles(self):
        out = _transform(self.PARALLEL)
        self.assertEqual("ברך · Grace after Meals", self._outline_entry(out))

    def test_from_primary_takes_the_first_column_alone(self):
        out = _transform(self.PARALLEL, **{"bookmarks-from": "primary"})
        self.assertEqual(1, out.count(r"\addcontentsline"))
        self.assertEqual("ברך", self._outline_entry(out))

    def test_from_alt_takes_the_second_column_alone(self):
        out = _transform(self.PARALLEL, **{"bookmarks-from": "alt"})
        self.assertEqual(1, out.count(r"\addcontentsline"))
        self.assertEqual("Grace after Meals", self._outline_entry(out))

    def test_a_second_head_on_one_division_is_rendered_and_not_dropped(self):
        """Every head after the first used to be discarded outright: the div template
        recursed on node()[not(self::tei:head)] and only tei:head[1] became a sentinel.
        It bit at random, because a division split across parallel columns gives each
        piece its own tei:head[1]."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div>
              <tei:head>ברך</tei:head>
              <tei:head xml:lang="en">Grace after Meals</tei:head>
              <tei:p>שלום</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\OSheadA{ברך}", out)
        # The translated title reaches the page, which it did not before.
        self.assertIn(r"\OSheadTranslation{", out)
        for word in ("Grace", "after", "Meals"):
            self.assertIn(word, out.split(r"\OSheadTranslation{", 1)[1][:200])
        # ...and the two titles are one entry, not two.
        self.assertEqual(1, out.count(r"\addcontentsline"))
        self.assertEqual("ברך · Grace after Meals", self._outline_entry(out))

    def test_two_heads_in_one_division_honour_from_primary(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div>
              <tei:head>ברך</tei:head>
              <tei:head xml:lang="en">Grace after Meals</tei:head>
              <tei:p>שלום</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, **{"bookmarks-from": "primary"})
        # The translated title is still set on the page; only the outline entry narrows.
        self.assertIn(r"\OSheadTranslation{", out)
        self.assertEqual("ברך", self._outline_entry(out))

    def test_identical_titles_are_not_doubled_in_one_entry(self):
        """Birnbaum heads his Hebrew and English pages alike, so combining would
        otherwise read "SHEMONEH ESREH · SHEMONEH ESREH"."""
        xml = self.PARALLEL.replace("<tei:head>Grace after Meals</tei:head>",
                                    "<tei:head>ברך</tei:head>")
        out = _transform(xml)
        self.assertEqual(1, out.count(r"\addcontentsline"))
        self.assertEqual("ברך", self._outline_entry(out))

    def test_a_heading_on_one_side_only_keeps_its_own_title(self):
        """A project's realisation of a URN need not cover every branch, so one column
        may hold a heading the other lacks. It must be bookmarked under its own title
        rather than dropped or given someone else's."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">
                <tei:div corresp="urn:x-opensiddur:text:haggadah:only-here">
                  <tei:head>יחיד</tei:head>
                  <tei:p>שלום</tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div corresp="urn:x-opensiddur:text:haggadah:only-here">
                  <tei:p>Hello</tei:p>
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertEqual(1, out.count(r"\addcontentsline"))
        self.assertEqual("יחיד", self._outline_entry(out))

    def test_single_language_document_is_unaffected(self):
        """The stream defaults to primary, so a document with no parallel block keeps
        exactly the bookmark it had before this setting existed."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div><tei:head>Genesis</tei:head><tei:p>In the beginning.</tei:p></tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(
            r"\phantomsection\addcontentsline{toc}{section}"
            r"{{\textdir TLT\foreignlanguage{english}{Genesis}}}",
            out,
        )
        self.assertEqual(1, out.count(r"\addcontentsline"))

    def test_part_divs_sharing_a_urn_pair_to_their_own_counterparts(self):
        """marker_reconstruct splits one authored division across the columns and stamps
        each piece with @p:part, so several pieces carry the same @corresp. Pairing on the
        URN alone would match the first piece every time and give the second piece the
        first's translation."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary">
                <tei:div corresp="urn:x-opensiddur:text:siddur:unit" p:part="first">
                  <tei:head>ראשון</tei:head><tei:p>א</tei:p>
                </tei:div>
                <tei:div corresp="urn:x-opensiddur:text:siddur:unit" p:part="middle">
                  <tei:head>שני</tei:head><tei:p>ב</tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel">
                <tei:div corresp="urn:x-opensiddur:text:siddur:unit" p:part="first">
                  <tei:head>First</tei:head><tei:p>a</tei:p>
                </tei:div>
                <tei:div corresp="urn:x-opensiddur:text:siddur:unit" p:part="middle">
                  <tei:head>Second</tei:head><tei:p>b</tei:p>
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertEqual(2, out.count(r"\addcontentsline"))
        # Each piece takes its own counterpart, not the first one twice. The entry is
        # wrapped run by run for the typeset contents page, so match on that form.
        english = r"{\textdir TLT\foreignlanguage{english}{"
        self.assertIn("\\texthebrew{ראשון}" + english + " · First}}", out)
        self.assertIn("\\texthebrew{שני}" + english + " · Second}}", out)
        self.assertNotIn("\\texthebrew{שני}" + english + " · First}}", out)

    def test_from_alt_on_a_single_text_takes_the_divisions_second_head(self):
        """'alt' means the other title, not the other column. A single text titled twice
        has no facing column, and tying the setting to the stream emitted no outline for
        it at all."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div>
              <tei:head>ברך</tei:head>
              <tei:head xml:lang="en">Grace</tei:head>
              <tei:p>שלום</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, **{"bookmarks-from": "alt"})
        self.assertEqual(1, out.count(r"\addcontentsline"))
        self.assertEqual("Grace", self._outline_entry(out))

    def test_every_mode_emits_exactly_one_entry_for_either_encoding(self):
        """The invariant the whole change exists to establish: one section, one entry,
        whichever way the work carries its two languages and whichever title is asked for."""
        single = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div>
              <tei:head>ברך</tei:head>
              <tei:head xml:lang="en">Grace</tei:head>
              <tei:p>שלום</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        for encoding, xml in (("two heads in one div", single),
                              ("two parallel columns", self.PARALLEL)):
            for mode in ("combined", "primary", "alt"):
                with self.subTest(encoding=encoding, mode=mode):
                    out = _transform(xml, **{"bookmarks-from": mode})
                    self.assertEqual(1, out.count(r"\addcontentsline"))
                    self.assertNotEqual("", self._outline_entry(out))


class TestParallelHeadings(unittest.TestCase):
    """A section titled twice gets one heading on the page where the titles agree.

    The same question ``bookmarks.from`` asks of the outline, asked of the page, so it
    takes the same vocabulary. Suppressing a heading is not dropping it: reledpar pairs
    the columns by counting \\pstart...\\pend, so the paragraph must stay, and reledmac
    cannot typeset an empty one.
    """

    @staticmethod
    def _parallel(primary_title: str, alt_title: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">
                <tei:div corresp="urn:x-opensiddur:text:siddur:unit">
                  <tei:head>{primary_title}</tei:head><tei:p>שלום</tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div corresp="urn:x-opensiddur:text:siddur:unit">
                  <tei:head>{alt_title}</tei:head><tei:p>Hello</tei:p>
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""

    @staticmethod
    def _translation_arg(out: str) -> str:
        r"""The argument of \OSheadTranslation, by balanced braces.

        A fixed-width window after the macro name is not good enough: the \addcontentsline
        that follows a few characters later carries a direction wrapper of its own, so a
        window wide enough to be useful catches it and the assertion passes on the wrong
        text. That is how the first version of these tests stayed green against the
        unfixed stylesheet."""
        rest = out.split(r"\OSheadTranslation{", 1)[1]
        depth, out_chars = 1, []
        for ch in rest:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            out_chars.append(ch)
        return "".join(out_chars)

    @staticmethod
    def _parallel_langs(primary_title: str, alt_title: str, *,
                        primary: str, parallel: str) -> str:
        """`_parallel` with the two columns' languages chosen, for the direction tests."""
        body = {"he": "שלום", "en": "Hello"}
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="{primary}">
                <tei:div corresp="urn:x-opensiddur:text:siddur:unit">
                  <tei:head xml:lang="{primary}">{primary_title}</tei:head><tei:p>{body[primary]}</tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="{parallel}">
                <tei:div corresp="urn:x-opensiddur:text:siddur:unit">
                  <tei:head xml:lang="{parallel}">{alt_title}</tei:head><tei:p>{body[parallel]}</tei:p>
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""

    @staticmethod
    def _pstarts(out: str) -> tuple:
        left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
        right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
        return (left.count(r"\pstart"), right.count(r"\pstart"))

    SAME = "KEDUSHAH"
    OTHER = "Sanctification"

    def test_columns_that_agree_set_the_heading_once(self):
        """Birnbaum heads his Hebrew and English pages alike, so both columns printed
        KEDUSHAH and the reader saw it twice."""
        out = _transform(self._parallel(self.SAME, self.SAME))
        self.assertEqual(1, out.count(r"\OSheadA{"))

    def test_columns_that_differ_show_both_titles(self):
        """Under the default they span the page together, the second set beneath the
        first; both are still on the page."""
        out = _transform(self._parallel(self.SAME, self.OTHER))
        self.assertIn(self.SAME, out)
        self.assertIn(self.OTHER, out)

    def test_from_primary_and_alt_each_set_exactly_one(self):
        for titles in ((self.SAME, self.SAME), (self.SAME, self.OTHER)):
            for mode in ("primary", "alt"):
                with self.subTest(titles=titles, mode=mode):
                    out = _transform(self._parallel(*titles),
                                     **{"headings-from": mode})
                    self.assertEqual(1, out.count(r"\OSheadA{"))

    def test_from_alt_sets_the_second_columns_title(self):
        out = _transform(self._parallel(self.SAME, self.OTHER),
                         **{"headings-from": "alt"})
        self.assertIn(rf"\OSheadA{{{{\textdir TLT\foreignlanguage{{english}}{{{self.OTHER}}}}}}}", out)

    def test_a_suppressed_heading_keeps_its_paragraph(self):
        """reledpar pairs the columns by counting \\pstart, so a suppressed heading must
        still open one. It must also not be empty: reledmac fails the whole build on an
        empty \\pstart rather than skipping it."""
        for titles in ((self.SAME, self.SAME), (self.SAME, self.OTHER)):
            for mode in ("combined", "primary", "alt"):
                with self.subTest(titles=titles, mode=mode):
                    out = _transform(self._parallel(*titles),
                                     **{"headings-from": mode})
                    left, right = self._pstarts(out)
                    self.assertEqual(left, right)
                    self.assertIsNone(re.search(r"\\pstart\s*\\pend", out))

    def test_the_running_head_still_knows_both_columns(self):
        """A suppressed heading is still in force on the page, so a page style must be
        able to name either language."""
        out = _transform(self._parallel(self.SAME, self.SAME))
        self.assertIn(r"\InsertMark{OSheadA}", out)
        self.assertIn(r"\InsertMark{OSheadAAlt}", out)

    def test_a_single_language_document_is_unaffected(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div><tei:head>Genesis</tei:head><tei:p>In the beginning.</tei:p></tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertEqual(1, out.count(r"\OSheadA{"))
        self.assertNotIn(r"\mbox{}", out.split(r"\begin{document}")[1])

    def test_a_shared_heading_is_set_across_the_page_not_inside_a_column(self):
        """A heading both columns give is not a heading of either: it names the section,
        and the section spans the opening. Set inside a column it would be centred over
        half the page."""
        out = _transform(self._parallel(self.SAME, self.SAME))
        left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
        right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
        self.assertEqual(1, out.count(r"\OSheadA{"))
        self.assertNotIn(r"\OSheadA{", left)
        self.assertNotIn(r"\OSheadA{", right)
        # ...and it is set before the columns it heads.
        self.assertLess(out.index(r"\OSheadA{"), out.index(r"\begin{Leftside}"))

    def test_a_spanning_heading_carries_the_marks_and_the_bookmark(self):
        """The heading inside the columns is suppressed, so it carries neither. Both
        running-head families are set, since a page style may name either language."""
        out = _transform(self._parallel(self.SAME, self.SAME))
        self.assertEqual(1, out.count(r"\addcontentsline"))
        self.assertIn(r"\InsertMark{OSheadA}", out)
        self.assertIn(r"\InsertMark{OSheadAAlt}", out)
        # The outline entry is anchored where the reader lands, outside the columns.
        self.assertLess(out.index(r"\addcontentsline"), out.index(r"\begin{Leftside}"))

    def test_headings_stay_in_their_columns_only_under_both(self):
        out = _transform(self._parallel(self.SAME, self.OTHER),
                         **{"headings-from": "both"})
        left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
        right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
        self.assertIn(r"\OSheadA{", left)
        self.assertIn(r"\OSheadA{", right)

    def test_every_mode_that_sets_one_heading_spans_the_page(self):
        """A heading set once is not a heading of either column — it names the section,
        and the section spans the opening. Which of the two titles it shows does not
        change that."""
        for titles in ((self.SAME, self.SAME), (self.SAME, self.OTHER)):
            for mode in ("combined", "primary", "alt"):
                with self.subTest(titles=titles, mode=mode):
                    out = _transform(self._parallel(*titles),
                                     **{"headings-from": mode})
                    self.assertLess(out.index(r"\OSheadA{"),
                                    out.index(r"\begin{Leftside}"))

    def test_both_keeps_a_heading_in_each_column(self):
        """The one mode that does not span. Where there really are two headings, each
        belongs to the column whose language it is in."""
        for titles in ((self.SAME, self.SAME), (self.SAME, self.OTHER)):
            with self.subTest(titles=titles):
                out = _transform(self._parallel(*titles), **{"headings-from": "both"})
                left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
                right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
                self.assertEqual(1, left.count(r"\OSheadA{"))
                self.assertEqual(1, right.count(r"\OSheadA{"))

    def test_both_does_not_deduplicate(self):
        """'both' means both, even where the two columns say the same thing."""
        out = _transform(self._parallel(self.SAME, self.SAME),
                         **{"headings-from": "both"})
        self.assertEqual(2, out.count(r"\OSheadA{"))

    def test_facing_pages_set_nothing_across_the_spread(self):
        r"""There is no measure spanning two pages, and a heading set before \Pages is
        stranded on a page of its own while \Pages clears to the next verso."""
        for titles in ((self.SAME, self.SAME), (self.SAME, self.OTHER)):
            for mode in ("combined", "primary", "alt", "both"):
                with self.subTest(titles=titles, mode=mode):
                    out = _transform(self._parallel(*titles), layout="pages",
                                     **{"headings-from": mode})
                    before = out.split(r"\begin{document}")[1].split(r"\begin{pages}")[0]
                    self.assertNotIn(r"\OSheadA{", before)
                    self.assertNotIn(r"\OSheadTranslation{", out)

    def test_combined_sets_the_heading_on_both_facing_pages(self):
        """Even where the titles agree: the reader cannot take a heading from the facing
        page the way they can from the next column."""
        for titles in ((self.SAME, self.SAME), (self.SAME, self.OTHER)):
            with self.subTest(titles=titles):
                out = _transform(self._parallel(*titles), layout="pages")
                left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
                right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
                self.assertIn(titles[0], left.split(r"\OSheadA{")[1])
                self.assertIn(titles[1], right.split(r"\OSheadA{")[1])

    def test_on_facing_pages_primary_and_alt_still_name_one_page(self):
        for mode, sets_left in (("primary", True), ("alt", False)):
            with self.subTest(mode=mode):
                out = _transform(self._parallel(self.SAME, self.OTHER), layout="pages",
                                 **{"headings-from": mode})
                left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
                right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
                self.assertEqual(sets_left, r"\OSheadA{" in left)
                self.assertEqual(not sets_left, r"\OSheadA{" in right)
                self.assertEqual(self._pstarts(out)[0], self._pstarts(out)[1])

    def test_facing_pages_mark_each_page_for_its_own_running_head(self):
        r"""Nothing is hoisted, so only the left page records the plain marks and only
        the right page the Alt ones: {section-title} on a verso names that verso's
        heading, {section-title-alt} on a recto names the recto's."""
        out = _transform(self._parallel(self.SAME, self.OTHER), layout="pages")
        left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
        right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
        self.assertIn(r"\InsertMark{OSheadAny}", left)
        self.assertNotIn(r"\InsertMark{OSheadAnyAlt}", left)
        self.assertIn(r"\InsertMark{OSheadAnyAlt}", right)
        self.assertNotIn(r"\InsertMark{OSheadAny}{", right)

    def test_facing_pages_write_one_outline_entry(self):
        for mode in ("combined", "primary", "alt", "both"):
            with self.subTest(mode=mode):
                out = _transform(self._parallel(self.SAME, self.OTHER), layout="pages",
                                 **{"headings-from": mode})
                self.assertEqual(1, out.count(r"\addcontentsline"))

    def test_facing_pages_keep_a_new_section_in_the_same_run(self):
        r"""Splitting the run at a heading only served hoisting it. Under \Pages each
        split costs a fresh spread, so the run stays whole."""
        block = self._parallel(self.SAME, self.OTHER)
        body = block.split("<tei:body>")[1].split("</tei:body>")[0]
        xml = block.replace(body, body + body)
        out = _transform(xml, layout="pages")
        self.assertEqual(1, out.count(r"\begin{pages}"))

    def test_combined_sets_a_differing_title_beneath_as_a_translation(self):
        """Spanning the page leaves nowhere to put a second title side by side, so it goes
        under the first — the shape a division titled twice in one column already takes."""
        out = _transform(self._parallel(self.SAME, self.OTHER))
        self.assertEqual(1, out.count(r"\OSheadA{"))
        self.assertEqual(1, out.count(r"\OSheadTranslation{"))
        self.assertIn(self.OTHER, self._translation_arg(out))

    def test_a_facing_title_in_the_other_language_is_set_in_its_own_direction(self):
        """The heading spans the page inside the hebrew environment when the primary title
        is Hebrew. An English title beneath it needs its own LTR wrapper, or it is typeset
        right to left and its letters are painted in reverse order on the page.

        The text being present proves nothing here — it was present, and reversed. What
        has to be asserted is the direction wrapper around it."""
        out = _transform(self._parallel_langs(self.SAME, self.OTHER,
                                              primary="he", parallel="en"))
        translation = self._translation_arg(out)
        self.assertIn(r"\textdir TLT", translation)
        self.assertIn(r"\foreignlanguage{english}", translation)

    def test_a_facing_title_takes_its_column_language_over_the_compiled_root(self):
        r"""A unit file states its language once, on its own tei:TEI, and titles its
        divisions without repeating it. Compiling two projects in parallel puts both under
        one root, which can only carry one language -- the primary project's -- and records
        each column's on its p:parallelItem. Reading the root and not the column made every
        English title in a Hebrew book Hebrew, so it was set \texthebrew and its words,
        each separately wrapped against the Hebrew around them, were laid out right to
        left: "Blessing After Meals" printed as "Meals After Blessing"."""
        out = _transform(f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">
                <tei:div corresp="urn:x-opensiddur:text:haggadah:barech">
                  <tei:head>בָּרֵךְ</tei:head><tei:p>שלום</tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div corresp="urn:x-opensiddur:text:haggadah:barech">
                  <tei:head>Blessing After Meals</tei:head><tei:p>Hello</tei:p>
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>""")
        translation = self._translation_arg(out)
        self.assertNotIn(r"\texthebrew", translation)
        self.assertIn(r"{\textdir TLT\foreignlanguage{english}{Blessing After Meals}}",
                      translation)

    def test_a_facing_hebrew_title_under_a_latin_one_is_wrapped_too(self):
        """The same requirement the other way round: the wrapper follows the title's own
        language, not the language of the heading it is set beneath."""
        out = _transform(self._parallel_langs("MORNING PRAYER", "שחרית",
                                              primary="en", parallel="he"))
        translation = self._translation_arg(out)
        self.assertIn(r"\texthebrew{", translation)

    def test_a_title_language_undeclared_anywhere_falls_back_to_the_latin_wrapper(self):
        """`f:section-title-lang` takes the nearest ancestor declaring a language, which is
        usually the head's own tei:div or its column. Where nothing on the way up declares
        one at all, the title is treated as Latin. Asserted as the shape of the fallback,
        not a case the projects rely on: their unit files all declare a language."""
        out = _transform(self._parallel(self.SAME, self.OTHER).replace(
            ' xml:lang="he"', "").replace(' xml:lang="en"', ""))
        translation = self._translation_arg(out)
        self.assertIn(r"\foreignlanguage{english}", translation)

    def test_one_outline_entry_in_every_mode(self):
        for titles in ((self.SAME, self.SAME), (self.SAME, self.OTHER)):
            for mode in ("combined", "primary", "alt", "both"):
                with self.subTest(titles=titles, mode=mode):
                    out = _transform(self._parallel(*titles),
                                     **{"headings-from": mode})
                    self.assertEqual(1, out.count(r"\addcontentsline"))

    def test_a_spanning_heading_is_centred_on_the_measure(self):
        r"""\parfillskip is 0pt plus 1fil on an ordinary paragraph, and the heading macros
        centre with an \hfill at each end. Three infinite glues put the title a third of
        the way across rather than half. reledmac zeroes \parfillskip inside a \pstart,
        which is why a heading set in a column looked right and this one, set between
        columns, sat left of centre."""
        out = _transform(self._parallel(self.SAME, self.SAME))
        spanning = out.split(r"\begin{Leftside}")[0]
        self.assertIn(r"{\parfillskip=0pt\interlinepenalty=10000\relax", spanning)
        # The group closes with \par, so the setting cannot leak into what follows.
        self.assertIn(r"\par}", spanning)
        self.assertLess(spanning.index(r"{\parfillskip=0pt\interlinepenalty=10000\relax"),
                        spanning.index(r"\OSheadA{"))

class TestParallelInstructions(unittest.TestCase):
    """A rubric both columns give is one rubric printed twice.

    HeadingsConfig's question asked of a rubric, and it takes the same vocabulary. What it
    does not do is span the page: a rubric stands mid-flow, and a parallel block cannot be
    interrupted partway through, so the kept one stays in its column.
    """

    @staticmethod
    def _parallel(primary: str, alt: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">
                <tei:div>
                  <tei:note type="instruction" xml:lang="en">{primary}</tei:note>
                  <tei:p>שלום</tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div>
                  <tei:note type="instruction" xml:lang="en">{alt}</tei:note>
                  <tei:p>Hello</tei:p>
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""

    MACROS = (r"\instructionnote{", r"\OSInstructionBlock{", r"\OSInstructionLine{")
    SAME = "Between Rosh Hashanah and Yom Kippur add:"
    OTHER = "On fast days the Reader adds:"

    @classmethod
    def _counts(cls, out: str) -> tuple:
        def n(s):
            return sum(s.count(m) for m in cls.MACROS)
        left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
        right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
        return n(left), n(right)

    def test_the_same_rubric_in_both_columns_is_set_once(self):
        """Birnbaum prints his rubrics in English on both sides of the opening, so both
        columns carried the same sentence and the reader saw it twice."""
        self.assertEqual((1, 0), self._counts(_transform(
            self._parallel(self.SAME, self.SAME), **{"instructions-from": "combined"})))

    def test_rubrics_that_differ_are_both_set(self):
        self.assertEqual((1, 1), self._counts(_transform(
            self._parallel(self.SAME, self.OTHER), **{"instructions-from": "combined"})))

    def test_naming_a_column_takes_that_column_whether_or_not_they_differ(self):
        """'primary' and 'alt' name a column and mean it — unlike 'combined', which only
        removes what the other column already says."""
        for titles in ((self.SAME, self.SAME), (self.SAME, self.OTHER)):
            with self.subTest(titles=titles):
                self.assertEqual(
                    (1, 0),
                    self._counts(_transform(self._parallel(*titles),
                                            **{"instructions-from": "primary"})))
                self.assertEqual(
                    (0, 1),
                    self._counts(_transform(self._parallel(*titles),
                                            **{"instructions-from": "alt"})))

    def test_both_is_the_default(self):
        """Deduplicating a rubric the columns are not aligned on loses it for one
        column's reader; keeping both merely repeats it."""
        self.assertEqual((1, 1), self._counts(_transform(
            self._parallel(self.SAME, self.SAME))))

    def test_both_keeps_every_rubric_where_it_is(self):
        for titles in ((self.SAME, self.SAME), (self.SAME, self.OTHER)):
            with self.subTest(titles=titles):
                self.assertEqual(
                    (1, 1),
                    self._counts(_transform(self._parallel(*titles),
                                            **{"instructions-from": "both"})))

    def test_block_rubrics_start_following_text_on_a_new_line_in_both_columns(self):
        out = _transform(self._parallel(self.SAME, self.SAME))
        for side in ("Leftside", "Rightside"):
            with self.subTest(side=side):
                stream = out.split(r"\begin{" + side + "}")[1].split(
                    r"\end{" + side + "}")[0]
                self.assertIn(r"\OSInstructionBlock{", stream)
                self.assertNotIn(r"\instructionnote{", stream)

    def test_conditional_block_rubrics_keep_both_prayers_below_the_instruction(self):
        xml = self._parallel(self.SAME, self.SAME).replace(
            'xmlns:p="http://jewishliturgy.org/ns/processing"',
            'xmlns:p="http://jewishliturgy.org/ns/processing" '
            'xmlns:j="http://jewishliturgy.org/ns/jlptei/2"')
        xml = xml.replace('<tei:note type="instruction"',
                          '<j:conditional><tei:note type="instruction"').replace(
                              '</tei:note>', '</tei:note></j:conditional>')
        out = _transform(xml)
        for side in ("Leftside", "Rightside"):
            with self.subTest(side=side):
                stream = out.split(r"\begin{" + side + "}")[1].split(
                    r"\end{" + side + "}")[0]
                self.assertIn(r"\OSInstructionBlock{", stream)
                self.assertNotIn(r"\instructionnote{", stream)

    def test_a_kept_rubric_stays_in_its_column(self):
        """Unlike a heading, which is hoisted out of the columns entirely."""
        out = _transform(self._parallel(self.SAME, self.SAME),
                         **{"instructions-from": "combined"})
        self.assertGreater(out.index(r"\OSInstructionBlock{"),
                           out.index(r"\begin{Leftside}"))

    def test_a_single_language_document_is_unaffected(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body>
            <tei:div>
              <tei:note type="instruction" xml:lang="en">Stand.</tei:note>
              <tei:p>שלום</tei:p>
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertEqual(1, sum(out.count(m) for m in self.MACROS))


class TestParallelParagraphSpacing(unittest.TestCase):
    r"""A paragraph break in one column must not open a gap in the other.

    ``\Columns`` takes each side one ``\baselineskip`` slice at a time and ``\unvbox``-es
    that slice onto the full-width page list, keeping only its ``\lastbox`` as the column's
    line. Glue in the slice stays behind on the shared list, between two full-width rows —
    so a ``\parskip`` after a paragraph in the Hebrew column used to open a blank line in
    the middle of the facing English paragraph.

    The cure is that no vertical glue may survive inside a parallel ``\pstart``. The
    separation becomes a blank line instead, which is the smallest column-local vertical
    unit reledpar has.
    """

    @staticmethod
    def _parallel(primary: str, alt: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">
                <tei:div>{primary}</tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div>{alt}</tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""

    TWO_PARAGRAPHS = _parallel.__func__(
        "<tei:p>שלום</tei:p><tei:p>עולם</tei:p>",
        "<tei:p>Hello</tei:p><tei:p>World</tei:p>",
    )

    @staticmethod
    def _sides(out: str) -> tuple[str, str]:
        left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
        right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
        return left, right

    def test_a_paragraph_break_is_a_blank_line_not_a_skip(self):
        """The regression test. A bare \\par between two paragraphs of a parallel block
        carries \\parskip glue, and that glue reaches the facing column."""
        out = _transform(self.TWO_PARAGRAPHS, layout="pairs")
        for side in self._sides(out):
            self.assertIn(r"\par\skipnumbering\OSKeepSep\par", side)

    def test_a_trailing_break_sets_no_blank_line(self):
        r"""A paragraph break is a terminator, so the last paragraph of a block carries one
        with nothing after it. Kept, it would set an empty row against \pend."""
        out = _transform(self.TWO_PARAGRAPHS, layout="pairs")
        for side in self._sides(out):
            self.assertEqual(1, side.count(r"\par\skipnumbering\OSKeepSep\par"))
            self.assertNotRegex(side, r"\\OSKeepSep\\par\s*\\pend")

    def test_parskip_is_zeroed_inside_both_columns(self):
        out = _transform(self.TWO_PARAGRAPHS, layout="pairs")
        for side in self._sides(out):
            self.assertIn(r"\setlength{\parskip}{0pt}", side)

    def test_the_columns_keep_their_own_paragraph_counts(self):
        r"""Column-local means column-local: the two sides need not break in the same
        places, and neither side gains a break because the other has one."""
        out = _transform(
            self._parallel(
                "<tei:p>שלום</tei:p><tei:p>עולם</tei:p><tei:p>שוב</tei:p>",
                "<tei:p>Hello world again</tei:p>",
            ),
            layout="pairs",
        )
        left, right = self._sides(out)
        self.assertEqual(2, left.count(r"\par\skipnumbering\OSKeepSep\par"))
        self.assertEqual(0, right.count(r"\par\skipnumbering\OSKeepSep\par"))

    def test_differing_paragraph_counts_still_pair_pstart_for_pstart(self):
        r"""The block stays the alignment unit. Paragraphs inside it are not pstarts, so
        an uneven number of them cannot desync the columns."""
        out = _transform(
            self._parallel(
                "<tei:p>שלום</tei:p><tei:p>עולם</tei:p><tei:p>שוב</tei:p>",
                "<tei:p>Hello world again</tei:p>",
            ),
            layout="pairs",
        )
        left, right = self._sides(out)
        self.assertEqual(left.count(r"\pstart"), right.count(r"\pstart"))
        self.assertEqual(left.count(r"\pend"), right.count(r"\pend"))

    def test_a_note_anchor_spends_no_row_of_its_own(self):
        r"""A note annotating the block after it is compiled in as a preceding sibling,
        and the source whitespace between the two used to reach the output as a blank
        line. The anchor's own \leavevmode has already opened the paragraph, so that
        \par set the mark alone on a row the Hebrew column — where the same whitespace
        lands in vertical mode and is discarded — never spent, and the columns drifted.
        """
        out = _transform(
            self._parallel(
                """<tei:p>
                שלום
                </tei:p>""",
                """<tei:note>Psalm 34:4.</tei:note>
                <tei:p>
                Exalt the Lord with me.
                </tei:p>""",
            ),
            layout="pairs",
        )
        left, right = self._sides(out)
        self.assertIn(r"\OSInterlinearNotemark{1}", right)
        self.assertIsNone(re.search(r"\n[ \t]*\n", right))
        self.assertEqual(left.count(r"\pstart"), right.count(r"\pstart"))

    def test_a_single_column_document_keeps_its_parskip(self):
        """Confined to parallel mode: nothing here touches ordinary numbered text."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div><tei:p>שלום</tei:p><tei:p>עולם</tei:p></tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        body = out.split(r"\begin{document}")[1]
        self.assertNotIn(r"\setlength{\parskip}{0pt}", body)
        self.assertNotIn(r"\skipnumbering\mbox{\strut}", body)


class TestPstartSkip(unittest.TestCase):
    r"""Space between one ``\pstart`` and the next.

    reledmac ``\pstart`` groups do not take ``\parskip`` between them, so without the hook
    there is no space between parallel blocks at all — what looks like separation is only
    the shorter column being padded out to the longer one.
    """

    PARALLEL = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
             xmlns:p="http://jewishliturgy.org/ns/processing">
      <tei:text><tei:body>
        <p:parallel column-order="primary_first">
          <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
          <p:parallelItem role="parallel" xml:lang="en"><tei:p>Hello</tei:p></p:parallelItem>
        </p:parallel>
      </tei:body></tei:text>
    </tei:TEI>"""

    SINGLE = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
      <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
    </tei:TEI>"""

    def test_the_hook_is_starred(self):
        r"""Unstarred, \AtEveryPstart prefixes \noindent, which makes reledpar treat the
        material as column content and give it a full-width row of its own — a blank line
        per \pstart rather than a skip."""
        out = _transform(self.SINGLE)
        self.assertIn(r"\AtEveryPstart*{\OSApplyKeep\vspace{\OSPstartSkip}}", out)
        self.assertNotIn(r"\AtEveryPstart{", out)

    def test_the_skip_is_halved_for_paired_columns(self):
        r"""\Columns runs the hook once for the left \pstart and again for the right one,
        so a paired compile would otherwise get twice a single-column one's skip."""
        self.assertIn(r"\newcommand{\OSPstartSkip}{0.5\parskip}", _transform(self.PARALLEL))
        self.assertIn(r"\newcommand{\OSPstartSkip}{\parskip}", _transform(self.SINGLE))

    def test_the_skip_follows_a_configured_paragraph_spacing(self):
        r"""A macro, not a length: typography.paragraphs.spacing rewrites \parskip further
        down the preamble, and the skip has to follow it rather than capture the default."""
        out = _transform(self.SINGLE)
        preamble = out.split(r"\begin{document}")[0]
        self.assertLess(
            preamble.index(r"\AtEveryPstart*"), len(preamble),
            "the hook must be defined in the preamble",
        )
        self.assertIn(r"{\parskip}", preamble)


class TestSingleStreamOmitsReledparOnly(unittest.TestCase):
    r"""\lineationR and the \...R lap macros live in reledpar, which is loaded only when
    the document has a parallel block. Emitting them anyway is an undefined control
    sequence at \begin{document}."""

    XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
      <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
    </tei:TEI>"""

    def test_no_reledpar_only_line_number_commands(self):
        out = _transform(self.XML)
        self.assertIn(r"\lineation{page}", out)
        for macro in (r"\lineationR", r"\leftlinenumR", r"\rightlinenumR"):
            self.assertNotIn(macro, out)

    def test_the_direction_safe_lap_is_not_parallel_only(self):
        """The single-column path laps through the same macro, so a Hebrew-only
        document has the identical bug latent."""
        self.assertIn(r"\renewcommand*{\leftlinenum}{\hbox dir TLT", _transform(self.XML))


class TestInlineLanguageSwitch(unittest.TestCase):
    r"""``\selectlanguage`` is polyglossia's *block* switch; ``\foreignlanguage`` is the
    inline one.

    Used inside a line, the block form contributes vertical material of its own. In
    ``\Columns`` that material escapes onto the shared page list -- reledpar re-selects
    each column's language around every line it sets -- and costs a row in *both* columns.
    Measured on the Birnbaum Amidah: an English rubric in the Hebrew column opened a 34.1pt
    gap where a row is 13.5, cutting the facing column's paragraph in half. Swapping only
    the switch, with the same content and the same pagination, gives 13.6.

    So no emitted TeX may use ``\selectlanguage`` inline. The one exception is the
    ``\pdfstringdefDisableCommands`` block, which defines it away for bookmark strings.
    """

    XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
      <tei:text><tei:body>
        <tei:div><tei:head>Genesis</tei:head>
          <tei:p>In the beginning<tei:note type="instruction" xml:lang="en">Reader:</tei:note></tei:p>
        </tei:div>
      </tei:body></tei:text>
    </tei:TEI>"""

    def test_no_inline_selectlanguage_survives(self):
        out = _transform(self.XML)
        body = out.split(r"\begin{document}")[1]
        self.assertNotIn(r"\selectlanguage", body)
        preamble = out.split(r"\begin{document}")[0]
        # Only where hyperref is told to ignore it.
        self.assertEqual(1, preamble.count(r"\selectlanguage"))
        self.assertIn(r"\def\selectlanguage#1{}", preamble)

    def test_bookmarks_keep_their_titles(self):
        r"""\foreignlanguage takes two arguments and the title is the *second*:
        \def\foreignlanguage#1#2{#1} would put "english" in every bookmark."""
        self.assertIn(r"\def\foreignlanguage#1#2{#2}", _transform(self.XML))

    def test_the_switch_wraps_its_text_in_a_group(self):
        out = _transform(self.XML)
        self.assertIn(r"{\textdir TLT\foreignlanguage{english}{Genesis}}", out)

    def test_every_emitted_group_is_balanced(self):
        """Turning a prefix switch into one that takes an argument adds a brace at every
        one of the twenty-five sites; an unbalanced one is a LaTeX error, not a test
        failure, so check the shape here where it is cheap."""
        body = _transform(self.XML).split(r"\begin{document}")[1]
        depth = 0
        for char in body:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                self.assertGreaterEqual(depth, 0, "a group closes that was never opened")
        self.assertEqual(0, depth, "a group is left open")


class TestLineNumberStyle(unittest.TestCase):
    r"""``\linenumberstyle`` is a declaration, not a formatter.

    Its argument is a style *name* -- ``arabic``, ``roman`` -- and its only job is to define
    ``\linenumrep``, which reledmac does once as it loads (``reledmac.sty:758-762``).
    Redefining it afterwards is never consulted, and had anything called it the way reledmac
    does, it would have set the word "arabic" in the margin. reledpar's ``\linenumberstyle*``
    forwards to both series, so leaving a broken definition there is a trap for anyone who
    reaches for the documented API.

    Nothing is lost by not touching it: the left series is already left-to-right, because
    ``\ledlinenum`` opens with ``\ifluatex\textdir TLT\fi`` (``reledmac.sty:770-774``).
    """

    XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
      <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
    </tei:TEI>"""

    PARALLEL = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
             xmlns:p="http://jewishliturgy.org/ns/processing">
      <tei:text><tei:body>
        <p:parallel column-order="primary_first">
          <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
          <p:parallelItem role="parallel" xml:lang="en"><tei:p>Hello</tei:p></p:parallelItem>
        </p:parallel>
      </tei:body></tei:text>
    </tei:TEI>"""

    def test_linenumberstyle_is_left_alone(self):
        """Matching test_typography_tex.py, so both halves of the codebase agree."""
        self.assertNotIn(r"\linenumberstyle", _transform(self.XML))
        self.assertNotIn(r"\linenumberstyle", _transform(self.PARALLEL, layout="pairs"))

    def test_the_right_series_still_gets_its_direction(self):
        r"""The asymmetry is the point. reledpar's \l@dlinenumR carries no \textdir TLT of
        its own, so \linenumrepR and \sublinenumrepR must keep theirs -- deleting this pair
        alongside \linenumberstyle would reverse the right column's digits."""
        out = _transform(self.PARALLEL, layout="pairs")
        self.assertIn(r"\renewcommand*{\linenumrepR}[1]{\hbox{\textdir TLT\@arabic{#1}}}", out)
        self.assertIn(r"\renewcommand*{\sublinenumrepR}[1]{\hbox{\textdir TLT\@arabic{#1}}}", out)

    def test_a_single_stream_needs_no_right_series(self):
        self.assertNotIn(r"\linenumrepR", _transform(self.XML))


class TestPreambleIsAllTeX(unittest.TestCase):
    r"""The preamble must contain only TeX.

    An XSLT comment that loses its opening ``<!--`` is still well-formed XML -- the prose
    simply becomes a text node and is copied into the output. It lands in the preamble,
    where LaTeX reads it as body text and dies with "Missing \begin{document}". No unit
    test noticed, because none of them looked at what the preamble was made of.
    """

    XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
      <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
    </tei:TEI>"""

    def test_no_stray_prose_before_begin_document(self):
        out = _transform(self.XML)
        preamble = out.split(r"\begin{document}")[0]
        # The preamble embeds Lua, whose lines are not TeX; skip from \directlua to the
        # brace that closes it.
        stray, in_lua = [], False
        for line in preamble.splitlines():
            if "directlua" in line:
                in_lua = True
            if in_lua:
                if line.rstrip().endswith("}"):
                    in_lua = False
                continue
            if line.strip() and not line.lstrip().startswith(("\\", "%", "}", "{", "]")):
                stray.append(line)
        self.assertEqual([], stray, "non-TeX lines in the preamble")

    def test_no_xml_comment_delimiters_survive(self):
        self.assertNotIn("-->", _transform(self.XML))


class TestEmptyLinesInAColumn(unittest.TestCase):
    r"""Every empty line inside a parallel ``\pstart`` must carry a strut.

    ``\Columns`` cuts each column into slices of ``\baselineskip``. A line of no height
    leaves the glue before it inside its own slice instead of at the cut, and reledpar then
    ``\unvbox``-es that slice onto the shared page list, where it moves both columns. A
    strut gives the line the height of ordinary text, so it becomes a row of its own column
    and nothing escapes. Measured: without the strut, two adjacent rubrics in the Hebrew
    column opened a 6pt gap in the middle of a word in the English one.
    """

    XML = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
      <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
    </tei:TEI>"""

    def test_the_instruction_macros_strut_the_line_they_break_from(self):
        r"""\ifhmode, not \leavevmode: end the line the rubric interrupts, but only when
        there is one. At the head of a \pstart there is none, and breaking there spends a
        row -- in one column only, since the facing column sets the same rubric run-in."""
        out = _transform(self.XML)
        for macro in (r"\OSInstructionBlock", r"\OSInstructionLine"):
            self.assertIn(
                r"\newcommand{" + macro + r"}[1]{\ifhmode\unskip\strut\newline\fi"
                r"{\OSKeepAttr=3\relax\bfseries #1}\newline\ignorespaces}",
                out,
            )
        self.assertNotIn(r"\leavevmode\unskip\strut", out)

    def test_the_suppressed_heading_placeholder_is_strutted(self):
        r"""The placeholder that keeps a suppressed heading's \pstart non-empty is itself a
        line of the column, and an unstrutted one leaks the same way."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">
                <tei:div corresp="urn:x-opensiddur:text:prayer:x">
                  <tei:head>SAME</tei:head><tei:p>שלום</tei:p>
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div corresp="urn:x-opensiddur:text:prayer:x">
                  <tei:head>SAME</tei:head><tei:p>Hello</tei:p>
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, layout="pairs")
        self.assertIn(r"\mbox{\strut}", out)
        self.assertNotRegex(out, r"\\mbox\{\}\\par")


class TestConditionalRuleWidth(unittest.TestCase):
    r"""The conditional rule is measured by its column, not by the page.

    reledpar narrows ``\hsize`` to the column inside a parallel raw box but leaves
    ``\linewidth`` at the page width — the same trap already documented for the
    instruction boxes. A ``\linewidth`` box is twice the width it has to fit in, so its
    centred rule lands outside the column it belongs to.
    """

    def test_the_default_rule_uses_hsize_less_the_paragraph_indents(self):
        """An indented paragraph — a list item, an interleaved translation — narrows its
        lines with \\leftskip and \\rightskip, not \\hsize."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>Hi</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(
            r"\newcommand{\OSCondRule}{\leavevmode\hbox to \OSMeasure"
            r"{\hss\rule{0.25\hsize}{0.4pt}\hss}}",
            out,
        )
        self.assertIn(
            r"\newcommand{\OSMeasure}{\dimexpr\hsize-\leftskip-\rightskip\relax}", out
        )


class TestTrailingLineBreak(unittest.TestCase):
    r"""A ``tei:lb`` that ends its paragraph is dropped.

    Verse is encoded line by line, and a source closes the last line of a paragraph with
    a break like every other. ``\\`` with nothing after it starts an empty line, which
    takes a line number and sets a blank row before the paragraph ends.
    """

    BREAK = r"\leavevmode\\{}"

    @staticmethod
    def _body(xml: str, **params) -> str:
        return _transform(xml, **params).split(r"\begin{document}", 1)[1]

    @staticmethod
    def _single(p: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>{p}</tei:body></tei:text>
        </tei:TEI>"""

    def test_a_break_between_lines_is_kept_and_the_last_is_dropped(self):
        body = self._body(self._single("<tei:p>one<tei:lb/>two<tei:lb/>\n</tei:p>"))
        self.assertEqual(1, body.count(self.BREAK))
        self.assertRegex(body, r"one\\leavevmode\\\\\{\}\s*two\s*\\pend")

    def test_the_numberless_verse_terminator_does_not_keep_a_break(self):
        body = self._body(self._single(
            '<tei:p><tei:milestone unit="verse" n="1"/>one<tei:lb/>'
            '<tei:milestone unit="verse"/></tei:p><tei:p>two</tei:p>'))
        self.assertNotIn(self.BREAK, body)

    def test_a_break_before_a_numbered_verse_is_kept(self):
        body = self._body(self._single(
            '<tei:p><tei:milestone unit="verse" n="1"/>one<tei:lb/>'
            '<tei:milestone unit="verse" n="2"/>two</tei:p>'))
        self.assertEqual(1, body.count(self.BREAK))

    def test_a_break_before_a_rubric_is_dropped(self):
        """The rubric's own macro breaks the line; two breaks set an empty one."""
        body = self._body(self._single(
            '<tei:p>one<tei:lb/><tei:note type="instruction">Say:</tei:note>two</tei:p>'))
        self.assertNotIn(self.BREAK, body)

    def test_columns_keep_their_pairing(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:p>א<tei:lb/>ב<tei:lb/></tei:p></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:p>A<tei:lb/>B<tei:lb/></tei:p></p:parallelItem>
            </p:parallel>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:p>ג<tei:lb/></tei:p></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:p>C</tei:p></p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        for layout in ("pages", "pairs", "interleaved"):
            with self.subTest(layout=layout):
                body = self._body(xml, layout=layout)
                self.assertEqual(2, body.count(self.BREAK))
                self.assertNotRegex(body, r"\\leavevmode\\\\\{\}\s*\\pend")
                if layout != "interleaved":
                    left = body.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
                    right = body.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
                    self.assertEqual(left.count(r"\pstart"), right.count(r"\pstart"))


class TestHeadingNotes(unittest.TestCase):
    r"""A note on a whole headed division is set after the heading's title.

    The compiler sets a note that targets a division as one of the division's own
    children, beside its head. Left in the flow it was a mark alone on a line between the
    heading and the text; set with the heading it follows the title it is about.
    """

    NOTE = ('<tei:note type="commentary" target="urn:x-opensiddur:text:t:sec">'
            '<tei:p>About the section.</tei:p></tei:note>')
    EDTEXT = r"\edtext{\OSInterlinearNotemark"

    @staticmethod
    def _body(xml: str, **params) -> str:
        return _transform(xml, **params).split(r"\begin{document}", 1)[1]

    def _single(self, inner: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>
            <tei:div corresp="urn:x-opensiddur:text:t:sec">{self.NOTE}
              <tei:head>Section</tei:head>{inner}
            </tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""

    def _parallel(self, primary_body: str = "", parallel_body: str = "",
                  titles=("כותרת", "Title"), lead: str = "") -> str:
        he, en = titles
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he">{lead and '<tei:p>א</tei:p>'}
                <tei:div corresp="urn:x-opensiddur:text:t:sec">
                  <tei:head>{he}</tei:head><tei:p>שלום</tei:p>{primary_body}
                </tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">{lead and '<tei:p>A</tei:p>'}
                <tei:div corresp="urn:x-opensiddur:text:t:sec">{self.NOTE}
                  <tei:head>{en}</tei:head><tei:p>Hello</tei:p>{parallel_body}
                </tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""

    @staticmethod
    def _arg(body: str, macro: str) -> str:
        """The balanced-brace argument of the first ``macro{``."""
        rest = body.split(macro + "{", 1)[1]
        depth, chars = 1, []
        for ch in rest:
            depth += {"{": 1, "}": -1}.get(ch, 0)
            if depth == 0:
                break
            chars.append(ch)
        return "".join(chars)

    def test_a_heading_in_the_flow_carries_its_divisions_note(self):
        body = self._body(self._single("<tei:p>Text</tei:p>"))
        self.assertEqual(1, body.count(self.EDTEXT))
        title = self._arg(body, r"\OSheadA")
        self.assertIn(self.EDTEXT, title)
        self.assertLess(title.index("Section"), title.index(self.EDTEXT))

    def test_a_division_of_heading_and_rubric_alone_still_carries_it(self):
        """The haggadah has sections with no text to anchor on."""
        body = self._body(self._single(
            '<tei:p><tei:note type="instruction">Wash the hands.</tei:note></tei:p>'))
        self.assertIn(self.EDTEXT, self._arg(body, r"\OSheadA"))

    def test_a_note_in_the_first_paragraph_stays_in_it(self):
        xml = self._single(
            '<tei:p>Text<tei:note type="commentary">On the text.</tei:note></tei:p>')
        body = self._body(xml.replace(self.NOTE, ""))
        self.assertNotIn(self.EDTEXT, self._arg(body, r"\OSheadA"))
        self.assertEqual(1, body.count(self.EDTEXT))

    def test_the_heading_set_across_the_page_carries_it(self):
        for layout in ("pairs", "interleaved"):
            with self.subTest(layout=layout):
                body = self._body(self._parallel(), layout=layout,
                                  **{"headings-from": "combined"})
                self.assertEqual(1, body.count(self.EDTEXT))
                spanning = body.split(r"\beginnumbering", 2)
                # The heading's own numbered section comes first, before any column.
                self.assertIn(self.EDTEXT, spanning[1])
                self.assertIn(r"\numberlinefalse", spanning[1])
                translation = self._arg(body, r"\OSheadTranslation")
                self.assertLess(translation.index("Title"), translation.index(self.EDTEXT))

    def test_on_facing_pages_the_page_whose_division_it_is_carries_it(self):
        """Facing pages hoist nothing, so the note stays with the heading of the division
        it is on — here the English one, on the right-hand page."""
        body = self._body(self._parallel(), layout="pages",
                          **{"headings-from": "combined"})
        self.assertEqual(1, body.count(self.EDTEXT))
        right = body.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
        self.assertIn(self.EDTEXT, self._arg(right, r"\OSheadA"))

    def test_a_heading_set_across_the_page_without_notes_is_unchanged(self):
        body = self._body(self._parallel().replace(self.NOTE, ""), layout="pairs")
        self.assertIn(
            r"{\parfillskip=0pt\interlinepenalty=10000\relax \begin{hebrew}\OSApplyKeep \OSheadA",
            body)

    def test_a_suppressed_heading_keeps_the_note_on_its_placeholder_row(self):
        """Further into a block the heading is not hoisted; where the titles agree the
        second column suppresses its copy, and the mark goes on that placeholder row."""
        xml = self._parallel(titles=("Kaddish", "Kaddish"), lead="yes")
        body = self._body(xml, layout="pairs", **{"headings-from": "combined"})
        self.assertEqual(1, body.count(self.EDTEXT))
        right = body.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
        left = body.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
        self.assertRegex(right, r"\\mbox\{\\strut\}\\leavevmode\{\\OSRTLfalse\\edtext")
        self.assertEqual(left.count(r"\pstart"), right.count(r"\pstart"))

    def test_interleaved_sets_a_suppressed_headings_note_on_a_placeholder(self):
        xml = self._parallel(titles=("Kaddish", "Kaddish"), lead="yes")
        body = self._body(xml, layout="interleaved", **{"headings-from": "combined"})
        self.assertEqual(1, body.count(self.EDTEXT))
        self.assertRegex(body, r"\\mbox\{\\strut\}\\leavevmode\{\\OSRTLfalse\\edtext")


class TestLabelledLists(unittest.TestCase):
    r"""``tei:list``, ``tei:label`` and ``tei:item`` are set as a list.

    All three used to fall through the ``match="*"`` pass-through in pass 1, which
    descends without emitting a sentinel. The label's text ran into the head of the
    paragraph it labelled, and the items lost every boundary between them: Birnbaum's
    comparison of his new translation against the old — two labelled blocks in the
    print — came out as one continuous run of prose, distinguished only by the label
    text embedded mid-flow.
    """

    GLOSS = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
      <tei:text><tei:front>
        <tei:div xml:lang="en">
          <tei:p>The following parallel columns will illustrate the difference.</tei:p>
          <tei:list type="gloss">
            <tei:label>THE NEW TRANSLATION</tei:label>
            <tei:item>
              <tei:p>Blessed art thou.</tei:p>
              <tei:p>Through thy abundant goodness.</tei:p>
            </tei:item>
            <tei:label>THE OLD TRANSLATION</tei:label>
            <tei:item><tei:p>Blessed art thou, who feedest.</tei:p></tei:item>
          </tei:list>
          <tei:p>Here and there new interpretations.</tei:p>
        </tei:div>
      </tei:front><tei:body><tei:p>Body.</tei:p></tei:body></tei:text>
    </tei:TEI>"""

    def _front(self, xml: str = None) -> str:
        out = _transform(xml if xml is not None else self.GLOSS)
        return out[out.index(r"\frontmatter"):out.index(r"\mainmatter")]

    def test_the_label_is_set_on_a_line_of_its_own(self):
        """The regression test for the reported defect: the label's paragraph closes
        before the paragraph it labels opens, rather than sharing a \\pstart with it."""
        front = self._front()
        self.assertIn(r"\OSListLabel{", front)
        label_at = front.index("THE NEW TRANSLATION")
        item_at = front.index("Blessed art thou.")
        self.assertLess(label_at, item_at)
        # ...and a \pend falls between the two.
        self.assertIn(r"\pend", front[label_at:item_at])

    def test_each_paragraph_of_an_item_is_indented(self):
        front = self._front()
        for text in ("Blessed art thou.", "Through thy abundant goodness.",
                     "Blessed art thou, who feedest."):
            with self.subTest(text=text):
                self.assertIn(r"\pstart\relax \OSListItemPar \OSListItem{" + text, front)

    def test_prose_around_the_list_is_not_indented(self):
        front = self._front()
        for text in ("The following parallel columns",
                     "Here and there new interpretations"):
            with self.subTest(text=text):
                self.assertIn(r"\pstart\relax " + text, front)
                self.assertNotIn(r"\OSListItemPar " + text, front)

    def test_the_label_is_not_a_heading(self):
        """It names an alternative inside a section; it does not open one. So it takes
        no running-head mark and no place in the PDF outline, and it stays out of the
        line numbering, which cites lines of the text."""
        front = self._front()
        self.assertIn("\\pstart\\relax \\skipnumbering\n\\OSListLabel{", front)
        self.assertNotIn(r"\InsertMark{OShead", front)
        self.assertNotIn(r"\addcontentsline", front)

    def test_an_english_label_in_a_hebrew_rooted_project_is_wrapped_ltr(self):
        """Birnbaum's introduction is English front matter realised by the English
        project and transcluded into a Hebrew index. Without the wrapper it reads
        backwards, which is what happened to the prose before it was grouped by its
        own language."""
        front = self._front()
        self.assertIn(
            r"\OSListLabel{{\textdir TLT\foreignlanguage{english}"
            r"{THE NEW TRANSLATION}}}",
            front,
        )

    def test_a_list_of_inline_items_separates_its_items(self):
        """The plain, label-less form the JPS 1917 books use. Each item is a paragraph
        of its own, and the list is closed off from the prose that follows it."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>
            <tei:p>Before.</tei:p>
            <tei:list><tei:item>Alpha</tei:item><tei:item>Beta</tei:item></tei:list>
            <tei:p>After.</tei:p>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertIn(r"\pstart\relax \OSListItemPar \OSListItem{Alpha}\pend", out)
        self.assertIn(r"\pstart\relax \OSListItemPar \OSListItem{Beta}\pend", out)
        self.assertIn(r"\pstart\relax After.\pend", out)

    def test_an_item_of_paragraphs_gets_no_second_break(self):
        r"""The item's last tei:p has already emitted one. A second would be a no-op
        here but would spend a blank strut line in a parallel stream."""
        front = self._front()
        self.assertNotIn(r"\pend\n\pend", front)
        self.assertEqual(front.count(r"\pstart"), front.count(r"\pend"))

    def test_a_list_on_one_side_does_not_desync_the_columns(self):
        r"""reledpar pairs the two sides by counting ``\pstart``...``\pend``, and a list
        is exactly the kind of thing only one side carries."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="en">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:list type="gloss">
                  <tei:label>NEW</tei:label>
                  <tei:item><tei:p>One.</tei:p><tei:p>Two.</tei:p></tei:item>
                </tei:list>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml, layout="pages")
        block = out[out.index(r"\begin{pages}"):out.index(r"\Pages")]
        left = block[block.index(r"\begin{Leftside}"):block.index(r"\end{Leftside}")]
        right = block[block.index(r"\begin{Rightside}"):block.index(r"\end{Rightside}")]
        self.assertEqual(left.count(r"\pstart"), right.count(r"\pstart"))
        self.assertEqual(left.count(r"\pend"), right.count(r"\pend"))
        self.assertIn(r"\OSListLabel{", right)

    def test_a_list_inside_a_note_separates_its_items_without_a_par(self):
        r"""``tei:note`` is emitted whole by pass 1, so a list nested in one — the JPS
        1917 index carries a 23-item list in a standoff note — never reaches the
        sentinel machinery and is rendered in mode="emit" instead. A ``\par`` inside
        ``\Bfootnote`` breaks reledmac's apparatus grouping, so the items are separated
        by ``\newline``."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>
            <tei:p>Text<tei:note>Preface.
              <tei:list><tei:item>Alpha</tei:item><tei:item>Beta</tei:item></tei:list>
            </tei:note>.</tei:p>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        note = out[out.index(r"\Bfootnote{"):]
        note = note[:note.index(r"\pend")]
        self.assertIn(r"\OSListItem{Alpha}\newline \OSListItem{Beta}", note)
        self.assertNotIn(r"\par", note)
        self.assertNotIn(r"\OSListItemPar", note)

    def test_a_standoff_note_label_is_left_alone(self):
        """The other use of tei:label names a standoff note, which is not text on the
        page. Only a label inside a list becomes a list label."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text>
            <tei:standOff type="notes">
              <tei:note target="#a"><tei:label>catchword</tei:label>A note.</tei:note>
            </tei:standOff>
            <tei:body><tei:p>Hi</tei:p></tei:body>
          </tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        # Scoped to the body: \OSListLabel is always defined in the preamble.
        body = out[out.index(r"\begin{document}"):]
        self.assertNotIn(r"\OSListLabel", body)


class TestParagraphOpeningBracket(unittest.TestCase):
    r"""A paragraph may begin with "[", and reledmac will eat it if we let it.

    ``\pstart`` is declared ``\newcommandx*{\pstart}[2][1,2,usedefault]`` -- **two**
    optional, bracket-delimited arguments -- and TeX skips spaces and newlines while
    scanning for one. Emitting

        \pstart
                  [We pray] for Israel, ...

    therefore parses as ``\pstart[We pray]``: the words become code run before the
    paragraph instead of text inside it, and the brackets vanish as delimiters. In the
    parallel Birnbaum that put a bare "We pray" in the gutter between the columns, with the
    English paragraph starting at "for Israel".

    Nothing else notices. The ``\pstart`` counts still match side for side, so the
    alignment invariants this module calls critical all stay green while the text is being
    set outside its column.

    Birnbaum's Kaddish de-Rabbanan and the Feinstein haggadah's
    "[This verse can be explained as follows:]" are both real instances.
    """

    #: ``\pstart`` followed only by whitespace and then a bracket: the defect itself.
    SWALLOWED = re.compile(r"\\pstart\s*\[")

    SINGLE = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
      <tei:text><tei:body>
        <tei:div><tei:p>[We pray] for Israel, for our teachers.</tei:p></tei:div>
      </tei:body></tei:text>
    </tei:TEI>"""

    PARALLEL = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
             xmlns:p="http://jewishliturgy.org/ns/processing">
      <tei:text><tei:body>
        <p:parallel column-order="primary_first">
          <p:parallelItem role="primary" xml:lang="he"><tei:p>עַל יִשְׂרָאֵל</tei:p></p:parallelItem>
          <p:parallelItem role="parallel" xml:lang="en"><tei:p>[We pray] for Israel.</tei:p></p:parallelItem>
        </p:parallel>
      </tei:body></tei:text>
    </tei:TEI>"""

    def test_no_pstart_hands_the_paragraph_to_reledmac_as_an_option(self):
        self.assertIsNone(self.SWALLOWED.search(_transform(self.SINGLE)))

    def test_the_bracket_and_its_words_survive_into_the_paragraph(self):
        out = _transform(self.SINGLE)
        self.assertIn("[We pray] for Israel, for our teachers.", out)

    def test_the_same_holds_in_a_parallel_block(self):
        out = _transform(self.PARALLEL, layout="pairs")
        self.assertIsNone(self.SWALLOWED.search(out))
        self.assertIn("[We pray] for Israel.", out)

    def test_the_columns_still_pair_pstart_for_pstart(self):
        r"""Whatever stops the scan must not add or drop a ``\pstart`` on one side: that
        would trade a typesetting bug for an alignment one."""
        out = _transform(self.PARALLEL, layout="pairs")
        left = out.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
        right = out.split(r"\begin{Rightside}")[1].split(r"\end{Rightside}")[0]
        self.assertEqual(left.count(r"\pstart"), right.count(r"\pstart"))
        self.assertEqual(left.count(r"\pend"), right.count(r"\pend"))

    def test_skipnumbering_still_follows_its_pstart(self):
        r"""Three emission sites write ``\pstart \skipnumbering``. Whatever is inserted
        between them must leave ``\skipnumbering`` applying to that same paragraph."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body>
            <tei:div><tei:head>A Heading</tei:head><tei:p>Text.</tei:p></tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        out = _transform(xml)
        self.assertTrue(re.search(r"\\pstart\S*\s*\\skipnumbering", out),
                        "\\skipnumbering no longer follows its \\pstart")


class TestRowsWithoutACounterpart(unittest.TestCase):
    """A block with text in one language has nothing to face, so it is set across the
    whole page, and the columns resume at the next block both languages set (#194)."""

    NOTE = "Birnbaum's note."
    # The shape Birnbaum's Hoshanot compile to: the English document marks the unit with
    # an empty correspondence anchor, and his note on the Hebrew is compiled onto it.
    APPARATUS_ONLY = (
        '<tei:p><tei:milestone unit="prayer-part" corresp="urn:x-opensiddur:text:t/1"/>'
        f'<tei:anchor xml:id="a1"><tei:note>{NOTE}</tei:note></tei:anchor></tei:p>'
    )

    @staticmethod
    def _document(rows, order: str = "primary_first") -> str:
        blocks = "".join(
            f"""<p:parallel column-order="{order}">
              <p:parallelItem role="primary" xml:lang="he">{he}</p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">{en}</p:parallelItem>
            </p:parallel>"""
            for he, en in rows
        )
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing"
                 xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="he">
          <tei:text><tei:body>{blocks}</tei:body></tei:text>
        </tei:TEI>"""

    def _body(self, rows, **params) -> str:
        params.setdefault("layout", "pairs")
        return _transform(self._document(rows, params.pop("order", "primary_first")),
                          **params).split(r"\begin{document}", 1)[1]

    def _sandwich(self, middle):
        return [("<tei:p>שלום</tei:p>", "<tei:p>Hello</tei:p>"), middle,
                ("<tei:p>ברוך</tei:p>", "<tei:p>Blessed</tei:p>")]

    def test_hebrew_alone_is_set_across_the_page(self):
        body = self._body(self._sandwich(("<tei:p>הושענא</tei:p>", "")))
        self.assertEqual(2, body.count(r"\begin{pairs}"))
        self.assertEqual(2, body.count(r"\Columns"))
        full_width = body.split(r"\Columns", 1)[1].split(r"\begin{pairs}", 1)[0]
        self.assertIn("הושענא", full_width)
        self.assertIn(r"\begin{hebrew}", full_width)
        self.assertIn(r"\beginnumbering", full_width)
        self.assertNotIn(r"\begin{Leftside}", full_width)
        self.assertNotRegex(body, r"\\pstart\\relax\s*\\pend")

    def test_an_apparatus_only_side_is_not_a_translation(self):
        body = self._body(self._sandwich(("<tei:p>הושענא</tei:p>", self.APPARATUS_ONLY)))
        self.assertEqual(2, body.count(r"\Columns"))
        full_width = body.split(r"\Columns", 1)[1].split(r"\begin{pairs}", 1)[0]
        self.assertEqual(1, body.count(self.NOTE))
        self.assertIn(self.NOTE, full_width)
        # The mark follows the text it annotates, in the same paragraph.
        self.assertRegex(full_width, r"\\pstart\\relax הושענא\s*\\leavevmode\{\\OSRTLfalse\\edtext")
        self.assertEqual(1, full_width.count(r"\pstart"))
        self.assertNotRegex(body, r"\\pstart\\relax\s*\\pend")

    def test_the_note_keeps_its_language(self):
        body = self._body(self._sandwich(("<tei:p>הושענא</tei:p>", self.APPARATUS_ONLY)))
        self.assertIn(r"\foreignlanguage{english}{" + self.NOTE + "}", body)

    def test_structural_rows_keep_page_labels_from_both_editions(self):
        """Birnbaum's long Taḥanun boundaries have no words on either side.

        Both editions' references need their labels, even though only one
        stream is rendered for a boundary-only block.
        """
        def boundary(label):
            return ('<tei:div><tei:milestone unit="section"/>'
                    f'<tei:anchor type="page-label" n="{label}"/>\n</tei:div>')

        for layout in ('pairs', 'pages', 'interleaved'):
            for order in ('primary_first', 'primary_last'):
                with self.subTest(layout=layout, order=order):
                    body = self._body(self._sandwich((boundary('he-page'), boundary('en-page'))),
                                      layout=layout, order=order)
                    self.assertEqual(1, body.count(r'\label{he-page}'))
                    self.assertEqual(1, body.count(r'\label{en-page}'))
                    self.assertRegex(body, r'\\label\{he-page\}\s*\\label\{en-page\}')

    def test_page_label_on_an_untranslated_side_survives_with_its_commentary(self):
        anchor = '<tei:anchor type="page-label" n="other-page"/>'
        for translated in (False, True):
            for layout in ('pairs', 'pages', 'interleaved'):
                with self.subTest(translated=translated, layout=layout):
                    text = '<tei:p>Untranslated text</tei:p>'
                    commentary = self.APPARATUS_ONLY.replace(
                        '<tei:note>', '<tei:note xml:lang="en">')
                    other = '<tei:div>' + anchor + commentary + '</tei:div>'
                    row = (other, text) if translated else (text, other)
                    body = self._body([row], layout=layout)
                    self.assertEqual(1, body.count(r'\label{other-page}'))
                    self.assertEqual(1, body.count(self.NOTE))
                    self.assertEqual(1, body.count(r'\pstart'))
                    self.assertNotIn(r'\Columns', body)

    def test_a_translation_alone_is_set_across_the_page_in_its_language(self):
        body = self._body(self._sandwich(("", "<tei:p>Untranslated English</tei:p>")))
        full_width = body.split(r"\Columns", 1)[1].split(r"\begin{pairs}", 1)[0]
        self.assertIn("Untranslated English", full_width)
        self.assertNotIn(r"\begin{hebrew}", full_width)

    def test_a_translation_alone_records_into_its_columns_running_heads(self):
        body = self._body(self._sandwich(
            ("", '<tei:div><tei:head>Section</tei:head><tei:p>English</tei:p></tei:div>')))
        full_width = body.split(r"\Columns", 1)[1].split(r"\begin{pairs}", 1)[0]
        self.assertIn(r"\InsertMark{OSheadAAlt}", full_width)
        self.assertNotIn(r"\InsertMark{OSheadA}", full_width)

    def test_adjacent_rows_in_one_language_share_one_section(self):
        body = self._body([("<tei:p>שלום</tei:p>", "<tei:p>Hello</tei:p>"),
                           ("<tei:p>אחד</tei:p>", ""),
                           ("<tei:p>שתיים</tei:p>", self.APPARATUS_ONLY)])
        full_width = body.split(r"\Columns", 1)[1]
        self.assertEqual(1, full_width.count(r"\beginnumbering"))
        self.assertEqual(2, full_width.count(r"\pstart"))

    def test_facing_pages_also_set_it_across_the_page(self):
        body = self._body(self._sandwich(("<tei:p>הושענא</tei:p>", self.APPARATUS_ONLY)),
                          layout="pages")
        self.assertEqual(2, body.count(r"\Pages"))
        full_width = body.split(r"\Pages", 1)[1].split(r"\begin{pages}", 1)[0]
        self.assertIn("הושענא", full_width)
        self.assertIn(self.NOTE, full_width)

    def test_primary_last_still_sets_the_lone_text(self):
        body = self._body(self._sandwich(("<tei:p>הושענא</tei:p>", self.APPARATUS_ONLY)),
                          order="primary_last")
        full_width = body.split(r"\Columns", 1)[1].split(r"\begin{pairs}", 1)[0]
        self.assertIn("הושענא", full_width)
        self.assertEqual(1, body.count(self.NOTE))

    def test_headings_conditions_and_markers_survive_in_order(self):
        condition = ('<tei:fs type="opensiddur:holiday-aggregate"><tei:f name="shabbat">'
                     '<tei:binary value="true"/></tei:f></tei:fs>')
        he = (f'<tei:div><tei:head>הושענות</tei:head><tei:p>'
              f'<tei:milestone unit="verse" n="7"/>לפני <j:conditional xml:id="c" type="marked">{condition}'
              f'</j:conditional>בשבת<j:endConditional target="#c"/> אחרי</tei:p></tei:div>')
        body = self._body(self._sandwich((he, self.APPARATUS_ONLY)))
        full_width = body.split(r"\Columns", 1)[1].split(r"\begin{pairs}", 1)[0]
        positions = [full_width.find(s) for s in
                     ("הושענות", "לפני", r"\OSCondStartInline", "בשבת",
                      r"\OSCondEndInline", "אחרי", self.NOTE)]
        self.assertNotIn(-1, positions)
        self.assertEqual(sorted(positions), positions)
        self.assertIn("7", full_width)

    def test_a_shared_row_stays_in_columns(self):
        """Notes beside a translation do not make it one-sided."""
        body = self._body([("<tei:p>שלום</tei:p>",
                            f'<tei:p>Hello<tei:note>{self.NOTE}</tei:note></tei:p>')])
        self.assertEqual(1, body.count(r"\Columns"))
        self.assertIn(self.NOTE, body.split(r"\begin{Rightside}", 1)[1])

    def test_interleaved_sets_the_notes_with_the_text_and_no_seam(self):
        body = self._body(self._sandwich(("<tei:p>הושענא</tei:p>", self.APPARATUS_ONLY)),
                          layout="interleaved")
        self.assertEqual(1, body.count(self.NOTE))
        self.assertEqual(2, body.count(r"\OSInterleavedSeam"))
        self.assertRegex(body, r"הושענא\s*\\leavevmode\{\\OSRTLfalse\\edtext")

    def test_a_rubric_inside_a_conditional_is_text(self):
        """A row whose only words are a conditional's rubric, on both sides, is a row both
        languages set: it stays in columns, and neither rubric is copied to the other."""
        condition = ('<tei:fs type="opensiddur:holiday-aggregate"><tei:f name="shabbat">'
                     '<tei:binary value="true"/></tei:f></tei:fs>')

        def rubric(lang):
            return (f'<tei:p><j:conditional xml:id="c{lang}"><tei:note type="instruction">'
                    f'On Hoshana Rabbah add:</tei:note>{condition}</j:conditional></tei:p>')

        body = self._body(self._sandwich((rubric("he"), rubric("en"))))
        self.assertEqual(1, body.count(r"\Columns"))
        self.assertEqual(2, body.count("On Hoshana Rabbah add:"))


class TestKeepTogether(unittest.TestCase):
    r"""What keeps lines and headings together across a page break (#198).

    These check that the pieces are emitted; ``test_keep_together_geometry`` typesets
    them and measures the pages.
    """

    SINGLE = """<?xml version="1.0" encoding="UTF-8"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
      <tei:text><tei:body>
        <tei:div><tei:head>Title</tei:head><tei:head>Translation</tei:head>
          <tei:p>Text</tei:p></tei:div>
      </tei:body></tei:text>
    </tei:TEI>"""

    @staticmethod
    def _parallel(left_title: str, right_title: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="en">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="en">
                <tei:div><tei:head>{left_title}</tei:head>
                  <tei:p>One</tei:p><tei:p>Two</tei:p></tei:div>
              </p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en">
                <tei:div><tei:head>{right_title}</tei:head>
                  <tei:p>Uno</tei:p></tei:div>
              </p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""

    @staticmethod
    def _body(out: str) -> str:
        return out.split(r"\begin{document}")[1]

    def test_widows_and_orphans_are_forbidden(self):
        out = _transform(self.SINGLE)
        self.assertIn(r"\clubpenalty=10000 \widowpenalty=10000", out)

    def test_a_heading_is_kept_whole_and_with_what_follows(self):
        body = self._body(_transform(self.SINGLE))
        opening = body.index(r"\begingroup\interlinepenalty=10000\relax")
        self.assertLess(opening, body.index(r"\OSheadA{"))
        self.assertIn(r"\pend\endgroup\OSKeepNext", body)
        self.assertLess(body.index(r"\OSheadA{"), body.index(r"\pend\endgroup\OSKeepNext"))
        self.assertLess(body.index(r"\pend\endgroup\OSKeepNext"), body.index("Text"))

    def test_a_translated_title_cannot_be_broken_from_its_heading(self):
        out = _transform(self.SINGLE)
        self.assertIn(r"\newcommand{\OSheadTranslation}[1]{\par\OSheadNobreak", out)
        self.assertIn(r"\newcommand{\OSheadNobreak}{\ifl@dpairing\else\nobreak\fi}", out)

    def test_the_next_pstart_takes_the_keep(self):
        out = _transform(self.SINGLE)
        self.assertIn(r"\AtEveryPstart*{\OSApplyKeep\vspace{\OSPstartSkip}}", out)

    def test_a_heading_across_the_page_is_kept_with_the_columns(self):
        body = self._body(_transform(self._parallel("Same", "Same"), layout="pairs"))
        spanning = body.split(r"\begin{pairs}")[0]
        self.assertIn(r"\OSheadA{", spanning)
        self.assertTrue(spanning.rstrip().endswith(r"\OSKeepNext"), spanning[-200:])

    def test_a_heading_in_a_column_is_tagged_as_one(self):
        body = self._body(_transform(self._parallel("Left", "Right"), layout="pairs",
                                     **{"headings-from": "both"}))
        for side in (r"\begin{Leftside}", r"\begin{Rightside}"):
            with self.subTest(side=side):
                column = body.split(side)[1].split(r"\end{")[0]
                self.assertLess(column.index(r"\OSKeepHeadBegin"), column.index(r"\OSheadA{"))
                self.assertLess(column.index(r"\OSheadA{"), column.index(r"\OSKeepHeadEnd\par"))

    def test_a_paragraph_break_in_a_column_is_tagged_as_one(self):
        body = self._body(_transform(self._parallel("Left", "Right"), layout="pairs"))
        left = body.split(r"\begin{Leftside}")[1].split(r"\end{Leftside}")[0]
        self.assertIn(r"\par\skipnumbering\OSKeepSep\par", left)

    def test_the_column_rules_are_installed_for_each_column_layout(self):
        for layout, patched in (("pairs", r"\apptocmd{\checkpb@columns}"),
                                ("pages", r"\apptocmd{\checkpageL}")):
            with self.subTest(layout=layout):
                out = _transform(self._parallel("Left", "Right"), layout=layout)
                self.assertIn("OSkeep = {", out)
                self.assertIn(patched, out)

    def test_no_column_rules_without_reledpar(self):
        for source, params in ((self.SINGLE, {}),
                               (self._parallel("Left", "Right"), {"layout": "interleaved"})):
            with self.subTest(params=params):
                out = _transform(source, **params)
                self.assertNotIn("function OSkeep.line(", out)
                self.assertNotIn(r"\do@lineLhook", out)

    def test_single_stream_rules_are_installed_everywhere(self):
        for source, params in ((self.SINGLE, {}),
                               (self._parallel("Left", "Right"), {"layout": "interleaved"}),
                               (self._parallel("Left", "Right"), {"layout": "pairs"})):
            with self.subTest(params=params):
                out = _transform(source, **params)
                self.assertIn("function OSkeep.single", out)
                self.assertIn(r"\appto\do@linehook{", out)
                self.assertIn(r"\patchcmd{\add@penalties}", out)

    def test_a_rubric_on_lines_of_its_own_is_tagged(self):
        out = _transform(self.SINGLE)
        for macro in ("OSInstructionBlock", "OSInstructionLine"):
            with self.subTest(macro=macro):
                definition = next(line for line in out.splitlines()
                                  if line.startswith(rf"\newcommand{{\{macro}}}"))
                self.assertIn(r"{\OSKeepAttr=3\relax\bfseries #1}", definition)
        run_in = next(line for line in out.splitlines()
                      if line.startswith(r"\newcommand{\instructionnote}"))
        self.assertNotIn("OSKeepAttr", run_in)

    def test_a_keep_reaches_a_heading_set_across_the_page(self):
        body = self._body(_transform(self._parallel("Same", "Same"), layout="pairs"))
        spanning = body.split(r"\begin{pairs}")[0]
        # Inside the title's language, which writes a record that would come between.
        self.assertLess(spanning.index(r"{\parfillskip=0pt"), spanning.index(r"\OSApplyKeep"))
        self.assertLess(spanning.index(r"\OSApplyKeep"), spanning.index(r"\OSheadA{"))


class TestEnglishForeignDirection(unittest.TestCase):
    def test_english_citation_is_scoped_inside_hebrew_prose(self):
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
        <tei:text><tei:body><tei:p>אשרי <tei:foreign xml:lang="en">Ps. cxlv.</tei:foreign>
        תהלה</tei:p></tei:body></tei:text></tei:TEI>'''
        out = _transform(xml)
        self.assertIn(r'\leavevmode{\textdir TLT\foreignlanguage{english}{\OSForeign{Ps. cxlv.}}}', out)
        self.assertEqual(out.count('Ps. cxlv.'), 1)
        self.assertIn('תהלה', out)

    def test_nested_hebrew_keeps_its_own_direction(self):
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
        <tei:text><tei:body><tei:p><tei:foreign xml:lang="en">Say
        <tei:foreign xml:lang="he">אשרי</tei:foreign>.</tei:foreign>
        </tei:p></tei:body></tei:text></tei:TEI>'''
        out = _transform(xml)
        self.assertIn(r'\texthebrew{\OSForeign{אשרי}}', out)
        self.assertIn(r'\textdir TLT\foreignlanguage{english}{\OSForeign{Say', out)


class TestNoteParagraphDirection(unittest.TestCase):
    def render_note(self, language, paragraphs):
        return _transform(f'''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="{language}">
          <tei:text><tei:body><tei:p>Anchor<tei:note type="commentary">{paragraphs}</tei:note></tei:p></tei:body></tei:text>
        </tei:TEI>''')

    def test_english_paragraph_overrides_hebrew_note_direction(self):
        out = self.render_note('he', '<tei:p xml:lang="en">Read by the Reader.</tei:p><tei:p>אשרי העם</tei:p>')
        self.assertIn(r'{{\textdir TLT\foreignlanguage{english}{Read by the Reader.}}}', out)
        self.assertIn('אשרי העם', out)

    def test_hebrew_paragraph_overrides_english_note_direction(self):
        out = self.render_note('en', '<tei:p>English explanation.</tei:p><tei:p xml:lang="he">אשרי העם</tei:p>')
        self.assertIn(r'{{\textdir TRT\foreignlanguage{hebrew}{אשרי העם}}}', out)
        self.assertIn('English explanation.', out)

    def test_each_later_paragraph_starts_a_new_line(self):
        out = self.render_note('he', '<tei:p xml:lang="en">Said by the Reader—</tei:p><tei:p>אשרי העם</tei:p>'
                                     '<tei:p>בחצצרות</tei:p>')
        note = out[out.index('Said by the Reader'):]
        self.assertEqual(2, note.count('\\newline '))
        self.assertLess(note.index('Said by the Reader'), note.index('\\newline '))
        self.assertLess(note.index('\\newline '), note.index('אשרי העם'))

    def test_a_single_paragraph_note_has_no_line_break(self):
        out = self.render_note('en', '<tei:p>Only one.</tei:p>')
        self.assertNotIn('\\newline', out[out.index('Only one.') - 200:])


class TestRendAndEscaping(unittest.TestCase):
    """tei:hi/@rend tokens, the escaping of TeX specials, and back matter."""

    @staticmethod
    def _p(body: str, lang: str = "en", back: str = "") -> str:
        return _transform(f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="{lang}">
          <tei:text><tei:body><tei:p>{body}</tei:p></tei:body>{back}</tei:text>
        </tei:TEI>""")

    def test_sup_is_superscript_not_bold(self):
        out = self._p('a<tei:hi rend="sup">*</tei:hi>')
        self.assertIn("\\textsuperscript{\\OSHighlightSuperscript{*}}", out)
        self.assertNotIn("\\OSHighlightBold{*}", out)

    def test_every_token_of_a_rend_is_applied(self):
        out = self._p('<tei:hi rend="small superscript">x</tei:hi>')
        self.assertIn("\\OSHighlightSmall{\\textsuperscript{\\OSHighlightSuperscript{x}}}", out)

    def test_a_layout_mark_sets_its_text_plain(self):
        out = self._p('<tei:hi rend="ketiv-only">(((x)))</tei:hi>')
        self.assertIn("(((x)))", out)
        self.assertNotIn("\\OSHighlight", out.split("\\begin{document}")[1])

    def test_a_backslash_is_escaped_once(self):
        out = self._p("a\\b")
        self.assertIn("a\\textbackslash{}b", out)
        self.assertNotIn("\\textbackslash\\{\\}", out)

    def test_back_matter_is_set_after_the_body(self):
        out = self._p("body text", back="<tei:back><tei:p>an afterword</tei:p></tei:back>")
        self.assertIn("\\backmatter", out)
        self.assertLess(out.index("body text"), out.index("an afterword"))

    def test_aramaic_is_set_in_hebrew_and_a_transliteration_is_not(self):
        out = self._p('<tei:foreign xml:lang="arc">קדיש</tei:foreign> and '
                      '<tei:foreign xml:lang="he-Latn">Kaddish</tei:foreign>')
        self.assertIn("\\texthebrew{", out)
        self.assertNotIn("\\texthebrew{Kaddish", out)
        self.assertNotIn("\\texthebrew{{\\textdir TLT", out)

    def test_a_transliteration_in_hebrew_reads_left_to_right(self):
        """Inside a Hebrew paragraph, a he-Latn run is wrapped left to right, not set bare."""
        out = self._p('שמע <tei:foreign xml:lang="he-Latn">Shema Yisrael</tei:foreign>', lang="he")
        self.assertIn("\\textdir TLT", out.split("\\begin{document}")[1])
        self.assertIn("\\OSForeign{{{\\textdir TLT\\foreignlanguage{english}{Shema}}}", out)
        self.assertNotIn("\\texthebrew{\\OSForeign", out)

    def test_align_right_nests_inside_other_styles(self):
        """A paragraph break inside a role's group is a fatal TeX error; align-right has none."""
        out = self._p('<tei:hi rend="bold align-right">ימין</tei:hi>').split("\\begin{document}")[1]
        self.assertIn("\\OSHighlightBold{\\hspace*{\\fill}", out)
        self.assertNotIn("\\par}", out)

    def test_a_note_inside_a_verse_milestone_is_set(self):
        out = self._p('<tei:milestone unit="verse" n="1"><tei:note>on the verse</tei:note>'
                      '</tei:milestone>text')
        self.assertIn("on the verse", out.split("\\begin{document}")[1])

    def test_notes_copied_with_a_rubric_keep_their_numbers(self):
        """In a parallel column a leaf holding a rubric is copied; its notes keep their serials."""
        import re
        par = ('<p:parallel><p:parallelItem role="primary" xml:lang="he"><tei:div><tei:p>עברית'
               '<tei:note>N-ONE</tei:note> עוד</tei:p></tei:div></p:parallelItem>'
               '<p:parallelItem role="parallel" xml:lang="en"><tei:div><tei:p>English'
               '<tei:note>N-TWO</tei:note> <j:conditional xml:id="c1"><tei:note>N-THREE</tei:note>'
               '<tei:note type="instruction">Say quietly:</tei:note></j:conditional> more'
               '<tei:note>N-FOUR</tei:note></tei:p></tei:div></p:parallelItem></p:parallel>')
        out = _transform(f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
                 xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
          <tei:text><tei:body>{par}</tei:body></tei:text></tei:TEI>""").split("\\begin{document}")[1]
        for serial, name in enumerate(("N-ONE", "N-TWO", "N-THREE", "N-FOUR"), start=1):
            with self.subTest(note=name):
                before = re.findall(r"OSFootnotemark\{(\d+)\}", out[:out.index(name)])
                self.assertEqual(before[-1], str(serial))

    def test_a_header_note_does_not_take_a_number(self):
        out = _transform("""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:teiHeader><tei:fileDesc><tei:sourceDesc><tei:bibl>b<tei:note>header</tei:note>
          </tei:bibl></tei:sourceDesc></tei:fileDesc></tei:teiHeader>
          <tei:text><tei:body><tei:p>word<tei:note>the first note</tei:note></tei:p></tei:body></tei:text>
        </tei:TEI>""")
        self.assertIn("\\OSInterlinearNotemark{1}", out)
        self.assertNotIn("\\OSInterlinearNotemark{2}", out)


class TestNotesInAHeading(unittest.TestCase):
    """A note in a tei:head is set with the heading, numbered from where it stands."""

    XML = """<?xml version="1.0"?>
    <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en"><tei:text><tei:body>
      <tei:div><tei:head>Heading<tei:note>On the heading.</tei:note></tei:head>
        <tei:p><tei:milestone unit="verse" n="1"/>text<tei:note>In the text.</tei:note></tei:p></tei:div>
      <tei:div><tei:head><tei:note>The first child.</tei:note>Second</tei:head><tei:p>more</tei:p></tei:div>
    </tei:body></tei:text></tei:TEI>"""

    def test_every_note_in_a_heading_is_printed(self):
        out = _transform(self.XML)
        for text in ("On the heading.", "The first child.", "In the text."):
            with self.subTest(text=text):
                self.assertEqual(1, out.count(text))

    def test_they_are_numbered_in_document_order(self):
        out = _transform(self.XML)
        order = [out.index(text) for text in ("On the heading.", "In the text.", "The first child.")]
        self.assertEqual(sorted(order), order)
        self.assertEqual(["1", "2", "3"], re.findall(r"OSInterlinearNotemark\{(\d+)\}", out))

    def test_a_note_is_set_inside_its_heading(self):
        out = _transform(self.XML)
        heading = out[out.index(r"\OSheadA{"):]
        self.assertLess(heading.index("On the heading."), heading.index(r"\phantomsection"))


class TestNotesNestedInAHeading(unittest.TestCase):

    def _heading(self, head: str, lang: str = "en") -> str:
        return _transform(f"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="{lang}"><tei:text><tei:body>
          <tei:div>{head}<tei:p><tei:milestone unit="verse" n="1"/>text</tei:p></tei:div>
        </tei:body></tei:text></tei:TEI>""")

    def test_a_note_inside_markup_in_a_heading_is_set_once(self):
        for head in ('<tei:head>Head <tei:hi rend="italic">it<tei:note>N</tei:note></tei:hi></tei:head>',
                     '<tei:head>Head <tei:foreign xml:lang="he">שם<tei:note>N</tei:note></tei:foreign></tei:head>'):
            with self.subTest(head=head):
                out = self._heading(head)
                self.assertEqual(1, out.count(r"\notenote{"))

    def test_a_rubric_in_a_heading_stays_in_it(self):
        out = self._heading('<tei:head>Head<tei:note type="instruction">Rise.</tei:note></tei:head>')
        self.assertEqual(1, out.count("Rise."))
        heading = out[out.index(r"\OSheadA{"):out.index(r"\phantomsection")]
        self.assertIn("Rise.", heading)

    def test_a_note_on_the_division_before_its_heading_comes_first(self):
        out = self._heading('<tei:note>On the division.</tei:note>'
                            '<tei:head>Head<tei:note>On the heading.</tei:note></tei:head>')
        self.assertLess(out.index("On the division."), out.index("On the heading."))
        self.assertEqual(["1", "2"], re.findall(r"OSInterlinearNotemark\{(\d+)\}", out))


class TestTextInAnotherLanguageThanTheRoot(unittest.TestCase):
    """English in a Hebrew-rooted body is its own stream, outside \\begin{hebrew}."""

    def _streams(self, body: str, lang: str = "he") -> int:
        out = _transform(f"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="{lang}"><tei:text><tei:body>
          {body}
        </tei:body></tei:text></tei:TEI>""")
        return out.split(r"\begin{document}")[1].count(r"\beginnumbering")

    def test_languages_of_one_direction_share_a_stream(self):
        self.assertEqual(1, self._streams(
            '<tei:div xml:lang="en"><tei:p>one</tei:p></tei:div>'
            '<tei:div xml:lang="en-US"><tei:p>two</tei:p></tei:div>', lang="en"))
        self.assertEqual(1, self._streams(
            '<tei:div xml:lang="he"><tei:p>אחת</tei:p></tei:div>'
            '<tei:div xml:lang="arc"><tei:p>תרתין</tei:p></tei:div>'))

    def test_a_page_break_between_two_sections_does_not_split_them(self):
        self.assertEqual(1, self._streams(
            '<tei:div xml:lang="en"><tei:p>one</tei:p></tei:div><tei:pb n="2"/>'
            '<!-- a comment --><tei:div xml:lang="en"><tei:p>two</tei:p></tei:div>'))

    def test_a_division_is_set_in_the_direction_of_its_text_not_its_tag(self):
        out = _transform("""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en"><tei:text><tei:body>
          <tei:div xml:lang="he"><tei:head>A heading</tei:head>
            <tei:p xml:lang="en">An English paragraph.</tei:p></tei:div>
        </tei:body></tei:text></tei:TEI>""")
        self.assertNotIn(r"\begin{hebrew}", out.split(r"\begin{document}")[1])

    def test_a_division_in_both_directions_is_set_in_its_own(self):
        out = _transform("""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en"><tei:text><tei:body>
          <tei:div xml:lang="he"><tei:p>שלום</tei:p>
            <tei:p xml:lang="en">An English paragraph.</tei:p></tei:div>
        </tei:body></tei:text></tei:TEI>""")
        body = out.split(r"\begin{document}")[1]
        self.assertLess(body.index(r"\begin{hebrew}"), body.index("שלום"))

    def test_an_english_section_is_not_set_right_to_left(self):
        out = _transform("""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he"><tei:text><tei:body>
          <tei:p><tei:milestone unit="verse" n="1"/>שלום</tei:p>
          <tei:div xml:lang="en"><tei:p>An English paragraph.</tei:p></tei:div>
          <tei:p>שוב</tei:p>
        </tei:body></tei:text></tei:TEI>""")
        body = out.split(r"\begin{document}")[1]
        english = body.index("An English paragraph.")
        self.assertGreater(english, body.index(r"\end{hebrew}"))
        self.assertLess(english, body.rindex(r"\begin{hebrew}"))
        self.assertLess(body.index("שלום"), body.index(r"\end{hebrew}"))
        self.assertGreater(body.index("שוב"), body.rindex(r"\begin{hebrew}"))



class TestInlineRoles(unittest.TestCase):
    """Each kind of inline text is set in its role's macro (typography_tex.INLINE_ROLE_MACROS)."""

    @staticmethod
    def _body(content: str, lang: str = "en") -> str:
        out = _transform(f"""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="{lang}">
          <tei:text><tei:body>{content}</tei:body></tei:text>
        </tei:TEI>""")
        return out.split("\\begin{document}")[1]

    def test_a_poetry_line_is_set_in_its_role(self):
        body = self._body("<tei:lg><tei:l>first line</tei:l><tei:l>second</tei:l></tei:lg>")
        self.assertIn(r"\OSPoetryLine{first line}", body)
        self.assertIn(r"\OSPoetryLine{second}", body)

    def test_the_line_role_is_outside_a_highlight_in_it(self):
        """So the highlight's own role, the inner one, overrides the line's."""
        body = self._body('<tei:lg><tei:l>a <tei:hi rend="italic">b</tei:hi></tei:l></tei:lg>')
        self.assertIn(r"\OSPoetryLine{\OSHighlightItalic{b}}", body)
        self.assertNotIn(r"\OSHighlightItalic{\OSPoetryLine", body)

    def test_a_note_in_a_line_is_not_set_in_the_line_role(self):
        body = self._body("<tei:lg><tei:l>words<tei:note>a note</tei:note></tei:l></tei:lg>")
        self.assertIn(r"\OSPoetryLine{words}", body)
        self.assertNotIn(r"\OSPoetryLine{a note", body)

    def test_the_nearest_container_wins(self):
        body = self._body("<tei:list><tei:item><tei:lg><tei:l>in a line</tei:l></tei:lg></tei:item>"
                          "<tei:item><tei:p>a block item</tei:p></tei:item></tei:list>")
        self.assertIn(r"\OSPoetryLine{in a line}", body)
        self.assertNotIn(r"\OSListItem{in a line", body)
        self.assertIn(r"\OSListItem{a block item}", body)

    def test_a_rubric_inside_a_highlight_keeps_the_line_role_in_a_parallel_column(self):
        """Pairing copies a leaf holding a rubric out of its tree; the copy still knows its line."""
        out = _transform("""<?xml version="1.0" encoding="UTF-8"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:lg><tei:l>שלום</tei:l></tei:lg></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:lg><tei:l>Hello <tei:hi rend="italic">x<tei:note type="instruction">say</tei:note></tei:hi> world</tei:l></tei:lg></p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>""")
        self.assertIn(r"\OSPoetryLine{\OSHighlightItalic{x", out)

    def test_prose_is_not_set_in_a_container_role(self):
        body = self._body("<tei:p>just prose</tei:p>")
        self.assertNotIn(r"\OSPoetryLine", body)
        self.assertNotIn(r"\OSListItem", body)

    def test_each_reading_form_is_set_in_its_role(self):
        body = self._body(
            "<tei:p><tei:choice><tei:abbr>abbr</tei:abbr><tei:expan>expan</tei:expan></tei:choice> "
            "<tei:choice><tei:sic>sic</tei:sic><tei:corr>corr</tei:corr></tei:choice> "
            "<tei:choice><tei:expan>only expan</tei:expan></tei:choice> "
            "<tei:choice><tei:sic>only sic</tei:sic></tei:choice> "
            "<tei:choice><j:option>one</j:option><j:option>two</j:option></tei:choice></tei:p>")
        self.assertIn(r"\OSAbbreviation{abbr}", body)
        self.assertNotIn("expan}", body.replace(r"\OSExpansion{only expan}", ""))
        self.assertIn(r"\OSCorrection{corr}", body)
        self.assertIn(r"\OSExpansion{only expan}", body)
        self.assertIn(r"\OSPrintedError{only sic}", body)
        self.assertIn(r"one (\OSAlternativeReading{two})", body)

    def test_a_qere_alone_and_a_ketiv_alone(self):
        body = self._body("<tei:p><tei:choice><j:read>r</j:read></tei:choice> "
                          "<tei:choice><j:written>w</j:written></tei:choice></tei:p>")
        self.assertIn(r"\OSQere{r}", body)
        self.assertIn(r"\OSKetiv{w}", body)
        self.assertNotIn("(", body.split(r"\OSQere{r}")[1].split(r"\OSKetiv")[0])

    def test_a_reference_is_set_in_its_role(self):
        body = self._body('<tei:p><tei:ref target="https://example.org/">a link</tei:ref> '
                          '<tei:ref>bare</tei:ref></tei:p>')
        self.assertIn(r"\href{https://example.org/}{\OSReference{a link}}", body)
        self.assertIn(r"\OSReference{bare}", body)

    def test_a_foreign_phrase_is_set_in_its_role(self):
        body = self._body('<tei:p>say <tei:foreign xml:lang="la">ecce</tei:foreign></tei:p>')
        self.assertIn(r"\OSForeign{ecce}", body)
        self.assertNotIn(r"\textit", body)

    def test_every_styled_rend_token_has_its_role(self):
        for token, macro in (("italic", "OSHighlightItalic"), ("bold", "OSHighlightBold"),
                             ("small-caps", "OSHighlightSmallCaps"), ("smallcaps", "OSHighlightSmallCaps"),
                             ("large", "OSHighlightLarge"), ("small", "OSHighlightSmall")):
            with self.subTest(token=token):
                body = self._body(f'<tei:p><tei:hi rend="{token}">x</tei:hi></tei:p>')
                self.assertIn(rf"\{macro}{{x}}", body)
        for token in ("sup", "superscript", "raised", "suspended"):
            with self.subTest(token=token):
                body = self._body(f'<tei:p><tei:hi rend="{token}">x</tei:hi></tei:p>')
                self.assertIn(r"\textsuperscript{\OSHighlightSuperscript{x}}", body)
