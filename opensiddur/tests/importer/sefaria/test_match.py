import tempfile
import unittest
from pathlib import Path

from opensiddur.common.validate_names import Spellings
from opensiddur.importer.sefaria.align import align_leaf
from opensiddur.importer.sefaria.blocks import TextBlock, divide
from opensiddur.importer.sefaria.match import (
    TextRecord,
    decide_work,
    load_records,
    mint,
    save_records,
)
from opensiddur.importer.sefaria.phrases import skeleton
from opensiddur.importer.sefaria.source import Leaf
from opensiddur.importer.util.incipit import IncipitIndex, words

T = "urn:x-opensiddur:text:"
NO_SPELLINGS = Spellings(frozenset(), {})

MODEH = ["<b>מוֹדֶה אֲנִי</b> לְפָנֶֽיךָ", "מֶֽלֶךְ חַי וְקַיָּם", "שֶׁהֶחֱזַֽרְתָּ בִּי נִשְׁמָתִי בְּחֶמְלָה",
         "רַבָּה אֱמוּנָתֶֽךָ"]
UNKNOWN = ["<b>זֶה טֶקְסְט</b> חָדָשׁ לְגַמְרֵי", "שֶׁאֵין לוֹ מָקוֹר בָּאוֹסֶף"]
PART_A = ["<b>יִתְגַּדַּל וְיִתְקַדַּשׁ</b> שְׁמֵהּ רַבָּא", "בְּעָלְמָא דִּי בְרָא כִרְעוּתֵהּ"]
PART_B = ["יְהֵא שְׁלָמָא רַבָּא מִן שְׁמַיָּא", "וְחַיִּים עָלֵינוּ וְעַל כָּל יִשְׂרָאֵל"]


def items(*hebrew: str):
    segments = list(hebrew)
    return divide(align_leaf(Leaf(("L",), (("L", "L"),), tuple(segments), tuple("e" for _ in segments))).pairs)


def index_of(**texts) -> IncipitIndex:
    index = IncipitIndex()
    for urn, text in texts.items():
        index.add(T + urn.replace("__", "/").replace("_c_", ":"), words(text))
    return index


def decide(leaves, index=None, records=None, phrases=None):
    return decide_work("w", leaves, index or IncipitIndex(), records or {}, set(),
                       recorded_phrases=phrases, spellings=NO_SPELLINGS)


class TestDecide(unittest.TestCase):
    def test_an_existing_text_is_reused(self):
        index = IncipitIndex()
        index.add(T + "prayer:modeh_ani", words(" ".join(MODEH)))
        outcome = decide([("L", items(*MODEH))], index)
        (record,) = outcome.decided
        self.assertEqual((record.kind, record.urn), ("existing", T + "prayer:modeh_ani"))
        self.assertEqual(record.block, 1)

    def test_an_unknown_text_is_minted_from_its_incipit(self):
        outcome = decide([("L", items(*UNKNOWN))])
        (record,) = outcome.decided
        self.assertEqual(record.kind, "new")
        self.assertEqual(record.urn, T + "prayer:zeh_teqst_chadash")

    def test_a_later_printing_transcludes_the_first(self):
        outcome = decide([("A", items(*MODEH)), ("B", items(*MODEH))])
        first, second = outcome.decided
        self.assertEqual(second.kind, "repeat")
        self.assertEqual(second.urn, first.urn)

    def test_a_later_printing_that_runs_on_is_cut_where_the_first_ends(self):
        later = items(*MODEH, *UNKNOWN[1:])
        outcome = decide([("A", items(*MODEH)), ("B", later)])
        kinds = [(r.leaf, r.kind) for r in outcome.decided]
        self.assertEqual(kinds, [("A", "new"), ("B", "repeat"), ("B", "new")])
        self.assertEqual(len([i for i in later if isinstance(i, TextBlock)]), 2)

    def test_a_different_text_with_the_same_opening_is_its_own(self):
        other = [MODEH[0], "דָּבָר אַחֵר לְגַמְרֵי בְּלִי שׁוּם קֶשֶׁר", "וְעוֹד דָּבָר שׁוֹנֶה מְאֹד"]
        outcome = decide([("A", items(*MODEH)), ("B", items(*other))])
        first, second = outcome.decided
        self.assertEqual(second.kind, "new")
        self.assertNotEqual(second.urn, first.urn)

    def test_a_block_that_runs_into_another_part_is_cut_there(self):
        index = IncipitIndex()
        index.add(T + "prayer:kaddish/x/a", words(" ".join(PART_A)))
        index.add(T + "prayer:kaddish/x/b", words(" ".join(PART_B)))
        outcome = decide([("L", items(*PART_A, *PART_B))], index)
        self.assertEqual([r.urn for r in outcome.decided], [T + "prayer:kaddish/x/a", T + "prayer:kaddish/x/b"])

    def test_the_opening_part_moves_up_to_the_whole_encoded_text(self):
        index = IncipitIndex()
        index.add(T + "prayer:kaddish/x", words(" ".join(PART_A + PART_B)))
        index.add(T + "prayer:kaddish/x/a", words(" ".join(PART_A)))
        index.add(T + "prayer:kaddish/x/b", words(" ".join(PART_B)))
        outcome = decide([("L", items(*PART_A, *PART_B))], index)
        self.assertEqual([r.urn for r in outcome.decided], [T + "prayer:kaddish/x"])

    def test_scripture_opened_mid_chapter_is_liturgy(self):
        index = IncipitIndex()
        index.add(T + "bible:psalms/30/5", words(" ".join(UNKNOWN)))
        outcome = decide([("L", items(*UNKNOWN))], index)
        self.assertEqual(outcome.decided[0].kind, "new")

    def test_a_chapter_opened_at_its_first_verse_is_the_chapter(self):
        index = IncipitIndex()
        index.add(T + "bible:psalms/30", words(" ".join(UNKNOWN)))
        index.add(T + "bible:psalms/30/1", words(UNKNOWN[0]))
        index.add(T + "bible:psalms/30/2", words(UNKNOWN[1]))
        outcome = decide([("L", items(*UNKNOWN))], index)
        self.assertEqual(outcome.decided[0].urn, T + "bible:psalms/30")

    def test_records_are_sticky_and_lapse_when_the_text_changes(self):
        first = decide([("L", items(*MODEH))])
        again = decide([("L", items(*MODEH))], records=first.records)
        self.assertEqual(again.decided, [])
        changed = decide([("L", items(MODEH[0], "מֶֽלֶךְ מְשֻׁנֶּה לְגַמְרֵי", *MODEH[2:]))], records=first.records)
        self.assertEqual(len(changed.lapsed), 1)
        self.assertEqual(len(changed.decided), 1)

    def test_a_text_whose_words_changed_keeps_its_urn(self):
        first = decide([("L", items(*UNKNOWN))])
        corrected = [UNKNOWN[0], "שֶׁאֵין לוֹ מָקוֹר בָּאוֹסֶף הַזֶּה"]
        again = decide([("L", items(*corrected))], records=first.records)
        self.assertEqual(again.decided[0].urn, first.decided[0].urn)
        self.assertEqual(again.lapsed, [first.decided[0]])

    def test_a_short_text_printed_again_is_a_repeat(self):
        short = ["<b>אָמֵן</b> סֶלָה"]
        outcome = decide([("A", items(*short)), ("B", items(*short))])
        self.assertEqual([r.kind for r in outcome.decided], ["new", "repeat"])

    def test_a_block_no_longer_printed_lapses(self):
        first = decide([("L", items(*MODEH))])
        gone = decide([("M", items(*UNKNOWN))], records=first.records)
        self.assertIn(first.decided[0], gone.lapsed)
        self.assertNotIn(first.decided[0].key, gone.records)

    def test_phrases_follow_an_earlier_volume(self):
        recorded = {"zeh_teqst_chadash": {1: skeleton(UNKNOWN[1]), 2: "something else entirely"}}
        outcome = decide([("L", items(*UNKNOWN))], phrases=recorded)
        self.assertEqual(outcome.decided[0].phrases, [3, 1])


class TestReviewCases(unittest.TestCase):
    def test_a_rerun_replays_the_cuts_and_decides_nothing(self):
        index = IncipitIndex()
        index.add(T + "prayer:kaddish/x/a", words(" ".join(PART_A)))
        index.add(T + "prayer:kaddish/x/b", words(" ".join(PART_B)))
        first = decide([("L", items(*PART_A, *PART_B))], index)
        self.assertEqual(len(first.decided), 2)
        leaf = items(*PART_A, *PART_B)
        again = decide([("L", leaf)], index, records=first.records)
        self.assertEqual((again.decided, again.lapsed), ([], []))
        self.assertEqual(len([i for i in leaf if isinstance(i, TextBlock)]), 2)

    def test_a_first_printing_that_ran_on_is_cut_where_the_later_ends(self):
        first_leaf = items(*MODEH, *UNKNOWN[1:])
        outcome = decide([("A", first_leaf), ("B", items(*MODEH))])
        self.assertEqual(len([i for i in first_leaf if isinstance(i, TextBlock)]), 2)
        a = [r for r in outcome.records.values() if r.leaf == "A"]
        b = [r for r in outcome.records.values() if r.leaf == "B"]
        self.assertEqual([r.kind for r in b], ["repeat"])
        self.assertEqual(b[0].urn, min(a, key=lambda r: r.block).urn)
        self.assertEqual(len(a), 2)

    def test_a_maqaf_does_not_hide_an_existing_text(self):
        index = IncipitIndex()
        index.add(T + "prayer:amidah/david", words("אֶת צֶמַח דָּוִד עַבְדְּךָ מְהֵרָה תַצְמִיחַ"))
        outcome = decide([("L", items("<b>אֶת־צֶֽמַח</b> דָּוִד עַבְדְּךָ", "מְהֵרָה תַצְמִיחַ"))], index)
        self.assertEqual(outcome.decided[0].urn, T + "prayer:amidah/david")

    def test_one_part_does_not_claim_the_whole(self):
        # The parent's opening is the first part's, but the block holds only that part and one
        # of three others: it stays the part.
        index = IncipitIndex()
        c = ["וְעוֹד חֵלֶק שְׁלִישִׁי שֶׁל הַתְּפִלָּה הַזֹּאת", "וְחֵלֶק רְבִיעִי אַחֲרוֹן בַּתְּפִלָּה הַזֹּאת"]
        index.add(T + "prayer:kaddish/x", words(" ".join(PART_A + PART_B + c)))
        index.add(T + "prayer:kaddish/x/a", words(" ".join(PART_A)))
        index.add(T + "prayer:kaddish/x/b", words(" ".join(PART_B)))
        index.add(T + "prayer:kaddish/x/c", words(c[0]))
        index.add(T + "prayer:kaddish/x/d", words(c[1]))
        outcome = decide([("L", items(*PART_A, *PART_B))], index)
        self.assertEqual(outcome.decided[0].urn, T + "prayer:kaddish/x/a")


class TestMint(unittest.TestCase):
    def test_a_blessing_is_named_after_its_formulas(self):
        text = "בָּרוּךְ אַתָּה יְהֹוָה אֱלֹהֵֽינוּ מֶֽלֶךְ הָעוֹלָם אֲשֶׁר קִדְּשָֽׁנוּ בְּמִצְוֹתָיו וְצִוָּֽנוּ עַל מִצְוַת צִיצִית"
        self.assertEqual(mint(text, set(), NO_SPELLINGS), T + "prayer:al_mitzvat_tzitzit")

    def test_maqaf_and_stray_punctuation_do_not_hide_the_formula(self):
        text = "בָּרוּךְ אַתָּה יְהֹוָה , אֱלֹהֵֽינוּ מֶֽלֶךְ־הָעוֹלָם הַמּוֹצִיא לֶֽחֶם מִן הָאָֽרֶץ"
        self.assertEqual(mint(text, set(), NO_SPELLINGS), T + "prayer:hamotzi_lechem_min")

    def test_a_taken_name_grows(self):
        text = "זֶה טֶקְסְט חָדָשׁ לְגַמְרֵי"
        self.assertEqual(mint(text, {T + "prayer:zeh_teqst_chadash"}, NO_SPELLINGS),
                         T + "prayer:zeh_teqst_chadash_legamrei")

    def test_unpointed_and_parenthesized_words_are_not_the_name(self):
        text = "(בעשי\"ת) זֶה טֶקְסְט חָדָשׁ"
        self.assertEqual(mint(text, set(), NO_SPELLINGS), T + "prayer:zeh_teqst_chadash")


class TestRecords(unittest.TestCase):
    def test_round_trip(self):
        record = TextRecord("w", "A / B", 3, T + "prayer:x", "new", "אבג", "h", ["why"], [2, 1])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "urns.jsonl"
            save_records({record.key: record}, path)
            self.assertEqual(load_records(path), {record.key: record})


if __name__ == "__main__":
    unittest.main()
