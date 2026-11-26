"""A heading-only Hebrew block must stay with the paired verse it introduces."""
import shutil
import unittest

from .test_keep_together_geometry import _typeset


def document():
    blocks = []
    for n in range(30):
        blocks.append(f'''<p:parallel column-order="primary_first">
          <p:parallelItem role="primary" xml:lang="he"><tei:div><tei:head>Heading{n}</tei:head></tei:div></p:parallelItem>
          <p:parallelItem role="parallel" xml:lang="en"><tei:div/></p:parallelItem>
        </p:parallel>''')
        lines = ''.join(f'<tei:l>Verse{n}line{k} שָׁלוֹם עוֹלָם</tei:l>' for k in range(6))
        prose = ' '.join(f'Prose{n}word{k}' for k in range(40 + (n % 7) * 11))
        blocks.append(f'''<p:parallel column-order="primary_first">
          <p:parallelItem role="primary" xml:lang="he"><tei:div><tei:lg>{lines}</tei:lg></tei:div></p:parallelItem>
          <p:parallelItem role="parallel" xml:lang="en"><tei:div><tei:p>{prose}</tei:p></tei:div></p:parallelItem>
        </p:parallel>''')
    return '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
      xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
      <tei:text><tei:body>''' + ''.join(blocks) + '</tei:body></tei:text></tei:TEI>'


@unittest.skipUnless(shutil.which('lualatex') and shutil.which('pdftotext'), 'requires LuaLaTeX and Poppler')
class UnpairedHeadingGeometryTests(unittest.TestCase):
    def test_heading_stays_with_first_verse_across_language_and_column_boundaries(self):
        positions, _ = _typeset(True, {'parallel': {'layout': 'pairs'}}, document=document())
        for n in range(30):
            with self.subTest(section=n):
                self.assertIn(f'Heading{n}', positions)
                self.assertIn(f'Verse{n}line0', positions)
                self.assertEqual(positions[f'Heading{n}'][0], positions[f'Verse{n}line0'][0])
