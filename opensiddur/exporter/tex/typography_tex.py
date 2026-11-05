""" Translating typography settings into LuaLaTeX.

``opensiddur/exporter/typography.py`` describes how a document should look in
renderer-agnostic terms. This module turns that description into TeX for the
reledmac pipeline. All the TeX is here; none of it is in the settings models,
and none of it is in a settings file.

Two products come out of a :class:`TypographyConfig`:

``documentclass_options`` — the bracketed options on ``\\documentclass``, which
have to be there and nowhere else.

``build_typography_preamble`` — the definitions of every macro and length a
setting controls, which ``reledmac.xslt`` emits after its own structural
preamble and before ``\\begin{document}``.

**Every setting is emitted, at its resolved value**, whether the settings file
wrote it or not. The stylesheet holds no copy of any default: what a book looks
like when its settings file says nothing is what ``typography.py`` says, and
nothing else. A macro the stylesheet relies on is therefore *defined* here, with
``\\newcommand``; only a macro a package already defines is renewed.
"""

from __future__ import annotations

from typing import Optional

from opensiddur.exporter.tex.escape import escape_tex
from opensiddur.exporter.typography import (
    Alignment,
    ChapterStart,
    ColumnPosition,
    ConditionalBlock,
    FontFace,
    FontStyle,
    FontVariant,
    FontWeight,
    HEBREW_FAMILY,
    Binding,
    InterleavedLineNumbers,
    LATIN_FAMILY,
    LineNumberMargin,
    NamedSize,
    NoteAnchor,
    Numerals,
    Orientation,
    PaperType,
    ParallelLayout,
    Sides,
    TextStyle,
    TypographyConfig,
    Visibility,
    resolve_font,
    right_bound_pages,
)


# ---------------------------------------------------------------------------
# Size and style tokens
# ---------------------------------------------------------------------------

# The named ladder, in the order it is documented. LaTeX's size commands are a
# ten-step scale whose steps are roughly 1.2x, which is where the ladder's shape
# comes from; each name is pinned to one step so that a document's sizes stay
# proportional when its base size changes.
_NAMED_SIZE_COMMANDS: dict[NamedSize, str] = {
    NamedSize.XXX_SMALL: r"\tiny",
    NamedSize.XX_SMALL: r"\scriptsize",
    NamedSize.X_SMALL: r"\footnotesize",
    NamedSize.SMALL: r"\small",
    NamedSize.NORMAL: r"\normalsize",
    NamedSize.LARGE: r"\large",
    NamedSize.X_LARGE: r"\Large",
    NamedSize.XX_LARGE: r"\LARGE",
    NamedSize.XXX_LARGE: r"\huge",
    NamedSize.XXXX_LARGE: r"\Huge",
}

_WEIGHT_COMMANDS = {FontWeight.NORMAL: r"\mdseries", FontWeight.BOLD: r"\bfseries"}
_SHAPE_COMMANDS = {FontStyle.NORMAL: r"\upshape", FontStyle.ITALIC: r"\itshape"}
_VARIANT_COMMANDS = {FontVariant.NORMAL: "", FontVariant.SMALL_CAPS: r"\scshape"}


def _size_command(size: Optional[str], line_spacing: float) -> str:
    """The TeX command that selects a size.

    A named size is one of the ten scale commands. An absolute length needs an
    explicit baseline too, since ``\\fontsize`` sets both; the conventional 1.2x
    leading is scaled by the document's line spacing so that a role given an
    exact size still respects ``paragraphs.line_spacing``.
    """
    if size is None:
        return ""
    if size in _NAMED_SIZE_COMMANDS:
        return _NAMED_SIZE_COMMANDS[NamedSize(size)]
    value, unit = _split_length(size)
    baseline = value * 1.2 * line_spacing
    return rf"\fontsize{{{_format_number(value)}{unit}}}{{{_format_number(baseline)}{unit}}}\selectfont"


def _split_length(length: str) -> tuple[float, str]:
    for position, character in enumerate(length):
        if character.isalpha():
            return float(length[:position]), length[position:]
    raise ValueError(f"length without a unit: {length!r}")  # pragma: no cover


def _format_number(value: float) -> str:
    """Trim a float to something TeX reads cleanly: 12.0 -> 12, 14.4 -> 14.4."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _font_command(family: Optional[str]) -> str:
    """The command that selects a declared family.

    ``latin`` is the document's main font, so selecting it is just returning to
    the normal font; ``hebrew`` is polyglossia's, which this module declares.
    Anything else is a family this module declared, named after its key.
    """
    if family is None:
        return ""
    if family == LATIN_FAMILY:
        return r"\normalfont"
    if family == HEBREW_FAMILY:
        return r"\hebrewfont"
    return "\\" + _family_macro_name(family)


def _family_macro_name(family: str) -> str:
    """A TeX control-sequence name for a user-declared family key.

    Control sequences are letters only, so the hyphens in the key are dropped
    and each word is capitalised: ``note-sans`` becomes ``OSfontNoteSans``.
    The key's spelling is validated (``TypographyConfig.validate_font_keys``) so
    that this is one to one.
    """
    words = "".join(character if character.isalnum() else " " for character in family)
    return "OSfont" + "".join(word.capitalize() for word in words.split())


def style_tokens(style: TextStyle, line_spacing: float = 1.0) -> str:
    """The font-switching commands for a style, in the order TeX wants them.

    The font comes first because it may reset the shape and series, then the
    size, then the attributes that survive a size change.
    """
    return "".join(
        (
            _font_command(style.font),
            _size_command(style.size, line_spacing),
            _WEIGHT_COMMANDS.get(style.weight, "") if style.weight else "",
            _SHAPE_COMMANDS.get(style.style, "") if style.style else "",
            _VARIANT_COMMANDS.get(style.variant, "") if style.variant else "",
        )
    )


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

# Two ways to align, because two contexts.
#
# Anything that can appear inside a reledmac \pstart is aligned with balanced
# \hfill inside the line. reledmac captures numbered text one \par-delimited
# line at a time, so a \par inside a group escapes that capture and, under
# reledpar's \Columns, lands outside its column; and a \parbox sizes itself from
# \linewidth, which is wider than a reledpar column. Fill glue works against the
# current measure, so it is correct in single-text and in either column.
_INLINE_ALIGNMENT: dict[Alignment, tuple[str, str]] = {
    Alignment.CENTER: (r"\mbox{}\hfill", r"\hfill\mbox{}"),
    Alignment.LEFT: ("", r"\hfill\mbox{}"),
    Alignment.RIGHT: (r"\mbox{}\hfill", ""),
    Alignment.JUSTIFY: ("", ""),
}

# Title-page material is set outside all numbering, so it can use real
# paragraph alignment and get proper line breaking.
_BLOCK_ALIGNMENT: dict[Alignment, str] = {
    Alignment.CENTER: r"\centering",
    Alignment.LEFT: r"\raggedright",
    Alignment.RIGHT: r"\raggedleft",
    Alignment.JUSTIFY: "",
}


def _inline_aligned(style: TextStyle, content: str) -> str:
    before, after = _INLINE_ALIGNMENT[style.align or Alignment.JUSTIFY]
    return before + content + after


def _vspace(length: Optional[str]) -> str:
    return rf"\vspace{{{length}}}" if length else ""


# A display set off from the text on either side, which takes the space a list
# environment puts around itself.
_DISPLAY_ENVIRONMENTS: dict[Alignment, str] = {
    Alignment.CENTER: "center",
    Alignment.LEFT: "flushleft",
    Alignment.RIGHT: "flushright",
}


def _display_block(style: TextStyle, body: str, line_spacing: float) -> str:
    """An aligned display between paragraphs, such as a section separator."""
    environment = _DISPLAY_ENVIRONMENTS.get(style.align or Alignment.JUSTIFY)
    if environment is None:
        return _block_paragraph(style, body, line_spacing)
    tokens = style_tokens(style, line_spacing)
    content = r"{\normalfont" + tokens + " " + body + "}" if tokens else body
    return (
        _vspace(style.space_before)
        + rf"\begin{{{environment}}}{content}\end{{{environment}}}"
        + _vspace(style.space_after)
    )


def _block_paragraph(style: TextStyle, body: str, line_spacing: float) -> str:
    """A centred (or otherwise aligned) paragraph with space around it."""
    alignment = _BLOCK_ALIGNMENT[style.align or Alignment.JUSTIFY]
    tokens = style_tokens(style, line_spacing)
    return (
        _vspace(style.space_before)
        + "{"
        + alignment
        + r"\normalfont"
        + tokens
        + " "
        + body
        + r"\par}"
        + _vspace(style.space_after)
    )


# ---------------------------------------------------------------------------
# Document class options
# ---------------------------------------------------------------------------


def documentclass_options(config: TypographyConfig) -> str:
    """The options for ``\\documentclass[...]{book}``.

    Only what the class itself has to be told: everything else is a package
    option or a declaration, and can be set later in the preamble where it is
    easier to reason about. ``twoside`` and ``openright`` are the class's own
    defaults and are left unsaid, so an unconfigured document keeps the exact
    option list it always had.
    """
    page = config.page
    options = [page.base_font_size.value]
    if page.paper is not PaperType.CUSTOM:
        options.append(page.paper.value)
    if page.sides is Sides.ONE:
        options.append("oneside")
    if page.chapter_start is ChapterStart.ANY:
        options.append("openany")
    return ",".join(options)


# ---------------------------------------------------------------------------
# Preamble sections
# ---------------------------------------------------------------------------


def _font_declaration(
    command: str, options: str, names: list[str],
    entries: Optional[list[FontFace]] = None, selector: str = "",
    *, at_compile_time: bool = False, optional: bool = False,
) -> list[str]:
    """Declare a font family, falling back through the chain if need be.

    When fontconfig can tell us which of the names is installed, the declaration
    names it outright. When it cannot — no fontconfig on this machine — the
    chain is emitted as nested ``\\IfFontExistsTF`` so TeX makes the same choice
    at compile time. The chain is known to contain an installed font either way:
    settings validation refuses one that does not.

    A default chain the settings file never named is not validated, so it may
    contain no installed font at all. ``at_compile_time`` leaves the whole choice
    to TeX, and ``optional`` guards the last name too, declaring nothing when
    none is present — the class's own font then stands.
    """
    def declaration(index: int) -> str:
        result = f"{command}{options}{{{names[index]}}}"
        if entries is not None and entries[index].normal_size is not None:
            size = str(entries[index].normal_size)
            result += rf"\OSRegisterFontSize{{{selector}}}{{{size}}}"
        return result

    if not at_compile_time:
        resolved = resolve_font(names)
        if resolved is not None:
            return [declaration(names.index(resolved))]

    guarded = len(names) if optional else len(names) - 1
    lines: list[str] = []
    for depth, name in enumerate(names[:guarded]):
        lines.append("  " * depth + rf"\IfFontExistsTF{{{name}}}{{")
        lines.append("  " * (depth + 1) + declaration(depth))
        lines.append("  " * depth + "}{")
    if not optional:
        lines.append("  " * guarded + declaration(len(names) - 1))
    lines.extend("  " * depth + "}" for depth in reversed(range(guarded)))
    return lines


# Hebrew faces in common use have no bold companion, so \bfseries would silently
# do nothing and a bold heading would be indistinguishable from body text.
# BoldFont={*} with AutoFakeBold synthesizes one. HarfBuzz shaping is what gets
# vowels and cantillation placed correctly.
_HEBREW_FONT_OPTIONS = "[Renderer=HarfBuzz,Script=Hebrew,BoldFont={*},AutoFakeBold=2]"


def _fonts_section(config: TypographyConfig) -> list[str]:
    sized = any(
        entry.normal_size is not None
        for spec in config.fonts.values() for entry in spec.entries
    )
    lines: list[str] = [
        r"\makeatletter",
        r"\newcommand{\OSRegisterFontSize}[2]{{#1\expandafter\xdef\csname OSnormal@\f@family\endcsname{#2}}}",
        r"\makeatother",
    ] if sized else []
    for family, spec in sorted(config.fonts.items()):
        # A default the settings file did not name was never checked against the
        # installed fonts (TypographyConfig.apply_font_defaults), so TeX chooses.
        default = family not in config.declared_fonts
        options = _HEBREW_FONT_OPTIONS if family == HEBREW_FAMILY else ""
        if any(entry.normal_size is not None for entry in spec.entries):
            # fontspec otherwise shares NFSS identities for identical faces. Two
            # configured families may choose that same face at different sizes.
            identity = "OS" + family.encode("utf-8").hex()
            options = (options[:-1] + "," if options else "[") + f"NFSSFamily={identity}]"
        if family == LATIN_FAMILY:
            # Without any of the default faces, the class's own font is the Latin one.
            lines.extend(
                _font_declaration(
                    r"\setmainfont", options, spec.names, spec.entries, r"\rmfamily",
                    at_compile_time=default, optional=default,
                )
            )
        elif family == HEBREW_FAMILY:
            # Polyglossia sets every Hebrew run in \hebrewfont, so this one is
            # declared whether or not any of its faces is present.
            lines.extend(
                _font_declaration(
                    r"\newfontfamily\hebrewfont", options, spec.names, spec.entries,
                    r"\hebrewfont", at_compile_time=default,
                )
            )
            # Polyglossia expects \hebrewfontsf if anything uses \sffamily inside
            # Hebrew; the alias saves declaring the same faces twice.
            lines.append(r"\let\hebrewfontsf\hebrewfont")
        else:
            lines.extend(
                _font_declaration(
                    "\\newfontfamily\\" + _family_macro_name(family), options, spec.names,
                    spec.entries, _font_command(family)
                )
            )
    if sized:
        lines.extend(_font_size_support().splitlines())
    return lines


def _font_size_support() -> str:
    """Keep logical role sizes separate from the selected family's physical size.

    NFSS family selection covers script switches, normalfont, and custom families.
    All state is group-local, so nested language switches restore their caller.
    Capture the class's actual normal size (11pt book uses 10.95pt), not its label.
    """
    return r"""\makeatletter
\begingroup\normalsize\xdef\OSdocumentnormal{\f@size}\endgroup
\edef\OSlogicalsize{\f@size}
\edef\OSlogicalbaseline{\f@baselineskip}
\newif\ifOSabsolute
\let\OSoriginalfontsize\fontsize
\let\OSoriginalselectfont\selectfont
\ExplSyntaxOn
\cs_new:Npn \OSscaled #1#2 { \fp_eval:n { (#1) * (#2) } }
\cs_new:Npn \OSratio #1 { \fp_eval:n { (#1) / \OSdocumentnormal } }
\cs_new:Npn \OSbaselinepoints { \dim_to_fp:n { \OSlogicalbaseline } }
\ExplSyntaxOff
\protected\def\fontsize#1#2{%
  \OSoriginalfontsize{#1}{#2}%
  \edef\OSlogicalsize{\f@size}%
  \edef\OSlogicalbaseline{\f@baselineskip}%
  \OSabsolutefalse}
\newcommand{\OSabsoluteSize}[2]{\fontsize{#1}{#2}\OSabsolutetrue}
\protected\def\selectfont{%
  \def\OSfactor{1}%
  \ifOSabsolute\else
    \ifcsname OSnormal@\f@family\endcsname
      \edef\OSfactor{\OSratio{\csname OSnormal@\f@family\endcsname}}%
    \fi
  \fi
  \OSoriginalfontsize{\OSscaled{\OSlogicalsize}{\OSfactor}}%
    {\OSscaled{\OSbaselinepoints}{\OSfactor}}%
  \OSoriginalselectfont}
\selectfont
\makeatother"""


def _geometry_section(config: TypographyConfig) -> list[str]:
    """Page size and margins, as ``geometry`` options.

    The stylesheet loads ``geometry`` with no options at all. A margin with no
    value is the document class's own, and is left unsaid.
    """
    page = config.page
    options: list[str] = []
    if page.paper is PaperType.CUSTOM:
        options.append(f"paperwidth={page.width}")
        options.append(f"paperheight={page.height}")
    if page.orientation is Orientation.LANDSCAPE:
        options.append("landscape")

    margins = page.margins
    # inner/outer are geometry's names for the binding and fore edges, and it
    # only understands them on a two-sided document. On a one-sided one they are
    # simply the left and right margins.
    two_sided = page.sides is Sides.TWO
    for name, option in (
        ("top", "top"),
        ("bottom", "bottom"),
        ("inner", "inner" if two_sided else "left"),
        ("outer", "outer" if two_sided else "right"),
        ("binding_offset", "bindingoffset"),
    ):
        value = getattr(margins, name)
        if value is not None:
            options.append(f"{option}={value}")

    lines = [rf"\geometry{{{','.join(options)}}}"] if options else []
    if right_bound_pages(page):
        lines.extend(_right_binding_lines())
    return lines


def _right_binding_lines() -> list[str]:
    """Move the binding to the right edge of an odd page.

    The book class and ``geometry`` know only a binding at the left: an odd page
    takes ``\\oddsidemargin``, with the inner margin (and any ``bindingoffset``)
    on its left. Under a right binding an odd page is laid out as the class lays
    out an even one. ``\\geometry`` computes the two in the preamble, so they are
    exchanged in ``begindocument/end``, after every package's own begin-document
    code (none of which recomputes them). Whatever the margins came from — the class, an explicit
    ``inner``/``outer`` or a binding offset — they arrive at the right edge
    unchanged.

    ``\\reversemarginpar`` keeps a marginal note in the outer margin, which the
    class otherwise puts at the right of an odd page.
    """
    return [
        r"\AddToHook{begindocument/end}{%",
        r"  \dimen0=\oddsidemargin",
        r"  \oddsidemargin=\evensidemargin",
        r"  \evensidemargin=\dimen0}",
        r"\reversemarginpar",
    ]


def _pdf_viewer_section(config: TypographyConfig) -> list[str]:
    """How a PDF viewer opens the book: its reading direction and page layout.

    A two-sided book opens as a cover page on its own and then spreads
    (``TwoPageRight``, "Two Up (Cover Page)"), read in the binding's direction
    (``/Direction``, "Binding: Right Edge"). The stylesheet loads ``hyperref``
    before the typography preamble, so ``\\hypersetup`` is defined here.
    """
    page = config.page
    direction = "R2L" if page.binding is Binding.RIGHT else "L2R"
    layout = "TwoPageRight" if page.sides is Sides.TWO else "SinglePage"
    return [rf"\hypersetup{{pdfdirection={direction},pdfpagelayout={layout}}}"]


def _paragraph_section(config: TypographyConfig) -> list[str]:
    paragraphs = config.paragraphs
    lines = [
        rf"\setlength{{\parindent}}{{{paragraphs.indent}}}",
        # The body is reledmac numbered text, whose paragraphs are \pstart...\pend
        # groups, and those do not take \parskip between them. reledmac.xslt hooks
        # \AtEveryPstart* to \OSPstartSkip for exactly that reason; \parskip is read
        # when a \pstart is set, so setting it here is all this has to do.
        rf"\setlength{{\parskip}}{{{paragraphs.spacing}}}",
        rf"\linespread{{{_format_number(paragraphs.line_spacing)}}}\selectfont",
    ]
    alignment = _BLOCK_ALIGNMENT[paragraphs.alignment]
    if alignment:
        # \AtBeginDocument because the raggedness has to survive the class's own
        # \normalfont setup, and because \raggedright in a preamble is a no-op.
        # Justified is what TeX does anyway, and says nothing.
        lines.append(rf"\AtBeginDocument{{{alignment}}}")
    return lines


# Each role, the macro that renders it, and how that macro is built. The
# stylesheet calls every one of these and defines none of them.
def _styles_section(config: TypographyConfig) -> list[str]:
    styles = config.styles
    markers = config.markers
    spacing = config.paragraphs.line_spacing
    lines: list[str] = []

    def tokens(style: TextStyle) -> str:
        return style_tokens(style, spacing)

    def define(role: str, definition_of) -> None:
        lines.append(definition_of(getattr(styles, role)))

    # Body text has no macro of its own; the stylesheet applies \OSBodyStyle at
    # the start of the document, where it is in force for everything.
    define("body", lambda s: rf"\newcommand{{\OSBodyStyle}}{{{tokens(s)}}}")

    # Headings: plain paragraph content inside a \pstart, hence inline alignment.
    for role, macro in (
        ("heading1", r"\OSheadA"),
        ("heading2", r"\OSheadB"),
        ("heading3", r"\OSheadC"),
        ("heading4", r"\OSheadD"),
    ):
        define(
            role,
            lambda s, macro=macro: rf"\newcommand{{{macro}}}[1]{{"
            + _inline_aligned(s, r"{\normalfont" + tokens(s) + " #1}")
            + "}",
        )

    # A translated title, under the heading it translates. \par first, because it is a
    # line of its own beneath the title rather than a continuation of it; the alignment
    # then applies to that line. \nobreak, because a page break between a title and its
    # translation would leave the translation heading a page it does not name (#198).
    # Set at whichever of the four levels the heading is, so it takes one style rather
    # than four.
    #
    # Not in a reledpar column, though. There reledpar cuts the paragraph into lines for
    # the column, and a penalty between a title's last line and its translation stops
    # that cut short: the title's last line escapes the column and is set full width
    # under the other one -- "TALMUDIC EXPO- / SITION OF THE SCRIP-" in the English
    # column and "TURES" under the Hebrew. The keep is not lost there: \OSKeepHeadBegin
    # tags both lines as heading, and the line-level keep holds them to what follows.
    # reledmac's own single stream copes with the penalty and keeps it.
    lines.extend([
        r"\makeatletter",
        r"\newcommand{\OSheadNobreak}{\ifl@dpairing\else\nobreak\fi}",
        r"\makeatother",
    ])
    define(
        "heading_translation",
        lambda s: r"\newcommand{\OSheadTranslation}[1]{\par\OSheadNobreak"
        + _inline_aligned(s, r"{\normalfont" + tokens(s) + " #1}")
        + "}",
    )

    # Title page: set outside all numbering, so real paragraphs are safe.
    for role, macro in (
        ("title_main", r"\OSTitleMain"),
        ("title_sub", r"\OSTitleSub"),
        ("title_alt", r"\OSTitleAlt"),
        ("byline", r"\OSByline"),
        ("edition", r"\OSDocEdition"),
        ("imprint", r"\OSDocImprint"),
        ("epigraph", r"\OSEpigraph"),
        ("imprimatur", r"\OSImprimatur"),
        ("title_page_block", r"\OSTitlePageBlock"),
        # The distribution notice and the back page are as far outside the numbering.
        ("distribution_notice", r"\OSDistributionNotice"),
        ("back_notice", r"\OSBackNotice"),
    ):
        define(
            role,
            lambda s, macro=macro: rf"\newcommand{{{macro}}}[1]{{"
            + _block_paragraph(s, "#1", spacing)
            + "}",
        )

    # Verse and chapter numbers force LTR: digits laid out in an RTL context
    # come out reversed, so 50 would read 05. A hidden number is a macro that
    # prints nothing, so the stylesheet need not know.
    if markers.verse_numbers is Visibility.HIDDEN:
        lines.append(r"\newcommand{\vno}[1]{}")
    else:
        define(
            "verse_number",
            lambda s: r"\newcommand{\vno}[1]{\textsuperscript{{\textdir TLT"
            r"\foreignlanguage{english}{" + tokens(s) + r"#1}}}\,}",
        )
    if markers.chapter_numbers is Visibility.HIDDEN:
        lines.append(r"\newcommand{\chno}[1]{}")
    else:
        define(
            "chapter_number",
            lambda s: r"\newcommand{\chno}[1]{{" + tokens(s)
            + r"{\textdir TLT\foreignlanguage{english}{#1}}}\,}",
        )
    define(
        "citation",
        lambda s: r"\newcommand{\OScitation}[1]{"
        + _inline_aligned(s, r"{\normalfont" + tokens(s) + " #1}")
        + "}",
    )
    define(
        "aliyah",
        lambda s: r"\newcommand{\OSaliyah}[1]{{" + tokens(s) + r"[#1]}\,}",
    )
    define(
        "parsha",
        lambda s: r"\newcommand{\OSParsha}[1]{{\normalfont" + tokens(s) + r" #1}\quad}",
    )
    # Regular braces, not \begingroup/\endgroup: the latter can close reledmac's
    # own groups early inside \edtext/\Bfootnote.
    define(
        "instruction",
        lambda s: r"\newcommand{\instructionnote}[1]{{" + tokens(s) + " #1}}",
    )
    define("note", lambda s: r"\newcommand{\notenote}[1]{{" + tokens(s) + " #1}}")
    # styles.line_number is emitted by _line_numbers_section: the style and
    # the numeral system write the same macro, so they have to be combined.
    define(
        "section_separator",
        lambda s: r"\newcommand{\OSSectionSeparatorStyle}[1]{"
        + _display_block(s, "#1", spacing)
        + "}",
    )
    # A list label, like a heading, is paragraph content inside a \pstart, so it
    # takes inline alignment for the same reason the heading roles do: a block
    # environment's \par escapes reledmac's per-line capture.
    define(
        "list_label",
        lambda s: r"\newcommand{\OSListLabelStyle}[1]{"
        + _inline_aligned(s, r"{\normalfont" + tokens(s) + " #1}")
        + "}",
    )
    return lines


def _note_mark_tex(style: TextStyle, anchor: NoteAnchor, spacing: float) -> list[str]:
    """The in-text anchor and the mark repeated where the note is printed.

    ``\\OSInterlinearNotemark`` keeps its name whichever anchor is chosen: it is
    what the stylesheet emits, and the setting decides only what it does.
    """
    # Note marks are set in a sans face so they read as editorial apparatus
    # rather than as part of the text, unless the settings name a font of their
    # own. Last, after the size, as a family switch.
    tokens = style_tokens(style, spacing) + (r"\sffamily" if style.font is None else "")
    if anchor is NoteAnchor.INTERLINEAR:
        # Raised, zero-width and centred on the anchor, so the mark sits in the
        # interlinear band and the text it annotates is not respaced — which is
        # what keeps two sides of a parallel text aligned.
        body = (
            r"\leavevmode\hbox to 0pt{\hss{\textdir TLT\raisebox{1.5ex}"
            r"{\foreignlanguage{english}{\kern0.05em\normalfont"
            + tokens
            + r" #1\kern0.05em}}}\hss}"
        )
    elif anchor is NoteAnchor.SUPERSCRIPT:
        body = (
            r"\textsuperscript{{\textdir TLT\foreignlanguage{english}{\normalfont"
            + tokens
            + " #1}}}"
        )
    else:
        body = r"{\textdir TLT\foreignlanguage{english}{\normalfont" + tokens + " #1}}"
    return [
        r"\newcommand{\OSInterlinearNotemark}[1]{%",
        "  " + body + "%",
        "}",
        # The mark at the head of the note itself, which is already in the
        # apparatus's own normal font.
        r"\newcommand{\OSFootnotemark}[1]{%",
        r"  {\textdir TLT\foreignlanguage{english}{" + tokens + r" #1}}\space",
        "}",
    ]


def _notes_section(config: TypographyConfig) -> list[str]:
    return _note_mark_tex(
        config.styles.note_mark, config.notes.anchor, config.paragraphs.line_spacing
    )


_MIRRORED_LINE_NUMBER_MARGIN = {
    LineNumberMargin.INNER: LineNumberMargin.OUTER,
    LineNumberMargin.OUTER: LineNumberMargin.INNER,
}


def _line_numbers_section(config: TypographyConfig, uses_reledpar: bool) -> list[str]:
    """Where line numbers go and how they are counted.

    Every declaration here must be in the preamble: ``\\lineation`` aborts with
    ``\\led@err@LineationInNumbered`` once numbering is open. Each has an ``R``
    twin for reledpar's right-hand series, which exists only when reledpar is
    loaded and which keeps settings of its own — so the twin is always said too.
    """
    line_numbers = config.line_numbers
    unit = line_numbers.unit.value
    margin = line_numbers.margin
    if right_bound_pages(config.page):
        # reledmac's inner and outer, like the class's, assume the binding is at the
        # left of an odd page. Its pages are already mirrored (_right_binding_lines),
        # so each names the other's edge; left and right are physical and stay.
        margin = _MIRRORED_LINE_NUMBER_MARGIN.get(margin, margin)
    margin = margin.value

    lines = [rf"\lineation{{{unit}}}"]
    if uses_reledpar:
        # reledpar keeps a separate \bypage@R that defaults to numbering by
        # section, so without the twin the right column runs on unbroken through
        # the whole document.
        lines.append(rf"\lineationR{{{unit}}}")
    lines.append(rf"\linenumincrement{{{line_numbers.increment}}}")
    if uses_reledpar:
        lines.append(rf"\linenumincrementR{{{line_numbers.increment}}}")
    lines.append(rf"\firstlinenum{{{line_numbers.first}}}")
    if uses_reledpar:
        lines.append(rf"\firstlinenumR{{{line_numbers.first}}}")
    lines.append(rf"\linenummargin{{{margin}}}")
    if uses_reledpar:
        lines.append(rf"\linenummarginR{{{margin}}}")
    # Between the number and the text. If too small, right-hand numbers collide
    # with the right column of a paired layout.
    lines.append(rf"\setlength{{\linenumsep}}{{{line_numbers.separation}}}")
    lines.extend(_line_number_format_tex(config, uses_reledpar))
    if not line_numbers.enabled:
        # reledmac's own switch, the one \skipnumbering sets for a single
        # paragraph. Setting it in the preamble applies it to all of them: the
        # numbering machinery still runs, so cross-references and the apparatus
        # are unaffected, but no number is printed.
        lines.append(r"\numberlinefalse")
    return lines


def _line_number_format_tex(config: TypographyConfig, uses_reledpar: bool) -> list[str]:
    """How a line number is set.

    The macro is ``\\linenumrep``, not ``\\linenumberstyle``: the latter is a
    declaration whose only job is to define the former, and reledmac calls it
    once, as it loads. Redefining it afterwards has no effect at all.

    Hebrew numerals are letters, so unlike digits they belong in the surrounding
    direction and need no left-to-right wrapper. Digits do: laid out in an RTL
    context they come out reversed, 50 reading as 05.

    Unstyled arabic numerals in the main series are reledmac's own
    ``\\linenumrep``, which is left alone: ``\\ledlinenum`` already sets them left
    to right. reledpar's right-hand series has no such switch, so its
    ``\\linenumrepR`` and ``\\sublinenumrepR`` are always given one.
    """
    tokens = style_tokens(config.styles.line_number, config.paragraphs.line_spacing)
    reledmac_own = config.line_numbers.numerals is Numerals.ARABIC and not tokens
    if config.line_numbers.numerals is Numerals.HEBREW:
        body = tokens + r"\hebrewnumeral{#1}"
    elif reledmac_own:
        body = r"\textdir TLT\@arabic{#1}"
    else:
        body = r"\textdir TLT\foreignlanguage{english}{" + tokens + r"\@arabic{#1}}"
    # \@arabic is internal; the \hbox keeps the direction and language switches
    # from leaking into reledmac's aux-file writes, which these tokens reach.
    lines: list[str] = []
    if not reledmac_own:
        lines.append(r"\renewcommand*{\linenumrep}[1]{\hbox{" + body + "}}")
    if uses_reledpar:
        lines.append(r"\renewcommand*{\linenumrepR}[1]{\hbox{" + body + "}}")
        lines.append(r"\renewcommand*{\sublinenumrepR}[1]{\hbox{\textdir TLT\@arabic{#1}}}")
    return [r"\makeatletter", *lines, r"\makeatother"] if lines else []


def _markers_section(config: TypographyConfig) -> list[str]:
    markers = config.markers
    separator = escape_tex(markers.section_separator)
    lines = [
        r"\newcommand{\OSSectionSeparator}{"
        + (rf"\OSSectionSeparatorStyle{{{separator}}}" if separator else "")
        + "}"
    ]

    # Only markers whose condition could not be decided survive compilation, so
    # a marker in the output means "say this only if ...", and the reader has to
    # see where that passage starts and stops.
    conditional = markers.conditional
    lines.append(
        r"\newcommand{\OSCondStartInline}{{\bfseries"
        + escape_tex(conditional.inline_open)
        + "}}"
    )
    lines.append(
        r"\newcommand{\OSCondEndInline}{{\bfseries"
        + escape_tex(conditional.inline_close)
        + "}}"
    )
    width = _percent_of(conditional.rule_width, r"\hsize")
    # A full-width box rather than \par-separated material: these rules sit
    # inside reledmac \pstart groups, where \par does not reliably break the
    # line. \hsize rather than \linewidth: reledpar narrows \hsize to the column
    # but leaves \linewidth at the page width, so a \linewidth box centres its
    # rule outside the column it belongs to. \OSMeasure is \hsize less the
    # paragraph's own indents.
    lines.append(
        r"\newcommand{\OSCondRule}{\leavevmode\hbox to \OSMeasure{\hss\rule{"
        + width
        + "}{"
        + conditional.rule_thickness
        + r"}\hss}}"
    )
    if conditional.block is ConditionalBlock.RULE:
        lines.append(r"\newcommand{\OSCondStartBlock}{\OSCondRule}")
        lines.append(r"\newcommand{\OSCondEndBlock}{\OSCondRule}")
    elif conditional.block is ConditionalBlock.BRACKETS:
        lines.append(r"\newcommand{\OSCondStartBlock}{\OSCondStartInline}")
        lines.append(r"\newcommand{\OSCondEndBlock}{\OSCondEndInline}")
    else:
        lines.append(r"\newcommand{\OSCondStartBlock}{}")
        lines.append(r"\newcommand{\OSCondEndBlock}{}")
    return lines


def _lists_section(config: TypographyConfig) -> list[str]:
    """The indent that sets a list item off from the prose around it.

    A length rather than a style key: ``TextStyle`` has no indent attribute, and
    the stylesheet applies this as ``\\leftskip``/``\\rightskip`` at the head of
    each of the item's paragraphs rather than as a box, so that a parallel
    compile measures it against the column and not the page.
    """
    return [rf"\newcommand{{\OSListIndent}}{{{config.lists.item_indent}}}"]


def _percent_of(percent: str, dimension: str) -> str:
    """``43%`` of ``\\textwidth`` is ``0.43\\textwidth``."""
    return _format_number(float(percent.rstrip("%")) / 100) + dimension


def _parallel_section(config: TypographyConfig, has_parallel: bool) -> list[str]:
    parallel = config.parallel
    if not has_parallel or parallel.layout is not ParallelLayout.PAIRS:
        # Column geometry exists only where there are two columns on one page.
        return []
    # Narrower than half, so the outer margins keep room for the line numbers.
    width = _percent_of(parallel.column_width, r"\textwidth")
    return [
        rf"\setlength{{\Lcolwidth}}{{{width}}}",
        rf"\setlength{{\Rcolwidth}}{{{width}}}",
        # reledpar's own default sets the block against the right edge of the
        # type area, which can leave no right margin for the numbers at all.
        rf"\columnsposition{{{_COLUMN_POSITIONS[parallel.column_position]}}}",
    ]


_COLUMN_POSITIONS = {
    ColumnPosition.LEFT: "L",
    ColumnPosition.CENTER: "C",
    ColumnPosition.RIGHT: "R",
}


def _interleaved_section(config: TypographyConfig, has_parallel: bool) -> list[str]:
    """How the translation is set apart when it follows the original in one column.

    The macros the stylesheet's ``OSInterleavedTranslation`` environment applies
    to the translation it wraps.
    """
    parallel = config.parallel
    if not has_parallel or parallel.layout is not ParallelLayout.INTERLEAVED:
        return []
    interleaved = parallel.interleaved
    size = _size_command(interleaved.translation_size, config.paragraphs.line_spacing)
    if interleaved.line_numbers is InterleavedLineNumbers.BOTH:
        # The translation's lines count like any other.
        numbering = ""
    else:
        # The translation is left unnumbered. \skipnumbering is disarmed as well,
        # or a heading or citation inside the translation would pull back the
        # count of the numbered text around it.
        numbering = r"\numberlinefalse\let\skipnumbering\relax"
    return [
        rf"\newcommand{{\OSInterleavedSize}}{{{size}}}",
        rf"\newcommand{{\OSInterleavedIndent}}{{{interleaved.translation_indent}}}",
        rf"\newcommand{{\OSInterleavedSpacing}}{{{interleaved.spacing}}}",
        rf"\newcommand{{\OSInterleavedNumbering}}{{{numbering}}}",
    ]


# ---------------------------------------------------------------------------
# The whole block
# ---------------------------------------------------------------------------


def build_typography_preamble(
    config: TypographyConfig, has_parallel: bool = False
) -> str:
    """Every setting, as TeX, in preamble order.

    ``has_parallel`` says whether the document has two aligned streams. Several
    reledpar declarations do not exist unless the package is loaded, and the
    package is loaded only for such a document, and only when it is set in
    columns or on facing pages, so emitting them unconditionally would break
    every other one. The interleaved layout sets both texts in one reledmac
    stream and does not load it.
    """
    uses_reledpar = (
        has_parallel and config.parallel.layout is not ParallelLayout.INTERLEAVED
    )
    sections = [
        ("Fonts", _fonts_section(config)),
        ("Page geometry", _geometry_section(config)),
        ("PDF viewer", _pdf_viewer_section(config)),
        ("Paragraphs", _paragraph_section(config)),
        ("Text styles", _styles_section(config)),
        ("Notes", _notes_section(config)),
        ("Line numbers", _line_numbers_section(config, uses_reledpar)),
        ("Markers", _markers_section(config)),
        ("Lists", _lists_section(config)),
        ("Parallel columns", _parallel_section(config, has_parallel)),
        ("Interleaved parallel", _interleaved_section(config, has_parallel)),
    ]
    sized = any(
        entry.normal_size is not None
        for spec in config.fonts.values() for entry in spec.entries
    )
    lines: list[str] = []
    for title, section in sections:
        if section:
            lines.append(f"% --- {title} (typography settings) ---")
            # All explicit style sizes originate in _size_command; mark them
            # absolute without changing legacy preambles or the support macros.
            if sized and title != "Fonts":
                section = [line.replace(r"\fontsize{", r"\OSabsoluteSize{") for line in section]
            lines.extend(section)
    return "\n".join(lines) + "\n" if lines else ""
