import unittest

SAMPLE_HTML = """
<table>
<tr>
<td><div class="liturgy"><h>קַדֵּשׁ</h></div></td>
<td><div class="english"><h3>Sanctification of the Day</h3><p>Kadesh</p></div></td>
</tr>
<tr>
<td><div class="liturgy">וַֽיְהִי־עֶ֥רֶב</div></td>
<td><div class="english"><p>Evening came</p></div></td>
</tr>
</table>
"""

HALLEL_NIRTZAH_HTML = """
<table>
<tr>
<td><div class="liturgy">הַלֵּל<br /></div></td>
<td><div class="english"><h3>Songs of Praise</h3></div></td>
</tr>
<tr>
<td><div class="liturgy">לֹא לָנוּ</div></td>
<td><div class="english"><p>Not unto us</p></div></td>
</tr>
<tr>
<td><div class="liturgy">נִרְצָה<br /></div></td>
<td><div class="english"><h3>Concluding Songs</h3></div></td>
</tr>
<tr>
<td><div class="liturgy">חֲסַל סִדּוּר פֶּסַח<br />כְּכָׇל מִשְׁפָּטוֹ</div></td>
<td><div class="english"><p>Completed</p><p>According to law</p></div></td>
</tr>
</table>
"""


#: A section heading followed by a subsection that opens mid-section with no h3 of its own.
#: The subsection is recognised by its incipit, and its first line is running text, not a head.
SUBSECTION_INCIPIT_HTML = """
<table>
<tr>
<td><div class="liturgy">מַגִּיד<br /></div></td>
<td><div class="english"><h3>Discussing the Exodus</h3></div></td>
</tr>
<tr>
<td><div class="liturgy">מַצָּה זוּ שֶׁאָנוּ אוֹכְלִים</div></td>
<td><div class="english"><p>This matzah that we eat</p></div></td>
</tr>
</table>
"""

#: A rubric the source marks with an instruction span, which must become a tei:note rather
#: than stay in the running text.
INSTRUCTION_HTML = """
<table>
<tr>
<td><div class="liturgy">קַדֵּשׁ<br /></div></td>
<td><div class="english"><h3>Sanctification of the Day</h3></div></td>
</tr>
<tr>
<td><div class="liturgy">וַֽיְהִי־עֶ֥רֶב</div></td>
<td><div class="english"><span class="instruction">(On Shabbat begin here.)</span>
<p>And there was evening</p></div></td>
</tr>
</table>
"""


class TestParseCompilation(unittest.TestCase):
    def test_parse_rows_extracts_h3_and_content(self) -> None:
        from opensiddur.importer.feinstein_haggadah.parse_compilation import (
            build_section_contents,
            parse_rows,
        )

        rows = parse_rows({"content": SAMPLE_HTML})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].h3_title, "Sanctification of the Day")
        self.assertIn("קַדֵּשׁ", rows[0].hebrew)
        self.assertIn("Evening came", rows[1].english)

        contents = build_section_contents(rows)
        self.assertIn("qaddesh", contents)
        qaddesh = contents["qaddesh"]
        self.assertEqual(qaddesh.blocks[0].kind, "head")
        self.assertIn("קַדֵּשׁ", qaddesh.blocks[0].hebrew)
        self.assertEqual(qaddesh.blocks[1].kind, "paragraph")

    def test_nirtzah_heading_goes_to_nirtzah_not_hallel(self) -> None:
        from opensiddur.importer.feinstein_haggadah.parse_compilation import (
            build_section_contents,
            parse_rows,
        )

        contents = build_section_contents(parse_rows({"content": HALLEL_NIRTZAH_HTML}))
        hallel = contents["hallel"]
        nirtzah = contents["nirtzah"]
        self.assertEqual(hallel.blocks[0].kind, "head")
        self.assertEqual(hallel.blocks[0].hebrew, "הַלֵּל")
        self.assertFalse(any("נִרְצָה" in block.hebrew for block in hallel.blocks))
        self.assertEqual(nirtzah.blocks[0].kind, "head")
        self.assertEqual(nirtzah.blocks[0].hebrew, "נִרְצָה")
        chasal = contents["chasal_siddur_pesach"]
        self.assertEqual(chasal.blocks[0].kind, "paragraph")
        self.assertTrue(chasal.blocks[0].hebrew.startswith("חֲסַל סִדּוּר פֶּסַח"))

    def test_subsection_incipit_is_not_head(self) -> None:
        """A subsection recognised by its incipit opens with text, not with a heading.

        Only a row carrying its own h3 supplies a head; an incipit match splits the section
        but the matched line is the subsection's first paragraph.
        """
        from opensiddur.importer.feinstein_haggadah.parse_compilation import (
            build_section_contents,
            parse_rows,
        )

        contents = build_section_contents(parse_rows({"content": SUBSECTION_INCIPIT_HTML}))
        matzah = contents["matzah_zu"]
        self.assertEqual(matzah.blocks[0].kind, "paragraph")
        self.assertIn("מַצָּה זוּ", matzah.blocks[0].hebrew)
        self.assertFalse(any(block.kind == "head" for block in matzah.blocks))
        # The parent keeps its own h3-supplied head and does not swallow the subsection.
        self.assertEqual(contents["maggid"].blocks[0].kind, "head")

    def test_english_instructions_become_notes(self) -> None:
        from opensiddur.importer.feinstein_haggadah.parse_compilation import (
            _clean_html_cell,
            build_section_contents,
            parse_rows,
            split_parenthetical_instructions,
        )

        parts = split_parenthetical_instructions(
            _clean_html_cell(
                '<span class="instruction">(On Shabbat begin here.)</span>'
                '<span class="instruction">(Recite quietly:)</span> And there was evening'
            )
        )
        self.assertEqual([(p.kind, p.text) for p in parts[:2]], [
            ("instruction", "On Shabbat begin here."),
            ("instruction", "Recite quietly:"),
        ])
        self.assertEqual(parts[2].kind, "paragraph")
        self.assertFalse(any(p.governs or p.governed for p in parts))

        contents = build_section_contents(parse_rows({"content": INSTRUCTION_HTML}))
        qaddesh = contents["qaddesh"]
        instructions = [b for b in qaddesh.blocks if b.kind == "instruction"]
        self.assertTrue(instructions)
        self.assertIn("Shabbat", instructions[0].english)
        # The rubric leaves the running text; it must not be repeated there.
        paragraphs = [b for b in qaddesh.blocks if b.kind == "paragraph"]
        self.assertTrue(paragraphs)
        self.assertNotIn("On Shabbat", " ".join(b.english for b in paragraphs))


class TestConditionalSegmentation(unittest.TestCase):
    """Where the parentheses fall relative to a rubric's span says whether it governs text.

    See ``parse_compilation.split_parenthetical_instructions``.
    """

    def _split(self, raw: str):
        from opensiddur.importer.feinstein_haggadah.parse_compilation import (
            _clean_html_cell,
            split_parenthetical_instructions,
        )

        return split_parenthetical_instructions(_clean_html_cell(raw))

    def test_paren_inside_the_span_is_a_plain_rubric(self) -> None:
        (segment,) = self._split('<span class="instruction">(On Shabbat begin here.)</span>')
        self.assertEqual((segment.kind, segment.text), ("instruction", "On Shabbat begin here."))
        self.assertFalse(segment.governs)

    def test_paren_around_the_span_governs_the_text_that_follows(self) -> None:
        rubric, text = self._split(
            '(<span class="instruction">on Shabbat say:</span> Sabbaths for rest and)'
        )
        self.assertEqual((rubric.text, rubric.governs), ("on Shabbat say:", True))
        self.assertEqual((text.text, text.governed), ("Sabbaths for rest and", True))

    def test_paren_straddling_the_span_governs_too(self) -> None:
        rubric, text = self._split('<span class="instruction">(some add:</span> to Pharaoh)')
        self.assertEqual((rubric.text, rubric.governs), ("some add:", True))
        self.assertEqual((text.text, text.governed), ("to Pharaoh", True))

    def test_rubric_keeps_its_own_nested_parentheses(self) -> None:
        """The source writes '(?!)' inside this rubric; a non-nesting scan truncates it."""
        rubric, text = self._split(
            '(<span class="instruction">Alternately, if people are present who did not'
            ' eat (?!) they respond:</span> May His name be blessed.)'
        )
        self.assertEqual(
            rubric.text,
            "Alternately, if people are present who did not eat (?!) they respond:",
        )
        self.assertEqual(text.text, "May His name be blessed.")

    def test_parentheses_without_a_span_stay_inline(self) -> None:
        """A translator's gloss is not a rubric, and reads as parenthetical text."""
        (segment,) = self._split("You defeated the prince of Harosheth (Sisera) with the stars")
        self.assertEqual(segment.kind, "paragraph")
        self.assertIn("(Sisera)", segment.text)

    def test_nested_spans_close_at_the_right_tag(self) -> None:
        rubric, text = self._split(
            '(<span class="instruction">say <span class="x">now</span>:</span> the words)'
        )
        self.assertEqual((rubric.text, rubric.governs), ("say now:", True))
        self.assertEqual(text.text, "the words")


class TestTeiBuilder(unittest.TestCase):
    def test_index_body_includes_head_and_transcludes(self) -> None:
        from opensiddur.importer.feinstein_haggadah.sections import SectionContent, TextBlock
        from opensiddur.importer.feinstein_haggadah.tei_builder import index_body

        section = SectionContent(
            slug="nirtzah",
            blocks=[TextBlock(kind="head", hebrew="נִרְצָה")],
        )
        body = index_body("nirtzah", ["chasal_siddur_pesach"], section, lang="he")
        self.assertIn("<tei:head>נִרְצָה</tei:head>", body)
        self.assertIn("nirtzah/chasal_siddur_pesach", body)
        self.assertNotIn("<tei:p>נִרְצָה</tei:p>", body)

    def test_content_body_emits_milestone_urns(self) -> None:
        from opensiddur.importer.feinstein_haggadah.sections import SectionContent, TextBlock
        from opensiddur.importer.feinstein_haggadah.tei_builder import content_body

        section = SectionContent(
            slug="karpas",
            blocks=[
                TextBlock(kind="head", hebrew="קַדֵּשׁ"),
                TextBlock(
                    kind="paragraph",
                    hebrew="בָּרוּךְ",
                    starts_paragraph=True,
                ),
            ],
        )
        body = content_body("karpas", section, lang="he")
        self.assertIn('<tei:milestone unit="paragraph" n="1" corresp="urn:x-opensiddur:text:haggadah:karpas/1"/>', body)
        self.assertIn("<tei:head>קַדֵּשׁ</tei:head>", body)

    def test_content_body_emits_instruction_notes(self) -> None:
        from opensiddur.importer.feinstein_haggadah.sections import SectionContent, TextBlock
        from opensiddur.importer.feinstein_haggadah.tei_builder import content_body

        section = SectionContent(
            slug="karpas",
            blocks=[
                TextBlock(kind="head", english="Sanctification of the Day"),
                TextBlock(
                    kind="instruction",
                    english="On Shabbat begin here.",
                    starts_paragraph=True,
                ),
                TextBlock(
                    kind="paragraph",
                    english="Blessed are You",
                    starts_paragraph=False,
                ),
            ],
        )
        body = content_body("karpas", section, lang="en")
        self.assertIn('<tei:note type="instruction">On Shabbat begin here.</tei:note>', body)
        self.assertNotIn("(On Shabbat begin here.)", body)


if __name__ == "__main__":
    unittest.main()
