""" Custom page headers and footers for the TeX/PDF stage.

A settings file declares what goes in the left, center and right slots of the
running head and foot, separately for odd and even pages (or for all pages at
once). Each slot is a template: literal text mixed with codes in braces that
stand for things only TeX knows at shipout time — the page number, the heading
in force, the chapter number.

The codes are backed by LaTeX mark classes that ``reledmac.xslt`` inserts at
every heading and chapter milestone. Marks survive reledmac's ``\\pstart``
boxing and reledpar's column assembly, so the value the page style reads is the
one in force on that page.

Template parsing, validation against the closed code list, and TeX generation
all live here rather than in the stylesheet: this is the part with real logic,
and it is directly testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from opensiddur.exporter.tex.escape import escape_tex

# ---------------------------------------------------------------------------
# The closed code list
# ---------------------------------------------------------------------------

# Marks are read with \LastMark, i.e. the value in force at the *end* of the
# page — the same semantics as LaTeX's own \botmark/\leftmark. A heading that
# starts partway down a page therefore names that page.
#
# The `-alt` family reads the second parallel stream. Without it only the
# primary (Leftside) column's headings could ever reach a running head, which
# would make an English running head impossible on a Hebrew-primary parallel
# volume. In a non-parallel document these marks are never set and the codes
# expand to nothing.
#
# \thepage is wrapped LTR for the same reason \chno and \vno wrap digits in the
# body: a slot declaring Hebrew forces RTL, and digits laid out in that
# direction come out reversed — page 50 reads "05". This applies to the roman
# numerals of the front matter too. An extra LTR group inside an LTR slot is
# harmless. \hebrewnumeral needs no such wrapper: its output is Hebrew letters,
# which belong in the slot's own direction.
RUNNING_HEAD_CODES: dict[str, str] = {
    "page": r"{\textdir TLT\foreignlanguage{english}{\thepage}}",
    "page-hebrew": r"\hebrewnumeral{\value{page}}",
    "document-title": r"\OSDocumentTitle",
    "book-title": r"\LastMark{OSbook}",
    "book-title-alt": r"\LastMark{OSbookAlt}",
    "chapter-number": r"\LastMark{OSchapter}",
    "chapter-number-hebrew": r"\OSHebrewNumber{\LastMark{OSchapter}}",
    "head1": r"\LastMark{OSheadA}",
    "head2": r"\LastMark{OSheadB}",
    "head3": r"\LastMark{OSheadC}",
    "head4": r"\LastMark{OSheadD}",
    "head1-alt": r"\LastMark{OSheadAAlt}",
    "head2-alt": r"\LastMark{OSheadBAlt}",
    "head3-alt": r"\LastMark{OSheadCAlt}",
    "head4-alt": r"\LastMark{OSheadDAlt}",
    "section-title": r"\LastMark{OSheadAny}",
    "section-title-alt": r"\LastMark{OSheadAnyAlt}",
}


# Hebrew block plus the Hebrew presentation forms, matching the range
# f:emit-bidi-mark uses in reledmac.xslt. Hebrew segments joined by whitespace
# or connecting punctuation are one run: a paired parsha name is written with
# an en-dash — תַזְרִיעַ–מְצֹרָע — which is outside the Hebrew block, and splitting on
# it would make the dash its own LTR embedding and let a neighbouring chapter
# number reorder into the middle of the name. (The maqaf of לֶךְ־לְךָ is inside
# the block and was never at risk.)
_HEBREW = "֐-׿יִ-ﭏ"
_HEBREW_JOINER = r"[\s‐-―/,.:;-]"
_HEBREW_RUN = re.compile(f"[{_HEBREW}]+(?:{_HEBREW_JOINER}*[{_HEBREW}]+)*")


def _emit_bidi_literal(s: str) -> str:
    """Give each run of literal template text its own direction and font.

    The Python counterpart of ``f:emit-bidi-mark``. A slot's declared language
    sets the base direction, which decides the order runs are laid out in, but
    ``\\textdir`` forces a direction rather than running the bidi algorithm — so
    a run left bare comes out reversed in a slot that runs the other way, and
    ``"p{page}"`` in a Hebrew slot reads "1p". Hebrew runs take ``\\texthebrew``,
    which also selects the Hebrew font a Latin-font slot has no glyphs from.
    """
    parts: list[str] = []
    position = 0
    for match in _HEBREW_RUN.finditer(s):
        _append_ltr(parts, s[position:match.start()])
        parts.append(r"\texthebrew{" + escape_tex(match.group()) + "}")
        position = match.end()
    _append_ltr(parts, s[position:])
    return "".join(parts)


def escape_with_hebrew_runs(s: str) -> str:
    """Escape text for a left-to-right context, setting each Hebrew run as Hebrew.

    Used for the colophon (licences, credits and the bibliography): the
    surrounding text is already left to right, so only the Hebrew needs a wrapper —
    for its direction and for the font a Latin face has no glyphs in.
    """
    parts: list[str] = []
    position = 0
    for match in _HEBREW_RUN.finditer(s):
        parts.append(escape_tex(s[position:match.start()]))
        parts.append(r"\texthebrew{" + escape_tex(match.group()) + "}")
        position = match.end()
    parts.append(escape_tex(s[position:]))
    return "".join(parts)


def _append_ltr(parts: list[str], text: str) -> None:
    if not text:
        return
    if not text.strip():
        # Whitespace between two runs carries no direction of its own; wrapping
        # it would only add empty groups.
        parts.append(text)
        return
    parts.append(r"{\textdir TLT\foreignlanguage{english}{" + escape_tex(text) + "}}")


@dataclass(frozen=True)
class Segment:
    """One piece of a parsed template: either literal text or a code."""

    is_code: bool
    value: str


def parse_template(template: str) -> list[Segment]:
    """Split a header/footer template into literal and code segments.

    ``{{`` and ``}}`` are literal braces. Everything else outside ``{...}`` is
    literal text.

    Raises:
        ValueError: on an unknown code, an unterminated ``{``, or a stray ``}``.
    """
    segments: list[Segment] = []
    literal: list[str] = []
    i = 0
    length = len(template)
    while i < length:
        char = template[i]
        if char == "{":
            if i + 1 < length and template[i + 1] == "{":
                literal.append("{")
                i += 2
                continue
            end = template.find("}", i + 1)
            if end == -1:
                raise ValueError(
                    f"Unterminated '{{' in header/footer template: {template!r}"
                )
            code = template[i + 1:end]
            if code not in RUNNING_HEAD_CODES:
                raise ValueError(
                    f"Unknown header/footer code: {{{code}}}. "
                    f"Known codes: {', '.join(sorted(RUNNING_HEAD_CODES))}"
                )
            if literal:
                segments.append(Segment(is_code=False, value="".join(literal)))
                literal = []
            segments.append(Segment(is_code=True, value=code))
            i = end + 1
        elif char == "}":
            if i + 1 < length and template[i + 1] == "}":
                literal.append("}")
                i += 2
                continue
            raise ValueError(
                f"Unmatched '}}' in header/footer template: {template!r} "
                "(write '}}' for a literal brace)"
            )
        else:
            literal.append(char)
            i += 1
    if literal:
        segments.append(Segment(is_code=False, value="".join(literal)))
    return segments


def expand_template(template: str) -> str:
    """Expand a template into TeX, escaping the literal parts."""
    return "".join(
        RUNNING_HEAD_CODES[segment.value]
        if segment.is_code
        else _emit_bidi_literal(segment.value)
        for segment in parse_template(template)
    )


def is_hebrew_language(language: str | None) -> bool:
    """Whether a declared language is written in the Hebrew script.

    The rule of ``f:is-hebrew-lang`` in ``tex/common.xsl``: a script subtag decides
    (``he-Latn`` is a transliteration, ``arc-Hebr`` Aramaic in Hebrew letters); without
    one, Hebrew, Yiddish and Aramaic are. Only Hebrew script vs not matters, because that
    is all the direction wrapper needs.
    """
    if not language:
        return False
    subtags = language.lower().split("-")
    script = next((tag for tag in subtags[1:] if len(tag) == 4), None)
    if script:
        return script == "hebr"
    return subtags[0] in ("he", "yi", "arc")


# ---------------------------------------------------------------------------
# Settings models
# ---------------------------------------------------------------------------


class RunningHeadPosition(BaseModel):
    """One slot (left, center or right) of a running head or foot.

    A bare string is accepted as shorthand for ``{text: ...}`` so the common
    case stays a one-liner in YAML.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    text: str = ""
    # Direction and font are chosen from this. Defaults to the document's own
    # language when unset. A BCP 47 tag, as in xml:lang: a misspelt one would
    # quietly set the slot left to right.
    language: str | None = Field(
        default=None, pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{1,8})*$"
    )
    # When set, the slot renders only if this template expands to something
    # non-empty. Literal text in `text` is suppressed along with the codes, so
    # "Chapter {chapter-number}" leaves no orphaned "Chapter" on a page before
    # the first chapter.
    if_: str | None = Field(default=None, alias="if")

    @model_validator(mode="before")
    @classmethod
    def accept_bare_string(cls, value: object) -> object:
        if isinstance(value, str):
            return {"text": value}
        return value

    @field_validator("text", "if_")
    @classmethod
    def validate_template(cls, v: str | None) -> str | None:
        if v:
            parse_template(v)
        return v

    def is_empty(self) -> bool:
        return not self.text


class RunningHeadSide(BaseModel):
    """The three slots of a running head or foot on one class of page."""

    model_config = ConfigDict(extra="forbid")

    left: RunningHeadPosition = Field(default_factory=RunningHeadPosition)
    center: RunningHeadPosition = Field(default_factory=RunningHeadPosition)
    right: RunningHeadPosition = Field(default_factory=RunningHeadPosition)

    def is_empty(self) -> bool:
        return all(p.is_empty() for p in (self.left, self.center, self.right))


class RunningHeadConfig(BaseModel):
    """A running head or foot.

    ``all`` is shorthand for "the same on every page"; it cannot be combined
    with ``odd`` or ``even``. The three are optional rather than
    default-constructed so that "declared but empty" stays distinguishable from
    "not declared", which the exclusivity check needs.

    Nothing declared means no head at all: fancyhdr leaves the slots empty. That
    is a real choice a settings file can make (`page_header: {}`), distinct from
    saying nothing, which takes ``default_page_header()``.
    """

    model_config = ConfigDict(extra="forbid")

    all: RunningHeadSide | None = None
    odd: RunningHeadSide | None = None
    even: RunningHeadSide | None = None

    @model_validator(mode="after")
    def validate_all_is_exclusive(self) -> RunningHeadConfig:
        if self.all is not None and (self.odd is not None or self.even is not None):
            raise ValueError(
                "`all` cannot be combined with `odd` or `even`: "
                "use `all` for the same content on every page, or `odd`/`even` "
                "to differentiate them"
            )
        return self

    def is_empty(self) -> bool:
        return all(
            side is None or side.is_empty()
            for side in (self.all, self.odd, self.even)
        )

    def declared_sides(self) -> list[tuple[str, RunningHeadSide]]:
        """Non-empty sides paired with their fancyhdr parity suffix."""
        pairs = (("", self.all), ("O", self.odd), ("E", self.even))
        return [
            (suffix, side)
            for suffix, side in pairs
            if side is not None and not side.is_empty()
        ]


# An unconfigured document still gets a running head. Every heading already
# records itself with \InsertMark (see the `heading` template in reledmac.xslt)
# and {section-title} reads the last of them, so naming the current section
# costs nothing that is not already emitted. The arrangement is book.cls's own —
# title inner, page number outer, where inner is the left of an odd page, the
# same sense `geometry` is given its margins in — so a document that configures
# nothing keeps its page number where it has always been. Under `page.sides:
# one` fancyhdr treats every page as odd, so the `odd` slots are the ones that
# apply.
# A right-bound book (`page.binding: right`, two-sided) has its binding at the
# right of an odd page, so the same arrangement is the mirror image of this one.
# `page_header: {}` in a settings file is the way to ask for no head at all.
DEFAULT_PAGE_HEADER = {
    "odd": {"left": "{section-title}", "right": "{page}"},
    "even": {"left": "{page}", "right": "{section-title}"},
}
DEFAULT_RIGHT_BOUND_PAGE_HEADER = {
    "odd": {"left": "{page}", "right": "{section-title}"},
    "even": {"left": "{section-title}", "right": "{page}"},
}


def default_page_header(right_bound: bool = False) -> RunningHeadConfig:
    """The running head a settings file gets when it declares none.

    ``right_bound`` says that recto and verso are laid out for a binding at the
    right (see ``typography.right_bound_pages``). A fresh instance each time: a
    shared model would be handed to every ``TypographyConfig`` at once.
    """
    return RunningHeadConfig.model_validate(
        DEFAULT_RIGHT_BOUND_PAGE_HEADER if right_bound else DEFAULT_PAGE_HEADER
    )


# ---------------------------------------------------------------------------
# TeX generation
# ---------------------------------------------------------------------------

_SLOT_LETTERS = (("left", "L"), ("center", "C"), ("right", "R"))

# Nothing in this exporter sets \leftmark/\rightmark deliberately: running heads
# come from fancyhdr slots driven by the kernel's mark classes, and \OSheadA-D
# are plain macros that never call \@mkboth. But book.cls's \tableofcontents
# issues \@mkboth{CONTENTS}{CONTENTS}, and with no later \markboth anywhere that
# head would stay in force for the rest of the book — which is exactly what it
# did. Silence automatic marks outright, so a document can only ever show a head
# it asked for.
_SILENCE_AUTOMATIC_MARKS = "\\makeatletter\n\\let\\@mkboth\\@gobbletwo\n\\makeatother\n"


def render_position(
    position: RunningHeadPosition,
    default_language: str | None = None,
) -> str:
    """Render one slot as TeX.

    The content is wrapped in an explicit direction group so it reads correctly
    regardless of the surrounding page's direction, and in ``\\OSHFIfNonEmpty``
    when the slot declares an ``if``.
    """
    if position.is_empty():
        return ""

    language = position.language if position.language is not None else default_language
    if is_hebrew_language(language):
        direction = r"\textdir TRT\foreignlanguage{hebrew}"
    else:
        direction = r"\textdir TLT\foreignlanguage{english}"

    # \foreignlanguage takes its text as an argument, so the group the direction
    # switch opens now closes around it rather than after it.
    content = "{" + direction + "{" + expand_template(position.text) + "}}"

    if position.if_:
        # The test is expanded bare: no direction wrapper, so an unset mark
        # really does yield an empty expansion.
        content = r"\OSHFIfNonEmpty{" + expand_template(position.if_) + "}{" + content + "}"
    return content


def _render_side(
    command: str,
    suffix: str,
    side: RunningHeadSide,
    default_language: str | None,
) -> list[str]:
    lines = []
    for attribute, letter in _SLOT_LETTERS:
        rendered = render_position(getattr(side, attribute), default_language)
        if rendered:
            lines.append(f"\\{command}[{letter}{suffix}]{{{rendered}}}")
    return lines


def build_page_style_tex(
    page_header: RunningHeadConfig | None = None,
    page_footer: RunningHeadConfig | None = None,
    default_language: str | None = None,
) -> str:
    """Build the fancyhdr preamble block for the configured headers and footers.

    Always silences the document class's automatic marks. When nothing is
    configured — which a settings file asks for with ``page_header: {}`` — that
    is all it emits: the book-class page style is left in place, but with no
    head it can carry but the page number.

    ``L``/``C``/``R`` are *physical* page positions; ``O``/``E`` are odd and
    even pages, which ``book`` distinguishes because it is twoside by default.
    A side declared under ``all`` emits the unsuffixed slots, which fancyhdr
    applies to both parities.
    """
    header_empty = page_header is None or page_header.is_empty()
    footer_empty = page_footer is None or page_footer.is_empty()
    if header_empty and footer_empty:
        return _SILENCE_AUTOMATIC_MARKS

    slots: list[str] = []
    if not header_empty:
        for suffix, side in page_header.declared_sides():
            slots.extend(_render_side("fancyhead", suffix, side, default_language))
    if not footer_empty:
        for suffix, side in page_footer.declared_sides():
            slots.extend(_render_side("fancyfoot", suffix, side, default_language))

    lines = [
        _SILENCE_AUTOMATIC_MARKS.rstrip("\n"),
        r"\usepackage{fancyhdr}",
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        # The kernel's \cleardoublepage inserts a blank verso to force the next
        # page odd — after a title page, among others — but leaves it in the
        # current page style, so a wholly blank page arrives carrying a running
        # head. Make the filler page empty, as it should be.
        r"\makeatletter",
        r"\renewcommand*{\cleardoublepage}{\clearpage\if@twoside\ifodd\c@page\else"
        r"\hbox{}\thispagestyle{empty}\newpage\if@twocolumn\hbox{}\newpage\fi\fi\fi}",
        r"\makeatother",
        *slots,
        # No rules: the running heads are content, not a frame. A project that
        # wants them can \renewcommand these through additional-preamble.
        r"\renewcommand{\headrulewidth}{0pt}",
        r"\renewcommand{\footrulewidth}{0pt}",
    ]
    if not header_empty:
        # The book class leaves \headheight at 12pt, which fancyhdr complains
        # about for anything but the smallest body font.
        lines.append(r"\setlength{\headheight}{15pt}")
    # `plain` is what \tableofcontents and other \chapter*-style pages use;
    # without this they would drop out of the running-head scheme. Title pages
    # are unaffected — they use `empty`.
    lines.append(r"\fancypagestyle{plain}{%")
    lines.append(r"  \fancyhf{}")
    lines.extend("  " + slot for slot in slots)
    lines.append(r"  \renewcommand{\headrulewidth}{0pt}%")
    lines.append(r"  \renewcommand{\footrulewidth}{0pt}%")
    lines.append(r"}")

    return "\n".join(lines) + "\n"
