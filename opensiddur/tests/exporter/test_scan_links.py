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

    def test_a_break_within_a_visible_rubric_keeps_its_exact_position(self):
        for kind in ("instruction", "description"):
            with self.subTest(kind=kind):
                root = _tree(f'<tei:note type="{kind}">before '
                             + _pb("2") + '<tei:hi>after</tei:hi></tei:note><tei:p>prayer</tei:p>')
                note = root.find(f".//{TEI}note")
                mark_scan_links(root)
                self.assertEqual(["2"], _linked(root))
                pb = root.find(f".//{TEI}pb")
                self.assertIs(note, pb.getparent())
                self.assertEqual(f"{TEI}hi", pb.getnext().tag)

    def test_rubric_page_break_inside_standoff_or_commentary_is_not_linked(self):
        for wrapper in ("<tei:standOff>{}</tei:standOff>",
                        '<tei:note type="commentary">{}</tei:note>'):
            with self.subTest(wrapper=wrapper):
                note = '<tei:note type="instruction">' + _pb("2") + "rubric</tei:note>"
                self.assertEqual([], _marked(wrapper.format(note)))

    def test_a_break_at_the_end_of_a_rubric_attaches_to_next_prayer(self):
        root = _tree('<tei:note type="instruction">rubric' + _pb("2")
                     + '</tei:note><tei:p>prayer</tei:p>')
        mark_scan_links(root)
        pb = root.find(f".//{TEI}pb")
        self.assertEqual(["2"], _linked(root))
        self.assertEqual(f"{TEI}p", pb.getparent().tag)
        self.assertEqual("prayer", pb.tail)

    def test_ordinary_note_words_do_not_keep_a_rubric_break(self):
        root = _tree('<tei:note type="instruction">rubric' + _pb("2")
                     + '<tei:note type="commentary">annotation</tei:note></tei:note>'
                     + '<tei:p>prayer</tei:p>')
        mark_scan_links(root)
        self.assertEqual(f"{TEI}p", root.find(f".//{TEI}pb").getparent().tag)

    def test_a_break_cannot_move_past_a_later_page_inside_a_rubric(self):
        root = _tree(_pb("1") + '<tei:note type="instruction">rubric '
                     + _pb("2") + 'continued</tei:note><tei:p>prayer</tei:p>')
        first = root.find(f".//{TEI}pb")
        parent = first.getparent()
        mark_scan_links(root)
        self.assertEqual(["1", "2"], _linked(root))
        self.assertIs(parent, first.getparent())

    def test_a_rubric_break_stays_a_barrier_after_it_moves_to_next_prayer(self):
        root = _tree(_pb("1") + '<tei:note type="instruction">rubric '
                     + _pb("2") + '</tei:note><tei:p>prayer</tei:p>')
        mark_scan_links(root)
        self.assertEqual(["1", "2"], _linked(root))

    def test_an_edition_with_only_a_rubric_break_needs_no_ordinary_context(self):
        self.assertEqual(["rubric"], _marked(
            '<tei:note type="instruction">' + _pb("rubric", "1949 shabbat/opening")
            + 'rubric words</tei:note>'))

    def test_rubric_uses_all_its_groups_printings_when_an_earlier_page_selects_one(self):
        inner = _transclude(
            "urn:prayer", '<tei:note type="instruction">'
            + _pb("r", "1949 chol/shacharit/b") + 'rubric</tei:note><tei:p>'
            + _pb("s", "1949 chol/shacharit/b") + _pb("m", "1949 chol/minchah/a")
            + 'words</tei:p>')
        body = _transclude("urn:book", '<tei:p>' + _pb("e", "1949 chol/minchah/a")
                           + 'earlier</tei:p>' + inner)
        self.assertEqual(["e", "m"], _marked(body))

    def test_many_transclusions_keep_their_own_printing_groups_alive(self):
        body = "".join(
            _transclude(f"urn:prayer:{n}", '<tei:p>' + _pb(f"p{n}") + 'prayer</tei:p>'
                        + '<tei:note type="instruction">' + _pb(f"r{n}")
                        + 'rubric</tei:note>') for n in range(40))
        self.assertEqual([value for n in range(40) for value in (f"p{n}", f"r{n}")],
                         _marked(body))

    def test_rubric_printing_never_changes_a_later_groups_printing_choice(self):
        shared = _transclude("urn:prayer", '<tei:p>' + _pb("a", "1949 chol/opening")
                            + _pb("b", "1949 shabbat/opening") + 'words</tei:p>')
        rubric = ('<tei:note type="instruction">' + _pb("rubric", "1949 shabbat/opening")
                  + 'rubric words</tei:note>')
        self.assertEqual(["a", "b"], _marked(shared))
        self.assertEqual(["rubric", "a", "b"], _marked(rubric + shared))

    def test_another_columns_rubric_break_does_not_pin_this_columns_break(self):
        body = ('<p:parallel><p:parallelItem role="primary">' + _pb("1")
                + '</p:parallelItem><p:parallelItem role="parallel">'
                + '<tei:note type="instruction">before ' + _pb("2")
                + 'after</tei:note></p:parallelItem></p:parallel>'
                + '<p:parallel><p:parallelItem role="primary"><tei:p>prayer</tei:p>'
                + '</p:parallelItem></p:parallel>')
        root = _tree(body)
        mark_scan_links(root)
        first = next(pb for pb in root.iter(f"{TEI}pb") if pb.get("n") == "1")
        self.assertEqual(f"{TEI}p", first.getparent().tag)

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


class TestTheContextTheEditionPrints(unittest.TestCase):
    """Where the edition prints the unit the book sets a text in, only that printing links."""

    @staticmethod
    def _minchah(shared: str) -> str:
        # The unit has breaks of its own printing, so the edition prints it.
        return _transclude(SIDDUR + "chol/minchah/amidah",
                           "<tei:p>" + _pb("161", "1949 chol/minchah/amidah") + "Avot</tei:p>"
                           + shared)

    def test_a_text_with_only_another_printings_breaks_links_none(self):
        shared = _transclude("urn:x-opensiddur:text:prayer:gevurot",
                             "<tei:p>" + _pb("83", "1949 chol/shacharit/amidah")
                             + "Atah gibor</tei:p>")
        self.assertEqual(["161"], _marked(self._minchah(shared)))

    def test_a_text_with_two_other_printings_links_neither(self):
        shared = _transclude("urn:x-opensiddur:text:prayer:gevurot",
                             "<tei:p>" + _pb("83", "1949 chol/shacharit/amidah")
                             + _pb("203", "1949 chol/arvit/amidah") + "Atah gibor</tei:p>")
        self.assertEqual(["161"], _marked(self._minchah(shared)))

    def test_its_own_printing_still_links(self):
        shared = _transclude("urn:x-opensiddur:text:prayer:gevurot",
                             "<tei:p>" + _pb("83", "1949 chol/shacharit/amidah")
                             + _pb("162", "1949 chol/minchah/amidah") + "Atah gibor</tei:p>")
        self.assertEqual(["161", "162"], _marked(self._minchah(shared)))

    def test_a_context_the_edition_never_prints_falls_back_to_the_nearest(self):
        shared = _transclude("urn:x-opensiddur:text:prayer:gevurot",
                             "<tei:p>" + _pb("83", "1949 chol/shacharit/amidah")
                             + "Atah gibor</tei:p>")
        self.assertEqual(["83"], _marked(_transclude(SIDDUR + "chol/maariv_nusach_x", shared)))

    def test_an_earlier_break_never_takes_a_texts_links_away(self):
        # The book arranges the text its own way (the edition never prints expanded/morning);
        # an earlier break of another printing must not leave the text without links.
        body = _transclude(
            SIDDUR + "expanded/morning",
            "<tei:p>" + _pb("320", "1949 shabbat/shacharit/pesukei_dezimra") + "Before</tei:p>"
            + _transclude("urn:x-opensiddur:text:prayer:yehi_khevod",
                          "<tei:p>" + _pb("53", "1949 chol/shacharit/pesukei_dezimra")
                          + "Yehi khevod</tei:p>"))
        self.assertEqual(["320", "53"], _marked(body))

    def test_printings_in_words_link_where_a_one_word_printing_matches_the_unit(self):
        # "regalim" is a printing in words, not the path of siddur:regalim/musaf; the
        # festival musaf's own breaks, in words too, keep their links.
        body = (
            _transclude(SIDDUR + "regalim/hallel",
                        "<tei:p>" + _pb("600", "1949 regalim") + "Hallel</tei:p>")
            + _transclude(SIDDUR + "regalim/musaf",
                          "<tei:p>" + _pb("615", "1949 festival musaf") + "Musaf</tei:p>"))
        self.assertEqual(["600", "615"], _marked(body))


class TestPageChanges(unittest.TestCase):
    def test_one_link_per_page_across_paragraphs_and_transclusions(self):
        root = _tree(_transclude("urn:a", "<tei:p>" + _pb("1") + "first</tei:p>")
                     + _transclude("urn:b", "<tei:p>" + _pb("1") + "second</tei:p>")
                     + "<tei:p>" + _pb("2") + "third</tei:p>")
        before = "".join(root.itertext())
        mark_scan_links(root)
        self.assertEqual(_linked(root), ["1", "2"])
        self.assertEqual(len(list(root.iter(TEI+"pb"))), 3)
        self.assertEqual("".join(root.itertext()), before)

    def test_returning_to_an_earlier_page_needs_its_link_again(self):
        self.assertEqual(_marked("".join("<tei:p>" + _pb(n) + "words</tei:p>"
                                        for n in ("1", "2", "1"))), ["1", "2", "1"])

    def test_scan_identity_overrides_repeated_printed_page_label(self):
        body = "<tei:p>" + _pb("1") + "first</tei:p><tei:p>" + _pb("2").replace('n="2"', 'n="1"') + "second</tei:p>"
        self.assertEqual(_marked(body), ["1", "1"])

    def test_parallel_columns_have_independent_page_states(self):
        def item(role, page):
            return f'<p:parallelItem role="{role}"><tei:p>' + _pb(page) + 'words</tei:p></p:parallelItem>'
        root = _tree('<p:parallel>' + item('primary', '1') + item('secondary', '1')
                     + item('primary', '1') + item('secondary', '2') + '</p:parallel>')
        mark_scan_links(root)
        self.assertEqual(_linked(root), ['1', '1', '2'])

    def test_a_conditional_link_does_not_hide_an_unconditional_link(self):
        j = 'http://jewishliturgy.org/ns/jlptei/2'
        body = f'<j:conditional xmlns:j="{j}" xml:id="optional"/>'
        body += '<tei:p>' + _pb('1') + 'optional words</tei:p>'
        body += f'<j:endConditional xmlns:j="{j}" target="#optional"/>'
        body += '<tei:p>' + _pb('1') + 'required words</tei:p>'
        self.assertEqual(_marked(body), ['1', '1'])

    def test_a_conditional_page_change_requires_a_link_after_the_scope(self):
        j = 'http://jewishliturgy.org/ns/jlptei/2'
        body = '<tei:p>' + _pb('1') + 'first</tei:p>'
        body += f'<j:conditional xmlns:j="{j}" xml:id="optional"/>'
        body += '<tei:p>' + _pb('2') + 'optional</tei:p>'
        body += f'<j:endConditional xmlns:j="{j}" target="#optional"/>'
        body += '<tei:p>' + _pb('1') + 'last</tei:p>'
        self.assertEqual(_marked(body), ['1', '2', '1'])

    def test_same_page_through_a_conditional_is_not_a_page_change(self):
        j = 'http://jewishliturgy.org/ns/jlptei/2'
        body = '<tei:p>' + _pb('1') + 'first</tei:p>'
        body += f'<j:conditional xmlns:j="{j}" xml:id="optional"/>'
        body += '<tei:p>' + _pb('1') + 'optional</tei:p>'
        body += f'<j:endConditional xmlns:j="{j}" target="#optional"/>'
        body += '<tei:p>' + _pb('1') + 'last</tei:p>'
        self.assertEqual(_marked(body), ['1'])

    def test_optional_rubric_cannot_hide_required_page_link(self):
        j = 'http://jewishliturgy.org/ns/jlptei/2'
        for condition in ('', f'<j:condition xmlns:j="{j}"/>'):
            with self.subTest(condition=bool(condition)):
                root = _tree('<tei:note type="instruction">' + condition + _pb('1')
                             + 'optional instruction</tei:note><tei:p>' + _pb('1') + 'required</tei:p>')
                mark_scan_links(root)
                self.assertEqual(_linked(root), ['1', '1'])

    def test_implicit_conditional_ends_at_parent_end_with_or_without_id(self):
        j = 'http://jewishliturgy.org/ns/jlptei/2'
        for identifier in ('', ' xml:id="optional"'):
            with self.subTest(identifier=identifier):
                body = f'<tei:div><j:conditional xmlns:j="{j}"{identifier}/>'
                body += '<tei:p>' + _pb('1') + 'optional</tei:p></tei:div>'
                body += '<tei:p>' + _pb('1') + 'required</tei:p>'
                self.assertEqual(_marked(body), ['1', '1'])

    def test_unknown_end_marker_does_not_hide_a_link(self):
        j = 'http://jewishliturgy.org/ns/jlptei/2'
        body = '<tei:p>' + _pb('1') + 'first</tei:p>'
        body += f'<j:endConditional xmlns:j="{j}" target="#absent"/>'
        body += '<tei:p>' + _pb('1') + 'after unmatched end</tei:p>'
        self.assertEqual(_marked(body), ['1', '1'])

    def test_nested_conditionals_preserve_both_paths(self):
        j = 'http://jewishliturgy.org/ns/jlptei/2'
        def start(key):
            return f'<j:conditional xmlns:j="{j}" xml:id="{key}"/>'
        def end(key):
            return f'<j:endConditional xmlns:j="{j}" target="#{key}"/>'
        body = '<tei:p>' + _pb('1') + 'first</tei:p>' + start('outer')
        body += '<tei:p>' + _pb('2') + 'outer</tei:p>' + start('inner')
        body += '<tei:p>' + _pb('3') + 'inner</tei:p>' + end('inner') + end('outer')
        body += '<tei:p>' + _pb('1') + 'last</tei:p>'
        self.assertEqual(_marked(body), ['1', '2', '3', '1'])

    def test_editions_keep_independent_page_states(self):
        body = '<tei:p>' + _pb('1', '1949') + 'first</tei:p>'
        body += '<tei:p>' + _pb('2', '1965') + 'second</tei:p>'
        body += '<tei:p>' + _pb('1', '1949') + 'still first edition page</tei:p>'
        self.assertEqual(_marked(body), ['1', '2'])

    def test_project_columns_and_shared_wrapper_do_not_share_page_state(self):
        for projects in (('he-project', 'en-project'), (None, None)):
            with self.subTest(projects=projects):
                def item(role, project):
                    attr = f' p:project="{project}"' if project else ''
                    return f'<p:parallelItem role="{role}"{attr}><tei:p>' + _pb('1') + 'words</tei:p></p:parallelItem>'
                body = '<p:transclude target="urn:book" p:project="he-project"><p:parallel>'
                body += ''.join(item(role, project) for _ in range(2)
                                for role, project in zip(('primary', 'secondary'), projects))
                body += '</p:parallel></p:transclude>'
                self.assertEqual(_marked(body), ['1', '1'])

    def test_attached_duplicate_remains_in_tree_without_link_mark(self):
        root = _tree('<tei:p>' + _pb('1') + 'first</tei:p>' + _pb('1') + '<tei:p>second</tei:p>')
        mark_scan_links(root)
        pages = list(root.iter(TEI+'pb'))
        self.assertEqual(_linked(root), ['1'])
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[1].getparent().tag, TEI+'p')
        self.assertEqual(pages[1].tail, 'second')
        self.assertIsNone(pages[1].get(SCAN_LINK))

    def test_electronic_compile_keeps_conditional_pair_through_transclusion(self):
        import tempfile
        from pathlib import Path
        from opensiddur.exporter.linear import LinearData
        from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
        from opensiddur.exporter.refdb import ReferenceDatabase
        j = 'http://jewishliturgy.org/ns/jlptei/2'
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base/'sample'
            project.mkdir()
            wrapper = f'<tei:TEI xmlns:tei="{TEI_NS}" xmlns:j="{j}" xml:lang="he"><tei:text><tei:body>{{}}</tei:body></tei:text></tei:TEI>'
            (project/'index.xml').write_text(wrapper.format('<j:transclude target="urn:x-opensiddur:text:prayer:sample"/>'), encoding='utf-8')
            body = '<j:conditional xml:id="optional"><tei:fs type="opensiddur:holiday-aggregate"><tei:f name="shabbat"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>'
            body += '<tei:p>' + _pb('1') + 'optional</tei:p><j:endConditional target="#optional"/>'
            body += '<tei:p>' + _pb('1') + 'required</tei:p>'
            (project/'part.xml').write_text(wrapper.format('<tei:div corresp="urn:x-opensiddur:text:prayer:sample">'+body+'</tei:div>'), encoding='utf-8')
            data = LinearData(defer_reader_settings=True, project_priority=["sample"])
            data.xml_cache.base_path = base
            with ReferenceDatabase(base/'refs.db') as db:
                db.index_project('sample', base)
                result = ExternalCompilerProcessor('sample', 'index.xml', linear_data=data, reference_database=db).process()[0]
            start = next(result.iter('{'+j+'}conditional'))
            end = next(result.iter('{'+j+'}endConditional'))
            self.assertEqual(end.get('target'), '#'+start.get('{http://www.w3.org/XML/1998/namespace}id'))
            mark_scan_links(result)
            self.assertEqual(_linked(result), ['1', '1'])
