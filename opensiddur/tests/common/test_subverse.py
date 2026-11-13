"""Tests for sub-verse milestone placement.

Every fixture here is hand-written. The point of these tests is the placement rule, which
must not move when a project is re-imported.
"""

import unittest
from unittest.mock import patch

from lxml import etree

from opensiddur.common.subverse import (
    VERSE_PARTS,
    insert_half_verses,
    insert_verse_parts,
)

TEI = "http://www.tei-c.org/ns/1.0"
JLPTEI = "http://jewishliturgy.org/ns/jlptei/2"
URN = "urn:x-opensiddur:text:bible:"


def document(body: str) -> str:
    """A minimal TEI document whose body is `body`, as source text."""
    return (
        f'<tei:TEI xmlns:tei="{TEI}" xmlns:j="{JLPTEI}" xml:lang="he">'
        f"<tei:text><tei:body>{body}</tei:body></tei:text></tei:TEI>"
    )


def verse(corresp: str, n: str = "1") -> str:
    return f'<tei:milestone unit="verse" n="{n}" corresp="{corresp}"/>'


class SubverseTestCase(unittest.TestCase):
    def half_verses(self, xml: str, *, project: str = "") -> str:
        """`insert_half_verses`, asserting that nothing was left unplaceable."""
        result, unplaceable = insert_half_verses(xml, project=project)
        self.assertEqual(unplaceable, [])
        return result

    def verse_parts(self, xml: str, *, language: str = "he") -> str:
        """`insert_verse_parts`, asserting that nothing was left unplaceable."""
        result, unplaceable = insert_verse_parts(xml, language=language)
        self.assertEqual(unplaceable, [])
        return result

    def milestones(self, xml: str, unit: str) -> list[tuple[str, str]]:
        """(n, corresp) of every milestone of `unit`, in document order."""
        return [
            (m.get("n"), m.get("corresp"))
            for m in etree.fromstring(xml.encode()).iter(f"{{{TEI}}}milestone")
            if m.get("unit") == unit
        ]

    def scope(self, xml: str, corresp: str) -> str:
        """The text from the milestone carrying `corresp` to the next milestone with a URN."""
        root = etree.fromstring(xml.encode())
        found = [m for m in root.iter(f"{{{TEI}}}milestone") if m.get("corresp") == corresp]
        self.assertEqual(len(found), 1, f"expected exactly one {corresp}")
        milestone = found[0]

        collected: list[str] = []
        started = False
        for node in root.iter():
            if node is milestone:
                started = True
                collected.append(node.tail or "")
                continue
            if not started:
                continue
            if node.tag == f"{{{TEI}}}milestone" and node.get("corresp"):
                break
            collected.append(node.text or "")
            collected.append(node.tail or "")
        return "".join(collected).strip()

    def assertTextUnchanged(self, xml: str, before: str):
        """The running text must come through untouched; only markup may be added."""
        self.assertEqual("".join(etree.fromstring(xml.encode()).itertext()), before)

    def text_of(self, xml: str) -> str:
        return "".join(etree.fromstring(xml.encode()).itertext())


class TestHalfVerses(SubverseTestCase):
    def test_divides_at_the_etnachta(self):
        """The accent closes the first half; the second half opens at the next word."""
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}"
            "וַיַּרְא אֱלֹהִים אֶת־כׇּל־אֲשֶׁר עָשָׂה וְהִנֵּה־טוֹב מְאֹ֑ד "
            "וַיְהִי־עֶרֶב וַיְהִי־בֹקֶר יוֹם הַשִּׁשִּׁי׃</tei:p>"
        )
        before = self.text_of(xml)

        xml = self.half_verses(xml)

        self.assertEqual(
            self.milestones(xml, "half-verse"),
            [("a", f"{URN}genesis/1/31/a"), ("b", f"{URN}genesis/1/31/b")],
        )
        self.assertTrue(self.scope(xml, f"{URN}genesis/1/31/a").endswith("מְאֹ֑ד"))
        self.assertTrue(self.scope(xml, f"{URN}genesis/1/31/b").startswith("וַיְהִי־עֶרֶב"))
        self.assertTextUnchanged(xml, before)

    def test_a_verse_with_no_etnachta_is_not_divided(self):
        xml = document(f"<tei:p>{verse(f'{URN}genesis/1/1')}בְּרֵאשִׁית בָּרָא׃</tei:p>")

        xml = self.half_verses(xml)
        self.assertEqual(self.milestones(xml, "half-verse"), [])

    def test_an_etnachta_on_the_last_word_divides_nothing(self):
        """There is no second half, so there are no halves."""
        xml = document(f"<tei:p>{verse(f'{URN}genesis/1/1')}בְּרֵאשִׁית בָּרָ֑א</tei:p>")

        xml = self.half_verses(xml)
        self.assertEqual(self.milestones(xml, "half-verse"), [])

    def test_the_boundary_does_not_split_a_maqqef_group(self):
        """Words joined by maqqef are read as one and the boundary goes before all of them."""
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}"
            "טוֹב מְאֹ֑ד וַיְהִי־עֶרֶב וַיְהִי־בֹקֶר׃</tei:p>"
        )

        xml = self.half_verses(xml)

        self.assertEqual(
            self.scope(xml, f"{URN}genesis/1/31/b"), "וַיְהִי־עֶרֶב וַיְהִי־בֹקֶר׃"
        )

    def test_a_verse_broken_over_two_paragraphs_is_one_verse(self):
        """A parashah break in the middle of a verse does not end it."""
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/35/22', '22')}וַיֵּלֶךְ רְאוּבֵ֑ן </tei:p>"
            "<tei:p>וַיִּהְיוּ בְנֵי־יַעֲקֹב שְׁנֵים עָשָׂר׃</tei:p>"
        )
        before = self.text_of(xml)

        xml = self.half_verses(xml)

        self.assertEqual(
            self.scope(xml, f"{URN}genesis/35/22/b"), "וַיִּהְיוּ בְנֵי־יַעֲקֹב שְׁנֵים עָשָׂר׃"
        )
        self.assertTextUnchanged(xml, before)

    def test_a_word_broken_over_an_element_is_one_word(self):
        """Miqra al pi ha-Masorah sets an enlarged first letter as its own element."""
        xml = document(
            f"<tei:p>{verse(f'{URN}exodus/34/7', '7')}"
            '<tei:hi rend="large">נֹ</tei:hi>צֵר חֶסֶד וְחַטָּאָ֑ה וְנַקֵּה לֹא יְנַקֶּה׃</tei:p>'
        )
        before = self.text_of(xml)

        xml = self.half_verses(xml)

        self.assertEqual(self.scope(xml, f"{URN}exodus/34/7/a"), "נֹצֵר חֶסֶד וְחַטָּאָ֑ה")
        self.assertTextUnchanged(xml, before)

    def test_a_ketiv_is_not_read_as_a_word_of_its_own(self):
        """Descending into both readings would put the unpointed ketiv into the text.

        Here the etnachta is on the word before the ketiv/qere, so counting the ketiv as a
        word would put the boundary one word late — inside the choice rather than before it.
        """
        xml = document(
            f"<tei:p>{verse(f'{URN}psalms/5/9', '9')}"
            "לְמַעַן שׁוֹרְרָ֑י "
            "<tei:choice><j:written>הושר</j:written><j:read>הַיְשַׁר</j:read></tei:choice>"
            " לְפָנַי דַּרְכֶּךָ׃</tei:p>"
        )
        before = self.text_of(xml)

        xml = self.half_verses(xml)

        self.assertEqual(self.scope(xml, f"{URN}psalms/5/9/a"), "לְמַעַן שׁוֹרְרָ֑י")
        # The milestone goes before the choice, not inside either reading of it.
        root = etree.fromstring(xml.encode())
        half = [
            m for m in root.iter(f"{{{TEI}}}milestone")
            if m.get("corresp") == f"{URN}psalms/5/9/b"
        ][0]
        self.assertEqual(half.getnext().tag, f"{{{TEI}}}choice")
        self.assertTextUnchanged(xml, before)

    def test_a_verse_with_variant_accentuation_is_not_divided(self):
        """The two cantillations of the Decalogue put the etnachta in different places.

        A URN must denote the same words wherever it resolves, so a verse whose division
        depends on which variant is selected gets none.
        """
        tachton = "אָנֹכִי יְהֹוָה אֱלֹהֶיךָ אֲשֶׁר הוֹצֵאתִיךָ מִבֵּית עֲבָדִ֑ים"
        elyon = "אָנֹכִי יְהֹוָה אֱלֹהֶ֑יךָ אֲשֶׁר הוֹצֵאתִיךָ מִבֵּית עֲבָדִים׃"
        xml = document(
            f"<tei:p>{verse(f'{URN}exodus/20/2', '2')}<tei:choice>"
            f'<j:option corresp="urn:x-opensiddur:condition:bible:taam-tachton">{tachton}</j:option>'
            f'<j:option corresp="urn:x-opensiddur:condition:bible:taam-elyon">{elyon}</j:option>'
            "</tei:choice></tei:p>"
        )

        xml = self.half_verses(xml)
        self.assertEqual(self.milestones(xml, "half-verse"), [])

    def test_a_poetic_verse_with_ole_is_not_divided(self):
        """Where ole-we-yored governs, the etnachta is not the primary division."""
        xml = document(
            f"<tei:p>{verse(f'{URN}psalms/1/1')}"
            "אַשְׁרֵ֥י הָאִ֗֫ישׁ אֲשֶׁר לֹא הָלַ֑ךְ בַּעֲצַת רְשָׁעִים׃</tei:p>"
        )

        xml = self.half_verses(xml)
        self.assertEqual(self.milestones(xml, "half-verse"), [])

    def test_a_poetic_verse_without_ole_is_divided_at_the_etnachta(self):
        xml = document(
            f"<tei:p>{verse(f'{URN}psalms/1/2')}"
            "כִּי אִם בְּתוֹרַת יְהֹוָה חֶפְצ֑וֹ וּבְתוֹרָתוֹ יֶהְגֶּה׃</tei:p>"
        )

        xml = self.half_verses(xml)

        self.assertEqual(self.scope(xml, f"{URN}psalms/1/2/b"), "וּבְתוֹרָתוֹ יֶהְגֶּה׃")

    def test_ole_in_a_prose_book_does_not_prevent_division(self):
        """Only the three books read with the poetic accents are held back."""
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/1')}"
            "בְּרֵאשִׁ֗֫ית בָּרָ֑א אֱלֹהִים אֵת הַשָּׁמַיִם׃</tei:p>"
        )

        xml = self.half_verses(xml)

        self.assertEqual(self.scope(xml, f"{URN}genesis/1/1/b"), "אֱלֹהִים אֵת הַשָּׁמַיִם׃")

    def test_each_verse_is_divided_independently(self):
        xml = document(
            f"<tei:p>{verse(f'{URN}nahum/2/2', '2')}"
            "עָלָה מֵפִיץ נָצוֹר מְצוּרָ֑ה צַפֵּה־דֶרֶךְ חַזֵּק מׇתְנַיִם׃"
            f"{verse(f'{URN}nahum/2/3', '3')}"
            "כִּי שָׁב יְהֹוָה כִּגְאוֹן יִשְׂרָאֵ֑ל כִּי בְקָקוּם בֹּקְקִים׃</tei:p>"
        )
        before = self.text_of(xml)

        xml = self.half_verses(xml)

        self.assertEqual(self.scope(xml, f"{URN}nahum/2/2/b"), "צַפֵּה־דֶרֶךְ חַזֵּק מׇתְנַיִם׃")
        self.assertEqual(self.scope(xml, f"{URN}nahum/2/3/a"), "כִּי שָׁב יְהֹוָה כִּגְאוֹן יִשְׂרָאֵ֑ל")
        self.assertTextUnchanged(xml, before)

    def test_a_chapter_milestone_ends_the_verse_before_it(self):
        """The last verse of a chapter must not run on into the next chapter's text."""
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}טוֹב מְאֹ֑ד יוֹם הַשִּׁשִּׁי׃</tei:p>"
            f'<tei:p><tei:milestone unit="chapter" n="2" corresp="{URN}genesis/2"/>'
            f"{verse(f'{URN}genesis/2/1')}וַיְכֻלּ֑וּ הַשָּׁמַיִם וְהָאָרֶץ׃</tei:p>"
        )

        xml = self.half_verses(xml)

        self.assertEqual(self.scope(xml, f"{URN}genesis/1/31/b"), "יוֹם הַשִּׁשִּׁי׃")
        self.assertEqual(self.scope(xml, f"{URN}genesis/2/1/b"), "הַשָּׁמַיִם וְהָאָרֶץ׃")

    def test_milestones_outside_tei_text_are_ignored(self):
        """A header may quote a verse; only the text carries the division."""
        xml = (
            f'<tei:TEI xmlns:tei="{TEI}" xml:lang="he"><tei:teiHeader>'
            f'<tei:milestone unit="verse" n="1" corresp="{URN}genesis/1/1"/>'
            "בְּרֵאשִׁ֑ית בָּרָא</tei:teiHeader>"
            "<tei:text><tei:body><tei:p/></tei:body></tei:text></tei:TEI>"
        )
        xml = self.half_verses(xml)
        self.assertEqual(self.milestones(xml, "half-verse"), [])


class TestSourceIsPreserved(SubverseTestCase):
    """The pass splices into the source; it must not rewrite anything it did not add.

    The WLC importer serialises through Saxon, which sets each attribute on its own line.
    Re-serialising with lxml would reformat every file it produces, and a regeneration would
    bury the milestones in a whole-project diff.
    """

    WLC_STYLE = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<tei:TEI xmlns:j="{JLPTEI}"\n         xmlns:tei="{TEI}"\n         xml:lang="he">\n'
        "   <tei:text xml:lang=\"he\">\n      <tei:body>\n         <tei:p>\n"
        '            <tei:milestone unit="verse"\n'
        f'                           corresp="{URN}genesis/1/1"\n'
        '                           n="1"/>בְּרֵאשִׁ֑ית בָּרָא אֱלֹהִים׃\n'
        "         </tei:p>\n      </tei:body>\n   </tei:text>\n</tei:TEI>\n"
    )

    def test_everything_but_the_insertions_survives_verbatim(self):
        result = self.half_verses(self.WLC_STYLE)

        self.assertNotEqual(result, self.WLC_STYLE, "nothing was inserted")
        without = result
        for milestone in self.milestones(result, "half-verse"):
            without = without.replace(
                f'<tei:milestone unit="half-verse" n="{milestone[0]}" '
                f'corresp="{milestone[1]}"/>',
                "",
            )
        self.assertEqual(without, self.WLC_STYLE)

    def test_the_xml_declaration_and_attribute_wrapping_are_kept(self):
        result = self.half_verses(self.WLC_STYLE)

        self.assertTrue(result.startswith('<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn('<tei:milestone unit="verse"\n', result)

    def test_the_boundary_lands_in_the_right_place_all_the_same(self):
        result = self.half_verses(self.WLC_STYLE)

        self.assertEqual(self.scope(result, f"{URN}genesis/1/1/a"), "בְּרֵאשִׁ֑ית")
        self.assertEqual(self.scope(result, f"{URN}genesis/1/1/b"), "בָּרָא אֱלֹהִים׃")


class TestVerseParts(SubverseTestCase):
    PARTS = {
        ("genesis", 1, 31): (("yom_hashishi", {"he": "יום הששי"}),),
    }

    def test_places_a_declared_part_at_its_incipit(self):
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}"
            "וַיְהִי־עֶרֶב וַיְהִי־בֹקֶר יוֹם הַשִּׁשִּׁי׃</tei:p>"
        )
        before = self.text_of(xml)

        with patch.dict(VERSE_PARTS, self.PARTS, clear=True):
            xml = self.verse_parts(xml)

        self.assertEqual(
            self.milestones(xml, "verse-part"),
            [("yom_hashishi", f"{URN}genesis/1/31/yom_hashishi")],
        )
        self.assertEqual(self.scope(xml, f"{URN}genesis/1/31/yom_hashishi"), "יוֹם הַשִּׁשִּׁי׃")
        self.assertTextUnchanged(xml, before)

    def test_matches_on_consonants_alone(self):
        """One declared incipit has to find the same words in every edition's pointing."""
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}"
            "וַיְהִי־בֹ֖קֶר י֥וֹם הַשִּׁשִּֽׁי׃</tei:p>"
        )

        with patch.dict(VERSE_PARTS, self.PARTS, clear=True):
            xml = self.verse_parts(xml)

        self.assertEqual(
            self.scope(xml, f"{URN}genesis/1/31/yom_hashishi"), "י֥וֹם הַשִּׁשִּֽׁי׃"
        )

    def test_line_break_without_literal_space_still_separates_words(self):
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}"
            'וַיְהִי־בֹקֶר<tei:lb type="indent"/>יוֹם הַשִּׁשִּׁי׃</tei:p>'
        )
        with patch.dict(VERSE_PARTS, self.PARTS, clear=True):
            result = self.verse_parts(xml)
        marker = '<tei:milestone unit="verse-part" n="yom_hashishi" corresp="'+URN+'genesis/1/31/yom_hashishi"/>'
        self.assertEqual(result.replace(marker, ''), xml)
        self.assertIn('<tei:lb type="indent"/>'+marker+'יוֹם', result)

    def test_an_incipit_that_is_not_there_is_reported(self):
        """A declared part that cannot be placed is the caller's problem to fail on."""
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}וַיְהִי־עֶרֶב וַיְהִי־בֹקֶר׃</tei:p>"
        )

        with patch.dict(VERSE_PARTS, self.PARTS, clear=True):
            _result, unplaceable = insert_verse_parts(xml, language="he")

        self.assertEqual(len(unplaceable), 1)
        self.assertEqual(unplaceable[0].urn, f"{URN}genesis/1/31/yom_hashishi")
        self.assertEqual(self.milestones(xml, "verse-part"), [])

    def test_an_incipit_beginning_inside_a_maqqef_group_is_reported(self):
        """The words a maqqef joins are read as one; nothing may be put between them.

        The incipit is found in the text — but only starting at the second word of a
        maqqef group, which is not a point a milestone can go.
        """
        parts = {("genesis", 1, 31): (("hashishi", {"he": "הששי"}),)}
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}"
            "וַיְהִי־בֹקֶר יוֹם־הַשִּׁשִּׁי׃</tei:p>"
        )

        with patch.dict(VERSE_PARTS, parts, clear=True):
            _result, unplaceable = insert_verse_parts(xml, language="he")

        self.assertEqual(len(unplaceable), 1)
        self.assertIn("word boundary", unplaceable[0].reason)

    def test_a_language_that_declares_nothing_gets_nothing(self):
        """A translation carries no parts rather than failing for want of an incipit."""
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}"
            "And there was evening and there was morning, the sixth day.</tei:p>"
        )

        with patch.dict(VERSE_PARTS, self.PARTS, clear=True):
            xml = self.verse_parts(xml, language="en")

        self.assertEqual(self.milestones(xml, "verse-part"), [])

    def test_several_parts_in_one_verse_are_all_placed(self):
        """A part's scope runs to the next one, so ending a passage needs two of them."""
        parts = {
            ("exodus", 34, 7): (
                ("venakeh", {"he": "ונקה"}),
                ("lo_yenakeh", {"he": "לא ינקה"}),
            ),
        }
        xml = document(
            f"<tei:p>{verse(f'{URN}exodus/34/7', '7')}"
            "נֹצֵר חֶסֶד וְחַטָּאָה וְנַקֵּה לֹא יְנַקֶּה פֹּקֵד עָוֺן׃</tei:p>"
        )
        before = self.text_of(xml)

        with patch.dict(VERSE_PARTS, parts, clear=True):
            xml = self.verse_parts(xml)

        self.assertEqual(
            [n for n, _ in self.milestones(xml, "verse-part")], ["venakeh", "lo_yenakeh"]
        )
        self.assertEqual(self.scope(xml, f"{URN}exodus/34/7/venakeh"), "וְנַקֵּה")
        self.assertTextUnchanged(xml, before)


class TestDeclaredVerseParts(SubverseTestCase):
    """The parts VERSE_PARTS actually declares, against hand-written verse texts."""

    def test_scroll_lifting_uses_last_al_pi_not_the_earlier_occurrences(self):
        text = 'עַל פִּי יְהוָה יַחֲנוּ וְעַל פִּי יְהוָה יִסָּעוּ אֶת מִשְׁמֶרֶת יְהוָה שָׁמָרוּ עַל פִּי יְהוָה בְּיַד מֹשֶׁה׃'
        xml = self.verse_parts(document(f'<tei:p>{verse(URN+"numbers/9/23", "23")}{text}</tei:p>'))
        self.assertEqual(self.scope(xml, URN+'numbers/9/23/al_pi'), 'עַל פִּי יְהוָה בְּיַד מֹשֶׁה׃')
        self.assertTextUnchanged(xml, text)

    def test_qedushah_call_and_response_remain_distinct_inside_one_verse(self):
        call = 'וְקָרָא זֶה אֶל־זֶה וְאָמַר '
        response = 'קָדוֹשׁ קָדוֹשׁ קָדוֹשׁ יְהוָה צְבָאוֹת מְלֹא כָל־הָאָרֶץ כְּבוֹדוֹ׃'
        xml = document(f'<tei:p>{verse(URN+"isaiah/6/3", "3")}{call}{response}</tei:p>')
        before = call + response
        xml = self.verse_parts(xml)
        self.assertEqual(self.scope(xml, URN+'isaiah/6/3/veqara'), call.strip())
        self.assertEqual(self.scope(xml, URN+'isaiah/6/3/qadosh'), response)
        self.assertTextUnchanged(xml, before)

    def test_the_thirteen_attributes(self):
        """They open at the second יהוה and close at ונקה, neither of them an accent."""
        xml = document(
            f"<tei:p>{verse(f'{URN}exodus/34/6', '6')}"
            "וַיַּעֲבֹר יְהֹוָה׀עַל־פָּנָיו וַיִּקְרָא יְהֹוָה׀יְהֹוָה אֵל רַחוּם וְחַנּ֑וּן "
            "אֶרֶךְ אַפַּיִם וְרַב־חֶסֶד וֶאֱמֶת׃"
            f"{verse(f'{URN}exodus/34/7', '7')}"
            "נֹצֵר חֶסֶד לָאֲלָפִים נֹשֵׂא עָוֺן וָפֶשַׁע וְחַטָּאָ֑ה וְנַקֵּה "
            "לֹא יְנַקֶּה פֹּקֵד עֲוֺן אָבוֹת׃</tei:p>"
        )
        before = self.text_of(xml)

        xml = self.verse_parts(xml)

        # The recitation opens here, three words before the etnachta of 34:6 ...
        self.assertTrue(
            self.scope(xml, f"{URN}exodus/34/6/adonai_adonai").startswith("יְהֹוָה׀יְהֹוָה אֵל")
        )
        # ... and closes here, one word past the etnachta of 34:7.
        self.assertEqual(self.scope(xml, f"{URN}exodus/34/7/notzer_chesed"),
                         'נֹצֵר חֶסֶד לָאֲלָפִים נֹשֵׂא עָוֺן וָפֶשַׁע וְחַטָּאָ֑ה')
        self.assertEqual(self.scope(xml, f"{URN}exodus/34/7/venakeh"), "וְנַקֵּה")
        self.assertTrue(
            self.scope(xml, f"{URN}exodus/34/7/lo_yenakeh").startswith("לֹא יְנַקֶּה")
        )
        self.assertTextUnchanged(xml, before)

    def test_a_paseq_separates_words_however_it_is_spaced(self):
        """Miqra al pi ha-Masorah sets the paseq tight and the WLC sets it with spaces.

        Either way the two divine names are two words, and the part opens on the first of
        them rather than in the middle of a token.
        """
        for label, text in [
            ("tight", "וַיִּקְרָא יְהוָה׀יְהוָה אֵל רַחוּם וְחַנּוּן׃"),
            ("spaced", "וַיִּקְרָא יְהוָה ׀ יְהוָה אֵל רַחוּם וְחַנּוּן׃"),
        ]:
            with self.subTest(label):
                xml = document(
                    f"<tei:p>{verse(f'{URN}exodus/34/6', '6')}{text}</tei:p>"
                )

                xml = self.verse_parts(xml)
                self.assertTrue(
                    self.scope(xml, f"{URN}exodus/34/6/adonai_adonai").startswith("יְהוָה")
                )
                # It opens after "and he proclaimed", not at the head of the verse.
                self.assertNotIn(
                    "וַיִּקְרָא", self.scope(xml, f"{URN}exodus/34/6/adonai_adonai")
                )

    def test_kiddush_opens_inside_the_second_half_of_genesis_1_31(self):
        xml = document(
            f"<tei:p>{verse(f'{URN}genesis/1/31', '31')}"
            "וְהִנֵּה־טוֹב מְאֹ֑ד וַיְהִי־עֶרֶב וַיְהִי־בֹקֶר יוֹם הַשִּׁשִּׁי׃</tei:p>"
        )

        xml = self.half_verses(xml)
        xml = self.verse_parts(xml)

        # The part sits inside the second half, which it neither ends nor is ended by.
        self.assertEqual(self.scope(xml, f"{URN}genesis/1/31/b"), "וַיְהִי־עֶרֶב וַיְהִי־בֹקֶר")
        self.assertEqual(self.scope(xml, f"{URN}genesis/1/31/yom_hashishi"), "יוֹם הַשִּׁשִּׁי׃")

    def test_no_declared_part_name_contains_a_dash(self):
        """A dash in the last component of a URN is what marks a range."""
        for key, parts in VERSE_PARTS.items():
            for name, _incipits in parts:
                self.assertNotIn("-", name, f"{key} declares {name!r}")


if __name__ == "__main__":
    unittest.main()
