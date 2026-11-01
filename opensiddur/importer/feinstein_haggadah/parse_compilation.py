"""Parse Open Siddur haggadah compilation JSON into section content."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Literal

from opensiddur.importer.feinstein_haggadah.sections import (
    BARECH_SUBSECTION_PREFIXES,
    H3_SLUGS,
    HALLEL_SUBSECTION_PREFIXES,
    INDEX_NODES,
    MAGID_SUBSECTION_PREFIXES,
    NIRTZAH_SUBSECTION_PREFIXES,
    SectionContent,
    TextBlock,
    match_subsection_by_incipit,
    match_subsection_slug,
)
from opensiddur.importer.util.pages import feinstein_haggadah_data_directory

#: Subsection tables that apply only inside one h3 section. Scoping matters: the second-cup and
#: fourth-cup בורא פרי הגפן blessings are word-for-word identical, and only their parent distinguishes
#: them.
SCOPED_SUBSECTION_PREFIXES: dict[str, list[tuple[str, str]]] = {
    "hallel": HALLEL_SUBSECTION_PREFIXES,
    "barekh": BARECH_SUBSECTION_PREFIXES,
}

#: Subsections the compilation runs together with the passage before them in a single table cell, so
#: that they have to be cut out mid-cell. Deliberately tiny: every other subsection begins its own
#: cell, and scanning a whole prefix table line by line would slice rows that merely quote a verse
#: another subsection also opens with.
ROW_SPLIT_PREFIXES: list[tuple[str, str]] = [
    ("לְשָּׁנָה הַבָּאָה בִּירוּשָׁלָיִם", "leshanah_habaah"),
]


@dataclass(frozen=True)
class Segment:
    """One run of an English cell, classified by what the source's markup says it is.

    ``governs``/``governed`` pair a rubric with the text it controls: they are set on the two
    segments of a conditional passage, so that the builder can wrap exactly those in
    ``j:conditional`` markers. A rubric with ``governs`` false merely instructs the reader.
    """

    kind: Literal["paragraph", "instruction"]
    text: str
    governs: bool = False
    governed: bool = False


@dataclass
class CompilationRow:
    hebrew: str
    english: str
    h3_title: str | None = None
    h3_boundary: bool = False


#: Private-use sentinels standing in for the boundaries of a ``<span class="instruction">``
#: once the tags have been stripped. The class attribute is the only thing in the source that
#: reliably separates a rubric from the text it governs, so it has to survive cleaning; see
#: :func:`split_parenthetical_instructions`.
RUBRIC_OPEN = ""
RUBRIC_CLOSE = ""

_INSTRUCTION_SPAN_OPEN = re.compile(r'<span[^>]*class="instruction"[^>]*>', re.IGNORECASE)
_SPAN_TAG = re.compile(r"<(/?)span\b[^>]*>", re.IGNORECASE)


def _mark_instruction_spans(raw: str) -> str:
    """Replace each instruction span's tags with sentinels, leaving other spans alone.

    A ``</span>`` closes whichever span is open, and the source nests spans, so the matching
    close has to be found by tracking depth rather than by taking the next one.
    """
    out: list[str] = []
    cursor = 0
    while True:
        opening = _INSTRUCTION_SPAN_OPEN.search(raw, cursor)
        if opening is None:
            out.append(raw[cursor:])
            return "".join(out)
        out.append(raw[cursor : opening.start()])
        out.append(RUBRIC_OPEN)
        depth = 1
        position = opening.end()
        while depth and (tag := _SPAN_TAG.search(raw, position)):
            out.append(raw[position : tag.start()])
            depth += -1 if tag.group(1) else 1
            if depth:
                out.append(tag.group())
            position = tag.end()
        out.append(RUBRIC_CLOSE)
        cursor = position


def _clean_html_cell(raw: str) -> str:
    text = _mark_instruction_spans(raw)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\s*jQuery\([^)]*\)\.tooltip\(\{.*?\}\)\s*;?", "", text, flags=re.DOTALL)
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln and ln != "\xa0")


def _first_line(text: str) -> str:
    for line in text.split("\n"):
        line = line.strip()
        if line and line != "\xa0":
            return line
    return ""


def _non_empty_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.split("\n") if ln.strip() and ln.strip() != "\xa0"]


def load_compilation_json(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = feinstein_haggadah_data_directory() / "compilation.json"
    return json.loads(path.read_text(encoding="utf-8"))


def parse_rows(compilation: dict[str, Any]) -> list[CompilationRow]:
    html = compilation["content"]
    pairs = re.findall(
        r'<tr>\s*<td[^>]*>\s*<div class="liturgy"[^>]*>(.*?)</div>\s*</td>\s*'
        r'<td[^>]*>\s*<div class="english"[^>]*>(.*?)</div>',
        html,
        re.DOTALL,
    )
    rows: list[CompilationRow] = []
    current_h3: str | None = None
    for he_raw, en_raw in pairs:
        h3_boundary = False
        if "<h3>" in en_raw:
            match = re.search(r"<h3>([^<]+)</h3>", en_raw)
            if match:
                current_h3 = match.group(1)
                h3_boundary = True
        rows.append(
            CompilationRow(
                hebrew=_clean_html_cell(he_raw),
                english=_clean_html_cell(en_raw),
                h3_title=current_h3,
                h3_boundary=h3_boundary,
            )
        )
    return rows


def _is_section_heading_row(row: CompilationRow) -> bool:
    """True for a short section title in its own table cell at an h3 boundary."""
    hebrew = row.hebrew.strip()
    if not hebrew or "\n" in hebrew or len(hebrew) > 40:
        return False
    if not row.h3_boundary:
        return False
    if len(hebrew.split()) > 6:
        return False
    return True


def _matching_paren(text: str, open_at: int) -> int | None:
    """Index of the ``)`` closing the ``(`` at ``open_at``, or None if unbalanced.

    Depth is tracked rather than taking the next ``)``, because rubrics contain parentheses of
    their own — the source writes "…who did not eat (?!) they respond:" inside one.
    """
    depth = 0
    for index in range(open_at, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _strip_sentinels(text: str) -> str:
    return text.replace(RUBRIC_OPEN, "").replace(RUBRIC_CLOSE, "").strip()


def split_parenthetical_instructions(
    text: str,
) -> list[Segment]:
    """Split English text into liturgical paragraphs, rubrics, and conditional passages.

    The source marks rubrics with ``<span class="instruction">``, which :func:`_clean_html_cell`
    has reduced to sentinels. Where the parentheses fall relative to that span is what says
    whether a rubric merely instructs the reader or governs text that is conditional:

    ``(On Shabbat begin here.)`` wholly inside the span
        a plain rubric — the parentheses are the rubric's own punctuation.

    ``(`` … span … text … ``)``, or ``(`` inside the span and ``)`` after it
        a conditional: the span is the rubric and the remainder inside the parentheses is the
        text it governs. The source is inconsistent about which side of the span's opening tag
        the ``(`` falls on, so both shapes are accepted.

    Text outside any parentheses is ordinary liturgical text.
    """
    segments: list[Segment] = []
    cursor = 0

    def emit_paragraph(raw: str) -> None:
        cleaned = _strip_sentinels(raw)
        if cleaned:
            segments.append(Segment("paragraph", cleaned))

    while (span_start := text.find(RUBRIC_OPEN, cursor)) != -1:
        span_end = text.find(RUBRIC_CLOSE, span_start)
        if span_end == -1:
            break
        rubric = text[span_start + len(RUBRIC_OPEN) : span_end]

        # The '(' that opens this rubric's region: either immediately before the span, or the
        # first character inside it.
        before = text[cursor:span_start]
        open_at = None
        if before.rstrip().endswith("("):
            open_at = cursor + before.rstrip().rindex("(")
        elif rubric.lstrip().startswith("("):
            open_at = span_start + len(RUBRIC_OPEN) + rubric.index("(")

        close_at = _matching_paren(text, open_at) if open_at is not None else None

        if close_at is not None and close_at > span_end:
            emit_paragraph(text[cursor:open_at])
            conditional_text = _strip_sentinels(text[span_end + len(RUBRIC_CLOSE) : close_at])
            segments.append(
                Segment("instruction", _strip_sentinels(rubric).lstrip("(").strip(),
                        governs=bool(conditional_text))
            )
            if conditional_text:
                segments.append(Segment("paragraph", conditional_text, governed=True))
            cursor = close_at + 1
            continue

        # A plain rubric: the parentheses are the rubric's own punctuation. The source is
        # inconsistent about which side of the span's tags they fall on — "(recite aloud:)"
        # is written with the "(" outside the span and the ")" inside — so an opening bracket
        # just before the span belongs to the rubric and must not be left in the text.
        cut = open_at if open_at is not None and open_at < span_start else span_start
        emit_paragraph(text[cursor:cut])
        rubric_text = _strip_sentinels(rubric).strip("()").strip()
        if rubric_text:
            segments.append(Segment("instruction", rubric_text))
        cursor = span_end + len(RUBRIC_CLOSE)

    emit_paragraph(text[cursor:])
    return segments


def _append_english_segments(
    section: SectionContent,
    text: str,
    *,
    starts_paragraph: bool,
) -> None:
    first_in_row = starts_paragraph
    for segment in split_parenthetical_instructions(text):
        block = TextBlock(
            kind=segment.kind,
            english=segment.text,
            starts_paragraph=first_in_row,
            governs=segment.governs,
            governed=segment.governed,
        )
        first_in_row = False
        section.blocks.append(block)


def _append_body_row(section: SectionContent, row: CompilationRow) -> None:
    hebrew = row.hebrew.strip()
    english = row.english.strip()
    if hebrew:
        section.blocks.append(
            TextBlock(
                kind="paragraph",
                hebrew=hebrew,
                starts_paragraph=True,
            )
        )
    if english:
        _append_english_segments(section, english, starts_paragraph=True)


def _split_row_at_incipits(
    row: CompilationRow,
    prefixes: list[tuple[str, str]] = ROW_SPLIT_PREFIXES,
) -> list[CompilationRow]:
    """Split a row wherever a line after the first opens a new subsection.

    Needed because the compilation runs חסל סדור פסח and לשנה הבאה בירושלים together in one cell,
    while the print separates them by the two fourth-cup blessings. Hebrew and English lines
    correspond one to one in such a cell; refuse to guess if they ever stop doing so.
    """
    hebrew_lines = _non_empty_lines(row.hebrew)
    cuts = [
        index
        for index, line in enumerate(hebrew_lines)
        if index and match_subsection_by_incipit(line, prefixes)
    ]
    if not cuts:
        return [row]

    english_lines = _non_empty_lines(row.english)
    if english_lines and len(english_lines) != len(hebrew_lines):
        raise ValueError(
            f"cannot split a row with {len(hebrew_lines)} Hebrew and "
            f"{len(english_lines)} English lines: {hebrew_lines[0][:40]!r}"
        )

    parts: list[CompilationRow] = []
    for start, end in zip([0, *cuts], [*cuts, len(hebrew_lines)]):
        parts.append(
            CompilationRow(
                hebrew="\n".join(hebrew_lines[start:end]),
                english="\n".join(english_lines[start:end]) if english_lines else "",
                h3_title=row.h3_title,
                h3_boundary=row.h3_boundary and start == 0,
            )
        )
    return parts


def _resolve_slug(
    h3_parent: str | None,
    first_line: str,
    *,
    nirtzah_mode: bool,
) -> tuple[str | None, bool]:
    if first_line:
        for prefixes, nirtzah_only in (
            (NIRTZAH_SUBSECTION_PREFIXES, True),
            (MAGID_SUBSECTION_PREFIXES, False),
        ):
            slug = match_subsection_slug(first_line, prefixes)
            if slug and (not nirtzah_only or nirtzah_mode or slug in ("echad_mi_yodea", "chad_gadya")):
                if nirtzah_only:
                    return slug, True
                if h3_parent == "maggid":
                    return slug, nirtzah_mode

    if h3_parent == "maggid":
        return None, nirtzah_mode
    if h3_parent == "nirtzah" or nirtzah_mode:
        return None, True
    if h3_parent:
        return h3_parent, False
    return None, nirtzah_mode


def _get_section(contents: dict[str, SectionContent], slug: str) -> SectionContent:
    if slug not in contents:
        contents[slug] = SectionContent(slug=slug)
    return contents[slug]


def _scoped_prefixes(h3_parent: str | None, nirtzah_mode: bool) -> list[tuple[str, str]]:
    if nirtzah_mode:
        return NIRTZAH_SUBSECTION_PREFIXES
    if h3_parent in SCOPED_SUBSECTION_PREFIXES:
        return SCOPED_SUBSECTION_PREFIXES[h3_parent]
    if h3_parent == "maggid":
        return MAGID_SUBSECTION_PREFIXES
    return []


def build_section_contents(rows: list[CompilationRow]) -> dict[str, SectionContent]:
    contents: dict[str, SectionContent] = {}
    h3_parent: str | None = None
    current_slug: str | None = None
    nirtzah_mode = False

    expanded = [part for row in rows for part in _split_row_at_incipits(row)]

    for row in expanded:
        if row.h3_title and row.h3_title in H3_SLUGS:
            h3_parent = H3_SLUGS[row.h3_title]
            if h3_parent in INDEX_NODES:
                current_slug = h3_parent
                nirtzah_mode = h3_parent == "nirtzah"
            else:
                current_slug = h3_parent
                nirtzah_mode = False

        first_he = _first_line(row.hebrew)
        resolved = match_subsection_by_incipit(
            row.hebrew, _scoped_prefixes(h3_parent, nirtzah_mode)
        )
        if resolved:
            nirtzah_mode = nirtzah_mode or bool(
                match_subsection_slug(first_he, NIRTZAH_SUBSECTION_PREFIXES)
            )
        else:
            resolved, nirtzah_mode = _resolve_slug(
                h3_parent, first_he, nirtzah_mode=nirtzah_mode
            )
        if resolved:
            if h3_parent in INDEX_NODES and resolved != h3_parent:
                parent = _get_section(contents, h3_parent)
                if parent.children_at is None:
                    parent.children_at = len(parent.blocks)
            current_slug = resolved

        if not current_slug or not (row.hebrew.strip() or row.english.strip()):
            continue

        section = _get_section(contents, current_slug)

        if _is_section_heading_row(row):
            en_lines = _non_empty_lines(row.english)
            head_en = en_lines[0] if en_lines else row.english.strip()
            section.blocks.append(
                TextBlock(
                    kind="head",
                    hebrew=row.hebrew.strip(),
                    english=head_en,
                )
            )
            for extra in en_lines[1:]:
                _append_english_segments(section, extra, starts_paragraph=False)
            continue

        _append_body_row(section, row)

    return contents
