import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.sefaria.phrases import (
    map_phrases,
    phrase_urn,
    recorded_phrases,
    skeleton,
    split_phrase_urn,
    text_path,
)

T = "urn:x-opensiddur:text:"


class TestPhraseUrns(unittest.TestCase):
    def test_shaped_like_the_text_not_the_volume(self):
        self.assertEqual(phrase_urn(T + "prayer:amidah/avot", 3), T + "metsudah:amidah/avot/3")
        self.assertEqual(phrase_urn(T + "bible:psalms/145", 1), T + "metsudah:psalms/145/1")
        self.assertEqual(text_path(T + "poem:adon_olam@some-project"), "adon_olam")

    def test_only_text_namespaces(self):
        with self.assertRaises(ValueError):
            text_path(T + "siddur:chol/shacharit")
        with self.assertRaises(ValueError):
            text_path("urn:x-opensiddur:instruction:rise")

    def test_split(self):
        self.assertEqual(split_phrase_urn(T + "metsudah:amidah/avot/3"), ("amidah/avot", 3))
        with self.assertRaises(ValueError):
            split_phrase_urn(T + "metsudah:amidah")


class TestMapPhrases(unittest.TestCase):
    def test_nothing_recorded_numbers_in_order(self):
        self.assertEqual(map_phrases(["a", "b"], {}), [1, 2])

    def test_same_phrases_keep_their_numbers(self):
        old = {1: skeleton("מוֹדֶה אֲנִי לְפָנֶֽיךָ"), 2: skeleton("מֶֽלֶךְ חַי וְקַיָּם")}
        new = [skeleton("מוֹדֶה אֲנִי לְפָנֶיךָ"), skeleton("מֶלֶךְ חַי וְקַיָּם")]
        self.assertEqual(map_phrases(new, old), [1, 2])

    def test_a_mostly_similar_phrase_keeps_its_number(self):
        # Another rite's wording of the same phrase (one word differs) is the same phrase.
        old = {1: skeleton("שִׂים שָׁלוֹם טוֹבָה וּבְרָכָה חֵן וָחֶסֶד וְרַחֲמִים")}
        new = [skeleton("שִׂים שָׁלוֹם טוֹבָה וּבְרָכָה חַיִּים חֵן וָחֶסֶד וְרַחֲמִים")]
        self.assertEqual(map_phrases(new, old), [1])

    def test_an_added_phrase_is_numbered_after_the_last(self):
        old = {1: skeleton("מוֹדֶה אֲנִי לְפָנֶֽיךָ"), 2: skeleton("מֶֽלֶךְ חַי וְקַיָּם")}
        new = [skeleton("מוֹדֶה אֲנִי לְפָנֶֽיךָ"), skeleton("שֶׁהֶחֱזַֽרְתָּ בִּי נִשְׁמָתִי"),
               skeleton("מֶֽלֶךְ חַי וְקַיָּם")]
        self.assertEqual(map_phrases(new, old), [1, 3, 2])


class TestRecordedPhrases(unittest.TestCase):
    def test_reads_phrase_milestones_and_their_words(self):
        xml = ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he"><tei:teiHeader/>'
               '<tei:text><tei:body><tei:div corresp="urn:x-opensiddur:text:prayer:modeh_ani"><tei:p>'
               f'<tei:milestone unit="phrase" corresp="{T}metsudah:modeh_ani/1"/>מוֹדֶה אֲנִי'
               '<tei:note type="instruction">not words</tei:note> '
               f'<tei:milestone unit="phrase" corresp="{T}metsudah:modeh_ani/2"/><tei:hi rend="small">מֶֽלֶךְ</tei:hi>'
               '</tei:p></tei:div></tei:body></tei:text></tei:TEI>')
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "p"
            project.mkdir()
            (project / "modeh_ani.xml").write_text(xml, encoding="utf-8")
            found = recorded_phrases([project])
        self.assertEqual(found, {"modeh_ani": {1: skeleton("מוֹדֶה אֲנִי"), 2: skeleton("מֶֽלֶךְ")}})


if __name__ == "__main__":
    unittest.main()
