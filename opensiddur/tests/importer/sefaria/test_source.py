import unittest

from opensiddur.importer.sefaria.source import leaf_hashes, read_work_source

from .support import AMIDAH, make_index, make_source, make_version


class TestReadWorkSource(unittest.TestCase):
    def test_nodes_and_leaves_in_schema_order(self):
        source = make_source()
        self.assertEqual([n.path for n in source.nodes], ["Morning"])
        self.assertEqual([leaf.path for leaf in source.leaves],
                         ["Morning / Upon Arising", "Morning / Amidah", "Blessings"])
        amidah = source.leaves[1]
        self.assertEqual(amidah.titles, (("Morning", "שחרית"), ("Amidah", "עמידה")))
        self.assertEqual(amidah.he, tuple(h for h, _ in AMIDAH))
        self.assertEqual(amidah.en, tuple(e for _, e in AMIDAH))

    def test_a_depth_two_leaf_is_a_leaf_per_chapter(self):
        index = make_index({"Days": [("א", "a")]})
        index["schema"]["nodes"][0]["depth"] = 2
        he = make_version({"Days": [("א", "a")]}, "he")
        en = make_version({"Days": [("א", "a")]}, "en")
        he["text"]["Days"] = [["א", "ב"], ["ג"]]
        en["text"]["Days"] = [["a", "b"]]
        leaves = read_work_source(index, he, en).leaves
        self.assertEqual([leaf.path for leaf in leaves], ["Days / 1", "Days / 2"])
        self.assertEqual(leaves[1].en, ())

    def test_a_default_node_takes_its_parents_place(self):
        index = make_index({"Outer": {"default": [("א", "a")]}})
        he = make_version({"Outer": {"": [("א", "a")]}}, "he")
        en = make_version({"Outer": {"": [("א", "a")]}}, "en")
        leaves = read_work_source(index, he, en).leaves
        self.assertEqual([leaf.path for leaf in leaves], ["Outer"])
        self.assertEqual(leaves[0].he, ("א",))

    def test_leaf_hashes(self):
        hashes = leaf_hashes(make_source())
        self.assertEqual(hashes["Morning / Amidah"]["he_segments"], len(AMIDAH))
        self.assertNotEqual(hashes["Morning / Amidah"]["he"], hashes["Blessings"]["he"])


if __name__ == "__main__":
    unittest.main()
