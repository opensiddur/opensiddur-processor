"""Build the JLPTEI of one opensiddur.org post in one language.

Each post and language is a project, named by :mod:`naming`, of two files:

- ``index.xml``: the full header, with the source ``tei:bibl``; the post's introduction and
  notes as front matter, in the project whose language they are written in; and a body that
  transcludes the text.
- ``<urn>.xml``: the text, named from the post's URN, one ``tei:div`` whose ``corresp`` is
  that URN. Each table
  row opens a ``tei:milestone`` whose ``corresp`` is the same in every language of the post,
  which is what sets the languages side by side.

The output depends only on its input, never on the clock, so converting an unchanged post
again gives identical files.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from opensiddur.importer.opensiddur_org.contributors import Credit, Credits
from opensiddur.importer.opensiddur_org.languages import DEFAULT_SCRIPT, ISO639_1
from opensiddur.importer.opensiddur_org.licences import LicenceDecision
from opensiddur.importer.opensiddur_org.parse_post import (
    Block,
    Cell,
    Column,
    FootnoteRef,
    Line,
    Node,
    Post,
    Span,
    Text,
    node_text,
    transcluded_urn,
)
from opensiddur.importer.opensiddur_org.scope import (
    column_mode,
    imported_columns,
    is_heading_row,
    table_views,
)
from opensiddur.importer.opensiddur_org.urns import PostUrns
from opensiddur.importer.util.tei_project import PROJECT_SOURCE_BIBL_ID, tei_document, xml_id_ref

SITE_URL = "https://opensiddur.org"
SITE_NAME = "Open Siddur Project"
UPSTREAM_REPOSITORY = "https://github.com/aharonium/opensiddur.org"

#: Inline span kinds -> (opening tag, closing tag).
SPAN_MARKUP: dict[str, tuple[str, str]] = {
    "divine": ("<j:divineName>", "</j:divineName>"),
    "instruction": ('<tei:note type="instruction">', "</tei:note>"),
    "acrostic": ('<tei:seg type="acrostic">', "</tei:seg>"),
    "citation": ("<tei:bibl>", "</tei:bibl>"),
    "italic": ('<tei:hi rend="italic">', "</tei:hi>"),
    "bold": ('<tei:hi rend="bold">', "</tei:hi>"),
    "superscript": ('<tei:hi rend="superscript">', "</tei:hi>"),
    "subscript": ('<tei:hi rend="subscript">', "</tei:hi>"),
    # From colours (see post_decisions.yaml).
    "quotation": ('<tei:seg type="quotation">', "</tei:seg>"),
    "choice": ("<tei:choice>", "</tei:choice>"),
    "written": ("<j:written>", "</j:written>"),
    "read": ("<j:read>", "</j:read>"),
}

#: Column roles whose cells are notes on the column beside them.
NOTE_ROLES = frozenset({"commentary", "description"})

#: Span kinds that may not nest inside themselves or a note, and are dropped there.
_NOTE_UNSAFE = frozenset({"instruction"})


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def attr(text: str) -> str:
    return html.escape(text, quote=True)


def text_file_stem(urn: str) -> str:
    """The text file's name: the path of the post's URN, its components joined by ``_``, so
    that the file and the URN spell the text's name the same way."""
    path = urn.split("#", 1)[0].split("@", 1)[0].split(":", 4)[-1]
    return "_".join(component for component in path.split("/") if component)


#: Scripts a title part may be written in, other than Latin, and the tag it is given. The
#: site sets titles "Hebrew | English"; a part in another script names no language we can
#: tell, only its script.
TITLE_SCRIPTS: tuple[tuple[str, str], ...] = (
    ("[\u0590-\u05FF]", "he"),
    ("[\u0600-\u06FF]", "und-Arab"),
    ("[\u0400-\u04FF]", "und-Cyrl"),
    ("[\u0370-\u03FF]", "und-Grek"),
)


def _script_language(text: str) -> str:
    """The language a title part is taken to be in: "he" in Hebrew letters, "en" in Latin."""
    for pattern, lang in TITLE_SCRIPTS:
        if re.search(pattern, text):
            return lang
    return "en"


def _is_latin(lang: str) -> bool:
    primary, *subtags = lang.split("-")
    if subtags:
        return "Latn" in subtags
    iso639_3 = next((k for k, v in ISO639_1.items() if v == primary), primary)
    return DEFAULT_SCRIPT.get(iso639_3, "Latn") == "Latn"


def titles_by_language(post: Post) -> list[tuple[str, str]]:
    """The title's parts with the language each is written in."""
    return [(_script_language(title), title) for title in post.titles]


# --------------------------------------------------------------------------------------------
# Inline content
# --------------------------------------------------------------------------------------------


@dataclass
class _Notes:
    """What a document collects while its text is rendered: the footnotes it anchors, and the
    conditions it numbers. ``condition_base`` names the text's own variants:
    ``urn:x-opensiddur:condition:<the text URN's path>``."""

    entries: list[tuple[int, tuple[Node, ...]]]
    condition_base: str = ""
    conditions: int = 0

    def anchor(self, ref: FootnoteRef) -> str:
        self.entries.append((ref.number, ref.note))
        return f'<tei:anchor xml:id="note_{ref.number}"/>'

    def conditional(self, kind: str, inner: str) -> str:
        """``inner`` as the scope of a condition, set off as the source marks it (by colour).
        When no setting decides the condition, both readings stand, set off."""
        self.conditions += 1
        cond_id = f"cond_{self.conditions}"
        return (f'<j:conditional xml:id="{cond_id}" type="marked">{condition_fs(kind, self.condition_base)}'
                f'</j:conditional>{inner}<j:endConditional target="#{cond_id}"/>')




def condition_base(text_urn: str) -> str:
    """The condition URNs of a text's variants: ``…:text:prayer:x`` -> ``…:condition:prayer:x``."""
    return "urn:x-opensiddur:condition:" + text_urn.split("urn:x-opensiddur:text:", 1)[-1]


def condition_fs(kind: str, base: str) -> str:
    """The feature structure a colour's condition tests: ``variant:amended`` -> the text's
    variant ``…/amended``, true (``:original`` makes it false); ``gender:female`` and
    ``rite:ashkenaz`` test the features JLPTEI has for them."""
    family, name, *rest = kind.split(":") + [""]
    if family == "gender":
        return (f'<tei:fs type="opensiddur:person"><tei:f name="gender">'
                f'<tei:symbol value="{attr(name)}"/></tei:f></tei:fs>')
    if family == "rite":
        return f'<tei:fs type="opensiddur:rite"><tei:f name="{attr(name)}"><tei:binary value="true"/></tei:f></tei:fs>'
    value = "false" if "original" in rest else "true"
    return (f'<tei:fs type="opensiddur:variant"><tei:f name="{attr(base)}/{attr(name)}">'
            f'<tei:binary value="{value}"/></tei:f></tei:fs>')


def _render_span(kind: str, inner: str, notes: _Notes | None) -> str:
    """A span whose kind has a particular after a colon (see ``parse_post.colour_kind``)."""
    family, _, particular = kind.partition(":")
    if family == "lang":
        return f'<tei:seg xml:lang="{attr(particular)}">{inner}</tei:seg>'
    if family in ("supplied", "cantillation"):
        # Who supplied the words ("scholars", "author"), or the melody to read in ("job").
        subtype = f' subtype="{attr(particular)}"' if particular else ""
        return f'<tei:seg type="{family}"{subtype}>{inner}</tei:seg>'
    if family in ("variant", "gender", "rite", "concealed") and notes is not None:
        return notes.conditional(kind if family != "concealed" else "variant:concealed", inner)
    if family in ("variant", "gender", "rite", "concealed"):
        return inner  # in a note: the condition belongs to the text
    raise ValueError(f"no encoding for a span of kind {kind!r}")


def render_inline(nodes: tuple[Node, ...] | Line, notes: _Notes | None, *, in_note: bool = False) -> str:
    out: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            out.append(esc(node.text))
        elif isinstance(node, FootnoteRef):
            if notes is not None and not in_note:
                out.append(notes.anchor(node))
        elif isinstance(node, Span):
            inner = render_inline(node.children, notes, in_note=in_note or node.kind == "instruction")
            if in_note and node.kind in _NOTE_UNSAFE:
                out.append(inner)
                continue
            if node.kind not in SPAN_MARKUP:
                out.append(_render_span(node.kind, inner, None if in_note else notes))
                continue
            opening, closing = SPAN_MARKUP[node.kind]
            out.append(f"{opening}{inner}{closing}")
            if node.kind == "instruction" and notes is not None and not in_note:
                # A note cannot hold an anchor for another note; it follows the instruction.
                out.extend(notes.anchor(ref) for ref in _footnote_refs(node.children))
    return "".join(out)


def _footnote_refs(nodes: tuple[Node, ...]) -> list[FootnoteRef]:
    found: list[FootnoteRef] = []
    for node in nodes:
        if isinstance(node, FootnoteRef):
            found.append(node)
        elif isinstance(node, Span):
            found.extend(_footnote_refs(node.children))
    return found


def _lang_attr(cell_lang: str | None, document_lang: str) -> str:
    if cell_lang and cell_lang != document_lang and cell_lang.split("-")[0] != "und":
        return f' xml:lang="{attr(cell_lang)}"'
    return ""


def render_block(block: Block, notes: _Notes, lang_attr: str = "") -> str:
    if block.kind == "stanza":
        lines = "".join(f"<tei:l>{render_inline(line, notes)}</tei:l>" for line in block.lines)
        return f"<tei:lg{lang_attr}>{lines}</tei:lg>"
    if block.kind == "paragraph":
        body = "<tei:lb/>".join(render_inline(line, notes) for line in block.lines)
        return f"<tei:p{lang_attr}>{body}</tei:p>"
    raise ValueError(f"a {block.kind} block is not rendered as text")


# --------------------------------------------------------------------------------------------
# The text document
# --------------------------------------------------------------------------------------------


def row_numbers(post: Post) -> dict[int, int]:
    """Row index -> its number in the URNs: rows are numbered from 1, headings skipped."""
    numbers: dict[int, int] = {}
    n = 0
    for index in range(len(post.rows)):
        if is_heading_row(post, index):
            continue
        n += 1
        numbers[index] = n
    return numbers


def hosted_notes(post: Post, column_index: int) -> list[tuple[int, Column]]:
    """The commentary and description columns whose cells are notes on ``column_index``: each
    belongs to the nearest column with text to its left, or else to its right."""
    texts = [index for index, _ in imported_columns(post)]
    hosted = []
    for index, column in enumerate(post.columns):
        if column.role not in NOTE_ROLES or not texts:
            continue
        left = [i for i in texts if i < index]
        host = left[-1] if left else min(texts)
        if host == column_index:
            hosted.append((index, column))
    return hosted


def _note(kind: str, cell: Cell, notes: _Notes, lang: str) -> str:
    """A cell of a commentary or description column, as a note. A description is a rubric,
    set inline like the source's ("Reader:"); a commentary may run to paragraphs."""
    lines = ["<tei:lb/>".join(render_inline(line, notes, in_note=True) for line in block.lines)
             for block in cell.blocks]
    body = "<tei:lb/>".join(lines) if kind == "description" else "".join(f"<tei:p>{p}</tei:p>" for p in lines)
    return f'<tei:note type="{kind}"{_lang_attr(cell.lang, lang)}>{body}</tei:note>'


def text_body(post: Post, column_index: int, column: Column, urns: PostUrns) -> tuple[str, str]:
    """The body ``tei:div`` of one column, and its ``tei:standOff`` (or "").

    A heading row opens a section in every language; a heading inside a cell opens one in its
    column's language only. Either way the row milestones are untouched, so the languages
    stay aligned.
    """
    notes = _Notes([], condition_base=condition_base(urns.urn))
    unit = "paragraph" if column_mode(post, column_index) == {"paragraph"} else "stanza"
    numbers = row_numbers(post)
    hosted = hosted_notes(post, column_index)
    parts: list[str] = [f'<tei:div corresp="{attr(urns.urn)}">']
    head = next((title for lang, title in titles_by_language(post) if lang == column.lang), "")
    if head:
        parts.append(f"<tei:head>{esc(head)}</tei:head>")
    in_section = False
    #: The span of the original the departing rows being set stand in for (see below).
    departure: str | None = None

    def open_section(heading_lines: tuple[Line, ...], lang_attr: str) -> None:
        nonlocal in_section
        if in_section:
            parts.append("</tei:div>")
        parts.append("<tei:div>")
        in_section = True
        if heading_lines:
            heading = "<tei:lb/>".join(render_inline(line, notes) for line in heading_lines)
            parts.append(f"<tei:head{lang_attr}>{heading}</tei:head>")

    for index, row in enumerate(post.rows):
        cell = row.cells[column_index]
        lang_attr = _lang_attr(cell.lang, column.lang)
        if index not in numbers:
            open_section(cell.blocks[0].lines if not cell.is_empty else (), lang_attr)
            continue
        if cell.is_empty:
            continue
        row_urn = urns.row_urn(numbers[index])
        span: str | None = None
        if row_urn:
            milestone = f'<tei:milestone unit="{unit}" corresp="{attr(row_urn)}"/>'
        elif urns.kind == "existing":
            # Where a version departs from the original, one milestone opens the run of rows,
            # corresponding to the span of the original they stand in for; added material
            # corresponds to nothing, and its milestone only ends the scope before it.
            span = urns.spans.get(numbers[index], "")
            milestone = "" if span == departure else (
                f'<tei:milestone unit="{unit}" corresp="{attr(span)}"/>' if span
                else f'<tei:milestone unit="{unit}"/>')
        else:
            milestone = ""
        blocks = list(cell.blocks)
        # Headings that open the cell open their section before the row begins.
        while blocks and blocks[0].kind == "heading":
            open_section(blocks.pop(0).lines, lang_attr)
        if not blocks:
            continue
        parts.append(milestone)
        # Only a milestone set down opens (or continues) a departing run.
        departure = span
        parts.extend(_note("description", row.cells[i], notes, column.lang)
                     for i, c in hosted if c.role == "description" and not row.cells[i].is_empty)
        for block in blocks:
            if block.kind == "heading":
                open_section(block.lines, lang_attr)
            else:
                parts.append(render_block(block, notes, lang_attr))
        parts.extend(_note("commentary", row.cells[i], notes, column.lang)
                     for i, c in hosted if c.role == "commentary" and not row.cells[i].is_empty)
    if in_section:
        parts.append("</tei:div>")
    parts.append("</tei:div>")
    return f"<tei:body>{''.join(parts)}</tei:body>", standoff(notes, column.lang)


def essay_body(post: Post, lang: str, urns: PostUrns) -> tuple[str, str]:
    """An essay's body: its paragraphs, transcluding each passage it quotes where it stands."""
    notes = _Notes([], condition_base=condition_base(urns.urn))
    quoted = urns.quoted()
    # Passage k is row k of the table, numbered as its milestones are (headings skipped).
    numbers = row_numbers(post)
    parts = [f'<tei:div corresp="{attr(urns.urn)}">']
    head = next((title for title_lang, title in titles_by_language(post) if title_lang == lang), "")
    if head:
        parts.append(f"<tei:head>{esc(head)}</tei:head>")
    for item in post.essay:
        if isinstance(item, int):
            if item - 1 in numbers:
                parts.append(f'<j:transclude type="external" target="{attr(quoted.row_urn(numbers[item - 1]))}"/>')
        else:
            parts.append(f"<tei:p>{render_inline(item, notes)}</tei:p>")
    parts.append("</tei:div>")
    return f"<tei:body>{''.join(parts)}</tei:body>", standoff(notes, lang)


def essay_language(post: Post, languages: list[str]) -> str | None:
    """The project an essay is written in: the language of its paragraphs (as
    :func:`front_language` judges it), else English, else the first."""
    lines = [item for item in post.essay if not isinstance(item, int)]
    return _written_language(lines, languages)


def standoff(notes: _Notes, lang: str) -> str:
    if not notes.entries:
        return ""
    entries = "".join(
        f'<tei:note type="commentary" n="{number}" target="#note_{number}">'
        f"<tei:p>{render_inline(note, None, in_note=True)}</tei:p></tei:note>"
        for number, note in notes.entries
    )
    return f'<tei:standOff type="notes">{entries}</tei:standOff>'


# --------------------------------------------------------------------------------------------
# Headers
# --------------------------------------------------------------------------------------------


def _titles(post: Post, lang: str) -> str:
    titles = titles_by_language(post)
    main_index = next((i for i, (title_lang, _) in enumerate(titles) if title_lang == lang), 0)
    out = []
    for index, (title_lang, title) in enumerate(titles):
        kind = "main" if index == main_index else "alt"
        out.append(f'<tei:title type="{kind}" xml:lang="{title_lang}">{esc(title)}</tei:title>')
    return "".join(out)


def _resp_statements(credits: tuple[Credit, ...]) -> str:
    return "".join(
        "<tei:respStmt>"
        f'<tei:resp key="{credit.key}">{esc(credit.resp)}</tei:resp>'
        f'<tei:name ref="{attr(credit.urn)}">{esc(credit.name)}</tei:name>'
        "</tei:respStmt>"
        for credit in credits
    )


def _publication(licence: LicenceDecision) -> str:
    assert licence.licence is not None, "only an allowed licence is written"
    basis = f"<tei:p>{esc(licence.basis)}</tei:p>" if licence.basis else ""
    return (
        "<tei:publicationStmt>"
        f'<tei:distributor><tei:ref target="{SITE_URL}">{SITE_NAME}</tei:ref></tei:distributor>'
        '<tei:availability status="free">'
        f'<tei:licence target="{attr(licence.licence.url)}">{esc(licence.licence.name)}</tei:licence>'
        f"{basis}</tei:availability>"
        "</tei:publicationStmt>"
    )


def iso_date(value: str) -> str:
    """The site's partial dates as ISO: ``1440-00-00`` is the year 1440, ``1834-05-00`` May 1834."""
    match = re.match(r"^(-?\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", value.strip())
    if not match:
        return ""
    year, month, day = match.groups()
    if not month or month == "00":
        return year
    if not day or day == "00":
        return f"{year}-{month}"
    return f"{year}-{month}-{day}"


def _date_of_original(post: Post) -> str:
    start, end = iso_date(post.date_src_start), iso_date(post.date_src_end)
    if not start and not end:
        return ""
    if start and end and start != end:
        return f'<tei:date from="{attr(start)}" to="{attr(end)}">{esc(start)} – {esc(end)}</tei:date>'
    when = start or end
    return f'<tei:date when="{attr(when)}">{esc(when)}</tei:date>'


def post_url(post: Post) -> str:
    """The post's address by ID, which WordPress redirects to wherever the post is filed."""
    return f"{SITE_URL}/?p={post.post_id}"


def source_bibl(
    post: Post, credits: Credits, *, upstream_commit: str, upstream_commit_date: str
) -> str:
    titles = "".join(
        f'<tei:title xml:lang="{lang}">{esc(title)}</tei:title>' for lang, title in titles_by_language(post)
    )
    authors = "".join(f"<tei:author>{esc(name)}</tei:author>" for name in credits.authors)
    authors += "".join(
        f'<tei:respStmt><tei:resp key="{credit.key}">{esc(credit.resp)}</tei:resp>'
        f"<tei:name>{esc(credit.name)}</tei:name></tei:respStmt>"
        for credit in credits.source_responsibilities
    )
    sources = "".join(
        f'<tei:note>Source: {esc(source.caption) + " " if source.caption else ""}'
        f'<tei:ref target="{attr(source.url)}">{esc(source.url)}</tei:ref></tei:note>'
        for source in post.sources
    )
    return (
        f'<tei:bibl xml:id="{PROJECT_SOURCE_BIBL_ID}">'
        f"{titles}{authors}"
        f'<tei:distributor><tei:ref target="{SITE_URL}">{SITE_NAME}</tei:ref></tei:distributor>'
        f"{_date_of_original(post)}"
        f'<tei:date type="accessed" when="{attr(upstream_commit_date)}">{esc(upstream_commit_date)}</tei:date>'
        # The post is cited by its ID: the exporter's bibliography links an entry to its URL,
        # and this one reaches the post wherever it is filed. The permalink is not kept: it
        # changes whenever the post moves category.
        f'<tei:idno type="url">{esc(post_url(post))}</tei:idno>'
        f'<tei:idno type="opensiddur.org">{post.post_id}</tei:idno>'
        f"{sources}"
        '<tei:note type="encoding">Converted from the export of opensiddur.org at '
        f'<tei:ref target="{UPSTREAM_REPOSITORY}/tree/{attr(upstream_commit)}">{esc(upstream_commit[:10])}</tei:ref>.'
        "</tei:note>"
        "</tei:bibl>"
    )


def header(
    post: Post,
    *,
    lang: str,
    credits: tuple[Credit, ...],
    licence: LicenceDecision,
    source_desc: str,
) -> str:
    return (
        "<tei:teiHeader><tei:fileDesc>"
        f"<tei:titleStmt>{_titles(post, lang)}{_resp_statements(credits)}</tei:titleStmt>"
        f"{_publication(licence)}"
        f"<tei:sourceDesc>{source_desc}</tei:sourceDesc>"
        "</tei:fileDesc></tei:teiHeader>"
    )


# --------------------------------------------------------------------------------------------
# Front matter
# --------------------------------------------------------------------------------------------


def front(post: Post, lang: str, id_prefix: str, *, shared: bool = True,
          own_introduction: bool = False) -> tuple[str, str]:
    """The post's own words, the paragraphs before and after its table, as colophon divisions
    gated on paratext, and the standOff of their footnotes. They are about the digital edition,
    not part of the source, so ``type="colophon"`` keeps them apart from front matter a source
    printed; the exporter sets them after its own colophon. They go in the project whose
    language they are written in (see :func:`front_language`): ``shared``. An introduction the
    post gives in several languages goes, each language's, in the project of that language:
    ``own_introduction``."""
    notes = _Notes([])
    sections = []
    intro = (post.intro if shared else []) + (post.intros_by_language.get(lang, []) if own_introduction else [])
    for name, lines in (("introduction", intro), ("notes", post.notes if shared else [])):
        if not lines:
            continue
        paragraphs = "".join(
            f'<j:transclude type="external" target="{attr(urn)}"/>' if (urn := transcluded_urn(line))
            else f"<tei:p>{render_inline(line, notes)}</tei:p>"
            for line in lines
        )
        cond_id = f"{id_prefix}_{name}"
        sections.append(
            f'<j:conditional xml:id="{cond_id}"><tei:fs type="opensiddur:paratext">'
            '<tei:f name="include"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>'
            f'<tei:div type="colophon" subtype="{name}">{paragraphs}</tei:div>'
            f'<j:endConditional target="#{cond_id}"/>'
        )
    if not sections:
        return "", ""
    return f"<tei:front>{''.join(sections)}</tei:front>", standoff(notes, lang)


def front_language(post: Post, languages: list[str]) -> str | None:
    """The project the front matter goes in: the one whose language it is written in, else
    English, else the first. Front matter with no words of its own, only a transclusion, goes
    in the first."""
    lines = post.intro + post.notes
    found = _written_language(lines, languages)
    if found is None and any(transcluded_urn(line) for line in lines) and languages:
        return languages[0]
    return found


def _written_language(lines: list[Line], languages: list[str]) -> str | None:
    text = " ".join(node_text(line) for line in lines)
    if not text.strip():
        return None
    if re.search(r"[A-Za-z]", text):
        latin = [lang for lang in languages if _is_latin(lang) and not lang.endswith("-Latn")]
        candidates = (["en"] if "en" in latin else []) + latin
    else:
        candidates = [_script_language(text)]
    for candidate in candidates:
        if candidate in languages:
            return candidate
    return languages[0] if languages else None


# --------------------------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectFiles:
    project_id: str
    lang: str
    files: dict[str, str]


def build_project(
    post: Post,
    column: Column,
    *,
    urns: PostUrns,
    credits: Credits,
    licence: LicenceDecision,
    upstream_commit: str,
    upstream_commit_date: str,
    with_front: bool,
    project_id: str,
    with_essay: bool = False,
    with_own_introduction: bool = False,
) -> ProjectFiles:
    """One project of the post: the column ``column.key`` of each of its tables. A post with
    more than one table holds that many texts, each in a file of its own, which the index
    transcludes in order.

    An essay's table is the passages it quotes (``<urn>/quoted``). The project of the essay's
    language (``with_essay``) also holds the essay, ``<urn>``, which transcludes each passage
    where it stands; its index transcludes the essay, and the other projects' the passages."""
    lang = column.lang
    pid = project_id
    column_credits = credits.for_column_role(column.role)
    text_header = header(
        post, lang=lang, credits=column_credits, licence=licence,
        source_desc=f'<tei:bibl><tei:ptr target="{xml_id_ref(pid, "index", PROJECT_SOURCE_BIBL_ID)}"/></tei:bibl>',
    )
    views = table_views(post)
    files: dict[str, str] = {}
    transclusions: list[str] = []
    for number, view in enumerate(views, 1):
        index = next((i for i, c in imported_columns(view) if c.key == column.key), None)
        if index is None:
            continue
        text_urns = urns.quoted() if post.essay else urns.table(number, len(views))
        body, notes = text_body(view, index, view.columns[index], text_urns)
        files[text_file_stem(text_urns.urn)] = tei_document(text_header, body, lang=lang, standoff_xml=notes)
        transclusions.append(f'<j:transclude type="external" target="{attr(text_urns.urn)}"/>')
    if post.essay and with_essay:
        body, notes = essay_body(post, lang, urns)
        files[text_file_stem(urns.urn)] = tei_document(text_header, body, lang=lang, standoff_xml=notes)
        transclusions = [f'<j:transclude type="external" target="{attr(urns.urn)}"/>']

    index_header = header(
        post, lang=lang, credits=column_credits, licence=licence,
        source_desc=source_bibl(
            post, credits, upstream_commit=upstream_commit, upstream_commit_date=upstream_commit_date
        ),
    )
    index_body = f"<tei:body><tei:div>{''.join(transclusions)}</tei:div></tei:body>"
    front_xml, front_notes = (
        front(post, lang, f"osp_{post.post_id}", shared=with_front, own_introduction=with_own_introduction)
        if with_front or with_own_introduction else ("", "")
    )
    index_document = tei_document(
        index_header, index_body, lang=lang, front_xml=front_xml, standoff_xml=front_notes
    )
    return ProjectFiles(pid, lang, {"index": index_document, **files})
