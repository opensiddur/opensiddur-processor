r"""Does a passage with no counterpart use the whole width of the page?

A parallel block whose other side sets no text -- none at all, or only an anchor carrying
a note -- has nothing to face, so it is set across the page between two column blocks
rather than in one column beside an empty one (#194). The ``.tex`` tests check the
structure; this one typesets it and measures the lines.

Every word names its block and side, as in the facing-pages tests: ``L2w7`` is the
eighth word of block 2's left text.
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


_NOTE = "Notetext"


def _block(n: int, left: str, right: str) -> str:
    return f"""
    <p:parallel column-order="primary_first">
      <p:parallelItem role="primary" xml:lang="en">{left}</p:parallelItem>
      <p:parallelItem role="parallel" xml:lang="en">{right}</p:parallelItem>
    </p:parallel>"""


_DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="en">
  <tei:text><tei:body>
    {_block(1, f"<tei:p>{_words('L1w', 80)}</tei:p>", f"<tei:p>{_words('R1w', 80)}</tei:p>")}
    {_block(2, f"<tei:p>{_words('L2w', 80)}</tei:p>",
            '<tei:p><tei:milestone unit="prayer-part" corresp="urn:x-opensiddur:text:t/2"/>'
            f'<tei:anchor xml:id="a2"><tei:note>{_NOTE}</tei:note></tei:anchor></tei:p>')}
    {_block(3, f"<tei:p>{_words('L3w', 80)}</tei:p>", f"<tei:p>{_words('R3w', 80)}</tei:p>")}
  </tei:body></tei:text>
</tei:TEI>"""


@unittest.skipUnless(
    shutil.which("lualatex") and shutil.which("pdftotext"),
    "requires a real lualatex installation and pdftotext",
)
class TestUnpairedPassageGeometry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "in.xml").write_text(_DOCUMENT)
            transform_xml_to_tex(
                work / "in.xml", output_file=str(work / "t.tex"),
                typography=TypographyConfig.model_validate({"parallel": {"layout": "pairs"}}),
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
        # (xMin, xMax, word) for every word of the document, on whichever page.
        cls.words = [
            (float(x0), float(x1), word) for x0, x1, word in re.findall(
                r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)"[^>]*>([^<]*)</word>',
                boxes)
        ]

    def _span(self, prefix: str) -> float:
        """How far across the page the words starting with ``prefix`` reach."""
        xs = [(x0, x1) for x0, x1, w in self.words if w.startswith(prefix)]
        self.assertTrue(xs, f"no {prefix} words were set")
        return max(x1 for _, x1 in xs) - min(x0 for x0, _ in xs)

    def test_the_lone_passage_is_wider_than_a_column(self):
        column = max(self._span("L1w"), self._span("R1w"))
        self.assertGreater(self._span("L2w"), 1.5 * column)

    def test_the_columns_resume_after_it(self):
        self.assertLess(self._span("L3w"), 0.6 * self._span("L2w"))
        self.assertTrue(any(w.startswith("R3w") for _, _, w in self.words))

    def test_the_note_is_set_once(self):
        self.assertEqual(1, sum(1 for _, _, w in self.words if _NOTE in w))
