"""Check that the conditional scopes a compile leaves undecided still come in pairs.

A `j:conditional` the compiler could not decide is copied into its output with the
`j:endConditional` that closes it, and every downstream stage finds the scope by pairing the
two: `xml:id` on the opener, `@target="#id"` on the closer. Reledmac brackets the text between
them; an electronic book shows or hides it. A pair that lost one end governs nothing a stage
can find -- an opener with no closer prints a bracket that never shuts -- so the pairing is
worth checking on its own rather than through how each stage happens to cope.

Scopes may cross; that is not a problem. What is:

- an opener with no closer, or a closer with no opener;
- a closer that comes before its opener;
- two openers with the same id;
- a pair whose ends lie in different parallel columns, or one in a column and one in the
  main flow, since each column is typeset as a stream of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

from opensiddur.exporter.conditional_settings import (
    J_CONDITIONAL,
    J_END_CONDITIONAL,
    XML_ID,
)
from opensiddur.exporter.constants import PROCESSING_NAMESPACE, RUBRIC_NOTE_TYPES

_PARALLEL_ITEM = f"{{{PROCESSING_NAMESPACE}}}parallelItem"

UNCLOSED = "unclosed"
ORPHAN = "orphan"
CLOSER_FIRST = "closer-before-opener"
DUPLICATE = "duplicate-id"
CROSS_STREAM = "cross-stream"


@dataclass(frozen=True)
class PairingProblem:
    kind: str
    xml_id: str
    line: int | None = None

    def __str__(self) -> str:
        where = f" (line {self.line})" if self.line else ""
        return f"{self.kind}: {self.xml_id}{where}"


def _stream(element: etree.ElementBase) -> str | None:
    """The column an element is typeset in -- its `p:parallelItem`'s role -- or None for
    the main flow.

    A column is one stream however many `p:parallel` rows it runs through: a scope may
    open in the primary column of one row and close in the primary column of a later one.
    """
    column = next(element.iterancestors(_PARALLEL_ITEM), None)
    return None if column is None else column.get("role")


def check_pairing(root: etree.ElementBase) -> list[PairingProblem]:
    """Every way the conditional markers under `root` fail to pair."""
    problems: list[PairingProblem] = []
    markers = list(root.iter(J_CONDITIONAL, J_END_CONDITIONAL))
    openers: dict[str, tuple[int, etree.ElementBase]] = {}
    for position, element in enumerate(markers):
        xml_id = element.get(XML_ID)
        if element.tag != J_CONDITIONAL or xml_id is None:
            continue
        if xml_id in openers:
            problems.append(PairingProblem(DUPLICATE, xml_id, element.sourceline))
        else:
            openers[xml_id] = (position, element)

    closed: set[str] = set()
    for position, element in enumerate(markers):
        if element.tag != J_END_CONDITIONAL:
            continue
        xml_id = (element.get("target") or "").removeprefix("#")
        if xml_id not in openers or xml_id in closed:
            problems.append(PairingProblem(ORPHAN, xml_id, element.sourceline))
            continue
        opener_position, opener = openers[xml_id]
        closed.add(xml_id)
        if opener_position > position:
            problems.append(PairingProblem(CLOSER_FIRST, xml_id, element.sourceline))
        elif _stream(opener) != _stream(element):
            problems.append(PairingProblem(CROSS_STREAM, xml_id, element.sourceline))

    for xml_id, (_, opener) in openers.items():
        if xml_id not in closed:
            problems.append(PairingProblem(UNCLOSED, xml_id, opener.sourceline))
    return problems


P_SILENT = f"{{{PROCESSING_NAMESPACE}}}silent"
_TEI_NOTE = "{http://www.tei-c.org/ns/1.0}note"


#: What a scope can begin with before its first words without being text: where a paragraph or
#: page begins.
_INVISIBLE = frozenset({"{http://www.tei-c.org/ns/1.0}milestone", "{http://www.tei-c.org/ns/1.0}pb"})


def _is_annotation(node: etree.ElementBase) -> bool:
    return node.tag == _TEI_NOTE and node.get("type") not in RUBRIC_NOTE_TYPES


def _opens_with_an_instruction(opener: etree.ElementBase) -> bool:
    """Whether the first thing a scope governs is its rubric.

    JLPTEI-3.md has a reading instruction sit inside the text it controls, so a source's own
    rubric -- "On Shabbat say:" -- is often the scope's first child rather than the
    conditional's note, and a description of the passage always is. It announces the scope
    all the same. An annotation the compiler anchored at the scope's start is passed over,
    as a milestone is: it is the apparatus, not the text.
    """
    node = opener
    while True:
        if (node.tail or "").strip():
            return False
        node = node.getnext()
        if node is None or not (node.tag in _INVISIBLE or _is_annotation(node)):
            break
    return node is not None and node.tag == _TEI_NOTE and node.get("type") in RUBRIC_NOTE_TYPES


def is_silent(opener: etree.ElementBase) -> bool:
    """Whether an undecided scope is shown with no delimiters of its own.

    How a scope is set off follows the source. One the source itself marks off -- with
    brackets, parentheses or a line -- is `type="marked"`, and takes the standard delimiters.
    One with an instruction, its own or the rubric it opens with, is set off by it. One with
    neither is a direction to the processor, not to the reader: an occasion's gate around a
    whole section, or the reading divisions of a humash's cycles (schema/JLPTEI-3.md, *How an
    undecided scope is set off*).
    """
    return (opener.get("type") != "marked" and opener.find(_TEI_NOTE) is None
            and not _opens_with_an_instruction(opener))


def mark_silent_scopes(root: etree.ElementBase) -> None:
    """Record on both markers of every scope under `root` whether it is silent (`p:silent`).

    The mark goes on the closer as well because each output stage meets the two apart: a
    scope around a section of parallel columns opens in one stream and closes in another, and
    the closer has no way back to its opener once a stage has copied it. Both values are
    written, so that a stage's own fallback test never overrides this one.
    """
    silent: dict[str, str] = {}
    for opener in root.iter(J_CONDITIONAL):
        value = "true" if is_silent(opener) else "false"
        opener.set(P_SILENT, value)
        silent[opener.get(XML_ID)] = value
    for closer in root.iter(J_END_CONDITIONAL):
        value = silent.get((closer.get("target") or "").removeprefix("#"))
        if value is not None:
            closer.set(P_SILENT, value)
