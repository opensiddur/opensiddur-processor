"""Tests for the TeX side of typography settings.

``opensiddur/exporter/tex/typography_tex.py`` is a pure function of the settings,
so it is tested directly rather than through the XSLT.

Every setting is emitted at its resolved value, written or not: the stylesheet
defines none of the macros a setting controls. That every documented default
arrives is tested in ``test_typography_defaults.py``; these test how each setting
is rendered.
"""

import unittest
from unittest.mock import patch

from pydantic import ValidationError

from opensiddur.exporter import typography as typography_module
from opensiddur.exporter.typography import NamedSize, TextStyle, TypographyConfig
from opensiddur.exporter.tex.typography_tex import (
    build_typography_preamble,
    documentclass_options,
    style_tokens,
)


def _no_fontconfig():
    """A machine that cannot be asked which fonts are installed.

    Font resolution then defers to the renderer, which is the branch that emits
    a fallback chain — the one worth testing, since it does not depend on which
    fonts this machine happens to have. Both validation and emission consult
    fontconfig, so both have to run inside this.
    """
    return patch.object(typography_module, "_installed_font_families", return_value=None)


def _config(data: dict) -> TypographyConfig:
    with _no_fontconfig():
        return TypographyConfig.model_validate(data)


def _tex(data: dict, has_parallel: bool = False) -> str:
    with _no_fontconfig():
        return build_typography_preamble(
            TypographyConfig.model_validate(data), has_parallel
        )


def _macro(tex: str, name: str) -> str:
    """The definition of one macro in a preamble, continuation lines included."""
    lines = tex.splitlines()
    for index, line in enumerate(lines):
        if line.startswith((rf"\newcommand{{{name}}}", rf"\renewcommand*{{{name}}}")):
            end = index + 1
            while lines[end - 1].endswith("%"):
                end += 1
            return "\n".join(lines[index:end])
    raise AssertionError(f"{name} is not defined")


class TestNothingConfigured(unittest.TestCase):
    def test_an_empty_settings_section_states_the_defaults(self):
        """The stylesheet has no copy of them to fall back on."""
        tex = _tex({})
        self.assertIn(r"\setlength{\parskip}{0.5em}", tex)
        self.assertIn(r"\newcommand{\OSheadA}[1]", tex)
        self.assertIn(r"\lineation{page}", tex)

    def test_default_class_options_are_what_they_have_always_been(self):
        self.assertEqual(documentclass_options(_config({})), "11pt,letterpaper")


class TestDocumentClassOptions(unittest.TestCase):
    def test_paper_and_base_size(self):
        options = documentclass_options(_config({"page": {"paper": "a5paper", "base_font_size": "12pt"}}))
        self.assertEqual(options, "12pt,a5paper")

    def test_one_sided_and_open_anywhere(self):
        options = documentclass_options(
            _config({"page": {"sides": "one", "chapter_start": "any"}})
        )
        self.assertEqual(options, "11pt,letterpaper,oneside,openany")

    def test_the_class_defaults_are_left_unsaid(self):
        """twoside and openright are the class's own, so saying them would
        change the option list of a document that configured nothing."""
        options = documentclass_options(
            _config({"page": {"sides": "two", "chapter_start": "recto"}})
        )
        self.assertEqual(options, "11pt,letterpaper")

    def test_custom_paper_is_left_out_of_the_class_options(self):
        """There is no class option for it; geometry sets the dimensions."""
        config = _config({"page": {"paper": "custom", "width": "6in", "height": "9in"}})
        self.assertEqual(documentclass_options(config), "11pt")
        tex = build_typography_preamble(config)
        self.assertIn(r"\geometry{paperwidth=6in,paperheight=9in}", tex)


class TestGeometry(unittest.TestCase):
    def test_margins_are_emitted_only_when_written(self):
        tex = _tex({"page": {"margins": {"top": "2cm", "inner": "25mm"}}})
        self.assertIn("top=2cm", tex)
        self.assertIn("inner=25mm", tex)
        self.assertNotIn("bottom=", tex)
        self.assertNotIn("outer=", tex)

    def test_inner_and_outer_become_left_and_right_on_a_one_sided_document(self):
        """geometry only understands inner/outer for a two-sided document; on a
        one-sided one they are simply the left and right margins."""
        tex = _tex({"page": {"sides": "one", "margins": {"inner": "1in", "outer": "2in"}}})
        self.assertIn("left=1in", tex)
        self.assertIn("right=2in", tex)
        self.assertNotIn("inner=", tex)

    def test_binding_offset(self):
        self.assertIn("bindingoffset=5mm", _tex({"page": {"margins": {"binding_offset": "5mm"}}}))

    def test_landscape(self):
        self.assertIn(r"\geometry{landscape}", _tex({"page": {"orientation": "landscape"}}))

    def test_no_geometry_call_when_the_page_is_not_configured(self):
        self.assertNotIn(r"\geometry", _tex({"page": {"base_font_size": "12pt"}}))


class TestBinding(unittest.TestCase):
    """A right-bound book is the default (#265)."""

    _SWAP = r"\oddsidemargin=\evensidemargin"

    def test_pdf_opens_right_to_left_with_a_cover_page_by_default(self):
        self.assertIn(r"\hypersetup{pdfdirection=R2L,pdfpagelayout=TwoPageRight}", _tex({}))

    def test_left_binding_opens_left_to_right(self):
        self.assertIn(r"\hypersetup{pdfdirection=L2R,pdfpagelayout=TwoPageRight}",
                      _tex({"page": {"binding": "left"}}))

    def test_one_sided_document_opens_a_page_at_a_time(self):
        """A one-sided document has no spreads, but still reads in its direction."""
        self.assertIn(r"\hypersetup{pdfdirection=R2L,pdfpagelayout=SinglePage}",
                      _tex({"page": {"sides": "one"}}))

    def test_right_binding_swaps_the_side_margins(self):
        """The class's own margins are asymmetric too, so the swap does not wait
        for a margin to be configured."""
        tex = _tex({})
        self.assertIn(self._SWAP, tex)
        self.assertIn(r"\evensidemargin=\dimen0", tex)
        self.assertIn(r"\reversemarginpar", tex)
        self.assertNotIn(r"\geometry", tex)

    def test_the_swap_runs_after_geometry_has_set_the_margins(self):
        self.assertIn(r"\AddToHook{begindocument/end}", _tex({"page": {"margins": {"inner": "1in"}}}))

    def test_left_binding_and_one_sided_documents_keep_their_margins(self):
        for page in ({"binding": "left"}, {"sides": "one"}):
            with self.subTest(page=page):
                tex = _tex({"page": page})
                self.assertNotIn(self._SWAP, tex)
                self.assertNotIn(r"\reversemarginpar", tex)

    def test_binding_must_be_left_or_right(self):
        with self.assertRaises(ValidationError):
            _config({"page": {"binding": "top"}})


class TestFonts(unittest.TestCase):
    def test_an_undeclared_family_is_chosen_when_the_document_is_typeset(self):
        """The defaults are never checked against the installed fonts (#88): a
        document that asked for nothing must build on a machine without this
        project's house fonts. So TeX chooses, and without any of the Latin
        defaults the class's own face stands."""
        with patch.object(
            typography_module, "_installed_font_families", return_value=frozenset()
        ):
            tex = build_typography_preamble(TypographyConfig.model_validate({}))
        self.assertIn("\\IfFontExistsTF{Linux Libertine O}{\n  \\setmainfont{Linux Libertine O}\n}{\n}", tex)
        self.assertIn(r"\IfFontExistsTF{SBL Hebrew}", tex)
        self.assertIn(r"\newfontfamily\hebrewfont[Renderer=HarfBuzz,Script=Hebrew,BoldFont={*},AutoFakeBold=2]{FreeSerif}", tex)

    def test_a_declared_latin_family_sets_the_main_font(self):
        """One name is not a chain: it is named outright, with no test around
        it, so a font that is not there fails the build rather than quietly
        becoming something else."""
        tex = _tex({"fonts": {"latin": "TeX Gyre Pagella"}})
        self.assertIn(r"\setmainfont{TeX Gyre Pagella}", tex)
        self.assertEqual(1, tex.count(r"\setmainfont"))
        self.assertNotIn(r"\IfFontExistsTF{TeX Gyre Pagella}", tex)

    def test_a_declared_hebrew_family_is_declared_once(self):
        """In place of the default chain, not after it: a second \\newfontfamily
        would be a "command already defined" error."""
        tex = _tex({"fonts": {"hebrew": ["Ezra SIL"]}})
        self.assertEqual(1, tex.count(r"\newfontfamily\hebrewfont"))
        self.assertNotIn(r"\renewfontfamily", tex)
        self.assertNotIn("Frank Ruehl CLM", tex)
        self.assertIn("Renderer=HarfBuzz", tex)
        self.assertIn(r"\let\hebrewfontsf\hebrewfont", tex)

    def test_a_chain_becomes_nested_tests_when_fontconfig_cannot_choose(self):
        tex = _tex({"fonts": {"latin": ["First", "Second", "Third"]}})
        self.assertIn(r"\IfFontExistsTF{First}", tex)
        self.assertIn(r"\IfFontExistsTF{Second}", tex)
        # The last name is the fallback, not another test.
        self.assertNotIn(r"\IfFontExistsTF{Third}", tex)
        self.assertIn(r"\setmainfont{Third}", tex)

    def test_a_resolved_chain_names_one_font_outright(self):
        with patch.object(
            typography_module,
            "_installed_font_families",
            return_value=frozenset({"second", "freeserif"}),
        ):
            config = TypographyConfig.model_validate({"fonts": {"latin": ["First", "Second"]}})
            tex = build_typography_preamble(config)
        self.assertIn(r"\setmainfont{Second}", tex)
        self.assertNotIn(r"\IfFontExistsTF{First}", tex)

    def test_a_user_family_gets_a_command_named_after_its_key(self):
        tex = _tex({"fonts": {"note-sans": "DejaVu Sans"}})
        self.assertIn(r"\newfontfamily\OSfontNoteSans{DejaVu Sans}", tex)

    def test_a_style_selects_a_user_family_by_that_command(self):
        tex = _tex(
            {"fonts": {"note-sans": "DejaVu Sans"}, "styles": {"note": {"font": "note-sans"}}}
        )
        self.assertIn(r"\newcommand{\notenote}[1]{{\OSfontNoteSans #1}}", tex)


class TestStyleTokens(unittest.TestCase):
    def test_the_named_ladder_maps_onto_the_size_commands(self):
        for name, command in (
            (NamedSize.XXX_SMALL, r"\tiny"),
            (NamedSize.SMALL, r"\small"),
            (NamedSize.NORMAL, r"\normalsize"),
            (NamedSize.XX_LARGE, r"\LARGE"),
            (NamedSize.XXXX_LARGE, r"\Huge"),
        ):
            self.assertEqual(style_tokens(TextStyle(size=name)), command)

    def test_an_absolute_size_carries_a_baseline_too(self):
        """\\fontsize sets both, so a size given alone would leave the leading
        of whatever font was in force."""
        self.assertEqual(
            style_tokens(TextStyle(size="10pt")), r"\fontsize{10pt}{12pt}\selectfont"
        )

    def test_line_spacing_scales_the_baseline_of_an_absolute_size(self):
        self.assertEqual(
            style_tokens(TextStyle(size="10pt"), line_spacing=1.5),
            r"\fontsize{10pt}{18pt}\selectfont",
        )

    def test_weight_style_and_variant(self):
        self.assertEqual(
            style_tokens(TextStyle(weight="bold", style="italic", variant="small-caps")),
            r"\bfseries\itshape\scshape",
        )

    def test_normal_is_stated_rather_than_implied(self):
        """A role whose default is bold needs a way to say "not bold"."""
        self.assertEqual(style_tokens(TextStyle(weight="normal")), r"\mdseries")


class TestStyles(unittest.TestCase):
    def test_a_written_role_replaces_its_default_whole(self):
        """And the roles it does not name keep theirs."""
        tex = _tex({"styles": {"heading1": {"size": "large"}}})
        self.assertEqual(r"\newcommand{\OSheadA}[1]{{\normalfont\large #1}}", _macro(tex, r"\OSheadA"))
        self.assertIn(r"{\normalfont\Large\bfseries #1}", _macro(tex, r"\OSheadB"))

    def test_headings_are_aligned_with_fill_glue_not_a_paragraph(self):
        """reledmac captures numbered text one \\par-delimited line at a time, so
        a \\par here would escape that capture and, under reledpar, land outside
        its column."""
        tex = _tex({"styles": {"heading1": {"size": "large", "align": "center"}}})
        self.assertIn(r"\mbox{}\hfill{\normalfont\large #1}\hfill\mbox{}", tex)
        self.assertNotIn(r"\centering", _macro(tex, r"\OSheadA"))
        self.assertNotIn(r"\par", _macro(tex, r"\OSheadA"))

    def test_left_and_right_alignment_use_one_sided_fill(self):
        self.assertIn(
            r"\newcommand{\OSheadA}[1]{{\normalfont\large #1}\hfill\mbox{}}",
            _tex({"styles": {"heading1": {"size": "large", "align": "left"}}}),
        )
        self.assertIn(
            r"\newcommand{\OSheadA}[1]{\mbox{}\hfill{\normalfont\large #1}}",
            _tex({"styles": {"heading1": {"size": "large", "align": "right"}}}),
        )

    def test_title_page_roles_are_real_paragraphs(self):
        """A title page is set outside all numbering, so it can have proper
        centred paragraphs with line breaking."""
        tex = _tex({"styles": {"title_main": {"size": "xxxx-large", "align": "center"}}})
        self.assertIn(r"{\centering\normalfont\Huge #1\par}", tex)

    def test_space_before_and_after_sit_outside_the_group(self):
        tex = _tex({"styles": {"byline": {"space_before": "3ex", "space_after": "1ex"}}})
        self.assertIn(r"\newcommand{\OSByline}[1]{\vspace{3ex}{", tex)
        self.assertTrue(_macro(tex, r"\OSByline").endswith(r"\par}\vspace{1ex}}"))

    def test_verse_and_chapter_numbers_stay_left_to_right(self):
        """Digits laid out in an RTL context come out reversed: 50 reads 05."""
        for role, macro in (("verse_number", r"\vno"), ("chapter_number", r"\chno")):
            tex = _tex({"styles": {role: {"size": "small"}}})
            self.assertIn(rf"\newcommand{{{macro}}}[1]{{", tex)
            self.assertIn(r"\textdir TLT\foreignlanguage{english}{", tex)

    def test_body_style_goes_through_the_document_wide_hook(self):
        self.assertIn(
            r"\newcommand{\OSBodyStyle}{\small}", _tex({"styles": {"body": {"size": "small"}}})
        )

    def test_notes_and_instructions(self):
        self.assertIn(
            r"\newcommand{\notenote}[1]{{\mdseries #1}}",
            _tex({"styles": {"note": {"weight": "normal"}}}),
        )
        self.assertIn(
            r"\newcommand{\instructionnote}[1]{{\itshape #1}}",
            _tex({"styles": {"instruction": {"style": "italic"}}}),
        )


class TestParagraphs(unittest.TestCase):
    def test_indent_spacing_and_leading(self):
        tex = _tex({"paragraphs": {"indent": "1em", "spacing": "1ex", "line_spacing": 1.5}})
        self.assertIn(r"\setlength{\parindent}{1em}", tex)
        self.assertIn(r"\setlength{\parskip}{1ex}", tex)
        self.assertIn(r"\linespread{1.5}\selectfont", tex)

    def test_alignment_is_applied_where_it_takes_effect(self):
        """\\raggedright in a preamble is a no-op; it has to be applied once the
        document has started."""
        self.assertIn(r"\AtBeginDocument{\raggedright}", _tex({"paragraphs": {"alignment": "left"}}))

    def test_justified_is_the_absence_of_raggedness(self):
        self.assertNotIn(r"\AtBeginDocument", _tex({"paragraphs": {"alignment": "justify"}}))


class TestLineNumbers(unittest.TestCase):
    def test_switching_them_off_uses_reledmacs_own_switch(self):
        """The numbering machinery still runs, so cross-references and the
        apparatus are unaffected; only the printing stops."""
        self.assertIn(r"\numberlinefalse", _tex({"line_numbers": {"enabled": False}}))

    def test_switching_them_off_still_configures_the_count(self):
        """Only the printing stops; the lines are still counted, and \\lineation still
        decides where the count restarts."""
        tex = _tex({"line_numbers": {"enabled": False, "increment": 2}}, has_parallel=True)
        self.assertIn(r"\numberlinefalse", tex)
        self.assertIn(r"\linenumincrement{2}", tex)
        self.assertIn(r"\lineation{page}", tex)
        self.assertIn(r"\lineationR{page}", tex)

    def test_increment_first_and_separation(self):
        tex = _tex({"line_numbers": {"increment": 2, "first": 1, "separation": "2em"}})
        self.assertIn(r"\linenumincrement{2}", tex)
        self.assertIn(r"\firstlinenum{1}", tex)
        self.assertIn(r"\setlength{\linenumsep}{2em}", tex)

    def test_the_right_hand_stream_is_configured_only_in_a_parallel_document(self):
        """\\linenumincrementR does not exist unless reledpar is loaded, and it is
        loaded only for a document with two aligned streams."""
        self.assertNotIn(r"\linenumincrementR", _tex({"line_numbers": {"increment": 2}}))
        self.assertIn(
            r"\linenumincrementR{2}", _tex({"line_numbers": {"increment": 2}}, has_parallel=True)
        )

    def test_lineation_unit_and_margin(self):
        tex = _tex({"page": {"binding": "left"},
                    "line_numbers": {"unit": "section", "margin": "inner"}})
        self.assertIn(r"\lineation{section}", tex)
        self.assertIn(r"\linenummargin{inner}", tex)

    def test_inner_and_outer_line_number_margins_follow_a_right_binding(self):
        """reledmac's inner and outer assume a left binding."""
        for margin, emitted in (("inner", "outer"), ("outer", "inner"),
                                ("left", "left"), ("right", "right")):
            with self.subTest(margin=margin):
                tex = _tex({"line_numbers": {"margin": margin}}, has_parallel=True)
                self.assertIn(rf"\linenummargin{{{emitted}}}", tex)
                self.assertIn(rf"\linenummarginR{{{emitted}}}", tex)

    def test_line_number_margins_are_not_mirrored_without_a_recto_and_verso(self):
        for page in ({"binding": "left"}, {"sides": "one"}):
            with self.subTest(page=page):
                tex = _tex({"page": page, "line_numbers": {"margin": "outer"}})
                self.assertIn(r"\linenummargin{outer}", tex)

    def test_lineation_applies_to_both_series_when_parallel(self):
        r"""\lineation sets the main series only; reledpar keeps a separate \bypage@R.
        This section is emitted after the XSLT's defaults and wins over them, so a
        settings file naming a unit would otherwise put the right column back to
        numbering by section."""
        self.assertNotIn(r"\lineationR", _tex({"line_numbers": {"unit": "section"}}))
        tex = _tex({"line_numbers": {"unit": "section"}}, has_parallel=True)
        self.assertIn(r"\lineation{section}", tex)
        self.assertIn(r"\lineationR{section}", tex)

    def test_lineation_by_page_also_resets_the_right_column(self):
        """`page' is the default the XSLT already emits, so writing it in a settings file
        looks like a no-op -- and used to silently undo the right column's reset."""
        tex = _tex({"line_numbers": {"unit": "page"}}, has_parallel=True)
        self.assertIn(r"\lineationR{page}", tex)

    def test_hebrew_numerals_need_no_left_to_right_wrapper(self):
        """Their output is Hebrew letters, which belong in the surrounding
        direction; only digits have to be forced."""
        tex = _tex({"line_numbers": {"numerals": "hebrew"}})
        self.assertIn(r"\hebrewnumeral{#1}", tex)
        self.assertNotIn(r"\textdir TLT", _macro(tex, r"\linenumrep"))

    def test_the_number_is_formatted_through_linenumrep(self):
        """\\linenumberstyle is a declaration whose only job is to define
        \\linenumrep, and reledmac calls it once as it loads — so redefining it
        afterwards silently does nothing."""
        tex = _tex({"line_numbers": {"numerals": "hebrew"}})
        self.assertIn(r"\renewcommand*{\linenumrep}", tex)
        self.assertNotIn(r"\linenumberstyle", tex)

    def test_a_line_number_style_and_the_numeral_system_share_one_macro(self):
        """Emitting them separately would let the second silently discard the
        first."""
        tex = _tex(
            {
                "styles": {"line_number": {"size": "small"}},
                "line_numbers": {"numerals": "hebrew"},
            }
        )
        self.assertEqual(tex.count(r"\renewcommand*{\linenumrep}"), 1)
        self.assertIn(r"\small\hebrewnumeral{#1}", tex)

    def test_unstyled_arabic_numerals_are_reledmacs_own(self):
        """reledmac's \\ledlinenum already sets them left to right in the main series;
        reledpar's right-hand series does not, so it is always given the switch."""
        self.assertNotIn(r"\linenumrep", _tex({}))
        tex = _tex({}, has_parallel=True)
        self.assertIn(r"\renewcommand*{\linenumrepR}[1]{\hbox{\textdir TLT\@arabic{#1}}}", tex)
        self.assertIn(r"\renewcommand*{\sublinenumrepR}[1]{\hbox{\textdir TLT\@arabic{#1}}}", tex)

    def test_a_numeral_setting_keeps_the_right_sub_line_numbers_left_to_right(self):
        tex = _tex({"line_numbers": {"numerals": "hebrew"}}, has_parallel=True)
        self.assertIn(r"\renewcommand*{\sublinenumrepR}[1]{\hbox{\textdir TLT\@arabic{#1}}}", tex)

    def test_the_right_hand_stream_is_formatted_only_in_a_parallel_document(self):
        settings = {"styles": {"line_number": {"size": "small"}}}
        self.assertNotIn(r"\linenumrepR", _tex(settings))
        self.assertIn(r"\linenumrepR", _tex(settings, has_parallel=True))


class TestNotes(unittest.TestCase):
    def test_the_default_anchor_is_raised_and_zero_width(self):
        """Zero width is what keeps the annotated text from being respaced, and
        with it the two sides of a parallel text aligned."""
        tex = _tex({"notes": {"anchor": "interlinear"}})
        self.assertIn(r"\hbox to 0pt", tex)
        self.assertIn(r"\raisebox{1.5ex}", tex)

    def test_a_superscript_anchor(self):
        mark = _macro(_tex({"notes": {"anchor": "superscript"}}), r"\OSInterlinearNotemark")
        self.assertIn(r"\textsuperscript", mark)
        self.assertNotIn(r"\hbox to 0pt", mark)

    def test_an_inline_anchor(self):
        mark = _macro(_tex({"notes": {"anchor": "inline"}}), r"\OSInterlinearNotemark")
        self.assertNotIn(r"\textsuperscript", mark)
        self.assertNotIn(r"\raisebox", mark)

    def test_the_mark_keeps_its_sans_face_unless_a_font_is_asked_for(self):
        """Changing the anchor should not silently change the face too."""
        self.assertIn(r"\sffamily", _tex({"notes": {"anchor": "inline"}}))
        tex = _tex(
            {"fonts": {"serif": "FreeSerif"}, "styles": {"note_mark": {"font": "serif"}}}
        )
        self.assertNotIn(r"\sffamily", tex)
        self.assertIn(r"\OSfontSerif", tex)

    def test_the_lemma_is_not_a_setting(self):
        """A note anchors at a point, so there are no annotated words to repeat;
        the apparatus lemma is the mark itself."""
        with self.assertRaises(Exception):
            _tex({"notes": {"show_lemma": True}})


class TestMarkers(unittest.TestCase):
    def test_the_section_separator_is_escaped(self):
        tex = _tex({"markers": {"section_separator": "~ & ~"}})
        self.assertIn(r"\textasciitilde{}", tex)
        self.assertIn(r"\&", tex)

    def test_an_empty_separator_leaves_nothing_but_the_space(self):
        self.assertIn(r"\newcommand{\OSSectionSeparator}{}", _tex({"markers": {"section_separator": ""}}))

    def test_hiding_verse_and_chapter_numbers(self):
        tex = _tex({"markers": {"verse_numbers": "hidden", "chapter_numbers": "hidden"}})
        self.assertIn(r"\newcommand{\vno}[1]{}", tex)
        self.assertIn(r"\newcommand{\chno}[1]{}", tex)

    def test_shown_numbers_are_set_in_their_style(self):
        tex = _tex({"markers": {"verse_numbers": "shown"}})
        self.assertIn(r"\newcommand{\vno}[1]{\textsuperscript{", tex)
        self.assertIn(r"\newcommand{\chno}[1]{{\large\bfseries", tex)

    def test_conditional_inline_markers(self):
        tex = _tex({"markers": {"conditional": {"inline_open": "(", "inline_close": ")"}}})
        self.assertIn(r"\newcommand{\OSCondStartInline}{{\bfseries(}}", tex)
        self.assertIn(r"\newcommand{\OSCondEndInline}{{\bfseries)}}", tex)

    def test_the_conditional_block_rule(self):
        tex = _tex({"markers": {"conditional": {"rule_width": "50%", "rule_thickness": "1pt"}}})
        self.assertIn(r"\rule{0.5\hsize}{1pt}", tex)

    def test_the_conditional_block_rule_is_measured_by_its_column(self):
        """\\hsize, not \\linewidth: reledpar narrows \\hsize to the column but leaves
        \\linewidth at the page width, so a \\linewidth rule lands outside its column.
        \\OSMeasure is \\hsize less the paragraph's own indents."""
        tex = _tex({"markers": {"conditional": {"rule_width": "50%"}}})
        self.assertIn(r"\hbox to \OSMeasure", tex)
        self.assertNotIn(r"\linewidth", tex)

    def test_a_bracketed_conditional_block_reuses_the_inline_markers(self):
        tex = _tex({"markers": {"conditional": {"block": "brackets"}}})
        self.assertIn(r"\newcommand{\OSCondStartBlock}{\OSCondStartInline}", tex)

    def test_conditional_blocks_can_be_left_unmarked(self):
        tex = _tex({"markers": {"conditional": {"block": "none"}}})
        self.assertIn(r"\newcommand{\OSCondStartBlock}{}", tex)
        self.assertIn(r"\newcommand{\OSCondEndBlock}{}", tex)


class TestParallelColumns(unittest.TestCase):
    def test_column_geometry_needs_two_columns_on_one_page(self):
        settings = {"parallel": {"column_width": "40%", "column_position": "left"}}
        self.assertNotIn(r"\Lcolwidth", _tex(settings))
        self.assertNotIn(r"\columnsposition", _tex(settings))
        tex = _tex(settings, has_parallel=True)
        self.assertIn(r"\setlength{\Lcolwidth}{0.4\textwidth}", tex)
        self.assertIn(r"\setlength{\Rcolwidth}{0.4\textwidth}", tex)
        self.assertIn(r"\columnsposition{L}", tex)

    def test_other_layouts_have_no_columns_to_size(self):
        # A settings file cannot name the column keys under these layouts (see
        # TestParallelColumnSettings in test_typography.py); their defaults stay unset.
        for layout in ("pages", "interleaved"):
            with self.subTest(layout=layout):
                tex = _tex({"parallel": {"layout": layout}}, has_parallel=True)
                self.assertNotIn(r"\Lcolwidth", tex)
                self.assertNotIn(r"\columnsposition", tex)


class TestInterleaved(unittest.TestCase):
    """Each setting defines a macro the stylesheet's translation environment applies."""

    INTERLEAVED = {"layout": "interleaved"}

    def _interleaved(self, settings: dict, has_parallel: bool = True, **rest) -> str:
        return _tex(
            {"parallel": {**self.INTERLEAVED, "interleaved": settings}, **rest},
            has_parallel,
        )

    def test_nothing_written_takes_the_models_defaults(self):
        tex = _tex({"parallel": self.INTERLEAVED}, has_parallel=True)
        self.assertIn(r"\newcommand{\OSInterleavedSize}{\small}", tex)
        self.assertIn(r"\newcommand{\OSInterleavedIndent}{1em}", tex)
        self.assertIn(r"\newcommand{\OSInterleavedSpacing}{0.25em}", tex)

    def test_nothing_without_a_parallel_text(self):
        self.assertNotIn("OSInterleaved", self._interleaved({"spacing": "2pt"}, has_parallel=False))

    def test_nothing_in_another_layout(self):
        tex = _tex(
            {"parallel": {"layout": "pairs", "interleaved": {"spacing": "2pt"}}},
            has_parallel=True,
        )
        self.assertNotIn("OSInterleaved", tex)

    def test_each_setting_overrides_its_macro(self):
        tex = self._interleaved(
            {"translation_size": "x-small", "translation_indent": "2em", "spacing": "3pt"}
        )
        self.assertIn(r"\newcommand{\OSInterleavedSize}{\footnotesize}", tex)
        self.assertIn(r"\newcommand{\OSInterleavedIndent}{2em}", tex)
        self.assertIn(r"\newcommand{\OSInterleavedSpacing}{3pt}", tex)

    def test_an_absolute_size_sets_its_own_leading(self):
        tex = self._interleaved({"translation_size": "9pt"})
        self.assertIn(
            r"\newcommand{\OSInterleavedSize}{\fontsize{9pt}{10.8pt}\selectfont}", tex
        )

    def test_numbering_both_texts_empties_the_switch(self):
        self.assertIn(
            r"\newcommand{\OSInterleavedNumbering}{}",
            self._interleaved({"line_numbers": "both"}),
        )
        # Numbering only the original also disarms \skipnumbering, or a heading inside
        # the translation would pull back the original's count (#193).
        self.assertIn(
            r"\newcommand{\OSInterleavedNumbering}{\numberlinefalse\let\skipnumbering\relax}",
            self._interleaved({"line_numbers": "primary"}),
        )

    def test_no_reledpar_series_in_an_interleaved_document(self):
        """reledpar is not loaded, so its R-series macros do not exist."""
        line_numbers = {
            "unit": "section", "increment": 2, "first": 1, "margin": "left",
            "numerals": "hebrew",
        }
        tex = self._interleaved({}, line_numbers=line_numbers)
        for macro in (r"\lineationR", r"\linenumincrementR", r"\firstlinenumR",
                      r"\linenummarginR", r"\linenumrepR"):
            self.assertNotIn(macro, tex)
        self.assertIn(r"\linenumincrement{2}", tex)
        self.assertIn(r"\linenummargin{left}", tex)
        columns = _tex(
            {"parallel": {"layout": "pairs"}, "line_numbers": line_numbers},
            has_parallel=True,
        )
        for macro in (r"\lineationR", r"\linenumincrementR", r"\firstlinenumR",
                      r"\linenummarginR", r"\linenumrepR"):
            self.assertIn(macro, columns)


class TestHeadingTranslation(unittest.TestCase):
    r"""The translated title under a heading, where a division is titled twice."""

    def test_the_default_cannot_be_broken_from_its_heading(self):
        """\\nobreak after the \\par (outside a reledpar column), or a page could end
        between the two (#208)."""
        self.assertEqual(
            r"\newcommand{\OSheadTranslation}[1]{\par\OSheadNobreak\mbox{}\hfill"
            r"{\normalfont\normalsize\itshape #1}\hfill\mbox{}}",
            _macro(_tex({}), r"\OSheadTranslation"),
        )

    def test_the_nobreak_is_left_out_in_a_reledpar_column(self):
        """A penalty in a column cuts reledpar's line list short, and a title's last line
        is set outside its column. There the heading-line keep (\\OSKeepHeadBegin) holds
        the title to what follows instead."""
        tex = _tex({})
        self.assertEqual(
            r"\newcommand{\OSheadNobreak}{\ifl@dpairing\else\nobreak\fi}",
            _macro(tex, r"\OSheadNobreak"),
        )
        lines = tex.splitlines()
        at = next(i for i, l in enumerate(lines) if l.startswith(r"\newcommand{\OSheadNobreak}"))
        self.assertEqual(r"\makeatletter", lines[at - 1])
        self.assertEqual(r"\makeatother", lines[at + 1])

    def test_a_configured_style_reaches_the_macro(self):
        tex = _tex({"styles": {"heading_translation":
                               {"size": "small", "style": "normal", "align": "right"}}})
        self.assertIn(r"\newcommand{\OSheadTranslation}[1]{\par", tex)
        self.assertIn(r"\small", tex)
        # Right-aligned: glue leads, and none follows.
        line = [l for l in tex.splitlines() if "OSheadTranslation" in l][0]
        self.assertTrue(line.rstrip().endswith("#1}}"))


class TestLists(unittest.TestCase):
    """The label's style and the item's indent are configured separately: the indent
    is not one of the eight ``TextStyle`` attributes, so it is a section of its own."""

    def test_the_label_style_writes_the_label_macro(self):
        tex = _tex({"styles": {"list_label": {"variant": "small-caps", "weight": "bold"}}})
        self.assertIn(r"\newcommand{\OSListLabelStyle}[1]{", tex)
        self.assertIn(r"\scshape", tex)
        self.assertIn(r"\bfseries", tex)

    def test_the_label_takes_inline_alignment(self):
        r"""Like a heading, it is set inside a \pstart, where a block environment's
        \par escapes reledmac's per-line capture."""
        tex = _tex({"styles": {"list_label": {"align": "center"}}})
        self.assertIn(r"\newcommand{\OSListLabelStyle}[1]{\mbox{}\hfill", tex)
        self.assertNotIn(r"\begin{center}", _macro(tex, r"\OSListLabelStyle"))

    def test_the_item_indent_writes_the_indent_macro(self):
        self.assertIn(
            r"\newcommand{\OSListIndent}{1.5em}",
            _tex({"lists": {"item_indent": "1.5em"}}),
        )

    def test_a_zero_indent_is_still_emitted(self):
        """Setting it to 0pt is how a file asks for flush items, and is not the same
        as leaving it unset."""
        self.assertIn(
            r"\newcommand{\OSListIndent}{0pt}",
            _tex({"lists": {"item_indent": "0pt"}}),
        )

    def test_unconfigured_they_take_the_models_defaults(self):
        tex = _tex({"paragraphs": {"indent": "1em"}})
        self.assertIn(r"\newcommand{\OSListIndent}{2em}", tex)
        self.assertIn(r"\newcommand{\OSListLabelStyle}[1]{{\normalfont\scshape #1}}", tex)


if __name__ == "__main__":
    unittest.main()
