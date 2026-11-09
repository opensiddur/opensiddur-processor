"""typography.py is the only source of a book's default appearance.

Three things used to state the defaults: the settings models, the reference in
``doc/typography.md``, and copies hard-coded into ``reledmac.xslt``. The copies
drifted (#103 raised the paragraph spacing; #104 put the stylesheet's copy back
without anyone noticing). Now the stylesheet keeps no copy, and these tests hold
the rest together:

- every default the reference documents is the model's default;
- every default reaches the stylesheet, rendered into its parameters — a new
  setting with no entry in ``_EXPECTED`` fails, so none can slip past;
- the stylesheet defines nothing a setting controls.
"""

from __future__ import annotations

import enum
import re
import unittest
from typing import Callable, NamedTuple, Optional

from lxml import etree
from pydantic import BaseModel

from opensiddur.exporter.tex.latex import XSLT_FILE, typography_parameters
from opensiddur.exporter.typography import TextStyle, TypographyConfig
from opensiddur.tests.exporter.test_typography_doc import DOC, _model_of


# A minimal document of each shape the preamble depends on: one stream, two
# aligned streams set by reledpar, two streams interleaved in one.
_SINGLE = "<TEI xmlns='http://www.tei-c.org/ns/1.0' xml:lang='en'/>"
_PARALLEL = (
    "<TEI xmlns='http://www.tei-c.org/ns/1.0' xml:lang='en'>"
    "<p:parallel xmlns:p='http://jewishliturgy.org/ns/processing'/></TEI>"
)
_INTERLEAVED_SETTINGS = {"parallel": {"layout": "interleaved"}}


def _parameters(document: str, settings: Optional[dict] = None) -> dict:
    config = TypographyConfig.model_validate(settings or {})
    return typography_parameters(config, etree.fromstring(document))


# Documented in prose rather than in the settings tables (test_typography_doc's
# _DOCUMENTED_AS_PROSE); styles have a table of their own, checked role by role.
_PROSE = {"fonts", "page_header", "page_footer", "styles"}


def _leaves(model: BaseModel, prefix: str = "") -> list[tuple[str, object]]:
    """Every scalar setting a settings file may write, with its resolved default.

    Keyed by the name a settings file uses (the alias, where there is one).
    """
    leaves: list[tuple[str, object]] = []
    for name, field in type(model).model_fields.items():
        path = f"{prefix}{field.alias or name}"
        if path in _PROSE:
            continue
        value = getattr(model, name)
        if _model_of(field.annotation) is not None and isinstance(value, BaseModel):
            leaves.extend(_leaves(value, path + "."))
        else:
            leaves.append((path, value))
    return leaves


# ---------------------------------------------------------------------------
# The reference agrees with the model
# ---------------------------------------------------------------------------

def _documented_defaults() -> dict[str, str]:
    """The Default column of every `| `a.b.c` | type | default | effect |` row."""
    rows: dict[str, str] = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        # The type column escapes its own pipes (`a` \| `b`), so split on bare ones.
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
        if len(cells) == 4 and cells[0].startswith("`") and "." in cells[0]:
            rows[cells[0].strip("`")] = cells[2]
    return rows


def _as_documented(value: object) -> set[str]:
    """How the reference writes a default, without the backticks."""
    if value is None:
        return {"—", "class default"}
    if isinstance(value, bool):
        return {str(value).lower()}
    if isinstance(value, enum.Enum):
        return {str(value.value)}
    return {str(value)}


_STYLE_ROWS = re.compile(r"^\| `styles\.([a-z_0-9]+)` \| ([^|]*) \|", re.M)


def _style_as_documented(style: TextStyle) -> str:
    """A role's default as the style-roles table writes it."""
    parts = []
    if style.size is not None:
        parts.append(f"`{getattr(style.size, 'value', style.size)}`")
    if style.weight is not None and style.weight.value != "normal":
        parts.append(style.weight.value)
    if style.style is not None and style.style.value != "normal":
        parts.append(style.style.value)
    if style.variant is not None and style.variant.value != "normal":
        parts.append(style.variant.value)
    if style.align is not None:
        parts.append({"center": "centered"}.get(style.align.value, style.align.value))
    if style.space_before is not None:
        parts.append(f"`{style.space_before}` before")
    if style.space_after is not None:
        parts.append(f"`{style.space_after}` after")
    return ", ".join(parts) or "inherits"


class TestTheReferenceStatesTheModelsDefaults(unittest.TestCase):
    def test_every_documented_default_is_the_models(self):
        documented = _documented_defaults()
        for path, value in _leaves(TypographyConfig()):
            with self.subTest(path=path):
                self.assertIn(path, documented, "no table row for this setting")
                self.assertIn(documented[path].strip("`"), _as_documented(value))

    def test_every_style_roles_documented_default_is_the_models(self):
        documented = dict(_STYLE_ROWS.findall(DOC.read_text(encoding="utf-8")))
        styles = TypographyConfig().styles
        for role in type(styles).model_fields:
            with self.subTest(role=role):
                self.assertEqual(
                    _style_as_documented(getattr(styles, role)), documented[role].strip()
                )


# ---------------------------------------------------------------------------
# Every default reaches the stylesheet
# ---------------------------------------------------------------------------


class Expect(NamedTuple):
    """Where a default shows, and what it looks like there.

    ``where`` names a stylesheet parameter. ``text`` turns the default into what
    must appear in it — or, with ``present=False``, what must not: a default that
    is the document class's or the package's own says nothing.
    """

    where: str
    text: Callable[[object], str]
    present: bool = True
    document: str = _SINGLE
    settings: Optional[dict] = None


def _v(value: object) -> str:
    return str(getattr(value, "value", value))


def _bound(margin: object) -> str:
    """A line-number margin as reledmac names it on a right-bound page."""
    return {"inner": "outer", "outer": "inner"}.get(_v(margin), _v(margin))


def _fraction(percent: object) -> str:
    return f"{float(str(percent).rstrip('%')) / 100:g}"


def _preamble(text, **kwargs) -> Expect:
    return Expect("typography-preamble", text, **kwargs)


def _parallel(text, **kwargs) -> Expect:
    return _preamble(text, document=_PARALLEL, **kwargs)


def _interleaved(text) -> Expect:
    return _preamble(text, document=_PARALLEL, settings=_INTERLEAVED_SETTINGS)


def _parameter(name: str) -> Expect:
    return Expect(name, lambda v: _v(v) if not isinstance(v, bool) else str(v))


_EXPECTED: dict[str, list[Expect]] = {
    "page.paper": [Expect("documentclass-options", _v)],
    "page.width": [_preamble(lambda v: "paperwidth", present=False)],
    "page.height": [_preamble(lambda v: "paperheight", present=False)],
    "page.orientation": [_preamble(lambda v: "landscape", present=False)],
    "page.sides": [Expect("documentclass-options", lambda v: "oneside", present=False)],
    "page.chapter_start": [
        Expect("documentclass-options", lambda v: "openany", present=False)
    ],
    "page.base_font_size": [Expect("documentclass-options", _v)],
    "page.binding": [_preamble(lambda v: "pdfdirection=R2L")],
    **{
        f"page.margins.{side}": [_preamble(lambda v: r"\geometry", present=False)]
        for side in ("top", "bottom", "inner", "outer", "binding_offset")
    },
    "paragraphs.indent": [_preamble(lambda v: rf"\setlength{{\parindent}}{{{v}}}")],
    "paragraphs.spacing": [_preamble(lambda v: rf"\setlength{{\parskip}}{{{v}}}")],
    "paragraphs.line_spacing": [_preamble(lambda v: rf"\linespread{{{v:g}}}")],
    # Justified is what TeX does anyway.
    "paragraphs.alignment": [_preamble(lambda v: r"\AtBeginDocument{", present=False)],
    "line_numbers.enabled": [_preamble(lambda v: r"\renewcommand*{\linenumberlist}{-1}", present=False)],
    "line_numbers.unit": [
        _preamble(lambda v: rf"\lineation{{{_v(v)}}}"),
        _parallel(lambda v: rf"\lineationR{{{_v(v)}}}"),
    ],
    "line_numbers.increment": [
        _preamble(lambda v: rf"\linenumincrement{{{v}}}"),
        _parallel(lambda v: rf"\linenumincrementR{{{v}}}"),
    ],
    "line_numbers.first": [
        _preamble(lambda v: rf"\firstlinenum{{{v}}}"),
        _parallel(lambda v: rf"\firstlinenumR{{{v}}}"),
    ],
    # reledmac assumes a left binding, so on the default right-bound page it calls the
    # outer margin inner.
    "line_numbers.margin": [
        _preamble(lambda v: rf"\linenummargin{{{_bound(v)}}}"),
        _parallel(lambda v: rf"\linenummarginR{{{_bound(v)}}}"),
        _interleaved(lambda v: rf"\linenummargin{{{_bound(v)}}}"),
    ],
    "line_numbers.separation": [_preamble(lambda v: rf"\setlength{{\linenumsep}}{{{v}}}")],
    # Arabic is reledmac's own numeral in the main series; reledpar's right-hand
    # series is told to set its digits left to right.
    "line_numbers.numerals": [
        _preamble(lambda v: r"\linenumrep}", present=False),
        _parallel(lambda v: r"\renewcommand*{\linenumrepR}[1]{\hbox{\textdir TLT\@arabic{#1}}}"),
    ],
    "notes.placement": [_parameter("notes-placement")],
    "notes.anchor": [_preamble(lambda v: r"\newcommand{\OSInterlinearNotemark}[1]{%"
                               "\n" r"  \leavevmode\hbox to 0pt{\hss{\textdir TLT\raisebox{1.5ex}")],
    "notes.mark": [_parameter("notes-mark")],
    "markers.section_separator": [
        _preamble(lambda v: rf"\newcommand{{\OSSectionSeparator}}{{\OSSectionSeparatorStyle{{{v}}}}}")
    ],
    "markers.verse_numbers": [_preamble(lambda v: r"\newcommand{\vno}[1]{\textsuperscript")],
    "markers.chapter_numbers": [_preamble(lambda v: r"\newcommand{\chno}[1]{{\large")],
    "markers.conditional.inline_open": [
        _preamble(lambda v: rf"\newcommand{{\OSCondStartInline}}{{{{\bfseries{v}}}}}")
    ],
    "markers.conditional.inline_close": [
        _preamble(lambda v: rf"\newcommand{{\OSCondEndInline}}{{{{\bfseries{v}}}}}")
    ],
    "markers.conditional.block": [
        _preamble(lambda v: r"\newcommand{\OSCondStartBlock}{\OSCondRule}"),
        _preamble(lambda v: r"\newcommand{\OSCondEndBlock}{\OSCondRule}"),
    ],
    "markers.conditional.rule_width": [
        _preamble(lambda v: rf"\rule{{{_fraction(v)}\hsize}}")
    ],
    "markers.conditional.rule_thickness": [_preamble(lambda v: rf"\hsize}}{{{v}}}\hss")],
    "lists.item_indent": [_preamble(lambda v: rf"\newcommand{{\OSListIndent}}{{{v}}}")],
    "parallel.layout": [_parameter("layout")],
    "parallel.column_width": [
        _parallel(lambda v: rf"\setlength{{\Lcolwidth}}{{{_fraction(v)}\textwidth}}"),
        _parallel(lambda v: rf"\setlength{{\Rcolwidth}}{{{_fraction(v)}\textwidth}}"),
    ],
    "parallel.column_position": [
        _parallel(lambda v: rf"\columnsposition{{{_v(v)[0].upper()}}}")
    ],
    "parallel.interleaved.translation_size": [
        _interleaved(lambda v: r"\newcommand{\OSInterleavedSize}{\small}")
    ],
    "parallel.interleaved.translation_indent": [
        _interleaved(lambda v: rf"\newcommand{{\OSInterleavedIndent}}{{{v}}}")
    ],
    "parallel.interleaved.spacing": [
        _interleaved(lambda v: rf"\newcommand{{\OSInterleavedSpacing}}{{{v}}}")
    ],
    "parallel.interleaved.line_numbers": [
        _interleaved(
            lambda v: r"\newcommand{\OSInterleavedNumbering}{\numberlinefalse\let\skipnumbering\relax}"
        )
    ],
    "table_of_contents.enabled": [_parameter("table-of-contents")],
    "table_of_contents.depth": [_parameter("table-of-contents-depth")],
    "bookmarks.from": [_parameter("bookmarks-from")],
    "headings.from": [_parameter("headings-from")],
    "instructions.from": [_parameter("instructions-from")],
}


# Each role, the macro that renders it, and how its alignment is written there:
# fill glue inside a numbered paragraph, a real paragraph on the title page.
_INLINE, _BLOCK = r"\mbox{}\hfill", r"\centering"
_ROLES: dict[str, tuple[str, Optional[str]]] = {
    "body": (r"\OSBodyStyle", None),
    "heading1": (r"\OSheadA", _INLINE),
    "heading2": (r"\OSheadB", _INLINE),
    "heading3": (r"\OSheadC", _INLINE),
    "heading4": (r"\OSheadD", _INLINE),
    "heading_translation": (r"\OSheadTranslation", _INLINE),
    "title_main": (r"\OSTitleMain", _BLOCK),
    "title_sub": (r"\OSTitleSub", _BLOCK),
    "title_alt": (r"\OSTitleAlt", _BLOCK),
    "byline": (r"\OSByline", _BLOCK),
    "edition": (r"\OSDocEdition", _BLOCK),
    "imprint": (r"\OSDocImprint", _BLOCK),
    "epigraph": (r"\OSEpigraph", _BLOCK),
    "imprimatur": (r"\OSImprimatur", _BLOCK),
    "title_page_block": (r"\OSTitlePageBlock", _BLOCK),
    "distribution_notice": (r"\OSDistributionNotice", _BLOCK),
    "back_notice": (r"\OSBackNotice", _BLOCK),
    "citation": (r"\OScitation", _INLINE),
    "parsha": (r"\OSParsha", None),
    "aliyah": (r"\OSaliyah", None),
    "verse_number": (r"\vno", None),
    "chapter_number": (r"\chno", None),
    "instruction": (r"\instructionnote", None),
    "note": (r"\notenote", None),
    "note_mark": (r"\OSInterlinearNotemark", None),
    "line_number": (r"\linenumrep", None),
    "section_separator": (r"\OSSectionSeparatorStyle", r"\begin{center}"),
    "list_label": (r"\OSListLabelStyle", None),
    "highlight_italic": (r"\OSHighlightItalic", None),
    "highlight_bold": (r"\OSHighlightBold", None),
    "highlight_small_caps": (r"\OSHighlightSmallCaps", None),
    "highlight_superscript": (r"\OSHighlightSuperscript", None),
    "highlight_large": (r"\OSHighlightLarge", None),
    "highlight_small": (r"\OSHighlightSmall", None),
    "foreign": (r"\OSForeign", None),
    "reference": (r"\OSReference", None),
    "poetry_line": (r"\OSPoetryLine", None),
    "list_item": (r"\OSListItem", None),
    "abbreviation": (r"\OSAbbreviation", None),
    "expansion": (r"\OSExpansion", None),
    "printed_error": (r"\OSPrintedError", None),
    "correction": (r"\OSCorrection", None),
    "qere": (r"\OSQere", None),
    "ketiv": (r"\OSKetiv", None),
    "alternative_reading": (r"\OSAlternativeReading", None),
}

_SIZES = {
    "xxx-small": r"\tiny", "xx-small": r"\scriptsize", "x-small": r"\footnotesize",
    "small": r"\small", "normal": r"\normalsize", "large": r"\large",
    "x-large": r"\Large", "xx-large": r"\LARGE", "xxx-large": r"\huge",
    "xxxx-large": r"\Huge",
}


def _definition(preamble: str, macro: str) -> Optional[str]:
    """The line that defines ``macro``, and for a % continued one the lines after it."""
    lines = preamble.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"\\(re)?newcommand\*?\{" + re.escape(macro) + r"\}", line):
            if line.endswith("%"):
                return "\n".join(lines[index:index + 3])
            return line
    return None


class TestEveryDefaultReachesTheStylesheet(unittest.TestCase):
    def test_every_setting_has_an_expectation(self):
        """A new setting must say where its default shows, or that it shows nowhere."""
        missing = [path for path, _ in _leaves(TypographyConfig()) if path not in _EXPECTED]
        self.assertEqual([], missing)

    def test_every_default_appears_in_the_parameters(self):
        defaults = dict(_leaves(TypographyConfig()))
        for path, expectations in _EXPECTED.items():
            for expect in expectations:
                with self.subTest(path=path, where=expect.where, document=expect.document):
                    parameter = str(
                        _parameters(expect.document, expect.settings)[expect.where]
                    )
                    text = expect.text(defaults[path])
                    if expect.present:
                        self.assertIn(text, parameter)
                    else:
                        self.assertNotIn(text, parameter)

    def test_every_style_role_has_a_macro_listed_here(self):
        self.assertEqual(set(_ROLES), set(type(TypographyConfig().styles).model_fields))

    def test_every_style_role_is_defined_with_its_default(self):
        """Its size, weight, shape and variant, and its alignment and space."""
        styles = TypographyConfig().styles
        preamble = _parameters(_PARALLEL)["typography-preamble"]
        for role, (macro, alignment) in _ROLES.items():
            style: TextStyle = getattr(styles, role)
            with self.subTest(role=role):
                definition = _definition(preamble, macro)
                if role == "line_number":
                    # Unstyled, the left series is reledmac's own; see numerals above.
                    self.assertIsNone(definition)
                    continue
                self.assertIsNotNone(definition, f"{macro} is not defined")
                tokens = "".join((
                    _SIZES[style.size] if style.size else "",
                    r"\bfseries" if style.weight and style.weight.value == "bold" else "",
                    r"\itshape" if style.style and style.style.value == "italic" else "",
                    r"\scshape" if style.variant and style.variant.value == "small-caps" else "",
                ))
                self.assertIn(tokens, definition)
                if alignment and style.align is not None:
                    self.assertIn(alignment, definition)
                for space in (style.space_before, style.space_after):
                    if space is not None:
                        self.assertIn(rf"\vspace{{{space}}}", definition)

    def test_the_default_fonts_are_declared(self):
        preamble = _parameters(_SINGLE)["typography-preamble"]
        for family, spec in TypographyConfig().fonts.items():
            for name in spec.names:
                with self.subTest(family=family, name=name):
                    # Chosen when the document is typeset, since the defaults are
                    # never checked against the installed fonts; the last of a
                    # chain that must declare something is declared unguarded.
                    self.assertIn(f"{{{name}}}", preamble)


# ---------------------------------------------------------------------------
# The stylesheet keeps no copy
# ---------------------------------------------------------------------------


class TestTheStylesheetKeepsNoCopy(unittest.TestCase):
    def setUp(self):
        # What it emits, not what its comments say: they show callers how to
        # redefine a macro, which is not a definition.
        self.stylesheet = re.sub(r"<!--.*?-->", "", XSLT_FILE.read_text(encoding="utf-8"), flags=re.S)
        self.preambles = [
            _parameters(_SINGLE)["typography-preamble"],
            _parameters(_PARALLEL)["typography-preamble"],
            _parameters(_PARALLEL, _INTERLEAVED_SETTINGS)["typography-preamble"],
        ]

    def test_it_defines_no_macro_the_typography_preamble_defines(self):
        defined = {
            name
            for preamble in self.preambles
            for name in re.findall(r"\\(?:re)?newcommand\*?\{(\\[A-Za-z]+)\}", preamble)
        }
        for macro in sorted(defined):
            with self.subTest(macro=macro):
                # However it might be defined: \newcommand, \renewcommand,
                # \providecommand (starred or not), \def or \let.
                found = re.search(
                    r"\\(?:(?:re|provide|new)command\*?\s*\{|def\s*|let\s*)"
                    + re.escape(macro) + r"(?![A-Za-z])",
                    self.stylesheet,
                )
                self.assertIsNone(found and found.group(0))

    def test_it_sets_no_length_or_declaration_a_setting_controls(self):
        for declaration in (
            r"\setlength{\parindent}", r"\setlength{\linenumsep}",
            r"\setlength{\Lcolwidth}", r"\setlength{\Rcolwidth}", r"\columnsposition{",
            r"\lineation{", r"\lineationR{", r"\linenummargin{", r"\linenummarginR{",
            r"\linenumincrement", r"\firstlinenum", r"\linespread",
            r"\setmainfont", r"\newfontfamily\hebrewfont", r"\IfFontExistsTF",
        ):
            with self.subTest(declaration=declaration):
                self.assertFalse(declaration in self.stylesheet, declaration)
        # Inside a parallel column \parskip is zeroed, which is structure, not a setting.
        found = re.search(r"\\setlength\{\\parskip\}\{(?!0pt\})", self.stylesheet)
        self.assertIsNone(found and found.group(0))

    def test_it_requires_every_typography_parameter(self):
        """No parameter carrying typography has a default of its own to fall back on."""
        parameters = _parameters(_SINGLE)
        for name in parameters:
            with self.subTest(parameter=name):
                declaration = re.search(
                    r'<xsl:param name="' + re.escape(name) + r'"[^>]*>', self.stylesheet
                )
                self.assertIsNotNone(declaration)
                self.assertIn('required="yes"', declaration.group(0))


if __name__ == "__main__":
    unittest.main()
