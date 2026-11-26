"""Semantic psalm titles cover nested source transclusions without rewriting prayers."""
import unittest

from lxml import etree as E

from opensiddur.exporter.html.psalms import (
    J,
    P,
    T,
    hebrew_number,
    normalize,
    psalm_number,
)


def fixture(body):
    return E.fromstring(f'<tei:TEI xmlns:tei="{T[1:-1]}" xmlns:p="{P[1:-1]}" xmlns:j="{J[1:-1]}"><tei:text><tei:body>{body}</tei:body></tei:text></tei:TEI>')


class TestPsalmHeadings(unittest.TestCase):
    def test_hebrew_numbers_and_whole_psalm_detection(self):
        for n,s in [(1,'א'),(15,'טו'),(16,'טז'),(23,'כג'),(92,'צב'),(100,'ק'),(115,'קטו'),(150,'קנ')]:
            self.assertEqual(hebrew_number(n),s)
        for n in [0,151]:
            with self.assertRaises(ValueError):hebrew_number(n)
        self.assertEqual(psalm_number('urn:x-opensiddur:text:bible:psalms/23'),23)
        self.assertIsNone(psalm_number('urn:x-opensiddur:text:bible:psalms/23/1'))
        self.assertIsNone(psalm_number('urn:x-opensiddur:text:prayer:ashrei'))

    def test_nested_whole_psalm_gets_two_titles_and_preserves_every_prayer_node(self):
        root=fixture('''<p:transclude target="urn:source-unit"><tei:div><tei:p>Introduction</tei:p></tei:div>
            <p:transclude target="urn:x-opensiddur:text:bible:psalms/23"><tei:div type="book">
            <tei:p><tei:milestone unit="chapter" n="23" corresp="urn:x-opensiddur:text:bible:psalms/23"/>
            <tei:milestone unit="verse" n="1"/>Prayer text</tei:p></tei:div></p:transclude></p:transclude>''')
        paragraphs=[E.tostring(p) for p in root.iter(T+'p')]
        report=normalize(root)
        self.assertEqual(report['wrapped'],1)
        heads=list(root.iter(T+'head'))
        self.assertEqual([h.text for h in heads],['תהלים כג','Psalm 23'])
        # The only annotation on existing nodes suppresses the chapter label.
        for mark in root.iter(T+'milestone'):mark.attrib.pop(P+'chapter-label',None)
        self.assertEqual([E.tostring(p) for p in root.iter(T+'p')],paragraphs)
        self.assertEqual(normalize(root)['wrapped'],0)

    def test_ranges_and_composites_are_preserved(self):
        body='''<tei:head xml:lang="en">Psalm 95:1–3</tei:head>
            <p:transclude target="urn:x-opensiddur:text:bible:psalms/95/1" targetEnd="urn:x-opensiddur:text:bible:psalms/95/3"><tei:p>Excerpt</tei:p></p:transclude>
            <p:transclude target="urn:x-opensiddur:text:prayer:ashrei"><tei:p>Composite prayer</tei:p></p:transclude>'''
        root=fixture(body);before=E.tostring(root)
        self.assertEqual(normalize(root)['wrapped'],0)
        self.assertEqual(E.tostring(root),before)

    def test_adjacent_old_titles_are_replaced_and_scope_boundaries_preserved(self):
        reference='<p:transclude target="urn:x-opensiddur:text:bible:psalms/23"><tei:p>Prayer</tei:p></p:transclude>'
        for boundary,expected in [('',2),('<j:conditional xml:id="eligible"/>',4)]:
            root=fixture('<tei:head xml:lang="he">תהלים 23</tei:head><tei:head xml:lang="en">PSALM 23</tei:head>'+boundary+reference)
            normalize(root)
            self.assertEqual(len([h for h in root.iter(T+'head') if h.get(P+'suppress-psalm-heading')!='true']),expected)
            self.assertEqual(len(list(root.iter(J+'conditional'))),bool(boundary))

    def test_hallel_titles_are_normalized_without_changing_full_hallel_predicate(self):
        root=fixture('''<tei:head xml:lang="he">תהלים 115</tei:head><tei:head xml:lang="en">Psalm 115</tei:head>
            <j:conditional xml:id="full"><tei:fs type="opensiddur:hallel"><tei:f name="full"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>
            <tei:p>First part</tei:p><j:endConditional target="#full"/><tei:p>Remaining part</tei:p>''')
        condition=E.tostring(next(root.iter(J+'conditional')))
        normalize(root)
        self.assertEqual([h.get(P+'psalm-title') for h in root.iter(T+'head')],['תהלים קטו','Psalm 115'])
        self.assertEqual(E.tostring(next(root.iter(J+'conditional'))),condition)
