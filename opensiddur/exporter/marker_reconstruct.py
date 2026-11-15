"""
Reconstruct flattened p:start / p:suspend / p:resume / p:end streams inside
parallel export columns into nested TEI, then prune empty segments and set p:part.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from opensiddur.exporter.constants import (
    JLPTEI_NAMESPACE,
    PROCESSING_NAMESPACE,
    STRUCTURAL_BLOCKS,
    TEI_NS,
)

_P_START = f"{{{PROCESSING_NAMESPACE}}}start"
_P_END = f"{{{PROCESSING_NAMESPACE}}}end"
_P_SUSPEND = f"{{{PROCESSING_NAMESPACE}}}suspend"
_P_RESUME = f"{{{PROCESSING_NAMESPACE}}}resume"
_P_LOGICAL = f"{{{PROCESSING_NAMESPACE}}}logical-id"
_P_PART = f"{{{PROCESSING_NAMESPACE}}}part"
_PARALLEL_ITEM = f"{{{PROCESSING_NAMESPACE}}}parallelItem"
_PARALLEL = f"{{{PROCESSING_NAMESPACE}}}parallel"
_TEI_MILESTONE = f"{{{TEI_NS}}}milestone"
_TEI_PB = f"{{{TEI_NS}}}pb"
_TRANSCLUDE = f"{{{PROCESSING_NAMESPACE}}}transclude"
_CONDITIONAL_MARKERS = (
    f"{{{JLPTEI_NAMESPACE}}}conditional",
    f"{{{JLPTEI_NAMESPACE}}}endConditional",
)

_SCOPE_MARKERS = (*_CONDITIONAL_MARKERS,
                  f"{{{JLPTEI_NAMESPACE}}}declare",
                  f"{{{JLPTEI_NAMESPACE}}}endDeclare")


def _structural_marker_map(el: etree.ElementBase) -> dict[str, str]:
    out = {}
    for key, pname in (
        (_P_START, "start"),
        (_P_END, "end"),
        (_P_SUSPEND, "suspend"),
        (_P_RESUME, "resume"),
    ):
        if val := el.get(key):
            out[pname] = val
    return out


def substantive_content(el: etree.ElementBase) -> bool:
    """Whether `el` carries anything worth keeping: real text, or a tei:milestone.

    A milestone (chapter, aliyah, citation, parsha...) has no text of its own, but it is
    never filler — it is a deliberate marker the source placed there, and the exporter has
    its own rendering for each kind (or explicitly renders nothing for the ones it doesn't
    know, see reledmac.xslt's generic milestone fallback). Pruning the wrapper that holds
    one, on the same footing as a genuinely empty leftover paragraph shell, would drop it
    from the compiled document before the exporter ever sees it — which is what silently
    erased chapter numbers whenever one landed alone in its own parallel-aligned segment.
    Page breaks are nonprinting: normalization relocates them before pruning wrappers.
    """
    def walk(x: etree.ElementBase) -> bool:
        if x.tag == _TEI_MILESTONE:
            return True
        if (x.text or "").strip():
            return True
        for c in x:
            if walk(c):
                return True
            if (c.tail or "").strip():
                return True
        return False

    return walk(el)


@dataclass
class _Frame:
    pid: str
    tag: str
    attrs: dict[str, str]
    buffer: list[etree.ElementBase] = field(default_factory=list)
    #: Text serialized before structural children (marker text/tails from compiler)
    text_chunks: list[str] = field(default_factory=list)


def _absorb_marker_strings(frame: _Frame, el: etree.ElementBase) -> None:
    if el.text:
        frame.text_chunks.append(el.text)
    if el.tail:
        frame.text_chunks.append(el.tail)


def _carrier_attrs_from_marker_el(el: etree.ElementBase) -> dict[str, str]:
    p_pref = f"{{{PROCESSING_NAMESPACE}}}"
    xml_id_key = "{http://www.w3.org/XML/1998/namespace}id"
    return {k: v for k, v in el.attrib.items() if k != xml_id_key and not k.startswith(p_pref)}


def _new_wrapped_segment(
    tag: str,
    attrs: dict[str, str],
    children: list[etree.ElementBase],
    *,
    logical_id: str | None,
    leading_text_chunks: list[str],
    makeelement=None,
) -> etree.ElementBase:
    nsmap = dict(children[0].nsmap) if children else {}
    factory = makeelement or etree.Element
    wrapped = factory(tag, nsmap=nsmap) if nsmap else factory(tag)
    for k, v in attrs.items():
        wrapped.set(k, v)
    prefix = "".join(leading_text_chunks)
    leading_text_chunks.clear()
    if prefix:
        wrapped.text = prefix
    for c in children:
        wrapped.append(c)

    marker_keys = (_P_START, _P_SUSPEND, _P_RESUME, _P_END, _P_LOGICAL, _P_PART)
    for mk in marker_keys:
        if mk in wrapped.attrib:
            del wrapped.attrib[mk]

    if logical_id:
        wrapped.set(_P_LOGICAL, logical_id)
    return wrapped


def _close_open_segment(
    stack: list[_Frame],
    fragments: list[etree.ElementBase],
    pid_state: dict[str, dict[str, Any]],
    *,
    pid: str,
    kind: str,
    makeelement=None,
) -> None:
    if not stack:
        raise ValueError(f"p:{kind} for {pid=} with empty reconstruction stack")

    frame = stack.pop()
    if frame.pid != pid:
        raise ValueError(f"p:{kind} expected top frame pid={pid}, got {frame.pid}")

    st = pid_state.setdefault(pid, {})
    suspended_before = st.get("suspended", False)
    logical_id: str | None = None

    if kind == "suspend":
        st["suspended"] = True
        logical_id = pid
    elif kind == "end":
        if suspended_before:
            logical_id = pid
        pid_state.pop(pid, None)
    else:
        raise ValueError(kind)

    wrapped = _new_wrapped_segment(
        frame.tag,
        frame.attrs,
        frame.buffer,
        logical_id=logical_id,
        leading_text_chunks=frame.text_chunks,
        makeelement=makeelement,
    )

    if stack:
        stack[-1].buffer.append(wrapped)
    else:
        fragments.append(wrapped)


def _move_plain_content(
    el: etree.ElementBase,
    stack: list[_Frame],
    fragments: list[etree.ElementBase],
) -> None:
    if stack:
        stack[-1].buffer.append(el)
    else:
        fragments.append(el)


def reconstruct_container(
    pi: etree.ElementBase,
    pid_state: defaultdict[str, dict[str, Any]],
) -> None:
    """Rebuild a container's direct linear stream into nested TEI fragments (mutating it).

    Container-agnostic: it consumes whatever direct children it is given. A parallel
    column (`p:parallelItem`) is the original caller, but with document-wide marker mode
    the top-level flow (`tei:body`, and each `p:transclude`) is a marker stream too and
    is rebuilt by the same walk.
    """
    fragments: list[etree.ElementBase] = []
    stack: list[_Frame] = []

    # Leave content in its document until it is reparented. Detaching large
    # subtrees first makes lxml migrate their namespaces and IDs to temporary
    # documents, only to migrate them again when the fragments are appended.
    # The snapshot also avoids repeatedly counting lxml's linked child list.
    for el in list(pi):

        mmap = _structural_marker_map(el)

        if el.tag not in STRUCTURAL_BLOCKS:
            _move_plain_content(el, stack, fragments)
            continue

        if not mmap:
            _move_plain_content(el, stack, fragments)
            continue

        if "start" in mmap:
            pid = mmap["start"]
            fr = _Frame(pid, el.tag, _carrier_attrs_from_marker_el(el), [])
            _absorb_marker_strings(fr, el)
            stack.append(fr)
            continue

        if "resume" in mmap:
            pid = mmap["resume"]
            fr = _Frame(pid, el.tag, _carrier_attrs_from_marker_el(el), [])
            _absorb_marker_strings(fr, el)
            stack.append(fr)
            continue

        if "suspend" in mmap:
            _close_open_segment(stack, fragments, pid_state, pid=mmap["suspend"], kind="suspend", makeelement=pi.makeelement)
            continue

        if "end" in mmap:
            _close_open_segment(stack, fragments, pid_state, pid=mmap["end"], kind="end", makeelement=pi.makeelement)
            continue

        _move_plain_content(el, stack, fragments)

    if stack:
        raise ValueError(f"unclosed structural frames remain in container: {[f.pid for f in stack]}")

    retained = set(fragments)
    for el in list(pi):
        if el not in retained:
            pi.remove(el)
    for frag in fragments:
        pi.append(frag)


def _collect_logical_buckets(root: etree.ElementBase) -> dict[str, list[etree.ElementBase]]:
    buckets: dict[str, list[etree.ElementBase]] = defaultdict(list)
    for el in root.iter():
        lid = el.get(_P_LOGICAL)
        if lid:
            buckets[lid].append(el)
    return buckets


def _hoist_nonprinting_markers(segment: etree.ElementBase) -> None:
    """Keep page/scope boundaries in order when their empty display wrapper is removed.

    This is also the fallback for page markers that cannot safely be forwarded: they
    must not disappear or cross a scope just because there are no words beside them.
    """
    markers = list(segment.iter(*_SCOPE_MARKERS, _TEI_PB))
    if not markers:
        return
    parent = segment.getparent()
    position = parent.index(segment)
    for offset, marker in enumerate(markers):
        # A prunable segment has no non-whitespace text to carry with it.
        marker.tail = None
        parent.insert(position + offset, marker)
    if segment.tail:
        markers[-1].tail = segment.tail
        segment.tail = None


def _page_marker_context(element: etree.ElementBase) -> tuple:
    """A column's identity and its enclosing transclusion/scope instances."""
    ancestors = list(element.iterancestors())
    column = (element if element.tag == _PARALLEL_ITEM else
              next((a for a in ancestors if a.tag == _PARALLEL_ITEM), None))
    column_key = None if column is None else tuple(column.get(k) for k in (
        'role', '{http://www.w3.org/XML/1998/namespace}lang',
        f'{{{PROCESSING_NAMESPACE}}}project', f'{{{PROCESSING_NAMESPACE}}}file_name'))
    scopes = tuple(a for a in ancestors if a.tag in (_TRANSCLUDE, *_SCOPE_MARKERS))
    return column_key, scopes


def _forward_page_markers(segment, destination, nodes, positions, forwarded) -> bool:
    """Prepend leading page markers to a continuation, without passing text or scopes."""
    markers = list(segment.iter(_TEI_PB))
    if (not markers or (segment.tail or '').strip()
            or next(segment.iter(*_SCOPE_MARKERS), None) is not None):
        return False
    context = _page_marker_context(segment)
    if context != _page_marker_context(destination):
        return False
    moved = {marker for group in forwarded.values() for marker in group}
    for node in nodes[positions[segment] + 1:positions[destination]]:
        if node in moved:
            continue
        node_context = _page_marker_context(node)
        # The opposite column does not intervene in this column's source order.
        if node_context[0] is not None and node_context[0] != context[0]:
            continue
        if node.tag in (_TRANSCLUDE, *_SCOPE_MARKERS):
            return False
        if (node.text or '').strip() or (node.tail or '').strip():
            return False
    previous = forwarded.setdefault(destination, [])
    prefix = destination.text or ''
    destination.text = None
    if previous:
        prefix = (previous[-1].tail or '') + prefix
        previous[-1].tail = None
    for index, marker in enumerate(markers, len(previous)):
        marker.tail = None  # Discard indentation from the empty source wrapper.
        destination.insert(index, marker)
    previous.extend(markers)
    if prefix:
        markers[-1].tail = (markers[-1].tail or '') + prefix
    return True


def normalize_segment_parts(root: etree.ElementBase) -> None:
    buckets = _collect_logical_buckets(root)
    stray_markers = {_P_START, _P_SUSPEND, _P_RESUME, _P_END}
    nodes = list(root.iter())
    positions = {el: i for i, el in enumerate(nodes)}
    forwarded: dict[etree.ElementBase, list[etree.ElementBase]] = {}

    for _lid, elems in buckets.items():
        for index, e in enumerate(elems):
            if substantive_content(e):
                continue
            parent = e.getparent()
            if parent is not None:
                if next(e.iter(_TEI_PB), None) is not None:
                    destination = next((candidate for candidate in elems[index + 1:]
                                        if candidate.getparent() is not None
                                        and substantive_content(candidate)), None)
                    if destination is not None:
                        _forward_page_markers(e, destination, nodes, positions, forwarded)
                # Trailing markers and markers blocked by a scope stay where they were,
                # but without the otherwise empty paragraph/division around them.
                _hoist_nonprinting_markers(e)
                parent.remove(e)

        surviving = [e for e in elems if e.getparent() is not None]

        for e in surviving:
            for mk in stray_markers:
                if mk in e.attrib:
                    del e.attrib[mk]

        for e in surviving:
            if _P_PART in e.attrib:
                del e.attrib[_P_PART]

        if len(surviving) == 1:
            el = surviving[0]
            el.attrib.pop(_P_LOGICAL, None)
        elif len(surviving) > 1:
            for i, el in enumerate(surviving):
                if i == 0:
                    el.set(_P_PART, "first")
                elif i == len(surviving) - 1:
                    el.set(_P_PART, "last")
                else:
                    el.set(_P_PART, "middle")
                el.attrib.pop(_P_LOGICAL, None)


def _strip_stray_processing_markers_under(element: etree.ElementBase) -> None:
    for el in element.iter():
        keys_to_strip = (_P_START, _P_SUSPEND, _P_RESUME, _P_END, _P_LOGICAL)
        for mk in keys_to_strip:
            if mk in el.attrib:
                del el.attrib[mk]


def doc_needs_marker_reconstruction(root: etree.ElementBase) -> bool:
    if root.find(f".//{{{PROCESSING_NAMESPACE}}}parallel") is not None:
        return True
    for el in root.iter():
        if el.tag not in STRUCTURAL_BLOCKS:
            continue
        if any(el.get(attr) for attr in (_P_START, _P_END, _P_SUSPEND, _P_RESUME)):
            return True
    return False


def _marker_containers(root: etree.ElementBase) -> list[etree.ElementBase]:
    """Elements outside the parallel columns whose direct children form a marker stream.

    Under document-wide marker mode the top-level flow is flattened the same way a column
    is, so `tei:body` — and any `p:transclude` or transcluded `tei:body` beneath it — has
    to be rebuilt too. Found by inspection rather than by tag, because which element ends
    up holding the stream depends on how the transclusion was spliced in.
    """
    containers = []
    for el in root.iter():
        if el.tag == _PARALLEL_ITEM:
            continue
        if any(child.tag in STRUCTURAL_BLOCKS and _structural_marker_map(child) for child in el):
            containers.append(el)
    return containers


def _depth(el: etree.ElementBase) -> int:
    return sum(1 for _ in el.iterancestors())


def reconstruct_markered_document(root: etree.ElementBase) -> None:
    pid_state: defaultdict[str, dict[str, Any]] = defaultdict(dict)

    # Snapshot before iterating: reconstruct_container mutates the tree underneath us.
    for parallel in list(root.iter()):
        if parallel.tag != _PARALLEL:
            continue
        for pi in parallel:
            if pi.tag == _PARALLEL_ITEM:
                reconstruct_container(pi, pid_state)

    # Then the flow around them, deepest first, so a container is rebuilt before an
    # ancestor's pass moves it. One shared pid_state throughout: a structural element
    # suspended before a transclusion resumes in a later segment, and both halves need
    # the same logical-id for normalize_segment_parts to pair them. Pids cannot collide
    # across passes -- _get_path_hash folds in the whole processing-context stack,
    # including each range's bounds.
    for container in sorted(_marker_containers(root), key=_depth, reverse=True):
        reconstruct_container(container, pid_state)

    normalize_segment_parts(root)

    header = root.find(".//{http://www.tei-c.org/ns/1.0}teiHeader")
    if header is not None:
        _strip_stray_processing_markers_under(header)

