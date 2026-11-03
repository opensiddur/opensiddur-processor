r"""Does a page break ever strand a line or a heading (#198)?

Five things must never happen at a page break:

* a widow: the last line of a paragraph alone at the head of a page;
* an orphan: the first line of a paragraph alone at the foot of one;
* a split heading: a heading, or its translated title, on two pages;
* a stranded heading: a heading at the foot of a page, the text it heads on the next;
* a stranded rubric: a rubric on one page and the text it introduces on the next. A
  rubric of up to five lines stays whole; a longer one keeps at least its last five.

Each layout breaks its pages differently -- TeX's page builder over reledmac's lines in a
single stream, the same over reledpar's rows under ``\Columns``, and reledpar's own count
under ``\Pages`` -- so each is typeset and measured on its own. None of it is visible in
the ``.tex``.

Nothing here aims a heading at the foot of a page, which would depend on the fonts. The
documents are a long run of headed sections whose paragraphs cycle through many lengths,
so their edges land at every height on the page and some of them meet a page break
whatever the metrics. Each layout is set a second time with the protection switched off,
which must then go wrong somewhere: otherwise the sweep never reached a page edge and the
clean result would mean nothing.

Every word names itself: ``LP3w7`` is the eighth word of section 3's first paragraph on
the left (or only) side, ``LQ3`` its second paragraph, ``LH3`` its heading, ``LT3`` the
heading's translation and ``LI3`` a rubric. Every third section has a rubric between its
heading and its text; the one after each of those is preceded by a rubric that ends the
block before it, the way a real compile so often has one ("Reader:").
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from opensiddur.exporter.tex.latex import transform_xml_to_tex
from opensiddur.tests.exporter.stylesheet_helpers import NO_NOTICES
from opensiddur.exporter.typography import TypographyConfig

_SECTIONS = 30
# Words in a section's first paragraph; the second has twice as many and five more.
_LENGTHS = (3, 9, 17, 26, 34, 45, 12, 21, 7, 40, 30, 15)
# A section with nothing on the right is set across the page between column blocks
# (#194), as a single stream inside a parallel text.
_UNPAIRED = {4, 11, 19, 26}
# Words in a rubric: from one line to several more than the five kept whole.
_RUBRICS = (4, 12, 22, 48, 7, 30, 64, 16, 90)
_RUBRIC_TAIL = 5


def _inner_rubric(n: int) -> bool:
    """A rubric between the heading and the first paragraph."""
    return n % 3 == 0


def _rubric_before(n: int) -> bool:
    """A rubric ending the block before the section."""
    return n % 3 == 1


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}w{n}" for n in range(count))


def _rubric(side: str, n: int) -> str:
    return (f'<tei:note type="instruction" xml:lang="en">'
            f"{_words(f'{side}I{n}', _RUBRICS[n % len(_RUBRICS)])}</tei:note>")


def _div(side: str, n: int, length: int, translated: bool, crossing: bool = False) -> str:
    """A section. ``crossing`` sets its text in a Hebrew division, so that an English rubric
    stands on lines of its own, as it does in every parallel layout, rather than run in."""
    heads = f"<tei:head>{side}H{n}</tei:head>"
    if translated:
        heads += f"<tei:head>{side}T{n}</tei:head>"
    div_lang, p_lang = (' xml:lang="he"', ' xml:lang="en"') if crossing else ("", "")
    rubric = _rubric(side, n) if _inner_rubric(n) else ""
    return (f'<tei:div corresp="urn:x-opensiddur:text:t:s{n}"{div_lang}>{heads}{rubric}'
            f"<tei:p{p_lang}>{_words(f'{side}P{n}', length)}</tei:p>"
            f"<tei:p{p_lang}>{_words(f'{side}Q{n}', 2 * length + 5)}</tei:p></tei:div>")


def _document(parallel: bool, primary: str = "en") -> str:
    """``primary`` is the language of the first column. Hebrew puts a Hebrew title across
    the page in its own language environment, which writes to the page as it opens."""
    sections = []
    for n in range(_SECTIONS):
        left = _LENGTHS[n % len(_LENGTHS)]
        if not parallel:
            if _rubric_before(n):
                sections.append(f'<tei:div xml:lang="he"><tei:p xml:lang="en">'
                                f"{_words(f'LO{n}', 8)}</tei:p>{_rubric('L', n)}</tei:div>")
            sections.append(_div("L", n, left, translated=True, crossing=True))
            continue
        if _rubric_before(n):
            sections.append(f"""
    <p:parallel column-order="primary_first">
      <p:parallelItem role="primary" xml:lang="{primary}"><tei:div>{_rubric("L", n)}</tei:div></p:parallelItem>
      <p:parallelItem role="parallel" xml:lang="en"><tei:div>{_rubric("R", n)}</tei:div></p:parallelItem>
    </p:parallel>""")
        right = (f'<tei:p><tei:milestone unit="prayer-part" '
                 f'corresp="urn:x-opensiddur:text:t:s{n}"/></tei:p>'
                 if n in _UNPAIRED
                 else _div("R", n, _LENGTHS[(n + 5) % len(_LENGTHS)], translated=False))
        sections.append(f"""
    <p:parallel column-order="primary_first">
      <p:parallelItem role="primary" xml:lang="{primary}">{_div("L", n, left, translated=False)}</p:parallelItem>
      <p:parallelItem role="parallel" xml:lang="en">{right}</p:parallelItem>
    </p:parallel>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="en">
  <tei:text><tei:body>{"".join(sections)}
  </tei:body></tei:text>
</tei:TEI>"""


# Everything #198 added, switched back off: the stock penalties, no heading kept with
# what follows it, and nothing read off a line. The heading's own lines stay bound; the
# sweep does not need them to show that it reaches the page edges.
_UNPROTECTED = r"""
\clubpenalty=150 \widowpenalty=150
\renewcommand{\OSApplyKeep}{\global\OSKeepNextfalse}
\directlua{
  OSkeep.single = function() tex.setcount("global", "OS@linebound", 0) end
  OSkeep.line = function() end
  OSkeep.chain = function() tex.setcount("global", "OS@chainlines", 1) end
}
"""

# Words above this are the running head, if there is one.
_HEAD_BOTTOM = 85.0


def _typeset(parallel: bool, typography: dict, protected: bool = True,
             primary: str = "en", document: str | None = None) -> tuple[dict[str, tuple[int, int]], str]:
    """Each word's (page, rounded yMin), and the ``.tex`` it was set from."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "in.xml").write_text(document if document is not None else _document(parallel, primary))
        transform_xml_to_tex(
            work / "in.xml", output_file=str(work / "t.tex"),
            typography=TypographyConfig.model_validate(typography),
            project_directory=work,
            distribution=NO_NOTICES,
        )
        tex = (work / "t.tex").read_text()
        if not protected:
            (work / "t.tex").write_text(
                tex.replace(r"\begin{document}", _UNPROTECTED + r"\begin{document}", 1))
        for _ in range(3):  # reledpar pairs and paginates from the earlier passes
            done = subprocess.run(
                ["lualatex", "-interaction=nonstopmode", "t.tex"],
                cwd=work, capture_output=True, text=True,
            )
        if not (work / "t.pdf").exists():
            raise AssertionError(f"lualatex produced no PDF:\n{done.stdout[-2000:]}")
        log = (work / "t.log").read_text(errors="replace")
        if "could not patch" in log:
            raise AssertionError("a reledmac or reledpar patch did not apply")
        errors = re.findall(r"^! .*", log, re.MULTILINE)
        if errors:
            raise AssertionError(f"TeX errors: {errors[:5]}")
        boxes = subprocess.run(
            ["pdftotext", "-bbox", "t.pdf", "-"],
            cwd=work, capture_output=True, text=True,
        ).stdout
    where = {}
    for page, chunk in enumerate(boxes.split("<page ")[1:], 1):
        for y, word in re.findall(
                r'<word xMin="[\d.]+" yMin="([\d.]+)"[^>]*>([^<]*)</word>', chunk):
            if float(y) > _HEAD_BOTTOM:
                where[word] = (page, round(float(y)))
    return where, tex


def _lines(where: dict[str, tuple[int, int]], paragraph: str) -> list[tuple[int, int]]:
    """A paragraph's printed lines, top to bottom, as (page, y)."""
    pattern = re.compile(re.escape(paragraph) + r"w\d+")
    return sorted({at for word, at in where.items() if pattern.fullmatch(word)})


def _violations(where: dict[str, tuple[int, int]], sides: str,
                facing_pages: bool = False) -> list[str]:
    found = []
    for side in sides:
        for n in range(_SECTIONS):
            head = where.get(f"{side}H{n}")
            text = _lines(where, f"{side}P{n}")
            rubric = _lines(where, f"{side}I{n}")
            if head is not None:
                translation = where.get(f"{side}T{n}")
                if translation is not None and translation[0] != head[0]:
                    found.append(f"split heading {side}H{n}")
                # A heading opens onto its rubric, where it has one.
                opening = (rubric if _inner_rubric(n) and rubric else text)[:2]
                if any(page != head[0] for page, _ in opening):
                    found.append(f"stranded heading {side}H{n}")
            # A rubric stays with what follows it: its section's text, or, ending the
            # block before a section, that section's heading. Not covered: a rubric
            # ending the facing pages before an unpaired passage, which is set across the
            # page after them and starts a new spread.
            below = text[0] if _inner_rubric(n) and text else head
            if rubric and below is not None and not (
                    facing_pages and _rubric_before(n) and n in _UNPAIRED):
                if any(page != below[0] for page, _ in rubric[-_RUBRIC_TAIL:]):
                    found.append(f"stranded rubric {side}I{n}")
            for paragraph in (f"{side}P{n}", f"{side}Q{n}"):
                lines = _lines(where, paragraph)
                if len(lines) >= 2 and lines[0][0] != lines[1][0]:
                    found.append(f"orphan {paragraph}")
                if len(lines) >= 2 and lines[-1][0] != lines[-2][0]:
                    found.append(f"widow {paragraph}")
    return found


class _KeepTogether:
    """Mixin: one layout, typeset with and without the protection."""

    PARALLEL: bool
    TYPOGRAPHY: dict
    SIDES: str
    FACING_PAGES = False
    PRIMARY = "en"

    @classmethod
    def setUpClass(cls):
        cls.where, cls.tex = _typeset(cls.PARALLEL, cls.TYPOGRAPHY, primary=cls.PRIMARY)
        cls.unprotected, _ = _typeset(cls.PARALLEL, cls.TYPOGRAPHY, protected=False,
                                      primary=cls.PRIMARY)

    def _of_kind(self, kind: str) -> list[str]:
        return [v for v in _violations(self.where, self.SIDES, self.FACING_PAGES)
                if v.startswith(kind)]

    def test_every_word_is_set(self):
        # A line lost while reading the columns would also mean no widows.
        expected = sum(_LENGTHS[n % len(_LENGTHS)] * 3 + 5 for n in range(_SECTIONS))
        self.assertEqual(
            sum(1 for w in self.where if re.fullmatch(r"L[PQ]\d+w\d+", w)), expected)
        rubrics = sum(_RUBRICS[n % len(_RUBRICS)] for n in range(_SECTIONS)
                      if _inner_rubric(n) or _rubric_before(n))
        self.assertEqual(
            sum(1 for w in self.where if re.fullmatch(r"LI\d+w\d+", w)), rubrics)

    def test_the_rubrics_stand_on_lines_of_their_own(self):
        # A rubric run in with its text is part of a line of text; only one on lines of
        # its own can be parted from what it introduces.
        self.assertNotIn(r"\instructionnote{", self.tex)
        self.assertIn(r"\OSInstructionBlock{", self.tex)

    def test_no_widows(self):
        self.assertEqual(self._of_kind("widow"), [])

    def test_no_orphans(self):
        self.assertEqual(self._of_kind("orphan"), [])

    def test_no_split_headings(self):
        self.assertEqual(self._of_kind("split heading"), [])

    def test_no_stranded_headings(self):
        self.assertEqual(self._of_kind("stranded heading"), [])

    def test_no_stranded_rubrics(self):
        self.assertEqual(self._of_kind("stranded rubric"), [])

    def test_the_sweep_reaches_a_page_edge(self):
        # Without the protection the same document breaks somewhere it should not, and a
        # rubric is among what it parts.
        broken = _violations(self.unprotected, self.SIDES, self.FACING_PAGES)
        self.assertTrue(any(v.startswith("stranded rubric") for v in broken), broken)


_NEEDS_TEX = unittest.skipUnless(
    shutil.which("lualatex") and shutil.which("pdftotext"),
    "requires a real lualatex installation and pdftotext",
)


@_NEEDS_TEX
class TestSingleStream(_KeepTogether, unittest.TestCase):
    """One text: each heading, with its translated title, is a \\pstart of its own, and an
    English rubric in the Hebrew text stands on lines of its own."""

    PARALLEL = False
    TYPOGRAPHY = {}
    SIDES = "L"


@_NEEDS_TEX
class TestPairsColumnHeadings(_KeepTogether, unittest.TestCase):
    """``\\Columns``, each column setting its own heading, with unpaired passages."""

    PARALLEL = True
    TYPOGRAPHY = {"parallel": {"layout": "pairs"}, "headings": {"from": "both"}}
    SIDES = "LR"


@_NEEDS_TEX
class TestPairsSpanningHeadings(_KeepTogether, unittest.TestCase):
    """``\\Columns``, with the headings set across the page above the columns, in Hebrew."""

    PARALLEL = True
    TYPOGRAPHY = {"parallel": {"layout": "pairs"}, "headings": {"from": "combined"}}
    SIDES = "LR"
    PRIMARY = "he"

    def test_the_titles_are_set_in_hebrew(self):
        self.assertIn(r"\begin{hebrew}\OSApplyKeep \OSheadA{", self.tex)


@_NEEDS_TEX
class TestFacingPages(_KeepTogether, unittest.TestCase):
    """``\\Pages``, where reledpar ends each page itself."""

    PARALLEL = True
    TYPOGRAPHY = {"parallel": {"layout": "pages"}, "headings": {"from": "both"}}
    SIDES = "LR"
    FACING_PAGES = True


@_NEEDS_TEX
class TestColumnHeadingStaysInItsColumn(unittest.TestCase):
    """A heading in a ``\\Columns`` column that runs to several lines, with a translated
    title under it, is set wholly in its own column.

    A \\nobreak between the two used to cut reledpar's reading of the column short, and the
    heading's last line was set full width, under the other column (Birnbaum's "TALMUDIC
    EXPOSITION OF THE SCRIPTURES", whose "TURES" landed under the Hebrew)."""

    HEADING_WORDS = 14

    @classmethod
    def setUpClass(cls):
        long_head = " ".join(f"RHw{n}" for n in range(cls.HEADING_WORDS))
        document = f"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="en">
  <tei:text><tei:body>
    <p:parallel column-order="primary_first">
      <p:parallelItem role="primary" xml:lang="en"><tei:div corresp="urn:x-opensiddur:text:t:s0"><tei:p>{_words("LP0", 40)}</tei:p></tei:div></p:parallelItem>
      <p:parallelItem role="parallel" xml:lang="en"><tei:div corresp="urn:x-opensiddur:text:t:s0"><tei:head>{long_head}</tei:head><tei:head>RT0</tei:head><tei:p>{_words("RP0", 40)}</tei:p></tei:div></p:parallelItem>
    </p:parallel>
  </tei:body></tei:text>
</tei:TEI>"""
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "in.xml").write_text(document)
            transform_xml_to_tex(
                work / "in.xml", output_file=str(work / "t.tex"),
                typography=TypographyConfig.model_validate(
                    {"parallel": {"layout": "pairs"}, "headings": {"from": "both"}}),
                project_directory=work,
                distribution=NO_NOTICES,
            )
            for _ in range(3):
                subprocess.run(["lualatex", "-interaction=nonstopmode", "t.tex"],
                               cwd=work, capture_output=True, text=True)
            boxes = subprocess.run(["pdftotext", "-bbox", "t.pdf", "-"],
                                   cwd=work, capture_output=True, text=True).stdout
        found = re.findall(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>([^<]*)</word>', boxes)
        cls.x = {word: float(x) for x, _, word in found}
        cls.y = {word: round(float(y)) for _, y, word in found}

    def test_every_word_of_the_heading_is_in_the_right_column(self):
        # The right column's text marks where that column begins.
        column = min(x for w, x in self.x.items() if w.startswith("RP0w"))
        heading = {w: x for w, x in self.x.items() if w.startswith("RHw")}
        self.assertEqual(len(heading), self.HEADING_WORDS)
        outside = [w for w, x in heading.items() if x < column - 1]
        self.assertEqual(outside, [])

    def test_the_heading_runs_to_several_lines(self):
        # Otherwise there is no last line to lose, and the test above proves nothing.
        lines = {y for w, y in self.y.items() if w.startswith("RHw")}
        self.assertGreater(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
