r"""Where the interleaved layout's line numbers land, measured on a PDF.

Like ``test_line_number_geometry``, and for the same reason: none of this is visible in
the ``.tex``. The interleaved layout changes direction from one paragraph to the next
inside one numbered section, and two things about reledmac's single-stream lines only
show up when it does:

* reledmac hangs a line's number off a ``\linewidth`` box that takes the prevailing
  direction. In a Hebrew paragraph that box runs right to left, so the "left" number is
  planted at the right-hand edge, over the first word — while the English paragraph
  beside it numbers in the left margin. Every Hebrew line of a single-stream Hebrew
  document had its number printed over its text in the same way.
* an unnumbered line (the translation's, by default) still advances reledmac's line
  count, but writes no record of which page it fell on, so every one of them brought the
  per-page restart a line early and the numbering began again partway down a page.

The document is the exporter's **real** output for a synthetic parallel text, preamble and
body both, so a regression anywhere in the stylesheet fails these tests.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from functools import cache
from pathlib import Path

from opensiddur.exporter.typography import TypographyConfig
from opensiddur.tests.exporter.stylesheet_helpers import transform

# Hebrew long enough for three lines a block, English for five; fourteen blocks run to
# several pages, so "restarts on every page" is more than one claim.
_HEBREW = " ".join(["שָׁלוֹם עוֹלָם וְשָׁלוֹם"] * 18)
_ENGLISH = " ".join(f"word{n}" for n in range(70))
_BLOCKS = 14

_TEI = """<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
  <tei:text><tei:body>
{blocks}
  </tei:body></tei:text>
</tei:TEI>""".format(blocks="\n".join(
    f"""    <p:parallel column-order="primary_first">
      <p:parallelItem role="primary" xml:lang="he"><tei:p>{_HEBREW}</tei:p></p:parallelItem>
      <p:parallelItem role="parallel" xml:lang="en"><tei:p>{_ENGLISH}</tei:p></p:parallelItem>
    </p:parallel>""" for _ in range(_BLOCKS)))

# A Hebrew text with no parallel at all: reledmac sets its lines the same way.
_SINGLE_TEI = """<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
  <tei:text><tei:body>
{paragraphs}
  </tei:body></tei:text>
</tei:TEI>""".format(paragraphs="\n".join(f"    <tei:p>{_HEBREW}</tei:p>" for _ in range(3 * _BLOCKS)))

# reledmac's stock definitions: the state before each repair, for the self-checks.
_STOCK_LINE_BOX = (r"\makeatletter\patchcmd{\print@line}{\hbox dir TLT to\linewidth}"
                   r"{\hb@xt@ \linewidth}{}{\PatchFailed}\makeatother")
_STOCK_LINE_LIST = (r"\makeatletter\patchcmd{\new@line}{\iftrue}{\ifnumberline}{}"
                    r"{\PatchFailed}\makeatother")

_WORD = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>'
)


class Box:
    def __init__(self, x0, y0, x1, y1, text):
        self.x0, self.y0, self.x1, self.y1, self.text = x0, y0, x1, y1, text

    def on_line_of(self, other: "Box") -> bool:
        return not (other.y1 <= self.y0 or other.y0 >= self.y1)

    def __repr__(self):
        return f"{self.text!r}@x[{self.x0:.1f},{self.x1:.1f}]y{self.y0:.1f}"


class Page:
    """One page's words: line numbers, Hebrew words and English words."""

    def __init__(self, boxes: list[Box]):
        self.numbers = [b for b in boxes if re.fullmatch(r"\d+", b.text)]
        self.english = [b for b in boxes if b.text.startswith("word")]
        self.hebrew = [b for b in boxes if b not in self.numbers and b not in self.english]

    @property
    def text(self) -> list[Box]:
        return self.hebrew + self.english

    @staticmethod
    def lines(boxes: list[Box]) -> list[Box]:
        """One representative box per printed line, top to bottom."""
        rows: list[Box] = []
        for box in sorted(boxes, key=lambda b: b.y0):
            if not any(box.on_line_of(row) for row in rows):
                rows.append(box)
        return rows


@cache
def _typeset(line_numbers: str = "primary", macros: str = "",
             single: bool = False) -> tuple[Page, ...]:
    settings = TypographyConfig.model_validate({
        # Number every line: the defects are per line, and a sparse sample would only
        # catch them where a numbered line happened to fall.
        "line_numbers": {"first": 1, "increment": 1},
        "parallel": {"layout": "interleaved",
                     "interleaved": {"line_numbers": line_numbers}},
    })
    tex = transform(_SINGLE_TEI if single else _TEI, settings, **{
        "additional-preamble": macros,
    })
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "t.tex").write_text(tex)
        for _ in range(3):  # line numbers need the aux file to settle
            done = subprocess.run(
                ["lualatex", "-interaction=nonstopmode", "t.tex"],
                cwd=work, capture_output=True, text=True,
            )
        if not (work / "t.pdf").exists():
            raise AssertionError(f"lualatex produced no PDF:\n{done.stdout[-2000:]}")
        if "PatchFailed" in (work / "t.log").read_text(errors="replace"):
            raise AssertionError("a self-check could not restore reledmac's definition")
        boxes = subprocess.run(
            ["pdftotext", "-bbox", "t.pdf", "-"],
            cwd=work, capture_output=True, text=True,
        ).stdout

    pages = []
    for chunk in boxes.split("<page")[1:]:
        found = [
            Box(float(m.group(1)), float(m.group(2)), float(m.group(3)),
                float(m.group(4)), m.group(5))
            for m in _WORD.finditer(chunk)
            if float(m.group(2)) > 85 and m.group(5).strip()  # not the running head
        ]
        if found:
            pages.append(Page(found))
    return tuple(pages)


@unittest.skipUnless(
    shutil.which("lualatex") and shutil.which("pdftotext"),
    "requires a real lualatex installation and pdftotext",
)
class TestInterleavedLineNumbers(unittest.TestCase):

    def pages(self, **kwargs) -> tuple[Page, ...]:
        pages = _typeset(**kwargs)
        self.assertGreater(len(pages), 2, "wanted several pages to check the restart on")
        return pages

    # -- the invariants ---------------------------------------------------------------

    def assertNumbersInOneMarginOutsideTheText(self, pages) -> None:
        """Every number on a page lies wholly outside the span of both texts, and all on
        the same side: a Hebrew line numbers in the margin an English one does."""
        for n, page in enumerate(pages, 1):
            lo = min(b.x0 for b in page.text)
            hi = max(b.x1 for b in page.text)
            left = [b for b in page.numbers if b.x1 <= lo]
            right = [b for b in page.numbers if b.x0 >= hi]
            inside = [b for b in page.numbers if b not in left and b not in right]
            self.assertEqual([], inside, f"page {n}: numbers inside the text [{lo:.1f},{hi:.1f}]")
            self.assertFalse(left and right, f"page {n}: numbers in both margins")

    def assertNumbersRunFromOneOnEveryPage(self, pages) -> None:
        for n, page in enumerate(pages, 1):
            seen = [int(b.text) for b in sorted(page.numbers, key=lambda b: b.y0)]
            self.assertEqual(list(range(1, len(seen) + 1)), seen,
                             f"page {n}: numbering does not run 1, 2, 3 ... down the page")

    # -- the tests ----------------------------------------------------------------------

    def test_numbers_share_one_margin_outside_both_texts(self):
        self.assertNumbersInOneMarginOutsideTheText(self.pages())

    def test_by_default_only_the_primary_text_is_numbered(self):
        pages = self.pages()
        for n, page in enumerate(pages, 1):
            hebrew_lines = Page.lines(page.hebrew)
            for number in page.numbers:
                self.assertTrue(any(number.on_line_of(line) for line in hebrew_lines),
                                f"page {n}: {number} is not on a Hebrew line")
            self.assertEqual(len(hebrew_lines), len(page.numbers),
                             f"page {n}: not every Hebrew line is numbered")
        self.assertNumbersRunFromOneOnEveryPage(pages)

    def test_both_numbers_every_line_in_one_series(self):
        pages = self.pages(line_numbers="both")
        for n, page in enumerate(pages, 1):
            self.assertEqual(len(Page.lines(page.text)), len(page.numbers),
                             f"page {n}: not every line is numbered")
        self.assertNumbersRunFromOneOnEveryPage(pages)
        self.assertNumbersInOneMarginOutsideTheText(pages)

    def test_a_single_hebrew_text_numbers_in_the_margin_too(self):
        """Not interleaved at all: the same line box sets every single-stream line."""
        pages = self.pages(single=True)
        self.assertNumbersInOneMarginOutsideTheText(pages)
        self.assertNumbersRunFromOneOnEveryPage(pages)

    def test_the_translation_is_indented_on_both_sides(self):
        for n, page in enumerate(self.pages(), 1):
            if not (page.hebrew and page.english):
                continue
            self.assertGreater(min(b.x0 for b in page.english),
                               min(b.x0 for b in page.hebrew) + 5, f"page {n}")
            self.assertLess(max(b.x1 for b in page.english),
                            max(b.x1 for b in page.hebrew) - 5, f"page {n}")

    # -- self-checks: an assertion that cannot fail proves nothing ------------------------

    def test_the_measurement_would_notice_a_number_over_the_hebrew(self):
        pages = self.pages(line_numbers="both", macros=_STOCK_LINE_BOX)
        with self.assertRaises(AssertionError):
            self.assertNumbersInOneMarginOutsideTheText(pages)

    def test_the_measurement_would_notice_a_single_hebrew_text_numbered_over_its_words(self):
        pages = self.pages(single=True, macros=_STOCK_LINE_BOX)
        with self.assertRaises(AssertionError):
            self.assertNumbersInOneMarginOutsideTheText(pages)

    def test_the_measurement_would_notice_numbering_restarting_mid_page(self):
        pages = self.pages(macros=_STOCK_LINE_LIST)
        with self.assertRaises(AssertionError):
            self.assertNumbersRunFromOneOnEveryPage(pages)


if __name__ == "__main__":
    unittest.main()
