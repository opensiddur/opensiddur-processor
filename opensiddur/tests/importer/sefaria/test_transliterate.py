import unittest

from opensiddur.common.validate_names import Spellings
from opensiddur.importer.util.transliterate import name_from_hebrew, transliterate


class TestTransliterate(unittest.TestCase):
    def test_table(self):
        cases = {
            "מוֹדֶה אֲנִי לְפָנֶֽיךָ": ["modeh", "ani", "lefanekha"],
            "אַשְׁרֵי יוֹשְׁ֒בֵי": ["ashrei", "yoshevei"],
            "הַלְ֒לוּיָהּ": ["haleluyah"],
            "בָּרוּךְ אַתָּה יְהֹוָה": ["barukh", "attah", "adonai"],
            "הוֹדוּ לַיהוָֹה": ["hodu", "ladonai"],
            "מִצְוֹתָיו": ["mitzvotav"],
            # A vav with holam after a vowelled letter is a consonant, however the holam is set.
            "עָוֹן וְשָׁלוֹם": ["avon", "veshalom"],
            "עֲוֺנֵינוּ": ["avoneinu"],
            "עֲו\u200dֹנוֹת": ["avonot"],
            "מִלְּ֒פָנֶֽיךָ": ["milefanekha"],
            "מִלְּפָנֶֽיךָ": ["milefanekha"],
            "שַׁבָּת": ["shabbat"],
            "עַל־הַצַּדִּיקִים": ["al", "hatzaddiqim"],
            "תְּהִלָּה לְדָוִד": ["tehillah", "ledavid"],
            "שְׁמַע יִשְׂרָאֵל": ["shema", "yisrael"],
        }
        for hebrew, expected in cases.items():
            with self.subTest(hebrew=hebrew):
                self.assertEqual(transliterate(hebrew), expected)

    def test_name_is_respelled(self):
        spellings = Spellings(frozenset(), {"modeh": "mode"})
        self.assertEqual(name_from_hebrew("מוֹדֶה אֲנִי לְפָנֶֽיךָ", 2, spellings), "mode_ani")


if __name__ == "__main__":
    unittest.main()
