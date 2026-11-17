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

    def test_a_rerun_replays_a_cut_before_a_short_text(self):
        index = IncipitIndex()
        index.add(T + "prayer:kaddish/x/a", words(" ".join(PART_A)))
        index.add(T + "prayer:kaddish/x/b", words("יְהֵא שְׁלָמָא רַבָּא מִן"))
        leaf = [*PART_A, "יְהֵא שְׁלָמָא רַבָּא מִן", *UNKNOWN[1:]]
        first = decide([("L", items(*leaf))], index)
        again = decide([("L", items(*leaf))], index, records=first.records)
        self.assertEqual((again.decided, again.lapsed), ([], []))

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

    def test_another_rites_wording_keeps_the_urn(self):
        index = IncipitIndex()
        ashkenaz = "רְצֵה יְהֹוָה אֱלֹהֵינוּ בְּעַמְּךָ יִשְׂרָאֵל וּבִתְפִלָּתָם וְהָשֵׁב אֶת הָעֲבוֹדָה לִדְבִיר בֵּיתֶךָ"
        index.add(T + "prayer:amidah/avodah", words(ashkenaz))
        index.add(T + "prayer:amidah/avodah/retzeh", words(ashkenaz))
        sefard = ["<b>רְצֵה</b> יְהֹוָה אֱלֹהֵינוּ בְּעַמְּךָ יִשְׂרָאֵל", "וְלִתְפִלָּתָם שְׁעֵה וְהָשֵׁב אֶת הָעֲבוֹדָה לִדְבִיר בֵּיתֶךָ"]
        outcome = decide([("L", items(*sefard))], index)
        self.assertEqual(outcome.decided[0].urn, T + "prayer:amidah/avodah/retzeh")

    def test_a_printing_with_words_of_its_own_is_a_variant(self):
        added = "נַחֵם יְהֹוָה אֱלֹהֵינוּ אֶת אֲבֵלֵי צִיּוֹן"
        later = [*MODEH[:2], added, *MODEH[2:]]
        outcome = decide_work("w", [("A", items(*MODEH)), ("B", items(*later))], IncipitIndex(), {}, set(),
                              spellings=NO_SPELLINGS, places={"B": "chol/minchah/amidah"})
        first, second = outcome.decided
        self.assertEqual((second.kind, second.urn, second.variant),
                         ("variant", first.urn, "chol_minchah_amidah"))
        self.assertEqual(second.phrases, [1, 2, 5, 3, 4])

    def test_a_long_passage_introduced_by_a_rubric_stands_inside_the_text(self):
        # Nachem at Minchah of Tisha b'Av: the text, then "On Tisha b'Av:" and a long passage of
        # its own, then the rest of the text.
        passage = [f"נַחֵם יְהֹוָה אֱלֹהֵינוּ פָּסוּק {n} חָדָשׁ לְגַמְרֵי" for n in "אבגדהוזחט"]
        later = [*MODEH[:2], ("", "<small>On Tisha b'Av:</small>"), *[(p, "x") for p in passage], *MODEH[2:]]
        leaf = Leaf(("B",), (("B", "B"),), tuple(h if isinstance(h, str) else h[0] for h in later),
                    tuple("e" if isinstance(h, str) else h[1] for h in later))
        later_items = divide(align_leaf(leaf).pairs)
        outcome = decide_work("w", [("A", items(*MODEH)), ("B", later_items)], IncipitIndex(), {}, set(),
                              spellings=NO_SPELLINGS, places={"B": "chol/minchah"})
        b = [r for r in outcome.decided if r.leaf == "B"]
        self.assertEqual([r.kind for r in b], ["variant"])
        self.assertEqual(b[0].phrases, [1, 2, *range(5, 14), 3, 4])

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


class TestThirdReview(unittest.TestCase):
    def test_a_block_moved_by_a_cut_in_its_own_leaf_is_decided_once(self):
        # One leaf: a first printing that runs on, a rubric, and the text printed again.
        outcome = decide([("A", items(*MODEH, *UNKNOWN[1:], "", *MODEH))])
        keys = [r.key for r in outcome.decided]
        self.assertEqual(len(keys), len(set(keys)))

    def test_a_repeat_whose_first_printing_was_renamed_is_decided_again(self):
        first = decide([("A", items(*MODEH)), ("B", items(*MODEH))])
        records = dict(first.records)
        a = next(r for r in records.values() if r.leaf == "A")
        records[a.key] = TextRecord(**{**a.__dict__, "urn": T + "prayer:renamed"})
        again = decide([("A", items(*MODEH)), ("B", items(*MODEH))], records=records)
        b = next(r for r in again.records.values() if r.leaf == "B")
        self.assertEqual(b.urn, T + "prayer:renamed")

    def test_a_reprint_with_a_parenthesized_insertion_is_a_repeat(self):
        text = ["<b>עוֹשֶׂה שָׁלוֹם</b> (בעשי\"ת הַשָּׁלוֹם) בִּמְרוֹמָיו הוּא", "יַעֲשֶׂה שָׁלוֹם עָלֵינוּ וְעַל כָּל יִשְׂרָאֵל"]
        outcome = decide([("A", items(*text)), ("B", items(*text))])
        self.assertEqual([r.kind for r in outcome.decided], ["new", "repeat"])

    def test_a_changed_text_keeps_the_numbers_its_phrases_had(self):
        first = decide([("L", items(*MODEH))])
        from opensiddur.importer.sefaria.phrases import text_path
        own = {text_path(first.decided[0].urn): {i + 1: skeleton(h) for i, h in enumerate(MODEH)}}
        inserted = [*MODEH[:3], "מְשֻׁנֶּה מְאֹד בְּיוֹתֵר", MODEH[3]]
        again = decide_work("w", [("L", items(*inserted))], IncipitIndex(), first.records, set(),
                            spellings=NO_SPELLINGS, own_phrases=own)
        self.assertEqual(again.decided[0].urn, first.decided[0].urn)
        self.assertEqual(again.decided[0].phrases, [1, 2, 3, 5, 4])


class TestBlessings(unittest.TestCase):
    def test_blessings_over_different_commandments_are_different_texts(self):
        tzitzit = ["<b>בָּרוּךְ</b> אַתָּה יְהֹוָה", "אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם", "אֲשֶׁר קִדְּשָׁנוּ בְּמִצְוֹתָיו",
                   "וְצִוָּנוּ עַל מִצְוַת צִיצִית"]
        tefillin = [*tzitzit[:3], "וְצִוָּנוּ עַל מִצְוַת תְּפִלִּין"]
        outcome = decide([("A", items(*tzitzit)), ("B", items(*tefillin))])
        first, second = outcome.decided
        self.assertEqual(second.kind, "new")
        self.assertNotEqual(second.urn, first.urn)


class TestScriptureVerses(unittest.TestCase):
    def test_a_quoted_verse_is_found_at_its_phrase(self):
        from opensiddur.importer.sefaria.match import scripture_verses
        verse = "זָכוֹר אֵת אֲשֶׁר עָשָׂה לְךָ עֲמָלֵק בַּדֶּרֶךְ בְּצֵאתְכֶם מִמִּצְרָיִם"
        index = IncipitIndex()
        index.add(T + "bible:deuteronomy/25/17", words(verse))
        (block,) = [i for i in items("<b>הִנֵּה</b> אֲנִי מוּכָן לְקַיֵּם", verse) if isinstance(i, TextBlock)]
        self.assertEqual(scripture_verses(block, index), {1: T + "bible:deuteronomy/25/17"})


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

    def test_a_whole_parenthetical_is_left_out_of_the_name(self):
        text = "עוֹשֶׂה (בעשי\"ת הַשָּׁלוֹם) שָׁלוֹם בִּמְרוֹמָיו"
        self.assertEqual(mint(text, set(), NO_SPELLINGS), T + "prayer:oseh_shalom_bimromav")

    def test_unpointed_and_parenthesized_words_are_not_the_name(self):
        text = "(בעשי\"ת) זֶה טֶקְסְט חָדָשׁ"
        self.assertEqual(mint(text, set(), NO_SPELLINGS), T + "prayer:zeh_teqst_chadash")


def documents(*bodies: str) -> IncipitIndex:
    """An index built as the collection's is, from synthetic documents."""
    from lxml import etree

    from opensiddur.importer.util.incipit import index_document

    index = IncipitIndex()
    for body in bodies:
        index_document(index, etree.fromstring(
            f'<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">'
            f"<tei:text><tei:body>{body}</tei:body></tei:text></tei:TEI>"))
    index.open_with_parts()
    return index


def div(urn: str, text: str) -> str:
    return f'<tei:div corresp="{T}{urn}"><tei:p>{text}</tei:p></tei:div>'


BINAH_OPEN = "אַתָּה חוֹנֵן לְאָדָם דַּעַת וּמְלַמֵּד לֶאֱנוֹשׁ בִּינָה"
BINAH_END_ASHKENAZ = "חָנֵּנוּ מֵאִתְּךָ דֵּעָה בִּינָה וְהַשְׂכֵּל בָּרוּךְ אַתָּה יְיָ חוֹנֵן הַדָּעַת"
BINAH_SEFARD = ["<b>אַתָּה חוֹנֵן</b> לְאָדָם דַּעַת", "וּמְלַמֵּד לֶאֱנוֹשׁ בִּינָה:", "חָנֵּנוּ מֵאִתְּךָ",
                "חָכְמָה בִּינָה וָדָעַת", "בָּרוּךְ אַתָּה יְהֹוָה", "חוֹנֵן הַדָּעַת:"]
BINAH = (f'<tei:div corresp="{T}prayer:amidah/binah"><tei:p>'
         f'<tei:milestone unit="part" corresp="{T}prayer:amidah/binah/opening"/>{BINAH_OPEN} '
         f'<tei:milestone unit="part" corresp="{T}prayer:amidah/binah/conclusion"/>{BINAH_END_ASHKENAZ}'
         "</tei:p></tei:div>")


class TestStageTwo(unittest.TestCase):
    def test_a_blessing_is_known_by_its_closing_in_another_rites_words(self):
        outcome = decide([("L", items(*BINAH_SEFARD))], documents(BINAH))
        self.assertEqual([r.urn for r in outcome.decided], [T + "prayer:amidah/binah"])

    def test_a_blessing_opened_otherwise_is_found_by_its_closing_alone(self):
        sefard = ["<b>אַהֲבַת עוֹלָם</b> אֲהַבְתָּנוּ", "חֶמְלָה גְדוֹלָה", "בָּרוּךְ אַתָּה יְהֹוָה",
                  "הַבּוֹחֵר בְּעַמּוֹ יִשְׂרָאֵל בְּאַהֲבָה:"]
        index = documents(div("prayer:ahavah_rabbah",
                              "אַהֲבָה רַבָּה אֲהַבְתָּנוּ חֶמְלָה גְדוֹלָה בָּרוּךְ אַתָּה יְיָ הַבּוֹחֵר בְּעַמּוֹ יִשְׂרָאֵל בְּאַהֲבָה"))
        outcome = decide([("L", items(*sefard))], index)
        self.assertEqual(outcome.decided[0].urn, T + "prayer:ahavah_rabbah")

    def test_a_block_that_runs_into_another_text_is_cut_there(self):
        other = ("אֱלֹהַי נְשָׁמָה שֶׁנָּתַתָּ בִּי טְהוֹרָה הִיא אַתָּה בְרָאתָהּ אַתָּה יְצַרְתָּהּ "
                 "אַתָּה נְפַחְתָּהּ בִּי וְאַתָּה מְשַׁמְּרָהּ בְּקִרְבִּי")
        index = documents(div("prayer:elohai_neshamah", other))
        outcome = decide([("L", items(*UNKNOWN, "אֱלֹהַי נְשָׁמָה שֶׁנָּתַתָּ בִּי טְהוֹרָה הִיא",
                                      "אַתָּה בְרָאתָהּ אַתָּה יְצַרְתָּהּ אַתָּה נְפַחְתָּהּ בִּי",
                                      "וְאַתָּה מְשַׁמְּרָהּ בְּקִרְבִּי"))], index)
        self.assertEqual([r.kind for r in outcome.decided], ["new", "existing"])
        self.assertEqual(outcome.decided[1].urn, T + "prayer:elohai_neshamah")

    def test_a_line_quoted_from_the_end_of_another_text_does_not_cut(self):
        line = "אָבִינוּ מַלְכֵּנוּ חָנֵּנוּ וַעֲנֵנוּ כִּי אֵין בָּנוּ מַעֲשִׂים עֲשֵׂה עִמָּנוּ צְדָקָה וָחֶסֶד וְהוֹשִׁיעֵנוּ"
        index = documents(f'<tei:div corresp="{T}prayer:avinu_malkenu"><tei:p>'
                          f'<tei:milestone unit="part" corresp="{T}prayer:avinu_malkenu/a"/>{" ".join(PART_A)} '
                          f'<tei:milestone unit="part" corresp="{T}prayer:avinu_malkenu/chonnenu"/>{line}</tei:p></tei:div>')
        outcome = decide([("L", items(*UNKNOWN, line, "וְעוֹד דְּבָרִים אֲחֵרִים שֶׁל הַתְּפִלָּה"))], index)
        self.assertEqual(len(outcome.decided), 1)

    def test_a_chapter_ends_at_its_last_verse(self):
        verses = ["מִזְמוֹר לְתוֹדָה הָרִיעוּ לַיהוָה כָּל הָאָרֶץ", "עִבְדוּ אֶת יְהוָה בְּשִׂמְחָה בֹּאוּ לְפָנָיו"]
        index = documents(f'<tei:div corresp="{T}bible:psalms/100"><tei:p>'
                          f'<tei:milestone unit="verse" corresp="{T}bible:psalms/100/1"/>{verses[0]} '
                          f'<tei:milestone unit="verse" corresp="{T}bible:psalms/100/2"/>{verses[1]}</tei:p></tei:div>')
        outcome = decide([("L", items(*verses, *UNKNOWN))], index)
        self.assertEqual([r.urn for r in outcome.decided][0], T + "bible:psalms/100")
        self.assertEqual(len(outcome.decided), 2)

    def test_a_block_that_is_one_whole_verse_is_that_verse(self):
        verse = "וְעָרְבָה לַיהוָה מִנְחַת יְהוּדָה וִירוּשָׁלָם כִּימֵי עוֹלָם וּכְשָׁנִים קַדְמֹנִיּוֹת"
        index = documents(f'<tei:div corresp="{T}bible:malachi/3"><tei:p>'
                          f'<tei:milestone unit="verse" corresp="{T}bible:malachi/3/4"/>{verse} '
                          f'<tei:milestone unit="verse" corresp="{T}bible:malachi/3/5"/>{" ".join(UNKNOWN)}'
                          "</tei:p></tei:div>")
        outcome = decide([("L", items("<b>וְעָרְבָה</b> לַיהוָה מִנְחַת יְהוּדָה וִירוּשָׁלָם",
                                      "כִּימֵי עוֹלָם וּכְשָׁנִים קַדְמֹנִיּוֹת"))], index)
        self.assertEqual(outcome.decided[0].urn, T + "bible:malachi/3/4")

    def test_a_later_printing_worded_otherwise_is_a_variant(self):
        later = [MODEH[0], "מֶֽלֶךְ חַי וְקַיָּם וְנִצָּח", "שֶׁהֶחֱזַֽרְתָּ בִּי נִשְׁמָתִי",
                 "רַבָּה אֱמוּנָתֶֽךָ לְעוֹלָם"]
        outcome = decide_work("w", [("A", items(*MODEH)), ("B", items(*later))], IncipitIndex(), {}, set(),
                              spellings=NO_SPELLINGS, places={"B": "b"})
        first, second = outcome.decided
        self.assertEqual((second.kind, second.urn), ("variant", first.urn))

    def test_a_parenthesized_passage_is_an_insertion(self):
        passage = [f"(אַתָּה חוֹנַנְתָּנוּ פָּסוּק {n} חָדָשׁ" if n == "א" else f"פָּסוּק {n} חָדָשׁ לְגַמְרֵי"
                   for n in "אבגדהו"]
        passage[-1] += ")"
        outcome = decide_work("w", [("A", items(*MODEH)), ("B", items(*MODEH[:2], *passage, *MODEH[2:]))],
                              IncipitIndex(), {}, set(), spellings=NO_SPELLINGS, places={"B": "b"})
        self.assertEqual([r.kind for r in outcome.decided], ["new", "variant"])

    def test_curated_choices_and_joins(self):
        from opensiddur.importer.sefaria.equivalents import Choice, Equivalents, Join, apply_joins

        table = Equivalents(texts=(Choice(tuple(words("זֶה טֶקְסְט")), T + "prayer:chosen_name"),),
                            joins=(Join(tuple(words("וְעוֹד דָּבָר"))),))
        leaf = apply_joins("L", items(*UNKNOWN, "", "<b>וְעוֹד דָּבָר</b> שׁוֹנֶה מְאֹד"), table)
        outcome = decide_work("w", [("L", leaf)], IncipitIndex(), {}, set(), spellings=NO_SPELLINGS,
                              equivalents=table, registered=set())
        (record,) = outcome.decided
        self.assertEqual((record.kind, record.urn), ("new", T + "prayer:chosen_name"))
        self.assertIn("chosen in equivalents.yaml", record.evidence[0])

    def test_the_next_part_of_the_same_text_is_preferred(self):
        index = documents(div("prayer:yotzer_or/qadosh", "קָדוֹשׁ קָדוֹשׁ קָדוֹשׁ יְיָ צְבָאוֹת מְלֹא כָל הָאָרֶץ כְּבוֹדוֹ"),
                          div("prayer:amidah/qedushah/neqaddesh", " ".join(UNKNOWN)),
                          div("prayer:amidah/qedushah/qadosh", "קָדוֹשׁ קָדוֹשׁ קָדוֹשׁ יְיָ צְבָאוֹת מְלֹא כָל הָאָרֶץ כְּבוֹדוֹ"))
        leaf = items(*UNKNOWN, "", "<b>קָדוֹשׁ קָדוֹשׁ קָדוֹשׁ</b> יְהֹוָה צְבָאוֹת", "מְלֹא כָל הָאָֽרֶץ כְּבוֹדוֹ:")
        outcome = decide([("L", leaf)], index)
        self.assertEqual([r.urn for r in outcome.decided],
                         [T + "prayer:amidah/qedushah/neqaddesh", T + "prayer:amidah/qedushah/qadosh"])


class TestPetitionNames(unittest.TestCase):
    def test_a_petition_is_named_past_its_formula(self):
        text = "יְהִי רָצוֹן מִלְּפָנֶיךָ יְהֹוָה אֱלֹהֵינוּ וֵאלֹהֵי אֲבוֹתֵינוּ שֶׁתִּשְׁלַח מְהֵרָה רְפוּאָה שְׁלֵמָה"
        self.assertEqual(mint(text, set(), NO_SPELLINGS), T + "prayer:yehi_ratzon_shetishlach_meherah")

    def test_a_response_before_the_text_is_not_its_name(self):
        text = "אָמֵן. כְּשֵׁם שֶׁנִּכְנַס לַבְּרִית כֵּן יִכָּנֵס לְתוֹרָה"
        self.assertEqual(mint(text, set(), NO_SPELLINGS), T + "prayer:keshem_shenikhnas_laberit")


class TestRecords(unittest.TestCase):
    def test_round_trip(self):
        record = TextRecord("w", "A / B", 3, T + "prayer:x", "new", "אבג", "h", ["why"], [2, 1])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "urns.jsonl"
            save_records({record.key: record}, path)
            self.assertEqual(load_records(path), {record.key: record})


if __name__ == "__main__":
    unittest.main()
