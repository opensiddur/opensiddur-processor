r"""Where do the links to the scans land on the page?

None of it is visible in the ``.tex``: a margin symbol is set where its page break is and
moved out to the margin by TeX, from a position saved on the run before. So the document
is typeset -- on the exporter's real preamble, from the stylesheet's real output -- and the
links are measured in the PDF.

A link must open the page break's ``@facs``, show its symbol, and, in the margin, lie
outside the text and clear of the line numbers -- in a Hebrew column as in an English one:
reledmac's own side notes are lost in right-to-left text, which is why they are not used.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lxml import etree
from pypdf import PdfReader

from opensiddur.exporter.scan_links import mark_scan_links
from opensiddur.tests.exporter.stylesheet_helpers import NO_NOTICES, transform

_WORD = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')

_HEBREW = " ".join(["שָׁלוֹם עוֹלָם וְשָׁלוֹם"] * 12)
_ENGLISH = " ".join(f"word{n}" for n in range(60))


def _pb(n: int) -> str:
    return f'<tei:pb n="{n}" ed="1" facs="https://scan.example/page?n={n}&amp;size=1"/>'


def _document(body: str, lang: str = "he") -> str:
    return (
        '<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" '
        f'xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="{lang}">'
        f"<tei:text><tei:body>{body}</tei:body></tei:text></tei:TEI>")


_SINGLE = _document(
    f"<tei:p>{_pb(1)}{_HEBREW}</tei:p><tei:p>{_HEBREW} {_pb(2)}{_HEBREW}</tei:p>")

_PARALLEL = _document(
    '<p:parallel column-order="primary_first">'
    f'<p:parallelItem role="primary" xml:lang="he"><tei:p>{_pb(1)}{_HEBREW}</tei:p>'
    "</p:parallelItem>"
    f'<p:parallelItem role="parallel" xml:lang="en"><tei:p>{_pb(2)}{_ENGLISH}</tei:p>'
    "</p:parallelItem></p:parallel>")


class Box:
    def __init__(self, x0: float, y0: float, x1: float, y1: float, text: str = ""):
        self.x0, self.y0, self.x1, self.y1, self.text = x0, y0, x1, y1, text

    def overlaps(self, other: "Box") -> bool:
        return not (self.x1 <= other.x0 or other.x1 <= self.x0
                    or self.y1 <= other.y0 or other.y1 <= self.y0)

    def __repr__(self):
        return f"{self.text!r}@x[{self.x0:.1f},{self.x1:.1f}] y[{self.y0:.1f},{self.y1:.1f}]"


@unittest.skipUnless(shutil.which("lualatex") and shutil.which("pdftotext"),
                     "requires a real lualatex installation and pdftotext")
class TestScanLinkGeometry(unittest.TestCase):

    def _typeset(self, xml: str, typography: dict):
        """The first page's links (as boxes in pdftotext's coordinates, top down), its
        words, and the run's log."""
        root = etree.fromstring(xml)
        mark_scan_links(root)
        tex = transform(etree.tostring(root, encoding="unicode"), typography=typography,
                        **{"distribution-notice": "", "back-notice": ""})
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "t.tex").write_text(tex, encoding="utf-8")
            for _ in range(3):  # reledmac and the saved positions need runs to settle
                done = subprocess.run(["lualatex", "-interaction=nonstopmode", "t.tex"],
                                      cwd=work, capture_output=True, text=True)
            self.assertTrue((work / "t.pdf").exists(),
                            f"lualatex produced no PDF:\n{done.stdout[-2000:]}")
            log = (work / "t.log").read_text(encoding="utf-8", errors="replace")
            page = PdfReader(work / "t.pdf").pages[0]
            height = float(page.mediabox.height)
            links = []
            for annotation in page.get("/Annots") or []:
                annotation = annotation.get_object()
                uri = annotation.get("/A", {}).get("/URI")
                if uri:
                    x0, y0, x1, y1 = (float(v) for v in annotation["/Rect"])
                    links.append(Box(x0, height - y1, x1, height - y0, uri))
            bbox = subprocess.run(["pdftotext", "-f", "1", "-l", "1", "-bbox", "t.pdf", "-"],
                                  cwd=work, capture_output=True, text=True).stdout
        words = [Box(*(float(m.group(i)) for i in range(1, 5)), m.group(5))
                 for m in _WORD.finditer(bbox) if m.group(5).strip()]
        return links, words, log

    @staticmethod
    def _text(words):
        """The words of the text: not the line numbers, the folio or the symbols."""
        return [w for w in words if not w.text.isdigit() and w.text != "↗"]

    @staticmethod
    def _line(link, words):
        return [w for w in words if not (w.y1 <= link.y0 or w.y0 >= link.y1)]

    def _margin(self, xml: str, **settings):
        typography = {"markers": {"scan_links": {"placement": "margin"}},
                      "line_numbers": {"increment": 1, "first": 1}, **settings}
        return self._typeset(xml, typography)

    def assertOutsideTheText(self, links, words):
        text = self._text(words)
        numbers = [w for w in words if w.text.isdigit()]
        for link in links:
            for word in text:
                self.assertFalse(link.overlaps(word), f"{link} is set on {word}")
            for number in numbers:
                self.assertFalse(link.overlaps(number), f"{link} is set on {number}")

    def test_a_hebrew_text_has_its_links_in_the_margin(self):
        links, words, log = self._margin(_SINGLE)
        self.assertEqual(["https://scan.example/page?n=1&size=1",
                          "https://scan.example/page?n=2&size=1"],
                         sorted(link.text for link in links))
        self.assertOutsideTheText(links, words)
        text = self._text(words)
        left, right = min(w.x0 for w in text), max(w.x1 for w in text)
        for link in links:
            self.assertTrue(link.x1 <= left or link.x0 >= right,
                            f"{link} is inside the text block [{left:.1f},{right:.1f}]")

    def test_a_margin_link_is_beside_its_line(self):
        links, words, _ = self._margin(_SINGLE)
        second = next(link for link in links if link.text.endswith("n=2&size=1"))
        self.assertTrue(self._text(self._line(second, words)),
                        f"no line of text beside {second}")

    def test_paired_columns_have_their_links_on_their_outer_sides(self):
        links, words, _ = self._margin(_PARALLEL, parallel={"layout": "pairs"})
        self.assertEqual(2, len(links))
        self.assertOutsideTheText(links, words)
        hebrew = next(link for link in links if "n=1" in link.text)
        english = next(link for link in links if "n=2" in link.text)
        text = self._text(words)
        self.assertLess(hebrew.x1, min(w.x0 for w in text))
        self.assertGreater(english.x0, max(w.x1 for w in text))

    def test_an_inline_link_is_in_the_line(self):
        links, words, log = self._typeset(
            _SINGLE, {"markers": {"scan_links": {"placement": "inline"}}})
        self.assertEqual(2, len(links))
        for link in links:
            # Next to a word of its line, not out in the margin.
            gap = min(max(w.x0 - link.x1, link.x0 - w.x1)
                      for w in self._text(self._line(link, words)))
            self.assertLess(gap, 6, f"{link} is not in its line")

    def test_the_symbol_is_in_the_font(self):
        _, _, log = self._margin(_SINGLE)
        self.assertNotIn("Missing character", log)


if __name__ == "__main__":
    unittest.main()
