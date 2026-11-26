"""Tests for checking the authored text against the reading.

Every fixture is synthetic. Asserting on the committed reading would test the data rather
than the code, and CI does not initialise the submodule that holds it.
"""
import pathlib
import tempfile
import unittest

from opensiddur.importer.birnbaum_scan import reverse


class TestPagesOfAPrayer(unittest.TestCase):
    def test_text_before_the_first_break_is_on_the_first_page(self):
        self.assertEqual(reverse.pages_of("<tei:p>אַלֶף בֵּית</tei:p>", 3),
                         {3: ["אַלֶף", "בֵּית"]})

    def test_a_break_moves_what_follows_to_the_page_it_names(self):
        body = '<tei:p>אַלֶף <tei:pb n="5" ed="x"/>בֵּית</tei:p>'
        self.assertEqual(reverse.pages_of(body, 3), {3: ["אַלֶף"], 5: ["בֵּית"]})

    def test_removed_markup_leaves_a_space(self):
        # Deleting a tag between two words joins them into one token, which is the same
        # mistake `strip_markup` had to be corrected for.
        body = "<tei:p>אַלֶף</tei:p><tei:p>בֵּית</tei:p>"
        self.assertEqual(reverse.pages_of(body, 3), {3: ["אַלֶף", "בֵּית"]})


class TestTheCheck(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def write(self, page, text):
        (self.dir / f"{page}.txt").write_text(text, encoding="utf-8")

    def prayer(self, body, first=3):
        return dict(name="x", body=body, first=first)

    def test_agreement_reports_nothing(self):
        self.write(3, "אַלֶף בֵּית")
        self.assertEqual(
            reverse.check([self.prayer("<tei:p>אַלֶף בֵּית</tei:p>")], self.dir, [3]), {})

    def test_a_dropped_word_is_reported(self):
        self.write(3, "אַלֶף בֵּית")
        report = reverse.check([self.prayer("<tei:p>אַלֶף</tei:p>")], self.dir, [3])
        self.assertIn(3, report)
        self.assertIn("-בֵּית", report[3])

    def test_a_single_wrong_point_is_reported(self):
        # The defect this was built for: `לְהָנִיחַ` for `לְהַנִֽיחַ` in a file that
        # validated, resolved and compiled.
        self.write(3, "לְהַנִֽיחַ")
        report = reverse.check([self.prayer("<tei:p>לְהָנִיחַ</tei:p>")], self.dir, [3])
        self.assertIn(3, report)

    def test_words_on_the_wrong_page_are_reported_on_both(self):
        self.write(3, "אַלֶף")
        self.write(5, "בֵּית")
        report = reverse.check([self.prayer("<tei:p>אַלֶף בֵּית</tei:p>")], self.dir, [3, 5])
        self.assertEqual(sorted(report), [3, 5])

    def test_a_declared_transclusion_is_not_counted_against_the_unit(self):
        self.write(3, "אַלֶף גִּימֶל בֵּית")
        reverse.TRANSCLUDED[3] = ("גִּימֶל",)
        try:
            self.assertEqual(
                reverse.check([self.prayer("<tei:p>אַלֶף בֵּית</tei:p>")], self.dir, [3]), {})
        finally:
            del reverse.TRANSCLUDED[3]

    def test_a_declared_transclusion_the_reading_does_not_have_is_reported(self):
        # A stale declaration would otherwise silently excuse a real omission.
        self.write(3, "אַלֶף בֵּית")
        reverse.TRANSCLUDED[3] = ("דָּלֶת",)
        try:
            report = reverse.check([self.prayer("<tei:p>אַלֶף בֵּית</tei:p>")], self.dir, [3])
            self.assertIn(3, report)
        finally:
            del reverse.TRANSCLUDED[3]


if __name__ == "__main__":
    unittest.main()
