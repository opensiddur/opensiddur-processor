r"""Does a facing-pages compile keep each spread together?

``layout: pages`` sets the two texts with reledpar's ``\Pages``: the left text on the
verso, the right on the recto, each paired ``\pstart`` starting at the same height on
both pages. Every other test of that layout reads the ``.tex``; what can go wrong here is
in what TeX makes of it, so these typeset a whole document through the real stylesheet
and measure the PDF.

The document is synthetic. Every word names its block and side -- ``L2w7`` is the
eighth word of block 2's left text -- so a page's contents can be read off without
guessing at its geometry.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from opensiddur.exporter.tex.latex import transform_xml_to_tex
from opensiddur.exporter.typography import TypographyConfig
from opensiddur.tests.exporter.stylesheet_helpers import NO_NOTICES


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{n}" for n in range(count))


def _block(n: int, left: int, right: int, titles: tuple[str, str] | None = None) -> str:
    heads = (f"<tei:head>{titles[0]}</tei:head>", f"<tei:head>{titles[1]}</tei:head>") \
        if titles else ("", "")
    return f"""
    <p:parallel column-order="primary_first">
      <p:parallelItem role="primary" xml:lang="en">
        <tei:div corresp="urn:x-opensiddur:text:t:s{n}">{heads[0]}<tei:p>{_words(f"L{n}w", left)}</tei:p></tei:div>
      </p:parallelItem>
      <p:parallelItem role="parallel" xml:lang="en">
        <tei:div corresp="urn:x-opensiddur:text:t:s{n}">{heads[1]}<tei:p>{_words(f"R{n}w", right)}</tei:p></tei:div>
      </p:parallelItem>
    </p:parallel>"""


# The opening runs onto a second page, so the spread after it has to be pushed past a
# blank recto to start on a verso. Block 1's right text runs to several pages against a
# few lines on the left, so the left side has to be padded for block 2 to stay in step.
_DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="en">
  <tei:text><tei:body>
    <tei:p>{_words("Open", 600)}</tei:p>
    {_block(1, 30, 900, ("PRIMARYONE", "ParallelOne"))}
    {_block(2, 30, 30)}
    {_block(3, 30, 30, ("PRIMARYTWO", "ParallelTwo"))}
  </tei:body></tei:text>
</tei:TEI>"""

_TYPOGRAPHY = {
    "parallel": {"layout": "pages"},
    "page_header": {
        "even": {"center": "{section-title}"},
        "odd": {"center": "{section-title-alt}"},
    },
}

# The running head sits above this, the text block below it.
_HEAD_BOTTOM = 80.0


@unittest.skipUnless(
    shutil.which("lualatex") and shutil.which("pdftotext"),
    "requires a real lualatex installation and pdftotext",
)
class TestFacingPagesGeometry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "in.xml").write_text(_DOCUMENT)
            transform_xml_to_tex(
                work / "in.xml", output_file=str(work / "t.tex"),
                typography=TypographyConfig.model_validate(_TYPOGRAPHY),
                project_directory=work,
                distribution=NO_NOTICES,
            )
            for _ in range(3):  # reledpar needs the earlier passes' line counts to pair
                done = subprocess.run(
                    ["lualatex", "-interaction=nonstopmode", "t.tex"],
                    cwd=work, capture_output=True, text=True,
                )
            if not (work / "t.pdf").exists():
                raise AssertionError(f"lualatex produced no PDF:\n{done.stdout[-2000:]}")
            boxes = subprocess.run(
                ["pdftotext", "-bbox", "t.pdf", "-"],
                cwd=work, capture_output=True, text=True,
            ).stdout
        # pages[i] is page i + 1: a list of (y, word).
        cls.pages = [
            [(float(y), word) for y, word in re.findall(
                r'<word xMin="[\d.]+" yMin="([\d.]+)"[^>]*>([^<]*)</word>', page)]
            for page in boxes.split("<page ")[1:]
        ]

    def _page_of(self, word: str) -> int:
        for number, words in enumerate(self.pages, 1):
            if any(w == word for _, w in words):
                return number
        self.fail(f"{word} is not on any page")

    def _y_of(self, word: str) -> float:
        return next(y for y, w in self.pages[self._page_of(word) - 1] if w == word)

    def _head(self, page: int) -> str:
        return " ".join(w for y, w in self.pages[page - 1] if y < _HEAD_BOTTOM)

    def test_the_left_text_is_on_a_verso_and_the_right_on_the_facing_recto(self):
        for block in (1, 2, 3):
            with self.subTest(block=block):
                verso = self._page_of(f"L{block}w0")
                self.assertEqual(0, verso % 2, "the left text starts on a recto")
                self.assertEqual(verso + 1, self._page_of(f"R{block}w0"))

    def test_a_block_starts_level_on_both_pages_after_a_longer_one(self):
        """Block 1's right text runs on for pages; the left side is padded through them,
        so block 2 opens on the same spread and the same line on both sides."""
        self.assertGreater(self._page_of("R1w899"), self._page_of("R1w0") + 2,
                           "block 1's right text did not run past its first spread")
        self.assertAlmostEqual(self._y_of("L2w0"), self._y_of("R2w0"), delta=1.0)

    def test_a_heading_opens_its_text_on_both_pages(self):
        """No heading is stranded on a page of its own before the spread."""
        for block, titles in ((1, ("PRIMARYONE", "ParallelOne")),
                              (3, ("PRIMARYTWO", "ParallelTwo"))):
            for side, title in zip("LR", titles):
                with self.subTest(block=block, side=side):
                    page = self._page_of(f"{side}{block}w0")
                    in_body = [w for y, w in self.pages[page - 1]
                               if y >= _HEAD_BOTTOM and w == title]
                    self.assertTrue(in_body, f"{title} is not set above {side}{block}w0")

    def test_the_blank_page_before_a_spread_is_wholly_blank(self):
        """The opening ends on a verso, so \\Pages inserts a recto before the spread. It
        carries no running head."""
        last_opening = self._page_of("Open599")
        first_spread = self._page_of("L1w0")
        self.assertEqual(last_opening + 2, first_spread,
                         "the measurement needs the opening to end on a verso")
        self.assertEqual([], self.pages[last_opening])

    def test_each_page_of_a_spread_heads_its_own_text(self):
        """{section-title} on the verso, {section-title-alt} on the recto."""
        verso = self._page_of("L3w0")
        self.assertEqual("PRIMARYTWO", self._head(verso))
        self.assertEqual("ParallelTwo", self._head(verso + 1))


# Hebrew on the verso, numbered in its outer margin -- the left one.
_HEBREW_LINE = " ".join(["שָׁלוֹם עוֹלָם וְשָׁלוֹם"] * 3)
_HEBREW_DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
  <tei:text><tei:body>
    <p:parallel column-order="primary_first">
      <p:parallelItem role="primary" xml:lang="he">
        {"".join(f"<tei:p>{_HEBREW_LINE}</tei:p>" for _ in range(12))}
      </p:parallelItem>
      <p:parallelItem role="parallel" xml:lang="en">
        {"".join(f"<tei:p>{_words(f'R{n}w', 6)}</tei:p>" for n in range(12))}
      </p:parallelItem>
    </p:parallel>
  </tei:body></tei:text>
</tei:TEI>"""


@unittest.skipUnless(
    shutil.which("lualatex") and shutil.which("pdftotext"),
    "requires a real lualatex installation and pdftotext",
)
class TestFacingPagesHebrewLineNumbers(unittest.TestCase):
    r"""\Pages built a Hebrew page's rows right to left, so the left margin was each
    row's right-hand end, and a Hebrew verso's line numbers were printed over the first
    word of their lines."""

    def test_a_hebrew_versos_line_numbers_are_in_its_outer_margin(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "in.xml").write_text(_HEBREW_DOCUMENT)
            transform_xml_to_tex(
                work / "in.xml", output_file=str(work / "t.tex"),
                typography=TypographyConfig.model_validate(
                    {"parallel": {"layout": "pages"}, "page_header": {}}),
                project_directory=work,
                distribution=NO_NOTICES,
            )
            for _ in range(3):
                done = subprocess.run(
                    ["lualatex", "-interaction=nonstopmode", "t.tex"],
                    cwd=work, capture_output=True, text=True,
                )
            self.assertTrue((work / "t.pdf").exists(),
                            f"lualatex produced no PDF:\n{done.stdout[-2000:]}")
            boxes = subprocess.run(
                ["pdftotext", "-bbox", "-f", "2", "-l", "2", "t.pdf", "-"],
                cwd=work, capture_output=True, text=True,
            ).stdout
        words = [(float(x0), float(x1), w) for x0, x1, w in re.findall(
            r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)"[^>]*>([^<]*)</word>',
            boxes)]
        numbers = [x1 for _, x1, w in words if w.isdigit()]
        text_left = min(x0 for x0, _, w in words if not w.isdigit())
        self.assertTrue(numbers, "the Hebrew verso has no line numbers")
        for right_edge in numbers:
            self.assertLess(right_edge, text_left,
                            "a line number on the Hebrew verso is set over its text")


if __name__ == "__main__":
    unittest.main()
