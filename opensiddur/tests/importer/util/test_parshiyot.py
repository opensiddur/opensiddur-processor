import json
import unittest

from opensiddur.importer.util.parshiyot import (
    COMBINED_PARSHIYOT,
    HEBCAL_TO_SLUG,
    PARSHA_NAMES,
    SLUG_TO_HEBREW,
    canonical_hebrew,
    hebcal_for_hebrew,
    skeleton_map_json,
    slug_for_hebrew,
    slugify_reading_name,
)


class TestParshaTable(unittest.TestCase):
    def test_fifty_four_parshiyot(self):
        self.assertEqual(54, len(PARSHA_NAMES))

    def test_slugs_are_unique(self):
        slugs = [slug for _, _, slug in PARSHA_NAMES]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_hebrew_names_are_unique(self):
        names = [hebrew for hebrew, _, _ in PARSHA_NAMES]
        self.assertEqual(len(names), len(set(names)))

    def test_slugs_are_urn_safe(self):
        for _, _, slug in PARSHA_NAMES:
            with self.subTest(slug=slug):
                self.assertRegex(slug, r"^[a-z][a-z_]*[a-z]$")

    def test_combined_parshiyot_are_in_the_hebcal_map(self):
        for hebcal_name, slug in COMBINED_PARSHIYOT:
            self.assertEqual(slug, HEBCAL_TO_SLUG[hebcal_name])

    def test_slug_to_hebrew_round_trips(self):
        for hebrew, _, slug in PARSHA_NAMES:
            self.assertEqual(hebrew, SLUG_TO_HEBREW[slug])


class TestLookupByHebrew(unittest.TestCase):
    def test_canonical_spelling_resolves(self):
        for hebrew, hebcal, slug in PARSHA_NAMES:
            with self.subTest(hebrew=hebrew):
                self.assertEqual(hebrew, canonical_hebrew(hebrew))
                self.assertEqual(slug, slug_for_hebrew(hebrew))
                self.assertEqual(hebcal, hebcal_for_hebrew(hebrew))

    def test_pointing_is_ignored(self):
        self.assertEqual("noach", slug_for_hebrew("נֹחַ"))
        self.assertEqual("lech_lecha", slug_for_hebrew("לֶךְ־לְךָ"))

    def test_jps1917_spellings_resolve(self):
        # The 1917 scans write the names unpointed, and write the maqaf as a space or not
        # at all. Each of these is the exact @n the jps1917 importer produced before the fix.
        cases = {
            "לךלך": ("לך־לך", "lech_lecha"),
            "כי תצא": ("כי־תצא", "ki_teitzei"),
            "כי תבוא": ("כי־תבוא", "ki_tavo"),
            "נח": ("נֹח", "noach"),
            "בא": ("בֹא", "bo"),
            "תולדות": ("תולדֹת", "toldot"),
            "אמור": ("אמֹר", "emor"),
            "קדשים": ("קדֹשים", "kedoshim"),
            "בחקתי": ("בחֻקֹתי", "bechukotai"),
            "בהעלתך": ("בהעלֹתך", "behaalotcha"),
            "מצרע": ("מצֹרע", "metzora"),
            "נשא": ("נשֹא", "nasso"),
            "שפטים": ("שֹפטים", "shoftim"),
            "נצבים": ("נִצבים", "nitzavim"),
            "וזאת הברכה": ("וזאת הברכה", "vezot_haberakhah"),
        }
        for written, (expected_name, expected_slug) in cases.items():
            with self.subTest(written=written):
                self.assertEqual(expected_name, canonical_hebrew(written))
                self.assertEqual(expected_slug, slug_for_hebrew(written))

    def test_similar_names_are_not_conflated(self):
        # Every pair below shares a consonant skeleton prefix or a mater lectionis with
        # another parshah; folding too aggressively would merge them.
        self.assertNotEqual(slug_for_hebrew("שלח"), slug_for_hebrew("וישלח"))
        self.assertNotEqual(slug_for_hebrew("כי תשא"), slug_for_hebrew("כי תצא"))
        self.assertNotEqual(slug_for_hebrew("כי תצא"), slug_for_hebrew("כי תבוא"))

    def test_unknown_name_raises(self):
        # The Psalm 119 acrostic letters must not resolve to a parshah.
        for letter in ("א", "ב", "ת"):
            with self.subTest(letter=letter):
                with self.assertRaises(KeyError):
                    slug_for_hebrew(letter)
        with self.assertRaises(KeyError):
            canonical_hebrew("Parashat Bereshit")


class TestSkeletonMapJson(unittest.TestCase):
    def test_every_parshah_is_reachable(self):
        table = json.loads(skeleton_map_json())
        slugs = {entry["slug"] for entry in table.values()}
        self.assertEqual({slug for _, _, slug in PARSHA_NAMES}, slugs)

    def test_entries_carry_the_canonical_name(self):
        table = json.loads(skeleton_map_json())
        for hebrew, _, slug in PARSHA_NAMES:
            entry = next(e for e in table.values() if e["slug"] == slug)
            self.assertEqual(hebrew, entry["n"])

    def test_jps1917_spellings_are_keys(self):
        table = json.loads(skeleton_map_json())
        # The XSLT strips everything but Hebrew letters before looking a name up, so the
        # skeleton of a source spelling must be a key.
        self.assertEqual("lech_lecha", table["לךלך"]["slug"])
        self.assertEqual("toldot", table["תולדות"]["slug"])

    def test_acrostic_letters_are_not_keys(self):
        table = json.loads(skeleton_map_json())
        for letter in ("א", "ב", "ג", "ת"):
            self.assertNotIn(letter, table)


class TestSlugifyReadingName(unittest.TestCase):
    def test_festival_names(self):
        self.assertEqual("rosh_hashanah_i", slugify_reading_name("Rosh Hashana I"))
        self.assertEqual("shabbat_chol_hamoed", slugify_reading_name("Shabbat Chol Hamoed"))

    def test_punctuation_is_dropped(self):
        self.assertEqual("fast_day_afternoon", slugify_reading_name("Fast Day (Afternoon)"))
        self.assertEqual("purim_on_shabbat", slugify_reading_name("Purim (on Shabbat),"))

    def test_apostrophes_are_dropped_not_replaced(self):
        self.assertEqual("sukkot_shabbat_chol_hamoed", slugify_reading_name(
            "Sukkot Shabbat Chol Hamoed"))
        self.assertEqual("erev_rosh_hashanah", slugify_reading_name("Erev Rosh Hashana"))
        self.assertEqual("shmini_atzeret", slugify_reading_name("Shmini Atzeret"))
        self.assertEqual("reeh", slugify_reading_name("Re'eh"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
