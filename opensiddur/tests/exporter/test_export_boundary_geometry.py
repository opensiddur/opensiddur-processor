"""Check actual word boundaries and wrapped footnote direction in rendered PDFs."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from opensiddur.tests.exporter.stylesheet_helpers import transform


def document(body, lang='en'):
    return ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" '
            'xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="'+lang+'">'
            '<tei:text><tei:body>'+body+'</tei:body></tei:text></tei:TEI>')


def render(xml):
    tex = transform(xml, typography={'line_numbers': {'enabled': False}},
                    **{'distribution-notice':'','back-notice':''})
    with tempfile.TemporaryDirectory() as tmp:
        work=Path(tmp);(work/'t.tex').write_text(tex)
        for _ in range(3):
            r=subprocess.run(['lualatex','-interaction=nonstopmode','-halt-on-error','t.tex'],
                             cwd=work,capture_output=True,text=True)
            if r.returncode:raise AssertionError(r.stdout[-4000:])
        text=subprocess.check_output(['pdftotext','t.pdf','-'],cwd=work,text=True)
        bbox=subprocess.check_output(['pdftotext','-bbox','t.pdf','-'],cwd=work,text=True)
    return text,bbox


@unittest.skipUnless(shutil.which('lualatex') and shutil.which('pdftotext'),
                     'requires lualatex and pdftotext')
class TestExportBoundaryGeometry(unittest.TestCase):
    def test_conditional_closing_bracket_preserves_word_space_and_prefix_join(self):
        xml=document('<tei:p>Before <j:conditional xml:id="a" type="marked"/>'
                     'inside <j:endConditional target="#a"/>after. '
                     '<j:conditional xml:id="b" type="marked"/>pre'
                     '<j:endConditional target="#b"/>fix.</tei:p>')
        text,_=render(xml)
        self.assertIn('[inside] after.',text)
        self.assertIn('[pre]fix.',text)

    def test_conditional_rubric_separates_the_opening_bracket(self):
        xml=document('<p:parallel column-order="primary_first">'
                     '<p:parallelItem role="primary" xml:lang="en"><tei:p>'
                     '<j:conditional xml:id="c" type="marked">'
                     '<tei:note type="instruction">Rubric</tei:note>'
                     '</j:conditional>inside'
                     '<j:endConditional target="#c"/></tei:p></p:parallelItem>'
                     '<p:parallelItem role="parallel" xml:lang="en">'
                     '<tei:p>Other column.</tei:p></p:parallelItem></p:parallel>')
        text,_=render(xml)
        self.assertIn('Rubric [inside]',text)

    def test_fullwidth_heading_clears_the_previous_cross_language_rubric(self):
        xml=document('<tei:div><tei:note type="instruction" xml:lang="en">'
                     'RubricEnd</tei:note><tei:div><tei:head>HeadingMark</tei:head>'
                     '<tei:p>שָׁלוֹם עוֹלָם</tei:p></tei:div></tei:div>',lang='he')
        _,bbox=render(xml)
        boxes={m[4]:tuple(float(m[i])for i in range(1,4))for m in re.finditer(
            r'<word xMin="[\d.]+" yMin="([\d.]+)" xMax="([\d.]+)" '
            r'yMax="([\d.]+)">(RubricEnd|HeadingMark)</word>',bbox)}
        self.assertEqual({'RubricEnd','HeadingMark'},boxes.keys())
        self.assertGreaterEqual(boxes['HeadingMark'][0]-boxes['RubricEnd'][2],3)

    def test_wrapped_english_footnote_keeps_ltr_last_line_in_hebrew_book(self):
        words=('The final abbreviation remains uncertain. א״ז״וו may represent '
               'German und so weiter (and so on); this is an editorial interpretation, '
               'not a confirmed source reading.')
        # This is a full-width passage inside a parallel book, like the
        # untranslated Minchah appendix; reledpar is loaded even for this row.
        xml=document('<p:parallel column-order="primary_first">'
                     '<p:parallelItem role="primary" xml:lang="he"><tei:div>'
                     '<tei:p>שָׁלוֹם<tei:note xml:lang="he">פירוש בעברית</tei:note>'
                     '<tei:note xml:lang="en">Footstart '+words+
                     ' Tailword</tei:note> עוֹלָם</tei:p></tei:div></p:parallelItem>'
                     '<p:parallelItem role="parallel" xml:lang="en"/>'
                     '</p:parallel>',lang='he')
        _,bbox=render(xml)
        points={m[3]:(float(m[1]),float(m[2]))for m in re.finditer(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>(Footstart|Tailword)</word>',bbox)}
        self.assertEqual({'Footstart','Tailword'},points.keys())
        self.assertGreater(points['Tailword'][1],points['Footstart'][1])
        # Inspect the first word of the naturally wrapped final line. A forced
        # line break can mask inherited RTL paragraph direction.
        final_y = points['Tailword'][1]
        final_x = [float(m[1]) for m in re.finditer(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>[^<]*</word>', bbox)
                   if abs(float(m[2]) - final_y) < 0.1]
        self.assertLessEqual(min(final_x), points['Footstart'][0] + 1)
