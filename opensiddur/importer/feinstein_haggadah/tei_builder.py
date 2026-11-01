"""TEI XML builders for haggadah projects."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from opensiddur.common.versification import WLC_PROJECT
from opensiddur.importer.feinstein_haggadah.conditionals import (
    Alternate,
    Conditional,
    ConditionalError,
    Inline,
    Paragraphs,
    Transclusion,
    condition_for_rubric,
    alternate_for,
    condition_markup,
    conditionals_for,
)
from opensiddur.importer.feinstein_haggadah.page_breaks import (
    PageBreak,
    PageBreakError,
    find_break_offset,
    pb_markup,
)
from opensiddur.importer.feinstein_haggadah.sections import (
    SectionContent,
    TextBlock,
    urn_for_section,
)
from opensiddur.importer.feinstein_haggadah.versify import BiblicalSection, PrintedPsalm
from opensiddur.importer.util.hebrew import normalize_hebrew
from opensiddur.importer.util.tei_project import (  # noqa: F401  (re-exported)
    PROJECT_SOURCE_BIBL_ID,
    tei_document,
    validate_and_write,
    validate_project_directory,
    xml_id_ref,
)
from opensiddur.importer.util.validation import validate

def _xml_escape(text: str) -> str:
    return html.escape(text, quote=False)


#: A page break milestone. See :func:`page_breaks.pb_markup`, which is the single place
#: ``tei:pb`` is serialised so the inline psalm transcriptions cannot drift from it.
_pb = pb_markup


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Return the (start, end) span in ``text`` of each rendered paragraph."""
    spans: list[tuple[int, int]] = []
    position = 0
    for part in text.split("\n\n"):
        stripped = part.strip()
        if stripped:
            lead = len(part) - len(part.lstrip())
            spans.append((position + lead, position + lead + len(stripped)))
        position += len(part) + 2
    return spans


def _splice(text: str, insertions: list[tuple[int, str] | tuple[int, str, int]]) -> str:
    """Escape ``text`` and splice markup in at the given offsets.

    Escaping is applied per fragment so that the offsets, which index the unescaped
    string, stay meaningful.

    An insertion may carry a third element, the number of source characters it consumes. A
    conditional marker replacing a parenthesis consumes the bracket it stands for, so the
    brackets do not survive alongside the markup that now expresses them.
    """
    out: list[str] = []
    cursor = 0
    for insertion in sorted(insertions):
        offset, markup = insertion[0], insertion[1]
        consumes = insertion[2] if len(insertion) > 2 else 0
        out.append(_xml_escape(text[cursor:offset]))
        out.append(markup)
        cursor = offset + consumes
    out.append(_xml_escape(text[cursor:]))
    return "".join(out).replace("\n", " ")


def conditional_markers(
    entry: Conditional,
    *,
    lang: str,
) -> tuple[str, str]:
    """The opening and closing markup for one conditional.

    The opening marker carries the condition and, where the sources give none of their own, an
    editorial note explaining when the passage applies. That note sits on the ``j:conditional``
    rather than inside its scope, so it is shown only when the condition cannot be decided. A
    passage the source brackets is ``type="marked"``.
    """
    note = entry.note_for(lang)
    note_markup = (
        f'<tei:note type="instruction">{_xml_escape(note)}</tei:note>' if note else ""
    )
    # Where the source brackets the passage, the markers stand for those brackets, and an
    # edition that cannot decide the condition prints them as the source did.
    scope = entry.scope_for(lang)
    marked = ' type="marked"' if scope is not None and scope.is_marked else ""
    opening = (
        f'<j:conditional xml:id="cond_{entry.cond_id}"{marked}>'
        f"{note_markup}{condition_markup(entry.condition)}"
        "</j:conditional>"
    )
    return opening, f'<j:endConditional target="#cond_{entry.cond_id}"/>'


def _alternate_xml(alternate: Alternate, text: str, slug: str) -> str:
    """Render a paragraph the source gives in two wordings as a ``tei:choice`` of options.

    Both wordings must be found in the source paragraph, so that a change in the text cannot
    leave a hand-written option silently standing in for wording that is no longer there.
    """
    for _, option in alternate.options:
        if normalize_hebrew(option) not in normalize_hebrew(text):
            raise ConditionalError(
                f"alternate wording {option!r} for {slug} paragraph "
                f"{alternate.paragraph} is not in the source text"
            )
    options = "".join(
        f'<j:option xml:lang="{lang}">{_xml_escape(option)}</j:option>'
        for lang, option in alternate.options
    )
    return f"<tei:p><tei:choice>{options}</tei:choice></tei:p>"


def _rubric_markup(entry: Conditional, lang: str) -> str:
    """A rubric to place inside the scope, where the source supplies none.

    ``schema/JLPTEI-3.md`` requires an instruction that tells the reader a text is conditional
    to sit inside the text it controls, so this is emitted after the opening marker.
    """
    rubric = entry.rubric_for(lang)
    return f'<tei:note type="instruction">{_xml_escape(rubric)}</tei:note>' if rubric else ""


def _paragraph_xml(
    text: str,
    breaks: list[tuple[int, str] | tuple[int, str, int]] | None = None,
) -> str:
    """Render ``text`` as tei:p elements, placing page breaks at the given offsets.

    ``tei:pb`` belongs to ``tei_model.global`` and so is valid inside ``tei:p``: a page
    turn falling mid-paragraph is marked in place rather than splitting the paragraph.

    A break always attaches to the text that follows it, since that is the text the new
    page carries. One that falls on a paragraph boundary, or in the whitespace between
    paragraphs, therefore opens the next paragraph rather than trailing the previous one.
    Only a break past the end of all text is emitted as a sibling.
    """
    breaks = sorted(breaks or [])
    spans = _paragraph_spans(text)
    if not spans and text.strip():
        spans = [(0, len(text))]

    assigned: dict[int, list[tuple[int, str, int]]] = {}
    trailing: list[str] = []
    for entry in breaks:
        offset, markup = entry[0], entry[1]
        consumes = entry[2] if len(entry) > 2 else 0
        index = next((i for i, (_, end) in enumerate(spans) if offset < end), None)
        if index is None:
            trailing.append(markup)
            continue
        start, _ = spans[index]
        assigned.setdefault(index, []).append((max(0, offset - start), markup, consumes))

    parts = [
        f"<tei:p>{_splice(text[start:end], assigned.get(index, []))}</tei:p>"
        for index, (start, end) in enumerate(spans)
    ]
    parts.extend(trailing)
    return "\n".join(parts)


def _block_texts(blocks: list[TextBlock], *, lang: str) -> list[str]:
    text_attr = "hebrew" if lang == "he" else "english"
    return [getattr(block, text_attr).strip() for block in blocks]


@dataclass(frozen=True)
class InlineAnchor:
    """An element to splice into a section's text at a point located by its wording.

    Page breaks and verse milestones are the same problem — a marker belonging at an exact
    spot in a run of text — so they share one mechanism. ``before_text``/``after_text`` are
    the words on either side of the point; both ``None`` means the very start of the section.
    ``label`` names the anchor in error messages.
    """

    markup: str
    label: str
    before_text: str | None = None
    after_text: str | None = None
    #: A bracket the anchor stands in place of. The anchor is moved onto that bracket and
    #: swallows it, since the markup now expresses what the bracket meant.
    replaces_bracket: str | None = None
    #: Whether the anchor closes on the words before it: placed before the space that ends
    #: them, not after it, so that a closing bracket hugs the words it closes.
    snug: bool = False

    @property
    def at_section_start(self) -> bool:
        return self.before_text is None and self.after_text is None


def verse_anchors(section: BiblicalSection) -> list[InlineAnchor]:
    """Chapter and verse milestones for a section that is a complete biblical unit.

    The canonical URNs go on the milestones, not on ``tei:div/@corresp``, exactly as
    ``project/tanakh-wlc-he/psalms.xml`` does: the div keeps its haggadah identity for transclusion while
    the milestones are what alignment against WLC and JPS1917 keys off.
    """
    reference = f"{section.book} {section.chapter}"
    anchors = [
        InlineAnchor(
            markup=(
                f'<tei:milestone unit="chapter" n="{section.chapter}" '
                f'corresp="{section.chapter_urn()}"/>'
            ),
            label=reference,
        )
    ]
    anchors.extend(
        InlineAnchor(
            markup=(
                f'<tei:milestone unit="verse" n="{verse.n}" '
                f'corresp="{section.verse_urn(verse.n)}"/>'
            ),
            label=f"{reference}:{verse.n}",
            before_text=verse.before_text,
            after_text=verse.after_text,
        )
        for verse in section.verses
    )
    return anchors


def page_break_anchors(breaks: list[PageBreak]) -> list[InlineAnchor]:
    return [
        InlineAnchor(
            markup=_pb(entry.page),
            label=f"page {entry.page}",
            before_text=entry.before_text,
            after_text=entry.after_text,
        )
        for entry in breaks
    ]


def _resolve_insertions(
    slug: str,
    texts: list[str],
    anchors: list[InlineAnchor],
    *,
    lang: str = "he",
) -> dict[int, list[tuple[int, str, int]]]:
    """Map each anchored insertion to (block index -> [(offset, markup, consumes)]).

    The section's blocks are matched as one continuous run of text, so an anchor is found
    even when it falls exactly on a boundary between two blocks.
    """
    if not anchors:
        return {}

    joined = "".join(texts)
    starts: list[int] = []
    position = 0
    for text in texts:
        starts.append(position)
        position += len(text)

    resolved: dict[int, list[tuple[int, str, int]]] = {}
    for anchor in anchors:
        try:
            offset = find_break_offset(
                joined, anchor.before_text or "", anchor.after_text or "", lang=lang
            )
        except PageBreakError as error:
            raise PageBreakError(f"{anchor.label} in section {slug}: {error}") from error
        consumes = 0
        if anchor.replaces_bracket:
            offset, consumes = _bracket_offset(
                joined, offset, anchor.replaces_bracket, anchor.label, slug
            )
        elif anchor.snug:
            while offset > 0 and joined[offset - 1].isspace():
                offset -= 1
        index = max(i for i, start in enumerate(starts) if start <= offset)
        resolved.setdefault(index, []).append(
            (offset - starts[index], anchor.markup, consumes)
        )
    return resolved


def _bracket_offset(
    text: str,
    offset: int,
    bracket: str,
    label: str,
    slug: str,
) -> tuple[int, int]:
    """Move an anchor back onto the bracket it stands in place of.

    Matching ignores punctuation, so an anchor between two words lands on the first character
    of the word that follows — past the bracket, not on it. The marker belongs where the
    bracket is, and takes it with it.

    Whitespace and bidi format characters are skipped on the way back: the Hebrew source
    places a right-to-left mark after a closing bracket to keep the punctuation rendering on
    the correct side.
    """
    index = offset - 1
    while index >= 0 and (text[index].isspace() or unicodedata.category(text[index]) == "Cf"):
        index -= 1
    if index < 0 or text[index] != bracket:
        raise ConditionalError(
            f"{label} in section {slug}: expected {bracket!r} immediately before the "
            f"anchored point, found {text[max(0, offset - 12):offset]!r}"
        )
    return index, 1


def inline_conditional_anchors(
    slug: str,
    entries: list[Conditional],
    *,
    lang: str,
) -> list[InlineAnchor]:
    """Marker anchors for the conditionals of ``slug`` that fall inside a paragraph.

    Each contributes two anchors, one per marker. Both are located by the words on either side
    exactly as a page break is, and each swallows the bracket it replaces.
    """
    anchors: list[InlineAnchor] = []
    for entry in entries:
        scope = entry.scope_for(lang)
        if not isinstance(scope, Inline):
            continue
        opening, closing = conditional_markers(entry, lang=lang)
        anchors.append(
            InlineAnchor(
                markup=opening + _rubric_markup(entry, lang),
                label=f"conditional {entry.cond_id} (start)",
                before_text=scope.before_text,
                after_text=scope.after_text,
                replaces_bracket="(" if scope.bracketed else None,
            )
        )
        anchors.append(
            InlineAnchor(
                markup=closing,
                label=f"conditional {entry.cond_id} (end)",
                before_text=scope.end_before_text,
                after_text=scope.end_after_text,
                replaces_bracket=")" if scope.bracketed else None,
                snug=not scope.bracketed,
            )
        )
    return anchors


def _source_marked_ids(
    entries: list[Conditional],
    *,
    lang: str,
) -> dict[str, list[str]]:
    """Table ids for the conditionals this language's source marks with its own rubrics.

    Such an entry declares no scope for the language, because the source already says where the
    passage begins and ends. It still needs its identity from the table: both projects must
    name the same passage by the same ``xml:id`` or the two cannot be aligned. Entries are
    queued per condition and consumed in document order, which is the order the table lists
    them in and the order the source prints them.
    """
    queues: dict[str, list[str]] = {}
    for entry in entries:
        if entry.scope_for(lang) is None:
            queues.setdefault(condition_markup(entry.condition), []).append(entry.cond_id)
    return queues


def _paragraph_conditionals(
    entries: list[Conditional],
    *,
    lang: str,
) -> tuple[dict[int, list[Conditional]], dict[int, list[Conditional]]]:
    """Conditionals opening before, and closing after, each numbered paragraph."""
    opens: dict[int, list[Conditional]] = {}
    closes: dict[int, list[Conditional]] = {}
    for entry in entries:
        scope = entry.scope_for(lang)
        if not isinstance(scope, Paragraphs):
            continue
        opens.setdefault(scope.first, []).append(entry)
        closes.setdefault(scope.through, []).append(entry)
    return opens, closes


def _bracketed_paragraphs(entries: list[Conditional], *, lang: str) -> set[int]:
    """Paragraph numbers the source wraps in brackets that the markers now replace."""
    return {
        number
        for entry in entries
        if isinstance(scope := entry.scope_for(lang), Paragraphs) and scope.bracketed
        for number in range(scope.first, scope.through + 1)
    }


def _unbracket(text: str) -> str:
    """Drop the brackets around a wholly parenthesised paragraph."""
    stripped = text.strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        return stripped[1:-1].strip()
    return text


def _render_blocks(
    slug: str,
    blocks: list[TextBlock],
    *,
    lang: str,
    anchors: list[InlineAnchor] | None = None,
    children_markup: str = "",
    children_at: int | None = None,
    number_paragraphs: bool = True,
    entries: list[Conditional] | None = None,
) -> str:
    parts: list[str] = []
    paragraph_number = 0
    texts = _block_texts(blocks, lang=lang)
    resolved = _resolve_insertions(slug, texts, anchors or [], lang=lang)
    entries = entries or []
    opens, closes = _paragraph_conditionals(entries, lang=lang)
    source_marked = _source_marked_ids(entries, lang=lang)
    bracketed = _bracketed_paragraphs(entries, lang=lang)
    pending_close: list[str] = []
    if children_at is None and children_markup:
        children_at = len(blocks)
    for index, (block, text) in enumerate(zip(blocks, texts)):
        if index == children_at and children_markup:
            parts.append(children_markup)
        block_breaks = resolved.get(index, [])
        if block.kind == "head":
            if text:
                parts.append(f"<tei:head>{_splice(text, block_breaks)}</tei:head>")
            continue
        if not text:
            parts.extend(markup for _, markup, _consumes in sorted(block_breaks))
            continue
        if block.starts_paragraph and number_paragraphs:
            # A paragraph-scoped conditional closes before the milestone of the paragraph
            # after its range, so that the marker pair brackets whole paragraphs.
            parts.extend(pending_close)
            pending_close = []
            paragraph_number += 1
            for entry in opens.get(paragraph_number, []):
                opening, closing = conditional_markers(entry, lang=lang)
                parts.append(opening)
                rubric = _rubric_markup(entry, lang)
                if rubric:
                    parts.append(rubric)
            for entry in closes.get(paragraph_number, []):
                pending_close.insert(0, conditional_markers(entry, lang=lang)[1])
            urn = urn_for_section(slug, paragraph=paragraph_number)
            corresp = f' corresp="{urn}"' if urn else ""
            parts.append(f'<tei:milestone unit="paragraph" n="{paragraph_number}"{corresp}/>')
        if block.kind == "instruction":
            note = f'<tei:note type="instruction">{_splice(text, block_breaks)}</tei:note>'
            if block.governs:
                # The source marked this rubric as governing the text that follows it. The
                # rubric goes inside the scope: JLPTEI-3.md requires an instruction that tells
                # the reader a text is conditional to sit inside the text it controls.
                condition = condition_for_rubric(block.english, slug)
                queue = source_marked.get(condition)
                if not queue:
                    raise ConditionalError(
                        f"section {slug}: the source marks a conditional with rubric "
                        f"{block.english!r}, but the table has no entry for that condition "
                        f"left to name it. Both projects must name a passage alike."
                    )
                cond_id = queue.pop(0)
                # Governing rubrics are found inside the source's parentheses, which set the
                # passage off: the scope is marked.
                parts.append(
                    f'<j:conditional xml:id="cond_{cond_id}" type="marked">{condition}'
                    "</j:conditional>"
                )
                parts.append(note)
                pending_close.insert(0, f'<j:endConditional target="#cond_{cond_id}"/>')
                continue
            parts.append(note)
            continue
        alternate = alternate_for(slug, lang, paragraph_number)
        if alternate is not None:
            parts.append(_alternate_xml(alternate, text, slug))
        elif paragraph_number in bracketed and not block_breaks:
            parts.append(_paragraph_xml(_unbracket(text)))
        else:
            parts.append(_paragraph_xml(text, block_breaks))
        if block.governed:
            parts.extend(pending_close)
            pending_close = []
    parts.extend(pending_close)
    if children_markup and children_at is not None and children_at >= len(blocks):
        parts.append(children_markup)
    return "\n".join(parts)


def _transclusion_markup(
    child: str,
    entries: list[Conditional],
    *,
    lang: str,
) -> str:
    """A child's transclusion, wrapped in conditional markers if its inclusion is conditional.

    A whole section is either transcluded or it is not, so a section-wide condition belongs
    here rather than inside the child, which remains an unconditional document of its own.
    """
    transclude = f'<j:transclude type="external" target="{urn_for_section(child)}"/>'
    for entry in entries:
        scope = entry.scope_for(lang)
        if isinstance(scope, Transclusion) and scope.child_slug == child:
            opening, closing = conditional_markers(entry, lang=lang)
            rubric = _rubric_markup(entry, lang)
            return f"{opening}\n{rubric}\n{transclude}\n{closing}" if rubric else (
                f"{opening}\n{transclude}\n{closing}"
            )
    return transclude


def section_body(
    slug: str,
    section: SectionContent | None,
    *,
    lang: str,
    anchors: list[InlineAnchor] | None = None,
    child_slugs: list[str] | None = None,
    number_paragraphs: bool = True,
) -> str:
    """Render one section's ``tei:body``.

    Transclusions go where the extracted material stood in the source, taken from
    ``section.children_at``, so a section can hold text both before and after its children —
    Birkat HaMazon transcludes Psalm 126 and then continues for another thirty paragraphs.
    """
    urn = urn_for_section(slug)
    entries = conditionals_for(slug)
    anchors = (anchors or []) + inline_conditional_anchors(slug, entries, lang=lang)
    opening = [anchor for anchor in anchors if anchor.at_section_start]
    anchored = [anchor for anchor in anchors if not anchor.at_section_start]
    leading = "".join(f"    {anchor.markup}\n" for anchor in opening)

    def _indent(rendered: str) -> str:
        return f"    {rendered.replace(chr(10), chr(10) + '    ')}\n" if rendered else ""

    transcludes = "\n".join(
        _transclusion_markup(child, entries, lang=lang) for child in child_slugs or []
    )

    if section and section.blocks:
        content = _indent(
            _render_blocks(
                slug,
                section.blocks,
                lang=lang,
                anchors=anchored,
                children_markup=transcludes,
                children_at=section.children_at,
                number_paragraphs=number_paragraphs,
                entries=entries,
            )
        )
    else:
        if anchored:
            raise PageBreakError(
                f"section {slug} has anchored insertions but no content: "
                + ", ".join(anchor.label for anchor in anchored)
            )
        content = _indent(transcludes)

    return f"""<tei:body>
  <tei:div corresp="{urn}">
{leading}{content}  </tei:div>
</tei:body>"""


def printed_verse_body(psalm: PrintedPsalm) -> str:
    """Render the ``tei:body`` of a psalm transcribed from the 1822 print.

    Same shape as :func:`section_body` produces for these sections — the div keeps its haggadah
    ``@corresp`` for transclusion while the canonical biblical URNs sit on the milestones — but
    the verse divisions come from the transcription itself, so nothing has to be matched against
    the text. The verse fragments are emitted unescaped: they are checked-in markup, not source
    text, and may contain only ``j:divineName`` and ``tei:pb``.
    """
    verses = dict(sorted(psalm.verses.items()))
    first = min(verses)

    def _verse(n: int) -> str:
        return f'<tei:milestone unit="verse" n="{n}" corresp="{psalm.verse_urn(n)}"/>'

    # Markers that precede the psalm's first word stand as siblings of the paragraph, matching
    # what the anchor-driven path emits for a section-opening anchor. A folio opening the psalm
    # comes first, so the page turn is marked before the chapter it begins.
    leading = []
    opening_pb = re.match(r"<tei:pb [^>]*/>", verses[first])
    if opening_pb:
        leading.append(opening_pb.group())
        verses[first] = verses[first][opening_pb.end() :]
    leading.append(
        f'<tei:milestone unit="chapter" n="{psalm.chapter}" corresp="{psalm.chapter_urn()}"/>'
    )
    leading.append(_verse(first))

    body = verses.pop(first) + "".join(
        f" {_verse(n)}{text}" for n, text in verses.items()
    )
    prefix = "".join(f"    {markup}\n" for markup in leading)
    return f"""<tei:body>
  <tei:div corresp="{urn_for_section(psalm.section)}">
{prefix}    <tei:p>{body}</tei:p>
  </tei:div>
</tei:body>"""


def content_body(
    slug: str,
    section: SectionContent | None,
    *,
    lang: str,
    anchors: list[InlineAnchor] | None = None,
    number_paragraphs: bool = True,
) -> str:
    return section_body(
        slug, section, lang=lang, anchors=anchors, number_paragraphs=number_paragraphs
    )


def index_body(
    index_slug: str,
    child_slugs: list[str],
    section: SectionContent | None = None,
    *,
    lang: str,
    anchors: list[InlineAnchor] | None = None,
) -> str:
    return section_body(
        index_slug,
        section,
        lang=lang,
        anchors=anchors,
        child_slugs=child_slugs,
    )


def validate_header_stub(stub_name: str, *, lang: str) -> None:
    """Validate a header stub as part of a well-formed TEI document."""
    header = read_header_stub(stub_name)
    sample = tei_document(header, index_body("index", ["pre_seder"], lang=lang), lang=lang)
    is_valid, errors = validate(sample)
    if not is_valid:
        raise RuntimeError(f"JLPTEI validation failed for header stub {stub_name}: {errors}")


def read_header_stub(stub_name: str) -> str:
    stub_path = Path(__file__).parent / stub_name
    return stub_path.read_text(encoding="utf-8").strip()


_LEADING_COMMENT_RE = re.compile(r"\A(?:\s*<!--.*?-->)+\s*", re.DOTALL)


def read_front_stub(stub_name: str) -> str:
    """Read a curated ``tei:front`` fragment (a transcribed title page).

    Same contract as :func:`read_header_stub`: the stub is a standalone, namespace-declaring
    fragment spliced into a document by :func:`tei_document`. Leading comments are notes to
    whoever maintains the stub and are dropped — the compiler is an lxml identity transform
    over elements and raises on a comment node, so no comment may reach the project data.
    """
    return _LEADING_COMMENT_RE.sub("", read_header_stub(stub_name)).strip()


def require_project_source_bibl_id(header_xml: str, *, header_stub: str) -> None:
    """Fail fast if the index header stub doesn't define the id every citation pointer names.

    ``citation_bibl``/``project_citation_bibl`` always point at
    ``{PROJECT_SOURCE_BIBL_ID}`` in the project index; if the stub never defines that id on a
    ``tei:bibl``, every citation in the project silently becomes a dangling pointer.
    """
    if f'xml:id="{PROJECT_SOURCE_BIBL_ID}"' not in header_xml:
        raise RuntimeError(
            f'{header_stub} has no tei:bibl xml:id="{PROJECT_SOURCE_BIBL_ID}"; '
            "citation_bibl()/project_citation_bibl() point at that id and would produce "
            "dangling references"
        )


def citation_bibl(project_id: str, from_page: str, to_page: str) -> str:
    """A per-document citation pointing at the project bibliography, scoped to its pages.

    See ``schema/JLPTEI-3.md``: the pointer is a file/fragment reference to the
    ``project_source_bibl`` entry in the project's index document.
    """
    target = xml_id_ref(project_id, "index", PROJECT_SOURCE_BIBL_ID)
    return (
        "<tei:bibl>"
        f'<tei:ptr target="{target}"/>'
        f'<tei:biblScope unit="pages" from="{from_page}" to="{to_page}"/>'
        "</tei:bibl>"
    )


def transcription_bibl(section: BiblicalSection) -> str:
    """Record that a biblical section's pointed text came from WLC, not the 1822 print.

    The 1822 edition is still the source this document represents — it supplies the wording's
    place, its pagination and its page range — but the vocalized text was taken from the
    Westminster Leningrad Codex, and a reader collating against the facsimile needs to know that.

    This is now true of ``psalm_126`` alone. The psalms the 1822 haggadah actually prints are
    transcribed from the facsimile (see ``heidenheim_psalms_1822.json``) and cite only the print,
    so ``convert_project`` does not emit this bibl for them.
    """
    return (
        "<tei:bibl>"
        f'<tei:ptr target="urn:x-opensiddur:text:bible:{section.book}@{WLC_PROJECT}"/>'
        f'<tei:biblScope unit="chapter" from="{section.chapter}" to="{section.chapter}"/>'
        "</tei:bibl>"
    )


def header_with_bibls(header_xml: str, bibls: list[str]) -> str:
    """Append bibls to a header's sourceDesc.

    Indentation is left to ``prettify_xml``, which reformats the whole document on write.
    """
    closing = "</tei:sourceDesc>"
    if closing not in header_xml:
        raise ValueError("header has no tei:sourceDesc to add a bibl to")
    return header_xml.replace(closing, "".join(bibls) + closing, 1)


def project_citation_bibl(
    project_id: str,
    *,
    from_page: str | None = None,
    to_page: str | None = None,
) -> str:
    """This document's whole ``sourceDesc`` when it is not the project index: a pointer to
    the index's bibliography, scoped to the pages this document occupies where they are
    known."""
    if from_page and to_page:
        return citation_bibl(project_id, from_page, to_page)
    target = xml_id_ref(project_id, "index", PROJECT_SOURCE_BIBL_ID)
    return f'<tei:bibl><tei:ptr target="{target}"/></tei:bibl>'


_SOURCE_DESC_RE = re.compile(
    r"<tei:sourceDesc\b[^>]*>.*?</tei:sourceDesc>", re.DOTALL
)


def header_with_only_bibls(header_xml: str, bibls: list[str]) -> str:
    """Replace a header's ``sourceDesc`` with ``bibls``.

    Per ``schema/JLPTEI-3.md``, the full bibliographic citations of a project's sources live
    in the project index alone; every other document cites them by pointer. Appending to the
    project header (:func:`header_with_bibls`) would copy those citations — and the
    ``xml:id``s they are addressed by — into each of the hundred-odd files that share it.
    """
    if not _SOURCE_DESC_RE.search(header_xml):
        raise ValueError("header has no tei:sourceDesc to replace")
    replacement = "<tei:sourceDesc>" + "".join(bibls) + "</tei:sourceDesc>"
    return _SOURCE_DESC_RE.sub(lambda _: replacement, header_xml, count=1)


def header_with_page_scope(
    header_xml: str,
    *,
    project_id: str,
    from_page: str,
    to_page: str,
) -> str:
    """Append a page-scoped citation bibl to a header's sourceDesc."""
    return header_with_bibls(header_xml, [citation_bibl(project_id, from_page, to_page)])


def minimal_index_header(
    title: str,
    *,
    project_id: str,
    urn_suffix: str,
    lang: str = "he",
    from_page: str | None = None,
    to_page: str | None = None,
) -> str:
    bibl = project_citation_bibl(project_id, from_page=from_page, to_page=to_page)
    return f"""<tei:teiHeader xmlns:tei="http://www.tei-c.org/ns/1.0">
  <tei:fileDesc>
    <tei:titleStmt>
      <tei:title type="main" xml:lang="{lang}">{_xml_escape(title)}</tei:title>
    </tei:titleStmt>
    <tei:publicationStmt>
      <tei:distributor>
        <tei:ref target="http://opensiddur.org">Open Siddur Project</tei:ref>
      </tei:distributor>
      <tei:idno type="urn">urn:x-opensiddur:text:haggadah:{urn_suffix}@{project_id}</tei:idno>
    </tei:publicationStmt>
    <tei:sourceDesc>
      {bibl}
    </tei:sourceDesc>
  </tei:fileDesc>
</tei:teiHeader>"""
