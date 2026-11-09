"""Hidden margin numbers must not disable apparatus line tracking."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.exporter.tex.latex import transform_xml_to_tex
from opensiddur.exporter.typography import TypographyConfig
from opensiddur.tests.exporter.stylesheet_helpers import NO_NOTICES


@unittest.skipUnless(shutil.which('lualatex') and shutil.which('pdftotext'),
                     'requires real lualatex and pdftotext')
class TestHiddenLineNumberNotes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        filler = ' '.join(['Sample']*60)
        def block(left, right):
            return ('<p:parallel column-order="primary_first">'
                    '<p:parallelItem role="primary" xml:lang="he"><tei:p>'+left+'</tei:p></p:parallelItem>'
                    '<p:parallelItem role="parallel" xml:lang="en"><tei:p>'+right+'</tei:p></p:parallelItem>'
                    '</p:parallel>')
        xml = ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" '
               'xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">'
               '<tei:text><tei:body>'
               + block(filler, 'Anchorone<tei:note xml:lang="en">Noteone</tei:note> '+filler)
               + block(filler, filler)
               + block('Anchortwo<tei:note xml:lang="en">Notetwo</tei:note> '+filler,
                       'Anchorthree<tei:note xml:lang="en">Notethree</tei:note> '+filler)
               + '</tei:body></tei:text></tei:TEI>')
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work/'in.xml').write_text(xml)
            transform_xml_to_tex(
                work/'in.xml', output_file=str(work/'t.tex'), project_directory=work,
                distribution=NO_NOTICES,
                typography=TypographyConfig.model_validate({
                    'parallel': {'layout': 'pairs'},
                    'line_numbers': {'enabled': False, 'increment': 1, 'first': 1}}))
            for _ in range(3):
                result = subprocess.run(['lualatex', '-interaction=nonstopmode', '-halt-on-error', 't.tex'],
                                        cwd=work, capture_output=True, text=True)
                if result.returncode:
                    raise AssertionError(result.stdout[-2000:])
            bbox = subprocess.check_output(['pdftotext', '-bbox', 't.pdf', '-'], cwd=work)
        tree = etree.fromstring(bbox)
        cls.positions = {}
        for page, node in enumerate(tree.xpath('//*[local-name()="page"]')):
            for word in node.xpath('.//*[local-name()="word"]'):
                cls.positions.setdefault(word.text, []).append((page, float(word.get('yMin'))))

    def test_notes_print_in_reading_order_across_columns(self):
        positions = [self.positions[name][0] for name in ('Noteone', 'Notetwo', 'Notethree')]
        self.assertEqual(positions, sorted(positions))

    def test_notes_stay_on_the_pages_of_their_references(self):
        for anchor, note in [('Anchorone', 'Noteone'), ('Anchortwo', 'Notetwo'),
                             ('Anchorthree', 'Notethree')]:
            with self.subTest(note=note):
                self.assertEqual(self.positions[anchor][0][0], self.positions[note][0][0])
