"""Tests for how the front matter of the 1949 print is assembled into an index.

The words are not checked here. They are a reading committed to `sourcetexts`, and
asserting on them would transcribe the book a second time into a test and break the
next time a reading is corrected. Every fragment below is synthetic. What is checked
is the arrangement: which leaf goes to which side, what a leaf with no section
contributes, and that the one-sided sections are transcluded by both indexes.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from lxml import etree

from opensiddur.importer.birnbaum_scan.build import common, front
from opensiddur.tests.importer.birnbaum_scan import write_synthetic_front

NS = {"tei": "http://www.tei-c.org/ns/1.0", "j": "http://jewishliturgy.org/ns/jlptei/2"}
WRAPPER = ('<root xmlns:tei="http://www.tei-c.org/ns/1.0" '
           'xmlns:j="http://jewishliturgy.org/ns/jlptei/2">%s</root>')



class FakeLeaf:
    def __init__(self, leaf):
        self.leaf = leaf


class FrontMatterTestCase(unittest.TestCase):
    """Every leaf the front matter covers, with a synthetic reading behind each file."""

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.fragments = write_synthetic_front(Path(directory.name))
        patch = mock.patch.object(front, "FRAGMENTS", self.fragments)
        patch.start()
        self.addCleanup(patch.stop)

    def parsed(self, project):
        return etree.fromstring(WRAPPER % front.front_block(project))[0]

    def test_the_two_sides_split_the_front_matter_by_language(self):
        """One leaf belongs to one side, as the recto/verso of the body already do."""
        self.assertEqual(
            set(front.TITLE_LEAVES[common.PROJECT_HE])
            & set(front.TITLE_LEAVES[common.PROJECT_EN]),
            set(),
        )

    def test_every_leaf_appears_exactly_once(self):
        for project in (common.PROJECT_HE, common.PROJECT_EN):
            with self.subTest(project=project):
                block = self.parsed(project)
                designations = [e.get("n") for e in block.iter("{%s}pb" % NS["tei"])]
                self.assertEqual(len(designations), len(set(designations)))

    def test_a_leaf_with_no_section_contributes_a_bare_page_break(self):
        """So that each side's foliation runs unbroken through the front matter. A title
        leaf's page break is lifted out of its title page, so it stands at the top too."""
        block = self.parsed(common.PROJECT_HE)
        top = [e.get("n") for e in block if etree.QName(e).localname == "pb"]
        leaves = sorted(set(front.BARE[common.PROJECT_HE])
                        | set(dict(front.TITLE_LEAVES[common.PROJECT_HE])))
        self.assertEqual(top, [front.DESIGNATION[leaf] for leaf in leaves])

    def gates(self, block):
        """Each element of the block, paired with the paratext feature gating it, if any."""
        open_gate = None
        for element in block:
            name = etree.QName(element).localname
            if name == "conditional":
                feature = element.find("tei:fs/tei:f", NS)
                self.assertEqual(element.find("tei:fs", NS).get("type"), "opensiddur:paratext")
                self.assertIsNone(element.get("type"), "a paratext gate is never marked")
                self.assertIsNone(element.find("tei:note", NS), "a paratext gate says nothing")
                open_gate = (element.get("{http://www.w3.org/XML/1998/namespace}id"),
                             feature.get("name"))
            elif name == "endConditional":
                self.assertEqual(element.get("target"), "#" + open_gate[0])
                open_gate = None
            else:
                yield element, open_gate and open_gate[1]

    def test_every_section_is_gated_as_paratext(self):
        for project in (common.PROJECT_HE, common.PROJECT_EN):
            with self.subTest(project=project):
                for element, feature in self.gates(self.parsed(project)):
                    if etree.QName(element).localname == "transclude":
                        self.assertEqual(feature, "include")

    def test_every_title_page_is_gated_as_a_title_page(self):
        for project in (common.PROJECT_HE, common.PROJECT_EN):
            with self.subTest(project=project):
                gated = [e for e, feature in self.gates(self.parsed(project))
                         if etree.QName(e).localname == "titlePage"
                         and feature == "title-page"]
                self.assertEqual(len(gated), len(front.TITLE_LEAVES[project]))

    def test_no_page_break_is_gated(self):
        """Leaving the paratext out must not break the foliation."""
        for project in (common.PROJECT_HE, common.PROJECT_EN):
            with self.subTest(project=project):
                block = self.parsed(project)
                for element, feature in self.gates(block):
                    if etree.QName(element).localname == "pb":
                        self.assertIsNone(feature)
                for title_page in block.findall("tei:titlePage", NS):
                    self.assertIsNone(title_page.find("tei:pb", NS))

    def test_a_title_leaf_without_its_page_break_is_refused(self):
        """Rather than gate a page break away with the title page it sits in."""
        name = dict(front.TITLE_LEAVES[common.PROJECT_HE])[2]
        (self.fragments / name).write_text(
            '<tei:titlePage xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:docTitle>'
            '<tei:titlePart>t</tei:titlePart></tei:docTitle></tei:titlePage>\n',
            encoding="utf-8")
        with self.assertRaises(ValueError):
            front.front_block(common.PROJECT_HE)

    def test_gate_ids_are_unique(self):
        for project in (common.PROJECT_HE, common.PROJECT_EN):
            with self.subTest(project=project):
                ids = [e.get("{http://www.w3.org/XML/1998/namespace}id")
                       for e in self.parsed(project).findall("j:conditional", NS)]
                self.assertEqual(len(ids), len(set(ids)))

    def test_a_page_break_in_the_front_matter_names_no_printing(self):
        block = self.parsed(common.PROJECT_EN)
        for element in block.iter("{%s}pb" % NS["tei"]):
            self.assertEqual(element.get("ed"), common.FRONT_SIGIL)

    def test_both_indexes_transclude_every_one_sided_section(self):
        """The Hebrew index realises none of these and transcludes them all: Birnbaum
        wrote them in English, and without the transclusion a Hebrew-primary compile
        would simply lack his introduction."""
        expected = [common.FRONT + s["slug"] for s in front.SECTIONS]
        for project in (common.PROJECT_HE, common.PROJECT_EN):
            with self.subTest(project=project):
                targets = [t.get("target")
                           for t in self.parsed(project).findall(".//j:transclude", NS)]
                self.assertEqual(targets, expected)

    def test_the_designations_the_book_does_not_print_are_bracketed(self):
        """The printed Roman sequence starts at IX on leaf 11, which fixes leaf 3 as I;
        everything before that is supplied, and says so."""
        self.assertEqual(front.DESIGNATION[11], "IX")
        self.assertEqual(front.DESIGNATION[25], "XXIII")
        self.assertEqual(front.DESIGNATION[3], "[I]")
        self.assertEqual(front.DESIGNATION[10], "[VIII]")
        for leaf in range(1, 11):
            self.assertTrue(front.DESIGNATION[leaf].startswith("["))
        for leaf in range(11, 26):
            self.assertFalse(front.DESIGNATION[leaf].startswith("["))


if __name__ == "__main__":
    unittest.main()
