"""A standalone rubric must break lines in its own paragraph direction."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from opensiddur.tests.exporter.stylesheet_helpers import transform

CONTENT = ('Then the congregation says the prayer on page 89. On Sabbath the scroll '
           'of the Torah is taken out and the following passage is read. After the '
           'scroll has been returned the reader says half Kaddish and the congregation '
           'says the prayer on page 89. The reader repeats the prayer aloud together '
           'with the Kedushah. It is followed by Avinu Malkenu on page 121. '
           '<tei:lb/>Alpha <tei:foreign xml:lang="he">קדיש תתקבל</tei:foreign>, '
           'Beta <tei:foreign xml:lang="he">עלינו</tei:foreign> and '
           'Gamma <tei:foreign xml:lang="he">קדיש יתום</tei:foreign>.')

def document(language):
    return ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="' + language + '">'
            '<tei:text><tei:body><tei:div><tei:p>שלום עולם</tei:p>'
            '<tei:note type="instruction" xml:lang="en">' + CONTENT + '</tei:note>'
            '<tei:p>שלום עולם</tei:p></tei:div></tei:body></tei:text></tei:TEI>')

@unittest.skipUnless(shutil.which('lualatex') and shutil.which('pdftotext'),
                     'requires lualatex and pdftotext')
class TestCrossLanguageRubricGeometry(unittest.TestCase):
    def test_wrapped_english_rubric_keeps_ltr_last_line_in_hebrew_stream(self):
        tex = transform(document('he'), typography={'line_numbers': {'enabled': False}},
                        **{'distribution-notice': '', 'back-notice': ''})
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / 't.tex').write_text(tex)
            for _ in range(3):
                result = subprocess.run(['lualatex', '-interaction=nonstopmode',
                                         '-halt-on-error', 't.tex'], cwd=work,
                                        capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stdout[-4000:])
            bbox = subprocess.run(['pdftotext', '-bbox', 't.pdf', '-'], cwd=work,
                                  capture_output=True, text=True, check=True).stdout
        points = {m[3]: (float(m[1]), float(m[2])) for m in re.finditer(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>(Then|Alpha|Beta|Gamma)</word>', bbox)}
        self.assertEqual({'Then', 'Alpha', 'Beta', 'Gamma'}, points.keys())
        self.assertAlmostEqual(points['Alpha'][1], points['Gamma'][1], delta=0.1)
        # A short last line must start at the LTR margin, not be aligned
        # against the Hebrew stream's right margin.
        self.assertAlmostEqual(points['Alpha'][0], points['Then'][0], delta=0.1)
        self.assertLess(points['Alpha'][0], points['Beta'][0])
        self.assertLess(points['Beta'][0], points['Gamma'][0])

    def test_own_language_scope_closes_before_following_hebrew_paragraph(self):
        tex = transform(document('he'), **{'distribution-notice': '', 'back-notice': ''})
        body = tex.split(r'\begin{document}', 1)[1]
        self.assertRegex(body, r'\\begin\{english\}\s*\\instructionnote\{\\pstart')
        self.assertRegex(body, r'\\pend\}\s*\\end\{english\}\s*\\pstart')
