r"""The interleaved parallel layout, as the stylesheet emits it.

`typography.parallel.layout: interleaved` sets a parallel text in one column: each block
the compiler aligned, then its translation, then the next block. These tests assert on the
emitted ``.tex``; what TeX makes of it — which margin the numbers land in, which lines are
counted — is measured in ``test_interleaved_geometry``.
"""

import re
import unittest

from opensiddur.exporter.tex.typography_tex import _NAMED_SIZE_COMMANDS
from opensiddur.exporter.typography import InterleavedConfig, InterleavedLineNumbers
from opensiddur.tests.exporter.stylesheet_helpers import transform

_TEI = """<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
  <tei:text><tei:body>
{blocks}
  </tei:body></tei:text>
</tei:TEI>"""

_BLOCK = """    <p:parallel column-order="{order}">
      <p:parallelItem role="primary" xml:lang="he">{primary}</p:parallelItem>
      <p:parallelItem role="parallel" xml:lang="en">{parallel}</p:parallelItem>
    </p:parallel>"""

# Three blocks: two words each side, one paragraph each.
_WORDS = (("אחד", "One"), ("שתיים", "Two"), ("שלוש", "Three"))


def _document(pairs, order: str = "primary_first") -> str:
    return _TEI.format(blocks="\n".join(
        _BLOCK.format(order=order, primary=primary, parallel=parallel)
        for primary, parallel in pairs
    ))


def _paragraphs(order: str = "primary_first") -> str:
    return _document(
        [(f"<tei:p>{he}</tei:p>", f"<tei:p>{en}</tei:p>") for he, en in _WORDS], order
    )


def _transform(xml: str, **params) -> str:
    return transform(xml, **{"layout": "interleaved", **params})


def _split(out: str) -> tuple[str, str]:
    preamble, body = out.split(r"\begin{document}", 1)
    return preamble, body


def _environments(body: str, name: str) -> list[str]:
    return re.findall(r"\\begin\{" + name + r"\}(.*?)\\end\{" + name + r"\}", body, re.S)


class TestInterleavedPreamble(unittest.TestCase):
    def setUp(self):
        self.preamble, _ = _split(_transform(_paragraphs()))

    def test_reledpar_is_not_loaded(self):
        self.assertNotIn(r"\usepackage{reledpar}", self.preamble)

    def test_no_reledpar_declarations(self):
        """Every one of these is undefined without reledpar, and fatal to call."""
        for macro in (r"\lineationR", r"\linenummarginR", r"\leftlinenumR", r"\linenumrepR",
                      r"\setRlineflag", r"\Columns", r"\Lcolwidth"):
            self.assertNotIn(macro, self.preamble)

    def test_numbers_still_default_to_the_outer_margin(self):
        # The book is right-bound by default, which reledmac, assuming a left binding,
        # calls the inner margin.
        self.assertIn(r"\linenummargin{inner}", self.preamble)

    def test_paragraph_skip_is_not_halved(self):
        """Halving is for \\Columns, which runs the \\pstart hook once per column."""
        self.assertIn(r"\newcommand{\OSPstartSkip}{\parskip}", self.preamble)

    def test_the_pstart_hook_knows_the_seam(self):
        hooks = re.findall(r"\\AtEveryPstart\*\{.*", self.preamble)
        self.assertEqual(1, len(hooks))
        self.assertIn(r"\OSInterleavedSpacing", hooks[0])
        self.assertIn(r"\OSPstartSkip", hooks[0])

    def test_stylesheet_defaults_are_the_models(self):
        """The settings stage writes a macro only for a setting a file names, so the
        stylesheet's default is what an unset setting means."""
        defaults = InterleavedConfig()

        def macro(name):
            return re.search(r"\\newcommand\{\\" + name + r"\}\{(.*)\}\n", self.preamble).group(1)

        self.assertEqual(_NAMED_SIZE_COMMANDS[defaults.translation_size],
                         macro("OSInterleavedSize"))
        self.assertEqual(defaults.translation_indent, macro("OSInterleavedIndent"))
        self.assertEqual(defaults.spacing, macro("OSInterleavedSpacing"))
        self.assertIs(defaults.line_numbers, InterleavedLineNumbers.PRIMARY)
        self.assertIn(r"\numberlinefalse", macro("OSInterleavedNumbering"))

    def test_a_document_without_a_parallel_text_is_untouched(self):
        xml = """<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body><tei:p>שלום</tei:p></tei:body></tei:text></tei:TEI>"""
        self.assertEqual(_transform(xml), _transform(xml, layout="pages"))

    def test_column_layouts_still_load_reledpar(self):
        # \Columns runs the pstart hook once per column, \Pages once per page.
        for layout, skip in (("pages", r"\parskip"), ("pairs", r"0.5\parskip")):
            with self.subTest(layout=layout):
                preamble, _ = _split(_transform(_paragraphs(), layout=layout))
                self.assertIn(r"\usepackage{reledpar}", preamble)
                self.assertIn(r"\lineationR{page}", preamble)
                self.assertIn(rf"\newcommand{{\OSPstartSkip}}{{{skip}}}", preamble)
                self.assertNotIn("OSInterleaved", preamble)


class TestReledmacLinePatches(unittest.TestCase):
    """Two reledmac repairs the interleaved layout depends on, applied to every document
    since they correct reledmac's own single-stream lines."""

    def test_every_document_patches_the_line_box_and_the_line_list(self):
        xml = """<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body><tei:p>שלום</tei:p></tei:body></tei:text></tei:TEI>"""
        for layout in ("pages", "pairs", "interleaved"):
            with self.subTest(layout=layout):
                preamble, _ = _split(_transform(xml, layout=layout))
                self.assertIn(r"\patchcmd{\print@line}", preamble)
                self.assertIn(r"\patchcmd{\new@line}", preamble)


class TestInterleavedStructure(unittest.TestCase):
    def test_one_numbered_section_and_no_columns(self):
        _, body = _split(_transform(_paragraphs()))
        self.assertEqual(1, body.count(r"\beginnumbering"))
        self.assertEqual(1, body.count(r"\endnumbering"))
        for column in (r"\begin{pages}", r"\begin{pairs}", "Leftside", "Rightside",
                       r"\Pages", r"\Columns"):
            self.assertNotIn(column, body)

    def test_each_block_is_followed_by_its_translation(self):
        _, body = _split(_transform(_paragraphs()))
        order = [body.index(word) for pair in _WORDS for word in pair]
        self.assertEqual(sorted(order), order)

    def test_primary_last_puts_the_translation_first_in_each_block(self):
        _, body = _split(_transform(_paragraphs("primary_last")))
        order = [body.index(word) for he, en in _WORDS for word in (en, he)]
        self.assertEqual(sorted(order), order)

    def test_the_translation_is_set_apart_whichever_comes_first(self):
        for order in ("primary_first", "primary_last"):
            with self.subTest(order=order):
                _, body = _split(_transform(_paragraphs(order)))
                translations = _environments(body, "OSInterleavedTranslation")
                self.assertEqual([en for _, en in _WORDS],
                                 [re.search(r"\\pstart\\relax (\w+)", t).group(1)
                                  for t in translations])
                for he, _ in _WORDS:
                    self.assertFalse(any(he in t for t in translations))

    def test_hebrew_goes_in_its_own_environment(self):
        _, body = _split(_transform(_paragraphs()))
        hebrew = _environments(body, "hebrew")
        self.assertEqual(len(_WORDS), len(hebrew))
        for (he, en), segment in zip(_WORDS, hebrew):
            self.assertIn(he, segment)
            self.assertNotIn(en, segment)

    def test_a_seam_between_the_two_texts_of_each_block(self):
        _, body = _split(_transform(_paragraphs()))
        self.assertEqual(len(_WORDS), body.count(r"\OSInterleavedSeam"))
        for he, en in _WORDS:
            self.assertRegex(
                body,
                re.escape(he) + r"\\pend\s*\\end\{hebrew\}\s*\\OSInterleavedSeam\s*"
                r"\\begin\{OSInterleavedTranslation\}\s*\\pstart\\relax " + re.escape(en),
            )

    def test_a_paragraph_is_a_paragraph(self):
        """No column pairing to preserve, so none of the column layouts' blank-line
        paragraph breaks: each paragraph is its own \\pstart and takes \\parskip."""
        xml = _document([("<tei:p>א</tei:p><tei:p>ב</tei:p>",
                          "<tei:p>A</tei:p><tei:p>B</tei:p>")])
        _, body = _split(_transform(xml))
        self.assertEqual(4, body.count(r"\pstart"))
        self.assertNotIn(r"\mbox{\strut}", body)
        self.assertNotIn(r"\skipnumbering", body)

    def test_a_block_with_one_side_empty_has_no_seam(self):
        xml = _document([("<tei:p>אחד</tei:p>", "<tei:p>One</tei:p>"),
                         ("<tei:p>שתיים</tei:p>", ""),
                         ("<tei:p>שלוש</tei:p>", "<tei:p>Three</tei:p>")])
        _, body = _split(_transform(xml))
        self.assertIn("שתיים", body)
        self.assertEqual(2, body.count(r"\OSInterleavedSeam"))
        self.assertNotRegex(body, r"שתיים\\pend\s*\\end\{hebrew\}\s*\\OSInterleavedSeam")

    def test_a_long_run_is_not_cut_into_batches(self):
        """The batches are for reledpar's chunk limit alone."""
        _, body = _split(_transform(_paragraphs(), **{"parallel-batch-size": 2}))
        self.assertEqual(1, body.count(r"\beginnumbering"))
        _, columns = _split(_transform(_paragraphs(), layout="pages",
                                       **{"parallel-batch-size": 2}))
        self.assertEqual(2, columns.count(r"\Pages"))


class TestInterleavedHeadings(unittest.TestCase):
    """Headings mean what they mean in columns, with the first text as the first column."""

    @staticmethod
    def _opening(primary_title: str = "כותרת", alt_title: str = "Title") -> str:
        return _document([
            (f"<tei:div><tei:head>{primary_title}</tei:head><tei:p>אחד</tei:p></tei:div>",
             f"<tei:div><tei:head>{alt_title}</tei:head><tei:p>One</tei:p></tei:div>"),
            ("<tei:p>שתיים</tei:p>", "<tei:p>Two</tei:p>"),
        ])

    @staticmethod
    def _further_in(title: str = "Kaddish") -> str:
        """A heading both texts give in the same words, partway into a block."""
        return _document([(
            f"<tei:p>אחד</tei:p><tei:div><tei:head>{title}</tei:head><tei:p>שתיים</tei:p></tei:div>",
            f"<tei:p>One</tei:p><tei:div><tei:head>{title}</tei:head><tei:p>Two</tei:p></tei:div>",
        )])

    def test_an_opening_heading_is_set_once_above_its_block(self):
        _, body = _split(_transform(self._opening(), **{"headings-from": "combined"}))
        self.assertEqual(1, body.count(r"\OSheadA{"))
        self.assertLess(body.index(r"\OSheadA{"), body.index(r"\beginnumbering"))
        self.assertNotIn(r"\mbox{\strut}", body)

    def test_the_translations_heading_records_into_the_alt_marks(self):
        """So `{head1-alt}` and `{section-title-alt}` name the translation's title."""
        _, body = _split(_transform(self._opening(), **{"headings-from": "combined"}))
        numbered = body.split(r"\beginnumbering", 1)[1]
        self.assertRegex(numbered, r"\\InsertMark\{OSheadAAlt\}\{[^\n]*Title")
        self.assertRegex(numbered, r"\\InsertMark\{OSheadAnyAlt\}\{[^\n]*Title")

    def test_a_heading_further_in_is_set_by_the_first_text_only(self):
        _, body = _split(_transform(self._further_in(), **{"headings-from": "combined"}))
        self.assertEqual(1, body.count(r"\OSheadA{"))
        self.assertLess(body.index(r"\OSheadA{"), body.index("One"))
        self.assertNotIn(r"\mbox{\strut}", body)
        self.assertIn(r"\InsertMark{OSheadAAlt}", body)

    def test_both_sets_each_texts_heading(self):
        _, body = _split(_transform(self._opening(), **{"headings-from": "both"}))
        self.assertEqual(2, body.count(r"\OSheadA{"))
        numbered = body.split(r"\beginnumbering", 1)[1]
        self.assertEqual(2, numbered.count(r"\OSheadA{"))

    def test_one_outline_entry_per_heading(self):
        for source in ("combined", "primary", "alt"):
            for xml in (self._opening(), self._further_in()):
                with self.subTest(source=source):
                    _, body = _split(_transform(xml, **{"bookmarks-from": source}))
                    self.assertEqual(1, body.count(r"\addcontentsline"))


class TestInterleavedInstructions(unittest.TestCase):
    SAME = "Between Rosh Hashanah and Yom Kippur add:"
    MACROS = (r"\instructionnote{", r"\OSInstructionBlock{", r"\OSInstructionLine{")

    def _count(self, instructions_from: str) -> int:
        note = f'<tei:note type="instruction" xml:lang="en">{self.SAME}</tei:note>'
        xml = _document([(f"<tei:div>{note}<tei:p>שלום</tei:p></tei:div>",
                          f"<tei:div>{note}<tei:p>Hello</tei:p></tei:div>")])
        _, body = _split(_transform(xml, **{"instructions-from": instructions_from}))
        return sum(body.count(m) for m in self.MACROS)

    def test_a_rubric_the_first_text_already_gives_is_not_repeated(self):
        """Interleaved, the two copies would stand a line apart."""
        self.assertEqual(1, self._count("combined"))

    def test_both_keeps_each_texts_rubric(self):
        self.assertEqual(2, self._count("both"))


if __name__ == "__main__":
    unittest.main()
