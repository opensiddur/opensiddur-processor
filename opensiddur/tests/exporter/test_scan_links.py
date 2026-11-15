"""Which page breaks link to the scan of their page (scan_links.py)."""

import unittest

from lxml import etree

from opensiddur.exporter.cli_common import prepare_compiled_tree
from opensiddur.exporter.constants import PROCESSING_NAMESPACE, TEI_NS
from opensiddur.exporter.scan_links import SCAN_LINK, mark_scan_links

TEI = f"{{{TEI_NS}}}"
SIDDUR = "urn:x-opensiddur:text:siddur:"


def _tree(body: str) -> etree.ElementBase:
    return etree.fromstring(
        f'<tei:TEI xmlns:tei="{TEI_NS}" xmlns:p="{PROCESSING_NAMESPACE}" xml:lang="he">'
        f"<tei:text><tei:body>{body}</tei:body></tei:text></tei:TEI>")


def _pb(n: str, ed: str = "1949", facs: bool = True) -> str:
    link = f' facs="https://scan.example/{n}"' if facs else ""
    return f'<tei:pb n="{n}" ed="{ed}"{link}/>'


def _transclude(target: str, content: str) -> str:
    return f'<p:transclude target="{target}" type="external">{content}</p:transclude>'


def _linked(root: etree.ElementBase) -> list[str]:
    return [pb.get("n") for pb in root.iter(f"{TEI}pb") if pb.get(SCAN_LINK) == "true"]


def _marked(body: str) -> list[str]:
    root = _tree(body)
    mark_scan_links(root)
    return _linked(root)


# One shared text, printed twice in its edition: once for weekdays, once for Shabbat.
_SHARED = _transclude(
    "urn:x-opensiddur:text:prayer:ashrei",
    "<tei:p>" + _pb("59", "1949 chol/shacharit/pesukei_dezimra")
    + _pb("321", "1949 shabbat/shacharit/pesukei_dezimra")
    + "Ashrei yoshvei veitekha" + _pb("60", "1949 chol/shacharit/pesukei_dezimra")
    + _pb("322", "1949 shabbat/shacharit/pesukei_dezimra") + " od yehallelukha</tei:p>")


class TestWhichBreaksAreCandidates(unittest.TestCase):
    def test_a_break_without_a_scan_is_never_linked(self):
        self.assertEqual([], _marked("<tei:p>" + _pb("1", facs=False) + "words</tei:p>"))

    def test_a_break_with_no_printing_is_linked(self):
        self.assertEqual(["1"], _marked("<tei:p>" + _pb("1") + "words</tei:p>"))

    def test_a_break_inside_a_note_is_ignored(self):
        self.assertEqual([], _marked(
            "<tei:p>words<tei:note>" + _pb("1") + "a note</tei:note> more</tei:p>"))

    def test_nothing_else_is_changed(self):
        root = _tree("<tei:p>" + _pb("1", facs=False) + "words</tei:p>")
        before = etree.tostring(root)
        mark_scan_links(root)
        self.assertEqual(before, etree.tostring(root))


class TestChoosingThePrinting(unittest.TestCase):
    def test_a_free_form_printing_label_is_one_printing(self):
        # Split on spaces, "sukkot rites" would be two printings; it is one.
        self.assertEqual(["703", "704"], _marked(
            "<tei:p>" + _pb("703", "1949 sukkot rites") + "words "
            + _pb("704", "1949 sukkot rites") + "more</tei:p>"))

    def test_the_enclosing_unit_chooses_the_printing(self):
        body = _transclude(SIDDUR + "shabbat/shacharit/pesukei_dezimra", _SHARED)
        self.assertEqual(["321", "322"], _marked(body))

    def test_the_same_text_in_another_unit_links_the_other_printing(self):
        body = _transclude(SIDDUR + "chol/shacharit/pesukei_dezimra", _SHARED)
        self.assertEqual(["59", "60"], _marked(body))

    def test_a_unit_inside_the_printing_matches_it(self):
        body = _transclude(SIDDUR + "shabbat/shacharit/pesukei_dezimra/ashrei", _SHARED)
        self.assertEqual(["321", "322"], _marked(body))

    def test_the_nearest_unit_decides(self):
        body = _transclude(
            SIDDUR + "chol",
            _transclude(SIDDUR + "shabbat/shacharit/pesukei_dezimra", _SHARED))
        self.assertEqual(["321", "322"], _marked(body))

    def test_a_break_naming_two_printings_counts_for_either(self):
        shared = _transclude(
            "urn:x-opensiddur:text:prayer:avot",
            "<tei:p>" + _pb("83", "1949 chol/shacharit/amidah chol/minchah/amidah")
            + _pb("451", "1949 shabbat/minchah") + "Barukh atah</tei:p>")
        body = _transclude(SIDDUR + "chol/minchah/amidah", shared)
        self.assertEqual(["83"], _marked(body))

    def test_the_longest_shared_path_is_the_fallback(self):
        # Neither printing is this unit's; the weekday morning one is closest.
        shared = _transclude(
            "urn:x-opensiddur:text:prayer:kaddish",
            "<tei:p>" + _pb("51", "1949 chol/shacharit/pesukei_dezimra")
            + _pb("301", "1949 shabbat/shacharit/pesukei_dezimra") + "Yitgadal</tei:p>")
        body = _transclude(SIDDUR + "chol/shacharit/opening", shared)
        self.assertEqual(["51"], _marked(body))

    def test_every_printing_is_linked_when_the_context_cannot_tell(self):
        # A book that copies several printings' units into one file.
        body = _transclude(SIDDUR + "expanded/evening", _SHARED)
        self.assertEqual(["59", "321", "60", "322"], _marked(body))

    def test_an_earlier_break_in_the_enclosing_unit_decides(self):
        body = _transclude(
            "urn:x-opensiddur:text:siddur:unknown",
            "<tei:p>" + _pb("320", "1949 shabbat/shacharit/pesukei_dezimra")
            + "Before</tei:p>" + _SHARED)
        self.assertEqual(["320", "321", "322"], _marked(body))

    def test_editions_are_chosen_separately(self):
        shared = _transclude(
            "urn:x-opensiddur:text:prayer:ashrei",
            "<tei:p>" + _pb("59", "1949 chol/shacharit/pesukei_dezimra")
            + _pb("321", "1949 shabbat/shacharit/pesukei_dezimra")
            + _pb("12", "1912") + "Ashrei</tei:p>")
        body = _transclude(SIDDUR + "shabbat/shacharit/pesukei_dezimra", shared)
        self.assertEqual(["321", "12"], _marked(body))


class TestMovingUpToTheWords(unittest.TestCase):
    def test_a_break_before_a_paragraph_moves_into_it(self):
        root = _tree(_pb("1") + "<tei:p>words</tei:p>")
        mark_scan_links(root)
        paragraph = root.find(f".//{TEI}p")
        self.assertEqual(f"{TEI}pb", paragraph[0].tag)
        self.assertEqual("words", paragraph[0].tail)

    def test_a_break_skips_a_heading(self):
        root = _tree("<tei:div>" + _pb("1") + "<tei:head>Title</tei:head>"
                     "<tei:p>words</tei:p></tei:div>")
        mark_scan_links(root)
        self.assertIsNotNone(root.find(f".//{TEI}p/{TEI}pb"))
        self.assertEqual("Title", root.find(f".//{TEI}head").text)

    def test_a_break_in_the_paragraph_of_its_words_stays(self):
        root = _tree("<tei:p>" + _pb("1") + '<tei:note type="instruction">Say:</tei:note>'
                     " words</tei:p>")
        before = etree.tostring(root.find(f".//{TEI}p"))
        mark_scan_links(root)
        pb = root.find(f".//{TEI}pb")
        del pb.attrib[SCAN_LINK]
        self.assertEqual(before, etree.tostring(root.find(f".//{TEI}p")))

    def test_a_break_skips_a_rubric_of_its_own(self):
        root = _tree(_pb("1") + '<tei:p><tei:note type="instruction">Say:</tei:note>'
                     " words</tei:p>")
        mark_scan_links(root)
        self.assertEqual(" words", root.find(f".//{TEI}pb").tail)

    def test_a_break_before_a_choice_goes_before_it(self):
        root = _tree("<tei:p>" + _pb("1") + "<tei:choice><tei:abbr>A</tei:abbr>"
                     "<tei:expan>Abbrev</tei:expan></tei:choice></tei:p>")
        mark_scan_links(root)
        self.assertEqual(f"{TEI}choice", root.find(f".//{TEI}pb").getnext().tag)

    def test_a_break_with_words_after_it_stays(self):
        root = _tree("<tei:p>before " + _pb("1") + "after</tei:p>")
        mark_scan_links(root)
        self.assertEqual("before ", root.find(f".//{TEI}p").text)
        self.assertEqual(["1"], _linked(root))

    def test_breaks_moved_to_the_same_words_keep_their_order(self):
        root = _tree(_pb("59", "1949 chol/x") + _pb("321", "1949 shabbat/x")
                     + "<tei:p>words</tei:p>")
        mark_scan_links(root)
        self.assertEqual(["59", "321"], [pb.get("n") for pb in root.iter(f"{TEI}pb")])

    def test_a_break_before_a_title_page_moves_onto_it(self):
        root = _tree(_pb("i") + '<tei:titlePage><tei:docTitle><tei:titlePart type="main">'
                     "Title</tei:titlePart></tei:docTitle></tei:titlePage>")
        mark_scan_links(root)
        self.assertEqual("Title", root.find(f".//{TEI}titlePart/{TEI}pb").tail)

    def test_a_break_that_no_words_follow_is_not_linked(self):
        self.assertEqual([], _marked("<tei:p>words</tei:p>" + _pb("1")))

    def test_a_break_followed_by_another_links_only_the_later_page(self):
        self.assertEqual(["2"], _marked("<tei:p>" + _pb("1") + _pb("2") + "words</tei:p>"))

    def test_two_breaks_linking_one_scan_page_link_it_once(self):
        # A unit's own break, and the break of the shared text it opens with.
        root = _tree(_transclude(
            SIDDUR + "chol/minchah",
            _pb("157", "1949 chol/minchah") + _transclude(
                "urn:x-opensiddur:text:prayer:ashrei",
                "<tei:p>" + _pb("157", "1949 chol/minchah/opening")
                + _pb("59", "1949 chol/shacharit/pesukei_dezimra") + "Ashrei</tei:p>")))
        mark_scan_links(root)
        self.assertEqual(["157"], _linked(root))

    def test_a_break_at_the_end_of_a_parallel_block_moves_to_the_next_one(self):
        body = (
            '<p:parallel><p:parallelItem role="primary" xml:lang="he">'
            "<tei:p>first</tei:p>" + _pb("1") + "</p:parallelItem>"
            '<p:parallelItem role="parallel" xml:lang="en"><tei:p>one</tei:p></p:parallelItem>'
            "</p:parallel>"
            '<p:parallel><p:parallelItem role="primary" xml:lang="he"><tei:p>second</tei:p>'
            '</p:parallelItem><p:parallelItem role="parallel" xml:lang="en">'
            "<tei:p>two</tei:p></p:parallelItem></p:parallel>")
        root = _tree(body)
        mark_scan_links(root)
        pb = root.find(f".//{TEI}pb")
        self.assertEqual(["1"], _linked(root))
        self.assertEqual("second", pb.tail)
        self.assertEqual("primary", next(pb.iterancestors(
            f"{{{PROCESSING_NAMESPACE}}}parallelItem")).get("role"))

    def test_a_break_does_not_move_into_the_other_column(self):
        body = (
            '<p:parallel><p:parallelItem role="primary" xml:lang="he">'
            "<tei:p>first</tei:p>" + _pb("1") + "</p:parallelItem>"
            '<p:parallelItem role="parallel" xml:lang="en"><tei:p>one</tei:p></p:parallelItem>'
            "</p:parallel>")
        self.assertEqual([], _marked(body))


class TestPreparation(unittest.TestCase):
    def test_breaks_are_left_alone_unless_scan_links_are_wanted(self):
        root = _tree(_pb("1") + "<tei:p>words</tei:p>")
        before = etree.tostring(root)
        prepare_compiled_tree(root)
        self.assertEqual(before, etree.tostring(root))

    def test_breaks_are_marked_when_scan_links_are_wanted(self):
        root = _tree(_pb("1") + "<tei:p>words</tei:p>")
        prepare_compiled_tree(root, scan_links=True)
        self.assertEqual(["1"], _linked(root))


if __name__ == "__main__":
    unittest.main()


class TestStayingInItsOwnText(unittest.TestCase):
    """Review findings: a break never moves into another text, or inside inline markup."""

    def test_a_break_does_not_leave_its_transclusion(self):
        root = _tree(
            _transclude("urn:a", "<tei:p>jps words" + _pb("1") + "</tei:p>")
            + _transclude("urn:b", "<tei:p>other book</tei:p>"))
        mark_scan_links(root)
        self.assertEqual([], _linked(root))
        self.assertEqual("other book", root.findall(f".//{TEI}p")[1].text)

    def test_a_break_may_move_into_a_nested_transclusion(self):
        root = _tree(_transclude(
            "urn:a", _pb("1") + _transclude("urn:b", "<tei:p>words</tei:p>")))
        mark_scan_links(root)
        self.assertEqual(["1"], _linked(root))
        self.assertIsNotNone(root.find(f".//{TEI}p/{TEI}pb"))

    def test_a_break_does_not_move_into_another_texts_parallel_block(self):
        block = ('<p:parallel><p:parallelItem role="primary" xml:lang="he">{he}'
                 '</p:parallelItem><p:parallelItem role="parallel" xml:lang="en">'
                 "<tei:p>en</tei:p></p:parallelItem></p:parallel>")
        root = _tree(
            _transclude("urn:a", block.format(he="<tei:p>first</tei:p>" + _pb("1")))
            + _transclude("urn:b", block.format(he="<tei:p>second</tei:p>")))
        mark_scan_links(root)
        self.assertEqual([], _linked(root))

    def test_a_break_before_a_parallel_block_enters_its_own_projects_column(self):
        root = _tree(
            '<p:transclude target="urn:a" p:project="en-proj">' + _pb("1")
            + '<p:parallel><p:parallelItem role="primary" xml:lang="he" p:project="he-proj">'
            "<tei:p>עברית</tei:p></p:parallelItem>"
            '<p:parallelItem role="parallel" xml:lang="en" p:project="en-proj">'
            "<tei:p>English</tei:p></p:parallelItem></p:parallel></p:transclude>")
        mark_scan_links(root)
        self.assertEqual("English", root.find(f".//{TEI}pb").tail)

    def test_a_break_does_not_move_inside_a_link(self):
        root = _tree(_pb("1") + '<tei:p><tei:ref target="https://x.example">link</tei:ref>'
                     " words</tei:p>")
        mark_scan_links(root)
        pb = root.find(f".//{TEI}pb")
        self.assertEqual(f"{TEI}p", pb.getparent().tag)
        self.assertEqual(f"{TEI}ref", pb.getnext().tag)

    def test_a_break_does_not_move_inside_a_highlight(self):
        root = _tree(_pb("1") + '<tei:p><tei:hi rend="sup">raised</tei:hi> words</tei:p>')
        mark_scan_links(root)
        self.assertEqual(f"{TEI}p", root.find(f".//{TEI}pb").getparent().tag)

    def test_a_break_opening_a_paragraph_takes_none_of_its_layout_space(self):
        root = _tree(_pb("1") + "<tei:p>\n        words</tei:p>")
        mark_scan_links(root)
        self.assertEqual("words", root.find(f".//{TEI}pb").tail)

    def test_a_printing_named_in_words_is_one_printing(self):
        # "sukkot rites" is one printing; split, "rites" alone could match no context and
        # "sukkot" could match siddur:sukkot by itself.
        shared = _transclude(
            "urn:x-opensiddur:text:prayer:x",
            "<tei:p>" + _pb("703", "1949 sukkot rites") + _pb("90", "1949 sukkot/arvit")
            + "words</tei:p>")
        self.assertEqual(["90"], _marked(_transclude(SIDDUR + "sukkot/arvit", shared)))


class TestAPageThatBeginsAtTheEndOfAText(unittest.TestCase):
    @staticmethod
    def _book(outer_project: str) -> etree.ElementBase:
        return _tree(
            f'<p:transclude target="urn:unit" p:project="{outer_project}">'
            '<p:transclude target="urn:text" p:project="birnbaum">'
            "<tei:p>words" + _pb("1") + "</tei:p></p:transclude>"
            "<tei:p>next text</tei:p></p:transclude>")

    def test_its_words_are_in_the_editions_next_text(self):
        root = self._book("birnbaum")
        mark_scan_links(root)
        self.assertEqual(["1"], _linked(root))
        self.assertEqual("next text", root.find(f".//{TEI}pb").tail)

    def test_never_in_another_books(self):
        root = self._book("jps")
        mark_scan_links(root)
        self.assertEqual([], _linked(root))
