"""A Hebrew-only TOC title must not reverse its page number or move it left."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.tests.exporter.stylesheet_helpers import transform


@unittest.skipUnless(shutil.which('lualatex') and shutil.which('mutool'), 'requires LuaLaTeX and mutool')
class TocDirectionGeometryTest(unittest.TestCase):
    def test_hebrew_entry_has_ltr_page_number_and_right_hand_page_column(self):
        xml='''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
        <tei:text><tei:body><tei:div><tei:head>פזמון</tei:head><tei:p>שלום עולם</tei:p></tei:div>
        </tei:body></tei:text></tei:TEI>'''
        tex=transform(xml,{'table_of_contents':{'enabled':True}})
        tex=tex.replace('\\mainmatter','\\mainmatter\\setcounter{page}{35}')
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp);(directory/'toc.tex').write_text(tex)
            for _ in range(3):
                completed=subprocess.run(['lualatex','-interaction=nonstopmode','-halt-on-error','toc.tex'],cwd=directory,capture_output=True)
                self.assertEqual(0,completed.returncode,completed.stdout.decode(errors='replace')[-2000:])
            output=subprocess.check_output(['mutool','draw','-F','stext','toc.pdf'],cwd=directory,stderr=subprocess.DEVNULL)
            tree=etree.fromstring(output)
            page=next(p for p in tree.findall('page') if any('Contents' in l.get('text','') for l in p.findall('.//line')))
            heading=next(l for l in page.findall('.//line') if any('פ' in c.get('c','') for c in l.findall('.//char')))
            y=float(heading.find('.//char').get('y'))
            row=[c for c in page.findall('.//char') if abs(float(c.get('y'))-y)<1]
            digits=[c for c in row if c.get('c','').isdigit()]
            self.assertEqual('35',''.join(c.get('c') for c in digits))
            self.assertLess(float(digits[0].get('x')),float(digits[1].get('x')),'TOC page number is reversed')
            hebrew=[float(c.get('x')) for c in row if '\u0590'<=c.get('c',' ')<='\u05ff']
            self.assertGreater(min(float(c.get('x')) for c in digits),max(hebrew),'TOC page number moved to the left column')
            self.assertEqual(sorted(hebrew,reverse=True),hebrew,'Hebrew title reversed')
            from pypdf import PdfReader
            self.assertEqual('פזמון',PdfReader(directory/'toc.pdf').outline[0].title)
