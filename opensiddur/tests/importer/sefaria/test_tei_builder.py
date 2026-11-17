import unittest

from lxml import etree

from opensiddur.importer.sefaria.align import align_leaf
from opensiddur.importer.sefaria.blocks import TextBlock, divide
from opensiddur.importer.sefaria.source import Leaf
from opensiddur.importer.sefaria.tei_builder import Notes, file_stem, render, text_body
from opensiddur.importer.sefaria.markup import parse_segment
from opensiddur.importer.util.hebrew import to_nfkd

from .support import AMIDAH, MORNING

T = "urn:x-opensiddur:text:"
NS = {"tei": "http://www.tei-c.org/ns/1.0", "j": "http://jewishliturgy.org/ns/jlptei/2"}


def blocks(segments):
    leaf = Leaf(("L",), (("L", "L"),), tuple(h for h, _ in segments), tuple(e for _, e in segments))
    return [i for i in divide(align_leaf(leaf).pairs) if isinstance(i, TextBlock)]


def parse(body: str) -> etree._Element:
    return etree.fromstring(
        f'<tei:TEI xmlns:tei="{NS["tei"]}" xmlns:j="{NS["j"]}">{body}</tei:TEI>')


class TestTextBody(unittest.TestCase):
    def test_phrase_milestones_match_across_languages(self):
        block = blocks(MORNING)[0]
        he = parse(text_body(T + "prayer:modeh_ani", block, [1, 2], "he", Notes("note")))
        en = parse(text_body(T + "prayer:modeh_ani", block, [1, 2], "en", Notes("note")))
        marks = "//tei:milestone[@unit='phrase']/@corresp"
        self.assertEqual(he.xpath(marks, namespaces=NS), [T + "metsudah:modeh_ani/1", T + "metsudah:modeh_ani/2"])
        self.assertEqual(he.xpath(marks, namespaces=NS), en.xpath(marks, namespaces=NS))
        self.assertEqual(he.xpath("//tei:div/@corresp", namespaces=NS), [T + "prayer:modeh_ani"])

    def test_footnotes_are_anchored_and_collected(self):
        notes = Notes("note")
        en = parse(text_body(T + "prayer:modeh_ani", blocks(MORNING)[0], [1, 2], "en", notes))
        self.assertEqual(en.xpath("//tei:anchor/@xml:id", namespaces=NS), ["note_1"])
        self.assertEqual(len(notes.entries), 1)

    def test_heading_and_leading_label(self):
        block = blocks(AMIDAH)[0]
        he = parse(text_body(T + "prayer:amidah/avot", block, [1, 2, 3], "he", Notes("note")))
        self.assertEqual(he.xpath("string(//tei:head)", namespaces=NS), "אבות")
        self.assertEqual(he.xpath("//tei:note[@type='instruction']/@xml:lang", namespaces=NS), ["he"])
        en = parse(text_body(T + "prayer:amidah/avot", block, [1, 2, 3], "en", Notes("note")))
        self.assertEqual(en.xpath("string(//tei:head)", namespaces=NS), "FOREFATHERS")
        self.assertEqual(en.xpath("//tei:hi/@rend", namespaces=NS), ["italic"])

    def test_a_rubric_closes_the_phrase_before_it_in_both_languages(self):
        (block,) = blocks([
            ("<b>מוֹדֶה אֲנִי</b> לְפָנֶֽיךָ", "I give thanks"),
            ("", "<small>(bow)</small>"),
            ("מֶֽלֶךְ חַי", "living King"),
        ])
        for lang in ("he", "en"):
            body = parse(text_body(T + "prayer:modeh_ani", block, [1, 2], lang, Notes("note")))
            marks = body.xpath("//tei:milestone[@unit='phrase']", namespaces=NS)
            self.assertEqual([m.get("corresp") for m in marks],
                             [T + "metsudah:modeh_ani/1", None, T + "metsudah:modeh_ani/2"])
        en = parse(text_body(T + "prayer:modeh_ani", block, [1, 2], "en", Notes("note")))
        self.assertEqual(en.xpath("string(//tei:note)", namespaces=NS), "(bow)")

    def test_an_untranslated_phrase_is_marked_in_the_english_too(self):
        (block,) = blocks([("<b>מוֹדֶה אֲנִי</b> לְפָנֶֽיךָ", "I give thanks"), ("מֶֽלֶךְ חַי", "")])
        en = parse(text_body(T + "prayer:modeh_ani", block, [1, 2], "en", Notes("note")))
        self.assertEqual(en.xpath("//tei:milestone/@corresp", namespaces=NS),
                         [T + "metsudah:modeh_ani/1", T + "metsudah:modeh_ani/2"])

    def test_verses_are_marked_and_closed_where_they_end(self):
        (block,) = blocks([
            ("<b>תְּהִלָּה</b> לְדָוִד", "A praise by David"),
            ("אֲרוֹמִמְךָ אֱלוֹהַי הַמֶּלֶךְ:", "I will exalt You"),
            ("וְעוֹד דָּבָר", "and more"),
        ])
        verses = {0: T + "bible:psalms/145/1"}
        for lang in ("he", "en"):
            body = parse(text_body(T + "prayer:ashrei", block, [1, 2, 3], lang, Notes("note"), (), verses))
            marks = body.xpath("//tei:milestone[@unit='verse']", namespaces=NS)
            self.assertEqual([m.get("corresp") for m in marks], [T + "bible:psalms/145/1", None])
            # The verse closes after the phrase that ends it, before the third phrase.
            following = marks[1].xpath("following::tei:milestone[@unit='phrase'][@corresp][1]/@corresp",
                                       namespaces=NS)
            self.assertEqual(following, [T + "metsudah:ashrei/3"])

    def test_a_verse_without_punctuation_closes_at_its_length_or_a_rubric(self):
        (block,) = blocks([
            ("<b>תְּהִלָּה</b> לְדָוִד", "A praise by David"),
            ("וְעוֹד דָּבָר אַחֵר", "and more"),
            ("", "<small>Say:</small>"),
            ("וְעוֹד", "more"),
        ])
        verse = T + "bible:psalms/145/1"
        by_length = parse(text_body(T + "prayer:x", block, [1, 2, 3], "he", Notes("note"), (), {0: verse},
                                    {verse: 2}))
        closes = by_length.xpath("//tei:milestone[@unit='verse'][not(@corresp)]", namespaces=NS)
        self.assertEqual(closes[0].xpath("following::tei:milestone[@corresp][1]/@corresp", namespaces=NS),
                         [T + "metsudah:x/2"])
        by_rubric = parse(text_body(T + "prayer:x", block, [1, 2, 3], "he", Notes("note"), (), {0: verse}))
        self.assertEqual(len(by_rubric.xpath("//tei:milestone[@unit='verse'][not(@corresp)]", namespaces=NS)), 1)

    def test_a_footnote_in_a_heading_is_kept(self):
        (block,) = blocks([
            ('<b>אבות</b>', '<b>FOREFATHERS</b><sup class="footnote-marker">1</sup><i class="footnote">The first.</i>'),
            ("<b>בָּרוּךְ</b> אַתָּה", "Blessed"),
        ])
        notes = Notes("note")
        en = parse(text_body(T + "prayer:amidah/avot", block, [1], "en", notes))
        self.assertEqual(en.xpath("//tei:head/tei:anchor/@xml:id", namespaces=NS), ["note_1"])
        self.assertEqual(len(notes.entries), 1)

    def test_hebrew_is_decomposed_and_bold_dropped(self):
        out = render(parse_segment("<b>שָׁ</b>"), "he", None)
        self.assertNotIn("<", out)
        self.assertEqual(out, to_nfkd("\u05e9\u05c1\u05b8"))  # shin, shin dot, qamatz, reordered


TABLE = None


def conditions():
    from opensiddur.importer.sefaria.conditions import (
        Conditions, LabelCondition, Replacement, RubricCondition)
    import re as _re
    from opensiddur.importer.util.incipit import words
    aseret = {"holiday-aggregate": {"aseret-ymei-tshuva": True}}
    return Conditions(
        rubrics=(RubricCondition(_re.compile("^During the Ten Days"), aseret),
                 RubricCondition(_re.compile("^On Sunday:"), {"day-of-week": {"hebrew-day": 1}}),
                 RubricCondition(_re.compile("^When the Chazzan repeats"), {"recitation": {"repetition": True}},
                                 section=True)),
        labels=(LabelCondition(tuple(words('לר"ח')), {"holiday": {"rosh-hodesh": True}}),),
        inline=(LabelCondition(tuple(words('בעשי"ת')), aseret),),
        replacements=(Replacement(tuple(words("הַשָּׁלוֹם")), tuple(words("שָׁלוֹם"))),
                      Replacement(tuple(words("וּלְעֵלָּא מִכָּל")), tuple(words("מִן כָּל")))),
    )


class TestConditions(unittest.TestCase):
    URN = T + "prayer:amidah/gevurot"
    SEGMENTS = [
        ("<b>אַתָּה גִבּוֹר</b> לְעוֹלָם", "You are mighty"),
        ("", "<small><i>During the Ten Days of Penitence add:</i></small>"),
        ("<small>מִי כָמוֹךָ אָב הָרַחֲמָן</small>", "Who is like You"),
        ("<small>זוֹכֵר יְצוּרָיו</small>", "Who remembers"),
        ("", "<small>If you forgot, see page 000.</small>"),
        ("וְנֶאֱמָן אַתָּה", "And You are faithful"),
    ]

    def body(self, segments, numbers, lang):
        (block,) = blocks(segments)
        return parse(text_body(self.URN, block, numbers, lang, Notes("note"), conditions=conditions()))

    def test_a_condition_rubric_governs_the_phrases_to_the_next_rubric(self):
        for lang in ("he", "en"):
            body = self.body(self.SEGMENTS, [1, 2, 3, 4], lang)
            (conditional,) = body.xpath("//j:conditional", namespaces=NS)
            self.assertEqual(conditional.xpath("tei:fs/tei:f/@name", namespaces=NS), ["aseret-ymei-tshuva"])
            inside = body.xpath("//tei:milestone[@unit='phrase'][preceding-sibling::j:conditional]"
                                "[following-sibling::j:endConditional]/@corresp", namespaces=NS)
            self.assertEqual(inside, [T + "metsudah:amidah/gevurot/2", T + "metsudah:amidah/gevurot/3"])
        en = self.body(self.SEGMENTS, [1, 2, 3, 4], "en")
        self.assertEqual(en.xpath("string(//j:conditional/tei:note)", namespaces=NS),
                         "During the Ten Days of Penitence add:")
        self.assertEqual(self.body(self.SEGMENTS, [1, 2, 3, 4], "he").xpath("//j:conditional/tei:note",
                                                                            namespaces=NS), [])
        # The directive after the passage is not inside it.
        self.assertEqual(len(en.xpath("//tei:note[@type='instruction'][preceding::j:endConditional]",
                                      namespaces=NS)), 1)

    def test_a_parenthesized_passage_ends_where_its_parenthesis_closes(self):
        segments = [("<b>אַתָּה גִבּוֹר</b> לְעוֹלָם", "x"), ("", "<small>During the Ten Days add:</small>"),
                    ("(מִי כָמוֹךָ)", "y"), ("וְנֶאֱמָן אַתָּה", "z")]
        he = self.body(segments, [1, 2, 3], "he")
        after = he.xpath("//tei:milestone[@unit='phrase'][preceding-sibling::j:endConditional]/@corresp",
                         namespaces=NS)
        self.assertEqual(after, [T + "metsudah:amidah/gevurot/3"])

    def test_a_labelled_phrase_is_conditional_its_label_the_note(self):
        segments = [("<b>יַעֲלֶה</b> וְיָבֹא", "May it rise"), ("<small>לְר\"ח:</small> רֹאשׁ הַחֹדֶשׁ הַזֶּה", "this Rosh Chodesh")]
        he = self.body(segments, [1, 2], "he")
        self.assertEqual(he.xpath("string(//j:conditional/tei:note)", namespaces=NS), 'לְר"ח:'.replace("ְ", "ְ"))
        self.assertEqual(he.xpath("//j:conditional/tei:fs/tei:f/@name", namespaces=NS), ["rosh-hodesh"])
        # The label is not printed again before the phrase.
        self.assertEqual(len(he.xpath("//tei:note", namespaces=NS)), 1)

    def test_an_inline_alternative_and_the_words_it_replaces(self):
        segments = [("<b>עֹשֶׂה</b> (בעשי\"ת הַשָּׁלוֹם) שָׁלוֹם בִּמְרוֹמָיו", "He Who makes peace"),
                    ("לְעֵלָּא (<small>בעשי\"ת</small> וּלְעֵלָּא מִכָּל) מִן־כָּל בִּרְכָתָא", "above")]
        he = self.body(segments, [1, 2], "he")
        marked = he.xpath("//j:conditional[@type='marked']", namespaces=NS)
        self.assertEqual(len(marked), 2)
        self.assertEqual([m.xpath("string(tei:note)", namespaces=NS) for m in marked], ['בעשי"ת', 'בעשי"ת'])
        negated = he.xpath("//j:conditional[j:none]", namespaces=NS)
        self.assertEqual(len(negated), 2)
        text = "".join(he.itertext())
        self.assertIn(to_nfkd("הַשָּׁלוֹם"), text)
        self.assertNotIn("(", text)

    def test_conditionals_nest_with_a_variants(self):
        from opensiddur.importer.sefaria.tei_builder import VariantPrinting

        (block,) = blocks(self.SEGMENTS)
        (later,) = blocks(self.SEGMENTS[:3] + self.SEGMENTS[4:])
        variant = VariantPrinting("musaf", later, [1, 2, 4])
        he = text_body(self.URN, block, [1, 2, 3, 4], "he", Notes("note"), (variant,), conditions=conditions())
        order = [(e.tag.split("}")[1], e.get("{http://www.w3.org/XML/1998/namespace}id") or e.get("target"))
                 for e in parse(he).iter() if e.tag.endswith(("}conditional", "}endConditional"))]
        stack = []
        for kind, ident in order:
            if kind == "conditional":
                stack.append(ident)
            else:
                self.assertEqual("#" + stack.pop(), ident)
        self.assertEqual(stack, [])


class TestLeafGates(unittest.TestCase):
    def test_a_condition_rubric_between_texts_gates_the_next_text_or_its_section(self):
        from opensiddur.importer.sefaria.tei_builder import leaf_body

        leaf = Leaf(("L",), (("L", "L"),), ("", "<b>מִזְמוֹר</b> לְדָוִד", "<b>שִׁיר</b> הַמַּעֲלוֹת",
                                         "", "<b>קדושה</b>", "<b>נַקְדִּישָׁךְ</b> וְנַעֲרִיצָךְ", "<b>קָדוֹשׁ</b> קָדוֹשׁ",
                                         "<b>תשובה</b>", "<b>הֲשִׁיבֵנוּ</b> אָבִינוּ"),
                    ("<small>On Sunday:</small>", "A psalm", "A song", "<small>When the Chazzan repeats:</small>",
                     "<b>Kedushah</b>", "We will hallow", "Holy", "<b>REPENTANCE</b>", "Bring us back"))
        items = divide(align_leaf(leaf).pairs)
        urns = {id(b): f"{T}prayer:t{n}" for n, b in enumerate(i for i in items if isinstance(i, TextBlock))}
        en = parse(leaf_body(T + "siddur:x", ("L", "L"), items, urns, "en", Notes("n"), conditions=conditions()))
        gates = en.xpath("//j:conditional", namespaces=NS)
        self.assertEqual([g.xpath("string(tei:note)", namespaces=NS) for g in gates],
                         ["On Sunday:", "When the Chazzan repeats:"])
        inside = [[t.get("target").rsplit(":", 1)[-1] for t in en.xpath(
            f"//j:transclude[preceding-sibling::j:conditional[@xml:id='{g.get('{http://www.w3.org/XML/1998/namespace}id')}']]"
            f"[following-sibling::j:endConditional[@target='#{g.get('{http://www.w3.org/XML/1998/namespace}id')}']]",
            namespaces=NS)] for g in gates]
        self.assertEqual(inside, [["t0"], ["t2", "t3"]])


class TestFileStem(unittest.TestCase):
    def test_stems(self):
        self.assertEqual(file_stem(T + "prayer:amidah/avot"), "amidah_avot")
        self.assertEqual(file_stem(T + "siddur:chol/shacharit"), "siddur_chol_shacharit")


if __name__ == "__main__":
    unittest.main()
