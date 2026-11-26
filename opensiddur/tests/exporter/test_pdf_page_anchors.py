"""Page destinations must survive printed folio resets without collisions."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from opensiddur.tests.exporter.stylesheet_helpers import transform


DOCUMENT = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="en">
  <tei:text><tei:front>
    <tei:titlePage><tei:docTitle><tei:titlePart type="main">First title</tei:titlePart></tei:docTitle></tei:titlePage>
    <tei:titlePage><tei:docTitle><tei:titlePart type="main">Second title</tei:titlePart></tei:docTitle></tei:titlePage>
    <tei:titlePage><tei:docImprint>Invented copyright</tei:docImprint></tei:titlePage>
  </tei:front><tei:body>
    <tei:div><tei:head>First section</tei:head><tei:p>Opening words. See page
      <tei:ref type="page" target="closing"/>.
      <tei:ref p:local-target="closing">Jump to closing</tei:ref>.</tei:p></tei:div>
    <tei:div><tei:head>Closing section</tei:head><tei:p>
      <tei:anchor type="page-label" n="closing"/>Closing body words.</tei:p></tei:div>
  </tei:body></tei:text>
</tei:TEI>'''


class PageAnchorPreambleTests(unittest.TestCase):
    def test_page_destinations_use_the_independent_counter(self):
        tex = transform(DOCUMENT)
        option = r'\hypersetup{hypertexnames=false}'
        self.assertIn(option, tex)
        self.assertLess(tex.index(r'\usepackage{hyperref}'), tex.index(option))
        self.assertLess(tex.index(option), tex.index(r'\begin{document}'))


@unittest.skipUnless(shutil.which('lualatex'), 'requires LuaLaTeX')
class PageAnchorPdfTests(unittest.TestCase):
    def test_repeated_folios_have_unique_physical_destinations_and_working_links(self):
        tex = transform(DOCUMENT, {'table_of_contents': {'enabled': True}})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'book.tex').write_text(tex, encoding='utf-8')
            for _ in range(3):
                run = subprocess.run(
                    ['lualatex', '-interaction=nonstopmode', '-halt-on-error', 'book.tex'],
                    cwd=root, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout[-3000:])
                self.assertNotIn('ignoring duplicate destination', run.stdout)
            reader = PdfReader(root/'book.pdf')
            # Title pages reset the displayed folio; identities must not reset.
            self.assertLess(len(set(reader.page_labels)), len(reader.page_labels))
            page_targets = {name: destination for name, destination
                            in reader.named_destinations.items() if name.startswith('page.')}
            self.assertEqual(set(page_targets), {f'page.{n}' for n in range(1, len(reader.pages)+1)})
            for name, destination in page_targets.items():
                self.assertEqual(reader.get_destination_page_number(destination), int(name[5:])-1)

            body_page = next(n for n, page in enumerate(reader.pages)
                             if 'Closing body words.' in page.extract_text())
            self.assertEqual(reader.page_labels[body_page], '1')
            self.assertRegex(reader.pages[body_page].extract_text(), r'See page\s*1')
            linked_pages = []
            for page in reader.pages:
                for reference in page.get('/Annots', []):
                    annotation = reference.get_object()
                    destination = annotation.get('/Dest')
                    if destination is None and annotation.get('/A', {}).get('/S') == '/GoTo':
                        destination = annotation['/A']['/D']
                    if isinstance(destination, str):
                        self.assertIn(destination, reader.named_destinations)
                        linked_pages.append(reader.get_destination_page_number(
                            reader.named_destinations[destination]))
            # Two contents entries plus the generated page number and literal link.
            self.assertGreaterEqual(linked_pages.count(body_page), 4)
            outline = [item for item in reader.outline if not isinstance(item, list)]
            self.assertEqual([item.title for item in outline], ['First section', 'Closing section'])
            self.assertTrue(all(reader.get_destination_page_number(item) == body_page for item in outline))
