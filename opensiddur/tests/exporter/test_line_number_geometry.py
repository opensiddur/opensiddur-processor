r"""Do the margin line numbers stay out of the columns they number?

Like ``test_parallel_column_geometry``, and for the same reason: none of this is visible in
the ``.tex``. Where a number lands is decided by TeX, out of a ``\llap`` whose direction is
whatever the column happens to be running in, so the emitted text looks identical whether the
number ends up in the margin or on top of the words.

Two defects live here, and both were found by measuring a PDF rather than by reading one:

* a lap is built in horizontal mode and takes the prevailing ``\textdir``. reledpar
  re-selects each column's own language, and with it its direction, around every line it sets
  (``reledpar.sty``, ``\Columns``). In the Hebrew column that mirrors the lap, so instead of
  hanging ``\linenumsep`` outside the measure the number is planted ``\linenumsep`` *inside*
  it, over the text, on every page.
* ``\lineation`` sets the main series only. reledpar keeps a separate ``\bypage@R`` which
  defaults to false, so the right column numbered by section and ran on unbroken -- to 320 by
  page 11 of the Birnbaum Amidah, while the left column restarted at 5 on every page.

The document is built on the exporter's **real** preamble, so a regression anywhere in it
fails these tests rather than a copy kept in step by hand.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from opensiddur.tests.exporter.stylesheet_helpers import transform

_PARALLEL_TEI = """<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:p="http://jewishliturgy.org/ns/processing">
  <tei:text><tei:body>
    <p:parallel column-order="primary_first">
      <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
      <p:parallelItem role="parallel" xml:lang="en"><tei:p>Hello</tei:p></p:parallelItem>
    </p:parallel>
  </tei:body></tei:text>
</tei:TEI>"""

# Long enough to run to several pages, so "resets on every page" is more than one claim.
_HEBREW = " ".join(["שָׁלוֹם עוֹלָם וְשָׁלוֹם"] * 160)
_ENGLISH = " ".join(f"word{n}" for n in range(700))

# Number every line rather than every fifth: the defect is per line, and a sparse sample
# would only catch it when a numbered line happened to be full measure.
_BODY = r"""\firstlinenum{1}\linenumincrement{1}\firstlinenumR{1}\linenumincrementR{1}
%(macros)s
\begin{document}
\begin{pairs}
\begin{Leftside}
\begin{hebrew}
\beginnumbering
\pstart %(hebrew)s\pend
\endnumbering
\end{hebrew}
\end{Leftside}
\begin{Rightside}
\beginnumbering
\pstart %(english)s\pend
\endnumbering
\end{Rightside}
\end{pairs}
\Columns
\end{document}
"""

_WORD = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>'
)


class Box:
    def __init__(self, x0, y0, x1, y1, text):
        self.x0, self.y0, self.x1, self.y1, self.text = x0, y0, x1, y1, text

    def __repr__(self):
        return f"{self.text!r}@x[{self.x0:.1f},{self.x1:.1f}]"


class Page:
    """One page's words, split into the two columns and into numbers versus text."""

    def __init__(self, boxes: list[Box]):
        numbers = [b for b in boxes if re.fullmatch(r"\d+", b.text)]
        text = [b for b in boxes if b not in numbers]
        # The columns are the two clusters of text; the divide is between them. Derived
        # from the page rather than hard-coded, so the test says nothing about
        # \columnsposition, \Lcolwidth, or the margin swap between recto and verso.
        self.divide = (min(b.x0 for b in text) + max(b.x1 for b in text)) / 2
        self.text = {
            "left": [b for b in text if b.x1 < self.divide],
            "right": [b for b in text if b.x0 > self.divide],
        }
        self.numbers = {
            "left": [b for b in numbers if b.x1 < self.divide],
            "right": [b for b in numbers if b.x0 > self.divide],
        }

    def span(self, column: str) -> tuple[float, float]:
        boxes = self.text[column]
        return min(b.x0 for b in boxes), max(b.x1 for b in boxes)


@unittest.skipUnless(
    shutil.which("lualatex") and shutil.which("pdftotext"),
    "requires a real lualatex installation and pdftotext",
)
class TestLineNumberGeometry(unittest.TestCase):

    @staticmethod
    def _preamble() -> str:
        out = transform(_PARALLEL_TEI, layout="pairs")
        return out.split(r"\begin{document}")[0]

    def _typeset(self, macros: str = "") -> list[Page]:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "t.tex").write_text(
                self._preamble()
                + _BODY % {"macros": macros, "hebrew": _HEBREW, "english": _ENGLISH}
            )
            for _ in range(3):  # line numbers need the aux file to settle
                done = subprocess.run(
                    ["lualatex", "-interaction=nonstopmode", "t.tex"],
                    cwd=work, capture_output=True, text=True,
                )
            self.assertTrue(
                (work / "t.pdf").exists(),
                f"lualatex produced no PDF:\n{done.stdout[-2000:]}",
            )
            # A \patchcmd that finds nothing to patch only reports it, and a PDF is made
            # regardless: an exporter patch or a simulation here could fail unnoticed.
            log = (work / "t.log").read_text(errors="replace")
            self.assertNotIn("! Package", log, "a package error while typesetting")
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
                if float(m.group(2)) > 85 and m.group(5).strip()  # not the running folio
            ]
            if found:
                pages.append(Page(found))
        self.assertGreater(len(pages), 2, "wanted several pages to check the reset on")
        return pages

    # -- the invariant, and the harm ------------------------------------------------

    def assertNumbersOutsideTheirColumn(self, pages: list[Page]) -> None:
        """A margin number belongs in the margin: its whole width must lie outside the
        span its column's text occupies. Stronger than "no collision", which would pass
        by luck on a page where no numbered line happened to reach full measure."""
        for n, page in enumerate(pages, 1):
            for column in ("left", "right"):
                if not page.numbers[column] or not page.text[column]:
                    continue
                lo, hi = page.span(column)
                for box in page.numbers[column]:
                    self.assertTrue(
                        box.x1 <= lo or box.x0 >= hi,
                        f"page {n}, {column} column: number {box} lies inside the text "
                        f"span [{lo:.1f},{hi:.1f}]",
                    )

    def assertNoNumberTouchesText(self, pages: list[Page]) -> None:
        """The symptom a reader sees: a number printed over a word."""
        for n, page in enumerate(pages, 1):
            for column in ("left", "right"):
                for num in page.numbers[column]:
                    for word in page.text[column]:
                        same_line = not (word.y1 <= num.y0 or word.y0 >= num.y1)
                        if same_line and word.x0 < num.x1 and word.x1 > num.x0:
                            self.fail(
                                f"page {n}, {column} column: number {num} overlaps {word}"
                            )

    def assertNumbersResetEachPage(self, pages: list[Page]) -> None:
        for n, page in enumerate(pages, 1):
            for column in ("left", "right"):
                seen = sorted(int(b.text) for b in page.numbers[column])
                if not seen:
                    continue
                self.assertEqual(
                    1, seen[0],
                    f"page {n}, {column} column starts at {seen[0]}, not 1 -- this column "
                    f"is not numbering by page",
                )

    # -- the tests ------------------------------------------------------------------

    def test_numbers_sit_outside_both_columns(self):
        pages = self._typeset()
        self.assertNumbersOutsideTheirColumn(pages)
        self.assertNoNumberTouchesText(pages)

    def test_both_columns_restart_their_numbering_on_every_page(self):
        self.assertNumbersResetEachPage(self._typeset())

    # -- self-checks: an assertion that cannot fail proves nothing -------------------

    def test_the_measurement_would_notice_a_number_inside_the_column(self):
        """reledmac's own definitions are the pre-fix state, and must be caught."""
        stock = (r"\makeatletter"
                 r"\renewcommand*{\leftlinenum}{\ledlinenum\kern\linenumsep}"
                 r"\renewcommand*{\rightlinenum}{\kern\linenumsep\ledlinenum}"
                 r"\renewcommand*{\leftlinenumR}{\l@dlinenumR\kern\linenumsep}"
                 r"\renewcommand*{\rightlinenumR}{\kern\linenumsep\l@dlinenumR}"
                 r"\makeatother")
        with self.assertRaises(AssertionError):
            self.assertNumbersOutsideTheirColumn(self._typeset(macros=stock))

    def test_the_measurement_would_notice_a_column_that_never_resets(self):
        r"""``\bypage@R`` defaults to false, so ``\lineationR{section}`` is a faithful
        reproduction of the pre-fix state rather than an invented one."""
        with self.assertRaises(AssertionError):
            self.assertNumbersResetEachPage(self._typeset(macros=r"\lineationR{section}"))

    # -- polyglossia 2.4 (TeX Live 2024): the direction reledpar's language switch leaves ---

    def assertHebrewInTheLeftColumn(self, pages: list[Page]) -> None:
        """``\\begin{Leftside}`` is the physical left column, whatever language it holds:
        on every page with both texts, all the Hebrew lies left of all the English."""
        for n, page in enumerate(pages, 1):
            words = page.text["left"] + page.text["right"]
            hebrew = [b for b in words if _HEBREW_LETTER.search(b.text)]
            # pdftotext splits pointed Hebrew into fragments, some of them only points, so
            # English is recognized by its own words rather than by having no Hebrew letter.
            english = [b for b in words if _ENGLISH_WORD.fullmatch(b.text)]
            if not hebrew or not english:
                continue
            self.assertLess(
                max(b.x1 for b in hebrew), min(b.x0 for b in english),
                f"page {n}: the Hebrew Leftside is not the left column",
            )

    def test_numbers_and_columns_survive_a_right_to_left_language_switch(self):
        """Under polyglossia 2.4 (TeX Live 2024) reledpar's switch to the English column's
        language around each row does not take, so ``\\textdir`` is still right to left
        when the row box and the English column's line box are built: the columns swapped
        places and every margin number landed over its first word (#338).
        Simulated here by selecting Hebrew again just before those boxes are built."""
        pages = self._typeset(macros=_LEAVE_RIGHT_TO_LEFT)
        self.assertHebrewInTheLeftColumn(pages)
        self.assertNumbersOutsideTheirColumn(pages)
        self.assertNoNumberTouchesText(pages)

    def test_the_simulation_breaks_the_unpatched_boxes(self):
        """Without the explicit directions, the simulation must reproduce the defect, or
        the test above proves nothing."""
        pages = self._typeset(macros=_LEAVE_RIGHT_TO_LEFT + _UNDO_DIRECTION_PATCHES)
        with self.assertRaises(AssertionError):
            self.assertHebrewInTheLeftColumn(pages)
        with self.assertRaises(AssertionError):
            self.assertNumbersOutsideTheirColumn(pages)


_HEBREW_LETTER = re.compile("[א-ת]")
_ENGLISH_WORD = re.compile(r"word\d+")

# The state polyglossia 2.4 leaves behind, measured under TeX Live 2024: reledpar's switch
# to the English column's language does not take, so Hebrew is still the language in force,
# right to left, when the row box and the English column's line box are built. Setting
# \textdir or \pardir alone does not reproduce the swapped columns; selecting Hebrew does.
# The row's language is selected just before its box, at the \OS@rowbound test the
# exporter puts there.
_LEAVE_RIGHT_TO_LEFT = (
    r"\makeatletter"
    r"\patchcmd{\OSreledparColumnsOrig}{\ifnum\OS@rowbound}{\selectlanguage{hebrew}\ifnum\OS@rowbound}{}"
    r"{\PackageError{test}{could not select Hebrew before the row}{}}"
    r"\pretocmd{\print@lineR}{\selectlanguage{hebrew}}{}"
    r"{\PackageError{test}{could not select Hebrew before print@lineR}{}}"
    r"\makeatother" "\n"
)

# The exporter's two direction patches, taken back out.
_UNDO_DIRECTION_PATCHES = (
    r"\makeatletter"
    r"\patchcmd{\OSreledparColumnsOrig}{\hbox dir TLT to\hsize}{\hb@xt@ \hsize}{}"
    r"{\PackageError{test}{could not undo the row patch}{}}"
    r"\patchcmd{\print@lineR}{\hbox dir TLT to\Rcolwidth}{\hb@xt@ \Rcolwidth}{}"
    r"{\PackageError{test}{could not undo the print@lineR patch}{}}"
    r"\makeatother" "\n"
)
