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
import re

from lxml import etree
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from typing import Any

from opensiddur.importer.sefaria.align import Pair
from opensiddur.importer.sefaria.blocks import Heading, Item, Rubric, TextBlock, is_heading, is_phrase
from opensiddur.importer.sefaria.markup import (
    Break,
    Correction,
    EnglishKind,
    HebrewKind,
    Footnote,
    Node,
    Styled,
    Text,
    english_kind,
    leading_label,
    plain_text,
)
from opensiddur.importer.sefaria.conditions import Conditions, LeafGate, condition_xml, negated_xml
from opensiddur.importer.sefaria.phrases import phrase_urn
from opensiddur.importer.sefaria.works import Work
from opensiddur.importer.util.hebrew import to_nfkd
from opensiddur.importer.util.incipit import TEXT_PREFIX, words
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


def file_stem(urn: str, clashes: Collection[str] = frozenset()) -> str:
    """A file named by a URN's path: ``prayer:amidah/avot`` -> ``amidah_avot``; a ``siddur:``
    URN keeps the prefix ``siddur_`` so that it can never meet a text's file. A path two text
    namespaces use (``clashes``) is told apart as its phrases are: ``poem_hamavdil_...``."""
    namespace, _, path = urn[len(TEXT_PREFIX):].partition(":")
    if path in clashes and namespace != "prayer":
        path = f"{namespace}/{path}"
    stem = path.replace("/", "_").replace("-", "_")  # a run of verses: psalms_3_2_9
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
        elif isinstance(node, Correction):
            out.append(f"<tei:choice><tei:sic>{_text(node.sic, lang)}</tei:sic>"
                       f"<tei:corr>{_text(node.corr, lang)}</tei:corr></tei:choice>")
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


def conditional_open(xml_id: str, note: str, condition: str) -> str:
    """A ``j:conditional`` whose note is a rubric (``instruction``): the anchors of the rubric's
    footnotes, which the conditional cannot hold, follow it."""
    head, end, anchors = note.rpartition("</tei:note>")
    return f'<j:conditional xml:id="{xml_id}">{head}{end}{condition}</j:conditional>{anchors}'


def rubric_xml(pair: Pair, lang: str, notes: Notes | None) -> str:
    """A rubric pair in one language: English printed whole in bold is a description (what
    the text is, "1) the existence of God"), anything else an instruction."""
    nodes = pair.he if lang == "he" else pair.en
    if not plain_text(nodes):
        return ""
    # A heading inside a text (the text joined across it) names the passage after it.
    kind = ("description" if is_heading(pair) or (lang == "en" and english_kind(nodes) is EnglishKind.HEADING)
            else "instruction")
    return instruction(nodes, lang, notes, kind=kind)


def phrase_xml(pair: Pair, lang: str, notes: Notes, milestone: str | None, *, label: bool = True) -> str:
    """A phrase in one language. Its Hebrew label (``לְר"ח:``) is an instruction before it,
    unless ``label`` is false: the label is then the note of the phrase's conditional."""
    nodes = pair.he if lang == "he" else pair.en
    mark = f'<tei:milestone unit="phrase" corresp="{attr(milestone)}"/>' if milestone else ""
    if not plain_text(nodes) and not footnotes_in(nodes):
        return mark
    prefix = ""
    if lang == "he":
        found, nodes = leading_label(nodes)
        if found is not None and label:
            prefix = instruction((found,), lang, notes) + " "
    return f"{mark}{prefix}{_trim(render(nodes, lang, notes))}"


def head_xml(pair: Pair, lang: str, notes: Notes | None, *, element: str = "head") -> str:
    """A heading (or, in a structure file, a ``tei:label``), with its footnotes anchored."""
    nodes = pair.he if lang == "he" else pair.en
    if not plain_text(nodes):
        return ""
    return f'<tei:{element} xml:lang="{lang}">{_trim(render(nodes, lang, notes))}</tei:{element}>'


#: Closes a phrase's scope without opening another (SIDDUR_URN_SCHEME.md, "Ending a scope").
PHRASE_END = '<tei:milestone unit="phrase"/>'
#: Closes a verse's scope.
VERSE_END = '<tei:milestone unit="verse"/>'
#: How a phrase that ends a verse of scripture ends (sof pasuq, or the colon prayer books use).
VERSE_ENDINGS = (":", "\u05c3")


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


CONDITION_PREFIX = "urn:x-opensiddur:condition:"


def variant_urn(text_urn: str, name: str) -> str:
    """The condition URN of one variant of a text (``schema/JLPTEI-3.md``, textual variants):
    the text's path with the variant's name, in the ``condition:`` namespace."""
    return text_urn.replace(TEXT_PREFIX, CONDITION_PREFIX, 1) + f"/{name}"


def variant_fs(features: list[tuple[str, bool]]) -> str:
    fs = "".join(f'<tei:f name="{attr(name)}"><tei:binary value="{"true" if value else "false"}"/></tei:f>'
                 for name, value in features)
    return f'<tei:fs type="opensiddur:variant">{fs}</tei:fs>'


@dataclass(frozen=True)
class VariantPrinting:
    """A later printing of a text with words of its own (``match.py``, kind "variant")."""

    name: str
    block: TextBlock
    numbers: list[int]
    #: texts the collection names among the variant's own words: first phrase number -> URN
    parts: dict[int, str] = field(default_factory=dict)


class _TextWriter:
    """A text's phrases, rubrics and conditional passages, in one language.

    A condition rubric (``conditions.yaml``) opens a conditional, its note the rubric, which the
    next rubric closes, or the end of the passage it is in -- or, where the passage opens with a
    parenthesis, the phrase that closes it."""

    def __init__(self, urn: str, lang: str, notes: Notes, conditions: Conditions | None = None,
                 clashes: Collection[str] = frozenset()):
        self.urn, self.lang, self.notes = urn, lang, notes
        #: the paths more than one text namespace uses (``phrases.clashing_paths``)
        self.clashes = clashes
        self.table = conditions or Conditions()
        self.parts: list[str] = []
        self.phrase_open = False
        self.verse_open = False
        self.conditions = 0
        #: the Hebrew document's inline conditionals, numbered apart, so that the two languages'
        #: other conditionals have the same ids
        self.inline = 0
        #: the variant conditionals open, innermost last
        self.open_variants: list[str] = []
        #: the condition rubrics' conditionals open, innermost last: [id, how many variant
        #: conditionals were open when it opened, whether its passage is in parentheses (None:
        #: not known until its first phrase), whether it is to close once it can]
        self.calendars: list[list] = []
        #: an inline alternative that ended the last phrase, and replaces words the next opens
        #: with: (its condition's XML, the replacement)
        self.pending: tuple[str, Any] | None = None

    def next_id(self, kind: str) -> str:
        if kind == "inline":
            self.inline += 1
            return f"inline_{self.inline}"
        self.conditions += 1
        return f"{kind}_{self.conditions}"

    @property
    def calendar(self) -> list | None:
        """The innermost condition rubric's conditional, when it was opened at this level."""
        if self.calendars and self.calendars[-1][1] == len(self.open_variants):
            return self.calendars[-1]
        return None

    def open_calendar(self, pair: Pair, when, through: tuple[str, ...] = ()) -> None:
        self.close_calendar()
        xml_id = self.next_id("when")
        note = instruction(pair.en, "en", self.notes) if self.lang == "en" else ""
        self.parts.append(conditional_open(xml_id, note, condition_xml(when)))
        # [id, depth, parenthesized, to close, the words that end it, the words so far]
        self.calendars.append([xml_id, len(self.open_variants), None, False, through, []])

    def close_calendar(self, *, everything: bool = False) -> None:
        """Close the condition rubric's conditional opened at this level (or, with
        ``everything``, every one): one opened outside a variant conditional that is open closes
        when that one does, so that the conditionals nest."""
        depth = len(self.open_variants)
        while self.calendars and (everything or self.calendars[-1][1] >= depth):
            self.end_phrase()
            self.verse(None)
            self.parts.append(f'<j:endConditional target="#{self.calendars.pop()[0]}"/>')
        if self.calendars and not everything:
            self.calendars[-1][3] = True  # an outer one: to close when its level is reached

    def end_phrase(self) -> None:
        if self.phrase_open:
            self.parts.append(PHRASE_END)
            self.phrase_open = False

    def verse(self, urn: str | None) -> None:
        """Open a verse's scope, or close it (``None``)."""
        if urn is not None:
            self.parts.append(f'<tei:milestone unit="verse" corresp="{attr(urn)}"/>')
            self.verse_open = True
        elif self.verse_open:
            self.parts.append(VERSE_END)
            self.verse_open = False

    def phrase(self, pair: Pair, number: int) -> None:
        # The Hebrew makes the phrase, so both languages mark it, the English even where it
        # leaves the phrase untranslated: the row is then set with an empty English cell,
        # rather than the Hebrew running on into the row before.
        hebrew = plain_text(pair.he)
        current = self.calendar
        if current is not None and current[2] is None:
            current[2] = hebrew.lstrip().startswith("(")
        label, _ = leading_label(pair.he)
        labelled = self.table.for_label(plain_text((label,))) if label is not None else None
        xml_id = None
        if labelled is not None:
            # The phrase is said when its label says (לְר"ח: רֹאשׁ הַחֹדֶשׁ הַזֶּה): the label is
            # the conditional's note.
            self.end_phrase()
            xml_id = self.next_id("when")
            note = instruction((label,), "he", self.notes) if self.lang == "he" else ""
            self.parts.append(conditional_open(xml_id, note, condition_xml(labelled.when)))
        xml = phrase_xml(pair, self.lang, self.notes, phrase_urn(self.urn, number, self.clashes), label=labelled is None)
        if self.lang == "he":
            xml = self.inline_conditions(self._carried(xml))
        self.parts.append(xml)
        self.phrase_open = True
        if xml_id is not None:
            self.end_phrase()
            self.parts.append(f'<j:endConditional target="#{xml_id}"/>')
        if current is not None and current[4]:
            current[5].extend(words(hebrew))
            if tuple(current[5][-len(current[4]):]) == current[4]:
                self.close_calendar()
        elif current is not None and current[2] and ")" in hebrew:
            self.close_calendar()
        elif self.calendars and self.calendars[-1][2] and ")" in hebrew:
            self.calendars[-1][3] = True  # its passage ended inside a variant's conditional

    def inline_conditions(self, xml: str) -> str:
        """A phrase's parenthesized alternatives that open with an abbreviation the table knows
        (``(בעשי"ת הַשָּׁלוֹם)``): each a marked conditional, its abbreviation the note, and the
        words it replaces, where it replaces some, conditional on the opposite."""
        def wrap(match: re.Match[str]) -> str:
            inner_xml = match.group(1)
            inner = html.unescape(re.sub(r"<[^>]*>", "", inner_xml))
            found = self.table.for_inline(inner)
            if found is None:
                return match.group(0)
            tokens = inner.split()
            label = " ".join(tokens[:len(found.label)]).rstrip(":")
            # The alternative's own markup, without the label (which may be set in small type).
            at = inner_xml.find(esc(label))
            alternative = inner_xml[at + len(esc(label)):] if at >= 0 else esc(" ".join(tokens[len(found.label):]))
            alternative = re.sub(r"<(tei:\w+)[^>]*></\1>", "", alternative.lstrip(":")).strip()
            alternative = re.sub(r"^</tei:hi>\s*", "", alternative).lstrip(": ")
            xml_id = self.next_id("inline")
            note = f'<tei:note type="instruction" xml:lang="he">{esc(label)}</tei:note>'
            return (f'<j:conditional xml:id="{xml_id}" type="marked">{note}{condition_xml(found.when)}</j:conditional>'
                    f'{alternative}<j:endConditional target="#{xml_id}"/>')

        saved = self.inline
        out = re.sub(r"\(((?:[^()<]|<[^>]*>)*)\)", wrap, xml)
        for replacement in self.table.replacements:
            while True:
                again = self._replace(out, replacement)
                if again == out:
                    break
                out = again
        if out != xml and not _well_formed(out):
            # Markup that straddles the parenthesis: the phrase is left as the book prints it.
            self.inline = saved
            return xml
        self.pending = self._unreplaced_at_end(out)
        return out

    def _unreplaced_at_end(self, xml: str) -> tuple[str, Any] | None:
        """The inline alternative the phrase ends with, when it replaces words and none beside it
        were: the next phrase may open with them."""
        last = None
        for last in _INLINE.finditer(xml):
            pass
        if last is None or re.sub(r"<[^>]*>|[\s,.:;]", "", xml[last.end():]):
            return None
        if re.search(r'</j:none></j:conditional>[^<]*<j:endConditional target="#inline_\d+"/>\s*$',
                     xml[:last.start()]):
            return None  # the words it replaces were found before it
        replacement = self.table.replaced(html.unescape(re.sub(r"<[^>]*>", "", last.group(3))))
        if replacement is None:
            return None
        when = re.search(r"</tei:note>(.*)</j:conditional>$", last.group(1)).group(1)
        return when, replacement

    def _carried(self, xml: str) -> str:
        """The words the last phrase's closing alternative replaces, where this phrase opens with
        them, conditional on its condition being false."""
        if self.pending is None:
            return xml
        when, replacement = self.pending
        self.pending = None
        opening = re.match(r"((?:\s|<tei:milestone[^>]*/>)*)([^<]*)", xml)
        text = opening.group(2)
        lead = len(text) - len(text.lstrip())
        taken = _leading_words(text[lead:], replacement.replaces)
        if taken is None:
            return xml
        begin = opening.start(2) + lead
        return xml[:begin] + self._negated(when, taken) + xml[begin + len(taken):]

    def _replace(self, xml: str, replacement) -> str:
        """The words an inline alternative replaces, beside it -- after it or before it --
        conditional on its condition being false."""
        for match in _INLINE.finditer(xml):
            if xml[match.end():].lstrip().startswith('<j:conditional xml:id="inline_') and "<j:none>" in \
                    xml[match.end():match.end() + 400].split("</j:conditional>", 1)[0]:
                continue  # its replaced words are conditional already
            alternative = html.unescape(re.sub(r"<[^>]*>", "", match.group(3)))
            if tuple(words(alternative)) != replacement.alternative:
                continue
            when = re.search(r"</tei:note>(.*)</j:conditional>$", match.group(1)).group(1)
            after = re.match(r"\s*([^<]*)", xml[match.end():])
            taken = _leading_words(after.group(1), replacement.replaces)
            if taken is not None:
                begin = match.end() + after.start(1)
                return (xml[:begin] + self._negated(when, taken) + xml[begin + len(taken):])
            before = re.search(r"([^<>]*?)(\s*)$", xml[:match.start()])
            taken = _trailing_words(before.group(1), replacement.replaces)
            if taken is not None:
                end = before.start(1) + len(before.group(1))
                return xml[:end - len(taken)] + self._negated(when, taken) + xml[end:]
        return xml

    def _negated(self, when: str, words_xml: str) -> str:
        xml_id = self.next_id("inline")
        return (f'<j:conditional xml:id="{xml_id}"><j:none>{when}</j:none></j:conditional>'
                f'{words_xml}<j:endConditional target="#{xml_id}"/>')

    def rubric(self, pair: Pair) -> None:
        # A rubric is not the phrase before it, nor scripture. The scopes are closed in both
        # languages, whichever the rubric is printed in, so that the two divide alike.
        self.end_phrase()
        self.verse(None)
        found = None
        if pair.he_kind is HebrewKind.EMPTY:
            found = self.table.for_rubric(plain_text(pair.en))
        elif pair.he_kind is HebrewKind.LABEL:
            # A label standing on its own line before the words it governs (<b>לפסח</b>, "On
            # Pesach"): known by its Hebrew, or else by its English.
            label = self.table.for_label(plain_text(pair.he))
            found = label if label is not None else self.table.for_rubric(plain_text(pair.en))
        current = self.calendar
        if found is None and current is not None and current[2] is None:
            # A rubric between a condition rubric and the first words it governs ("Chazzan:",
            # an explanation) leads into the passage: the conditional stays open.
            xml = rubric_xml(pair, self.lang, self.notes)
            if xml:
                self.parts.append(xml)
            return
        self.close_calendar()
        self.pending = None
        if found is not None:
            self.open_calendar(pair, found.when, getattr(found, "through", ()))
            return
        xml = rubric_xml(pair, self.lang, self.notes)
        if xml:
            self.parts.append(xml)

    def open_condition(self, features: list[tuple[str, bool]]) -> str:
        self.end_phrase()
        self.conditions += 1
        xml_id = f"variant_{self.conditions}"
        self.parts.append(f'<j:conditional xml:id="{xml_id}">{variant_fs(features)}</j:conditional>')
        self.open_variants.append(xml_id)
        return xml_id

    def close_condition(self, xml_id: str) -> None:
        # A condition rubric inside the variant's passage governs it to its end, and no further.
        depth = len(self.open_variants)
        while self.calendars and self.calendars[-1][1] >= depth:
            self.end_phrase()
            self.verse(None)
            self.parts.append(f'<j:endConditional target="#{self.calendars.pop()[0]}"/>')
        self.end_phrase()
        self.parts.append(f'<j:endConditional target="#{xml_id}"/>')
        if self.open_variants and self.open_variants[-1] == xml_id:
            self.open_variants.pop()
        # One outside it whose passage ended inside it closes now.
        if self.calendars and self.calendars[-1][3] and self.calendars[-1][1] == len(self.open_variants):
            self.end_phrase()
            self.verse(None)
            self.parts.append(f'<j:endConditional target="#{self.calendars.pop()[0]}"/>')


#: an inline alternative: its conditional (1), id (2), words (3) and end (4)
_INLINE = re.compile(r'(<j:conditional xml:id="(inline_\d+)" type="marked">.*?</j:conditional>)'
                     r'(.*?)(<j:endConditional target="#\2"/>)')


def _well_formed(xml: str) -> bool:
    try:
        etree.fromstring(f'<x xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">'
                         f"{xml}</x>")
    except etree.XMLSyntaxError:
        return False
    return True


def _leading_words(text: str, wanted: tuple[str, ...]) -> str | None:
    """The opening of ``text`` that is ``wanted`` (compared as the index compares words, a maqaf
    separating them), or None."""
    for match in re.finditer(r"\S+", text):
        found = tuple(words(text[:match.end()]))
        if found == wanted:
            return text[:match.end()]
        if len(found) >= len(wanted):
            return None
    return None


def _trailing_words(text: str, wanted: tuple[str, ...]) -> str | None:
    """The end of ``text`` that is ``wanted``, or None."""
    starts = [m.start() for m in re.finditer(r"\S+", text)]
    for start in reversed(starts):
        found = tuple(words(text[start:]))
        if found == wanted:
            return text[start:].rstrip()
        if len(found) >= len(wanted):
            return None
    return None


def variant_passages(variant: VariantPrinting, base: set[int]) -> dict[int | None, list[tuple[Pair, int | None]]]:
    """A variant's own words, by the phrase of the first printing they follow (None: before
    the first): each run of its new phrases, with the rubrics that lead into them."""
    passages: dict[int | None, list[tuple[Pair, int | None]]] = {}
    numbers = iter(variant.numbers)
    anchor: int | None = None
    run: list[tuple[Pair, int | None]] = []
    pending: list[tuple[Pair, int | None]] = []
    for pair in variant.block.pairs:
        if not is_phrase(pair):
            pending.append((pair, None))
            continue
        number = next(numbers)
        if number in base:
            if run:
                passages.setdefault(anchor, []).extend(run)
                run = []
            pending = []  # a rubric before the shared words is the first printing's to give
            anchor = number
        else:
            run.extend(pending)
            pending = []
            run.append((pair, number))
    if run:
        passages.setdefault(anchor, []).extend(run)
    return passages


def text_body(urn: str, block: TextBlock, phrase_numbers: list[int], lang: str, notes: Notes,
              variants: tuple[VariantPrinting, ...] = (), verses: dict[int, str] | None = None,
              verse_lengths: dict[str, int] | None = None, conditions: Conditions | None = None,
              clashes: Collection[str] = frozenset(), opening: tuple[str, int] | None = None) -> str:
    """A text's division: its heading, then its phrases and the rubrics among them.

    With ``variants``, the one text of every printing: the first printing's words, a phrase a
    variant leaves out conditional on that variant being false, and each variant's own words,
    after the phrase they follow, conditional on it being true.

    ``verses`` (``match.scripture_verses``) gives the verse of scripture each phrase that opens
    one opens: its ``bible:`` URN is set before the phrase, in both languages, and its scope
    closed after the phrase that ends it -- by its punctuation, or by its length in words where
    ``verse_lengths`` knows it -- or before a rubric, unless another verse follows at once.

    With ``opening`` -- a text's URN and a number of phrases -- the text opens with that text,
    transcluded in place of its first phrases and the rubrics among them (the full Kaddish, with
    the half Kaddish it opens with)."""
    verses = verses or {}
    verse_lengths = verse_lengths or {}
    verse_words = 0
    verse_length: int | None = None
    head = head_xml(block.head, lang, notes) if block.head is not None else ""
    writer = _TextWriter(urn, lang, notes, conditions, clashes)
    base = set(phrase_numbers)
    passages = [(v, variant_passages(v, base)) for v in variants]
    absent = {n: [v.name for v in variants if n not in set(v.numbers)] for n in phrase_numbers}
    # A document carries a URN once: a text a variant names among its own words is marked
    # unless the text's own words, or another variant's, already mark it (two printings of the
    # Shema lining שְׁמַע יִשְׂרָאֵל otherwise, each naming Deuteronomy 6:4).
    skip = opening[1] if opening else 0
    marked = {verse for position, verse in verses.items() if position >= skip}

    def insert(anchor: int | None) -> None:
        for variant, by_anchor in passages:
            if anchor in by_anchor:
                xml_id = writer.open_condition([(variant_urn(urn, variant.name), True)])
                part_open = False
                for pair, number in by_anchor[anchor]:
                    if number is None:
                        writer.rubric(pair)
                        continue
                    if number in variant.parts and variant.parts[number] not in marked:
                        # A text the collection names, inside this text: its URN on a
                        # milestone (the next part's ends it), its scope closed with the passage.
                        marked.add(variant.parts[number])
                        writer.end_phrase()
                        writer.parts.append(f'<tei:milestone unit="prayer" corresp="{attr(variant.parts[number])}"/>')
                        part_open = True
                    elif number in variant.parts and part_open:
                        # A part already marked ends the one before it, unmarked here.
                        writer.end_phrase()
                        writer.parts.append('<tei:milestone unit="prayer"/>')
                        part_open = False
                    writer.phrase(pair, number)
                if part_open:
                    writer.end_phrase()
                    writer.parts.append('<tei:milestone unit="prayer"/>')
                writer.close_condition(xml_id)

    insert(None)
    numbers = iter(phrase_numbers)
    position = -1
    for pair in block.pairs:
        if not is_phrase(pair):
            if position + 1 >= skip:
                writer.rubric(pair)
            continue
        number = next(numbers)
        position += 1
        if position < skip:
            insert(number)  # (the transcluded text's own words: only after its last, a variant's)
            continue
        if position in verses:
            writer.verse(verses[position])
            verse_words, verse_length = 0, verse_lengths.get(verses[position])
        verse_words += len(plain_text(pair.he).split())
        if absent.get(number):
            xml_id = writer.open_condition([(variant_urn(urn, name), False) for name in absent[number]])
            writer.phrase(pair, number)
            writer.close_condition(xml_id)
        else:
            writer.phrase(pair, number)
        ended = plain_text(pair.he).rstrip().endswith(VERSE_ENDINGS) or (
            verse_length is not None and verse_words >= verse_length)
        if writer.verse_open and ended and position + 1 not in verses:
            writer.end_phrase()
            writer.verse(None)
        insert(number)
    writer.close_calendar(everything=True)
    content = "\n".join(writer.parts)
    paragraph = f"<tei:p>{content}</tei:p>" if content else ""
    transclusion = f'<j:transclude type="external" target="{attr(opening[0])}"/>' if opening else ""
    return f'<tei:body><tei:div corresp="{attr(urn)}">{head}{transclusion}{paragraph}</tei:div></tei:body>'


def leaf_body(urn: str, titles: tuple[str, str], items: list[Item], text_urns: dict[int, str],
              lang: str, notes: Notes,
              declarations: dict[int, list[tuple[str, bool]]] | None = None,
              conditions: Conditions | None = None,
              leading: dict[int, Pair] | None = None) -> str:
    """A leaf's structure division: its heading, then its rubrics, headings and texts.
    ``text_urns`` maps each text block (by ``id``) to its URN; ``declarations``, to the
    variants of its text that are and are not printed here, declared around its transclusion.

    A condition rubric (``conditions``) between texts gates the next text's transclusion --
    or, for a rubric that governs a section, everything to the next heading -- its words the
    conditional's note. ``leading`` gives, for a text printed before (whose own file is the first
    printing's), the condition rubric it opens with, which then gates its transclusion here."""
    leading = leading or {}
    declarations = declarations or {}
    table = conditions or Conditions()
    declared = 0
    gates = 0
    gate: str | None = None
    section = False
    until = None
    until_included = False
    #: where in ``parts`` the last transclusion is, while nothing has followed it
    previous: int | None = None
    texts = 0
    title = titles[1] if lang == "he" else titles[0]
    parts = [f'<tei:head xml:lang="{lang}">{_text(title, lang)}</tei:head>'] if title else []

    def close_gate() -> None:
        nonlocal gate
        if gate is not None:
            parts.append(f'<j:endConditional target="#{gate}"/>')
            gate = None

    for item in items:
        if isinstance(item, Rubric):
            for pair in item.pairs:
                found = table.for_rubric(plain_text(pair.en)) if pair.he_kind is HebrewKind.EMPTY else None
                if found is None:
                    ends = gate is not None and until is not None and bool(
                        until.search(" ".join(plain_text(pair.en).split())))
                    if ends and not until_included:
                        close_gate()  # the rubric the section's condition runs to
                    xml = rubric_xml(pair, lang, notes)
                    if xml:
                        parts.append(xml)
                    if ends and until_included:
                        close_gate()  # ... and ends with
                    continue
                close_gate()
                if found.instead_of_previous and previous is not None and all(
                        p.startswith("<j:endConditional") for p in parts[previous + 1:]):
                    # (inside a gate of its own that has closed: the conditionals nest)
                    gates += 1
                    parts[previous] = (f'<j:conditional xml:id="when_{gates}">{negated_xml(found.when)}</j:conditional>'
                                       f'{parts[previous]}<j:endConditional target="#when_{gates}"/>')
                gates += 1
                gate, section, until, texts = f"when_{gates}", found.section, found.until, 0
                until_included = found.until_included
                note = instruction(pair.en, "en", notes) if lang == "en" else ""
                parts.append(conditional_open(gate, note, condition_xml(found.when)))
        elif isinstance(item, Heading):
            if gate is not None and section and until is None and texts:
                close_gate()
            label = head_xml(item.pair, lang, notes, element="label")
            if label:
                parts.append(label)
        elif isinstance(item, TextBlock):
            if gate is not None and section and until is None and texts and item.head is not None:
                close_gate()  # a text under a heading of its own begins the next section
            transclude = f'<j:transclude type="external" target="{attr(text_urns[id(item)])}"/>'
            if declarations.get(id(item)):
                declared += 1
                xml_id = f"variants_{declared}"
                transclude = (f'<j:declare xml:id="{xml_id}">{variant_fs(declarations[id(item)])}</j:declare>'
                              f'{transclude}<j:endDeclare target="#{xml_id}"/>')
            lead = leading.get(id(item))
            found = table.for_rubric(plain_text(lead.en)) if lead is not None else None
            # The rubric a section's condition runs to may open the next text's block.
            ends = gate is not None and until is not None and any(
                until.search(" ".join(plain_text(pair.en).split()))
                for pair in item.pairs[:next((k for k, p in enumerate(item.pairs) if is_phrase(p)), 0)])
            if ends and not until_included:
                close_gate()
            if lead is not None:
                # The rubrics before the condition the text opens with are the place's: they
                # close the text before ("(Deliver us...; Mourner's Kaddish.)" after one day's
                # psalm, before the next day's rubric).
                for pair in item.pairs:
                    if pair is lead or is_phrase(pair):
                        break
                    if pair.he_kind is HebrewKind.EMPTY and table.for_rubric(plain_text(pair.en)):
                        continue  # an earlier condition, overridden by the one the text opens with
                    xml = rubric_xml(pair, lang, notes)
                    if xml:
                        parts.append(xml)
            if ends and until_included:
                close_gate()
            if found is not None and found.section:
                # A condition over a section (one day's introduction and psalm) gates every text
                # to its end, as the same rubric between texts does.
                close_gate()
                gates += 1
                gate, section, until, texts = f"when_{gates}", found.section, found.until, 0
                until_included = found.until_included
                note = instruction(lead.en, "en", notes) if lang == "en" else ""
                parts.append(conditional_open(gate, note, condition_xml(found.when)))
            elif found is not None and gate is None:
                gates += 1
                note = instruction(lead.en, "en", notes) if lang == "en" else ""
                transclude = (conditional_open(f"when_{gates}", note, condition_xml(found.when))
                              + f'{transclude}<j:endConditional target="#when_{gates}"/>')
            parts.append(transclude)
            previous = len(parts) - 1
            texts += 1
            if gate is not None and not section:
                close_gate()
    close_gate()
    return f'<tei:body><tei:div corresp="{attr(urn)}">{"".join(parts)}</tei:div></tei:body>'


def node_body(urn: str, titles: tuple[str, str], children: list[str], lang: str,
              gates: dict[str, LeafGate] | None = None) -> str:
    """An inner node's division: its heading and a transclusion of each child -- conditional,
    for a child ``gates`` names (``conditions.yaml`` leaves)."""
    title = titles[1] if lang == "he" else titles[0]
    head = f'<tei:head xml:lang="{lang}">{_text(title, lang)}</tei:head>' if title else ""
    transclusions = _transclusions(children, lang, gates)
    return f'<tei:body><tei:div corresp="{attr(urn)}">{head}{transclusions}</tei:div></tei:body>'


def _transclusions(children: list[str], lang: str, gates: dict[str, LeafGate] | None) -> str:
    gates = gates or {}
    parts = []
    for n, child in enumerate(children, start=1):
        transclude = f'<j:transclude type="external" target="{attr(child)}"/>'
        gate = gates.get(child)
        if gate is not None:
            note = (f'<tei:note type="instruction" xml:lang="en">{esc(gate.note)}</tei:note>'
                    if gate.note and lang == "en" else "")
            transclude = (f'<j:conditional xml:id="leaf_{n}">{note}{condition_xml(gate.when)}</j:conditional>'
                          f'{transclude}<j:endConditional target="#leaf_{n}"/>')
        parts.append(transclude)
    return "".join(parts)


def index_body(work: Work, children: list[str], lang: str, gates: dict[str, LeafGate] | None = None) -> str:
    title = work.title_he if lang == "he" else work.title_en
    head = f'<tei:head xml:lang="{lang}">{_text(title, lang)}</tei:head>'
    transclusions = _transclusions(children, lang, gates)
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
    # The translation is the book's own, as Birnbaum's is his: its translator is the bibl's
    # author, not a contributor to the encoding (a tei:respStmt, which needs a contributor URN).
    translator = f"<tei:author>{esc(work.translator)}</tei:author>"
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
        f"<tei:note xml:lang=\"en\">The English is {esc(work.translator)}’s translation, printed in the "
        "book’s linear layout opposite the Hebrew.</tei:note>"
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
