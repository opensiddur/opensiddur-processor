"""The HTML inside a Sefaria segment, as inline nodes, and what kind of segment it is.

Sefaria's Metsudah segments use a handful of tags:

========================================  ====================================================
markup                                    meaning
========================================  ====================================================
``<b>``                                   the opening words of a prayer, an emphasized line,
                                          or (unpointed, the whole segment) a heading
``<small>``                               Hebrew: a quieter line, a seasonal insertion, or
                                          (unpointed) a label; English: a rubric
``<i>``                                   English: a transliterated word, or a rubric
``<big>``                                 a larger heading
``<span>`` (no class)                     Hebrew words inside the English
``<br>``                                  a line break
``<sup class="footnote-marker">`` then    a footnote: its marker, then its text, which may
``<i class="footnote">``                  hold ``<i>`` and ``<br>`` of its own
========================================  ====================================================

:func:`parse_segment` reads a segment into :class:`Text`, :class:`Styled`, :class:`Break` and
:class:`Footnote` nodes; :func:`hebrew_kind` and :func:`english_kind` say what a segment is,
which is what decides where it goes (``blocks.py``). Pointing decides between a Hebrew heading
and Hebrew text that happens to be bold: Metsudah's headings (``אבות``) are unpointed, its
liturgy pointed.
"""

from __future__ import annotations

import enum
import logging
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache

from lxml import etree, html

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Styled:
    """``style`` is one of bold, italic, small, large, foreign (Hebrew inside English) or
    superscript."""

    style: str
    children: tuple["Node", ...]


@dataclass(frozen=True)
class Break:
    pass


@dataclass(frozen=True)
class Correction:
    """A misprint and its correction (``corrections.yaml``): the corrected words are the text's
    words wherever words are compared, and both are written, as ``tei:sic`` and ``tei:corr``."""

    sic: str
    corr: str


@dataclass(frozen=True)
class Footnote:
    marker: str
    children: tuple["Node", ...]


Node = Text | Styled | Break | Footnote | Correction

_TAG_STYLES = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic", "small": "small",
               "big": "large", "span": "foreign", "sup": "superscript"}


def _classes(element: etree._Element) -> set[str]:
    return set((element.get("class") or "").split())


def _children(element: etree._Element) -> tuple[Node, ...]:
    nodes: list[Node] = []
    if element.text:
        nodes.append(Text(element.text))
    children = list(element)
    i = 0
    while i < len(children):
        child = children[i]
        if not isinstance(child.tag, str):  # a comment or processing instruction
            if child.tail:
                nodes.append(Text(child.tail))
            i += 1
            continue
        tag = child.tag.lower()
        if tag == "sup" and "footnote-marker" in _classes(child):
            marker = child.text_content().strip()
            body: tuple[Node, ...] = ()
            nxt = children[i + 1] if i + 1 < len(children) else None
            # The note follows its marker directly; text between the two would be lost.
            if (nxt is not None and isinstance(nxt.tag, str) and nxt.tag.lower() == "i"
                    and "footnote" in _classes(nxt) and not (child.tail or "").strip()):
                body = _children(nxt)
                nodes.append(Footnote(marker, body))
                if nxt.tail:
                    nodes.append(Text(nxt.tail))
                i += 2
                continue
            logger.warning("a footnote marker %r has no footnote after it", marker)
            nodes.append(Footnote(marker, body))
        elif tag == "i" and "footnote" in _classes(child):
            logger.warning("a footnote with no marker: %r", child.text_content()[:40])
            nodes.append(Footnote("", _children(child)))
        elif tag == "br":
            nodes.append(Break())
        elif tag in _TAG_STYLES:
            nodes.append(Styled(_TAG_STYLES[tag], _children(child)))
        else:
            logger.warning("unknown tag <%s> in a segment; its text is kept", tag)
            nodes.extend(_children(child))
        if child.tail:
            nodes.append(Text(child.tail))
        i += 1
    return tuple(nodes)


@lru_cache(maxsize=None)
def parse_segment(segment: str) -> tuple[Node, ...]:
    if not segment.strip():
        return ()
    root = html.fragment_fromstring(segment, create_parent="div")
    return _children(root)


def walk(nodes: Iterable[Node], *, footnotes: bool = False) -> Iterator[Node]:
    """Every node, depth first; a footnote's text only when ``footnotes``."""
    for node in nodes:
        yield node
        if isinstance(node, Styled):
            yield from walk(node.children, footnotes=footnotes)
        elif isinstance(node, Footnote) and footnotes:
            yield from walk(node.children, footnotes=footnotes)


def plain_text(nodes: Iterable[Node]) -> str:
    """The words of a segment, without its footnotes, whitespace collapsed."""
    parts: list[str] = []
    for node in walk(nodes):
        if isinstance(node, Text):
            parts.append(node.text)
        elif isinstance(node, Correction):
            parts.append(node.corr)
        elif isinstance(node, Break):
            parts.append(" ")
    return " ".join("".join(parts).split())


_POINTING = re.compile("[ְ-ׇּׁׂ]")
_HEBREW_LETTER = re.compile("[א-ת]")


def is_pointed(text: str) -> bool:
    return bool(_POINTING.search(text))


def has_hebrew(text: str) -> bool:
    return bool(_HEBREW_LETTER.search(text))


def _content(nodes: tuple[Node, ...]) -> tuple[Node, ...]:
    """The nodes that carry words: without footnotes, breaks and blank text."""
    return tuple(n for n in nodes if not isinstance(n, (Footnote, Break))
                 and not (isinstance(n, Text) and not n.text.strip()))


def wholly(nodes: tuple[Node, ...], styles: set[str]) -> bool:
    """Whether every word of the segment is inside one of ``styles``, at any depth."""
    content = _content(nodes)
    if not content:
        return False
    for node in content:
        if not isinstance(node, Styled):
            return False
        if node.style not in styles and not wholly(node.children, styles):
            return False
    return True


def opens_with(nodes: tuple[Node, ...], style: str) -> bool:
    """Whether the segment's first words are in ``style`` (possibly inside another style)."""
    content = _content(nodes)
    if not content:
        return False
    first = content[0]
    if not isinstance(first, Styled):
        return False
    return first.style == style or opens_with(first.children, style)


class HebrewKind(enum.Enum):
    EMPTY = "empty"
    #: an unpointed label printed whole in bold or small: a heading or a rubric
    LABEL = "label"
    #: pointed text whose first words are bold: the opening of a prayer
    BOLD_OPENING = "bold_opening"
    TEXT = "text"


class EnglishKind(enum.Enum):
    EMPTY = "empty"
    #: printed whole in bold: a heading
    HEADING = "heading"
    #: printed whole in small or italic: a rubric (or, beside Hebrew, a translated label)
    RUBRIC = "rubric"
    TEXT = "text"


#: A label is a few words; a long unpointed bold or small passage is text.
MAX_LABEL_WORDS = 8


#: A text's number, as the Selichot numbers its selichot: a Hebrew numeral and a stop
#: (``א.`` to ``ק.``) before the selichah's description, title or nothing.
NUMBER = re.compile(r"\s*[\u05d0-\u05ea]{1,3}\.(\s|$)")


def is_numbered(nodes: tuple[Node, ...]) -> bool:
    """A segment that numbers the text after it: ``יא. <small>חתום שמעון בר יצחק</small>``,
    ``ד. <b>במוצאי מנוחה</b>``, ``נז.`` -- the numeral, then nothing pointed."""
    text = plain_text(nodes)
    return bool(NUMBER.match(text)) and not is_pointed(text)


def hebrew_kind(nodes: tuple[Node, ...]) -> HebrewKind:
    text = plain_text(nodes)
    if not text:
        return HebrewKind.EMPTY
    if is_numbered(nodes):
        return HebrewKind.LABEL
    if has_hebrew(text) and not is_pointed(text) and wholly(nodes, {"small"}):
        # An instruction in small print, however long ("ש"ץ מתחיל בקול רם והצבור עונין
        # אחריו פסוק אחר פסוק ..."): the book prints its texts pointed.
        return HebrewKind.LABEL
    if (has_hebrew(text) and not is_pointed(text) and len(text.split()) <= MAX_LABEL_WORDS
            and wholly(nodes, {"bold", "small", "large"})):
        return HebrewKind.LABEL
    if opens_with(nodes, "bold"):
        return HebrewKind.BOLD_OPENING
    return HebrewKind.TEXT


def english_kind(nodes: tuple[Node, ...]) -> EnglishKind:
    if not plain_text(nodes):
        return EnglishKind.EMPTY
    if wholly(nodes, {"bold", "large"}):
        return EnglishKind.HEADING
    if wholly(nodes, {"small", "italic"}):
        return EnglishKind.RUBRIC
    return EnglishKind.TEXT


#: A label set before the words it governs ("לְר"ח:") is a word or two and a colon.
MAX_LEADING_LABEL_WORDS = 3


def leading_label(nodes: tuple[Node, ...]) -> tuple[Node | None, tuple[Node, ...]]:
    """A Hebrew segment that opens with an unpointed small label ending in a colon
    (``<small>לְר"ח:</small> רֹאשׁ הַחֹדֶשׁ הַזֶּה``): the label, and the rest."""
    content = _content(nodes)
    if not content:
        return None, nodes
    first = content[0]
    if isinstance(first, Styled) and first.style == "small":
        label = plain_text(first.children)
        if label.endswith(":") and len(label.split()) <= MAX_LEADING_LABEL_WORDS:
            index = nodes.index(first)
            rest = nodes[index + 1:]
            if plain_text(rest):
                return first, rest
    return None, nodes
