"""Silent chapter fragments cannot consume a rubric's keep-with-next request."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from opensiddur.tests.exporter.stylesheet_helpers import transform


def _block(primary, other=''):
    return ('<p:parallel column-order="primary_first"><p:parallelItem role="primary" xml:lang="en">'
            + primary + '</p:parallelItem><p:parallelItem role="parallel" xml:lang="en">'
            + other + '</p:parallelItem></p:parallel>')


def document():
    blocks = []
    for n in range(35):
        blocks.append(_block(f'<tei:div><tei:note type="instruction">Role{n}</tei:note></tei:div>'))
        marker = '<tei:p p:part="middle"><tei:milestone unit="chapter" n="6"/></tei:p>'
        blocks.append(_block(marker, marker))
        blocks.append(_block(f'<tei:p>Left{n} responds.</tei:p>',
                             f'<tei:p>Right{n} responds.</tei:p>'))
    return ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" '
            'xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="en">'
            '<tei:text><tei:body>' + ''.join(blocks) + '</tei:body></tei:text></tei:TEI>')


class TestSilentFragmentRubricStructure(unittest.TestCase):
    def test_unpaired_marker_does_not_open_a_numbered_paragraph(self):
        tex = transform(document(), **{'distribution-notice': '', 'back-notice': ''})
        body = tex.split(r'\begin{document}', 1)[1]
        self.assertEqual(35 * 3, body.count(r'\pstart\relax'))
        self.assertEqual(35, body.count(r'\InsertMark{OSchapter}'))


@unittest.skipUnless(shutil.which('lualatex') and shutil.which('pdftotext'),
                     'requires lualatex and pdftotext')
class TestSilentFragmentRubricGeometry(unittest.TestCase):
    def test_every_role_stays_with_its_following_parallel_row(self):
        tex = transform(document(), typography={'line_numbers': {'enabled': False}},
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
        points = {}
        for page, content in enumerate(re.findall(r'<page[^>]*>(.*?)</page>', bbox, re.S)):
            for m in re.finditer(r'<word xMin="[\d.]+" yMin="([\d.]+)"[^>]*>((?:Role|Left|Right)\d+)</word>', content):
                points[m[2]] = (page, float(m[1]))
        for n in range(35):
            role, text = points[f'Role{n}'], points[f'Left{n}']
            self.assertEqual(role[0], text[0], f'Role{n} stranded at a page bottom')
            self.assertGreater(text[1], role[1])
            self.assertLess(text[1] - role[1], 30, f'Role{n} detached from its row')
