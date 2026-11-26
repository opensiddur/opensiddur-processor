"""Tests for custom page headers and footers (opensiddur/exporter/tex/running_heads.py).

Template parsing, code expansion and the fancyhdr block are all pure functions
of the settings, so they are tested directly rather than through the XSLT.
"""

import unittest

from pydantic import ValidationError

from opensiddur.exporter.settings import TypographyConfig
from opensiddur.exporter.tex.running_heads import (
    RUNNING_HEAD_CODES,
    RunningHeadConfig,
    RunningHeadPosition,
    RunningHeadSide,
    build_page_style_tex,
    default_page_header,
    escape_with_hebrew_runs,
    expand_template,
    parse_template,
    render_position,
)

LTR = r"{\textdir TLT\foreignlanguage{english}{"


class TestParseTemplate(unittest.TestCase):
    """Templates are literal text with codes from a closed list in braces."""

    def test_plain_text_is_one_literal_segment(self):
        segments = parse_template("Page")
        self.assertEqual(len(segments), 1)
        self.assertFalse(segments[0].is_code)
        self.assertEqual(segments[0].value, "Page")

    def test_code_and_literal_are_separate_segments(self):
        segments = parse_template("Page {page} of it")
        self.assertEqual(
            [(s.is_code, s.value) for s in segments],
            [(False, "Page "), (True, "page"), (False, " of it")],
        )

    def test_doubled_braces_are_literal_braces(self):
        segments = parse_template("{{page}}")
        self.assertEqual([(s.is_code, s.value) for s in segments], [(False, "{page}")])

    def test_unknown_code_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            parse_template("{not-a-code}")
        self.assertIn("Unknown header/footer code", str(ctx.exception))

    def test_unterminated_brace_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            parse_template("Page {page")
        self.assertIn("Unterminated", str(ctx.exception))

    def test_unmatched_closing_brace_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            parse_template("Page page}")
        self.assertIn("Unmatched", str(ctx.exception))


class TestExpandTemplate(unittest.TestCase):
    """Codes become TeX; literals are escaped the way reledmac.xslt escapes them."""

    def test_every_documented_code_expands(self):
        for code, expansion in RUNNING_HEAD_CODES.items():
            with self.subTest(code=code):
                self.assertEqual(expand_template("{" + code + "}"), expansion)

    def test_page_number_uses_thepage_forced_ltr(self):
        """Digits laid out RTL come out reversed: page 50 would read "05"."""
        self.assertEqual(
            expand_template("{page}"),
            r"{\textdir TLT\foreignlanguage{english}{\thepage}}",
        )

    def test_hebrew_page_number_uses_hebrewnumeral(self):
        self.assertEqual(expand_template("{page-hebrew}"), r"\hebrewnumeral{\value{page}}")

    def test_heading_levels_map_to_their_mark_classes(self):
        self.assertEqual(expand_template("{head1}"), r"\LastMark{OSheadA}")
        self.assertEqual(expand_template("{head4}"), r"\LastMark{OSheadD}")

    def test_alt_codes_read_the_second_parallel_stream(self):
        self.assertEqual(expand_template("{head2-alt}"), r"\LastMark{OSheadBAlt}")
        self.assertEqual(expand_template("{book-title-alt}"), r"\LastMark{OSbookAlt}")

    def test_literal_tex_specials_are_escaped(self):
        self.assertEqual(
            expand_template("100% & more_"),
            LTR + r"100\% \& more\_" + "}}",
        )

    def test_literal_backslash_is_escaped_before_the_rest(self):
        self.assertEqual(
            expand_template("a\\b"), LTR + r"a\textbackslash{}b" + "}}"
        )

    def test_doubled_braces_survive_as_escaped_literal_braces(self):
        self.assertEqual(expand_template("{{x}}"), LTR + r"\{x\}" + "}}")


class TestRenderPosition(unittest.TestCase):
    """A slot carries its own direction, and can be suppressed wholesale."""

    def test_empty_slot_renders_nothing(self):
        self.assertEqual(render_position(RunningHeadPosition()), "")

    def test_non_hebrew_slot_forces_ltr(self):
        out = render_position(RunningHeadPosition(text="{page}", language="en"))
        self.assertTrue(out.startswith(r"{\textdir TLT\foreignlanguage{english}{"))

    def test_hebrew_slot_forces_rtl(self):
        out = render_position(RunningHeadPosition(text="{page}", language="he"))
        self.assertTrue(out.startswith(r"{\textdir TRT\foreignlanguage{hebrew}{"))

    def test_hebrew_subtag_counts_as_hebrew(self):
        out = render_position(RunningHeadPosition(text="{page}", language="he-IL"))
        self.assertIn(r"\textdir TRT", out)

    def test_slot_without_a_language_follows_the_document(self):
        position = RunningHeadPosition(text="{page}")
        self.assertIn(r"\textdir TRT", render_position(position, default_language="he"))
        self.assertIn(r"\textdir TLT", render_position(position, default_language="en"))

    def test_slot_language_overrides_the_document(self):
        position = RunningHeadPosition(text="{page}", language="en")
        self.assertIn(r"\textdir TLT", render_position(position, default_language="he"))

    def test_if_wraps_the_whole_slot_including_its_literals(self):
        out = render_position(
            RunningHeadPosition(
                text="Chapter {chapter-number}", language="en", **{"if": "{chapter-number}"}
            )
        )
        self.assertTrue(out.startswith(r"\OSHFIfNonEmpty{\LastMark{OSchapter}}{"))
        self.assertIn("Chapter ", out)

    def test_if_test_carries_no_direction_wrapper(self):
        """The emptiness test must expand to nothing when the mark is unset;
        a direction wrapper would make it non-empty on every page."""
        out = render_position(
            RunningHeadPosition(text="x", language="he", **{"if": "{head1}"})
        )
        self.assertIn(r"\OSHFIfNonEmpty{\LastMark{OSheadA}}{", out)


class TestBidiLiterals(unittest.TestCase):
    """Literal template text gets per-run direction, like the marks do.

    The slot's declared language sets the base direction, which decides the
    order runs are laid out in; \textdir forces a direction rather than running
    the bidi algorithm, so a run left bare comes out reversed in a slot that
    runs the other way.
    """

    def test_latin_literal_is_wrapped_ltr(self):
        self.assertEqual(expand_template("Page"), LTR + "Page}}")

    def test_hebrew_literal_takes_texthebrew(self):
        """\\texthebrew carries the Hebrew font too, without which a Latin-font
        slot has no glyphs for it."""
        self.assertEqual(expand_template("פרק"), r"\texthebrew{פרק}")

    def test_mixed_literal_splits_into_runs(self):
        """The space separating them rides along with the Latin run, which is
        harmless — what matters is that neither run is left bare."""
        self.assertEqual(
            expand_template("פרק ch"), r"\texthebrew{פרק}" + LTR + " ch}}"
        )

    def test_whitespace_alone_is_not_wrapped(self):
        """Whitespace between two codes carries no direction of its own;
        wrapping it would only add an empty group."""
        self.assertEqual(
            expand_template("{head1} {head2}"),
            r"\LastMark{OSheadA} \LastMark{OSheadB}",
        )

    def test_hebrew_joined_by_an_en_dash_stays_one_run(self):
        """A paired parsha name uses an en-dash, outside the Hebrew block.
        Splitting on it would make the dash its own LTR embedding and let a
        neighbouring chapter number reorder into the middle of the name."""
        self.assertEqual(
            expand_template("\u05ea\u05b7\u05d6\u05b0\u05e8\u05b4\u05d9\u05e2\u05b7\u2013\u05de\u05b0\u05e6\u05b9\u05e8\u05b8\u05e2"),
            "\\texthebrew{\u05ea\u05b7\u05d6\u05b0\u05e8\u05b4\u05d9\u05e2\u05b7\u2013\u05de\u05b0\u05e6\u05b9\u05e8\u05b8\u05e2}",
        )

    def test_hebrew_joined_by_a_space_and_a_dash_stays_one_run(self):
        self.assertEqual(
            expand_template("\u05d0\u05b7\u05d7\u05b2\u05e8\u05b5\u05d9 \u05de\u05d5\u05b9\u05ea\u2013\u05e7\u05b0\u05d3\u05b9\u05e9\u05c1\u05b4\u05d9\u05dd"),
            "\\texthebrew{\u05d0\u05b7\u05d7\u05b2\u05e8\u05b5\u05d9 \u05de\u05d5\u05b9\u05ea\u2013\u05e7\u05b0\u05d3\u05b9\u05e9\u05c1\u05b4\u05d9\u05dd}",
        )

    def test_a_digit_after_hebrew_is_still_its_own_run(self):
        """The joiner must not swallow the chapter number into the name."""
        out = expand_template("\u05e4\u05e8\u05e7 14")
        self.assertEqual(out, "\\texthebrew{\u05e4\u05e8\u05e7}" + LTR + " 14}}")

    def test_a_latin_literal_beside_the_page_number_reads_in_order(self):
        """Regression: "p{page}" in a Hebrew slot used to read "1p"."""
        out = expand_template("p{page}")
        self.assertEqual(
            out, LTR + "p}}" + r"{\textdir TLT\foreignlanguage{english}{\thepage}}"
        )


class TestRunningHeadModels(unittest.TestCase):
    """Settings shorthands and the all/odd-even exclusivity rule."""

    def test_bare_string_is_shorthand_for_text(self):
        side = RunningHeadSide.model_validate({"left": "{page}"})
        self.assertEqual(side.left.text, "{page}")
        self.assertIsNone(side.left.language)

    def test_mapping_form_carries_language_and_if(self):
        side = RunningHeadSide.model_validate(
            {"center": {"text": "{head2}", "language": "he", "if": "{head2}"}}
        )
        self.assertEqual(side.center.language, "he")
        self.assertEqual(side.center.if_, "{head2}")

    def test_language_must_be_a_language_tag(self):
        """A misspelt tag would quietly set the slot left to right."""
        for tag in ("he", "en-US", "he-Latn", "arc"):
            RunningHeadPosition(text="{page}", language=tag)
        for tag in ("hebrew", "he_IL", "", "h", "he-"):
            with self.assertRaises(ValidationError, msg=repr(tag)):
                RunningHeadPosition(text="{page}", language=tag)

    def test_unknown_code_in_text_fails_validation(self):
        with self.assertRaises(ValidationError) as ctx:
            RunningHeadSide.model_validate({"left": "{bogus}"})
        self.assertIn("Unknown header/footer code", str(ctx.exception))

    def test_unknown_code_in_if_fails_validation(self):
        with self.assertRaises(ValidationError) as ctx:
            RunningHeadSide.model_validate({"left": {"text": "x", "if": "{bogus}"}})
        self.assertIn("Unknown header/footer code", str(ctx.exception))

    def test_all_alone_is_valid(self):
        config = RunningHeadConfig.model_validate({"all": {"center": "{page}"}})
        self.assertFalse(config.is_empty())
        self.assertEqual([suffix for suffix, _ in config.declared_sides()], [""])

    def test_odd_and_even_together_are_valid(self):
        config = RunningHeadConfig.model_validate(
            {"odd": {"left": "{page}"}, "even": {"right": "{page}"}}
        )
        self.assertEqual([suffix for suffix, _ in config.declared_sides()], ["O", "E"])

    def test_all_with_odd_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            RunningHeadConfig.model_validate(
                {"all": {"center": "{page}"}, "odd": {"left": "{page}"}}
            )
        self.assertIn("`all` cannot be combined", str(ctx.exception))

    def test_all_with_even_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            RunningHeadConfig.model_validate(
                {"all": {"center": "{page}"}, "even": {"left": "{page}"}}
            )
        self.assertIn("`all` cannot be combined", str(ctx.exception))

    def test_nothing_declared_is_empty(self):
        self.assertTrue(RunningHeadConfig().is_empty())

    def test_declared_but_blank_side_is_empty(self):
        config = RunningHeadConfig.model_validate({"all": {"center": ""}})
        self.assertTrue(config.is_empty())

    def test_typography_defaults_to_a_section_title_head_and_no_foot(self):
        typography = TypographyConfig()
        self.assertEqual(typography.page_header, default_page_header(right_bound=True))
        self.assertTrue(typography.page_footer.is_empty())

    def test_default_head_follows_the_binding(self):
        for page, right_bound in (({}, True), ({"binding": "left"}, False),
                                  ({"sides": "one"}, False)):
            with self.subTest(page=page):
                typography = TypographyConfig.model_validate({"page": page})
                self.assertEqual(typography.page_header,
                                 default_page_header(right_bound=right_bound))
                # Still the default, not something the settings file said.
                self.assertNotIn("page_header", typography.model_fields_set)

    def test_a_stated_head_is_not_mirrored(self):
        """Its left and right are the settings file's own physical positions."""
        head = {"odd": {"left": "{page}"}, "even": {"right": "{page}"}}
        typography = TypographyConfig.model_validate({"page_header": head})
        self.assertEqual(typography.page_header, RunningHeadConfig.model_validate(head))

    def test_settings_can_ask_for_no_head_at_all(self):
        """An empty mapping is a real choice, distinct from saying nothing."""
        typography = TypographyConfig.model_validate({"page_header": {}})
        self.assertTrue(typography.page_header.is_empty())


class TestDefaultPageHeader(unittest.TestCase):
    """The head a settings file gets when it declares none."""

    def test_default_is_not_empty(self):
        self.assertFalse(default_page_header().is_empty())

    def test_default_is_a_fresh_instance_each_call(self):
        self.assertIsNot(default_page_header(), default_page_header())

    def test_default_names_the_section_and_numbers_the_page(self):
        """The marks it reads are already inserted at every heading."""
        out = build_page_style_tex(default_page_header(), None, "he")
        for slot in ("LO", "RO", "LE", "RE"):
            with self.subTest(slot=slot):
                self.assertIn(r"\fancyhead[%s]{" % slot, out)
        # Title inner, page number outer: inner is the left of an odd page, the
        # same sense `geometry` is given its margins in.
        self.assertIn(r"\fancyhead[LO]{{\textdir TRT\foreignlanguage{hebrew}{\LastMark{OSheadAny}}}}", out)
        self.assertIn(r"\fancyhead[RE]{{\textdir TRT\foreignlanguage{hebrew}{\LastMark{OSheadAny}}}}", out)
        self.assertEqual(out.count(r"\thepage"), 4)  # RO and LE, once per page style

    def test_right_bound_default_is_the_mirror_image(self):
        """The page number stays on the fore edge, which a right binding moves to
        the left of an odd page."""
        out = build_page_style_tex(default_page_header(right_bound=True), None, "he")
        self.assertIn(r"\fancyhead[RO]{{\textdir TRT\foreignlanguage{hebrew}{\LastMark{OSheadAny}}}}", out)
        self.assertIn(r"\fancyhead[LE]{{\textdir TRT\foreignlanguage{hebrew}{\LastMark{OSheadAny}}}}", out)
        for slot in ("LO", "RE"):
            with self.subTest(slot=slot):
                self.assertRegex(out, r"\\fancyhead\[%s\]\{.*\\thepage" % slot)

    def test_default_never_reads_the_class_marks(self):
        """\\leftmark/\\rightmark are what carried "CONTENTS" through the book."""
        out = build_page_style_tex(default_page_header(), None, "he")
        self.assertNotIn(r"\leftmark", out)
        self.assertNotIn(r"\rightmark", out)


class TestBuildPageStyleTex(unittest.TestCase):
    """The fancyhdr block: nothing at all unless something is configured."""

    def test_explicitly_empty_head_and_foot_silence_automatic_marks(self):
        """A document asking for no head must not inherit the class's own.

        book.cls's \\tableofcontents issues \\@mkboth{CONTENTS}{CONTENTS}, and
        nothing here ever sets another mark, so without this "CONTENTS" stayed
        in the running head for the rest of the book.
        """
        for page_header, page_footer in (
            (None, None),
            (RunningHeadConfig(), RunningHeadConfig()),
        ):
            with self.subTest(page_header=page_header):
                out = build_page_style_tex(page_header, page_footer)
                self.assertIn(r"\let\@mkboth\@gobbletwo", out)
                self.assertNotIn("fancyhdr", out)
                self.assertNotIn(r"\pagestyle{fancy}", out)

    def test_configured_page_style_also_silences_automatic_marks(self):
        header = RunningHeadConfig.model_validate({"all": {"left": "{page}"}})
        self.assertIn(r"\let\@mkboth\@gobbletwo", build_page_style_tex(header, None))

    def test_configured_header_loads_fancyhdr_and_switches_page_style(self):
        header = RunningHeadConfig.model_validate({"all": {"left": "{page}"}})
        out = build_page_style_tex(header, None)
        self.assertIn(r"\usepackage{fancyhdr}", out)
        self.assertIn(r"\pagestyle{fancy}", out)
        self.assertIn(r"\fancyhf{}", out)

    def test_odd_and_even_slots_get_parity_suffixes(self):
        header = RunningHeadConfig.model_validate(
            {
                "odd": {"left": "{page}", "center": "{page}", "right": "{page}"},
                "even": {"left": "{page}", "center": "{page}", "right": "{page}"},
            }
        )
        out = build_page_style_tex(header, None, "en")
        for slot in ("LO", "CO", "RO", "LE", "CE", "RE"):
            with self.subTest(slot=slot):
                self.assertIn(r"\fancyhead[%s]{" % slot, out)

    def test_all_side_emits_unsuffixed_slots(self):
        header = RunningHeadConfig.model_validate({"all": {"left": "{page}"}})
        out = build_page_style_tex(header, None, "en")
        self.assertIn(r"\fancyhead[L]{", out)
        self.assertNotIn(r"\fancyhead[LO]{", out)
        self.assertNotIn(r"\fancyhead[LE]{", out)

    def test_footers_use_fancyfoot(self):
        footer = RunningHeadConfig.model_validate({"all": {"center": "{page}"}})
        out = build_page_style_tex(None, footer, "en")
        self.assertIn(r"\fancyfoot[C]{", out)
        self.assertNotIn(r"\fancyhead[", out)

    def test_empty_slots_emit_no_command(self):
        header = RunningHeadConfig.model_validate({"all": {"left": "{page}"}})
        out = build_page_style_tex(header, None, "en")
        self.assertNotIn(r"\fancyhead[C]", out)
        self.assertNotIn(r"\fancyhead[R]", out)

    def test_plain_page_style_repeats_the_slots(self):
        """\\tableofcontents and other \\chapter*-style pages use `plain`; without
        this they would silently drop out of the running-head scheme."""
        header = RunningHeadConfig.model_validate({"all": {"left": "{page}"}})
        out = build_page_style_tex(header, None, "en")
        self.assertIn(r"\fancypagestyle{plain}{", out)
        self.assertEqual(out.count(r"\fancyhead[L]{"), 2)

    def test_blank_filler_pages_are_left_empty(self):
        """\\cleardoublepage's blank verso would otherwise arrive carrying a
        running head — most visibly on the page facing a title page."""
        header = RunningHeadConfig.model_validate({"all": {"left": "{page}"}})
        out = build_page_style_tex(header, None, "en")
        self.assertIn(r"\renewcommand*{\cleardoublepage}", out)
        self.assertIn(r"\thispagestyle{empty}", out)

    def test_header_reserves_head_height(self):
        header = RunningHeadConfig.model_validate({"all": {"left": "{page}"}})
        self.assertIn(r"\setlength{\headheight}", build_page_style_tex(header, None))

    def test_footer_only_does_not_reserve_head_height(self):
        footer = RunningHeadConfig.model_validate({"all": {"center": "{page}"}})
        self.assertNotIn(r"\setlength{\headheight}", build_page_style_tex(None, footer))

    def test_document_language_reaches_slots_that_declare_none(self):
        header = RunningHeadConfig.model_validate({"all": {"left": "{book-title}"}})
        out = build_page_style_tex(header, None, "he")
        self.assertIn(r"\textdir TRT", out)



class TestHebrewScript(unittest.TestCase):
    """The running heads decide the Hebrew script by the rule the stylesheets use."""

    def test_the_script_subtag_decides(self):
        from opensiddur.exporter.tex.running_heads import is_hebrew_language
        for language, hebrew in (("he", True), ("he-IL", True), ("he-Latn", False),
                                 ("arc", True), ("arc-Hebr", True), ("yi", True),
                                 ("en", False), ("en-Hebr", True), (None, False), ("", False)):
            with self.subTest(language=language):
                self.assertIs(is_hebrew_language(language), hebrew)



class TestEscapeWithHebrewRuns(unittest.TestCase):
    def test_only_the_hebrew_is_wrapped(self):
        self.assertEqual(
            r"From \texthebrew{ויקיטקסט} 100\%", escape_with_hebrew_runs("From ויקיטקסט 100%")
        )

    def test_latin_text_is_only_escaped(self):
        self.assertEqual(r"A \& B\_C", escape_with_hebrew_runs("A & B_C"))


if __name__ == "__main__":
    unittest.main()
