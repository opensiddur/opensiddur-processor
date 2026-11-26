"""Explicit Hebrew-script languages must retain direction in parallel columns."""
import re
import unittest

from opensiddur.tests.exporter.test_reledmac_xslt import _transform


class TestHebrewScriptStream(unittest.TestCase):
    def test_aramaic_script_controls_column_environment(self):
        for lang,expected in [('arc-Hebr',True),('he',True),('he-IL',True),('arc-Latn',False)]:
            with self.subTest(lang=lang):
                xml=f'''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                  xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="he">
                  <tei:text><tei:body><p:parallel>
                    <p:parallelItem role="primary" xml:lang="{lang}"><tei:p>אבג דהו</tei:p></p:parallelItem>
                    <p:parallelItem role="parallel" xml:lang="en"><tei:p>Sample words</tei:p></p:parallelItem>
                  </p:parallel></tei:body></tei:text></tei:TEI>'''
                out=_transform(xml)
                left=re.search(r'\\begin\{Leftside\}(.*?)\\end\{Leftside\}',out,re.S)
                self.assertIsNotNone(left)
                self.assertEqual(r'\begin{hebrew}' in left[1],expected)
                self.assertEqual(r'\end{hebrew}' in left[1],expected)
                if expected:
                    self.assertLess(left[1].index(r'\begin{hebrew}'),left[1].index('אבג'))
                    self.assertGreater(left[1].index(r'\end{hebrew}'),left[1].index('אבג'))
