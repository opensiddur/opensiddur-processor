r"""Running-head marks must not disturb reledmac's extraction of single lines.

Compare actual PDF word coordinates with and without chapter milestones. The
same paragraph contains marks at its start, middle and end; a following
paragraph catches a mark queue escaping into the next one. The marks must also
reach the running head, rather than being discarded to repair the geometry.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from opensiddur.tests.exporter.stylesheet_helpers import transform

_WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" '
                   r'xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')


def _document(marked):
    words = []
    for n in range(150):
        if marked and n in (0, 27, 89):
            words.append(f'<tei:milestone unit="chapter" n="{17 + n}"/>')
        words.append(f'word{n}')
    if marked:
        words.append('<tei:milestone unit="chapter"/>')
    tail = ' '.join(f'next{n}' for n in range(50))
    return ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">'
            '<tei:text><tei:body><tei:p>' + ' '.join(words) + '</tei:p>'
            '<tei:p>' + tail + '</tei:p></tei:body></tei:text></tei:TEI>')


@unittest.skipUnless(shutil.which('lualatex') and shutil.which('pdftotext'),
                     'requires lualatex and pdftotext')
class TestSingleStreamMarkGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rendered = {}
        for marked in (False, True):
            tex = transform(_document(marked),
                            typography={'line_numbers': {'enabled': False}},
                            **{"distribution-notice": "", "back-notice": ""})
            # Read the first actual chapter mark from the PDF's running head.
            tex = tex.replace(r'\begin{document}',
                              r'\begin{document}\pagestyle{fancy}\fancyhf{}'
                              r'\fancyhead[R]{Chapter \FirstMark{OSchapter}}', 1)
            with tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                (work / 't.tex').write_text(tex)
                for _ in range(3):
                    done = subprocess.run(
                        ['lualatex', '-interaction=nonstopmode', '-halt-on-error', 't.tex'],
                        cwd=work, capture_output=True, text=True)
                    if done.returncode:
                        raise AssertionError(done.stdout[-4000:])
                bbox = subprocess.run(['pdftotext', '-bbox', 't.pdf', '-'],
                                      cwd=work, check=True, capture_output=True,
                                      text=True).stdout
            all_words = list(_WORD.finditer(bbox))
            points = {m[5]: tuple(float(m[i]) for i in range(1, 5))
                      for m in all_words if re.fullmatch(r'(word|next)\d+', m[5])}
            cls.rendered[marked] = (points, [m[5] for m in all_words])

    def test_chapter_marks_preserve_every_word_and_its_line_geometry(self):
        plain, _ = self.rendered[False]
        marked, _ = self.rendered[True]
        self.assertEqual(200, len(plain))
        self.assertEqual(plain.keys(), marked.keys())
        for word in plain:
            for expected, actual in zip(plain[word][1::2], marked[word][1::2]):
                self.assertAlmostEqual(expected, actual, delta=0.05,
                                       msg=f'{word} moved after adding chapter marks')

    def test_collected_marks_still_reach_the_running_head(self):
        _, words = self.rendered[True]
        self.assertIn('Chapter', words)
        self.assertIn('17', words)
