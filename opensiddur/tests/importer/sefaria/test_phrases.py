import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.sefaria.phrases import (
    clashing_paths,
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

    def test_a_run_of_verses_is_not_spelled_as_a_range(self):
        from opensiddur.exporter.urn import split_range
        urn = phrase_urn(T + "bible:proverbs/31/10-31", 2)
        self.assertEqual(urn, T + "metsudah:proverbs/31/10_31/2")
        self.assertIsNone(split_range(urn))

    def test_a_path_two_namespaces_use_is_kept_by_prayer(self):
        clashes = clashing_paths([T + "prayer:hamavdil", T + "poem:hamavdil", T + "poem:adon_olam",
                                  T + "siddur:hamavdil", "urn:x-opensiddur:contributor:x/hamavdil"])
        self.assertEqual(clashes, frozenset({"hamavdil"}))
        self.assertEqual(phrase_urn(T + "prayer:hamavdil", 2, clashes), T + "metsudah:hamavdil/2")
        self.assertEqual(phrase_urn(T + "poem:hamavdil", 2, clashes), T + "metsudah:poem/hamavdil/2")
        # a poem whose path no other namespace uses keeps the bare path
        self.assertEqual(phrase_urn(T + "poem:adon_olam", 1, clashes), T + "metsudah:adon_olam/1")
        self.assertEqual(split_phrase_urn(T + "metsudah:poem/hamavdil/2"), ("poem/hamavdil", 2))

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

    def test_the_order_is_the_printings_not_the_numbers(self):
        # Phrase 3 was added after the first printing's own (an earlier volume named 1 and 2),
        # between them: a later printing in the same words keeps every number.
        old = {1: skeleton("מוֹדֶה אֲנִי לְפָנֶֽיךָ"), 3: skeleton("שֶׁהֶחֱזַֽרְתָּ בִּי נִשְׁמָתִי"),
               2: skeleton("מֶֽלֶךְ חַי וְקַיָּם")}
        self.assertEqual(map_phrases(list(old.values()), old), [1, 3, 2])


class TestRecordedPhrases(unittest.TestCase):
    def test_reads_phrase_milestones_and_their_words(self):
        xml = ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he"><tei:teiHeader/>'
               '<tei:text><tei:body><tei:div corresp="urn:x-opensiddur:text:prayer:modeh_ani"><tei:p>'
               f'<tei:milestone unit="phrase" corresp="{T}metsudah:modeh_ani/1"/>מוֹדֶה אֲנִי'
               '<tei:note type="instruction">not words</tei:note> '
               f'<tei:milestone unit="phrase" corresp="{T}metsudah:modeh_ani/2"/><tei:hi rend="small">מֶֽלֶךְ</tei:hi> '
               '<tei:choice><tei:sic>חַי</tei:sic><tei:corr>חַי וְקַיָּם</tei:corr></tei:choice>'
               '</tei:p></tei:div></tei:body></tei:text></tei:TEI>')
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "p"
            project.mkdir()
            (project / "modeh_ani.xml").write_text(xml, encoding="utf-8")
            found = recorded_phrases([project])
        self.assertEqual(found, {"modeh_ani": {1: skeleton("מוֹדֶה אֲנִי"), 2: skeleton("מֶֽלֶךְ חַי וְקַיָּם")}})

    def test_the_order_across_projects_is_the_fullest_printings(self):
        # The first project transcludes the text the full Kaddish opens with, and holds only the
        # phrases after it (and one of its own); the second prints it whole.
        words = {1: "יִתְגַּדַּל", 2: "בְּעָלְמָא", 3: "יְהֵא", 4: "יִתְבָּרַךְ", 5: "תִּתְקַבַּל", 6: "וְיַצְמַח"}

        def project(root, name, numbers):
            milestones = "".join(f'<tei:milestone unit="phrase" corresp="{T}metsudah:kaddish/shalem/{n}"/>{words[n]} '
                                 for n in numbers)
            (root / name).mkdir()
            (root / name / "kaddish_shalem.xml").write_text(
                '<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he"><tei:teiHeader/><tei:text>'
                f'<tei:body><tei:div><tei:p>{milestones}</tei:p></tei:div></tei:body></tei:text></tei:TEI>',
                encoding="utf-8")
            return root / name
        with tempfile.TemporaryDirectory() as tmp:
            found = recorded_phrases([project(Path(tmp), "a", [3, 4, 6]), project(Path(tmp), "b", [1, 2, 3, 4, 5])])
        self.assertEqual(list(found["kaddish/shalem"]), [1, 2, 3, 4, 6, 5])
        # Mapped against it, a whole printing keeps every number.
        self.assertEqual(map_phrases([found["kaddish/shalem"][n] for n in (1, 2, 3, 4, 5)], found["kaddish/shalem"]),
                         [1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main()
