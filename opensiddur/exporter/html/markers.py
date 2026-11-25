"""Prepare a compiled document's undecided conditions for an electronic book.

A scope the compiler could not decide reaches the compiled document as a pair of sibling
markers, `j:conditional` ... `j:endConditional`, around whatever it governs -- a phrase, a
paragraph, a run of sections. On the page the reader's device shows or hides what a scope
governs, which the HTML can only do element by element. Scopes may also cross, so they cannot
simply become wrapping elements.

So instead, every element and every run of text is labelled with each scope that governs all
of it, and the device hides whatever carries the label of a scope that does not hold. This
pass computes the labels on the compiled tree, as `p:scopes` attributes and `p:span` wrappers
around text, for html.xslt to turn into classes:

- an element is governed by a scope that is open at its start and still open at its end;
- a run of text, by every scope open where it stands;
- each is labelled only with the scopes its parent is not already labelled with.

A parallel column is a stream of its own. A scope opened in the primary column governs that
column through the rows that follow, and not the column beside it; a scope opened outside the
columns governs both.

The pass also numbers the scopes (`p:cid`, on both markers) and collects their conditions, for
the book's JSON.
"""

from __future__ import annotations

from copy import deepcopy
import json
import re
import logging
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from opensiddur.exporter.client_settings import is_reader_supplied
from opensiddur.exporter.condition_eval import (
    condition_features,
    condition_to_json,
    parse_condition_element,
)
from opensiddur.exporter.conditional_markers import check_pairing, mark_silent_scopes
from opensiddur.exporter.conditional_settings import J_CONDITIONAL, J_END_CONDITIONAL, XML_ID
from opensiddur.exporter.constants import (
    JLPTEI_NAMESPACE,
    PROCESSING_NAMESPACE,
    TEI_NS,
    is_element_node,
)

logger = logging.getLogger(__name__)

P_CID = f"{{{PROCESSING_NAMESPACE}}}cid"
P_SCOPES = f"{{{PROCESSING_NAMESPACE}}}scopes"
P_SPAN = f"{{{PROCESSING_NAMESPACE}}}span"
P_PINNED = f"{{{PROCESSING_NAMESPACE}}}pinned"
P_PARALLEL_ITEM = f"{{{PROCESSING_NAMESPACE}}}parallelItem"
P_SECTION = f"{{{PROCESSING_NAMESPACE}}}section"
P_PARALLEL = f"{{{PROCESSING_NAMESPACE}}}parallel"
P_ROW = f"{{{PROCESSING_NAMESPACE}}}row"
P_OPTIONAL_REFERENCE = f"{{{PROCESSING_NAMESPACE}}}optional-reference"
P_HEADING_LEVEL = f"{{{PROCESSING_NAMESPACE}}}heading-level"
TEI_HEAD = f"{{{TEI_NS}}}head"
TEI_ANCHOR = f"{{{TEI_NS}}}anchor"
TEI_SEG = f"{{{TEI_NS}}}seg"
TEI_REF = f"{{{TEI_NS}}}ref"


@dataclass
class Feature:
    """A feature the book's undecided conditions ask about, for the settings panel."""

    fs: str
    name: str
    #: The values conditions compare it with, in the order first met.
    values: list[Any] = field(default_factory=list)
    #: The scopes that turn on it, where it was not pinned.
    cids: list[int] = field(default_factory=list)
    #: Whether a device could one day answer it from its clock and its location.
    calendar: bool = False
    #: How much of the book's text turns on it, in characters (see `measure_text`).
    chars: int = 0

    @property
    def scopes(self) -> int:
        return len(self.cids)

    @property
    def kind(self) -> str:
        """binary, numeric or string, by the values conditions compare it with."""
        if all(isinstance(value, bool) for value in self.values):
            return "binary"
        if all(isinstance(value, dict) and "num" in value for value in self.values):
            return "numeric"
        return "string"


@dataclass
class BookConditions:
    #: Distinct (condition, pinned values) pairs, as JSON.
    expressions: list[dict[str, Any]] = field(default_factory=list)
    #: For each scope, by its number, the index of its expression.
    scopes: list[int] = field(default_factory=list)
    features: list[Feature] = field(default_factory=list)
    #: For each scope, the characters of text it governs.
    scope_chars: list[int] = field(default_factory=list)
    #: The characters of text governed by any scope, each counted once.
    conditional_chars: int = 0
    #: For each section (a heading, and what follows it up to the next heading at its level or
    #: above), None if some of its text is governed by no scope, or else the distinct sets of
    #: scopes that govern its runs of text: it shows if any one set has no scope that is false.
    sections: list[list[list[int]] | None] = field(default_factory=list)
    #: For each optional page reference whose destination the settings can hide, by its number
    #: (p:optional-reference), the destinations of its page references: for each, the distinct
    #: sets of scopes that govern its occurrences. It shows if every destination has a set with
    #: no scope that is false.
    optional_references: list[list[list[list[int]]]] = field(default_factory=list)
    #: For each row of parallel text all of whose text is governed by scopes, by its number
    #: (p:row), the distinct sets of scopes that govern its runs of text: it shows if any one
    #: set has no scope that is false. A row the settings leave with no text is hidden whole, so
    #: that, off screen, it is not taken to have a row's height.
    rows: list[list[list[int]]] = field(default_factory=list)


def _leaf_values(condition: dict[str, Any]):
    """(fs, feature, value) for every value a JSON condition compares with."""
    if "fs" in condition:
        for f in condition["f"]:
            yield from _values_of(condition["fs"], f["name"], f["v"])
        return
    for child in condition["args"]:
        yield from _leaf_values(child)


def _values_of(fs, name, value):
    if isinstance(value, dict) and "alt" in value:
        for alt in value["alt"]:
            yield from _values_of(fs, name, alt)
    elif isinstance(value, dict) and "not" in value:
        yield from _values_of(fs, name, value["not"])
    elif not (isinstance(value, dict) and value.get("undefined")):
        yield fs, name, value


def _number_scopes(root: etree.ElementBase) -> tuple[dict[str, etree.ElementBase], BookConditions]:
    """Number each paired scope in document order, and collect its condition.

    Returns the openers by their xml:id, and the book's conditions.
    """
    problems = check_pairing(root)
    unpaired = {problem.xml_id for problem in problems}
    for problem in problems:
        logger.warning("conditional markers do not pair, left undecided: %s", problem)

    book = BookConditions()
    expression_index: dict[str, int] = {}
    features: dict[tuple[str, str], Feature] = {}
    openers: dict[str, etree.ElementBase] = {}

    for opener in root.iter(J_CONDITIONAL):
        xml_id = opener.get(XML_ID)
        pinned_element = opener.find(P_PINNED)
        pinned = json.loads(pinned_element.text) if pinned_element is not None else {}
        if pinned_element is not None:
            opener.remove(pinned_element)
        if xml_id is None or xml_id in unpaired:
            continue

        node = parse_condition_element(opener)
        expression = {"cond": condition_to_json(node), "pinned": pinned}
        key = json.dumps(expression, sort_keys=True, ensure_ascii=False)
        if key not in expression_index:
            expression_index[key] = len(book.expressions)
            book.expressions.append(expression)

        cid = len(book.scopes)
        book.scopes.append(expression_index[key])
        opener.set(P_CID, str(cid))
        openers[xml_id] = opener

        for fs, name in sorted(condition_features(node)):
            if name not in pinned.get(fs, {}) and opener.get(
                    f"{{{PROCESSING_NAMESPACE}}}separator") != "true":
                feature = features.setdefault(
                    (fs, name), Feature(fs, name, calendar=not is_reader_supplied(fs)))
                feature.cids.append(cid)
        for fs, name, value in _leaf_values(expression["cond"]):
            feature = features.get((fs, name))
            if feature is not None and value not in feature.values:
                feature.values.append(value)

    for closer in root.iter(J_END_CONDITIONAL):
        opener = openers.get((closer.get("target") or "").removeprefix("#"))
        if opener is not None:
            closer.set(P_CID, opener.get(P_CID))

    # A feature conditions compare only with "undefined" has nothing a reader could choose.
    book.features = sorted((f for f in features.values() if f.values), key=lambda f: (f.fs, f.name))
    return openers, book


class _Spans:
    """The open scopes, per stream, as the walk goes through the document."""

    def __init__(self):
        self.open: dict[str | None, list[int]] = {}

    def active(self, stream: str | None) -> frozenset[int]:
        found = set(self.open.get(None, ()))
        if stream is not None:
            found.update(self.open.get(stream, ()))
        return frozenset(found)

    def toggle(self, marker: etree.ElementBase, stream: str | None) -> None:
        cid = int(marker.get(P_CID))
        scopes = self.open.setdefault(stream, [])
        if marker.tag == J_CONDITIONAL:
            scopes.append(cid)
        elif cid in scopes:
            scopes.remove(cid)


def _is_marker(element: etree.ElementBase) -> bool:
    return element.tag in (J_CONDITIONAL, J_END_CONDITIONAL) and element.get(P_CID) is not None


def _measure(root: etree.ElementBase) -> dict[etree.ElementBase, tuple[frozenset, frozenset]]:
    """The scopes active at the start and at the end of every element."""
    spans = _Spans()
    measured: dict[etree.ElementBase, tuple[frozenset, frozenset]] = {}

    def walk(element, stream):
        if element.tag == P_PARALLEL_ITEM:
            stream = element.get("role")
        before = spans.active(stream)
        if _is_marker(element):
            spans.toggle(element, stream)
        else:
            for child in element:
                if is_element_node(child):
                    walk(child, stream)
        measured[element] = (before, spans.active(stream))

    walk(root, None)
    return measured


def _label(element: etree.ElementBase, scopes: frozenset[int]) -> None:
    if scopes:
        element.set(P_SCOPES, " ".join(str(cid) for cid in sorted(scopes)))


def _span(text: str, scopes: frozenset[int]) -> etree.ElementBase:
    span = etree.Element(P_SPAN)
    span.text = text
    _label(span, scopes)
    return span


def _sections(root: etree.ElementBase, measured, book: BookConditions) -> None:
    """Which scopes each section's text turns on, so that the book's contents can leave out a
    section none of whose text will show (see BookConditions.sections).

    A heading in the translation column repeats its row's, and is no section of its own; its
    text, like any heading's, is not the section's. Nor are a scope's markers -- the rubric says
    when the text applies, and is not the text.
    """
    open_sections: list[tuple[int, int]] = []  # (level, index), innermost last
    found: list[set[frozenset[int]] | None] = []

    def record(text, active):
        if not (text and text.strip()):
            return
        for _, index in open_sections:
            if found[index] is None:
                continue
            if active:
                found[index].add(active)
            else:
                found[index] = None

    def walk(element, stream):
        if element.tag == P_PARALLEL_ITEM:
            stream = element.get("role")
        if element.tag == TEI_HEAD:
            if stream != "parallel":
                level = int(element.get(P_HEADING_LEVEL) or 2)
                while open_sections and open_sections[-1][0] >= level:
                    open_sections.pop()
                index = len(found)
                found.append(set())
                open_sections.append((level, index))
                element.set(P_SECTION, str(index))
            return
        if _is_marker(element):
            return
        record(element.text, measured[element][0])
        for child in element:
            if is_element_node(child):
                walk(child, stream)
                record(child.tail, measured[child][1])
            else:
                record(child.tail, measured[element][0])

    walk(root, None)
    book.sections = [None if sets is None else sorted(sorted(s) for s in sets) for sets in found]


def _rows(root: etree.ElementBase, measured, book: BookConditions) -> None:
    """Which scopes each row of parallel text turns on (see BookConditions.rows).

    Every row's text counts, a nested row's included, and its headings; a scope's markers do
    not, being no text of the row. A row with some text no scope governs always shows, and one
    with no text at all is left alone: it is no row's height.
    """
    for row in root.iter(P_PARALLEL):
        sets: set[frozenset[int]] = set()
        unconditional = False

        def record(text, active):
            nonlocal unconditional
            if not (text and text.strip()):
                return
            if active:
                sets.add(active)
            else:
                unconditional = True

        def walk(element):
            if _is_marker(element):
                return
            record(element.text, measured[element][0])
            for child in element:
                if is_element_node(child):
                    walk(child)
                    record(child.tail, measured[child][1])
                else:
                    record(child.tail, measured[element][0])

        walk(row)
        if sets and not unconditional:
            row.set(P_ROW, str(len(book.rows)))
            book.rows.append(sorted(sorted(s) for s in sets))


def _optional_references(root: etree.ElementBase, measured, book: BookConditions) -> None:
    """When each optional page reference can reach its destination (see
    BookConditions.optional_references), numbering the ones the settings can strand.

    Print drops an optional reference whose destination did not survive compilation. The reader's
    settings can hide a destination the electronic book keeps -- every occurrence of it, which
    page_references labels -- and the reference goes with it.
    """
    labels: dict[str, list[etree.ElementBase]] = {}
    for anchor in root.iter(TEI_ANCHOR):
        if anchor.get("type") == "page-label":
            labels.setdefault(anchor.get("n"), []).append(anchor)
    book.optional_references = []
    for span in root.iter(TEI_SEG):
        # One in a conditional's own rubric is the marker's, which is never labelled.
        if span.get("type") != "optional-page-reference" or span not in measured:
            continue
        refs = []
        for ref in span.iter(TEI_REF):
            occurrences = {measured[anchor][0] for anchor in labels.get(ref.get("target"), [])}
            if ref.get("type") == "page" and occurrences and frozenset() not in occurrences:
                refs.append(sorted(sorted(scopes) for scopes in occurrences))
        if refs:
            span.set(P_OPTIONAL_REFERENCE, str(len(book.optional_references)))
            book.optional_references.append(refs)


def _assign(root: etree.ElementBase, measured) -> None:
    """Label each element and run of text with the scopes that govern it and not its parent."""

    def walk(element, inherited):
        before, after = measured[element]
        governed = before & after
        _label(element, governed - inherited)
        if _is_marker(element):
            return
        covered = inherited | governed
        children = list(element)
        if element.text and element.text.strip() and before - covered:
            element.insert(0, _span(element.text, before - covered))
            element.text = None
        for child in children:
            if not is_element_node(child):
                continue
            walk(child, covered)
            tail_scopes = measured[child][1] - covered
            if child.tail and child.tail.strip() and tail_scopes:
                span = _span(child.tail, tail_scopes)
                child.tail = None
                child.addnext(span)

    walk(root, frozenset())


_CONDITION_TAGS = frozenset(
    f"{{{namespace}}}{name}" for namespace, name in (
        (TEI_NS, "fs"), (JLPTEI_NAMESPACE, "all"), (JLPTEI_NAMESPACE, "any"),
        (JLPTEI_NAMESPACE, "none"), (JLPTEI_NAMESPACE, "one")))


def _text_length(element: etree.ElementBase) -> int:
    """The characters of text in an element, not counting spaces or a condition's values."""
    if element.tag in _CONDITION_TAGS:
        return 0
    length = len("".join((element.text or "").split()))
    for child in element:
        if is_element_node(child):
            length += _text_length(child)
        length += len("".join((child.tail or "").split()))
    return length


def measure_text(root: etree.ElementBase, book: BookConditions) -> None:
    """How much text each scope governs, and each feature turns, for ranking the settings.

    A labelled element or span counts its whole text towards each scope it is labelled with;
    its ancestors are never labelled with the same scope, so no scope counts a character
    twice. A feature counts the text of every scope that turns on it -- text that two of
    those scopes govern together counts twice, which ranking can bear.
    """
    book.scope_chars = [0] * len(book.scopes)
    book.conditional_chars = 0
    for element in root.iter():
        labels = element.get(P_SCOPES)
        if not labels:
            continue
        length = _text_length(element)
        for cid in labels.split():
            book.scope_chars[int(cid)] += length
        if not any(ancestor.get(P_SCOPES) for ancestor in element.iterancestors()):
            book.conditional_chars += length
    for feature in book.features:
        feature.chars = sum(book.scope_chars[cid] for cid in feature.cids)


def prepare(root: etree.ElementBase) -> BookConditions:
    """Number, collect and label the undecided scopes in a compiled document, in place."""
    _conditional_separators(root)
    openers, book = _number_scopes(root)
    if book.scopes:
        mark_silent_scopes(root)
        measured = _measure(root)
        _sections(root, measured, book)
        _rows(root, measured, book)
        _optional_references(root, measured, book)
        _assign(root, measured)
        measure_text(root, book)
    return book


def _conditional_separators(root):
    """Hide a separator with an omitted inline insert immediately before punctuation.

    The separator stays before the original marked scope, so undecided brackets
    keep their printed spacing. Its separate silent scope shares the same
    predicate and pinned settings, and needs no new reader setting.
    """
    from opensiddur.exporter.whitespace import closes_omitted_insert
    identifiers = {node.get(XML_ID) for node in root.iter() if node.get(XML_ID)}
    for opener in list(root.iter(J_CONDITIONAL)):
        identifier = opener.get(XML_ID)
        if not identifier:
            continue
        parent = opener.getparent()
        if parent is None or not any(
                node.tag in (f"{{{TEI_NS}}}p", f"{{{TEI_NS}}}l")
                for node in [parent, *parent.iterancestors()]):
            continue
        endpoints = [node for node in parent if node.tag == J_END_CONDITIONAL
                     and node.get("target") == "#"+identifier]
        if len(endpoints) != 1 or parent.index(endpoints[0]) <= parent.index(opener):
            continue
        after = endpoints[0].tail or ""
        if not closes_omitted_insert(after, parent):
            continue
        previous = opener.getprevious()
        prefix = (previous.tail if previous is not None else parent.text) or ""
        match = re.search(r"[ \t\r\n]+$", prefix)
        if not match:
            continue
        earlier_text = (parent.text or "")+"".join(
            "".join(node.itertext())+(node.tail or "")
            for node in list(parent)[:parent.index(opener)])
        if not earlier_text.strip():
            continue
        whitespace = match.group()
        if previous is None:
            parent.text = prefix[:match.start()]
        else:
            previous.tail = prefix[:match.start()]
        new_id = identifier+"_separator"
        while new_id in identifiers:
            new_id += "_"
        identifiers.add(new_id)
        separator = deepcopy(opener)
        separator.set(XML_ID, new_id)
        # This auxiliary scope controls whitespace, not another passage in the
        # reader's settings panel or its feature-ranking counts.
        separator.set(f"{{{PROCESSING_NAMESPACE}}}separator", "true")
        separator.attrib.pop("type", None)
        separator.attrib.pop(f"{{{PROCESSING_NAMESPACE}}}silent", None)
        for child in list(separator):
            if child.tag == f"{{{TEI_NS}}}note":
                separator.remove(child)
        # _assign deliberately ignores whitespace-only text runs. An explicit
        # inline holder lets the separator itself receive the scope's class.
        separator.tail = None
        space = etree.Element(f"{{{TEI_NS}}}seg")
        space.text = whitespace
        endpoint = etree.Element(J_END_CONDITIONAL, target="#"+new_id)
        position = parent.index(opener)
        parent.insert(position, separator)
        parent.insert(position+1, space)
        parent.insert(position+2, endpoint)
