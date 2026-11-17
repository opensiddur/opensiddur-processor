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


if __name__ == "__main__":
    unittest.main()
