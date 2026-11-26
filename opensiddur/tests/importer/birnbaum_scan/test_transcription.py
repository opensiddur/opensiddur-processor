# -*- coding: utf-8 -*-
"""Tests for resolving the Wikisource foundation text to what the 1949 print reads.

Every fixture here is synthetic. Asserting on the committed transcription would test the
data rather than the code, and CI does not initialise the submodule that holds it.
"""

import unittest

from opensiddur.importer.birnbaum_scan import transcription


class TestVariantResolution(unittest.TestCase):
    def test_a_named_birnbaum_parameter_is_the_reading(self):
        r = transcription.resolve("{{נוסח|אָבוֹא|בירנבוים=אָבֹא}}")
        self.assertEqual(r.text, "אָבֹא")
        self.assertEqual(r.substitutions, [("אָבוֹא", "אָבֹא")])

    def test_a_template_inside_a_template_closes_on_its_own_braces(self):
        # The Kaddish sets `{{נוסח|בְּאַתְרָא [{{ק|בארץ:}} קַדִּישָׁא]|בירנבוים=בְּאַתְרָא}}`.
        # A non-greedy `}}` closes on the inner template, takes half a word as the
        # positional and throws the `בירנבוים=` reading away -- silently, leaving a stray
        # bracket in the slice.
        r = transcription.resolve(
            "{{נוסח|בְּאַתְרָא [{{ק|בארץ:}} קַדִּישָׁא]|בירנבוים=בְּאַתְרָא}} הָדֵן"
        )
        self.assertEqual(r.text, "בְּאַתְרָא הָדֵן")

    def test_an_attribution_to_someone_else_still_defers_to_birnbaum(self):
        """`|=מסורה` says the positional is the Masorah's, not this book's."""
        r = transcription.resolve("{{נוסח|מְּאֹד|=מסורה|בירנבוים=מְאֹד}}")
        self.assertEqual(r.text, "מְאֹד")

    def test_an_attribution_to_birnbaum_makes_the_positional_the_reading(self):
        """The convention inverts here, and preferring a named parameter would take the
        variant. `אחרים=` is everyone who is *not* this book."""
        r = transcription.resolve("{{נוסח|הַרְהוֹר|=בירנבוים|אחרים=הִרְהוּר}}")
        self.assertEqual(r.text, "הַרְהוֹר")

    def test_an_attribution_naming_birnbaum_among_others_reads_the_same_way(self):
        r = transcription.resolve('{{נוסח|לְהַנִּֽיחַ|=בירנבוים ועבו"י|אחרים=לְהָנִֽיחַ}}')
        self.assertEqual(r.text, "לְהַנִּֽיחַ")

    def test_a_prose_note_is_not_substituted_into_the_text(self):
        """One of these is a sentence about how he sets two Torah portions. Substituting
        it would put a paragraph of Hebrew prose into the middle of a prayer, and the
        comparison would report it as the print's own words."""
        note = "בלי חלוקה בין שתי הפרשות, ואילו בתרגום האנגלי המקביל חילק ביניהן"
        r = transcription.resolve("{{נוסח|וְהָיָה|בירנבוים=" + note + "}}")
        self.assertEqual(r.text, "וְהָיָה")
        self.assertEqual(len(r.comments), 1)

    def test_a_short_note_is_not_mistaken_for_a_reading(self):
        """A four-word Hebrew sentence saying a full stop is missing passed the word cap
        and was substituted into the middle of a blessing. A variant replaces the text it
        is given against, so it is about as long as that text."""
        r = transcription.resolve("{{נוסח|תּוֹרָה.|בירנבוים=חסרה נקודה בסוף המשפט}}")
        self.assertEqual(r.text, "תּוֹרָה.")
        self.assertEqual(len(r.comments), 1)

    def test_a_two_word_variant_on_a_two_word_positional_is_still_a_reading(self):
        r = transcription.resolve("{{נוסח|אָ בּ|בירנבוים=גּ דּ}}")
        self.assertEqual(r.text, "גּ דּ")

    def test_a_template_with_no_birnbaum_parameter_keeps_its_positional(self):
        r = transcription.resolve("{{נוסח|שָׁלוֹם|אחרים=שָׁלֹם}}")
        self.assertEqual(r.text, "שָׁלוֹם")

    def test_text_outside_a_template_is_untouched(self):
        r = transcription.resolve("אַ {{נוסח|בּ|בירנבוים=גּ}} דּ")
        self.assertEqual(r.text, "אַ גּ דּ")


class TestMarkupStripping(unittest.TestCase):
    def test_nothing_but_text_and_separators_survives(self):
        """`compare` tokenises whatever it is handed, so a surviving brace is a word."""
        out = transcription.strip_markup(
            "{{#קטע:א/ב|ג}} [[תהלים לו/טעמים#לו ח|תהלים לו]] '''בּ''' <קטע התחלה=x/>")
        self.assertNotIn("{", out)
        self.assertNotIn("[", out)
        self.assertNotIn("<", out)
        self.assertNotIn("'", out)

    def test_removed_markup_leaves_a_word_boundary(self):
        """A tag between two words is a boundary. Deleting it outright joins them into
        one token, which `compare` reports as two consonantal differences, and the
        misalignment cascades through the rest of the page."""
        out = transcription.strip_markup("לְרֵאשִׁיתוֹ.<קטע סוף=א/><קטע התחלה=ב/>הִנּוֹ")
        self.assertEqual(out.split(), ["לְרֵאשִׁיתוֹ.", "הִנּוֹ"])

    def test_a_removed_transclusion_also_leaves_a_boundary(self):
        out = transcription.strip_markup("אָ{{#קטע:א/ב|ג}}בּ")
        self.assertEqual(out.split(), ["אָ", "בּ"])

    def test_a_piped_link_keeps_what_was_displayed(self):
        self.assertEqual(transcription.strip_markup("[[a/b#c|תהלים לו]]"), "תהלים לו")


class TestSectionExtraction(unittest.TestCase):
    def test_a_named_span_is_taken_whole(self):
        page = "x<קטע התחלה=מה טובו/>מַה טֹּֽבוּ<קטע סוף=מה טובו/>y"
        self.assertEqual(transcription.section(page, "מה טובו"), "מַה טֹּֽבוּ")

    def test_a_span_that_is_not_there_is_reported_as_missing(self):
        self.assertIsNone(transcription.section("x", "לא קיים"))

    def test_a_span_that_wraps_other_spans_is_taken_whole(self):
        # The outer span closes after the inner ones; stopping at the first end tag of any
        # name would return only the first half of the passage.
        page = (
            "<קטע התחלה=הכל/>"
            "<קטע התחלה=א/>רִאשׁוֹן<קטע סוף=א/>"
            " {{רובריקה}} "
            "<קטע התחלה=ב/>אַחֲרוֹן<קטע סוף=ב/>"
            "<קטע סוף=הכל/>"
        )
        whole = transcription.section(page, "הכל")
        self.assertIn("רִאשׁוֹן", whole)
        self.assertIn("אַחֲרוֹן", whole)


class TestSpanKinds(unittest.TestCase):
    """Only the print's own Hebrew words belong on either side of the comparison."""

    def test_prayer_words_are_taken(self):
        self.assertTrue(transcription.is_prayer_span("מה טובו"))
        self.assertTrue(transcription.is_prayer_span("אלו דברים מילים"))

    def test_a_rubric_is_not(self):
        # The edition renders Birnbaum's *English* rubrics into Hebrew, so there is
        # nothing on his Hebrew page to compare one against.
        self.assertFalse(transcription.is_prayer_span("הוראה כשמלובשים"))

    def test_a_heading_is_not(self):
        # He prints Hebrew headings, but they are read into `readings/`, not `hebrew/`.
        self.assertFalse(transcription.is_prayer_span("כותרת ברכות השחר"))

    def test_a_citation_is_not(self):
        # His citations are English footnotes; the edition sets them in the Hebrew column.
        self.assertFalse(transcription.is_prayer_span("פרשת התמיד מקור"))
        self.assertFalse(transcription.is_prayer_span("פיטום הקטורת מקורות"))
        self.assertFalse(transcription.is_prayer_span("מקור לאלו דברים"))


class TestPageSlice(unittest.TestCase):
    """A printed page of the edition, assembled from the spans it transcludes."""

    FOUNDATION = {
        "דף": (
            "<קטע התחלה=א/>אַלֶף<קטע סוף=א/>"
            "<קטע התחלה=ב/>בֵּית<קטע סוף=ב/>"
            "<קטע התחלה=כותרת ג/>כּוֹתֶֽרֶת<קטע סוף=כותרת ג/>"
        ),
    }

    def load(self, name):
        return self.FOUNDATION[name]

    def transclude(self, span):
        return "{{#קטע:ספר/אשכנז/דפי יסוד/דף|" + span + "}}"

    def test_the_text_between_two_transclusions_is_kept(self):
        # Printed page 1 joins five spans into one sentence with `. ` between them.
        page = self.transclude("א") + ". " + self.transclude("ב")
        self.assertEqual(self.slice(page).text, "אַלֶף. בֵּית")

    def test_a_line_of_the_page_is_a_line_of_the_slice(self):
        page = self.transclude("א") + "\n" + self.transclude("ב")
        self.assertEqual(self.slice(page).text, "אַלֶף\nבֵּית")

    def test_a_centring_wrapper_keeps_what_it_wraps(self):
        # `{{מרכז|...}}` holds braces of its own, so a rule that only removes brace-free
        # templates would leave its braces behind -- and one that ran after substitution
        # would delete the words with it.
        page = "{{מרכז|" + self.transclude("א") + "{{ש}}" + self.transclude("ב") + "}}"
        self.assertEqual(self.slice(page).text, "אַלֶף\nבֵּית")

    def test_a_noinclude_region_is_not_part_of_the_work(self):
        # The page wrapper opens inside one `<noinclude>` and closes inside another, so it
        # is only balanced once both regions are gone. Left in, the unpaired `{{name|` is
        # not a template any rule can collapse and survives into the slice as words.
        page = (
            "<noinclude>{{עטיפה|</noinclude>"
            + self.transclude("א")
            + "<noinclude>}}</noinclude>"
        )
        self.assertEqual(self.slice(page).text, "אַלֶף")

    def test_a_line_leading_indent_marker_is_markup(self):
        # Rabbi Ishmael's thirteen rules are set as an indented list; left in, the marker
        # rides on the first token of every rule and `compare` reports thirteen
        # differences that are the slicer's own punctuation.
        page = ":" + self.transclude("א") + "\n::" + self.transclude("ב")
        self.assertEqual(self.slice(page).text, "אַלֶף\nבֵּית")

    def test_a_colon_inside_a_line_is_text(self):
        page = self.transclude("א") + ": " + self.transclude("ב")
        self.assertEqual(self.slice(page).text, "אַלֶף: בֵּית")

    def test_a_heading_span_is_left_out(self):
        page = self.transclude("כותרת ג") + "\n" + self.transclude("א")
        self.assertEqual(self.slice(page).text, "אַלֶף")

    def test_a_span_the_foundation_page_does_not_define_is_reported(self):
        # Never silently: a slice with a hole in it reads afterwards as a wall of
        # consonantal differences rather than as a slice error.
        sliced = self.slice(self.transclude("ד"))
        self.assertEqual(sliced.missing, [("דף", "ד")])

    def slice(self, page):
        return transcription.page_slice(page, self.load)


class TestMissingSpanCli(unittest.TestCase):
    def test_missing_page_does_not_corrupt_foundation_path_for_next_page(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from contextlib import redirect_stderr
        from io import StringIO
        with TemporaryDirectory() as d:
            root=Path(d);book=root/'sources/birnbaum_siddur'
            foundation=book/'source/text/אשכנז/דפי יסוד';foundation.mkdir(parents=True)
            (foundation/'דף.txt').write_text('<קטע התחלה=א/>אַלֶף<קטע סוף=א/>',encoding='utf-8')
            (book/'text').mkdir();out=book/'scan_reading/transcription';out.mkdir(parents=True)
            for page,span in [(26,'חסר'),(27,'א')]:
                (book/'text'/f'{page:03d}.txt').write_text('{{#קטע:ספר/אשכנז/דפי יסוד/דף|'+span+'}}',encoding='utf-8')
            with redirect_stderr(StringIO()):status=transcription._cli(['1','2','--sourcetexts',str(root)])
            self.assertEqual(status,1)
            self.assertFalse((out/'1.txt').exists())
            self.assertEqual((out/'2.txt').read_text(encoding='utf-8'),'אַלֶף\n')

    def test_renamed_havdalah_span_keeps_both_nested_parts(self):
        foundation='קידוש והבדלה וסעודות שבת ויום טוב';old='ברכת המבדיל בין קודש לקודש'
        text=f'<קטע התחלה={old} הכל/><קטע התחלה=א/>אחד<קטע סוף=א/><קטע התחלה=ב/>שנים<קטע סוף=ב/><קטע סוף={old} הכל/>'
        page='{{#קטע:ספר/אשכנז/דפי יסוד/'+foundation+'|'+old+'}}'
        sliced=transcription.page_slice(page,lambda name:text)
        self.assertEqual(sliced.missing,[])
        self.assertIn('אחד',sliced.text);self.assertIn('שנים',sliced.text)


if __name__ == "__main__":
    unittest.main()
