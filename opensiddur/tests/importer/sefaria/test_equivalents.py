import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.sefaria.align import align_leaf
from opensiddur.importer.sefaria.blocks import Heading, Rubric, TextBlock, divide, is_heading
from opensiddur.importer.sefaria.equivalents import EquivalentsError, apply_joins, load_equivalents
from opensiddur.importer.sefaria.source import Leaf
from opensiddur.importer.util.incipit import words

T = "urn:x-opensiddur:text:"

TABLE = f"""
texts:
  - opens: למען תזכור
    urn: {T}prayer:shesh_zekhirot
  - opens: למען תזכור את יום צאתך
    leaf: Six
    urn: {T}prayer:six_longer
joins:
  - opens: זכור את אשר עשה לך עמלק
    leaf: Six
"""


def equivalents(text: str = TABLE):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "equivalents.yaml"
        path.write_text(text, encoding="utf-8")
        return load_equivalents(path)


def items(segments):
    leaf = Leaf(("Six",), (("Six", "Six"),), tuple(h for h, _ in segments), tuple(e for _, e in segments))
    return divide(align_leaf(leaf).pairs)


SIX = [
    ("<b>זכירת יציאת מצרים</b>", "<b>REMEMBERING THE EXODUS</b>"),
    ("<b>לְמַעַן תִּזְכֹּר</b> אֶת יוֹם צֵאתְךָ", "That you may remember"),
    ("<b>זכירת מחיית עמלק</b>", "<b>REMEMBERING AMALEK</b>"),
    ("<b>זָכוֹר</b> אֵת אֲשֶׁר עָשָׂה לְךָ עֲמָלֵק", "Remember what Amalek did"),
]


class TestEquivalents(unittest.TestCase):
    def test_the_longest_matching_choice_wins_and_a_leaf_limits_it(self):
        table = equivalents()
        opening = words("לְמַעַן תִּזְכֹּר אֶת יוֹם צֵאתְךָ מֵאֶרֶץ מִצְרַיִם")
        self.assertEqual(table.choice("Six", opening).urn, T + "prayer:six_longer")
        self.assertEqual(table.choice("Other", opening).urn, T + "prayer:shesh_zekhirot")
        self.assertIsNone(table.choice("Six", words("דָּבָר אַחֵר")))

    def test_a_list_of_leaves_finds_the_text_where_each_volume_prints_it(self):
        table = equivalents(f"""
texts:
  - opens: למען תזכור
    leaf: [Six, "Morning / Six"]
    urn: {T}prayer:shesh_zekhirot
""")
        opening = words("לְמַעַן תִּזְכֹּר אֶת יוֹם")
        self.assertEqual(table.choice("Morning / Six", opening).urn, T + "prayer:shesh_zekhirot")
        self.assertIsNone(table.choice("Other", opening))

    def test_a_joined_block_continues_the_text_before_it(self):
        found = apply_joins("Six", items(SIX), equivalents())
        (text,) = [i for i in found if isinstance(i, TextBlock)]
        self.assertEqual(len(text.phrases), 2)
        # The second heading is now a pair inside the text, naming the passage after it.
        self.assertTrue(any(is_heading(p) for p in text.pairs))
        self.assertFalse(any(isinstance(i, (Heading, Rubric)) for i in found[found.index(text) + 1:]))

    def test_a_join_applies_only_in_its_leaf(self):
        found = apply_joins("Elsewhere", items(SIX), equivalents())
        self.assertEqual(len([i for i in found if isinstance(i, TextBlock)]), 2)

    def test_a_bad_entry_is_an_error(self):
        with self.assertRaises(EquivalentsError):
            equivalents("texts:\n  - opens: אבג\n    urn: prayer:x\n")
        with self.assertRaises(EquivalentsError):
            equivalents("joins:\n  - opens: ''\n")
        # A string for ``with`` would be read letter by letter: a run in every block.
        with self.assertRaises(EquivalentsError):
            equivalents("texts:\n  - opens: אבג\n    with: דהו\n    urn: urn:x-opensiddur:text:prayer:x\n")


class TestEnds(unittest.TestCase):
    """A choice that names the words its text ends with (the Selichot's full Kaddish)."""
    TABLE = """
texts:
  - opens: יתגדל ויתקדש
    ends: עשה שלום במרומיו
    urn: urn:x-opensiddur:text:prayer:kaddish/shalem
"""

    def test_only_a_block_with_the_words_is_the_text(self):
        table = equivalents(self.TABLE)
        self.assertIsNotNone(table.choice("L", words("יִתְגַּדַּל וְיִתְקַדַּשׁ שְׁמֵהּ עֹשֶׂה שָׁלוֹם בִּמְרוֹמָיו")))
        self.assertIsNone(table.choice("L", words("יִתְגַּדַּל וְיִתְקַדַּשׁ שְׁמֵהּ רַבָּא")))

    def test_the_text_ends_after_the_phrase_its_words_end(self):
        (choice,) = equivalents(self.TABLE).texts
        phrases = [words("יִתְגַּדַּל וְיִתְקַדַּשׁ"), words("עֹשֶׂה שָׁלוֹם"), words("בִּמְרוֹמָיו"), words("אַחֵר")]
        self.assertEqual(choice.end(phrases), 3)
        self.assertIsNone(choice.end(phrases[:3]))  # the block ends with them: nothing to cut


class TestKaddishChoices(unittest.TestCase):
    """Each Kaddish whole, told apart by its ending and the words it has."""
    TABLE = """
texts:
  - opens: יתגדל ויתקדש
    ends: דאמירן בעלמא ואמרו אמן
    urn: urn:x-opensiddur:text:prayer:kaddish/chatzi
  - opens: יתגדל ויתקדש
    with: [תתקבל צלותהון]
    ends: ועל כל ישראל ואמרו אמן
    urn: urn:x-opensiddur:text:prayer:kaddish/shalem
  - opens: יתגדל ויתקדש
    ends: ועל כל ישראל ואמרו אמן
    urn: urn:x-opensiddur:text:prayer:kaddish/yatom
joins:
  - opens: יהא שמה רבא
    after: יתגדל ויתקדש
"""
    HALF = "יִתְגַּדַּל וְיִתְקַדַּשׁ שְׁמֵהּ יְהֵא שְׁמֵהּ רַבָּא יִתְבָּרַךְ דַּאֲמִירָן בְּעָלְמָא וְאִמְרוּ אָמֵן"
    PEACE = " יְהֵא שְׁלָמָא עָלֵינוּ וְעַל כָּל יִשְׂרָאֵל וְאִמְרוּ אָמֵן"

    def choice(self, text):
        return equivalents(self.TABLE).choice("L", words(text)).urn.rsplit("/", 1)[-1]

    def test_the_kaddish_that_reaches_furthest_with_its_words(self):
        self.assertEqual(self.choice(self.HALF), "chatzi")
        self.assertEqual(self.choice(self.HALF + self.PEACE), "yatom")
        self.assertEqual(self.choice(self.HALF + " תִּתְקַבֵּל צְלוֹתְהוֹן" + self.PEACE), "shalem")

    def test_a_part_joins_only_a_kaddish(self):
        table = equivalents(self.TABLE)
        self.assertTrue(table.joins_previous("L", words("יְהֵא שְׁמֵהּ רַבָּא"), words("יִתְגַּדַּל וְיִתְקַדַּשׁ שְׁמֵהּ")))
        self.assertFalse(table.joins_previous("L", words("יְהֵא שְׁמֵהּ רַבָּא"), words("בָּרְכוּ אֶת יְהֹוָה")))
        self.assertFalse(table.joins_previous("L", words("יְהֵא שְׁמֵהּ רַבָּא")))

    def test_a_kaddish_running_on_at_the_end_of_the_block_before(self):
        # Ashrei, and the half Kaddish after it in the same block.
        before = words("אַשְׁרֵי יוֹשְׁבֵי בֵיתֶךָ הַלְלוּיָהּ יִתְגַּדַּל וְיִתְקַדַּשׁ שְׁמֵהּ")
        self.assertTrue(equivalents(self.TABLE).joins_previous("L", words("יְהֵא שְׁמֵהּ רַבָּא"), before))


if __name__ == "__main__":
    unittest.main()
