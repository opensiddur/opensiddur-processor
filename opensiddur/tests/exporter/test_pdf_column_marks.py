"""Optional real-engine regression for lines escaping a parallel column."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from lxml import etree

from opensiddur.tests.exporter.stylesheet_helpers import transform


@unittest.skipUnless(shutil.which('lualatex') and shutil.which('pdftotext'),
                     'requires LuaLaTeX and Poppler')
class ColumnMarkRenderingTest(unittest.TestCase):
    def test_a_chapter_mark_does_not_move_a_continuation_to_the_other_column(self):
        # The mark migrates after the final line box. reledpar must retain that
        # line in its column, even when there is little text on the other side.
        count = 60
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                    xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
          <tei:text><tei:body><p:parallel column-order="primary_first">
            <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום עולם
              <tei:milestone unit="chapter" n="2"/></tei:p></p:parallelItem>
            <p:parallelItem role="parallel" xml:lang="en"><tei:p>'''+(
                'continuation ' * count)+'''<tei:milestone unit="chapter" n="2"/>
              </tei:p></p:parallelItem>
          </p:parallel></tei:body></tei:text></tei:TEI>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path/'columns.tex'
            source.write_text(transform(xml, layout='pairs'))
            env = dict(os.environ)
            for name in ('TEXMFCACHE', 'TEXMFVAR'):
                env.setdefault(name, str(path/'cache'))
            for _ in range(3):
                result = subprocess.run(
                    ['lualatex', '-interaction=nonstopmode', '-halt-on-error', source.name],
                    cwd=path, env=env, capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout[-5000:])
            result = subprocess.run(['pdftotext', '-bbox', str(path/'columns.pdf'), '-'],
                                    capture_output=True, check=True)
            root = etree.fromstring(result.stdout)
            words = root.xpath('//*[local-name()="word" and .="continuation"]')
            self.assertEqual(len(words), count, 'No prayer words may disappear or repeat')
            for word in words:
                page = next(p for p in word.iterancestors()
                            if etree.QName(p).localname == 'page')
                self.assertGreaterEqual(float(word.get('xMin')), float(page.get('width'))/2,
                                        'An English continuation escaped the right column')
