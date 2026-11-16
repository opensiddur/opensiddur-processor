"""Build the JLPTEI files of a Sefaria work's Hebrew and English projects.

Each language's project is laid out as the house style lays out a siddur (Birnbaum, Asher):

- ``index.xml``: the full header, with the source bibl, and a ``siddur:siddur`` division that
  transcludes each top-level part of the book.
- **Structure files**, one for each node of Sefaria's schema, named by the node's ``siddur:``
  URN (``structure/<work>.yaml``). An inner node transcludes its children. A leaf holds its
  heading, the rubrics between its texts and a transclusion of each text, in order: a
  ``siddur:`` division holds no words of its own besides headings and rubrics.
- **Text files**, one for each text the work sets (``match.py``), named by its URN: a
  ``tei:div`` with that URN, the text's heading, and the text with a phrase milestone
  (``metsudah:<text path>/<n>``, ``phrases.py``) before each phrase. A text printed again later
  in the book is transcluded from its first printing and has no second file.

Both projects have the same files and the same URNs, so the English sets beside the Hebrew,
phrase by phrase. A rubric Metsudah gives only in English, opposite an empty Hebrew segment, is
in the English project only.

Rendering:

- Hebrew is stored decomposed (``util/hebrew.to_nfkd``).
- Bold, the opening words of a prayer, is presentation and is dropped.
- Small Hebrew print (a quieter line, a seasonal insertion) is ``tei:hi rend="small"``; an
  unpointed label before the words it governs (``לְר"ח:``) is an instruction.
- English italic is ``tei:hi rend="italic"``; ``<span>`` (Hebrew inside English) is
  ``tei:foreign xml:lang="he"``; a line break is a space.
- A footnote is a ``tei:anchor`` in the text and a ``tei:note type="commentary"`` in the file's
  ``tei:standOff``; inside a rubric, its anchor follows the rubric.
"""

from __future__ import annotations

import html
from collections.abc import Iterable
from dataclasses import dataclass, field

from opensiddur.importer.sefaria.align import Pair
from opensiddur.importer.sefaria.blocks import Heading, Item, Rubric, TextBlock, is_phrase
from opensiddur.importer.sefaria.markup import (
    Break,
    EnglishKind,
    Footnote,
    Node,
    Styled,
    Text,
    english_kind,
    leading_label,
    plain_text,
)
from opensiddur.importer.sefaria.phrases import phrase_urn
from opensiddur.importer.sefaria.works import Work
from opensiddur.importer.util.hebrew import to_nfkd
from opensiddur.importer.util.incipit import TEXT_PREFIX
from opensiddur.importer.util.tei_project import PROJECT_SOURCE_BIBL_ID, tei_document

SIDDUR_PREFIX = f"{TEXT_PREFIX}siddur:"
LICENCE_NAMES = {
    "https://creativecommons.org/licenses/by/3.0/": "Creative Commons Attribution 3.0 Unported",
}
SEFARIA_URL = "https://www.sefaria.org"


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def attr(text: str) -> str:
    return html.escape(text, quote=True)


def siddur_urn(path: str) -> str:
    return f"{SIDDUR_PREFIX}{path}"


def file_stem(urn: str) -> str:
    """A file named by a URN's path: ``prayer:amidah/avot`` -> ``amidah_avot``; a ``siddur:``
    URN keeps the prefix ``siddur_`` so that it can never meet a text's file."""
    namespace, _, path = urn[len(TEXT_PREFIX):].partition(":")
    stem = path.replace("/", "_")
    return f"siddur_{stem}" if namespace == "siddur" else stem


# --------------------------------------------------------------------------------------------
# Inline content
# --------------------------------------------------------------------------------------------


@dataclass
class Notes:
    """The footnotes a file anchors, numbered within the file."""

    prefix: str
    entries: list[tuple[str, tuple[Node, ...]]] = field(default_factory=list)

    def anchor(self, note: Footnote) -> str:
        xml_id = f"{self.prefix}_{len(self.entries) + 1}"
        self.entries.append((xml_id, note.children))
        return f'<tei:anchor xml:id="{xml_id}"/>'


def _text(text: str, lang: str) -> str:
    return esc(to_nfkd(text) if lang == "he" else text)


def render(nodes: Iterable[Node], lang: str, notes: Notes | None, *, in_note: bool = False) -> str:
    """Inline nodes as TEI. In a note (``in_note``) a footnote's anchor cannot be set, and the
    caller sets it after the note (:func:`footnotes_in`)."""
    out: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            out.append(_text(node.text, lang))
        elif isinstance(node, Break):
            out.append(" ")
        elif isinstance(node, Footnote):
            if notes is not None and not in_note:
                out.append(notes.anchor(node))
        elif isinstance(node, Styled):
            inner = render(node.children, lang, notes, in_note=in_note)
            if node.style == "bold":
                out.append(inner)
            elif node.style == "italic":
                out.append(f'<tei:hi rend="italic">{inner}</tei:hi>' if lang != "he" else inner)
            elif node.style in ("small", "large"):
                out.append(f'<tei:hi rend="{node.style}">{inner}</tei:hi>' if not in_note else inner)
            elif node.style == "superscript":
                out.append(f'<tei:hi rend="superscript">{inner}</tei:hi>')
            elif node.style == "foreign":
                hebrew = render(node.children, "he", notes, in_note=in_note)
                out.append(f'<tei:foreign xml:lang="he">{hebrew}</tei:foreign>')
            else:  # pragma: no cover - markup.py produces no other style
                out.append(inner)
    return "".join(out)


def footnotes_in(nodes: Iterable[Node]) -> list[Footnote]:
    found: list[Footnote] = []
    for node in nodes:
        if isinstance(node, Footnote):
            found.append(node)
        elif isinstance(node, Styled):
            found.extend(footnotes_in(node.children))
    return found


def _trim(xml: str) -> str:
    return " ".join(xml.split())


def instruction(nodes: tuple[Node, ...], lang: str, notes: Notes | None, *, kind: str = "instruction") -> str:
    """A rubric: its words as a note, then the anchors of its footnotes."""
    body = _trim(render(nodes, lang, notes, in_note=True))
    if not body:
        return ""
    anchors = "".join(notes.anchor(n) for n in footnotes_in(nodes)) if notes is not None else ""
    return f'<tei:note type="{kind}" xml:lang="{lang}">{body}</tei:note>{anchors}'


def rubric_xml(pair: Pair, lang: str, notes: Notes | None) -> str:
    """A rubric pair in one language: English printed whole in bold is a description (what
    the text is, "1) the existence of God"), anything else an instruction."""
    nodes = pair.he if lang == "he" else pair.en
    if not plain_text(nodes):
        return ""
    kind = "description" if lang == "en" and english_kind(nodes) is EnglishKind.HEADING else "instruction"
    return instruction(nodes, lang, notes, kind=kind)


def phrase_xml(pair: Pair, lang: str, notes: Notes, milestone: str | None) -> str:
    nodes = pair.he if lang == "he" else pair.en
    if not plain_text(nodes) and not footnotes_in(nodes):
        return ""
    prefix = ""
    if lang == "he":
        label, nodes = leading_label(nodes)
        if label is not None:
            prefix = instruction((label,), lang, notes) + " "
    mark = f'<tei:milestone unit="phrase" corresp="{attr(milestone)}"/>' if milestone else ""
    return f"{mark}{prefix}{_trim(render(nodes, lang, notes))}"


def head_xml(pair: Pair, lang: str, notes: Notes | None, *, element: str = "head") -> str:
    """A heading (or, in a structure file, a ``tei:label``), with its footnotes anchored."""
    nodes = pair.he if lang == "he" else pair.en
    if not plain_text(nodes):
        return ""
    return f'<tei:{element} xml:lang="{lang}">{_trim(render(nodes, lang, notes))}</tei:{element}>'


#: Closes a phrase's scope without opening another (SIDDUR_URN_SCHEME.md, "Ending a scope").
PHRASE_END = '<tei:milestone unit="phrase"/>'


# --------------------------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------------------------


def standoff(notes: Notes, lang: str) -> str:
    if not notes.entries:
        return ""
    entries = "".join(
        f'<tei:note type="commentary" target="#{xml_id}" xml:lang="{lang}">'
        f"<tei:p>{_trim(render(body, lang, None, in_note=True))}</tei:p></tei:note>"
        for xml_id, body in notes.entries
    )
    return f'<tei:standOff type="notes">{entries}</tei:standOff>'


def text_body(urn: str, block: TextBlock, phrase_numbers: list[int], lang: str, notes: Notes) -> str:
    """A text's division: its heading, then its phrases and the rubrics among them."""
    head = head_xml(block.head, lang, notes) if block.head is not None else ""
    numbers = iter(phrase_numbers)
    parts: list[str] = []
    phrase_open = False
    for pair in block.pairs:
        if is_phrase(pair):
            number = next(numbers)
            nodes = pair.he if lang == "he" else pair.en
            milestone = phrase_urn(urn, number) if plain_text(nodes) else None
            xml = phrase_xml(pair, lang, notes, milestone)
            if milestone:
                phrase_open = True
            elif phrase_open and xml:
                # Words with no counterpart in the other language: not the last phrase's.
                parts.append(PHRASE_END)
                phrase_open = False
        else:
            # A rubric is not the phrase before it. The scope is closed in both languages,
            # whichever the rubric is printed in, so that the two divide alike.
            if phrase_open:
                parts.append(PHRASE_END)
                phrase_open = False
            xml = rubric_xml(pair, lang, notes)
        if xml:
            parts.append(xml)
    content = "\n".join(parts)
    paragraph = f"<tei:p>{content}</tei:p>" if content else ""
    return f'<tei:body><tei:div corresp="{attr(urn)}">{head}{paragraph}</tei:div></tei:body>'


def leaf_body(urn: str, titles: tuple[str, str], items: list[Item], text_urns: dict[int, str],
              lang: str, notes: Notes) -> str:
    """A leaf's structure division: its heading, then its rubrics, headings and texts.
    ``text_urns`` maps each text block (by ``id``) to its URN."""
    title = titles[1] if lang == "he" else titles[0]
    parts = [f'<tei:head xml:lang="{lang}">{_text(title, lang)}</tei:head>'] if title else []
    for item in items:
        if isinstance(item, Rubric):
            parts.extend(x for x in (rubric_xml(pair, lang, notes) for pair in item.pairs) if x)
        elif isinstance(item, Heading):
            label = head_xml(item.pair, lang, notes, element="label")
            if label:
                parts.append(label)
        elif isinstance(item, TextBlock):
            parts.append(f'<j:transclude type="external" target="{attr(text_urns[id(item)])}"/>')
    return f'<tei:body><tei:div corresp="{attr(urn)}">{"".join(parts)}</tei:div></tei:body>'


def node_body(urn: str, titles: tuple[str, str], children: list[str], lang: str) -> str:
    """An inner node's division: its heading and a transclusion of each child."""
    title = titles[1] if lang == "he" else titles[0]
    head = f'<tei:head xml:lang="{lang}">{_text(title, lang)}</tei:head>' if title else ""
    transclusions = "".join(f'<j:transclude type="external" target="{attr(c)}"/>' for c in children)
    return f'<tei:body><tei:div corresp="{attr(urn)}">{head}{transclusions}</tei:div></tei:body>'


def index_body(work: Work, children: list[str], lang: str) -> str:
    title = work.title_he if lang == "he" else work.title_en
    head = f'<tei:head xml:lang="{lang}">{_text(title, lang)}</tei:head>'
    transclusions = "".join(f'<j:transclude type="external" target="{attr(c)}"/>' for c in children)
    return (f'<tei:body><tei:div corresp="{SIDDUR_PREFIX}siddur">{head}{transclusions}</tei:div>'
            "</tei:body>")


# --------------------------------------------------------------------------------------------
# Headers
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceInfo:
    """What the header says about the copy imported (from the download's manifest)."""

    last_export: str
    version_url: dict[str, str]
    md5: dict[str, str]


def _publication(work: Work) -> str:
    name = LICENCE_NAMES.get(work.licence, work.licence)
    return (
        "<tei:publicationStmt>"
        '<tei:distributor><tei:ref target="https://opensiddur.org">Open Siddur Project</tei:ref></tei:distributor>'
        '<tei:availability status="free">'
        f'<tei:licence target="{attr(work.licence)}">{esc(name)}</tei:licence>'
        "<tei:p>Published by Sefaria under CC-BY, which Sefaria defines as Creative Commons "
        "Attribution 3.0.</tei:p>"
        "</tei:availability>"
        "</tei:publicationStmt>"
    )


def _titles(work: Work, lang: str) -> str:
    if lang == "he":
        return (f'<tei:title type="main" xml:lang="he">{esc(work.title_he)}</tei:title>'
                f'<tei:title type="alt" xml:lang="en">{esc(work.title_en)}</tei:title>')
    return (f'<tei:title type="main" xml:lang="en">{esc(work.title_en)}</tei:title>'
            '<tei:title type="sub" xml:lang="en">English translation</tei:title>'
            f'<tei:title type="alt" xml:lang="he">{esc(work.title_he)}</tei:title>')


def source_bibl(work: Work, lang: str, info: SourceInfo) -> str:
    version_title = work.versions[lang]
    translator = (f'<tei:respStmt><tei:resp key="trl">Translated by</tei:resp>'
                  f"<tei:name>{esc(work.translator)}</tei:name></tei:respStmt>")
    place = f"<tei:pubPlace>{esc(work.place)}</tei:pubPlace>" if work.place else ""
    accessed = info.last_export[:10]
    other = "en" if lang == "he" else "he"
    return (
        f'<tei:bibl xml:id="{PROJECT_SOURCE_BIBL_ID}">'
        f'<tei:title xml:lang="en">{esc(work.title_en)}</tei:title>'
        f'<tei:title xml:lang="he">{esc(work.title_he)}</tei:title>'
        f"{translator}"
        f"<tei:publisher>{esc(work.publisher)}</tei:publisher>{place}"
        f'<tei:date when="{attr(work.date)}">{esc(work.date)}</tei:date>'
        f'<tei:distributor><tei:ref target="{SEFARIA_URL}">Sefaria</tei:ref></tei:distributor>'
        f'<tei:date type="accessed" when="{attr(accessed)}">{esc(accessed)}</tei:date>'
        f'<tei:idno type="url">{esc(info.version_url[lang])}</tei:idno>'
        f'<tei:idno type="sefaria">{esc(version_title)}</tei:idno>'
        f"<tei:note>Rite: {esc(work.rite)}</tei:note>"
        f"<tei:note>Digitized by Sefaria as the {'Hebrew' if lang == 'he' else 'English'} version "
        f"“{esc(version_title)}” of {esc(work.title)}; its "
        f"{'English translation' if lang == 'he' else 'Hebrew text'} is the project "
        f"{esc(work.projects[other])}.</tei:note>"
        '<tei:note type="encoding">Converted from the Sefaria export of '
        f"{esc(info.last_export)} (md5 {esc(info.md5[lang])}), one phrase of the linear layout "
        "to a phrase milestone. See specs/SEFARIA_IMPORT.md in opensiddur-processor.</tei:note>"
        "</tei:bibl>"
    )


def index_header(work: Work, lang: str, info: SourceInfo) -> str:
    return (
        "<tei:teiHeader><tei:fileDesc>"
        f"<tei:titleStmt>{_titles(work, lang)}</tei:titleStmt>"
        f"{_publication(work)}"
        f"<tei:sourceDesc>{source_bibl(work, lang, info)}</tei:sourceDesc>"
        "</tei:fileDesc></tei:teiHeader>"
    )


def document_header(work: Work, lang: str, title: str) -> str:
    project = work.projects[lang]
    return (
        "<tei:teiHeader><tei:fileDesc>"
        f'<tei:titleStmt><tei:title type="main" xml:lang="{lang}">{_text(title, lang)}</tei:title></tei:titleStmt>'
        f"{_publication(work)}"
        f'<tei:sourceDesc><tei:bibl><tei:ptr target="/{project}/index#{PROJECT_SOURCE_BIBL_ID}"/>'
        "</tei:bibl></tei:sourceDesc>"
        "</tei:fileDesc></tei:teiHeader>"
    )


def document(header: str, body: str, lang: str, notes: Notes | None = None) -> str:
    return tei_document(header, body, lang=lang, standoff_xml=standoff(notes, lang) if notes else "")
