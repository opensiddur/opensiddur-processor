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


class TestFileStem(unittest.TestCase):
    def test_stems(self):
        self.assertEqual(file_stem(T + "prayer:amidah/avot"), "amidah_avot")
        self.assertEqual(file_stem(T + "siddur:chol/shacharit"), "siddur_chol_shacharit")


if __name__ == "__main__":
    unittest.main()
