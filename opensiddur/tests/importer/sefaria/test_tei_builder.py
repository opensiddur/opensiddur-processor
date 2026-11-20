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
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


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


class TestConditionScopes(unittest.TestCase):
    """How far a condition reaches inside a text, and where its parts go."""
    URN = T + "prayer:amidah/gevurot"

    def body(self, segments, numbers, lang):
        (block,) = blocks(segments)
        return parse(text_body(self.URN, block, numbers, lang, Notes("note"), conditions=conditions()))

    def test_replaced_words_that_open_the_next_phrase(self):
        # (בעשי"ת וּלְעֵלָּא מִכָּל) ends one phrase; the next opens with the words it replaces.
        segments = [("<b>לְעֵלָּא</b> (בעשי\"ת וּלְעֵלָּא מִכָּל)", "above"),
                    ("מִן כָּל בִּרְכָתָא", "all the blessings")]
        he = self.body(segments, [1, 2], "he")
        (negated,) = he.xpath("//j:conditional[j:none]", namespaces=NS)
        self.assertEqual(negated.xpath("j:none/tei:fs/tei:f/@name", namespaces=NS), ["aseret-ymei-tshuva"])
        # It is in the second phrase, around its opening words only.
        self.assertEqual(negated.xpath("preceding-sibling::tei:milestone[@unit='phrase'][1]/@corresp",
                                       namespaces=NS), [T + "metsudah:amidah/gevurot/2"])
        self.assertEqual(negated.tail, to_nfkd("מִן כָּל"))
        # Nor when the words it replaces were found before it in its own phrase.
        before = [("שָׁלוֹם (בעשי\"ת הַשָּׁלוֹם)", "peace"), ("שָׁלוֹם עָלֵינוּ", "peace upon us")]
        negated = self.body(before, [1, 2], "he").xpath("//j:conditional[j:none]", namespaces=NS)
        self.assertEqual(len(negated), 1)
        # Nothing carries past a phrase that does not open with them.
        segments[1] = ("בִּרְכָתָא", "blessings")
        self.assertEqual(self.body(segments, [1, 2], "he").xpath("//j:conditional[j:none]", namespaces=NS), [])

    def test_a_rubric_leading_into_a_passage_stays_inside_it(self):
        segments = [("<b>אַתָּה גִבּוֹר</b>", "You are mighty"),
                    ("", "<small>During the Ten Days of Penitence add:</small>"),
                    ("", "<small>Chazzan:</small>"),
                    ("<small>מִי כָמוֹךָ</small>", "Who is like You"),
                    ("", "<small>Congregation:</small>"),
                    ("וְנֶאֱמָן אַתָּה", "And You are faithful")]
        en = self.body(segments, [1, 2, 3], "en")
        inside = en.xpath("//tei:note[preceding-sibling::j:conditional][following-sibling::j:endConditional]",
                          namespaces=NS)
        self.assertEqual([n.xpath("string()") for n in inside], ["Chazzan:"])
        phrases = en.xpath("//tei:milestone[@unit='phrase'][preceding-sibling::j:conditional]"
                           "[following-sibling::j:endConditional]/@corresp", namespaces=NS)
        self.assertEqual(phrases, [T + "metsudah:amidah/gevurot/2"])

    def test_a_passage_through_the_words_that_end_it(self):
        import re as _re
        from opensiddur.importer.sefaria.conditions import Conditions, RubricCondition
        from opensiddur.importer.util.incipit import words
        table = Conditions(rubrics=(RubricCondition(_re.compile("^When the Chazzan repeats"),
                                                    {"recitation": {"repetition": True}},
                                                    through=tuple(words("בָּרוּךְ אֵל הַהוֹדָאוֹת"))),))
        segments = [("<b>מוֹדִים</b> אֲנַחְנוּ לָךְ", "We thank You"), ("", "<small>When the Chazzan repeats:</small>"),
                    ("מוֹדִים אֲנַחְנוּ לָךְ", "We thank You"), ("בָּרוּךְ אֵל", "Blessed is the Almighty"),
                    ("הַהוֹדָאוֹת:", "of thanks"), ("וְעַל כֻּלָּם", "And for all these")]
        (block,) = blocks(segments)
        for lang in ("he", "en"):
            body = parse(text_body(self.URN, block, [1, 2, 3, 4, 5], lang, Notes("n"), conditions=table))
            inside = body.xpath("//tei:milestone[@unit='phrase'][preceding-sibling::j:conditional]"
                                "[following-sibling::j:endConditional]/@corresp", namespaces=NS)
            self.assertEqual([u.rsplit("/", 1)[-1] for u in inside], ["2", "3", "4"], lang)

    def test_a_footnote_on_a_condition_rubric_is_anchored_after_the_conditional(self):
        segments = [("<b>אַתָּה גִבּוֹר</b>", "You are mighty"),
                    ("", '<small>During the Ten Days add:</small><sup class="footnote-marker">1</sup>'
                         '<i class="footnote">A note.</i>'),
                    ("מִי כָמוֹךָ", "Who is like You")]
        en = self.body(segments, [1, 2], "en")
        (anchor,) = en.xpath("//tei:anchor", namespaces=NS)
        self.assertEqual(anchor.xpath("local-name(preceding-sibling::*[1])"), "conditional")
        self.assertEqual(en.xpath("//j:conditional/tei:anchor", namespaces=NS), [])


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

    def test_a_label_on_a_line_of_its_own_conditions_the_words_after_it(self):
        segments = [("<b>וְאֶת</b> מוּסַף", "And the Musaf-offering of"),
                    ("<small>לר\"ח</small>", "<small>On Rosh Chodesh:</small>"),
                    ("רֹאשׁ הַחֹדֶשׁ הַזֶּה", "this Rosh Chodesh")]
        for lang in ("he", "en"):
            body = self.body(segments, [1, 2], lang)
            self.assertEqual(body.xpath("//j:conditional/tei:fs/tei:f/@name", namespaces=NS), ["rosh-hodesh"])

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


def assert_nested(test, xml):
    stack = []
    for e in parse(xml).iter():
        if e.tag.endswith("}conditional"):
            stack.append("#" + e.get("{http://www.w3.org/XML/1998/namespace}id"))
        elif e.tag.endswith("}endConditional"):
            test.assertEqual(stack.pop(), e.get("target"))
    test.assertEqual(stack, [])


class TestNestingAndMarkup(unittest.TestCase):
    URN = T + "prayer:x"

    def test_a_parenthesis_closing_in_a_phrase_a_variant_leaves_out(self):
        from opensiddur.importer.sefaria.tei_builder import VariantPrinting

        segments = [("<b>אַתָּה</b> גִבּוֹר", "a"), ("", "<small>During the Ten Days add:</small>"),
                    ("(מִי כָמוֹךָ", "b"), ("זוֹכֵר יְצוּרָיו)", "c"), ("וְנֶאֱמָן אַתָּה", "d")]
        (block,) = blocks(segments)
        (later,) = blocks(segments[:3] + segments[4:])
        variant = VariantPrinting("v", later, [1, 2, 4])
        for lang in ("he", "en"):
            assert_nested(self, text_body(self.URN, block, [1, 2, 3, 4], lang, Notes("n"), (variant,),
                                          conditions=conditions()))

    def test_a_rubric_in_a_variants_passage_inside_a_condition(self):
        from opensiddur.importer.sefaria.tei_builder import VariantPrinting

        segments = [("<b>אַתָּה</b> גִבּוֹר", "a"), ("", "<small>During the Ten Days add:</small>"),
                    ("מִי כָמוֹךָ", "b"), ("וְנֶאֱמָן אַתָּה", "d")]
        (block,) = blocks(segments)
        (later,) = blocks(segments[:3] + [("", "<small>(bow)</small>"), ("פָּסוּק חָדָשׁ לְגַמְרֵי", "e")]
                          + segments[3:])
        variant = VariantPrinting("v", later, [1, 2, 4, 3])
        for lang in ("he", "en"):
            assert_nested(self, text_body(self.URN, block, [1, 2, 3], lang, Notes("n"), (variant,),
                                          conditions=conditions()))

    def test_markup_that_straddles_a_parenthesis_is_left_as_printed(self):
        for segment in ("<b>עֹשֶׂה</b> <small>(בעשי\"ת</small> הַשָּׁלוֹם) שָׁלוֹם",
                        "<b>עֹשֶׂה</b> (<small>בעשי\"ת הַשָּׁלוֹם</small>) שָׁלוֹם"):
            (block,) = blocks([(segment, "x")])
            parse(text_body(self.URN, block, [1], "he", Notes("n"), conditions=conditions()))

    def test_a_label_in_small_type_leaves_no_colon(self):
        (block,) = blocks([("<b>עֹשֶׂה</b> (<small>בעשי\"ת</small>: הַשָּׁלוֹם) שָׁלוֹם", "x")])
        he = parse(text_body(self.URN, block, [1], "he", Notes("n"), conditions=conditions()))
        self.assertNotIn(":", "".join(he.xpath("//j:conditional[@type='marked']/following-sibling::text()[1]",
                                                namespaces=NS)))


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

    def leaf(self, he, en, table, **kwargs):
        from opensiddur.importer.sefaria.tei_builder import leaf_body
        leaf = Leaf(("L",), (("L", "L"),), he, en)
        items = divide(align_leaf(leaf).pairs)
        urns = {id(b): f"{T}prayer:t{n}" for n, b in enumerate(i for i in items if isinstance(i, TextBlock))}
        return items, urns, lambda lang: parse(leaf_body(T + "siddur:x", ("L", "L"), items, urns, lang, Notes("n"),
                                                         conditions=table, **kwargs))

    @staticmethod
    def gated(body):
        return [[t.get("target").rsplit(":", 1)[-1] for t in body.xpath(
            f"//j:transclude[preceding-sibling::j:conditional[@xml:id='{g.get(XML_ID)}']]"
            f"[following-sibling::j:endConditional[@target='#{g.get(XML_ID)}']]", namespaces=NS)]
            for g in body.xpath("//j:conditional", namespaces=NS)]

    def test_a_section_runs_until_the_rubric_it_names(self):
        import re as _re
        from opensiddur.importer.sefaria.conditions import Conditions, RubricCondition
        table = Conditions(rubrics=(RubricCondition(_re.compile("^Tachanun is also omitted"),
                                                    {"override": {"omit-tahanun": False}}, section=True,
                                                    until=_re.compile("^The Chazzan recites the following Kaddish")),))
        _, _, body = self.leaf(
            ("", "<b>אָשַׁמְנוּ</b> בָּגַדְנוּ", "<b>וַיֹּאמֶר</b> דָּוִד", "", "<b>יִתְגַּדַּל</b> וְיִתְקַדַּשׁ"),
            ("<small>Tachanun is also omitted today.</small>", "We have trespassed", "And David said",
             "<small>The Chazzan recites the following Kaddish</small>", "Exalted"), table)
        self.assertEqual(self.gated(body("en")), [["t0", "t1"]])
        # A heading before that rubric does not end it.
        _, _, body = self.leaf(
            ("", "<b>אָשַׁמְנוּ</b> בָּגַדְנוּ", "<b>נפילת אפים</b>", "<b>וַיֹּאמֶר</b> דָּוִד", "",
             "<b>יִתְגַּדַּל</b> וְיִתְקַדַּשׁ"),
            ("<small>Tachanun is also omitted today.</small>", "We have trespassed", "<b>FALLING ON THE FACE</b>",
             "And David said", "<small>The Chazzan recites the following Kaddish</small>", "Exalted"), table)
        self.assertEqual(self.gated(body("en")), [["t0", "t1"]])

    def test_a_woman_says_makes_the_text_before_the_alternative(self):
        import re as _re
        from opensiddur.importer.sefaria.conditions import Conditions, RubricCondition
        female = {"person": {"gender": "female"}}
        table = Conditions(rubrics=(RubricCondition(_re.compile("^A woman says:"), female,
                                                    instead_of_previous=True),))
        _, _, body = self.leaf(("<b>שֶׁלֹּא</b> עָשַׂנִי אִשָּׁה", "", "<b>שֶׁעָשַׂנִי</b> כִּרְצוֹנוֹ"),
                               ("Who did not make me a woman", "<small>A woman says:</small>", "Who made me"), table)
        en = body("en")
        self.assertEqual(self.gated(en), [["t0"], ["t1"]])
        first, second = en.xpath("//j:conditional", namespaces=NS)
        self.assertEqual(first.xpath("j:none/tei:fs/tei:f/tei:symbol/@value", namespaces=NS), ["female"])
        self.assertEqual(second.xpath("tei:fs/tei:f/tei:symbol/@value", namespaces=NS), ["female"])

    def test_the_text_before_the_alternative_may_be_gated_already(self):
        import re as _re
        from opensiddur.importer.sefaria.conditions import Conditions, RubricCondition
        female = {"person": {"gender": "female"}}
        table = Conditions(rubrics=(RubricCondition(_re.compile("^On Sunday:"), {"day-of-week": {"hebrew-day": 1}}),
                                    RubricCondition(_re.compile("^A woman says:"), female, instead_of_previous=True)))
        _, _, body = self.leaf(("", "<b>שֶׁלֹּא</b> עָשַׂנִי אִשָּׁה", "", "<b>שֶׁעָשַׂנִי</b> כִּרְצוֹנוֹ"),
                               ("<small>On Sunday:</small>", "Who did not make me a woman",
                                "<small>A woman says:</small>", "Who made me"), table)
        en = body("en")
        self.assertEqual(self.gated(en), [["t0"], ["t0"], ["t1"]])
        etree.fromstring(etree.tostring(en))  # well-formed, the conditionals nested

    def test_a_text_printed_before_is_gated_by_the_condition_rubric_it_opens_with(self):
        items, urns, body = self.leaf(("<b>מִי</b> כָמוֹךָ", "", "<b>וְנֶאֱמָן</b> אַתָּה"),
                                      ("Who is like You", "<small>On Sunday:</small>", "And You are faithful"),
                                      conditions())
        # Make the leading rubric part of the block, as division does when a rubric opens it.
        from dataclasses import replace
        blocks_ = [i for i in items if isinstance(i, TextBlock)]
        rubric = next(i for i in items if not isinstance(i, TextBlock)).pairs[0]
        from opensiddur.importer.sefaria.tei_builder import leaf_body
        repeat = blocks_[1]
        en = parse(leaf_body(T + "siddur:x", ("L", "L"), [blocks_[0], repeat], urns, "en", Notes("n"),
                             conditions=conditions(), leading={id(repeat): rubric}))
        self.assertEqual(self.gated(en), [["t1"]])
        self.assertEqual(en.xpath("string(//j:conditional/tei:note)", namespaces=NS), "On Sunday:")


    def test_a_section_rubric_a_text_opens_with_gates_the_texts_after_it_to_its_end(self):
        # One day's introduction and psalm, cut apart, the day's rubric inside the first
        # block; the next block opens with the rubric the day runs to, then the next day's.
        import re as _re
        from opensiddur.importer.sefaria.conditions import Conditions, RubricCondition
        deliver = _re.compile("^\\(Deliver us")
        table = Conditions(rubrics=(
            RubricCondition(_re.compile("^On Sunday:"), {"day-of-week": {"hebrew-day": 1}}, section=True, until=deliver,
                            until_included=True),
            RubricCondition(_re.compile("^On Monday:"), {"day-of-week": {"hebrew-day": 2}}, section=True, until=deliver,
                            until_included=True)))
        items, urns, _ = self.leaf(("", "<b>הַיּוֹם</b> יוֹם רִאשׁוֹן", "<b>לְדָוִד</b> מִזְמוֹר", "", "",
                                    "<b>הַיּוֹם</b> יוֹם שֵׁנִי", "<b>שִׁיר</b> מִזְמוֹר"),
                                   ("<small>On Sunday:</small>", "Today is Sunday", "A psalm of David",
                                    "<small>(Deliver us...; Mourner's Kaddish.)</small>", "<small>On Monday:</small>",
                                    "Today is Monday", "A song"), table)
        intro1, psalm1, intro2, psalm2 = [i for i in items if isinstance(i, TextBlock)]
        sunday, deliver_us, monday = [pair for i in items if not isinstance(i, TextBlock)
                                      for pair in getattr(i, "pairs", ())]
        intro1.pairs[:0] = [sunday]
        intro2.pairs[:0] = [deliver_us, monday]
        from opensiddur.importer.sefaria.tei_builder import leaf_body
        en = parse(leaf_body(T + "siddur:x", ("L", "L"), [intro1, psalm1, intro2, psalm2], urns, "en", Notes("n"),
                             conditions=table, leading={id(intro1): sunday, id(intro2): monday}))
        self.assertEqual(self.gated(en), [["t0", "t1"], ["t2", "t3"]])
        # The rubric that closes Sunday's psalm is written in the place, at the end of Sunday's
        # gate, not in Monday's text.
        notes = en.xpath("//tei:note[@type='instruction']", namespaces=NS)
        deliver = [n for n in notes if "Deliver us" in "".join(n.itertext())]
        self.assertEqual(len(deliver), 1)
        following = deliver[0].xpath("following-sibling::*[1]", namespaces=NS)[0]
        self.assertEqual((etree.QName(following).localname, following.get("target")), ("endConditional", "#when_1"))


    def test_a_section_may_end_with_the_rubric_it_runs_to(self):
        # Wednesday's psalm, then "(Deliver us...)" and Thursday's rubric between texts: the
        # Kaddish rubric is Wednesday's, inside its gate.
        import re as _re
        from opensiddur.importer.sefaria.conditions import Conditions, RubricCondition
        deliver = _re.compile("^\\(Deliver us")
        table = Conditions(rubrics=(
            RubricCondition(_re.compile("^On Wednesday:"), {"day-of-week": {"hebrew-day": 4}}, section=True,
                            until=deliver, until_included=True),
            RubricCondition(_re.compile("^On Thursday:"), {"day-of-week": {"hebrew-day": 5}}, section=True,
                            until=deliver, until_included=True)))
        _, _, body = self.leaf(("", "<b>אֵל</b> נְקָמוֹת", "", "", "<b>לַמְנַצֵּחַ</b> עַל הַגִּתִּית"),
                               ("<small>On Wednesday:</small>", "God of vengeance",
                                "<small>(Deliver us...; Mourner's Kaddish.)</small>", "<small>On Thursday:</small>",
                                "For the conductor"), table)
        en = body("en")
        self.assertEqual(self.gated(en), [["t0"], ["t1"]])
        deliver_note = [n for n in en.xpath("//tei:note[@type='instruction']", namespaces=NS)
                        if "Deliver us" in "".join(n.itertext())][0]
        following = deliver_note.xpath("following-sibling::*[1]", namespaces=NS)[0]
        self.assertEqual((etree.QName(following).localname, following.get("target")), ("endConditional", "#when_1"))


class TestNodeGates(unittest.TestCase):
    def test_a_gated_child_is_transcluded_conditionally(self):
        from opensiddur.importer.sefaria.conditions import LeafGate
        from opensiddur.importer.sefaria.tei_builder import index_body, node_body
        from .support import WORK
        gate = LeafGate("w", "Morning / Torah", {"day-of-week": {"hebrew-day": 2}}, "On Mondays:")
        children = [T + "siddur:a", T + "siddur:b"]
        for lang in ("he", "en"):
            for body in (node_body(T + "siddur:n", ("N", "N"), children, lang, {T + "siddur:b": gate}),
                         index_body(WORK, children, lang, {T + "siddur:b": gate})):
                xml = parse(body)
                (conditional,) = xml.xpath("//j:conditional", namespaces=NS)
                self.assertEqual(xml.xpath("//j:transclude[preceding-sibling::j:conditional]/@target",
                                           namespaces=NS), [T + "siddur:b"])
                self.assertEqual(conditional.xpath("string(tei:note)", namespaces=NS),
                                 "On Mondays:" if lang == "en" else "")


class TestSourceBibl(unittest.TestCase):
    def test_the_translator_is_the_bibl_author_not_a_respstmt(self):
        from opensiddur.importer.sefaria.tei_builder import SourceInfo, source_bibl
        from .support import WORK
        info = SourceInfo("2026-11-01T00:00:00", {"he": "https://x/he", "en": "https://x/en"},
                          {"he": "a", "en": "b"})
        for lang in ("he", "en"):
            bibl = parse(source_bibl(WORK, lang, info))
            self.assertEqual(bibl.xpath("//tei:bibl/tei:author/text()", namespaces=NS), [WORK.translator])
            self.assertEqual(bibl.xpath("//tei:respStmt", namespaces=NS), [])


class TestFileStem(unittest.TestCase):
    def test_stems(self):
        self.assertEqual(file_stem(T + "prayer:amidah/avot"), "amidah_avot")
        self.assertEqual(file_stem(T + "siddur:chol/shacharit"), "siddur_chol_shacharit")
        self.assertEqual(file_stem(T + "bible:psalms/3/2-9"), "psalms_3_2_9")
        self.assertEqual(file_stem(T + "poem:hamavdil", frozenset({"hamavdil"})), "poem_hamavdil")
        self.assertEqual(file_stem(T + "prayer:hamavdil", frozenset({"hamavdil"})), "hamavdil")


if __name__ == "__main__":
    unittest.main()
