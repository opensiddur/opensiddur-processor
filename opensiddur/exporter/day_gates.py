"""A section that says what kind of day it is for is shown only on such a day.

A `j:declare` of `opensiddur:holiday-aggregate` features -- the weekday service declaring that
it is neither Shabbat nor yom tov, the festival Amidah declaring that it is yom tov -- says
what kind of day the text it covers is for. Where the day is known to be another kind, the
section is not that day's text, and is left out: a book that follows the date shows only what
is appropriate for the day, and never reaches a section whose own settings contradict it.

The compiler does this by reading each such declaration as gated as well: it is given, as it
is loaded, a `j:conditional` on the same features in front of it, closed after its
`j:endDeclare`. The gate is judged against the day: what the date gives, before the
declaration. What an enclosing text or the volume *declares* is not the day but context, which
the section's declaration overrides -- a selichot volume for the Ten Days has a first day
before them -- and counts as unknown to the gate (compiler._TheDay); an electronic compile does
not pin it. On the reader's device the gate is judged against the day the device works out,
and against what the reader sets by hand. So:

- where they agree with it, the section stands, and the gate leaves no trace;
- where they contradict it, the section is left out;
- where they say nothing (no date), print keeps the section and leaves no trace of the gate
  (CompilerProcessor._handle_conditional_element); an electronic book keeps the gate, for the
  reader's device to decide against the day it works out. A gate with no rubric is silent.

A declaration already gated by a conditional just before it on the same features -- the way
the running order gates each occasion's sections, `j:none` of Shabbat and yom tov before a
declaration of both false (importer/util/occasion.gate) -- is left as it is.
"""

from copy import deepcopy

from lxml import etree

from opensiddur.exporter.condition_eval import (
    condition_features,
    parse_condition_element,
)
from opensiddur.exporter.conditional_settings import (
    J_ALL,
    J_CONDITIONAL,
    J_DECLARE,
    J_END_CONDITIONAL,
    J_END_DECLARE,
    XML_ID,
)
from opensiddur.exporter.constants import TEI_NS, is_element_node

TEI_FS = f"{{{TEI_NS}}}fs"

#: The feature structures that say what kind of day a text is for.
KIND_OF_DAY_FS_TYPES = frozenset({"opensiddur:holiday-aggregate"})

GATE_SUFFIX = "__day"


def is_day_gate(conditional: etree.ElementBase) -> bool:
    """Whether a j:conditional is a gate this module gave a declaration."""
    return (conditional.get(XML_ID) or "").endswith(GATE_SUFFIX)


def _previous_element(element: etree.ElementBase):
    previous = element.getprevious()
    while previous is not None and not is_element_node(previous):
        previous = previous.getprevious()
    return previous


def _reads(conditional: etree.ElementBase) -> set[tuple[str, str]]:
    try:
        return set(condition_features(parse_condition_element(conditional)))
    except ValueError:
        return set()


def gate_kind_of_day_declarations(root: etree.ElementBase) -> None:
    """Give each kind-of-day declaration in a document its gate, in place."""
    ends = {end.get("target", "").removeprefix("#"): end for end in root.iter(J_END_DECLARE)}
    for declare in list(root.iter(J_DECLARE)):
        structures = [fs for fs in declare.findall(TEI_FS) if fs.get("type") in KIND_OF_DAY_FS_TYPES]
        xml_id = declare.get(XML_ID)
        if not structures or not xml_id:
            continue
        gate = etree.Element(J_CONDITIONAL)
        gate.set(XML_ID, xml_id + GATE_SUFFIX)
        holder = gate if len(structures) == 1 else etree.SubElement(gate, J_ALL)
        for fs in structures:
            copy = deepcopy(fs)
            copy.tail = None
            holder.append(copy)
        previous = _previous_element(declare)
        if previous is not None and previous.tag == J_CONDITIONAL and _reads(gate) <= _reads(previous):
            continue
        declare.addprevious(gate)
        end = ends.get(xml_id)
        if end is None:
            # A declaration to the end of the text is a gate to the end of the text.
            continue
        closer = etree.Element(J_END_CONDITIONAL)
        closer.set("target", "#" + xml_id + GATE_SUFFIX)
        # Right after the j:endDeclare, ahead of the text that follows it.
        closer.tail, end.tail = end.tail, None
        end.addnext(closer)
