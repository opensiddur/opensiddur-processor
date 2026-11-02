"""Parse one opensiddur.org post, as exported to JSON, into columns, rows and metadata.

The post's ``content`` is the HTML WordPress rendered. A prayer is set in a
``table.toggleable-table``: each ``<th>`` names a column's role and language ("Source
(Hebrew)", "Translation (English)", "Transliteration (romanized Hebrew)"), and each ``<tr>``
is one stanza or block, with one ``td > div[lang]`` per column. Lines are separated by
``<br>``, and a line holding only a non-breaking space marks a stanza gap.

The parser keeps what the TEI needs and nothing else:

- inline spans with a meaning (``divine-referent``, ``instruction``, ``acrostic``,
  ``citation``), emphasis, and footnotes, whose text is taken from the plugin's inline
  tooltip;
- the HTML before the table (the introduction) and after it (notes), as paragraphs;
- the captions and links of the ``Source(s)`` section, which are recorded but never fetched.

Everything else the site renders around a post (scripts, styles, the iframe plugin's
boilerplate) is dropped. See ``specs/OPENSIDDUR_ORG_IMPORT.md``.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Union

import lxml.html
from lxml.html import HtmlElement

from opensiddur.importer.opensiddur_org.languages import (
    NOT_TEXT_ROLES,
    UNKNOWN_LANGUAGE,
    language_from_header,
    language_from_lang_attribute,
    resolve_disagreement,
    same_language,
)
from opensiddur.importer.opensiddur_org.post_decisions import (
    NO_DECISIONS,
    PostDecisions,
    default_post_decisions,
)
from opensiddur.importer.util.hebrew import to_nfkd

POST_ID_RE = re.compile(r"_\((\d+)\)\.json$")

#: Span classes the site uses with a meaning the TEI keeps. Every other span is transparent.
SEMANTIC_SPANS: dict[str, str] = {
    "divine-referent": "divine",
    "instruction": "instruction",
    "acrostic": "acrostic",
    "citation": "citation",
}

#: Inline formatting kept as ``tei:hi``.
FORMATTING_TAGS: dict[str, str] = {
    "em": "italic",
    "i": "italic",
    "strong": "bold",
    "b": "bold",
    "sup": "superscript",
    "sub": "subscript",
}

#: Elements dropped with everything inside them.
DROPPED_TAGS = frozenset({"script", "style", "noscript", "iframe", "audio", "video", "img"})

HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

NBSP = "\xa0"


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Span:
    """An inline span. ``kind`` is one of the values of :data:`SEMANTIC_SPANS` or
    :data:`FORMATTING_TAGS`."""

    kind: str
    children: tuple["Node", ...]


@dataclass(frozen=True)
class FootnoteRef:
    """A footnote marker. ``number`` counts footnotes through the whole post, in order."""

    number: int
    note: tuple["Node", ...]


Node = Union[Text, Span, FootnoteRef]
Line = tuple[Node, ...]


@dataclass(frozen=True)
class Block:
    """A stanza of lines, a prose paragraph, or a heading."""

    kind: Literal["stanza", "paragraph", "heading"]
    lines: tuple[Line, ...]


@dataclass
class Cell:
    lang: str | None
    css_class: str | None
    blocks: list[Block]
    #: The ``lang`` attribute as written (``jrb-Hebr``), which says whether a script was given.
    raw_lang: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.blocks


@dataclass
class Column:
    header: str
    role: str
    lang: str
    #: Why the column's language was read the way it was, when the ``<th>`` and the
    #: ``div@lang`` disagree; empty when they agree.
    mismatch: str = ""
    #: What tells this column apart from an earlier one in the same language ("1852",
    #: "literal"), which names its project; empty for the first column in a language.
    variant: str = ""

    @property
    def key(self) -> str:
        """The column's project within its post: its language, and its variant if it has one."""
        return f"{self.lang}/{self.variant}" if self.variant else self.lang


@dataclass
class Row:
    cells: list[Cell]


@dataclass
class Table:
    """One table of a post: one text, set in parallel columns."""

    columns: list[Column]
    rows: list[Row]


@dataclass(frozen=True)
class SourceRef:
    caption: str
    url: str


@dataclass(frozen=True)
class Coauthor:
    name: str
    profile_slug: str
    qualifier: str


@dataclass
class Post:
    post_id: int
    title: str
    slug: str
    permalink: str
    source_link: str
    date: str
    last_updated: str
    coauthors: list[Coauthor]
    categories: list[str]
    tags: list[str]
    licence_html: str
    licence_url: str
    languages: list[str]
    date_src_start: str
    date_src_end: str
    #: The first table's columns and rows (see :attr:`tables` for all of them).
    columns: list[Column] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)
    table_count: int = 0
    #: Every table of the post, in order. A post with more than one table holds that many
    #: texts, each its own file.
    tables: list[Table] = field(default_factory=list)
    intro: list[Line] = field(default_factory=list)
    notes: list[Line] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    #: Body ``div[lang]`` blocks set outside any table: the prose-only layout.
    loose_cells: list[Cell] = field(default_factory=list)
    #: Paragraphs between the ``div[lang]`` blocks of a post with no table.
    between_blocks: list[Line] = field(default_factory=list)
    #: For an essay about the passages it quotes: its paragraphs in order, with the number
    #: (from 1) of each quoted passage where it stands. The passages are the rows of the post's
    #: table.
    essay: list[Line | int] = field(default_factory=list)
    has_colour_alignment: bool = False
    #: Colours the post sets that no decision gives a meaning (``post_decisions.yaml``).
    undecided_colours: set[str] = field(default_factory=set)
    file_links: list[str] = field(default_factory=list)
    embeds: list[str] = field(default_factory=list)

    @property
    def titles(self) -> list[str]:
        return split_title(self.title)


# --------------------------------------------------------------------------------------------
# Small text helpers
# --------------------------------------------------------------------------------------------

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿︎️‍]"
)
_WS_RE = re.compile(r"[ \t\r\n\f\v]+")


def clean_text(text: str, *, unescape: bool = False) -> str:
    """Drop emoji and normalize to the storage form (NFKD). ``unescape`` decodes entities, for
    the export's raw JSON strings; text that lxml parsed is decoded already, and decoding it
    again would turn a literal ``&lt;`` into ``<``."""
    if unescape:
        text = html.unescape(text)
    # A typo for the entity, which the site renders as written (post 66797).
    text = text.replace("^nbsp;", NBSP)
    text = _EMOJI_RE.sub("", text)
    return to_nfkd(text)


def split_title(title: str) -> list[str]:
    """The post title's parts. Titles are set "Hebrew | English"."""
    parts = [_WS_RE.sub(" ", clean_text(part, unescape=True)).strip() for part in title.split("|")]
    return [part for part in parts if part]


def licence_url(licence_html: str) -> str:
    """The URL a licence's ``<a href>`` names, or "" when it names none."""
    match = re.search(r"href=['\"]([^'\"]+)['\"]", licence_html)
    if not match:
        return ""
    url = html.unescape(match.group(1)).strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def _first(values: Any) -> str:
    if isinstance(values, list):
        return str(values[0]) if values else ""
    return str(values or "")


def _languages_meta(custom_fields: dict[str, Any]) -> list[str]:
    try:
        entries = json.loads(_first(custom_fields.get("languages_meta")) or "[]")
    except json.JSONDecodeError:
        return []
    return [entry.get("code", "") for entry in entries if isinstance(entry, dict)]


_QUALIFIER_RE = re.compile(r"\s*\(([^()]*)\)\s*$")


def parse_coauthor(entry: dict[str, Any]) -> Coauthor:
    name = html.unescape(entry.get("name", "")).strip()
    qualifier = ""
    match = _QUALIFIER_RE.search(name)
    if match:
        qualifier = match.group(1).strip()
        name = name[: match.start()].strip()
    profile = entry.get("profile_link", "") or ""
    slug = profile.rstrip("/").rsplit("/", 1)[-1] if profile else ""
    return Coauthor(name=to_nfkd(name), profile_slug=slug, qualifier=qualifier)


def post_id_from_path(path: str) -> int | None:
    match = POST_ID_RE.search(path)
    return int(match.group(1)) if match else None


# --------------------------------------------------------------------------------------------
# Inline content
# --------------------------------------------------------------------------------------------


class _Footnotes:
    """Numbers footnotes through a post in the order they appear."""

    def __init__(self) -> None:
        self.count = 0

    def next(self) -> int:
        self.count += 1
        return self.count


def _classes(element: HtmlElement) -> set[str]:
    return set((element.get("class") or "").split())


def _inline_nodes(element: HtmlElement, footnotes: _Footnotes) -> list[Node | str]:
    """The inline content of ``element``. Line breaks come back as the string ``"\\n"``."""
    out: list[Node | str] = []
    if element.text:
        out.append(Text(element.text))
    for child in element:
        out.extend(_child_nodes(child, footnotes))
        if child.tail:
            out.append(Text(child.tail))
    return out


def _child_nodes(child: HtmlElement, footnotes: _Footnotes) -> list[Node | str]:
    tag = child.tag if isinstance(child.tag, str) else ""
    if not tag or tag in DROPPED_TAGS:
        return []
    if tag == "br":
        return ["\n"]
    classes = _classes(child)
    if tag == "span" and "footnote_referrer" in classes:
        tooltip = child.xpath('.//span[contains(@class, "footnote_tooltip")]')
        note: list[Node | str] = _inline_nodes(tooltip[0], footnotes) if tooltip else []
        return [FootnoteRef(footnotes.next(), _join_inline(note))]
    if tag in ("span", "font"):
        kind = next((SEMANTIC_SPANS[c] for c in sorted(classes) if c in SEMANTIC_SPANS), None)
        colour = _colour(child)
        if kind is None and colour:
            # What a colour means is the post's own (see apply_colours).
            kind = f"{COLOUR_KIND}{colour}"
        inner = _inline_nodes(child, footnotes)
        if kind is None:
            return inner
        return _wrap(kind, inner)
    if tag in FORMATTING_TAGS:
        return _wrap(FORMATTING_TAGS[tag], _inline_nodes(child, footnotes))
    if tag in ("p", "div", "li", "blockquote"):
        # A block inside inline content ends the line it is on.
        return ["\n", *_inline_nodes(child, footnotes), "\n"]
    return _inline_nodes(child, footnotes)


#: The kind of a span whose colour has not been given a meaning yet: ``colour:green``.
COLOUR_KIND = "colour:"
_COLOUR_RE = re.compile(r"(?<![-\w])color\s*:\s*([#\w]+)", re.IGNORECASE)
#: Colours that are the page's own, not the author's.
_PLAIN_COLOURS = frozenset({"#000000", "#000", "black", "inherit", "initial", "transparent"})


def _colour(element: HtmlElement) -> str:
    """The text colour an element's style sets, lowercased (``dodgerblue``, ``#808080``), or ""."""
    match = _COLOUR_RE.search(element.get("style") or "")
    if not match or match.group(1).lower() in _PLAIN_COLOURS:
        return ""
    return match.group(1).lower()


def _wrap(kind: str, inner: list[Node | str]) -> list[Node | str]:
    """Wrap ``inner`` in a span, splitting it at line breaks so that no span crosses one."""
    out: list[Node | str] = []
    segment: list[Node | str] = []

    def flush() -> None:
        # Spaces at a span's edges are kept: "in<em> Midrash</em>" must not become "inMidrash".
        children = _join_inline(segment, trim=False)
        if children and node_text(children).strip() or any(not isinstance(c, Text) for c in children):
            out.append(Span(kind, children))
        elif children:
            out.extend(children)  # a span of nothing but space is just the space
        segment.clear()

    for node in inner:
        if node == "\n":
            flush()
            out.append("\n")
        else:
            segment.append(node)
    flush()
    return out


def _join_inline(nodes: list[Node | str], *, trim: bool = True) -> tuple[Node, ...]:
    """Merge adjacent text and collapse whitespace, then trim unless ``trim`` is false. Line
    breaks become spaces."""
    merged: list[Node] = []
    for node in nodes:
        if isinstance(node, str):
            node = Text(" ")
        if isinstance(node, Text):
            text = clean_text(node.text)
            if merged and isinstance(merged[-1], Text):
                merged[-1] = Text(merged[-1].text + text)
            else:
                merged.append(Text(text))
        else:
            merged.append(node)
    collapsed = [
        Text(_WS_RE.sub(" ", n.text.replace(NBSP, " "))) if isinstance(n, Text) else n
        for n in merged
    ]
    kept = tuple(n for n in collapsed if not (isinstance(n, Text) and not n.text))
    return _trim(kept) if trim else kept


def _trim(nodes: tuple[Node, ...], *, start: bool = True, end: bool = True) -> tuple[Node, ...]:
    """Trim the whitespace at the edges of a line, inside an edge span too, and the doubled
    space where a span's edge space meets the text beside it."""
    items = list(nodes)
    if start:
        while items and isinstance(items[0], Text) and not items[0].text.strip():
            items.pop(0)
        if items and isinstance(items[0], Text):
            items[0] = Text(items[0].text.lstrip())
        elif items and isinstance(items[0], Span):
            items[0] = Span(items[0].kind, _trim(items[0].children, end=False))
    if end:
        while items and isinstance(items[-1], Text) and not items[-1].text.strip():
            items.pop()
        if items and isinstance(items[-1], Text):
            items[-1] = Text(items[-1].text.rstrip())
        elif items and isinstance(items[-1], Span):
            items[-1] = Span(items[-1].kind, _trim(items[-1].children, start=False))
    return tuple(items)


def node_text(nodes: tuple[Node, ...] | list[Node]) -> str:
    """Plain text of inline nodes, without footnote text."""
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            parts.append(node.text)
        elif isinstance(node, Span):
            parts.append(node_text(node.children))
    return "".join(parts)


def _split_lines(nodes: list[Node | str]) -> list[tuple[Line, bool]]:
    """Split inline content at line breaks. Each line comes with whether it is a gap: a line
    that held only (non-breaking) whitespace, which is how the site marks a stanza break."""
    lines: list[tuple[Line, bool]] = []
    current: list[Node | str] = []

    def flush() -> None:
        raw = "".join(n.text for n in current if isinstance(n, Text))
        has_content = any(not isinstance(n, Text) for n in current) or raw.strip(" \t\r\n\f\v" + NBSP)
        if has_content:
            lines.append((_join_inline(current), False))
        elif NBSP in raw:
            lines.append(((), True))
        current.clear()

    for node in nodes:
        if node == "\n":
            flush()
        else:
            current.append(node)
    flush()
    return lines


def _stanzas(nodes: list[Node | str]) -> list[Block]:
    blocks: list[Block] = []
    current: list[Line] = []
    for line, gap in _split_lines(nodes):
        if gap:
            if current:
                blocks.append(Block("stanza", tuple(current)))
                current = []
        elif line:
            current.append(line)
    if current:
        blocks.append(Block("stanza", tuple(current)))
    return blocks


def _cell_blocks(div: HtmlElement, footnotes: _Footnotes) -> list[Block]:
    """A cell's blocks. Children that are paragraphs or headings make the cell prose."""
    block_children = [
        c for c in div if isinstance(c.tag, str) and (c.tag == "p" or c.tag in HEADING_TAGS)
    ]
    if not block_children:
        return _stanzas(_inline_nodes(div, footnotes))

    blocks: list[Block] = []
    loose: list[Node | str] = [Text(div.text)] if div.text else []

    def flush_loose() -> None:
        for line, _gap in _split_lines(loose):
            if line:
                blocks.append(Block("paragraph", (line,)))
        loose.clear()

    for child in div:
        if not isinstance(child.tag, str):
            continue
        if child.tag in HEADING_TAGS:
            flush_loose()
            heading = _join_inline(_inline_nodes(child, footnotes))
            if heading:
                blocks.append(Block("heading", (heading,)))
        elif child.tag == "p":
            flush_loose()
            lines = [line for line, _gap in _split_lines(_inline_nodes(child, footnotes)) if line]
            if lines:
                blocks.append(Block("paragraph", tuple(lines)))
        else:
            loose.extend(_child_nodes(child, footnotes))
        if child.tail:
            loose.append(Text(child.tail))
    flush_loose()
    return blocks


# --------------------------------------------------------------------------------------------
# The post
# --------------------------------------------------------------------------------------------


#: The footnote plugin's own list of the notes, set after the post. The notes are read from
#: their inline tooltips instead, so this would only repeat them as garbled text.
_FOOTNOTE_CONTAINERS = (
    '//*[contains(@class, "footnote_container_prepare")]'
    '|//*[contains(@class, "footnote-reference-container")]'
    '|//*[contains(@class, "footnotes_table")]'
)


def _strip_noise(root: HtmlElement) -> None:
    for element in root.xpath(f"//script|//style|//noscript|{_FOOTNOTE_CONTAINERS}"):
        tail = element.tail
        parent = element.getparent()
        if parent is None:
            continue
        if tail:
            previous = element.getprevious()
            if previous is not None:
                previous.tail = (previous.tail or "") + tail
            else:
                parent.text = (parent.text or "") + tail
        parent.remove(element)


def _cell(td: HtmlElement, footnotes: _Footnotes) -> Cell:
    divs = [c for c in td if isinstance(c.tag, str) and c.tag == "div" and c.get("lang")]
    if not divs:
        blocks = _cell_blocks(td, footnotes)
        return Cell(lang=None, css_class=None, blocks=blocks)
    blocks: list[Block] = []
    for div in divs:
        div_blocks = _cell_blocks(div, footnotes)
        colour = _colour(div)
        if colour:
            # A cell set in a colour: every line of it is coloured.
            div_blocks = [Block(b.kind, tuple((Span(f"{COLOUR_KIND}{colour}", line),) if line else line
                                              for line in b.lines)) for b in div_blocks]
        blocks.extend(div_blocks)
    first = divs[0]
    return Cell(
        lang=language_from_lang_attribute(first.get("lang", "")),
        css_class=(first.get("class") or "").strip() or None,
        blocks=blocks,
        raw_lang=first.get("lang", "").strip(),
    )


def _column_language(header: str, cells: list[Cell], override: str = "") -> tuple[str, str, str]:
    """A column's role and language, and why, when the header and the markup disagree.

    When the ``<th>`` names a language that the ``div@lang`` contradicts,
    :func:`resolve_disagreement` decides: post 68472 marks its English ``heb-Latn``, and the
    Kaddish's "Source (Aramaic)" is often marked ``heb-Hebr``, but a "Source (Hebrew)" column
    marked ``yid-Hebr`` holds Yiddish. ``override`` is a person's decision for this column
    (``post_decisions.yaml``), which wins over both.
    """
    role, header_lang = language_from_header(header)
    if override:
        return role, override, ""
    counts: dict[str, int] = {}
    for cell in cells:
        if cell.lang and not cell.is_empty:
            counts[cell.lang] = counts.get(cell.lang, 0) + 1
    markup_lang = max(sorted(counts), key=lambda k: counts[k]) if counts else ""
    scripts_given = any(len(c.raw_lang.split("-")) > 1 for c in cells if c.raw_lang and not c.is_empty)
    if (
        role == "transliteration"
        and header_lang.endswith("-Latn")
        and markup_lang
        and not scripts_given
        and same_language(header_lang, f"{markup_lang.split('-')[0]}-Latn")
    ):
        # The markup names the language but not the script; a transliteration is Latin.
        return role, header_lang, ""
    if header_lang and markup_lang and not same_language(header_lang, markup_lang):
        return (role, resolve_disagreement(header_lang, markup_lang),
                f"header says {header_lang}, markup says {markup_lang}")
    # Where they agree the markup is the more precise of the two (a dialect, a script).
    lang = markup_lang or header_lang or UNKNOWN_LANGUAGE
    return role, lang, ""


def _paragraph_lines(elements: list[HtmlElement], footnotes: _Footnotes) -> list[Line]:
    lines: list[Line] = []
    for element in elements:
        if not isinstance(element.tag, str) or element.tag in DROPPED_TAGS:
            continue
        if element.tag in ("hr",):
            continue
        for line, _gap in _split_lines(_inline_nodes(element, footnotes)):
            if line:
                lines.append(line)
    return lines


def _source_refs(elements: list[HtmlElement]) -> list[SourceRef]:
    refs: list[SourceRef] = []
    seen: set[str] = set()
    for element in elements:
        if not isinstance(element.tag, str):
            continue
        for caption_div in element.xpath('descendant-or-self::div[contains(@class, "wp-caption")]'):
            links = caption_div.xpath(".//a/@href")
            caption = " ".join(caption_div.xpath('.//*[contains(@class, "wp-caption-text")]//text()'))
            if links and links[0] not in seen:
                seen.add(links[0])
                refs.append(SourceRef(_WS_RE.sub(" ", clean_text(caption)).strip(), links[0]))
        for url in element.xpath("descendant-or-self::iframe/@src | descendant-or-self::a[contains(@class, 'mtli_')]/@href"):
            if url not in seen:
                seen.add(url)
                refs.append(SourceRef("", url))
    return refs


def _top_level(root: HtmlElement) -> list[HtmlElement]:
    return [child for child in root if isinstance(child.tag, str)]


def parse_post(data: dict[str, Any], decisions: PostDecisions = NO_DECISIONS) -> Post:
    custom_fields = data.get("custom_fields") or {}
    licence_html = _first(custom_fields.get("open_content_license"))
    post = Post(
        post_id=int(data["post_id"]),
        title=data.get("title", ""),
        slug=data.get("slug", ""),
        permalink=data.get("permalink", ""),
        source_link=data.get("source_link", ""),
        date=data.get("date", ""),
        last_updated=data.get("last_updated", ""),
        coauthors=[parse_coauthor(c) for c in data.get("coauthors") or []],
        categories=[html.unescape(c) for c in data.get("categories") or []],
        tags=[html.unescape(t) for t in data.get("tags") or []],
        licence_html=licence_html,
        licence_url=licence_url(licence_html),
        languages=_languages_meta(custom_fields),
        date_src_start=_first(custom_fields.get("date_src_start")),
        date_src_end=_first(custom_fields.get("date_src_end")),
    )
    content = data.get("content") or ""
    if not content.strip():
        return post

    root = lxml.html.fromstring(f"<div>{content}</div>")
    post.file_links = list(root.xpath("//a[contains(@class, 'mtli_')]/@href"))
    post.embeds = list(root.xpath("//iframe/@src"))
    post.has_colour_alignment = bool(
        root.xpath('//table[contains(@class, "toggleable-table")]//*[contains(@style, "color")]')
    )
    _strip_noise(root)
    footnotes = _Footnotes()

    top = _top_level(root)
    tables = root.xpath('//table[contains(@class, "toggleable-table")]')
    post.table_count = len(tables)
    def sources_heading(after: int) -> int:
        """The "Source(s)" heading that follows the text, not one in the introduction."""
        return next(
            (i for i, el in enumerate(top) if i > after and el.tag in HEADING_TAGS
             and "source" in el.text_content().lower()),
            len(top),
        )

    if tables:
        def top_index(table: HtmlElement) -> int:
            table_top = table
            while table_top.getparent() is not None and table_top.getparent() is not root:
                table_top = table_top.getparent()
            return top.index(table_top) if table_top in top else 0

        table_tops = [top_index(table) for table in tables]
        first_at, last_at = min(table_tops), max(table_tops)
        sources_at = sources_heading(last_at)
        post.intro = _paragraph_lines(top[:first_at], footnotes)
        overrides = decisions.column_languages.get(post.post_id, {})
        post.tables = [_parse_table(table, footnotes, overrides) for table in tables]
        _roles_of_unheaded_columns(post.tables)
        post.columns, post.rows = post.tables[0].columns, post.tables[0].rows
        # Text between tables is the post's own words too, kept with what follows the last.
        between = [el for i, el in enumerate(top[first_at:sources_at], first_at) if i not in table_tops]
        post.notes = _paragraph_lines(between, footnotes)
    elif post.post_id in decisions.essays:
        _parse_essay(post, top, footnotes, sources_heading)
        apply_colours(post, decisions.colours.get(post.post_id, {}))
        return post
    else:
        loose = root.xpath("//div[@lang]")
        post.loose_cells = [
            Cell(
                lang=language_from_lang_attribute(div.get("lang", "")),
                css_class=(div.get("class") or "").strip() or None,
                blocks=_cell_blocks(div, footnotes),
                raw_lang=div.get("lang", "").strip(),
            )
            for div in loose
            if div.getparent() is not None and not div.getparent().xpath("ancestor-or-self::div[@lang]")
        ]
        loose_tops = [i for i, el in enumerate(top) if el.xpath("descendant-or-self::div[@lang]")]
        first_loose = loose_tops[0] if loose_tops else len(top)
        last_loose = loose_tops[-1] if loose_tops else len(top)
        sources_at = sources_heading(last_loose)
        post.intro = _paragraph_lines(top[:first_loose], footnotes)
        post.notes = _paragraph_lines(top[last_loose + 1 : sources_at], footnotes)
        post.between_blocks = _paragraph_lines(
            [el for el in top[first_loose:last_loose] if not el.xpath("descendant-or-self::div[@lang]")],
            footnotes)
        table = loose_table(post.loose_cells)
        if table is not None:
            post.tables = [table]
            post.columns, post.rows = table.columns, table.rows
    post.sources = _source_refs(top[sources_at:])
    apply_colours(post, decisions.colours.get(post.post_id, {}))
    return post


def _parse_table(table: HtmlElement, footnotes: _Footnotes, overrides: dict[str, str]) -> Table:
    headers = [
        _WS_RE.sub(" ", clean_text(th.text_content()).replace(NBSP, " ")).strip()
        for th in table.xpath("./thead//th | ./tr[1][th]/th")
    ]
    body_rows = table.xpath("./tbody/tr[td] | ./tr[td]")
    rows = [Row([_cell(td, footnotes) for td in tr.xpath("./td")]) for tr in body_rows]
    width = max([len(headers)] + [len(r.cells) for r in rows]) if rows or headers else 0
    for row in rows:
        while len(row.cells) < width:
            row.cells.append(Cell(lang=None, css_class=None, blocks=[]))
    headers += [""] * (width - len(headers))
    columns = []
    for index, header in enumerate(headers):
        cells = [row.cells[index] for row in rows]
        role, lang, mismatch = _column_language(header, cells, overrides.get(header, ""))
        if role == "contribute" and any(not cell.is_empty for cell in cells):
            # The placeholder column is sometimes used for the original of quoted verses.
            role = "source"
        columns.append(Column(header=header, role=role, lang=lang, mismatch=mismatch))
    _finish_columns(columns, rows)
    return Table(columns, rows)


def _parse_essay(post: Post, top: list[HtmlElement], footnotes: _Footnotes, sources_heading) -> None:
    """An essay about the passages it quotes. Each top-level element holding ``div[lang]``
    blocks is one quoted passage, a row of the post's table with a column per language; the
    paragraphs around them are the essay. What follows the last rule (``<hr>``) is the post's
    own words, as after a table."""
    passages = [i for i, el in enumerate(top) if el.xpath("descendant-or-self::div[@lang]")]
    sources_at = sources_heading(passages[-1] if passages else 0)
    rules = [i for i, el in enumerate(top[:sources_at]) if el.tag == "hr" and i > (passages[-1] if passages else 0)]
    end = rules[-1] if rules else sources_at
    cells_by_passage: list[dict[str, Cell]] = []
    for index in range(end):
        element = top[index]
        if index in passages:
            cells: dict[str, Cell] = {}
            for div in element.xpath("descendant-or-self::div[@lang]"):
                lang = language_from_lang_attribute(div.get("lang", "")) or UNKNOWN_LANGUAGE
                cell = cells.setdefault(lang, Cell(lang=lang, css_class=div.get("class"), blocks=[],
                                                   raw_lang=div.get("lang", "")))
                cell.blocks.extend(_cell_blocks(div, footnotes))
            cells_by_passage.append(cells)
            post.essay.append(len(cells_by_passage))
        else:
            post.essay.extend(_paragraph_lines([element], footnotes))
    post.notes = _paragraph_lines(top[end + 1 : sources_at], footnotes) if rules else []
    post.sources = _source_refs(top[sources_at:])
    order = sorted({lang for cells in cells_by_passage for lang in cells}, key=lambda l: (l.split("-")[0] != "he", l))
    columns = [Column(header="", role="source" if i == 0 else "translation", lang=lang) for i, lang in enumerate(order)]
    rows = [Row([cells.get(lang, Cell(lang=None, css_class=None, blocks=[])) for lang in order])
            for cells in cells_by_passage]
    if columns:
        post.tables = [Table(columns, rows)]
        post.columns, post.rows = columns, rows


def _roles_of_unheaded_columns(tables: list[Table]) -> None:
    """Give a column with no header the role of the column in its language in another table of
    the post; where there is none, the Hebrew column is the source and the others are
    translations (or, with no Hebrew, the first is the source)."""
    known = {c.lang: c.role for t in tables for c in t.columns if c.header and c.role}
    for table in tables:
        unheaded = [c for c in table.columns if not c.header and not c.role]
        if not unheaded:
            continue
        hebrew = any(c.lang.split("-")[0] == "he" for c in table.columns)
        for index, column in enumerate(table.columns):
            if column not in unheaded:
                continue
            if column.lang in known:
                column.role = known[column.lang]
            elif hebrew:
                column.role = "source" if column.lang.split("-")[0] == "he" else "translation"
            else:
                column.role = "source" if index == 0 else "translation"


def loose_table(cells: list[Cell]) -> Table | None:
    """The ``div[lang]`` blocks of a post with no table, read as a table.

    Blocks all in one language are one column, a row each. Blocks that alternate languages
    (Hebrew, English, Hebrew, English…) pair up into rows of a two-column table. Anything else
    is not a table (None).
    """
    # An empty block still holds its place: a Hebrew block left empty beside its English.
    if not any(not cell.is_empty for cell in cells) or any(not cell.lang for cell in cells):
        return None
    order: list[str] = []
    for cell in cells:
        if cell.lang in order:
            break
        order.append(cell.lang)
    width = len(order)
    if width > 2 or len(cells) % width or any(
        cell.lang != order[i % width] for i, cell in enumerate(cells)
    ):
        return None
    # The Hebrew, where there is one, is the original; otherwise the first.
    source = next((lang for lang in order if lang.split("-")[0] == "he"), order[0])
    columns = [Column(header="", role="source" if lang == source else "translation", lang=lang)
               for lang in order]
    rows = [Row(cells[i : i + width]) for i in range(0, len(cells), width)]
    _finish_columns(columns, rows)
    return Table(columns, rows)


def _finish_columns(columns: list[Column], rows: list[Row]) -> None:
    """Settle what a column's header and markup alone cannot.

    - A transliteration whose header names no language ("Transliteration (Romanization)")
      romanizes the source column beside it.
    - A column in the same language as an earlier one is a variant of its own, named from its
      header.
    - An "Initials" column's letters are marked as acrostics where the source's stanza begins
      with them.
    """
    source = next((c for c in columns if c.role == "source"), None)
    for column in columns:
        if (column.role == "transliteration" and not language_from_header(column.header)[1]
                and source is not None and not source.lang.endswith("-Latn")
                and source.lang != UNKNOWN_LANGUAGE):
            column.lang = f"{source.lang.split('-')[0]}-Latn"

    seen: dict[str, Column] = {}
    variants: set[str] = set()
    for index, column in enumerate(columns):
        if column.role in NOT_TEXT_ROLES or not any(not row.cells[index].is_empty for row in rows):
            continue
        first = seen.setdefault(column.lang, column)
        if first is column:
            continue
        name = _variant_name(column.header) or (column.role if column.role != first.role else "")
        name = name or str(index + 1)
        while f"{column.lang}/{name}" in variants:
            name = f"{name}_{index + 1}"
        variants.add(f"{column.lang}/{name}")
        column.variant = name

    for index, column in enumerate(columns):
        if column.role != "initials":
            continue
        target = next((i for i, c in enumerate(columns)
                       if c.lang == column.lang and c.role not in NOT_TEXT_ROLES), None)
        if target is None:
            continue
        for row in rows:
            initial = re.sub(r"[\W\d_]", "", "".join(
                node_text(line) for block in row.cells[index].blocks for line in block.lines))
            _mark_acrostic(row.cells[target], initial[:1])


#: Words in a header that do not tell one column from another.
_GENERIC_HEADER_WORDS = frozenset({
    "of", "the", "from", "by", "and", "a", "an", "in", "also", "but", "trans", "tanslation",
    "translation", "source", "adaptation", "transliteration", "romanization", "romanized",
    "version", "text",
})


def _variant_name(header: str) -> str:
    """The words of a header that tell its column apart: "1914 Rhyming Translation, Rose P.
    Stokes & Helena Frank (English)" -> ``1914_rhyming_rose``. Language names are left out."""
    from opensiddur.importer.opensiddur_org.languages import LANGUAGE_NAMES

    folded = "".join(c for c in unicodedata.normalize("NFKD", header.lower()) if not unicodedata.combining(c))
    language_words = {w for name in LANGUAGE_NAMES for w in re.findall(r"[a-z]+", name)}
    words = [w for w in re.findall(r"[a-z0-9]+", folded)
             if w not in _GENERIC_HEADER_WORDS and w not in language_words and len(w) > 1]
    return "_".join(words[:3])


def _base_letter(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))[:1]


def _mark_acrostic(cell: Cell, initial: str) -> None:
    """Mark the first letter of ``cell`` as an acrostic if it is ``initial``."""
    if not initial or not cell.blocks or not cell.blocks[0].lines:
        return
    block = cell.blocks[0]
    line = block.lines[0]
    if not line or not isinstance(line[0], Text) or _base_letter(line[0].text) != _base_letter(initial):
        return
    text = line[0].text
    end = 1
    while end < len(text) and unicodedata.combining(text[end]):
        end += 1
    marked: Line = (Span("acrostic", (Text(text[:end]),)), *((Text(text[end:]),) if text[end:] else ()), *line[1:])
    cell.blocks[0] = Block(block.kind, (marked, *block.lines[1:]))


#: Colour meanings (``post_decisions.yaml``) -> the span kind they become. A meaning's second
#: word is its particular: the melody, the language, who supplied the words.
_COLOUR_MEANINGS = {
    "acrostic": "acrostic",
    "quotation": "quotation",
    "language": "lang",
    "supplied": "supplied",
    "cantillation": "cantillation",
    "amendment": "variant",
    "alternative": "variant",
    "hidden": "concealed",
    "ketiv": "ketiv",
}
#: Alternatives named for a feature that already exists: a gender, or a rite.
_GENDERS = frozenset({"male", "female"})
_RITES = frozenset({"ashkenaz", "sepharad", "edot_hamizrach", "teimani_baladi"})


def colour_kind(meaning: str) -> str | None:
    """The span kind a colour meaning becomes, or None to drop the colour.

    ``amendment`` -> ``variant:amended``; ``alternative saadia`` -> ``variant:saadia``;
    ``alternative female`` -> ``gender:female``; ``alternative ashkenaz`` -> ``rite:ashkenaz``;
    ``language arc`` -> ``lang:arc``; ``cantillation job`` -> ``cantillation:job``.
    """
    word, _, particular = meaning.strip().partition(" ")
    if word == "none":
        return None
    if word not in _COLOUR_MEANINGS:
        raise ValueError(f"unknown colour meaning {meaning!r}")
    kind = _COLOUR_MEANINGS[word]
    if word == "amendment":
        return "variant:amended"
    if word == "alternative":
        if particular in _GENDERS:
            return f"gender:{particular}"
        if particular in _RITES:
            return f"rite:{particular}"
        return f"variant:{particular or 'alternative'}"
    return f"{kind}:{particular}" if particular else kind


def apply_colours(post: Post, meanings: dict[str, str]) -> None:
    """Give the post's coloured spans the meanings decided for them; colours with no meaning
    are left as they are and listed in ``post.undecided_colours``.

    A ketiv takes the word before it as its reading. An amendment followed by ``| word``
    offers the word as the original it replaces (post 19667), the opposite reading.
    """
    def convert_line(line: Line) -> Line:
        out: list[Node] = []
        nodes = list(line)
        i = 0
        while i < len(nodes):
            node = nodes[i]
            if isinstance(node, Span):
                children = convert_line(node.children)
                if node.kind.startswith(COLOUR_KIND):
                    colour = node.kind[len(COLOUR_KIND):]
                    if colour not in meanings:
                        post.undecided_colours.add(colour)
                        out.append(Span(node.kind, children))
                        i += 1
                        continue
                    kind = colour_kind(meanings[colour])
                    if kind is None:
                        out.extend(children)
                    elif kind == "ketiv":
                        out.extend(_ketiv(out, children))
                    else:
                        out.append(Span(kind, children))
                        if kind.startswith("variant:") and i + 1 < len(nodes) and isinstance(nodes[i + 1], Text):
                            replaced = re.match(r"^(\s*\|\s*)(\S+)(.*)$", nodes[i + 1].text, re.S)
                            if replaced:
                                out.append(Text(" "))
                                out.append(Span(kind + ":original", (Text(replaced.group(2)),)))
                                if replaced.group(3):
                                    out.append(Text(replaced.group(3)))
                                i += 2
                                continue
                else:
                    out.append(Span(node.kind, children))
            elif isinstance(node, FootnoteRef):
                out.append(FootnoteRef(node.number, convert_line(node.note)))
            else:
                out.append(node)
            i += 1
        return tuple(out)

    for table in post.tables:
        for row in table.rows:
            for cell in row.cells:
                cell.blocks = [Block(b.kind, tuple(convert_line(line) for line in b.lines)) for b in cell.blocks]
    # In the post's own words a colour only shows which colour it is explaining ("Adapted text
    # in GREEN above"): it is dropped.
    post.intro = [_uncoloured(line) for line in post.intro]
    post.notes = [_uncoloured(line) for line in post.notes]
    post.essay = [item if isinstance(item, int) else _uncoloured(item) for item in post.essay]


def _uncoloured(line: Line) -> Line:
    out: list[Node] = []
    for node in line:
        if isinstance(node, FootnoteRef):
            out.append(FootnoteRef(node.number, _uncoloured(node.note)))
        elif isinstance(node, Span):
            children = _uncoloured(node.children)
            if node.kind.startswith(COLOUR_KIND):
                out.extend(children)
            else:
                out.append(Span(node.kind, children))
        else:
            out.append(node)
    return tuple(out)


def _ketiv(before: list[Node], written: tuple[Node, ...]) -> list[Node]:
    """A written form and the word before it, its reading, as one choice. With no word before
    it, the written form stands alone."""
    if before and isinstance(before[-1], Text):
        match = re.match(r"^(.*?)(\S+)(\s*)$", before[-1].text, re.S)
        if match:
            before.pop()
            prefix = [Text(match.group(1))] if match.group(1) else []
            return [*prefix, Span("choice", (Span("written", written), Span("read", (Text(match.group(2)),)))),
                    *([Text(match.group(3))] if match.group(3) else [])]
    return [Span("written", written)]


def load_post(path: Path, decisions: PostDecisions | None = None) -> Post:
    """The post at ``path``, read with the decisions of ``post_decisions.yaml`` unless others
    are given."""
    return parse_post(json.loads(path.read_text(encoding="utf-8")),
                      default_post_decisions() if decisions is None else decisions)


def normalize_key(text: str) -> str:
    """A comparison key: NFKD, marks dropped, case-folded, letters and digits only."""
    stripped = "".join(c for c in unicodedata.normalize("NFKD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]+", " ", stripped.casefold()).strip()
