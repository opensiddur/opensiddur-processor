"""A section's URN: under `haggadah:`, or a shared text's own."""
import unittest

from opensiddur.importer.feinstein_haggadah.sections import SHARED_PARAGRAPHS, SHARED_TEXTS, urn_for_section


class UrnForSectionTestCase(unittest.TestCase):
    def test_a_haggadah_section_and_its_paragraphs_are_under_haggadah(self):
        self.assertEqual(urn_for_section("index"), "urn:x-opensiddur:text:haggadah:haggadah")
        self.assertEqual(urn_for_section("maggid"), "urn:x-opensiddur:text:haggadah:maggid")
        self.assertEqual(urn_for_section("maggid", paragraph=2), "urn:x-opensiddur:text:haggadah:maggid/2")

    def test_a_shared_text_is_named_by_its_own_urn(self):
        for slug, urn in SHARED_TEXTS.items():
            with self.subTest(slug=slug):
                self.assertEqual(urn_for_section(slug), urn)
                self.assertFalse(urn.startswith("urn:x-opensiddur:text:haggadah:"))

    def test_a_shared_texts_paragraph_has_no_urn(self):
        # The text is one paragraph, which its own URN already names.
        self.assertIsNone(urn_for_section("psalm_115", paragraph=1))

    def test_a_shared_paragraph_is_named_by_its_own_urn_and_the_rest_keep_theirs(self):
        for (slug, paragraph), urn in SHARED_PARAGRAPHS.items():
            with self.subTest(slug=slug, paragraph=paragraph):
                self.assertEqual(urn_for_section(slug, paragraph=paragraph), urn)
        self.assertEqual(urn_for_section("barekh"), "urn:x-opensiddur:text:haggadah:barekh")
        self.assertEqual(urn_for_section("barekh", paragraph=30), "urn:x-opensiddur:text:haggadah:barekh/30")


if __name__ == "__main__":
    unittest.main()
