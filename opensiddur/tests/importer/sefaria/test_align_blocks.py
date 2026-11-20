import unittest

from opensiddur.importer.sefaria.align import (
    AlignmentError,
    LeafDecision,
    align_leaf,
    align_work,
)
from opensiddur.importer.sefaria.blocks import Heading, Rubric, TextBlock, divide, split_block
from opensiddur.importer.sefaria.markup import plain_text
from opensiddur.importer.sefaria.source import Leaf, segments_hash


def leaf(he, en, path="A"):
    return Leaf((path,), ((path, path),), tuple(he), tuple(en))


def pairs_of(segments):
    return align_leaf(leaf([h for h, _ in segments], [e for _, e in segments])).pairs


class TestAlign(unittest.TestCase):
    def test_equal_counts_pair_one_to_one(self):
        result = align_leaf(leaf(["א", "ב"], ["a", "b"]))
        self.assertEqual(result.policy, "equal")
        self.assertEqual([(p.he_index, p.en_index) for p in result.pairs], [(1, 1), (2, 2)])

    def test_trailing_english_rubrics_stand_alone(self):
        result = align_leaf(leaf(["א"], ["a", "<small>Kaddish.</small>", "<small>More.</small>"]))
        self.assertEqual(result.policy, "trailing")
        self.assertEqual([(p.he_index, p.en_index) for p in result.pairs], [(1, 1), (None, 2), (None, 3)])

    def test_trailing_untranslated_hebrew_stands_alone(self):
        result = align_leaf(leaf(["א", "ב"], ["a"]))
        self.assertEqual([(p.he_index, p.en_index) for p in result.pairs], [(1, 1), (2, None)])

    def test_a_long_untranslated_run_needs_a_decision(self):
        with self.assertRaisesRegex(AlignmentError, "record a decision"):
            align_leaf(leaf(["א", "ב", "ג", "ד", "ה"], ["a"]))

    def test_other_mismatch_needs_a_decision(self):
        with self.assertRaisesRegex(AlignmentError, "record a decision"):
            align_leaf(leaf(["א"], ["a", "b plain"]))

    def test_a_decision_sets_segments_aside(self):
        he, en = ["א", "ב"], ["a", "x", "b"]
        decision = LeafDecision(segments_hash(tuple(he)), segments_hash(tuple(en)), frozenset(), frozenset({2}))
        result = align_leaf(leaf(he, en), decision)
        self.assertEqual(result.policy, "decision")
        self.assertEqual([(p.he_index, p.en_index) for p in result.pairs], [(1, 1), (None, 2), (2, 3)])

    def test_a_decision_names_the_segments_that_open_texts(self):
        he, en = ["<b>א</b> א", "ב", "ג"], ["a"]
        decision = LeafDecision(segments_hash(tuple(he)), segments_hash(tuple(en)),
                                frozenset({2, 3}), frozenset(), opens=frozenset({3}))
        result = align_leaf(leaf(he, en), decision)
        self.assertEqual(result.opens, frozenset({3}))
        # untranslated texts with no bold opening run on, unless the decision opens one
        self.assertEqual([len(b.phrases) for b in divide(result.pairs)], [3])
        self.assertEqual([len(b.phrases) for b in divide(result.pairs, opens=result.opens)], [2, 1])

    def test_opens_must_name_a_segment(self):
        he, en = ["א", "ב"], ["a"]
        decision = LeafDecision(segments_hash(tuple(he)), segments_hash(tuple(en)),
                                frozenset({2}), frozenset(), opens=frozenset({5}))
        with self.assertRaisesRegex(AlignmentError, "opens names segment 5"):
            align_leaf(leaf(he, en), decision)

    def test_a_decision_lapses_when_the_leaf_changes(self):
        decision = LeafDecision("old", "old", frozenset(), frozenset({2}))
        with self.assertRaisesRegex(AlignmentError, "earlier version"):
            align_leaf(leaf(["א"], ["a", "b"]), decision)

    def test_a_decision_that_does_not_balance_is_an_error(self):
        he, en = ["א"], ["a", "b", "c"]
        decision = LeafDecision(segments_hash(tuple(he)), segments_hash(tuple(en)), frozenset(), frozenset({2}))
        with self.assertRaisesRegex(AlignmentError, "remain to pair"):
            align_leaf(leaf(he, en), decision)

    def test_align_work_reports_every_problem(self):
        leaves = (leaf(["א"], ["a", "b plain"], "A"), leaf(["א"], ["a", "b plain"], "B"))
        decisions = {"w": {"Gone": LeafDecision("", "", frozenset(), frozenset())}}
        with self.assertRaises(AlignmentError) as caught:
            align_work("w", leaves, decisions)
        message = str(caught.exception)
        self.assertIn("A:", message)
        self.assertIn("B:", message)
        self.assertIn("Gone: a decision for a leaf the work no longer has", message)


class TestDivide(unittest.TestCase):
    def test_rubrics_between_texts_and_bold_openings(self):
        items = divide(pairs_of([
            ("", "<small><i>On waking:</i></small>"),
            ("<b>מוֹדֶה</b> אֲנִי", "I thank"),
            ("מֶֽלֶךְ", "King"),
            ("", "<small><i>After washing:</i></small>"),
            ("<b>רֵאשִׁית</b> חָכְמָה", "The beginning"),
        ]))
        self.assertEqual([type(i) for i in items], [Rubric, TextBlock, Rubric, TextBlock])
        self.assertEqual(len(items[1].phrases), 2)
        self.assertEqual(items[3].first_index, 5)

    def test_a_rubric_inside_a_text_stays_in_it(self):
        items = divide(pairs_of([
            ("<b>מוֹדֶה</b> אֲנִי", "I thank"),
            ("", "<small>(bow)</small>"),
            ("מֶֽלֶךְ", "King"),
        ]))
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0].pairs), 3)

    def test_a_heading_opens_a_text_and_the_bold_after_it_continues(self):
        items = divide(pairs_of([
            ("<b>אבות</b>", "<b>FOREFATHERS</b>"),
            ("<b>בָּרוּךְ</b> אַתָּה", "Blessed"),
            ("<b>גבורות</b>", "<b>MIGHT</b>"),
            ("<b>אַתָּה</b> גִבּוֹר", "You are mighty"),
        ]))
        self.assertEqual([type(i) for i in items], [TextBlock, TextBlock])
        self.assertEqual(plain_text(items[0].head.he), "אבות")
        self.assertEqual(len(items[0].phrases), 1)

    def test_lines_printed_whole_in_bold_continue_each_other(self):
        items = divide(pairs_of([
            ("<b>שְׁמַע יִשְׂרָאֵל</b>", "<b>Hear Israel</b>"),
            ("<b>יְהֹוָה אֶחָד:</b>", "<b>Adonoy is One</b>"),
        ]))
        self.assertEqual(len(items), 1)

    def test_a_bold_opening_after_a_rubric_opens_a_text(self):
        items = divide(pairs_of([
            ("<b>בָּרוּךְ יְהֹוָה הַמְבֹרָךְ</b>", "<b>Blessed is Adonoy</b>"),
            ("", "<small>Continue:</small>"),
            ("<b>אַהֲבָה</b> רַבָּה", "With great love"),
        ]))
        self.assertEqual([type(i) for i in items], [TextBlock, Rubric, TextBlock])

    def test_a_placeholder_label_is_part_of_the_text(self):
        items = divide(pairs_of([
            ("<b>רְפָאֵֽנוּ</b> יְהֹוָה", "Heal us"),
            ("<b>(פלוני)</b>", "(name)"),
            ("בְּתוֹךְ", "among"),
        ]))
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0].phrases), 3)

    def test_a_response_label_is_part_of_the_text(self):
        items = divide(pairs_of([
            ("<b>לִבְרָכָה</b> וְלֹא לִקְלָלָה:", "For blessing and not for curse."),
            ("<small>אמן</small>", "Amein."),
            ("לְחַיִּים וְלֹא לַמָּֽוֶת:", "For life and not for death."),
        ]))
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0].phrases), 3)

    def test_a_condition_label_is_a_rubric_inside_the_text(self):
        segments = [
            ("<b>וְאֶת</b> מוּסַף יוֹם", "And the Musaf-offering of:"),
            ("<b>לפסח</b>", "<b>On Pesach</b>"),
            ("חַג הַמַּצּוֹת הַזֶּה", "this Festival of Matzos"),
        ]
        # without the conditions table, a bold label is a heading that opens a new text
        self.assertEqual(len(divide(pairs_of(segments))), 2)
        items = divide(pairs_of(segments), lambda pair: plain_text(pair.he) == "לפסח")
        self.assertEqual([type(i) for i in items], [TextBlock])
        self.assertEqual(len(items[0].phrases), 2)

    def test_a_heading_with_no_text_is_a_heading(self):
        items = divide(pairs_of([("<b>אבות</b>", "<b>FOREFATHERS</b>"), ("", "<small>Say:</small>")]))
        self.assertEqual([type(i) for i in items], [Heading, Rubric])

    def test_split_block_gives_rubrics_to_the_second_text(self):
        (block,) = divide(pairs_of([
            ("<b>מוֹדֶה</b> אֲנִי", "I thank"),
            ("", "<small>(bow)</small>"),
            ("מֶֽלֶךְ", "King"),
        ]))
        first, rest = split_block(block, 1)
        self.assertEqual(len(first.pairs), 1)
        self.assertEqual(len(rest.pairs), 2)
        self.assertEqual(rest.first_index, 3)  # the Hebrew index of its first phrase
        with self.assertRaises(ValueError):
            split_block(block, 0)


if __name__ == "__main__":
    unittest.main()
