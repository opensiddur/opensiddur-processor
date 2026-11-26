"""Tests for the typography settings models (opensiddur/exporter/typography.py).

Two things are being checked throughout: that every default reproduces the
output this exporter produced before any of it was configurable, and that
anything invalid is refused at load time rather than passed to the renderer.

Font resolution shells out to fontconfig, so it is mocked here — a test that
depended on which fonts this machine has installed would pass or fail for
reasons that have nothing to do with the code.
"""

import unittest
from unittest.mock import patch

from pydantic import ValidationError

from opensiddur.exporter import typography as typography_module
from opensiddur.exporter.tex.running_heads import default_page_header
from opensiddur.exporter.typography import (
    RESOLVE_FONTS,
    Alignment,
    BaseFontSize,
    ConditionalBlock,
    FontFamily,
    FontWeight,
    InterleavedLineNumbers,
    LineationUnit,
    NamedSize,
    NoteAnchor,
    NoteMark,
    NotePlacement,
    PaperType,
    ParallelLayout,
    Sides,
    TextStyle,
    TypographyConfig,
    Visibility,
    resolve_font,
)


def _validate(data: dict) -> TypographyConfig:
    """Validate a settings fragment with fontconfig reporting nothing installed.

    ``None`` from the query means "cannot be asked", which is how a machine
    without fontconfig behaves, so no font chain is rejected and the tests stay
    about the setting under test.
    """
    with patch.object(typography_module, "_installed_font_families", return_value=None):
        return TypographyConfig.model_validate(data)


def _refused(test: unittest.TestCase, data: dict, *fragments: str) -> None:
    with test.assertRaises(ValidationError, msg=repr(data)) as caught:
        _validate(data)
    for fragment in fragments:
        test.assertIn(fragment, str(caught.exception))


class TestDefaults(unittest.TestCase):
    """An empty settings section has to mean "what it has always looked like"."""

    def setUp(self):
        self.config = _validate({})

    def test_page_defaults(self):
        self.assertEqual(self.config.page.paper, PaperType.LETTERPAPER)
        self.assertEqual(self.config.page.base_font_size, BaseFontSize.PT11)
        self.assertEqual(self.config.page.sides, Sides.TWO)
        self.assertTrue(self.config.page.margins.is_empty())

    def test_paragraph_defaults_match_the_stylesheet(self):
        self.assertEqual(self.config.paragraphs.indent, "0pt")
        self.assertEqual(self.config.paragraphs.spacing, "0.5em")
        self.assertEqual(self.config.paragraphs.line_spacing, 1.0)

    def test_heading_defaults_step_down_by_one_rung_each(self):
        sizes = [
            self.config.styles.heading1.size,
            self.config.styles.heading2.size,
            self.config.styles.heading3.size,
            self.config.styles.heading4.size,
        ]
        self.assertEqual(
            sizes,
            [
                NamedSize.XX_LARGE,
                NamedSize.X_LARGE,
                NamedSize.LARGE,
                NamedSize.NORMAL,
            ],
        )
        for style in (
            self.config.styles.heading1,
            self.config.styles.heading4,
        ):
            self.assertEqual(style.weight, FontWeight.BOLD)
            self.assertEqual(style.align, Alignment.CENTER)

    def test_line_number_defaults_match_reledmac(self):
        self.assertTrue(self.config.line_numbers.enabled)
        self.assertEqual(self.config.line_numbers.unit, LineationUnit.PAGE)
        # 5 and 5, so the numbers run 5, 10, 15 as they always have.
        self.assertEqual(self.config.line_numbers.increment, 5)
        self.assertEqual(self.config.line_numbers.first, 5)
        self.assertEqual(self.config.line_numbers.separation, "1em")

    def test_note_defaults(self):
        self.assertEqual(self.config.notes.placement, NotePlacement.FOOTNOTE)
        self.assertEqual(self.config.notes.anchor, NoteAnchor.INTERLINEAR)
        self.assertEqual(self.config.notes.mark, NoteMark.NUMERIC)

    def test_marker_defaults(self):
        self.assertEqual(self.config.markers.section_separator, "* * * *")
        self.assertEqual(self.config.markers.verse_numbers, Visibility.SHOWN)
        self.assertEqual(self.config.markers.conditional.inline_open, "[")
        self.assertEqual(self.config.markers.conditional.block, ConditionalBlock.RULE)
        self.assertEqual(self.config.markers.conditional.rule_width, "25%")

    def test_parallel_defaults(self):
        self.assertEqual(self.config.parallel.layout, ParallelLayout.PAIRS)
        self.assertEqual(self.config.parallel.column_width, "43%")

    def test_table_of_contents_defaults_to_disabled(self):
        self.assertFalse(self.config.table_of_contents.enabled)
        self.assertEqual(self.config.table_of_contents.depth, 4)

    def test_running_head_defaults_to_the_section_title_and_the_foot_to_nothing(self):
        self.assertEqual(self.config.page_header, default_page_header(right_bound=True))
        self.assertTrue(self.config.page_footer.is_empty())


class TestUnknownKeysAreRefused(unittest.TestCase):
    """A key nobody reads is a setting that silently did not happen."""

    def test_unknown_key_at_the_top_level(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"pgae": {}})
        self.assertIn("pgae", str(caught.exception))

    def test_unknown_key_in_a_section(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"page": {"papper": "a4paper"}})
        self.assertIn("papper", str(caught.exception))

    def test_unknown_role_in_styles(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"styles": {"heading5": {"size": "large"}}})
        self.assertIn("heading5", str(caught.exception))

    def test_unknown_attribute_in_a_style(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"styles": {"body": {"colour": "red"}}})
        self.assertIn("colour", str(caught.exception))

    def test_unknown_key_in_a_nested_section(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"markers": {"conditional": {"inline_middle": "-"}}})
        self.assertIn("inline_middle", str(caught.exception))


class TestClosedVocabularies(unittest.TestCase):
    def test_paper_must_be_a_known_size(self):
        with self.assertRaises(ValidationError):
            _validate({"page": {"paper": "tabloid"}})

    def test_base_font_size_is_restricted_to_the_three_that_exist(self):
        """Anything else silently becomes one of these, so asking is an error."""
        for size in ("10pt", "11pt", "12pt"):
            _validate({"page": {"base_font_size": size}})
        for size in ("13pt", "11", "large"):
            with self.assertRaises(ValidationError, msg=size):
                _validate({"page": {"base_font_size": size}})

    def test_note_placement_alignment_and_layout_are_closed(self):
        for section, key, bad in (
            ("notes", "placement", "margin"),
            ("notes", "anchor", "raised"),
            ("notes", "mark", "dingbat"),
            ("paragraphs", "alignment", "middle"),
            ("parallel", "layout", "columns"),
            ("line_numbers", "unit", "paragraph"),
            ("line_numbers", "numerals", "greek"),
            ("markers", "verse_numbers", "maybe"),
        ):
            with self.assertRaises(ValidationError, msg=f"{section}.{key}"):
                _validate({section: {key: bad}})

    def test_style_attributes_are_closed(self):
        for key, bad in (
            ("weight", "semibold"),
            ("style", "oblique"),
            ("variant", "all-caps"),
            ("align", "start"),
        ):
            with self.assertRaises(ValidationError, msg=key):
                _validate({"styles": {"body": {key: bad}}})


class TestLengths(unittest.TestCase):
    def test_accepted_lengths(self):
        for length in ("0pt", "12pt", "1.5em", "25mm", ".5in", "-3pt", "2ex", "1pc"):
            _validate({"paragraphs": {"indent": length}})

    def test_rejected_lengths(self):
        for length in ("12", "12 pt", "large", "12px", "", "pt"):
            with self.assertRaises(ValidationError, msg=repr(length)):
                _validate({"paragraphs": {"indent": length}})

    def test_a_size_may_be_a_named_rung_or_an_absolute_length(self):
        config = _validate({"styles": {"note": {"size": "9pt"}, "body": {"size": "small"}}})
        self.assertEqual(config.styles.note.size, "9pt")
        self.assertEqual(config.styles.body.size, NamedSize.SMALL)

    def test_a_size_may_not_be_relative_to_the_size_it_defines(self):
        for size in ("1.2em", "2ex"):
            with self.assertRaises(ValidationError, msg=size):
                _validate({"styles": {"note": {"size": size}}})

    def test_percentages(self):
        _validate({"parallel": {"column_width": "40%"}})
        for bad in ("40", "40 %", "%40"):
            with self.assertRaises(ValidationError, msg=bad):
                _validate({"parallel": {"column_width": bad}})

    def test_bounded_numbers(self):
        _validate({"paragraphs": {"line_spacing": 1.5}})
        for bad in (0.1, 4.0):
            with self.assertRaises(ValidationError, msg=str(bad)):
                _validate({"paragraphs": {"line_spacing": bad}})
        with self.assertRaises(ValidationError):
            _validate({"line_numbers": {"increment": 0}})
        with self.assertRaises(ValidationError):
            _validate({"table_of_contents": {"depth": 5}})


class TestCustomPaper(unittest.TestCase):
    def test_custom_paper_needs_both_dimensions(self):
        _validate({"page": {"paper": "custom", "width": "6in", "height": "9in"}})
        with self.assertRaises(ValidationError) as caught:
            _validate({"page": {"paper": "custom", "width": "6in"}})
        self.assertIn("height", str(caught.exception))

    def test_dimensions_without_custom_paper_are_an_error(self):
        """Silently ignoring them would print a document at the wrong size."""
        with self.assertRaises(ValidationError) as caught:
            _validate({"page": {"paper": "a4paper", "width": "6in", "height": "9in"}})
        self.assertIn("custom", str(caught.exception))


class TestFontFamilies(unittest.TestCase):
    def test_latin_and_hebrew_always_exist(self):
        config = _validate({})
        self.assertEqual(config.fonts["latin"].names, ["Linux Libertine O"])
        self.assertIn("FreeSerif", config.fonts["hebrew"].names)

    def test_a_bare_string_is_a_one_name_chain(self):
        config = _validate({"fonts": {"latin": "TeX Gyre Pagella"}})
        self.assertEqual(config.fonts["latin"].names, ["TeX Gyre Pagella"])

    def test_declaring_a_family_replaces_its_default_chain(self):
        """Leaving the old chain underneath would answer a misspelled font name
        with the house font and no complaint."""
        config = _validate({"fonts": {"hebrew": ["Ezra SIL"]}})
        self.assertEqual(config.fonts["hebrew"].names, ["Ezra SIL"])

    def test_declared_families_are_distinguished_from_filled_in_ones(self):
        config = _validate({"fonts": {"hebrew": "Ezra SIL"}})
        self.assertEqual(config.declared_fonts, frozenset({"hebrew"}))

    def test_an_empty_chain_is_refused(self):
        with self.assertRaises(ValidationError):
            _validate({"fonts": {"latin": []}})

    def test_a_style_may_only_name_a_declared_family(self):
        _validate({"fonts": {"sans": "DejaVu Sans"}, "styles": {"note": {"font": "sans"}}})
        with self.assertRaises(ValidationError) as caught:
            _validate({"styles": {"note": {"font": "sans"}}})
        self.assertIn("sans", str(caught.exception))


class TestDefaultFontsOnAMachineWithoutThem(unittest.TestCase):
    """The default chains must never be the reason a build fails.

    The house fonts are not installed everywhere — they are not on CI — and a
    document that asked for nothing must still export. The renderer falls back
    for the defaults; only a chain the settings file named is an error.
    """

    def _installed(self, *families):
        return patch.object(
            typography_module,
            "_installed_font_families",
            return_value=frozenset(name.casefold() for name in families),
        )

    def test_defaults_validate_where_none_of_them_is_installed(self):
        with self._installed("DejaVu Sans"):
            config = TypographyConfig()
        self.assertEqual(config.fonts["latin"].names, ["Linux Libertine O"])

    def test_a_settings_file_that_names_no_fonts_validates_too(self):
        with self._installed("DejaVu Sans"):
            TypographyConfig.model_validate({"page": {"paper": "a4paper"}})

    def test_but_a_named_font_that_is_missing_still_fails(self):
        with self._installed("DejaVu Sans"):
            with self.assertRaises(ValidationError):
                TypographyConfig.model_validate({"fonts": {"latin": "No Such Face"}})

    def test_naming_a_default_chain_explicitly_opts_into_the_check(self):
        """Writing it down is asking for it, whatever its value happens to be."""
        with self._installed("DejaVu Sans"):
            with self.assertRaises(ValidationError):
                TypographyConfig.model_validate(
                    {"fonts": {"latin": ["Linux Libertine O"]}}
                )


class TestFontResolution(unittest.TestCase):
    """The first installed name in a chain wins; none installed is an error."""

    def setUp(self):
        typography_module._installed_font_families.cache_clear()
        self.addCleanup(typography_module._installed_font_families.cache_clear)

    def _installed(self, *families):
        return patch.object(
            typography_module,
            "_installed_font_families",
            return_value=frozenset(name.casefold() for name in families),
        )

    def test_first_installed_name_wins(self):
        with self._installed("Ezra SIL", "FreeSerif"):
            self.assertEqual(
                resolve_font(["Frank Ruehl CLM", "Ezra SIL", "FreeSerif"]), "Ezra SIL"
            )

    def test_matching_ignores_case(self):
        with self._installed("freeserif"):
            self.assertEqual(resolve_font(["FreeSerif"]), "FreeSerif")

    def test_nothing_installed_is_an_error_naming_what_was_tried(self):
        with self._installed("DejaVu Sans"):
            with self.assertRaises(ValueError) as caught:
                resolve_font(["Frank Ruehl CLM", "Ezra SIL"])
        message = str(caught.exception)
        self.assertIn("Frank Ruehl CLM", message)
        self.assertIn("Ezra SIL", message)

    def test_no_fontconfig_defers_the_choice_to_the_renderer(self):
        with patch.object(typography_module.shutil, "which", return_value=None):
            self.assertIsNone(resolve_font(["A Font That Does Not Exist"]))

    def test_an_unresolvable_chain_fails_validation_naming_the_family(self):
        with self._installed("DejaVu Sans"):
            with self.assertRaises(ValidationError) as caught:
                TypographyConfig.model_validate({"fonts": {"hebrew": ["No Such Face"]}})
        message = str(caught.exception)
        self.assertIn("hebrew", message)
        self.assertIn("No Such Face", message)


class TestContradictorySettings(unittest.TestCase):
    def test_styling_notes_that_are_switched_off_is_an_error(self):
        """Both intentions cannot hold, and the one that silently wins deletes
        the notes."""
        with self.assertRaises(ValidationError) as caught:
            _validate({"notes": {"placement": "none"}, "styles": {"note": {"size": "9pt"}}})
        self.assertIn("placement", str(caught.exception))

    def test_switching_notes_off_alone_is_fine(self):
        config = _validate({"notes": {"placement": "none"}})
        self.assertEqual(config.notes.placement, NotePlacement.NONE)

    def test_running_head_all_cannot_be_combined_with_odd_or_even(self):
        with self.assertRaises(ValidationError):
            _validate({"page_header": {"all": {"left": "x"}, "odd": {"left": "y"}}})


class TestWhatTheUserWrote(unittest.TestCase):
    """The renderer emits a directive only for a setting that was written, so
    "written" has to stay distinguishable from "left at its default"."""

    def test_an_unwritten_field_is_not_in_fields_set(self):
        config = _validate({"line_numbers": {"increment": 10}})
        self.assertIn("increment", config.line_numbers.model_fields_set)
        self.assertNotIn("margin", config.line_numbers.model_fields_set)

    def test_a_field_written_at_its_default_value_still_counts_as_written(self):
        config = _validate({"line_numbers": {"increment": 5}})
        self.assertIn("increment", config.line_numbers.model_fields_set)


class TestFontNormalSizes(unittest.TestCase):
    def test_mixed_legacy_and_sized_entries(self):
        family = FontFamily.model_validate([
            {"name": "One", "normal_size": 12}, "Two", {"name": "Three"},
        ])
        self.assertEqual(family.names, ["One", "Two", "Three"])
        self.assertEqual([entry.normal_size for entry in family.entries], [12, None, None])
        self.assertEqual(FontFamily.model_validate(family.model_dump()), family)

    def test_invalid_sizes_are_rejected(self):
        for size in [0, -1, float("inf"), float("nan"), True, "12pt", "12"]:
            with self.subTest(size=size), self.assertRaises(ValueError):
                FontFamily.model_validate([{"name": "One", "normal_size": size}])

    def test_entry_keys_and_name_are_validated(self):
        for entry in [{"normal_size": 12}, {"name": ""}, {"name": "One", "size": 12}]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                FontFamily.model_validate([entry])


class TestTextStyle(unittest.TestCase):
    def test_an_empty_style_says_nothing(self):
        self.assertTrue(TextStyle().is_empty())
        self.assertFalse(TextStyle(weight=FontWeight.BOLD).is_empty())

    def test_a_font_family_accepts_a_list_or_a_string(self):
        self.assertEqual(FontFamily.model_validate("One").names, ["One"])
        self.assertEqual(FontFamily.model_validate(["One", "Two"]).names, ["One", "Two"])



class TestNonNegativeLengths(unittest.TestCase):
    """A margin, a page or a rule cannot be negative; TeX would accept one and
    produce a page that makes no sense."""

    def test_negative_geometry_is_refused(self):
        for data in (
            {"page": {"margins": {"top": "-1cm"}}},
            {"page": {"paper": "custom", "width": "-6in", "height": "9in"}},
            {"paragraphs": {"spacing": "-1ex"}},
            {"notes": {"separation": "-2pt"}},
        ):
            with self.assertRaises(ValidationError, msg=repr(data)):
                _validate(data)

    def test_zero_and_positive_geometry_are_accepted(self):
        _validate({"page": {"margins": {"top": "0pt", "inner": "2.5cm"}}})

    def test_a_paragraph_indent_may_still_hang(self):
        _validate({"paragraphs": {"indent": "-1em"}})


class TestColumnWidth(unittest.TestCase):
    def test_a_column_of_half_the_block_or_more_is_refused(self):
        _validate({"parallel": {"column_width": "49.5%"}})
        for width in ("50%", "75%", "100%"):
            _refused(self, {"parallel": {"column_width": width}}, "under 50%")


class TestFontKeys(unittest.TestCase):
    """A family key names a TeX command, which is letters only."""

    def test_lower_case_words_joined_by_hyphens(self):
        _validate({"fonts": {"note-sans": "DejaVu Sans", "sans": "DejaVu Sans"}})

    def test_keys_that_would_not_make_a_distinct_command_are_refused(self):
        for key in ("sans2", "note_sans", "Note", "note--sans", "-sans", "sans-"):
            _refused(self, {"fonts": {key: "DejaVu Sans"}}, key)


class TestFontFaceNames(unittest.TestCase):
    def test_tex_specials_in_a_face_name_are_refused(self):
        for name in ("Bad}Font", "Font\\x", "50% Serif", "A_B"):
            with self.assertRaises(ValidationError, msg=name):
                _validate({"fonts": {"latin": [name]}})

    def test_ordinary_face_names_are_accepted(self):
        _validate({"fonts": {"latin": ["TeX Gyre Pagella", "Linux Libertine O"]}})


class TestBlockOnlyStyleProperties(unittest.TestCase):
    """`align` and `space_*` were accepted on every role and honoured on few."""

    def test_align_on_an_inline_role_is_refused(self):
        _refused(self, {"styles": {"note": {"align": "center"}}}, "styles.note.align")

    def test_space_on_a_role_set_inside_a_paragraph_is_refused(self):
        _refused(
            self, {"styles": {"heading1": {"space_before": "1ex"}}}, "styles.heading1.space_before"
        )

    def test_an_explicit_null_asks_for_nothing(self):
        _validate({"styles": {"note": {"align": None, "space_before": None}}})

    def test_the_roles_that_honour_them_accept_them(self):
        _validate({
            "styles": {
                "heading2": {"align": "left"},
                "list_label": {"align": "right"},
                "title_main": {"align": "left", "space_after": "2ex"},
                "section_separator": {"space_before": "1ex"},
            }
        })


class TestHtmlDoesNotResolveFonts(unittest.TestCase):
    def test_a_missing_font_is_not_an_error_when_fonts_are_not_resolved(self):
        with patch.object(
            typography_module, "_installed_font_families", return_value=frozenset()
        ):
            with self.assertRaises(ValidationError):
                TypographyConfig.model_validate({"fonts": {"latin": "No Such Face"}})
            config = TypographyConfig.model_validate(
                {"fonts": {"latin": "No Such Face"}}, context={RESOLVE_FONTS: False}
            )
        self.assertEqual(["No Such Face"], config.fonts["latin"].names)


if __name__ == "__main__":
    unittest.main()


class TestBookmarksConfig(unittest.TestCase):
    """The PDF outline of a work that names a section in two languages.

    This is the one setting whose default deliberately does *not* reproduce prior
    output: before it, a parallel compile wrote two entries per heading, interleaved
    out of document order. Nobody chose that, so the default fixes it.
    """

    def test_default_is_combined(self):
        self.assertEqual("combined", _validate({}).bookmarks.from_.value)

    def test_from_is_read_under_its_yaml_name(self):
        """The field is ``from_`` in Python because ``from`` is a keyword, but the
        settings file must still say ``from``."""
        self.assertEqual("primary", _validate({"bookmarks": {"from": "primary"}})
                         .bookmarks.from_.value)
        self.assertEqual("alt", _validate({"bookmarks": {"from": "alt"}})
                         .bookmarks.from_.value)

    def test_an_unknown_source_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"bookmarks": {"from": "both"}})
        self.assertIn("bookmarks.from", str(caught.exception))

    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"bookmarks": {"depth": 2}})
        self.assertIn("depth", str(caught.exception))


class TestHeadingTranslationStyle(unittest.TestCase):
    """The translated title under a heading, where a division is titled twice."""

    def test_default_is_the_documented_appearance(self):
        """Normal size, italic, centred: the second title reads as naming the same
        section again rather than opening one of its own."""
        style = _validate({}).styles.heading_translation
        self.assertEqual("normal", style.size)
        self.assertEqual("italic", style.style)
        self.assertEqual("center", style.align)

    def test_it_is_configurable_like_any_other_role(self):
        style = _validate(
            {"styles": {"heading_translation": {"size": "small", "align": "right"}}}
        ).styles.heading_translation
        self.assertEqual("small", style.size)
        self.assertEqual("right", style.align)

    def test_an_unknown_attribute_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"styles": {"heading_translation": {"colour": "red"}}})
        self.assertIn("colour", str(caught.exception))


class TestHeadingsConfig(unittest.TestCase):
    """Headings on the page, where a work titles a section in two languages.

    Deliberately the same vocabulary as `bookmarks`: it is the same question about the
    same pair of titles, asked of the page rather than of the outline.
    """

    def test_default_is_combined(self):
        self.assertEqual("combined", _validate({}).headings.from_.value)

    def test_from_is_read_under_its_yaml_name(self):
        self.assertEqual("primary", _validate({"headings": {"from": "primary"}})
                         .headings.from_.value)
        self.assertEqual("alt", _validate({"headings": {"from": "alt"}})
                         .headings.from_.value)

    def test_it_shares_the_bookmark_vocabulary_and_adds_one(self):
        """One vocabulary for one question, so a settings file reads consistently — plus
        `both`, which only a page can honour."""
        from opensiddur.exporter.typography import BookmarkSource, HeadingSource
        self.assertEqual({s.value for s in BookmarkSource} | {"both"},
                         {s.value for s in HeadingSource})

    def test_an_unknown_source_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"headings": {"from": "matched"}})
        self.assertIn("headings.from", str(caught.exception))

    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"headings": {"level": 2}})
        self.assertIn("level", str(caught.exception))

    def test_both_is_accepted_here_and_not_in_bookmarks(self):
        """A page can show two titles in two places; an outline entry is one line."""
        self.assertEqual("both", _validate({"headings": {"from": "both"}})
                         .headings.from_.value)
        with self.assertRaises(ValidationError):
            _validate({"bookmarks": {"from": "both"}})


class TestInstructionsConfig(unittest.TestCase):
    """Rubrics, where a work prints the same one in both columns."""

    def test_default_is_both(self):
        """The conservative value, not the tidy one: deduplicating a rubric where the
        columns are not aligned at its position loses it for one column's reader, where
        keeping both merely repeats it. Headings default the other way, and the asymmetry
        is deliberate — a heading is lifted clear of the columns, so deduplicating one
        costs nothing."""
        self.assertEqual("both", _validate({}).instructions.from_.value)
        self.assertEqual("combined", _validate({}).headings.from_.value)

    def test_it_takes_the_heading_vocabulary(self):
        """The same question asked of a rubric, so the same four values."""
        from opensiddur.exporter.typography import HeadingSource
        for value in (s.value for s in HeadingSource):
            with self.subTest(value=value):
                self.assertEqual(value, _validate({"instructions": {"from": value}})
                                 .instructions.from_.value)

    def test_an_unknown_source_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"instructions": {"from": "spanning"}})
        self.assertIn("instructions.from", str(caught.exception))

    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"instructions": {"span": True}})
        self.assertIn("span", str(caught.exception))


class TestParallelColumnSettings(unittest.TestCase):
    """Column geometry is read only in the `pairs` layout, so naming it under another is an
    error rather than a setting that silently does nothing."""

    def test_column_keys_are_accepted_in_pairs(self):
        config = _validate({"parallel": {"layout": "pairs", "column_width": "40%",
                                         "column_position": "left"}})
        self.assertEqual(config.parallel.column_width, "40%")

    def test_column_keys_are_rejected_elsewhere(self):
        for layout in ("pages", "interleaved"):
            for key, value in (("column_width", "40%"), ("column_position", "left")):
                with self.subTest(layout=layout, key=key):
                    with self.assertRaises(ValidationError) as caught:
                        _validate({"parallel": {"layout": layout, key: value}})
                    self.assertIn(key, str(caught.exception))
                    self.assertIn(f"layout: {layout}", str(caught.exception))

    def test_the_column_keys_default_quietly_in_other_layouts(self):
        """Their defaults are not something the settings file asked for."""
        config = _validate({"parallel": {"layout": "pages"}})
        self.assertIs(config.parallel.layout, ParallelLayout.PAGES)


class TestInterleavedLayout(unittest.TestCase):
    """The third parallel layout, and the settings that only it reads."""

    def test_interleaved_is_a_layout(self):
        config = _validate({"parallel": {"layout": "interleaved"}})
        self.assertIs(config.parallel.layout, ParallelLayout.INTERLEAVED)

    def test_defaults(self):
        interleaved = _validate({}).parallel.interleaved
        self.assertEqual(interleaved.translation_size, NamedSize.SMALL)
        self.assertEqual(interleaved.translation_indent, "1em")
        self.assertEqual(interleaved.spacing, "0.25em")
        self.assertIs(interleaved.line_numbers, InterleavedLineNumbers.PRIMARY)

    def test_translation_size_is_named_or_absolute(self):
        for size in ("x-small", "9pt"):
            config = _validate({"parallel": {"interleaved": {"translation_size": size}}})
            self.assertEqual(config.parallel.interleaved.translation_size, size)
        for size in ("0.8em", "tiny"):
            with self.assertRaises(ValidationError, msg=size):
                _validate({"parallel": {"interleaved": {"translation_size": size}}})

    def test_lengths_need_a_unit(self):
        for key in ("translation_indent", "spacing"):
            with self.assertRaises(ValidationError, msg=key):
                _validate({"parallel": {"interleaved": {key: "1"}}})

    def test_line_numbers_is_closed(self):
        self.assertIs(
            _validate({"parallel": {"interleaved": {"line_numbers": "both"}}})
            .parallel.interleaved.line_numbers,
            InterleavedLineNumbers.BOTH,
        )
        with self.assertRaises(ValidationError):
            _validate({"parallel": {"interleaved": {"line_numbers": "translation"}}})

    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            _validate({"parallel": {"interleaved": {"rule": True}}})
        self.assertIn("rule", str(caught.exception))
