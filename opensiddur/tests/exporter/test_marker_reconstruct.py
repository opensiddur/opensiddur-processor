"""Tests for flattened parallel marker reconstruction (compiler output stage)."""

import unittest
import unittest.mock

from lxml import etree

from opensiddur.exporter.constants import JLPTEI_NAMESPACE
from opensiddur.exporter.external_compiler import PROCESSING_NAMESPACE, TEI_NS
from opensiddur.exporter.marker_reconstruct import (
    doc_needs_marker_reconstruction,
    reconstruct_markered_document,
    reconstruct_container,
    substantive_content,
)
from opensiddur.exporter import marker_reconstruct as mr

P_NS = PROCESSING_NAMESPACE
J_NS = JLPTEI_NAMESPACE
XML_NS = "http://www.w3.org/XML/1998/namespace"


class TestMarkerReconstruct(unittest.TestCase):

    def test_doc_needs_parallel(self):
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:text><tei:body><p:parallel><p:parallelItem role="primary"/>
          </p:parallel></tei:body></tei:text></tei:TEI>"""
        root = etree.fromstring(xml.encode())
        self.assertTrue(doc_needs_marker_reconstruction(root))

    def test_legacy_body_no_reconstruct_flag(self):
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}"><tei:text><tei:body>
          <tei:div><tei:p>Hello</tei:p></tei:div>
        </tei:body></tei:text></tei:TEI>"""
        root = etree.fromstring(xml.encode())
        self.assertFalse(doc_needs_marker_reconstruction(root))

    def test_whole_start_to_end_has_no_p_part(self):
        ns = {"tei": TEI_NS, "p": P_NS}
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:text><tei:body>
            <p:parallel><p:parallelItem role="primary" xml:lang="he">
              <tei:div p:start="x" n="a"/>
              <tei:head>H</tei:head>
              <tei:p p:start="y"><tei:hi>in</tei:hi></tei:p>
              <tei:p p:end="y"/>
              <tei:div p:end="x"/>
            </p:parallelItem><p:parallelItem role="parallel" xml:lang="en">
              <tei:div p:start="x2" n="a"/>
              <tei:head>E</tei:head>
              <tei:p p:start="y2">en</tei:p>
              <tei:p p:end="y2"/>
              <tei:div p:end="x2"/>
            </p:parallelItem></p:parallel>
          </tei:body></tei:text></tei:TEI>"""
        root = etree.fromstring(xml.encode())
        reconstruct_markered_document(root)
        divs = root.xpath("//tei:div[@n='a']", namespaces=ns)
        self.assertEqual(len(divs), 2)
        for d in divs:
            self.assertIsNone(d.get(f"{{{P_NS}}}part"))
            self.assertIsNone(d.get(f"{{{P_NS}}}start"))

    def test_split_segments_get_p_part(self):
        ns = {"tei": TEI_NS, "p": P_NS}
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:text><tei:body>
            <p:parallel><p:parallelItem role="primary">
              <tei:p p:start="a">A</tei:p>
              <tei:p p:suspend="a"/>
            </p:parallelItem></p:parallel>
            <p:parallel><p:parallelItem role="primary">
              <tei:p p:resume="a">B</tei:p>
              <tei:p p:end="a"/>
            </p:parallelItem></p:parallel>
          </tei:body></tei:text></tei:TEI>"""
        root = etree.fromstring(xml.encode())
        reconstruct_markered_document(root)
        parts = [
            el.get(f"{{{P_NS}}}part")
            for el in root.xpath("//tei:p", namespaces=ns)
            if el.get(f"{{{P_NS}}}part")
        ]
        self.assertEqual(parts, ["first", "last"])

    def test_empty_segment_dropped_and_relabeled(self):
        ns = {"tei": TEI_NS, "p": P_NS}
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:text><tei:body>
            <p:parallel><p:parallelItem role="primary">
              <tei:p p:start="a"/>
              <tei:p p:suspend="a"/>
            </p:parallelItem></p:parallel>
            <p:parallel><p:parallelItem role="primary">
              <tei:p p:resume="a">Only</tei:p>
              <tei:p p:end="a"/>
            </p:parallelItem></p:parallel>
          </tei:body></tei:text></tei:TEI>"""
        root = etree.fromstring(xml.encode())
        reconstruct_markered_document(root)
        ps = root.xpath("//tei:p", namespaces=ns)
        self.assertEqual(len(ps), 1)
        self.assertIsNone(ps[0].get(f"{{{P_NS}}}part"))
        self.assertIn("Only", "".join(ps[0].itertext()))

    def test_conditional_markers_outlive_a_pruned_segment(self):
        """A segment holding only a scope's closer (or a rubric-less opener) has no words,
        and is pruned -- but the markers must stay, where the segment was, or the scope
        loses an end."""
        ns = {"tei": TEI_NS, "p": P_NS, "j": J_NS}
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}" xmlns:j="{J_NS}">
          <tei:text><tei:body>
            <p:parallel><p:parallelItem role="primary">
              <tei:div p:start="a"/>Before
              <tei:div p:suspend="a"/>
            </p:parallelItem></p:parallel>
            <p:parallel><p:parallelItem role="primary">
              <tei:div p:resume="a"/><j:endConditional target="#c1"/>
              <tei:div p:suspend="a"/>
            </p:parallelItem></p:parallel>
            <p:parallel><p:parallelItem role="primary">
              <tei:div p:resume="a"/><j:conditional xml:id="c2"/>
              <tei:div p:suspend="a"/>
            </p:parallelItem></p:parallel>
            <p:parallel><p:parallelItem role="primary">
              <tei:div p:resume="a"/>After
              <tei:div p:end="a"/>
            </p:parallelItem></p:parallel>
          </tei:body></tei:text></tei:TEI>"""
        root = etree.fromstring(xml.encode())
        reconstruct_markered_document(root)
        items = root.xpath("//p:parallelItem", namespaces=ns)
        self.assertEqual(
            [(child.tag, child.get("target") or child.get(f"{{{XML_NS}}}id"))
             for child in items[1]],
            [(f"{{{J_NS}}}endConditional", "#c1")])
        self.assertEqual(
            [child.get(f"{{{XML_NS}}}id") for child in items[2]], ["c2"])
        self.assertEqual(
            [d.get(f"{{{P_NS}}}part") for d in root.xpath("//tei:div", namespaces=ns)],
            ["first", "last"])

    def test_nested_conditional_marker_outlives_a_pruned_segment(self):
        """A marker nested in an empty paragraph of the pruned segment is kept too."""
        ns = {"tei": TEI_NS, "p": P_NS, "j": J_NS}
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}" xmlns:j="{J_NS}">
          <tei:text><tei:body>
            <p:parallel><p:parallelItem role="primary">
              <tei:div p:start="a"/>Before
              <tei:div p:suspend="a"/>
            </p:parallelItem></p:parallel>
            <p:parallel><p:parallelItem role="primary">
              <tei:div p:resume="a"/><tei:p><j:endConditional target="#c1"/></tei:p>
              <tei:div p:end="a"/>
            </p:parallelItem></p:parallel>
          </tei:body></tei:text></tei:TEI>"""
        root = etree.fromstring(xml.encode())
        reconstruct_markered_document(root)
        closers = root.xpath("//j:endConditional", namespaces=ns)
        self.assertEqual([c.get("target") for c in closers], ["#c1"])
        self.assertEqual(closers[0].getparent().tag, f"{{{P_NS}}}parallelItem")

    def test_substantive_content_milestone_tail(self):
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}">
          <tei:p><tei:milestone unit="verse" n="1"/>text</tei:p>
        </tei:TEI>"""
        root = etree.fromstring(xml.encode())
        p = root.find(f".//{{{TEI_NS}}}p")
        self.assertTrue(substantive_content(p))

    def test_substantive_content_bare_milestone(self):
        """A milestone with no text of its own (e.g. a chapter marker) still counts: it
        is a deliberate marker, never filler, even though it carries no text."""
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}">
          <tei:p><tei:milestone unit="chapter" n="5"/></tei:p>
        </tei:TEI>"""
        root = etree.fromstring(xml.encode())
        p = root.find(f".//{{{TEI_NS}}}p")
        self.assertTrue(substantive_content(p))

    def test_a_bare_milestone_fragment_is_not_pruned(self):
        """A source tei:p that a chapter-boundary milestone splits into three parallel-row
        fragments (verses before, the bare milestone alone, verses after) reconstructs into
        three same-logical-id fragments. The middle one carries no text of its own — this
        is what silently erased chapter numbers from the compiled humash, wherever one
        landed alone between two verse-aligned parallel segments like this."""
        ns = {"tei": TEI_NS, "p": P_NS}
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:text><tei:body>
            <tei:p p:logical-id="a" p:part="first">before</tei:p>
            <tei:p p:logical-id="a" p:part="middle"><tei:milestone unit="chapter" n="6"/></tei:p>
            <tei:p p:logical-id="a" p:part="last">after</tei:p>
          </tei:body></tei:text></tei:TEI>"""
        root = etree.fromstring(xml.encode())
        from opensiddur.exporter.marker_reconstruct import normalize_segment_parts
        normalize_segment_parts(root)
        ps = root.xpath("//tei:p", namespaces=ns)
        self.assertEqual(len(ps), 3, "the milestone-only fragment must survive")
        milestones = root.xpath("//tei:milestone[@unit='chapter']", namespaces=ns)
        self.assertEqual(len(milestones), 1)
        self.assertEqual(milestones[0].get("n"), "6")
        # Still ordered first/middle/last across all three surviving fragments.
        self.assertEqual([p.get(f"{{{P_NS}}}part") for p in ps], ["first", "middle", "last"])

    def test_substantive_content_nested_child_text(self):
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}">
          <tei:p><tei:hi><tei:seg>deep</tei:seg></tei:hi></tei:p>
        </tei:TEI>"""
        root = etree.fromstring(xml.encode())
        p = root.find(f".//{{{TEI_NS}}}p")
        self.assertTrue(substantive_content(p))

    def test_reconstruct_parallel_item_raises_on_unclosed_stack(self):
        xml = f"""<p:parallelItem xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:div p:start="x">dangling</tei:div>
        </p:parallelItem>"""
        pi = etree.fromstring(xml.encode())
        with self.assertRaises(ValueError):
            reconstruct_container(pi, mr.defaultdict(dict))

    def test_close_open_segment_validates_stack_and_pid(self):
        stack: list[mr._Frame] = []
        fragments: list[etree.ElementBase] = []
        pid_state: dict[str, dict] = {}

        with self.assertRaises(ValueError):
            mr._close_open_segment(stack, fragments, pid_state, pid="x", kind="end")

        stack.append(mr._Frame("a", f"{{{TEI_NS}}}div", {}, []))
        with self.assertRaises(ValueError):
            mr._close_open_segment(stack, fragments, pid_state, pid="b", kind="end")

        stack.append(mr._Frame("c", f"{{{TEI_NS}}}div", {}, []))
        with self.assertRaises(ValueError):
            mr._close_open_segment(stack, fragments, pid_state, pid="c", kind="bogus")

    def test_new_wrapped_segment_strips_processing_markers(self):
        child = etree.Element(f"{{{TEI_NS}}}p", nsmap={"tei": TEI_NS, "p": P_NS})
        el = mr._new_wrapped_segment(
            f"{{{TEI_NS}}}div",
            {
                mr._P_START: "s",
                mr._P_END: "e",
                mr._P_SUSPEND: "su",
                mr._P_RESUME: "r",
                mr._P_LOGICAL: "lid",
                mr._P_PART: "first",
            },
            [child],
            logical_id=None,
            leading_text_chunks=[],
        )
        for mk in (mr._P_START, mr._P_END, mr._P_SUSPEND, mr._P_RESUME, mr._P_LOGICAL, mr._P_PART):
            self.assertIsNone(el.get(mk))

    def test_normalize_segment_parts_strips_stray_markers_and_sets_middle(self):
        ns = {"tei": TEI_NS, "p": P_NS}
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:text><tei:body>
            <tei:p p:logical-id="a" p:start="x">one</tei:p>
            <tei:p p:logical-id="a" p:part="ignored">two</tei:p>
            <tei:p p:logical-id="a" p:end="x">three</tei:p>
          </tei:body></tei:text></tei:TEI>"""
        root = etree.fromstring(xml.encode())
        mr.normalize_segment_parts(root)

        ps = root.xpath("//tei:p", namespaces=ns)
        self.assertEqual([p.get(f"{{{P_NS}}}part") for p in ps], ["first", "middle", "last"])
        for p in ps:
            self.assertIsNone(p.get(f"{{{P_NS}}}logical-id"))
            self.assertIsNone(p.get(f"{{{P_NS}}}start"))
            self.assertIsNone(p.get(f"{{{P_NS}}}end"))

    def test_strip_processing_markers_from_header(self):
        ns = {"tei": TEI_NS, "p": P_NS}
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:teiHeader>
            <tei:fileDesc>
              <tei:titleStmt>
                <tei:title p:start="x" p:logical-id="lid">T</tei:title>
              </tei:titleStmt>
            </tei:fileDesc>
          </tei:teiHeader>
          <tei:text><tei:body>
            <p:parallel><p:parallelItem role="primary">
              <tei:p p:start="a">A</tei:p><tei:p p:end="a"/>
            </p:parallelItem></p:parallel>
          </tei:body></tei:text>
        </tei:TEI>"""
        root = etree.fromstring(xml.encode())
        header = root.xpath("//tei:teiHeader", namespaces=ns)[0]
        title = root.xpath("//tei:title", namespaces=ns)[0]
        self.assertIn(f"{{{P_NS}}}start", title.attrib)
        self.assertIn(f"{{{P_NS}}}logical-id", title.attrib)
        reconstruct_markered_document(root)
        self.assertIsNone(title.get(f"{{{P_NS}}}start"))
        self.assertIsNone(title.get(f"{{{P_NS}}}logical-id"))

        # Also cover the helper directly to ensure marker stripping is executed.
        title.set(f"{{{P_NS}}}start", "x2")
        mr._strip_stray_processing_markers_under(header)
        self.assertIsNone(title.get(f"{{{P_NS}}}start"))

    def test_doc_needs_marker_reconstruction_structural_marker(self):
        xml = f"""<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:text><tei:body>
            <tei:div p:start="x"><tei:p>Hi</tei:p></tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        root = etree.fromstring(xml.encode())
        self.assertTrue(doc_needs_marker_reconstruction(root))

    def test_reconstruct_parallel_item_moves_structural_with_unknown_marker(self):
        # _structural_marker_map normally only returns start/end/suspend/resume.
        # Patch it to simulate a future/unknown marker key so we hit the fallback move path.
        xml = f"""<p:parallelItem xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}">
          <tei:div p:start="x"/><tei:div p:end="x"/>
        </p:parallelItem>"""
        pi = etree.fromstring(xml.encode())
        with unittest.mock.patch.object(mr, "_structural_marker_map", return_value={"unknown": "z"}):
            reconstruct_container(pi, mr.defaultdict(dict))
        self.assertEqual(len(pi), 2)

    def test_large_stream_reparents_content_without_detaching_it(self):
        # Detached lxml subtrees migrate namespaces and IDs to temporary
        # documents. A book-sized stream must move its content directly into
        # the rebuilt wrappers; only the empty marker carriers are discarded.
        class RetainedElement(etree.ElementBase):
            def remove(self, element):
                if not mr._structural_marker_map(element):
                    raise AssertionError('content was detached into a temporary document')
                return super().remove(element)
        parser = etree.XMLParser()
        parser.set_element_class_lookup(etree.ElementDefaultClassLookup(element=RetainedElement))
        children = ''.join(f'<tei:seg xml:id="word-{i}">word {i}</tei:seg>' for i in range(1000))
        xml = f'<root xmlns:tei="{TEI_NS}" xmlns:p="{P_NS}"><tei:p p:start="paragraph"/>{children}<tei:p p:end="paragraph"/></root>'
        root = etree.fromstring(xml.encode(), parser)
        original = list(root)[1:-1]
        reconstruct_container(root, mr.defaultdict(dict))
        self.assertEqual(len(root), 1)
        self.assertEqual(root[0].tag, f'{{{TEI_NS}}}p')
        self.assertEqual(list(root[0]), original)
        self.assertEqual([e.text for e in root[0]], [f'word {i}' for i in range(1000)])
        self.assertEqual(root[0][500].get(f'{{{XML_NS}}}id'), 'word-500')
        reparsed = etree.fromstring(etree.tostring(root))
        self.assertEqual(len(reparsed.xpath("id('word-500')")), 1)


class TestPageMarkerFragments(unittest.TestCase):
    ns = {'t': TEI_NS, 'p': P_NS, 'j': J_NS}

    def normalize(self, content):
        root = etree.fromstring((f'<root xmlns:t="{TEI_NS}" xmlns:p="{P_NS}" '
                                 f'xmlns:j="{J_NS}">{content}</root>').encode())
        mr.normalize_segment_parts(root)
        return root

    def test_leading_markers_move_to_text_without_empty_paragraph(self):
        root = self.normalize(
            '<t:p p:logical-id="x"><t:pb n="1" ed="book" facs="leaf1"/></t:p>'
            '<t:p p:logical-id="x">Words<t:hi> more</t:hi></t:p>')
        self.assertEqual(len(root), 1)
        paragraph = root[0]
        self.assertEqual(paragraph[0].attrib, {'n': '1', 'ed': 'book', 'facs': 'leaf1'})
        self.assertIsNone(paragraph.text)
        self.assertEqual(paragraph[0].tail, 'Words')
        self.assertEqual(''.join(paragraph.itertext()), 'Words more')
        self.assertIsNone(paragraph.get(f'{{{P_NS}}}part'))

    def test_multiple_empty_fragments_preserve_marker_order_and_column(self):
        root = self.normalize(
            '<p:parallel><p:parallelItem role="primary" xml:lang="he">'
            '<t:p p:logical-id="h"><t:pb n="1"/></t:p></p:parallelItem>'
            '<p:parallelItem role="parallel" xml:lang="en">English</p:parallelItem></p:parallel>'
            '<p:parallel><p:parallelItem role="primary" xml:lang="he">'
            '<t:p p:logical-id="h"><t:pb n="2"/><t:pb n="3"/></t:p></p:parallelItem></p:parallel>'
            '<p:parallel><p:parallelItem role="primary" xml:lang="he">'
            '<t:p p:logical-id="h">Hebrew</t:p></p:parallelItem></p:parallel>')
        paragraphs = root.xpath('//t:p', namespaces=self.ns)
        self.assertEqual(len(paragraphs), 1)
        self.assertEqual([n.get('n') for n in paragraphs[0]], ['1', '2', '3'])
        self.assertEqual(paragraphs[0][-1].tail, 'Hebrew')
        self.assertFalse(root.xpath('//p:parallelItem[@role="parallel"]//t:pb', namespaces=self.ns))

    def test_trailing_marker_survives_without_empty_wrapper(self):
        root = self.normalize('<t:p p:logical-id="x">Words</t:p>'
                              '<t:p p:logical-id="x"><t:pb n="2"/></t:p>')
        self.assertEqual([n.tag for n in root], [f'{{{TEI_NS}}}p', f'{{{TEI_NS}}}pb'])
        self.assertEqual(root[1].get('n'), '2')

    def test_cannot_pass_intervening_text_or_scope(self):
        for middle in ['<t:p>Other words</t:p>', '<j:conditional xml:id="c"/>',
                       '<j:endConditional target="#c"/>', '<j:declare xml:id="d"/>',
                       '<j:endDeclare target="#d"/>', '<p:transclude><t:p>Other</t:p></p:transclude>']:
            with self.subTest(middle=middle):
                root = self.normalize('<t:p p:logical-id="x"><t:pb n="1"/></t:p>' +
                                      middle + '<t:p p:logical-id="x">Words</t:p>')
                self.assertEqual(root[0].tag, f'{{{TEI_NS}}}pb')
                self.assertEqual(root[-1].text, 'Words')

    def test_cannot_cross_column_or_transclusion_instances(self):
        for opening, closing in [('<p:parallelItem role="parallel" xml:lang="en">', '</p:parallelItem>'),
                                 ('<p:transclude>', '</p:transclude>')]:
            with self.subTest(opening=opening):
                root = self.normalize(
                    '<p:parallelItem role="primary" xml:lang="he">'
                    '<t:p p:logical-id="x"><t:pb n="1"/></t:p></p:parallelItem>' +
                    opening + '<t:p p:logical-id="x">Words</t:p>' + closing)
                self.assertEqual(root[0][0].tag, f'{{{TEI_NS}}}pb')
                self.assertFalse(root[1].xpath('.//t:pb', namespaces=self.ns))

    def test_donor_scope_markers_stay_in_original_order(self):
        root = self.normalize(
            '<t:div p:logical-id="x"><t:p><j:conditional xml:id="c"/>'
            '<t:pb n="1"/><j:endConditional target="#c"/></t:p></t:div>'
            '<t:div p:logical-id="x">Words</t:div>')
        self.assertEqual([n.tag for n in root], [f'{{{J_NS}}}conditional',
                         f'{{{TEI_NS}}}pb', f'{{{J_NS}}}endConditional', f'{{{TEI_NS}}}div'])
        self.assertEqual(root[-1].text, 'Words')

    def test_destination_conditional_is_not_entered(self):
        root = self.normalize('<t:p p:logical-id="x"><t:pb n="1"/></t:p>'
                              '<j:conditional xml:id="c"/><t:p p:logical-id="x">Words</t:p>')
        self.assertEqual(root[0].tag, f'{{{TEI_NS}}}pb')
        self.assertEqual(root[-1].text, 'Words')

    def test_marker_does_not_pass_text_in_empty_wrappers_tail(self):
        root = self.normalize('<t:p p:logical-id="x"><t:pb n="1"/></t:p>Between'
                              '<t:p p:logical-id="x">Words</t:p>')
        self.assertEqual(root[0].tag, f'{{{TEI_NS}}}pb')
        self.assertEqual(root[0].tail, 'Between')
        self.assertEqual(root[1].text, 'Words')

    def test_reconstructed_parallel_preamble_joins_following_alignment_row(self):
        root = etree.fromstring((f'<root xmlns:t="{TEI_NS}" xmlns:p="{P_NS}">'
            '<p:parallel><p:parallelItem role="primary" xml:lang="he">'
            '<t:p p:start="x"/><t:pb xml:id="pb1" n="92" facs="scan203"/>'
            '<t:p p:suspend="x"/></p:parallelItem></p:parallel>'
            '<p:parallel><p:parallelItem role="primary" xml:lang="he">'
            '<t:p p:resume="x"/><t:milestone unit="prayer-part" corresp="urn:part"/>Words'
            '<t:p p:end="x"/></p:parallelItem></p:parallel></root>').encode())
        reconstruct_markered_document(root)
        paragraphs = root.xpath('//t:p', namespaces=self.ns)
        self.assertEqual(len(paragraphs), 1)
        self.assertEqual([n.tag for n in paragraphs[0]],
                         [f'{{{TEI_NS}}}pb', f'{{{TEI_NS}}}milestone'])
        self.assertEqual(paragraphs[0][0].get(f'{{{XML_NS}}}id'), 'pb1')
        self.assertEqual(paragraphs[0][0].get('facs'), 'scan203')
        self.assertEqual(''.join(paragraphs[0].itertext()), 'Words')
