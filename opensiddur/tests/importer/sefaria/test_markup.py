import unittest

from opensiddur.importer.sefaria.markup import (
    Break,
    EnglishKind,
    Footnote,
    HebrewKind,
    Styled,
    Text,
    english_kind,
    hebrew_kind,
    leading_label,
    parse_segment,
    plain_text,
    wholly,
)


class TestParseSegment(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(parse_segment(""), ())
        self.assertEqual(parse_segment("   "), ())

    def test_styles_and_breaks(self):
        nodes = parse_segment("<b>מוֹדֶה</b> אֲנִי<br><small>x</small><big>y</big><span>שׁ</span>")
        self.assertEqual(nodes[0], Styled("bold", (Text("מוֹדֶה"),)))
        self.assertEqual(nodes[1], Text(" אֲנִי"))
        self.assertIsInstance(nodes[2], Break)
        self.assertEqual([n.style for n in nodes[3:]], ["small", "large", "foreign"])

    def test_footnote_pairs_marker_with_note(self):
        nodes = parse_segment('the 613<sup class="footnote-marker">1</sup><i class="footnote">'
                              'Value of <i>tzitzis</i>.<br>More.</i> commandments')
        self.assertEqual(nodes[0], Text("the 613"))
        note = nodes[1]
        self.assertIsInstance(note, Footnote)
        self.assertEqual(note.marker, "1")
        self.assertEqual(plain_text(note.children), "Value of tzitzis. More.")
        self.assertEqual(nodes[2], Text(" commandments"))

    def test_plain_text_leaves_out_footnotes(self):
        nodes = parse_segment('King<sup class="footnote-marker">1</sup><i class="footnote">Note.</i>')
        self.assertEqual(plain_text(nodes), "King")

    def test_unknown_tag_keeps_text(self):
        with self.assertLogs("opensiddur.importer.sefaria.markup", level="WARNING"):
            nodes = parse_segment("<u>under</u> line")
        self.assertEqual(plain_text(nodes), "under line")


class TestKinds(unittest.TestCase):
    def test_hebrew_kinds(self):
        self.assertIs(hebrew_kind(parse_segment("")), HebrewKind.EMPTY)
        self.assertIs(hebrew_kind(parse_segment("<b>אבות</b>")), HebrewKind.LABEL)
        self.assertIs(hebrew_kind(parse_segment("<small>משנה א</small>")), HebrewKind.LABEL)
        # Pointed and bold is the opening of a prayer, not a heading.
        self.assertIs(hebrew_kind(parse_segment("<b>שְׁמַע יִשְׂרָאֵל</b>")), HebrewKind.BOLD_OPENING)
        self.assertIs(hebrew_kind(parse_segment("<b>מוֹדֶה אֲנִי</b> לְפָנֶֽיךָ")), HebrewKind.BOLD_OPENING)
        self.assertIs(hebrew_kind(parse_segment("מֶֽלֶךְ חַי")), HebrewKind.TEXT)
        self.assertIs(hebrew_kind(parse_segment("<small>בָּרוּךְ שֵׁם</small>")), HebrewKind.TEXT)

    def test_english_kinds(self):
        self.assertIs(english_kind(parse_segment("")), EnglishKind.EMPTY)
        self.assertIs(english_kind(parse_segment("<b>FOREFATHERS</b>")), EnglishKind.HEADING)
        self.assertIs(english_kind(parse_segment("<small><i>Say:</i></small>")), EnglishKind.RUBRIC)
        self.assertIs(english_kind(parse_segment("<i>Rosh Chodesh</i>")), EnglishKind.RUBRIC)
        self.assertIs(english_kind(parse_segment("I give <i>thanks</i>")), EnglishKind.TEXT)

    def test_wholly_ignores_footnotes(self):
        nodes = parse_segment('<b>Heading</b><sup class="footnote-marker">1</sup><i class="footnote">n</i>')
        self.assertTrue(wholly(nodes, {"bold"}))

    def test_leading_label(self):
        label, rest = leading_label(parse_segment('<small>לְר"ח:</small> רֹאשׁ הַחֹֽדֶשׁ'))
        self.assertEqual(plain_text((label,)), 'לְר"ח:')
        self.assertEqual(plain_text(rest), "רֹאשׁ הַחֹֽדֶשׁ")
        label, rest = leading_label(parse_segment("<small>בָּרוּךְ שֵׁם</small> כְּבוֹד"))
        self.assertIsNone(label)


if __name__ == "__main__":
    unittest.main()
