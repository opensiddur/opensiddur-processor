"""Inline references remain within their containing bilingual paragraph."""
import unittest

from lxml import etree

from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.marker_reconstruct import reconstruct_markered_document

T='http://www.tei-c.org/ns/1.0'
P='http://jewishliturgy.org/ns/processing'


class ParallelInlineBoundariesTests(unittest.TestCase):
    def stream(self, words):
        start=etree.Element('{'+T+'}p',{'{'+P+'}start':'paragraph'})
        result=[start]
        for word in words:
            ref=etree.Element('{'+P+'}transclude',type='inline',target='urn:test:'+word)
            ref.text=word+' '
            result.append(ref)
        result.append(etree.Element('{'+T+'}p',{'{'+P+'}end':'paragraph'}))
        return result

    def assemble(self,primary,parallel):
        return ExternalCompilerProcessor._assemble_parallel_streams(
            primary,'he','original','book.xml',parallel,'en','translation','book.xml',
            'primary_first',{'tei':T,'p':P})

    def test_unequal_inline_lists_keep_paragraph_frames_and_translation(self):
        result=self.assemble(self.stream(['extra','verses']),self.stream(['translation']))
        root=etree.Element('root');root.extend(result)
        reconstruct_markered_document(root)
        self.assertEqual(len(root),1)
        self.assertEqual(root[0].tag,'{'+P+'}parallel')
        self.assertEqual([''.join(n.itertext()) for n in root[0]],['extra verses ','translation '])
        for item,count in zip(root[0],[2,1]):
            paragraph=item.find('{'+T+'}p')
            self.assertIsNotNone(paragraph)
            self.assertEqual(len(paragraph.findall('{'+P+'}transclude')),count)

    def test_inline_lists_do_not_shift_following_external_reference(self):
        streams=[self.stream(['extra','verses']),self.stream(['translation'])]
        for stream,word in zip(streams,['prayer','translated prayer']):
            ref=etree.Element('{'+P+'}transclude',type='external',target='urn:test:prayer')
            etree.SubElement(ref,'{'+T+'}p').text=word
            stream.append(ref)
        root=etree.Element('root');root.extend(self.assemble(*streams))
        reconstruct_markered_document(root)
        self.assertEqual([n.tag for n in root],['{'+P+'}parallel','{'+P+'}transclude'])
        self.assertEqual([''.join(n.itertext()) for n in root[1][0]],['prayer','translated prayer'])


class TestARubricOpeningARow(unittest.TestCase):
    """The rubric that opens a division moves into the division's row, with what is between."""

    def test_an_annotation_between_opener_and_description_moves_with_them(self):
        from lxml import etree

        from opensiddur.exporter.external_compiler import _alignment_boundaries
        tei, j = "http://www.tei-c.org/ns/1.0", "http://jewishliturgy.org/ns/jlptei/2"
        root = etree.fromstring(
            f'<r xmlns:tei="{tei}" xmlns:j="{j}"><tei:p>before</tei:p>'
            '<tei:note type="commentary">on what came before</tei:note>'
            '<j:conditional xml:id="c"/>'
            '<tei:note type="commentary">on the passage</tei:note>'
            '<tei:note type="description">Reader:</tei:note>'
            '<tei:milestone unit="verse" corresp="urn:x"/></r>')
        boundaries = _alignment_boundaries(list(root))
        self.assertEqual([None, None, "urn:x", None, None, None], boundaries)
