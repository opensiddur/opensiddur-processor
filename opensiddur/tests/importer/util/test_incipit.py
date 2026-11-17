"""What the incipit index records of a document: openings, lengths, closings and transclusions.
Synthetic documents only."""

import unittest

from lxml import etree

from opensiddur.importer.util.incipit import IncipitIndex, index_document, words

T = "urn:x-opensiddur:text:"
TEI = "http://www.tei-c.org/ns/1.0"
J = "http://jewishliturgy.org/ns/jlptei/2"


def document(body: str) -> etree._Element:
    return etree.fromstring(f'<tei:TEI xmlns:tei="{TEI}" xmlns:j="{J}"><tei:text><tei:body>{body}'
                            "</tei:body></tei:text></tei:TEI>")


def indexed(*bodies: str) -> IncipitIndex:
    index = IncipitIndex()
    for body in bodies:
        index_document(index, document(body))
    index.open_with_parts()
    return index


SHORT = "מַשִּׁיב הָרוּחַ וּמוֹרִיד הַגָּשֶׁם"
LONG = ("מְכַלְכֵּל חַיִּים בְּחֶסֶד מְחַיֵּה מֵתִים בְּרַחֲמִים רַבִּים סוֹמֵךְ נוֹפְלִים וְרוֹפֵא חוֹלִים "
        "וּמַתִּיר אֲסוּרִים וּמְקַיֵּם אֱמוּנָתוֹ לִישֵׁנֵי עָפָר מִי כָמוֹךָ")
CLOSING = "בָּרוּךְ אַתָּה יְיָ מְחַיֵּה הַמֵּתִים"


class TestLengths(unittest.TestCase):
    def test_a_short_scope_records_how_many_words_are_its_own(self):
        index = indexed(f'<tei:div corresp="{T}prayer:g/a"><tei:p>{SHORT}</tei:p></tei:div>'
                        f'<tei:div corresp="{T}prayer:g/b"><tei:p>{LONG}</tei:p></tei:div>')
        self.assertEqual(index.length_of[T + "prayer:g/a"], 4)
        # The collected opening still runs on, so that a short part is found by its neighbours.
        self.assertGreater(len(index.incipit_of[T + "prayer:g/a"]), 4)
        self.assertEqual(index.own_opening(T + "prayer:g/a"), tuple(words(SHORT)))
        self.assertNotIn(T + "prayer:g/b", index.length_of)

    def test_a_milestone_scope_ends_at_the_next_of_its_unit(self):
        index = indexed(f'<tei:div><tei:p><tei:milestone unit="part" corresp="{T}prayer:g/a"/>{SHORT} '
                        f'<tei:milestone unit="part" corresp="{T}prayer:g/b"/>{LONG}</tei:p></tei:div>')
        self.assertEqual(index.length_of[T + "prayer:g/a"], 4)
        self.assertIn(T + "prayer:g/a", index.milestone_scoped)


    def test_a_milestone_scope_ends_with_its_division(self):
        index = indexed(f'<tei:div corresp="{T}bible:ps/1"><tei:p><tei:milestone unit="verse" corresp="{T}bible:ps/1/1"/>'
                        f'{SHORT}</tei:p></tei:div><tei:div corresp="{T}prayer:next"><tei:p>{LONG}</tei:p></tei:div>')
        self.assertEqual(index.length_of[T + "bible:ps/1/1"], 4)
        self.assertEqual(index.closing(T + "bible:ps/1/1"), tuple(words(SHORT)))


class TestTransclusions(unittest.TestCase):
    PARENT = (f'<tei:div corresp="{T}prayer:g"><j:transclude target="{T}prayer:g/first"/>'
              f'<tei:p>{SHORT}</tei:p><j:transclude target="{T}prayer:g/last"/></tei:div>')
    FIRST = f'<tei:div corresp="{T}prayer:g/first"><tei:p>{LONG}</tei:p></tei:div>'
    LAST = f'<tei:div corresp="{T}prayer:g/last"><tei:p>וְנֶאֱמָן אַתָּה {CLOSING}</tei:p></tei:div>'

    def test_a_text_that_opens_by_transcluding_is_indexed_by_its_first_part(self):
        index = indexed(self.PARENT, self.FIRST, self.LAST)
        self.assertEqual(index.opens_with[T + "prayer:g"], T + "prayer:g/first")
        self.assertIn(T + "prayer:g", index.compound)
        self.assertEqual(index.incipit_of[T + "prayer:g"], index.incipit_of[T + "prayer:g/first"])
        self.assertNotIn(T + "prayer:g", index.by_incipit.get(tuple(words(SHORT)), set()))

    def test_closing_and_inclusions_follow_the_transclusions(self):
        index = indexed(self.PARENT, self.FIRST, self.LAST)
        self.assertEqual(index.ends_with[T + "prayer:g"], T + "prayer:g/last")
        self.assertEqual(index.closing(T + "prayer:g")[-4:], tuple(words(CLOSING))[-4:])
        self.assertEqual(index.included(T + "prayer:g"), {T + "prayer:g/first", T + "prayer:g/last"})

    def test_a_conditional_transclusion_neither_opens_nor_ends_a_text(self):
        body = (f'<tei:div corresp="{T}prayer:h"><j:conditional xml:id="c1"><tei:fs type="opensiddur:x"/>'
                f'</j:conditional><j:transclude target="{T}prayer:h/sometimes"/><j:endConditional target="#c1"/>'
                f'<tei:p>{SHORT}</tei:p></tei:div>')
        index = indexed(body)
        self.assertNotIn(T + "prayer:h", index.opens_with)
        self.assertIn(T + "prayer:h/sometimes", index.included(T + "prayer:h"))


class TestWords(unittest.TestCase):
    def test_halleluyah_is_one_word_however_it_is_printed(self):
        self.assertEqual(words("הַֽלְלוּ יָהּ"), words("הַלְלוּיָהּ"))


class TestJson(unittest.TestCase):
    def test_round_trip_keeps_what_the_index_records(self):
        index = indexed(TestTransclusions.PARENT, TestTransclusions.FIRST, TestTransclusions.LAST,
                        f'<tei:div corresp="{T}prayer:s"><tei:p>{SHORT}</tei:p></tei:div>')
        again = IncipitIndex.from_json(index.to_json())
        for name in ("incipit_of", "opens_with", "compound", "length_of", "closing_of", "ends_with",
                     "includes", "milestone_scoped"):
            self.assertEqual(getattr(again, name), getattr(index, name), name)


if __name__ == "__main__":
    unittest.main()
