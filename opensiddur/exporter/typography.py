""" Typography settings: the user-facing description of how a document should look.

This module is deliberately renderer-agnostic. Nothing here knows about TeX —
sizes are a named ladder or a length with a unit, not ``\\LARGE``; a page has
``inner`` and ``outer`` margins, not ``\\geometry`` options. The translation into
one renderer's commands lives beside that renderer; for the PDF stage that is
``opensiddur/exporter/tex/typography_tex.py``.

Two rules shape the models:

*Every setting has a default, and the defaults reproduce the output the exporter
produced before any of this was configurable.* A settings file that omits the
``typography`` section, or any part of it, gets exactly what it got before.

*Invalid settings fail at load time, not in the renderer.* Every model forbids
unknown keys, every vocabulary is a closed enum, and lengths are pattern-checked,
so a typo names itself and its YAML path instead of surfacing as a LaTeX error
several minutes into a build — or, worse, as a silently wrong page.

The one part of the settings tree that lives elsewhere is
``page_header``/``page_footer``: their model and their TeX generator are a single
piece of logic, and both are in ``tex/running_heads.py``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

from opensiddur.exporter.tex.running_heads import RunningHeadConfig, default_page_header


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------

# Units a length may carry. `em`/`ex` are relative to the font in force where the
# length is used, which is what makes a setting like `paragraphs.spacing: 0.5em`
# survive a change of base font size. The rest are absolute.
_LENGTH_PATTERN = r"^-?(?:\d+(?:\.\d+)?|\.\d+)(?:pt|bp|mm|cm|in|pc|em|ex)$"

Length = Annotated[
    str,
    StringConstraints(pattern=_LENGTH_PATTERN),
    Field(
        description=(
            "A length with a unit: pt, bp, mm, cm, in, pc, em or ex. "
            "em and ex are relative to the font in force."
        ),
    ),
]

# A font size given as a length must be absolute: a size in `em` would be
# relative to the size it is itself defining. Use a NamedSize for a size
# relative to the base.
_ABSOLUTE_LENGTH_PATTERN = r"^(?:\d+(?:\.\d+)?|\.\d+)(?:pt|bp|mm|cm|in|pc)$"

AbsoluteLength = Annotated[
    str,
    StringConstraints(pattern=_ABSOLUTE_LENGTH_PATTERN),
    Field(
        description=(
            "A positive length in an absolute unit: pt, bp, mm, cm, in or pc. "
            "Relative units are not allowed where the length defines a font size."
        ),
    ),
]

# A length that cannot sensibly be negative: a margin, a page size, a rule's thickness.
_NON_NEGATIVE_LENGTH_PATTERN = r"^(?:\d+(?:\.\d+)?|\.\d+)(?:pt|bp|mm|cm|in|pc|em|ex)$"

NonNegativeLength = Annotated[
    str,
    StringConstraints(pattern=_NON_NEGATIVE_LENGTH_PATTERN),
    Field(
        description=(
            "A length of zero or more, with a unit: pt, bp, mm, cm, in, pc, em or ex."
        ),
    ),
]

_PERCENT_PATTERN = r"^(?:\d+(?:\.\d+)?|\.\d+)%$"

Percent = Annotated[
    str,
    StringConstraints(pattern=_PERCENT_PATTERN),
    Field(description="A percentage of the enclosing measure, e.g. `43%`."),
]


class NamedSize(StrEnum):
    """ A font size relative to the document's base size.

    A named size follows the selected font’s ``normal_size``, falling back to
    the document class sizes from ``page.base_font_size``. Use an absolute
    :data:`Length` instead when a role needs an exact size regardless.

    The ladder is symmetric around ``normal`` and each step is roughly 1.2x.
    """

    XXX_SMALL = "xxx-small"
    XX_SMALL = "xx-small"
    X_SMALL = "x-small"
    SMALL = "small"
    NORMAL = "normal"
    LARGE = "large"
    X_LARGE = "x-large"
    XX_LARGE = "xx-large"
    XXX_LARGE = "xxx-large"
    XXXX_LARGE = "xxxx-large"


FontSize = Union[NamedSize, AbsoluteLength]


class FontWeight(StrEnum):
    NORMAL = "normal"
    BOLD = "bold"


class FontStyle(StrEnum):
    NORMAL = "normal"
    ITALIC = "italic"


class FontVariant(StrEnum):
    NORMAL = "normal"
    SMALL_CAPS = "small-caps"


class Alignment(StrEnum):
    """ Horizontal alignment.

    ``left`` and ``right`` are physical positions on the page, so they mean the
    same thing in a Hebrew and an English stream; ``start``/``end`` semantics are
    deliberately not offered, because a bilingual document would need both at
    once and could not say so.
    """

    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"
    JUSTIFY = "justify"


class Sides(StrEnum):
    """ Whether the document is printed on one or both sides of the leaf. """

    ONE = "one"
    TWO = "two"


class Binding(StrEnum):
    """ Which edge of the book the leaves are bound at.

    A Hebrew-primary book is bound at the right, so it opens from what a Latin-script
    reader takes for the back, its spreads read right to left, and its recto — an
    odd page, as in any book — is the left-hand page of a spread.
    """

    LEFT = "left"
    RIGHT = "right"


class ChapterStart(StrEnum):
    """ Where a new book or chapter is allowed to begin. """

    RECTO = "recto"  # always on a recto (odd) page, inserting a blank if needed
    ANY = "any"


class Orientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class Numerals(StrEnum):
    ARABIC = "arabic"
    HEBREW = "hebrew"


class BaseFontSize(StrEnum):
    """ The document's base font size.

    Only these three are available: they are the sizes the underlying document
    class ships font-size tables for, and asking for anything else silently gets
    one of them. Set individual roles in ``styles`` for other sizes.
    """

    PT10 = "10pt"
    PT11 = "11pt"
    PT12 = "12pt"


class PaperType(StrEnum):
    """ Paper size.

    ``custom`` requires ``page.width`` and ``page.height``; every other value
    forbids them.
    """

    A4PAPER = "a4paper"
    LETTERPAPER = "letterpaper"
    LEGALPAPER = "legalpaper"
    A5PAPER = "a5paper"
    B5PAPER = "b5paper"
    EXECUTIVEPAPER = "executivepaper"
    CUSTOM = "custom"


class ParallelLayout(StrEnum):
    """ Parallel-text page layout.

    pages: facing pages — best for full critical editions.
    pairs: two columns on the same page — best for short documents.
    interleaved: one column, each translation block following the block it
    translates — for a measure too narrow to split.
    """

    PAGES = "pages"
    PAIRS = "pairs"
    INTERLEAVED = "interleaved"


class InterleavedLineNumbers(StrEnum):
    """ Which text's lines are numbered in the interleaved parallel layout. """

    PRIMARY = "primary"
    BOTH = "both"


class LineationUnit(StrEnum):
    """ What line numbering counts within before restarting. """

    PAGE = "page"
    SECTION = "section"


class LineNumberMargin(StrEnum):
    """ Which margin line numbers sit in.

    ``inner``/``outer`` are relative to the binding and therefore swap between
    recto and verso; ``left``/``right`` are fixed physical positions.
    """

    INNER = "inner"
    OUTER = "outer"
    LEFT = "left"
    RIGHT = "right"


class NotePlacement(StrEnum):
    """ Where the text of a note is printed.

    footnote: at the foot of the page the note is anchored on.
    endnote:  collected at the end of the document.
    none:     notes are dropped entirely, anchor and all.
    """

    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    NONE = "none"


class NoteAnchor(StrEnum):
    """ How the mark that points at a note is set in the text.

    interlinear: raised into the space above the line, taking no width, so the
                 text it annotates is not respaced.
    superscript: an ordinary superscript attached to the preceding word.
    inline:      at full size on the baseline.
    """

    INTERLINEAR = "interlinear"
    SUPERSCRIPT = "superscript"
    INLINE = "inline"


class NoteMark(StrEnum):
    """ The series a note's mark is drawn from. """

    NUMERIC = "numeric"
    ALPHA = "alpha"
    ROMAN = "roman"
    SYMBOL = "symbol"


class ConditionalBlock(StrEnum):
    """ How a whole conditional paragraph is delimited.

    Only conditions the compiler could not decide survive into the output, so a
    marker means "say this only if ...", and a reader has to see where the
    passage starts and stops.
    """

    RULE = "rule"
    BRACKETS = "brackets"
    NONE = "none"


class Visibility(StrEnum):
    SHOWN = "shown"
    HIDDEN = "hidden"


class ColumnPosition(StrEnum):
    """ Where the pair of columns sits within the text block. """

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------


class ForbidExtra(BaseModel):
    """ Base for every settings model: an unknown key is an error.

    Silently ignoring a key the user wrote means the setting they asked for is
    simply absent from the output, with nothing to say why. Forbidding extras
    turns every typo into a message that names the key and its path.
    """

    model_config = ConfigDict(extra="forbid")


class FontFace(ForbidExtra):
    """One fallback face and its optional normal size, in points."""

    # The name goes into \setmainfont{…} and \newfontfamily as written, so it may not hold a
    # character TeX gives a meaning to.
    name: str = Field(min_length=1, pattern=r"^[^{}\\%#&$^_~]+$")
    normal_size: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False, strict=True)

    @model_validator(mode="before")
    @classmethod
    def accept_name(cls, value: object) -> object:
        return {"name": value} if isinstance(value, str) else value


class FontFamily(ForbidExtra):
    """Ordered fallback faces; legacy strings inherit the document's normal size."""

    model_config = ConfigDict(populate_by_name=True)

    entries: list[FontFace] = Field(alias="names", min_length=1)

    @property
    def names(self) -> list[str]:
        return [entry.name for entry in self.entries]

    @model_validator(mode="before")
    @classmethod
    def accept_bare_string_or_list(cls, value: object) -> object:
        if isinstance(value, str):
            return {"names": [value]}
        if isinstance(value, list):
            return {"names": value}
        return value


# Families that always exist, because the stylesheet refers to them by role
# rather than by name: every Hebrew run is set in `hebrew` and everything else
# in `latin`. Users may add more and point a style at them.
LATIN_FAMILY = "latin"
HEBREW_FAMILY = "hebrew"

_DEFAULT_FONTS = {
    LATIN_FAMILY: ["Linux Libertine O"],
    # Frank Ruehl CLM is the house face; Ezra SIL and SBL Hebrew are the usual
    # scholarly substitutes; FreeSerif is the last resort that is present on
    # essentially every Linux TeX installation.
    HEBREW_FAMILY: ["Frank Ruehl CLM", "Ezra SIL", "SBL Hebrew", "FreeSerif"],
}


@lru_cache(maxsize=1)
def _installed_font_families() -> Optional[frozenset[str]]:
    """ Every font family fontconfig knows about, or None if it cannot be asked.

    Cached: a settings file declares a handful of chains and each would
    otherwise re-run the same query. Returning None rather than an empty set
    keeps "fontconfig said there are no fonts" distinguishable from "there is no
    fontconfig", which is the difference between failing and deferring the check
    to the renderer.
    """
    if shutil.which("fc-list") is None:
        return None
    try:
        result = subprocess.run(
            ["fc-list", "--format", "%{family}\n"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    families = set()
    for line in result.stdout.splitlines():
        # fc-list reports a family's aliases comma-separated on one line.
        for name in line.split(","):
            name = name.strip()
            if name:
                families.add(name.casefold())
    return frozenset(families)


def resolve_font(names: list[str]) -> Optional[str]:
    """ The first installed name in a chain.

    Returns None when fontconfig is unavailable, which means "undecidable here";
    the caller leaves the choice to the renderer in that case. Raises when
    fontconfig is available and none of the names is installed.
    """
    installed = _installed_font_families()
    if installed is None:
        return None
    for name in names:
        if name.casefold() in installed:
            return name
    raise ValueError(
        "none of these fonts is installed: "
        + ", ".join(repr(name) for name in names)
        + ". Install one of them, or name a font that is present "
        "(`fc-list : family` lists them)."
    )


# ---------------------------------------------------------------------------
# Text styles
# ---------------------------------------------------------------------------


class TextStyle(ForbidExtra):
    """ How one kind of text is set.

    Every field is optional and ``None`` means "leave it as the surrounding text
    has it", so a style says only what it changes. The defaults on the roles in
    :class:`Styles` spell out the appearance the exporter has always produced.
    """

    font: Optional[str] = Field(
        default=None,
        description=(
            "A family declared in `typography.fonts`. Omit to let the text keep "
            "the font its script selects (`hebrew` for Hebrew, `latin` otherwise)."
        ),
    )
    size: Optional[FontSize] = Field(
        default=None,
        description=(
            "A named size (xxx-small ... xxxx-large), which follows "
            "the selected font’s normal_size (or page.base_font_size when omitted), "
            "or an absolute length such as `9pt`."
        ),
    )
    weight: Optional[FontWeight] = Field(default=None, description="normal | bold")
    style: Optional[FontStyle] = Field(default=None, description="normal | italic")
    variant: Optional[FontVariant] = Field(
        default=None, description="normal | small-caps"
    )
    align: Optional[Alignment] = Field(
        default=None,
        description=(
            "left | right | center | justify. Only on headings, citations, list "
            "labels, the title page and the section separator; an error elsewhere."
        ),
    )
    space_before: Optional[Length] = Field(
        default=None,
        description="Vertical space above. Title-page roles and the section separator only.",
    )
    space_after: Optional[Length] = Field(
        default=None,
        description="Vertical space below. Title-page roles and the section separator only.",
    )

    def is_empty(self) -> bool:
        return all(value is None for value in self.__dict__.values())


class Styles(ForbidExtra):
    """ The appearance of each kind of text the exporter distinguishes.

    The defaults are a book's appearance when its settings say nothing; no renderer
    keeps a copy of them. Changing one changes only that role.
    """

    body: TextStyle = Field(
        default_factory=TextStyle,
        description="Ordinary running text.",
    )
    heading1: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.XX_LARGE, weight=FontWeight.BOLD, align=Alignment.CENTER
        ),
        description="Top-level section heading.",
    )
    heading2: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.X_LARGE, weight=FontWeight.BOLD, align=Alignment.CENTER
        ),
        description="Second-level section heading.",
    )
    heading3: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.LARGE, weight=FontWeight.BOLD, align=Alignment.CENTER
        ),
        description="Third-level section heading.",
    )
    heading4: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.NORMAL, weight=FontWeight.BOLD, align=Alignment.CENTER
        ),
        description="Fourth-level section heading; the deepest level there is.",
    )
    heading_translation: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.NORMAL, style=FontStyle.ITALIC, align=Alignment.CENTER
        ),
        description=(
            "A heading's translated title, where a division is titled twice. Set under "
            "the title it translates, at any of the four heading levels."
        ),
    )
    title_main: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.XXXX_LARGE,
            weight=FontWeight.BOLD,
            align=Alignment.CENTER,
            space_after="1.5ex",
        ),
        description="The main title on the title page.",
    )
    title_sub: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.X_LARGE, align=Alignment.CENTER, space_before="1.5ex"
        ),
        description="The subtitle on the title page.",
    )
    title_alt: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.LARGE, align=Alignment.CENTER, space_after="1ex"
        ),
        description="An alternative title, usually the title in the other language.",
    )
    byline: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.LARGE, align=Alignment.CENTER, space_before="3ex"
        ),
        description="The author/editor line on the title page.",
    )
    edition: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.NORMAL, align=Alignment.CENTER, space_before="2ex"
        ),
        description="The edition statement on the title page.",
    )
    imprint: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.NORMAL, align=Alignment.CENTER, space_before="4ex"
        ),
        description="The publisher/place/date block at the foot of the title page.",
    )
    epigraph: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.SMALL,
            style=FontStyle.ITALIC,
            align=Alignment.CENTER,
            space_before="2ex",
        ),
        description="An epigraph on the title page.",
    )
    imprimatur: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.SMALL,
            style=FontStyle.ITALIC,
            align=Alignment.CENTER,
            space_before="2ex",
        ),
        description="An imprimatur or approbation on the title page.",
    )
    title_page_block: TextStyle = Field(
        default_factory=lambda: TextStyle(size=NamedSize.NORMAL, align=Alignment.CENTER),
        description="Any other paragraph on the title page.",
    )
    distribution_notice: TextStyle = Field(
        default_factory=lambda: TextStyle(size=NamedSize.SMALL, align=Alignment.CENTER),
        description=(
            "The distribution notice on the verso of the title page: who distributes the "
            "book, and where (see the settings file's `distribution.notice`)."
        ),
    )
    back_notice: TextStyle = Field(
        default_factory=lambda: TextStyle(size=NamedSize.SMALL, space_before="2ex"),
        description=(
            "The statement on the book's last page, after the colophon (see the settings "
            "file's `distribution.back_notice`)."
        ),
    )
    citation: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=NamedSize.NORMAL, style=FontStyle.ITALIC, align=Alignment.CENTER
        ),
        description=(
            "A scriptural citation set on a line of its own, naming where a "
            "reading begins or resumes."
        ),
    )
    parsha: TextStyle = Field(
        default_factory=lambda: TextStyle(size=NamedSize.LARGE, weight=FontWeight.BOLD),
        description="A parsha name, run in at the head of the text it opens.",
    )
    aliyah: TextStyle = Field(
        default_factory=lambda: TextStyle(weight=FontWeight.BOLD),
        description="An aliyah or maftir marker, inline at the verse it begins on.",
    )
    verse_number: TextStyle = Field(
        default_factory=TextStyle,
        description="The verse number at the start of each verse.",
    )
    chapter_number: TextStyle = Field(
        default_factory=lambda: TextStyle(size=NamedSize.LARGE, weight=FontWeight.BOLD),
        description="The chapter number, inline at the start of a chapter.",
    )
    instruction: TextStyle = Field(
        default_factory=lambda: TextStyle(weight=FontWeight.BOLD),
        description="An instruction to the reader, in the note apparatus.",
    )
    note: TextStyle = Field(
        default_factory=lambda: TextStyle(weight=FontWeight.BOLD),
        description="The text of an editorial note.",
    )
    note_mark: TextStyle = Field(
        default_factory=lambda: TextStyle(size=NamedSize.XX_SMALL),
        description=(
            "The mark that anchors a note, both in the text and where the note "
            "is printed."
        ),
    )
    line_number: TextStyle = Field(
        default_factory=TextStyle,
        description="Marginal line numbers.",
    )
    section_separator: TextStyle = Field(
        default_factory=lambda: TextStyle(align=Alignment.CENTER),
        description="The separator between unheaded sections.",
    )
    list_label: TextStyle = Field(
        default_factory=lambda: TextStyle(variant=FontVariant.SMALL_CAPS),
        description=(
            "The label naming an item of a labelled list, on a line of its own "
            "above the item."
        ),
    )

    # Highlighted text (tei:hi). Each kind of @rend that changes the look of the text
    # has a role, defaulting to the look its name describes; a hi with several tokens
    # nests them in order. Layout and reading tokens (centered, align-right, ketiv-only,
    # qeri-only) have none.
    highlight_italic: TextStyle = Field(
        default_factory=lambda: TextStyle(style=FontStyle.ITALIC),
        description="Highlighted text the source sets in italics (`rend=\"italic\"`).",
    )
    highlight_bold: TextStyle = Field(
        default_factory=lambda: TextStyle(weight=FontWeight.BOLD),
        description="Highlighted text the source sets in bold (`rend=\"bold\"`).",
    )
    highlight_small_caps: TextStyle = Field(
        default_factory=lambda: TextStyle(variant=FontVariant.SMALL_CAPS),
        description="Highlighted text the source sets in small capitals (`rend=\"small-caps\"`).",
    )
    highlight_superscript: TextStyle = Field(
        default_factory=TextStyle,
        description=(
            "Highlighted text the source raises above the line (`rend` `sup`, "
            "`superscript`, `raised` or `suspended`). It is always raised, and reduced "
            "unless the style names a size, which is then the raised text's size."
        ),
    )
    highlight_large: TextStyle = Field(
        default_factory=lambda: TextStyle(size=NamedSize.X_LARGE),
        description="Highlighted text the source sets larger (`rend=\"large\"`).",
    )
    highlight_small: TextStyle = Field(
        default_factory=lambda: TextStyle(size=NamedSize.SMALL),
        description="Highlighted text the source sets smaller (`rend=\"small\"`).",
    )
    foreign: TextStyle = Field(
        default_factory=TextStyle,
        description=(
            "A phrase in another language than the text around it, such as Hebrew "
            "quoted in English. Its script's font is selected either way."
        ),
    )
    reference: TextStyle = Field(
        default_factory=TextStyle,
        description="The text of a reference or link to a source or another place.",
    )
    poetry_line: TextStyle = Field(
        default_factory=TextStyle,
        description="A line of poetry.",
    )
    list_item: TextStyle = Field(
        default_factory=TextStyle,
        description="The text of an item in a list.",
    )
    abbreviation: TextStyle = Field(
        default_factory=TextStyle,
        description="An abbreviation, where a book reads abbreviations as printed.",
    )
    expansion: TextStyle = Field(
        default_factory=TextStyle,
        description="The expansion of an abbreviation, where a book reads them expanded.",
    )
    printed_error: TextStyle = Field(
        default_factory=TextStyle,
        description="A misprint as the edition printed it, where a book reads errors as printed.",
    )
    correction: TextStyle = Field(
        default_factory=TextStyle,
        description="The correction of a misprint, where a book reads errors corrected.",
    )
    qere: TextStyle = Field(
        default_factory=lambda: TextStyle(style=FontStyle.ITALIC),
        description="The qere: a word as it is read, where it differs from how it is written.",
    )
    ketiv: TextStyle = Field(
        default_factory=TextStyle,
        description=(
            "The ketiv: a word as it is written, printed in parentheses after the qere "
            "when both are given."
        ),
    )
    alternative_reading: TextStyle = Field(
        default_factory=TextStyle,
        description=(
            "An alternative wording, printed in parentheses after the first when a text "
            "gives more than one."
        ),
    )

    @model_validator(mode="after")
    def validate_block_properties(self) -> "Styles":
        """ Refuse an alignment or vertical space on a role that cannot honour it.

        Most roles are set in the middle of a line — a verse number, a note — where
        neither has a meaning, and the renderer would accept the setting and do
        nothing with it.
        """
        for role in type(self).model_fields:
            style: TextStyle = getattr(self, role)
            # Written and not null: `align: null` asks for nothing, so it has no effect to
            # complain about.
            written = {name for name in style.model_fields_set if getattr(style, name) is not None}
            if "align" in written and role not in ALIGNABLE_ROLES:
                raise ValueError(
                    f"styles.{role}.align has no effect: {role} is not set as a line "
                    f"of its own. Roles that take `align`: {', '.join(ALIGNABLE_ROLES)}"
                )
            for name in ("space_before", "space_after"):
                if name in written and role not in SPACED_ROLES:
                    raise ValueError(
                        f"styles.{role}.{name} has no effect: {role} is not set as a "
                        f"paragraph of its own. Roles that take `{name}`: "
                        f"{', '.join(SPACED_ROLES)}"
                    )
        return self


# The roles set as paragraphs of their own, outside reledmac's numbering, which take
# vertical space as well as an alignment.
SPACED_ROLES: tuple[str, ...] = (
    "title_main",
    "title_sub",
    "title_alt",
    "byline",
    "edition",
    "imprint",
    "epigraph",
    "imprimatur",
    "title_page_block",
    "distribution_notice",
    "back_notice",
    "section_separator",
)

# Every role with a line of its own. Those not in SPACED_ROLES sit inside a numbered
# paragraph, where the alignment is set by fills on the line rather than by a block.
ALIGNABLE_ROLES: tuple[str, ...] = (
    "heading1",
    "heading2",
    "heading3",
    "heading4",
    "heading_translation",
    "citation",
    "list_label",
) + SPACED_ROLES


# ---------------------------------------------------------------------------
# Page, paragraphs, and the rest
# ---------------------------------------------------------------------------


class Margins(ForbidExtra):
    """ The white space around the text block.

    Every margin defaults to None, which leaves the renderer's own default in
    place — for the PDF stage that is the document class's, which is what the
    exporter produced before margins were configurable.

    Margins are always named ``inner`` and ``outer`` rather than left and right.
    On a two-sided document the inner margin is the one at the binding, so it
    changes sides between recto and verso; on a one-sided document inner is left
    and outer is right, and the renderer maps them.
    """

    top: Optional[NonNegativeLength] = Field(default=None, description="Space above the text block.")
    bottom: Optional[NonNegativeLength] = Field(
        default=None, description="Space below the text block."
    )
    inner: Optional[NonNegativeLength] = Field(
        default=None,
        description="Margin at the binding edge (the left margin when `sides: one`).",
    )
    outer: Optional[NonNegativeLength] = Field(
        default=None,
        description="Margin at the fore edge (the right margin when `sides: one`).",
    )
    binding_offset: Optional[NonNegativeLength] = Field(
        default=None,
        description=(
            "Extra space added at the binding edge and taken off the fore edge, "
            "for the part of the page a binding swallows."
        ),
    )

    def is_empty(self) -> bool:
        return all(value is None for value in self.__dict__.values())


class PageConfig(ForbidExtra):
    """ The sheet itself: its size, which way up it is, and how it is bound. """

    paper: PaperType = Field(
        default=PaperType.LETTERPAPER,
        description=(
            "a4paper | letterpaper | legalpaper | a5paper | b5paper | "
            "executivepaper | custom. `custom` requires `width` and `height`."
        ),
    )
    width: Optional[NonNegativeLength] = Field(
        default=None, description="Sheet width. Only with `paper: custom`."
    )
    height: Optional[NonNegativeLength] = Field(
        default=None, description="Sheet height. Only with `paper: custom`."
    )
    orientation: Orientation = Field(
        default=Orientation.PORTRAIT, description="portrait | landscape"
    )
    sides: Sides = Field(
        default=Sides.TWO,
        description=(
            "two: printed on both sides, with margins and running heads that "
            "mirror between recto and verso. one: printed on one side only."
        ),
    )
    chapter_start: ChapterStart = Field(
        default=ChapterStart.RECTO,
        description=(
            "recto: a book always opens on a recto (odd) page, with a blank "
            "inserted if needed; under `binding: right` that is the left-hand page "
            "of a spread. any: it opens on whichever page comes next."
        ),
    )
    binding: Binding = Field(
        default=Binding.RIGHT,
        description=(
            "right | left. The edge the book is bound at. It sets the reading "
            "direction of the PDF's spreads, and with `sides: two` it puts the inner "
            "margin, the inner line-number margin and the default running head's "
            "inner slot at that edge of each page."
        ),
    )
    base_font_size: BaseFontSize = Field(
        default=BaseFontSize.PT11,
        description="10pt | 11pt | 12pt. Named sizes in `styles` are relative to this.",
    )
    margins: Margins = Field(
        default_factory=Margins,
        description="Margins around the text block. Omitted margins keep the renderer's default.",
    )

    @model_validator(mode="after")
    def validate_custom_paper(self) -> "PageConfig":
        if self.paper is PaperType.CUSTOM:
            missing = [
                name
                for name in ("width", "height")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    "`paper: custom` requires " + " and ".join(missing)
                )
        elif self.width is not None or self.height is not None:
            raise ValueError(
                f"`width` and `height` may only be set with `paper: custom`, "
                f"not `paper: {self.paper.value}`"
            )
        return self


def right_bound_pages(page: PageConfig) -> bool:
    """ Whether recto and verso are laid out for a binding at the right.

    Only a two-sided document has a recto and a verso to mirror; a one-sided one keeps
    its left and right margins wherever it is bound.
    """
    return page.binding is Binding.RIGHT and page.sides is Sides.TWO


class ParagraphConfig(ForbidExtra):
    """ How paragraphs of running text are set. """

    indent: Length = Field(
        default="0pt", description="First-line indent. `0pt` for unindented paragraphs."
    )
    spacing: NonNegativeLength = Field(
        default="0.5em",
        description=(
            "Vertical space between paragraphs, in addition to normal line "
            "spacing."
        ),
    )
    line_spacing: float = Field(
        default=1.0,
        ge=0.5,
        le=3.0,
        description=(
            "Multiple of single spacing. 1.0 is set solid, 1.5 is one-and-a-half "
            "spaced. Note that Hebrew with vowels and cantillation needs more "
            "leading than unpointed text."
        ),
    )
    alignment: Alignment = Field(
        default=Alignment.JUSTIFY,
        description="justify | left | right | center",
    )


class LineNumberConfig(ForbidExtra):
    """ Marginal line numbers, as a critical edition uses to cite a passage. """

    enabled: bool = Field(
        default=True, description="Whether line numbers are printed at all."
    )
    unit: LineationUnit = Field(
        default=LineationUnit.PAGE,
        description="page | section — what numbering restarts at.",
    )
    increment: int = Field(
        default=5, ge=1, description="Print a number every nth line."
    )
    first: int = Field(
        default=5,
        ge=1,
        description=(
            "The first line number to print. The default matches `increment`, so "
            "the numbers run 5, 10, 15 rather than 1, 5, 10."
        ),
    )
    margin: LineNumberMargin = Field(
        default=LineNumberMargin.OUTER,
        description=(
            "inner | outer | left | right. In a two-column parallel layout each "
            "column takes the nearer outer margin regardless of this setting, "
            "since the alternative is numbers in the gutter between the columns. "
            "In the interleaved layout both texts share the one margin chosen here, "
            "whichever direction each runs in."
        ),
    )
    separation: NonNegativeLength = Field(
        default="1em",
        description="Space between the number and the text block.",
    )
    numerals: Numerals = Field(
        default=Numerals.ARABIC, description="arabic | hebrew"
    )


class NoteConfig(ForbidExtra):
    """ Editorial notes and instructions: where they go and how they are marked. """

    placement: NotePlacement = Field(
        default=NotePlacement.FOOTNOTE,
        description="footnote | endnote | none",
    )
    anchor: NoteAnchor = Field(
        default=NoteAnchor.INTERLINEAR,
        description=(
            "interlinear | superscript | inline. `interlinear` raises the mark "
            "above the line and gives it no width, so the text it annotates is "
            "not respaced — which matters when both sides of a parallel text "
            "have to stay aligned in columns."
        ),
    )
    mark: NoteMark = Field(
        default=NoteMark.NUMERIC,
        description="numeric | alpha | roman | symbol — the series marks are drawn from.",
    )
    # There is deliberately no setting for showing the lemma — the words a note
    # is attached to, repeated where the note is printed. A note in this schema
    # anchors at a point rather than over a range, so there are no such words to
    # repeat: the apparatus entry's lemma is the mark itself, and printing it
    # would give "* ] * the note text".


class ConditionalMarkerConfig(ForbidExtra):
    """ How an undecided conditional passage is delimited.

    A condition the compiler could decide is resolved away, so anything marked
    here is a passage the reader has to choose to say or skip.
    """

    inline_open: str = Field(
        default="[", description="Opens a conditional run inside a paragraph."
    )
    inline_close: str = Field(
        default="]", description="Closes a conditional run inside a paragraph."
    )
    block: ConditionalBlock = Field(
        default=ConditionalBlock.RULE,
        description=(
            "rule | brackets | none — how a whole conditional paragraph is "
            "delimited. Brackets several lines apart do not read as a pair, "
            "hence the rule."
        ),
    )
    rule_width: Percent = Field(
        default="25%", description="Width of the rule, as a percentage of the measure."
    )
    rule_thickness: NonNegativeLength = Field(default="0.4pt", description="Thickness of the rule.")


class MarkerConfig(ForbidExtra):
    """ The small marks that structure a text without being part of it. """

    section_separator: str = Field(
        default="* * * *",
        description=(
            "Printed between sections that have no heading. Set to an empty "
            "string to leave nothing but the space."
        ),
    )
    verse_numbers: Visibility = Field(
        default=Visibility.SHOWN, description="shown | hidden"
    )
    chapter_numbers: Visibility = Field(
        default=Visibility.SHOWN, description="shown | hidden"
    )
    conditional: ConditionalMarkerConfig = Field(
        default_factory=ConditionalMarkerConfig,
        description="Markers around passages whose condition could not be decided.",
    )


class InterleavedConfig(ForbidExtra):
    """ How the translation is set apart in the interleaved parallel layout.

    Without a column boundary between them, the original and its translation are
    told apart by these alone — and by script and direction, where they differ.
    Applies only when `parallel.layout` is `interleaved`.
    """

    translation_size: FontSize = Field(
        default=NamedSize.SMALL,
        description=(
            "Font size of the translation: a named size relative to the base, or an "
            "absolute length."
        ),
    )
    translation_indent: NonNegativeLength = Field(
        default="1em",
        description=(
            "Indent applied to both margins of the translation's paragraphs. `0pt` "
            "to set the translation to the full measure."
        ),
    )
    spacing: NonNegativeLength = Field(
        default="0.25em",
        description=(
            "Vertical space between a block and its translation. The space between "
            "one pair and the next is `paragraphs.spacing`, so keeping this smaller "
            "is what makes each original and its translation read as a pair."
        ),
    )
    line_numbers: InterleavedLineNumbers = Field(
        default=InterleavedLineNumbers.PRIMARY,
        description=(
            "primary | both. `primary` numbers only the primary text's lines, so a "
            "line number cites the text being translated; `both` counts every line "
            "in one series."
        ),
    )


class ParallelTypographyConfig(ForbidExtra):
    """ The geometry of a parallel-text layout.

    Which text goes on which side — or, in the interleaved layout, which comes
    first — is not set here: it is `parallel.column_order` in the compiler section
    of the settings file, because the compiler is what decides the order the
    streams are emitted in.
    """

    layout: ParallelLayout = Field(
        default=ParallelLayout.PAIRS,
        description=(
            "pairs: two columns on the same page. pages: facing pages, which "
            "gives each text a full measure and suits a long work. interleaved: "
            "one column, each block followed by its translation, for a measure "
            "too narrow to split."
        ),
    )
    column_width: Percent = Field(
        default="43%",
        description=(
            "Width of each column as a percentage of the text block. Only in "
            "`pairs` layout; an error under any other. The two columns and the "
            "gap between them share 100%, so well under 50% each — the remainder "
            "leaves the outer margins room for line numbers."
        ),
    )
    column_position: ColumnPosition = Field(
        default=ColumnPosition.CENTER,
        description=(
            "left | center | right — where the pair of columns sits in the text "
            "block. Only in `pairs` layout; an error under any other."
        ),
    )
    interleaved: InterleavedConfig = Field(
        default_factory=InterleavedConfig,
        description="How the translation is set apart, in `interleaved` layout.",
    )

    @model_validator(mode="after")
    def validate_column_settings(self) -> "ParallelTypographyConfig":
        # Column geometry exists only where there are two columns on one page. Under
        # any other layout it would be accepted and do nothing, so a settings file
        # asking for it would look as though it had worked.
        if self.layout is not ParallelLayout.PAIRS:
            for name in ("column_width", "column_position"):
                if name in self.model_fields_set:
                    raise ValueError(
                        f"`{name}` applies only to `layout: pairs`, "
                        f"not `layout: {self.layout.value}`"
                    )
        # Two columns and the gap between them share the text block, so a column of
        # half of it or more leaves the other column nowhere to go.
        if float(self.column_width.rstrip("%")) >= 50:
            raise ValueError(
                f"`column_width` is {self.column_width}, but two columns of it would not "
                "fit beside each other; it must be under 50%"
            )
        return self


class BookmarkSource(StrEnum):
    """Which language a PDF bookmark carries where a work names a section twice."""

    COMBINED = "combined"
    PRIMARY = "primary"
    ALT = "alt"


class BookmarksConfig(ForbidExtra):
    """The PDF outline of a work that names its sections in two languages.

    A work does that in one of two ways — a division with two ``tei:head``, or two
    projects compiled in parallel — and this setting governs both, because to a reader
    they are the same question asked twice.

    ``depth`` is not settable here: the outline is always four levels deep. See
    :class:`TableOfContentsConfig`, whose ``depth`` is the printed table only.
    """

    from_: BookmarkSource = Field(
        default=BookmarkSource.COMBINED,
        alias="from",
        description=(
            "combined: join both titles in one entry. primary: the first column's "
            "title, or the division's first head. alt: the other one."
        ),
    )


class HeadingSource(StrEnum):
    """Which heading a section carries on the page, where a work titles it twice.

    The first three are :class:`BookmarkSource`'s, and mean the same. ``BOTH`` has no
    counterpart there because an outline entry is one line and cannot show two titles in
    two places; a page can.
    """

    COMBINED = "combined"
    PRIMARY = "primary"
    ALT = "alt"
    BOTH = "both"


class HeadingsConfig(ForbidExtra):
    """The heading a section carries on the page, where a work titles it twice.

    The same question :class:`BookmarksConfig` asks of the outline, asked of the page, so
    it takes the same vocabulary. The values differ only in what "combined" can mean: an
    outline entry can join two titles into one string, while a heading on a page cannot,
    so ``combined`` there prints one heading where the columns agree and both where they
    do not.
    """

    from_: HeadingSource = Field(
        default=HeadingSource.COMBINED,
        alias="from",
        description=(
            "combined: one heading, spanning the page — both titles where the columns "
            "differ, one where they agree. primary: the first column's title, spanning. "
            "alt: the other one, spanning. both: each column keeps its own heading, in "
            "its column."
        ),
    )


class InstructionsConfig(ForbidExtra):
    """The rubric a passage carries, where a work prints it in both columns.

    :class:`HeadingsConfig`'s question, asked of a rubric. It takes the same vocabulary,
    but a rubric is not hoisted out of the columns the way a heading is: it stands
    mid-flow, and a parallel block cannot be interrupted partway through. The rubric that
    is kept therefore stays *in its column*.

    **Anything but ``both`` requires that every rubric fall on an alignment boundary.**
    Where the columns are aligned at the rubric's own position, a reader of either sees it
    on the row it governs. Where they are not, the column that gave up its copy has no
    rubric anywhere near the passage it is about, and a reader of that column loses it
    outright. ``both`` carries no such requirement, and is therefore the default —
    the one setting here whose default is the conservative value rather than the tidy one,
    because getting it wrong loses a rubric rather than merely repeating one.

    :class:`HeadingsConfig` defaults the other way, and the asymmetry is deliberate: a
    heading is lifted clear of the columns, so deduplicating one costs nothing.
    """

    from_: HeadingSource = Field(
        default=HeadingSource.BOTH,
        alias="from",
        description=(
            "combined: one rubric where the two columns give it alike, both where they "
            "differ. primary: always the first column's. alt: always the other. both: "
            "each column keeps its own. Anything but both requires that every rubric fall "
            "on an alignment boundary, or the column that gives up its copy loses it near "
            "the passage it is about."
        ),
    )


class TableOfContentsConfig(ForbidExtra):
    """ An auto-generated table of contents.

    ``depth`` is independent of the PDF bookmark depth, which is always four
    levels deep regardless of this setting.
    """

    enabled: bool = Field(
        default=False, description="Whether to print a table of contents."
    )
    depth: int = Field(
        default=4, ge=1, le=4, description="Heading levels shown, 1-4."
    )


# ---------------------------------------------------------------------------
# The whole tree
# ---------------------------------------------------------------------------


class ListConfig(ForbidExtra):
    """ How the items of a labelled list are set off from the prose around them. """

    item_indent: NonNegativeLength = Field(
        default="2em",
        description=(
            "Indent applied to both margins of an item's paragraphs, so an item "
            "reads as a block of its own. `0pt` to set items flush with the "
            "surrounding text and let the label alone distinguish them."
        ),
    )


# Validation-context key: False skips checking that declared font chains resolve here.
RESOLVE_FONTS = "resolve_fonts"

_FONT_KEY_PATTERN = re.compile(r"[a-z]+(?:-[a-z]+)*")


class TypographyConfig(ForbidExtra):
    """ Everything about how the exported document looks.

    Read by the output stage only; the linear-XML compiler ignores it. Every
    section is optional, so a settings file need only say what it wants changed.

    See ``doc/typography.md`` for the full reference.
    """

    fonts: dict[str, FontFamily] = Field(
        default_factory=dict,
        description=(
            "Named font families, each a chain of names or {name, normal_size} entries tried in order. "
            "`latin` and `hebrew` always exist and are used for Latin-script and "
            "Hebrew-script text respectively; add your own and point a style at "
            "them by name."
        ),
    )
    page: PageConfig = Field(
        default_factory=PageConfig, description="Paper size, sides, base font size, margins."
    )
    paragraphs: ParagraphConfig = Field(
        default_factory=ParagraphConfig, description="Indent, spacing, leading, alignment."
    )
    styles: Styles = Field(
        default_factory=Styles, description="The appearance of each kind of text."
    )
    line_numbers: LineNumberConfig = Field(
        default_factory=LineNumberConfig, description="Marginal line numbers."
    )
    notes: NoteConfig = Field(
        default_factory=NoteConfig, description="Placement and marking of notes."
    )
    markers: MarkerConfig = Field(
        default_factory=MarkerConfig,
        description="Section separators, verse and chapter numbers, conditional markers.",
    )
    lists: ListConfig = Field(
        default_factory=ListConfig,
        description="How the items of a labelled list are indented.",
    )
    parallel: ParallelTypographyConfig = Field(
        default_factory=ParallelTypographyConfig,
        description="Geometry of a parallel-text layout.",
    )
    table_of_contents: TableOfContentsConfig = Field(
        default_factory=TableOfContentsConfig,
        description="An auto-generated table of contents.",
    )
    bookmarks: BookmarksConfig = Field(
        default_factory=BookmarksConfig,
        description="The PDF outline, where a work names a section in two languages.",
    )
    headings: HeadingsConfig = Field(
        default_factory=HeadingsConfig,
        description="Headings on the page, where a work names a section in two languages.",
    )
    instructions: InstructionsConfig = Field(
        default_factory=InstructionsConfig,
        description="Rubrics, where a work prints the same one in both columns.",
    )
    page_header: RunningHeadConfig = Field(
        default_factory=default_page_header,
        description=(
            "Running head. Defaults to the current section title on the inner "
            "edge and the page number on the outer, wherever `page.binding` puts "
            "them; write `{}` for no head at all. See doc/typography.md for the "
            "template codes."
        ),
    )
    page_footer: RunningHeadConfig = Field(
        default_factory=RunningHeadConfig,
        description="Running foot; same shape as `page_header`, but empty by default.",
    )

    # Which families the settings file actually named, as opposed to the ones
    # filled in below. Only the former are checked against the installed
    # fonts, so the PDF stage leaves the choice among an unmentioned default's
    # faces to TeX.
    _declared_fonts: frozenset[str] = PrivateAttr(default=frozenset())

    @property
    def declared_fonts(self) -> frozenset[str]:
        """ The font families the settings file named itself. """
        return self._declared_fonts

    @field_validator("fonts")
    @classmethod
    def validate_font_keys(cls, fonts: dict[str, FontFamily]) -> dict[str, FontFamily]:
        """ A family key becomes the name of a TeX command, so it is spelled to fit one.

        TeX control sequences are letters only. Lower-case words joined by single
        hyphens map one to one onto ``OSfont`` plus the capitalised words, so two keys
        can never declare the same command.
        """
        for key in fonts:
            if not _FONT_KEY_PATTERN.fullmatch(key):
                raise ValueError(
                    f"font family `{key}` must be lower-case letters, with single "
                    "hyphens between words (e.g. `note-sans`)"
                )
        return fonts

    @model_validator(mode="after")
    def apply_font_defaults(self, info: ValidationInfo) -> "TypographyConfig":
        """ Fill in `latin` and `hebrew` and check every chain resolves.

        A user-declared `latin` or `hebrew` replaces the default outright rather
        than extending it: someone who names a Hebrew face and gets Frank Ruehl
        anyway, because their name was misspelled and the old chain was still
        underneath, has been told nothing.

        A renderer that does not select fonts itself (the electronic book leaves that
        to the reader's device) validates with ``context={RESOLVE_FONTS: False}``,
        since whether this machine has a face says nothing about the reader's.
        """
        self._declared_fonts = frozenset(self.fonts)
        for family, names in _DEFAULT_FONTS.items():
            self.fonts.setdefault(family, FontFamily(names=list(names)))
        # Only a chain the settings file named is checked. A default the user
        # never asked for must not fail on a machine that happens not to have
        # it: the renderer falls back for those — the PDF stage leaves the
        # choice to TeX, as an \IfFontExistsTF chain — and refusing to build at
        # all would mean nobody could export anything without first installing
        # this project's house fonts.
        if not (info.context or {}).get(RESOLVE_FONTS, True):
            return self
        for family in self._declared_fonts:
            try:
                resolve_font(self.fonts[family].names)
            except ValueError as e:
                raise ValueError(f"font `{family}`: {e}") from e
        return self

    @model_validator(mode="after")
    def bind_default_page_header(self) -> "TypographyConfig":
        """ The default running head follows the binding.

        Its slots are physical positions, so a right-bound book needs them mirrored to
        keep the page number on the fore edge. A head the settings file states is its
        own author's physical positions and is left as written.
        """
        if "page_header" not in self.model_fields_set:
            self.page_header = default_page_header(right_bound=right_bound_pages(self.page))
            # Assignment marks the field set; it is still the default, not the file's.
            self.__pydantic_fields_set__.discard("page_header")
        return self

    @model_validator(mode="after")
    def validate_style_font_references(self) -> "TypographyConfig":
        for role, style in self.styles.__dict__.items():
            if style.font is not None and style.font not in self.fonts:
                known = ", ".join(sorted(self.fonts))
                raise ValueError(
                    f"styles.{role}.font names `{style.font}`, which is not "
                    f"declared in typography.fonts (declared: {known})"
                )
        return self

    @model_validator(mode="after")
    def validate_notes_are_not_styled_away(self) -> "TypographyConfig":
        """ Styling notes that are switched off is a contradiction, not a no-op.

        Someone who sets a note style and `placement: none` in the same file has
        two intentions that cannot both hold, and the one that silently wins
        deletes their notes.
        """
        if self.notes.placement is NotePlacement.NONE:
            # Only an explicitly written style is a contradiction; the defaults
            # are always present and say nothing about what the user wants.
            for role in ("note", "note_mark"):
                if role in self.styles.model_fields_set:
                    raise ValueError(
                        f"styles.{role} is set but notes.placement is `none`, "
                        "so no notes are printed. Remove one of the two."
                    )
        return self
