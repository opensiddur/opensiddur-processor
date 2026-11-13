"""Resolve page and literal text pointers against surviving compiled content."""
import hashlib
from lxml import etree
from opensiddur.exporter.constants import RUBRIC_NOTE_TYPES

TEI = "http://www.tei-c.org/ns/1.0"
P = "http://jewishliturgy.org/ns/processing"


def _remove_preserving_tail(node):
    parent = node.getparent()
    previous = node.getprevious()
    if previous is None:
        parent.text = (parent.text or "") + (node.tail or "")
    else:
        previous.tail = (previous.tail or "") + (node.tail or "")
    parent.remove(node)


# Destinations with no content of their own: the label goes after them, not inside.
_EMPTY_DESTINATIONS = frozenset(
    "{" + TEI + "}" + name for name in ("milestone", "anchor", "pb", "lb", "cb", "ptr"))


def _insert_label(node, label, repeat=False):
    anchor = etree.Element("{" + TEI + "}anchor", type="page-label", n=label)
    if repeat:
        anchor.set("subtype", "repeat")
    if node.tag in _EMPTY_DESTINATIONS:
        anchor.tail, node.tail = node.tail, None
        node.addnext(anchor)
    else:
        anchor.tail, node.text = node.text, None
        node.insert(0, anchor)


def resolve_page_references(root, every_occurrence=False):
    """Replace edition-qualified text URNs with labels in the compiled edition.

    Literal edition-qualified references keep their words and receive local links
    when their destination survives; absent external citations remain unchanged.
    Optional spans disappear when any of their destinations is absent. Repeated
    content uses the first surviving occurrence in the requested source edition.
    With every_occurrence, as for an electronic book, whose reader may hide the first, the
    later occurrences are labelled too, with subtype="repeat".
    """
    ns = {"tei": TEI}
    page_refs = root.xpath(".//tei:ref[@type='page']", namespaces=ns)
    text_refs = [ref for ref in root.xpath(".//tei:ref[@target]", namespaces=ns)
                 if ref.get("type") != "page"
                 and ref.get("target", "").startswith("urn:x-opensiddur:text:")
                 and "@" in ref.get("target", "")]
    if not page_refs and not text_refs:
        return
    destinations = {}
    for node in root.iter():
        project = next((a.get("{" + P + "}project") for a in
                        [node, *node.iterancestors()] if a.get("{" + P + "}project")), None)
        for urn in node.get("corresp", "").split():
            if project and node.tag != "{" + TEI + "}note":
                destinations.setdefault(urn + "@" + project, []).append(node)
    for span in list(root.xpath(".//tei:seg[@type='optional-page-reference']", namespaces=ns)):
        if any(ref.get("target") not in destinations for ref in
               span.xpath(".//tei:ref[@type='page']", namespaces=ns)):
            note = span.getparent()
            _remove_preserving_tail(span)
            if (note.tag == "{" + TEI + "}note" and note.get("type") in RUBRIC_NOTE_TYPES
                    and not len(note) and not (note.text or "").strip()):
                _remove_preserving_tail(note)
    labelled = set()
    surviving_pages = root.xpath(".//tei:ref[@type='page']", namespaces=ns)
    text_refs = [ref for ref in text_refs if root in ref.iterancestors()]
    for ref in [*surviving_pages, *text_refs]:
        target = ref.get("target")
        nodes = destinations.get(target)
        if nodes is None:
            if ref.get("type") == "page":
                raise ValueError(f"Page reference destination absent: {target}")
            # A literal citation may intentionally point outside this compilation.
            continue
        label = "os-page-" + hashlib.sha256(target.encode()).hexdigest()[:20]
        if ref.get("type") == "page":
            ref.set("target", label)
        else:
            # Keep the source URI and printed words; renderers use this local label.
            ref.set("{" + P + "}local-target", label)
        if target not in labelled:
            _insert_label(nodes[0], label)
            if every_occurrence:
                for node in nodes[1:]:
                    _insert_label(node, label, repeat=True)
            labelled.add(target)
