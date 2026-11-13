"""External compiler processor for processing specific ranges of XML files."""

import difflib
import logging
from contextlib import contextmanager
from typing import Any, Optional
from lxml.etree import ElementBase

from opensiddur.exporter.compiler import (
    CompilerProcessor,
    _ProcessingCommand,
    _ProcessingContext,
    _AnnotationCommand,
    UnresolvedTarget,
    transclusion_type_of,
)
from opensiddur.exporter.conditional_settings import CONDITIONAL_CONTROL_TAGS
from opensiddur.exporter.constants import (
    RUBRIC_NOTE_TYPES,
    JLPTEI_NAMESPACE,
    PROCESSING_NAMESPACE,
    STRUCTURAL_BLOCKS,
    TEI_NS,
    XML_NS,
    is_element_node,
)
from opensiddur.exporter.linear import LinearData
from opensiddur.exporter.refdb import UNIT_CONTAINED_BY, ReferenceDatabase
from opensiddur.exporter.urn import (
    ResolvedUrnRange,
    UrnResolver,
    split_project,
    with_project,
)
from lxml import etree

from opensiddur.exporter.marker_reconstruct import (
    doc_needs_marker_reconstruction,
    reconstruct_markered_document,
)

from opensiddur.exporter.annotation_placement import (
    place_structural_annotations,
    place_structural_annotations_in_stream,
)
from opensiddur.exporter.milestone_annotations import place_milestone_annotations

logger = logging.getLogger(__name__)


# End keys are distinct from URNs: a bounded structural correspondence also
# aligns the continuation after it, without pretending it is another milestone.
AlignmentKey = str | tuple[str, str]


def _alignment_boundaries(elements: list[ElementBase]) -> list[Optional[AlignmentKey]]:
    """Keys before milestones and the opening/closing markers of bounded units."""
    structural: dict[str, str] = {}
    boundaries = []
    for el in elements:
        corresp = el.get("corresp")
        start = el.get(f"{{{PROCESSING_NAMESPACE}}}start")
        resume = el.get(f"{{{PROCESSING_NAMESPACE}}}resume")
        end = el.get(f"{{{PROCESSING_NAMESPACE}}}end")
        key = None
        if el.tag == f"{{{TEI_NS}}}milestone":
            key = corresp
        elif el.tag in STRUCTURAL_BLOCKS:
            if corresp and (start or resume):
                structural[start or resume] = corresp
                # A resumed container was already opened in an earlier stream.
                if start:
                    key = corresp
            elif end and end in structural:
                key = (structural.pop(end), "end")
        boundaries.append(key)
    # A rubric introducing a division belongs in its new row. Conditional
    # instructions live inside the opening control element, before the div, and a
    # description first inside the scope, after it. An annotation anchored between them
    # is apparatus, and moves with them.
    for index, key in enumerate(list(boundaries)):
        if key is None or isinstance(key, tuple):
            continue
        beginning = index
        while beginning:
            previous = elements[beginning - 1]
            opening_rubric = (
                previous.tag == f"{{{JLPTEI_NAMESPACE}}}conditional"
                or previous.tag == f"{{{TEI_NS}}}note"
            )
            if (not opening_rubric or (previous.tail or "").strip()
                    or boundaries[beginning - 1] is not None):
                break
            beginning -= 1
        # Annotations before the first opener or rubric belong to the text they follow.
        while beginning < index and _is_annotation(elements[beginning]):
            beginning += 1
        if beginning != index:
            boundaries[beginning], boundaries[index] = key, None
    return boundaries


def _is_annotation(element: ElementBase) -> bool:
    return element.tag == f"{{{TEI_NS}}}note" and element.get("type") not in RUBRIC_NOTE_TYPES


def _alignment_corresps(elements: list[ElementBase]) -> set[AlignmentKey]:
    """The alignment boundaries declared in a flat marker stream."""
    return {key for key in _alignment_boundaries(elements) if key is not None}


def _shared_split_points(a: set[AlignmentKey], b: set[AlignmentKey]) -> set[AlignmentKey]:
    """The divisions two streams set beside each other are both cut at.

    Two editions need not divide the text alike: the Hebrew is divided at its accents and a
    translation cannot be, and one edition marks the parshiyot where the other marks only
    chapters. A division the other side does not carry is not a row boundary — its text
    belongs in the row of the nearest preceding division both carry, or the halves of a
    Hebrew verse would face an empty English cell and the English verse an empty Hebrew one.

    So a boundary is a URN *both* sides mark, and nothing else. Both streams are therefore
    cut at one identical key set, which is what every row having both its columns rests on,
    and in turn what reledpar's pairing of the Nth chunk on each side rests on. Where the two
    sides share no division at all they are set as a single row: the text of one beside the
    text of the other, which is the only correspondence the encoding actually declares.

    Falling back on a division only one side marks is what this must not do. It would put the
    text under a URN that side never claimed, and — since the fallback differs per side — cut
    the two streams at different keys, which is the bug this replaced: an original marking
    `bible:psalms/126/1`..`/6` beside a translation marking only
    `haggadah:barech/psalm_126/1` promoted all seven URNs to boundaries, and the psalm was
    set as six Hebrew rows facing nothing followed by its translation facing nothing.

    Not done here: if one side marked *only* ancestors of the other's marks, across more than
    one such ancestor (`…/1/1`..`/1/6`, `/2/1`..`/2/8` beside `…/1`, `…/2`), a row per
    ancestor would beat the single row this gives. That needs a corresp → row-key mapping
    returned from here and honoured by `_split_at_milestones` in place of `@corresp`. No
    project has that shape, and this rule is a strict improvement on every one that exists.
    """
    return a & b


def _attrs_structural_original(source: ElementBase) -> dict[str, str]:
    """Structural node attrs copied onto exporter carriers; never duplicate xml:id."""
    xml_id_key = f"{{{XML_NS}}}id"
    return {k: v for k, v in source.attrib.items() if k != xml_id_key}


def _carrier_attrs_from_marker_el(el: ElementBase, p_ns: str) -> dict[str, str]:
    """Attrs from flattened marker TEI nodes: drop xml:id and p:* markers."""
    xml_id_key = f"{{{XML_NS}}}id"
    p_pref = f"{{{p_ns}}}"
    return {
        k: v
        for k, v in el.attrib.items()
        if k != xml_id_key and not k.startswith(p_pref)
    }


class ExternalCompilerProcessor(CompilerProcessor):
    def _get_deepest_common_ancestor(self,
        from_start: Optional[str] = None,
        to_end: Optional[str] = None,
        include_tail_after_end: bool = False
    ) -> tuple[Optional[ElementBase], Optional[ElementBase], Optional[ElementBase], bool]:
        """
        Get the deepest common ancestor,
        the start element,
        the end element,
        a flag indicating whether to include the tail after the end element

        There is one exception: if start and end are siblings, return the start element.
        We do this because then we don't need the surrounding elements to be copied.
        """
        start_element, end_element = self._get_start_and_end_elements_from_ranges(from_start, to_end)

        if start_element is None or end_element is None:
            return None, None, None, include_tail_after_end

        if start_element is end_element:
            return start_element, start_element, end_element, include_tail_after_end
        if start_element.getparent() is end_element.getparent():
            # siblings... no need to go deeper
            return start_element, start_element, end_element, include_tail_after_end
        end_element_ancestors = set(end_element.iterancestors())
        for element in start_element.iterancestors():
            if element in end_element_ancestors:
                return element, start_element, end_element, include_tail_after_end
        raise ValueError(f"No common ancestor found for {from_start=} and {to_end=}")

    def __init__(
        self,
        project: str,
        file_name: str,
        from_start: Optional[str] = None,
        to_end: Optional[str] = None,
        include_tail_after_end: bool = False,
        linear_data: Optional[LinearData] = None,
        reference_database: Optional[ReferenceDatabase] = None):
        """ Process the given file/project.
        Only start from the given start and end, inclusive.
        Start and end must be in the same file.

        Arguments:
            from_start: the start element path, or None to process the entire file
            to_end: the end element path, or None to process the entire file; always inclusive
            include_tail_after_end: whether to include the tail after the end element
            linear_data: the linear data
            reference_database: the reference database
        """
        super().__init__(project, file_name, linear_data=linear_data, reference_database=reference_database)

        if (from_start is None and to_end is not None) or (from_start is not None and to_end is None):
            raise ValueError("from_start and to_end must be given together, or both be None")
        self.from_start = from_start
        self.to_end = to_end

        self.deepest_common_ancestor, self.start_element, self.end_element, self.include_tail_after_end = self._get_deepest_common_ancestor(from_start, to_end, include_tail_after_end)

        # The only elements that are copied before the start is reached are the start's own
        # ancestors, to rebuild the structure it sits in. Held on self so the proxies stay alive.
        self.start_ancestors = (
            frozenset(self.start_element.iterancestors()) if self.start_element is not None else frozenset()
        )

        # None = marker mode off; [] = marker mode active
        self.marker_stack: list[tuple[str, ElementBase]] | None = None

    def _is_boundary_container_milestone(self, element: ElementBase) -> bool:
        """True when `element` is a milestone that opens the container the range's start
        opens into — e.g. a chapter milestone immediately before the verse milestone a
        range starts at — so it belongs to the range even though it sits just before it.

        Everything else immediately preceding the start is deliberately excluded (#51: a
        verse milestone from the verse before would otherwise print a spurious number), but
        a milestone whose unit *contains* the start's unit (refdb.UNIT_CONTAINED_BY) carries
        no such content of its own — it only announces the boundary the range is stepping
        into, which is exactly the range's own first moment.
        """
        tei_milestone_tag = f"{{{TEI_NS}}}milestone"
        if element.tag != tei_milestone_tag or self.start_element is None:
            return False
        if self.start_element.tag != tei_milestone_tag:
            return False
        start_unit = self.start_element.get("unit")
        containers = UNIT_CONTAINED_BY.get(start_unit, frozenset())
        following = element.getnext()
        while following is not None and not isinstance(following.tag, str):
            following = following.getnext()  # a comment between the two hides nothing
        return element.get("unit") in containers and following is self.start_element

    # ── Marker-mode helpers ─────────────────────────────────────────────────

    def _tail_is_in_range(self) -> bool:
        """True when the tail of the child just processed belongs to the compiled range.

        Must be consulted *after* the child has been processed, so that the range flags
        already reflect crossing the start or the end element: a `tei:p` that spans the
        range start owns children on both sides of it, and only the ones after it
        contribute text.

        Marker mode has to ask, because `copy_text` is fixed for the whole element while
        `before_start` flips partway through its children. Carrying tails unconditionally
        prepended every verse preceding a range to that range's output, which grew
        quadratically across the aliyot and inflated the parallel humash to 377MB.
        """
        context = self.linear_data.processing_context[-1]
        if context['before_start']:
            return False
        if context['after_end']:
            return bool(context['include_tail_after_end'])
        return True

    def _process_element_as_marker(
        self,
        element: ElementBase,
        root: Optional[ElementBase] = None,
        *,
        copy_text: bool = True,
        annotations: Optional[list[ElementBase]] = None,
    ) -> list[ElementBase]:
        """Compile element as a marker-ified structural element.

        Emits empty start/end tags with p:start/p:end attributes.
        At external transclusion boundaries, emits p:suspend before and p:resume after.
        """
        # A marker id is unique across the whole compiled book, where 32 bits would collide
        # by the birthday bound at about 77,000 structural elements -- a parallel Humash.
        p_id = self._get_path_hash(element=element, length=16)
        p_ns = PROCESSING_NAMESPACE

        xml_id_key = f"{{{XML_NS}}}id"
        start_marker = etree.Element(element.tag, nsmap=self.ns_map)
        for key, value in element.attrib.items():
            if key == xml_id_key:
                continue
            start_marker.set(key, value)
        start_marker.set(f"{{{p_ns}}}start", p_id)
        # text before first child moves to start_marker.tail
        start_marker.tail = element.text if copy_text else None

        self.marker_stack.append((p_id, element))
        result = [start_marker]
        # Resolved once at the source opening, not at its later resumed fragments. A
        # rubric is a block in its own right and stays there; the rest of the apparatus
        # is anchored on the element's first words once its content is compiled, below.
        # The notes' ids were rewritten once already, by their own processors, and their
        # pointers repointed at this context's ids (CompilerProcessor._annotate).
        movable, opening = [], []
        if annotations:
            for note in annotations:
                (opening if note.get("type") in RUBRIC_NOTE_TYPES else movable).append(note)
        if opening:
            # Original leading text must follow the apparatus, just as child insertion
            # in the ordinary compiler moves element.text behind the inserted notes.
            opening[-1].tail = (opening[-1].tail or '') + (start_marker.tail or '')
            start_marker.tail = None
            result.extend(opening)

        for child in self._reading_children(element):
            is_external_transclude = (
                child.tag == f"{{{JLPTEI_NAMESPACE}}}transclude"
                and transclusion_type_of(child) == 'external'
            )
            if is_external_transclude:
                child_context = self._update_processing_context_before(child)

                if child_context["command"] == _ProcessingCommand.SKIP:
                    # After the range's end: _process_element would return [] here too,
                    # without calling _update_processing_context_after (see its SKIP branch).
                    continue

                if self._should_skip_conditional_content():
                    # Marker-mode transclusions must honor the same conditional
                    # filtering as ordinary elements before resolving a target.
                    self._update_processing_context_after(child)
                    continue

                if child_context["command"] == _ProcessingCommand.RECURSE:
                    # Before the range's start (#63, same root cause as #53): don't resolve
                    # the transclusion or emit suspend/resume brackets for it at all. RECURSE
                    # here also means the start is not inside this child (a start ancestor
                    # would have been COPY_ELEMENT_AND_RECURSE), so its tail is pre-range
                    # text and is dropped with it.
                    self._update_processing_context_after(child)
                    continue

                if self._markers_at_start:
                    # The transclusion was the range's start: _process_element, which puts
                    # them in front of the start's output, is not called on this path.
                    result.extend(self._markers_at_start)
                    self._markers_at_start = []

                # Suspend: LIFO, no pop
                for sid, selem in reversed(self.marker_stack):
                    suspend = etree.Element(selem.tag, nsmap=self.ns_map)
                    suspend.set(f"{{{p_ns}}}suspend", sid)
                    result.append(suspend)

                transcluded = self._transclude(child, type_override='external')
                if transcluded is not None:
                    result.append(transcluded)

                # Resume: FIFO (copy TEI/XML attrs like xml:lang, not xml:id)
                for sid, selem in self.marker_stack:
                    resume = etree.Element(selem.tag, nsmap=self.ns_map)
                    for k, v in _attrs_structural_original(selem).items():
                        resume.set(k, v)
                    resume.set(f"{{{p_ns}}}resume", sid)
                    result.append(resume)

                # After the context update, as in the else branch below: if this transclude
                # was the range's end element, after_end is only set by that call, and
                # whether its tail survives is then include_tail_after_end's decision.
                self._update_processing_context_after(child)

                if child.tail and result and self._tail_is_in_range():
                    result[-1].tail = (result[-1].tail or '') + child.tail
                self._flush_closers_due(result)
            else:
                child_result = self._process_element(child, root)
                result.extend(child_result)
                if child.tail and self._tail_is_in_range():
                    if child_result and self._should_skip_conditional_content():
                        # Text inside a false scope, after a range's start markers.
                        pass
                    elif child_result:
                        last = child_result[-1]
                        last.tail = (last.tail or '') + child.tail
                    else:
                        # A child that compiles to nothing (a comment, a stripped j:conditional)
                        # still leaves its tail behind as document text.
                        self._carry_dropped_tail(result, child)
                self._flush_closers_due(result)

        self.marker_stack.pop()

        if movable and not place_structural_annotations_in_stream(result, start_marker, movable):
            # Nothing of the element's own to anchor on — an empty block, or one whose
            # whole content is a transclusion. Keep the apparatus at the opening.
            holder = opening[-1] if opening else start_marker
            movable[-1].tail = (movable[-1].tail or '') + (holder.tail or '')
            holder.tail = None
            index = result.index(holder) + 1
            result[index:index] = movable

        end_marker = etree.Element(element.tag, nsmap=self.ns_map)
        end_marker.set(f"{{{p_ns}}}end", p_id)
        end_marker.tail = element.tail
        result.append(end_marker)

        return result

    # ── Parallel-mode helpers ───────────────────────────────────────────────

    @staticmethod
    def _build_parallel_urn(target: str, parallel_project: str) -> str:
        """Replace or append @project suffix to point at parallel_project."""
        return with_project(target, parallel_project)

    @staticmethod
    def _split_at_milestones(
        elements: list[ElementBase],
        ns_map: dict,
        split_at: Optional[set[AlignmentKey]] = None,
    ) -> list[tuple[Optional[AlignmentKey], list[ElementBase]]]:
        """Split at shared milestone and bounded structural correspondences.

        Returns a list of (corresp_or_None, [elements]) tuples.
        corresp_or_None is None for content before the first milestone.
        At each boundary, open structural markers are suspended (LIFO) into the
        current sub-segment and resumed (FIFO) into the new sub-segment.

        `split_at` limits which shared keys are boundaries. None selects every
        milestone and structural correspondence, including structural end keys.
        """
        p_ns = PROCESSING_NAMESPACE
        open_stack: list[dict[str, Any]] = []  # id, tag, attrs (no xml:id, no p:*)
        result: list[tuple[Optional[AlignmentKey], list]] = [(None, [])]

        for el, boundary in zip(elements, _alignment_boundaries(elements)):
            p_start = el.get(f"{{{p_ns}}}start")
            p_end = el.get(f"{{{p_ns}}}end")
            p_suspend = el.get(f"{{{p_ns}}}suspend")
            p_resume = el.get(f"{{{p_ns}}}resume")

            if boundary is not None and (split_at is None or boundary in split_at):

                # Close current sub-segment: emit suspends LIFO (carry TEI/XML attrs)
                for item in reversed(open_stack):
                    s = etree.Element(item["tag"], nsmap=ns_map)
                    for ak, av in item["attrs"].items():
                        s.set(ak, av)
                    s.set(f"{{{p_ns}}}suspend", item["id"])
                    result[-1][1].append(s)

                # Start new sub-segment
                result.append((boundary, []))

                # Open new sub-segment: emit resumes FIFO
                for item in open_stack:
                    r = etree.Element(item["tag"], nsmap=ns_map)
                    for ak, av in item["attrs"].items():
                        r.set(ak, av)
                    r.set(f"{{{p_ns}}}resume", item["id"])
                    result[-1][1].append(r)

            # Track markers even when the marker itself opened an alignment row.
            # At a structural end, the resumed carrier closes before its tail, so
            # text following the bounded unit belongs to the new continuation row.
            if p_start or p_resume:
                open_stack.append({
                    "id": p_start or p_resume,
                    "tag": el.tag,
                    "attrs": _carrier_attrs_from_marker_el(el, p_ns),
                })
            elif p_end or p_suspend:
                open_stack = [x for x in open_stack if x["id"] != (p_end or p_suspend)]

            result[-1][1].append(el)

        result = [(c, els) for c, els in result if els]
        return result if result else [(None, [])]

    @staticmethod
    def _assemble_parallel_streams(
        primary: list[ElementBase],
        primary_lang: Optional[str],
        primary_project: str,
        primary_file: str,
        parallel: list[ElementBase],
        parallel_lang: Optional[str],
        parallel_project: str,
        parallel_file: str,
        column_order: str,
        ns_map: dict,
    ) -> list[ElementBase]:
        """Zip primary and parallel flat streams into p:parallel / p:transclude pairs.

        Splits each stream at p:transclude elements and shared milestone/structural
        boundaries. Returns a list: [p:parallel, p:transclude, p:parallel, ...].
        """
        p_ns = PROCESSING_NAMESPACE
        xml_lang = '{http://www.w3.org/XML/1998/namespace}lang'

        def split_at_transcludes(elements):
            segments = [[]]
            transcludes = []
            for el in elements:
                if (el.tag == f"{{{p_ns}}}transclude"
                        and transclusion_type_of(el) == 'external'):
                    transcludes.append(el)
                    segments.append([])
                else:
                    segments[-1].append(el)
            return segments, transcludes

        def make_item(role, lang, project, file_name, elements):
            pi = etree.Element(f"{{{p_ns}}}parallelItem", nsmap=ns_map)
            pi.set("role", role)
            if lang:
                pi.set(xml_lang, lang)
            pi.set(f"{{{p_ns}}}project", project)
            pi.set(f"{{{p_ns}}}file_name", file_name)
            for el in elements:
                pi.append(el)
            return pi

        def make_parallel(col_order, pi_prim, pi_par):
            parallel_el = etree.Element(f"{{{p_ns}}}parallel", nsmap=ns_map)
            parallel_el.set("column-order", col_order)
            parallel_el.append(pi_prim)
            parallel_el.append(pi_par)
            return parallel_el

        def source_of(transclude_el, default_project, default_file):
            """Provenance of a boundary transclude, falling back to the enclosing document."""
            if transclude_el is None:
                return default_project, default_file
            return (
                transclude_el.get(f"{{{p_ns}}}project") or default_project,
                transclude_el.get(f"{{{p_ns}}}file_name") or default_file,
            )

        def lang_of(transclude_el, default_lang):
            """Language of a boundary transclude, falling back to the enclosing document.

            Mirrors source_of(): a nested transclude may cross into a document in a
            different language (e.g. an English translation transcluded into a Hebrew
            humash), and each p:parallelItem must be stamped with the language of the
            content it actually holds, not the language of the outermost stream.
            """
            if transclude_el is None:
                return default_lang
            return transclude_el.get(xml_lang) or default_lang

        def make_rows(prim_flat, par_flat, prim_src, par_src, prim_lang, par_lang):
            # Only divisions both sides carry are row boundaries — see _shared_split_points.
            # One set, cutting both streams: the rows can only line up if the two sides are
            # cut at the same keys. Deciding this before splitting rather than merging the
            # rows afterwards matters too: every split suspends and resumes the structure
            # open across it, and those carriers would survive a merge and break the verse
            # into pieces inside its row.
            prim_corresps = _alignment_corresps(prim_flat)
            par_corresps = _alignment_corresps(par_flat)
            split_at = _shared_split_points(prim_corresps, par_corresps)
            if prim_corresps and par_corresps and not split_at:
                logger.warning(
                    "parallel: %s/%s and %s/%s divide this text on different URN axes "
                    "(%s beside %s) and so share no alignment division; setting each "
                    "beside the other as a single row. Give both sides a common corresp "
                    "to align them more finely.",
                    prim_src[0], prim_src[1], par_src[0], par_src[1],
                    min(prim_corresps, key=str), min(par_corresps, key=str),
                )
            prim_sub = ExternalCompilerProcessor._split_at_milestones(
                prim_flat, ns_map, split_at)
            par_sub = ExternalCompilerProcessor._split_at_milestones(
                par_flat, ns_map, split_at)

            def by_key(segments, source):
                """The segments by alignment key. A key repeated in one stream (a refrain
                carrying the same corresp twice) keeps its first segment: the join is on the
                URN, and two segments cannot both sit beside the other side's one. The rest
                are dropped, and said to be."""
                found: dict[Optional[AlignmentKey], list] = {}
                for c, els in segments:
                    if c not in found:
                        found[c] = els
                    elif c is not None and els:
                        logger.warning(
                            "parallel: %s/%s carries the alignment key %s more than once; "
                            "only its first segment is set in parallel", source[0], source[1], c)
                return found

            prim_by_c = by_key(prim_sub, prim_src)
            par_by_c = by_key(par_sub, par_src)

            # The preamble — content before the first shared division — is the first row
            # whichever side carries it. _split_at_milestones drops an empty one, so a
            # primary that opens exactly on a shared division has no None segment, and
            # taking document order from it alone would order the parallel's opening text
            # after every row: the same "prints below instead of beside" failure, in
            # miniature. Merging a one-sided preamble into the row after it is not the
            # answer — it ends in p:suspend carriers the next segment resumes, and joining
            # them would leave that pair stranded mid-row.
            seen: set = set()
            ordered: list = []
            if prim_by_c.get(None) or par_by_c.get(None):
                seen.add(None)
                ordered.append(None)
            for c, _ in prim_sub:
                if c not in seen:
                    seen.add(c)
                    ordered.append(c)
            # Both sides are cut at one key set, so this second pass should find nothing
            # new. It stays as a safety net: a stream that omits a shared corresp still
            # contributes its rows here rather than losing them.
            for c, _ in par_sub:
                if c not in seen:
                    seen.add(c)
                    ordered.append(c)

            rows = []
            for c in ordered:
                p_elems = prim_by_c.get(c, [])
                q_elems = par_by_c.get(c, [])
                if not p_elems and not q_elems:
                    continue
                rows.append(make_parallel(
                    column_order,
                    make_item("primary", prim_lang, prim_src[0], prim_src[1], p_elems),
                    make_item("parallel", par_lang, par_src[0], par_src[1], q_elems),
                ))
            return rows

        def transclude_key(transclude_el):
            """What a transclusion takes, whichever project it takes it from."""
            return (split_project(transclude_el.get('target') or '')[0],
                    split_project(transclude_el.get('targetEnd') or '')[0])

        def pair_transcludes(prim_ts, par_ts):
            """(i, j) for each primary transclusion paired, in order, with a parallel one.

            Paired first by what they transclude, as many as can be kept in order (the
            longest common subsequence of the two key sequences), not by position: a column
            that transcludes one file more than the other must not set the next file's
            translation beside the wrong text. Between two such pairs, what is left on each
            side is paired by position, as everything once was -- the two sides may take the
            same text at different granularity (a chapter beside its verses). Only what is
            left over then is set alone.
            """
            prim_keys = [transclude_key(t) for t in prim_ts]
            par_keys = [transclude_key(t) for t in par_ts]
            matcher = difflib.SequenceMatcher(None, prim_keys, par_keys, autojunk=False)
            anchors = [(block.a + k, block.b + k)
                       for block in matcher.get_matching_blocks() for k in range(block.size)]
            pairs = []
            i0 = j0 = 0
            for i, j in anchors + [(len(prim_ts), len(par_ts))]:
                gap = min(i - i0, j - j0)
                pairs.extend((i0 + k, j0 + k) for k in range(gap))
                if i < len(prim_ts):
                    pairs.append((i, j))
                i0, j0 = i + 1, j + 1
            return pairs

        def combine(prim_t, par_t, prim_src, par_src, prim_lang, par_lang):
            """One p:transclude from a primary and a parallel transclusion, either possibly absent.

            Recurses: the parallel block ends at *every* external transclusion, at every depth.
            Going through assemble() rather than make_rows() means any transclude among these
            children is hoisted out too, so a p:parallelItem never contains a p:transclude and
            parallels never nest. The p:transclude wrapper itself is a display no-op, so the
            hierarchy it holds is independent of the enclosing one rather than nested inside it.
            Items built from a transcluded document must be attributed to that document, not to
            the enclosing one: metadata.get_file_references reads these attributes to build the
            licences and bibliography, and numbered-stream in reledmac.xslt reads
            @xml:lang to pick the stream's typesetting direction, so a stale language here
            mislabels a translation as the host document's language and gets it mirrored under
            RTL (#p856).
            """
            combined = etree.Element(f"{{{p_ns}}}transclude", nsmap=ns_map)
            for key, val in (prim_t if prim_t is not None else par_t).attrib.items():
                combined.set(key, val)
            inner = assemble(
                list(prim_t) if prim_t is not None else [],
                list(par_t) if par_t is not None else [],
                source_of(prim_t, *prim_src), source_of(par_t, *par_src),
                lang_of(prim_t, prim_lang), lang_of(par_t, par_lang))
            for child in inner:
                combined.append(child)
            return combined

        def assemble(prim_flat, par_flat, prim_src, par_src, prim_lang, par_lang):
            primary_segments, primary_transcludes = split_at_transcludes(prim_flat)
            parallel_segments, parallel_transcludes = split_at_transcludes(par_flat)

            def rows(prim_elements, par_elements):
                return make_rows(prim_elements, par_elements, prim_src, par_src,
                                 prim_lang, par_lang)

            def joined(prim_t, par_t):
                return combine(prim_t, par_t, prim_src, par_src, prim_lang, par_lang)

            # Segment k precedes transclusion k. Between two matched transclusions, each
            # side's unmatched ones are set alone, each followed by its own segment; the
            # sentinel pair carries the segments after the last match.
            pairs = pair_transcludes(primary_transcludes, parallel_transcludes)
            pairs.append((len(primary_transcludes), len(parallel_transcludes)))
            output = []
            i0 = j0 = 0
            for i, j in pairs:
                output.extend(rows(primary_segments[i0], parallel_segments[j0]))
                for k in range(i0, i):
                    logger.warning(
                        "parallel: %s/%s transcludes %s, which %s/%s has no counterpart of; "
                        "it is set without a parallel column",
                        prim_src[0], prim_src[1], primary_transcludes[k].get('target'),
                        par_src[0], par_src[1])
                    output.append(joined(primary_transcludes[k], None))
                    output.extend(rows(primary_segments[k + 1], []))
                for k in range(j0, j):
                    logger.warning(
                        "parallel: %s/%s transcludes %s, which %s/%s has no counterpart of; "
                        "it is set without a primary column",
                        par_src[0], par_src[1], parallel_transcludes[k].get('target'),
                        prim_src[0], prim_src[1])
                    output.append(joined(None, parallel_transcludes[k]))
                    output.extend(rows([], parallel_segments[k + 1]))
                if i < len(primary_transcludes):
                    output.append(joined(primary_transcludes[i], parallel_transcludes[j]))
                i0, j0 = i + 1, j + 1
            return output

        return assemble(
            primary, parallel,
            (primary_project, primary_file), (parallel_project, parallel_file),
            primary_lang, parallel_lang)

    def _resolve_parallel_range(self, target: str, target_end: Optional[str], parallel_project: str):
        """Resolve a parallel URN to (project, file_name, from_start, to_end, include_tail).

        Resolved as the primary is (`_get_start_and_end_from_ranges`), within
        parallel_project. A project that does not divide the text this finely -- a translation
        has no accents and so carries no half-verses -- sets the containing verse beside the
        primary rather than leaving the column empty; make_rows pairs the two up at whatever
        division they have in common.

        Returns None if the URN cannot be resolved in parallel_project.
        """
        parallel_target = self._build_parallel_urn(target, parallel_project)
        parallel_end = (self._build_parallel_urn(target_end, parallel_project)
                        if target_end is not None else None)
        try:
            resolved = self._get_start_and_end_from_ranges(
                parallel_target, parallel_end, project_priority=[parallel_project])
        except UnresolvedTarget as unresolved:
            # The usual case: this project does not carry the text at all.
            logger.debug("parallel: %s has no column for %s: %s",
                         parallel_project, parallel_target, unresolved)
            return None
        except Exception:
            logger.warning(
                "parallel: could not resolve %s in project %s; that project contributes no "
                "parallel column here", parallel_target, parallel_project, exc_info=True)
            return None
        end = resolved.end
        return (resolved.start.project, resolved.start.file_name, resolved.start.element_path,
                end.end_element_path or end.element_path, end.end_includes_tail)

    def _transclude_parallel(self, element: ElementBase, transclude_range: ResolvedUrnRange, transclusion_type: str) -> Optional[ElementBase]:
        """Compile a transclusion in parallel mode, returning p:transclude(p:parallel(...)).

        Returns None if no parallel project resolves, signalling caller to fall back.
        """
        target = element.get('target')
        target_end = element.get('targetEnd')

        primary_project = transclude_range.start.project
        primary_file = transclude_range.start.file_name
        primary_start = transclude_range.start.element_path
        primary_end = transclude_range.end.end_element_path or transclude_range.end.element_path
        include_tail = transclude_range.end.end_includes_tail

        with self._parallel_sub_compilation():
            # Establish a successful counterpart before assigning it apparatus;
            # failed resolution/compilation must leave primary fallback unfiltered.
            parallel_result = None
            parallel_project = None
            parallel_file = None
            parallel_proc = None

            for proj in self.linear_data.parallel_projects:
                # Never parallelize a project against itself; doing so duplicates streams and
                # can introduce duplicate xml:id values (e.g., anchors) into the assembled output.
                if proj == primary_project:
                    continue
                resolved = self._resolve_parallel_range(target, target_end, proj)
                if resolved is None:
                    continue
                p_project, p_file, p_start, p_end, p_tail = resolved
                try:
                    with self._printed_annotations_rollback(), self._parallel_priority(p_project):
                        parallel_proc = ExternalCompilerProcessor(
                            p_project, p_file,
                            from_start=p_start,
                            to_end=p_end,
                            include_tail_after_end=p_tail,
                            linear_data=self.linear_data,
                            reference_database=self._refdb)
                        parallel_proc.marker_stack = []
                        parallel_result = parallel_proc.process()
                    parallel_project = p_project
                    parallel_file = p_file
                    break
                except Exception:
                    logger.warning(
                        "parallel: compiling %s/%s as the parallel column for %s failed; "
                        "trying the next configured parallel project",
                        p_project, p_file, target, exc_info=True)
                    continue

            if parallel_result is not None:
                with self._primary_annotations(parallel_project):
                    primary_proc = ExternalCompilerProcessor(
                        primary_project, primary_file,
                        from_start=primary_start,
                        to_end=primary_end,
                        include_tail_after_end=include_tail,
                        linear_data=self.linear_data,
                        reference_database=self._refdb)
                    primary_proc.marker_stack = []
                    with self._transclusion_guard(primary_project, primary_file, primary_start,
                                                  primary_end, target):
                        primary_result = primary_proc.process()

        if parallel_result is None:
            return None

        assembled = self._assemble_parallel_streams(
            primary_result, primary_proc.root_language,
            primary_project, primary_file,
            parallel_result, parallel_proc.root_language,
            parallel_project, parallel_file,
            str(self.linear_data.parallel_column_order),
            self.ns_map,
        )

        processing_element = etree.Element(f"{{{PROCESSING_NAMESPACE}}}transclude", nsmap=self.ns_map)
        processing_element.set('target', target)
        if target_end:
            processing_element.set('targetEnd', target_end)
        processing_element.set('type', transclusion_type)
        processing_element.set(f"{{{PROCESSING_NAMESPACE}}}project", primary_project)
        processing_element.set(f"{{{PROCESSING_NAMESPACE}}}file_name", primary_file)

        context_lang = self._get_in_scope_language(element)
        if primary_proc.root_language and context_lang != primary_proc.root_language:
            processing_element.set('{http://www.w3.org/XML/1998/namespace}lang', primary_proc.root_language)

        for child in assembled:
            processing_element.append(child)

        return processing_element

    @contextmanager
    def _parallel_sub_compilation(self):
        """Suppress nested parallel triggers for the duration of a sub-compilation.

        Parallel blocks end at every external transclusion and never nest, so nothing compiled
        underneath a parallel sub-compilation may open a parallel block of its own.
        """
        self.linear_data.parallel_compilation_depth += 1
        try:
            yield
        finally:
            self.linear_data.parallel_compilation_depth -= 1

    @contextmanager
    def _primary_annotations(self, parallel_project: str):
        """Leave the successfully selected column's enabled apparatus on that side."""
        saved = self.linear_data.annotation_projects
        try:
            self.linear_data.annotation_projects = [p for p in saved if p != parallel_project]
            yield
        finally:
            self.linear_data.annotation_projects = saved

    @contextmanager
    def _parallel_priority(self, parallel_project: str):
        """Select column-local text, instructions, and explicitly enabled apparatus."""
        saved_priority = self.linear_data.project_priority
        saved_instr = self.linear_data.instruction_priority
        saved_annotations = self.linear_data.annotation_projects
        try:
            column_priority = [parallel_project] + [
                project for project in self.linear_data.parallel_projects
                if project != parallel_project]
            self.linear_data.project_priority = column_priority
            self.linear_data.instruction_priority = column_priority
            self.linear_data.annotation_projects = [
                p for p in saved_annotations if p == parallel_project]
            yield
        finally:
            self.linear_data.project_priority = saved_priority
            self.linear_data.instruction_priority = saved_instr
            self.linear_data.annotation_projects = saved_annotations

    def _root_correspondence_urn(self) -> Optional[str]:
        """The URN identifying this document as a whole, for parallel-column matching.

        Prefers the @corresp of the body's first tei:div, which is what the reference
        database indexes; falls back to the header's URN idno with any @project stripped.
        Returns None if the document declares neither.
        """
        body_div = self.root_tree.find(
            f"{{{TEI_NS}}}text/{{{TEI_NS}}}body/{{{TEI_NS}}}div")
        if body_div is not None and body_div.get('corresp'):
            return body_div.get('corresp')

        idno = self.root_tree.find(
            f"{{{TEI_NS}}}teiHeader//{{{TEI_NS}}}idno[@type='urn']")
        if idno is not None and idno.text:
            return split_project(idno.text.strip())[0]

        return None

    def _select_root_parallel_project(self) -> Optional[tuple[str, str]]:
        """Pick the project holding this document's counterpart, as (project, file_name).

        Correspondence is decided by URN, not by file name: two documents pair up only when
        the parallel project actually contains this document's URN. Matching on file name
        alone pairs unrelated documents that happen to share a name -- every project has an
        index.xml -- which silently commits the whole compilation to a bogus column pairing
        and suppresses the per-transclusion parallels that would have been correct.

        Returns None when this document has no counterpart, which is the normal case for a
        project that holds no text of its own and only transcludes (its URNs are private to
        it, while its transclusion *targets* are what the parallel project shares).
        """
        root_urn = self._root_correspondence_urn()
        if root_urn is None:
            logger.warning(
                "parallel: %s/%s declares no URN, so no parallel counterpart can be "
                "identified; falling back to per-transclusion parallels",
                self.project, self.file_name)
            return None

        for proj in self.linear_data.parallel_projects:
            # Never parallelize a project against itself.
            if proj == self.project:
                continue
            try:
                resolved = self._urn_resolver.resolve_range(
                    self._build_parallel_urn(root_urn, proj))
            except Exception:
                logger.warning(
                    "parallel: resolving %s in project %s failed", root_urn, proj,
                    exc_info=True)
                continue
            if not resolved:
                continue
            match = resolved[0]
            file_name = (match.start.file_name
                         if isinstance(match, ResolvedUrnRange) else match.file_name)
            return proj, file_name

        logger.warning(
            "parallel: %s (%s/%s) has no counterpart in any configured parallel project "
            "(%s); falling back to per-transclusion parallels",
            root_urn, self.project, self.file_name,
            ", ".join(self.linear_data.parallel_projects) or "none")
        return None

    def _process_parallel_root(self) -> Optional[list[ElementBase]]:
        """Compile this file in parallel mode, replacing tei:body with p:parallel content.

        Returns None if no parallel project holds a counterpart of this document, signalling
        the caller to compile normally so that each transclusion can pair itself instead.
        """
        selected = self._select_root_parallel_project()
        if selected is None:
            return None
        parallel_project, parallel_file = selected

        with self._parallel_sub_compilation():
            try:
                with self._printed_annotations_rollback(), self._parallel_priority(parallel_project):
                    parallel_proc = ExternalCompilerProcessor(
                        parallel_project, parallel_file,
                        linear_data=self.linear_data,
                        reference_database=self._refdb)
                    parallel_proc.marker_stack = []
                    parallel_result = parallel_proc.process()
            except Exception:
                logger.warning(
                    "parallel: compiling %s/%s as the parallel column for %s/%s failed; "
                    "falling back to per-transclusion parallels",
                    parallel_project, parallel_file, self.project, self.file_name,
                    exc_info=True)
                parallel_result = None

            if parallel_result is not None:
                with self._primary_annotations(parallel_project):
                    primary_proc = ExternalCompilerProcessor(
                        self.project, self.file_name,
                        linear_data=self.linear_data,
                        reference_database=self._refdb)
                    primary_proc.marker_stack = []
                    primary_result = primary_proc.process()

        if parallel_result is None:
            return None

        def _body_children(result):
            for el in result:
                if el.tag == f"{{{TEI_NS}}}TEI":
                    body = el.find(f"{{{TEI_NS}}}text/{{{TEI_NS}}}body")
                    if body is None:
                        body = el.find(f".//{{{TEI_NS}}}body")
                    if body is not None:
                        return list(body)
            return result

        assembled = self._assemble_parallel_streams(
            _body_children(primary_result), primary_proc.root_language,
            self.project, self.file_name,
            _body_children(parallel_result), parallel_proc.root_language,
            parallel_project, parallel_file,
            str(self.linear_data.parallel_column_order),
            self.ns_map,
        )

        tei_ns = TEI_NS
        tei_root = None
        for element in primary_result:
            if element.tag == f"{{{tei_ns}}}TEI":
                tei_root = element
                break
        if tei_root is None and primary_result:
            tei_root = primary_result[0]

        if tei_root is not None:
            tei_body = tei_root.find(f"{{{tei_ns}}}text/{{{tei_ns}}}body")
            if tei_body is None:
                tei_body = tei_root.find(f".//{{{tei_ns}}}body")
            if tei_body is not None:
                for child in list(tei_body):
                    tei_body.remove(child)
                tei_body.text = None
                for child in assembled:
                    tei_body.append(child)

        if primary_result:
            self._mark_file_source(
                primary_result[0], enclosing=self._enclosing_source(own_frame_on_stack=False))
        return primary_result

    # ── Standard compiler overrides ─────────────────────────────────────────

    def _update_processing_context_before(self, element: ElementBase) -> _ProcessingContext:
        """
        Update the processing context for the given element, before the element has been processed.
        """
        context = self.linear_data.processing_context[-1]

        # always reset the include_tail_after_end flag
        context['include_tail_after_end'] = False

        context['element_path'] = element.getroottree().getpath(element)
        # Possible contexts:
        #    before the deepest common ancestor has been reached, RECURSE
        #    deepest common ancestor has been reached,
        #      check if this element is the start
        #       if yes, set before_start to False and return COPY_AND_RECURSE,
        #       else
        #           before start? an ancestor of the start: COPY_ELEMENT_AND_RECURSE
        #                         anything else: RECURSE
        #           after start? COPY_AND_RECURSE
        #    after end, SKIP

        if context['after_end']:
            context['command'] = _ProcessingCommand.SKIP
            return context

        corresp = element.attrib.get("corresp", "")
        xml_id = element.attrib.get("{http://www.w3.org/XML/1998/namespace}id", "")

        # is start
        if corresp or xml_id:
            if element is self.start_element:
                context['before_start'] = False
                context['command'] = _ProcessingCommand.COPY_AND_RECURSE
                self._open_scopes_at_start()
                return context

        # is after start?
        if context['before_start']:
            if element is self.deepest_common_ancestor:
                context['inside_deepest_common_ancestor'] = True
                context['command'] = _ProcessingCommand.COPY_ELEMENT_AND_RECURSE
                return context
            elif context['inside_deepest_common_ancestor'] and element in self.start_ancestors:
                # Skeleton copies exist to rebuild the start element's ancestor chain, and
                # nothing else. Copying every element that merely precedes the start left an
                # empty shell of each one -- including verse milestones, which then printed
                # spurious verse numbers and broke parallel alignment (#51).
                context['command'] = _ProcessingCommand.COPY_ELEMENT_AND_RECURSE
                return context
            elif self._is_boundary_container_milestone(element):
                context['command'] = _ProcessingCommand.COPY_AND_RECURSE
                return context
            else:
                context['command'] = _ProcessingCommand.RECURSE
                return context

        # must be after start and before end
        context['command'] = _ProcessingCommand.COPY_AND_RECURSE
        return context

    def _update_processing_context_after(self, element: ElementBase) -> _ProcessingContext:
        """
        Update the processing context for the given element, after the element has been processed.
        """
        context = self.linear_data.processing_context[-1]

        # A single-point range (start == end == deepest_common_ancestor) must still close here,
        # since there is no deeper element for the end-element check below to ever run against.
        is_end_element = (
            not context['before_start']
            and not context['after_end']
            and element is self.end_element
        )
        if is_end_element:
            context['after_end'] = True
            # The scopes the range ends inside close where it ends, innermost first.
            self._closers_due = [
                self._closer_for(xml_id) for xml_id in reversed(self._scopes_open_in_range)]
            self._scopes_open_in_range = []

        if element is self.deepest_common_ancestor:
            context['inside_deepest_common_ancestor'] = False
            context["include_tail_after_end"] = self.include_tail_after_end if is_end_element else False
            return context

        # always reset the include_tail_after_end flag except for the one case where we are processing the end element
        context["include_tail_after_end"] = self.include_tail_after_end if is_end_element else False

        context['element_path'] = None
        return context

    def _process_element(self, element: ElementBase, root: Optional[ElementBase] = None) -> list[ElementBase]:
        # The final parallel tree no longer contains all source ancestors. Carry
        # their logical heading depth while recursing, including across files.
        depth = self.linear_data.heading_depth
        headed = (element.tag == f"{{{TEI_NS}}}div"
                  and element.find(f"{{{TEI_NS}}}head") is not None)
        before_start = self.linear_data.processing_context[-1].get('before_start', False)
        if headed and (not before_start or element is self.start_element):
            self.linear_data.heading_depth = depth + 1
        try:
            result = self._process_element_with_heading_depth(element, root)
        finally:
            self.linear_data.heading_depth = depth
        if self._markers_at_start and element is self.start_element:
            # This element was the range's start: the scopes still open around it open here.
            result = self._markers_at_start + result
            self._markers_at_start = []
        return result

    def _process_element_with_heading_depth(self, element: ElementBase, root: Optional[ElementBase] = None) -> list[ElementBase]:
        """
        Process the given element and return the list of processed elements.
        """
        # Comments and processing instructions are dropped before the processing context sees
        # them: a visit would reset include_tail_after_end and lose the end element's tail.
        if not is_element_node(element):
            return []

        context = self._update_processing_context_before(element)
        # The context is shared with every child: by the end of the loop below its command
        # is the last child's, not this element's.
        command = context["command"]

        processed = []

        if context["command"] == _ProcessingCommand.SKIP:
            return []

        if (
            self._should_skip_conditional_content()
            and element.tag not in CONDITIONAL_CONTROL_TAGS
        ):
            self._update_processing_context_after(element)
            return []

        if self._handle_settings_element(element):
            self._update_processing_context_after(element)
            return []

        handled, conditional_copy = self._handle_conditional_element(element)
        if handled:
            # Placed before the context update: a closer can be the range's end element
            # itself (a milestone range ends on the last element before the next
            # milestone), and the update is what settles which scopes the end leaves open.
            placed = self._place_conditional_marker(
                element, conditional_copy, context['before_start'])
            self._update_processing_context_after(element)
            return placed

        # Before the range's start, a transclusion or annotation must not be resolved at
        # all: resolving it here would leak content that RECURSE is meant to suppress
        # entirely (see #53), and would raise on an unresolvable target that will never
        # actually appear in the output.
        if context["command"] != _ProcessingCommand.RECURSE:
            # These return early, so they settle the context themselves: either can be the
            # range's end element, the last element before the next milestone.
            transcluded = self._transclude(element)
            if transcluded is not None:
                # Each element's ids are rewritten once, by the call that produces it. The
                # transclusion's own processor compiled what is inside, but not this wrapper.
                transcluded = self._rewrite_ids(transcluded)
                self._update_processing_context_after(element)
                return [transcluded]

            annotations, annotation_command = self._annotate(element, root)
            if annotation_command == _AnnotationCommand.REPLACE:
                # Already compiled -- and its ids rewritten -- by its own processor.
                self._update_processing_context_after(element)
                return [annotations[0]]
        else:
            annotations, annotation_command = [], _AnnotationCommand.NONE

        # Marker mode retains the start's ancestor chain for suspend/resume,
        # but pre-range siblings must not leave empty paragraph or line markers.
        # Those reconstruct as visible blank lines in poetry exports.
        if (self.marker_stack is not None and element.tag in STRUCTURAL_BLOCKS
                and (context["command"] != _ProcessingCommand.RECURSE
                     or element in self.start_ancestors)):
            result = self._process_element_as_marker(
                element,
                root,
                annotations=annotations,
                copy_text=(context["command"] == _ProcessingCommand.COPY_AND_RECURSE),
            )
            self._update_processing_context_after(element)
            return result

        if context["command"] == _ProcessingCommand.RECURSE:
            append_to = processed
        elif context["command"] == _ProcessingCommand.COPY_ELEMENT_AND_RECURSE:
            copied = etree.Element(element.tag, nsmap=self.ns_map)
            for key, value in element.attrib.items():
                copied.set(key, value)
            processed.append(copied)
            append_to = copied
        elif context["command"] == _ProcessingCommand.COPY_AND_RECURSE:
            copied = etree.Element(element.tag, nsmap=self.ns_map)
            for key, value in element.attrib.items():
                copied.set(key, value)
            copied.text = element.text
            processed.append(copied)
            append_to = copied

        if element.tag == f"{{{TEI_NS}}}head" and context["command"] != _ProcessingCommand.RECURSE:
            copied.set(f"{{{PROCESSING_NAMESPACE}}}heading-level", str(max(1, self.linear_data.heading_depth)))

        for child in self._reading_children(element):
            child_result = self._process_element(child, root)
            append_to.extend(child_result)
            if (
                context["command"] == _ProcessingCommand.COPY_AND_RECURSE
                or context["include_tail_after_end"]):
                # Only copy tail if we're not after the end marker
                if child.tail and (context["include_tail_after_end"] or not context['after_end']):
                    if child_result and self._should_skip_conditional_content():
                        # Text inside a false scope. The child itself is skipped, but a range
                        # starting here leaves the markers of the scopes open around it.
                        pass
                    elif child_result:
                        if child_result[-1].tail is None:
                            child_result[-1].tail = child.tail
                        else:
                            child_result[-1].tail += child.tail
                    else:
                        # A stripped j:conditional and friends leave no output, but the text
                        # around them is document text. See _carry_dropped_tail.
                        self._carry_dropped_tail(append_to, child)
            self._flush_closers_due(append_to)

        if command != _ProcessingCommand.RECURSE:
            # Under RECURSE, processed holds only the children's output, whose ids each
            # child has already rewritten; rewriting them again appended the same hash once
            # per level between the file's root and the range. Done before the notes go in:
            # theirs were rewritten by their own processors, and their pointers already point
            # at this context's ids.
            processed = self._rewrite_ids(processed)

        if annotation_command == _AnnotationCommand.INSERT and element.tag == f"{{{TEI_NS}}}milestone":
            # Keep apparatus with its opening milestone until the entire source
            # span is compiled, then place it at the end before parallel splitting.
            copied.extend(note for note in annotations if note.get("type") not in RUBRIC_NOTE_TYPES)
            # Rubrics belong before the addressed words, inside their new row.
            processed.extend(note for note in annotations if note.get("type") in RUBRIC_NOTE_TYPES)
        elif annotation_command == _AnnotationCommand.INSERT:
            for annotation in reversed(annotations):
                # ExternalCompilerProcessor returns a list[Element]; insertion is at the
                # sequence level, not as a child of an element.
                processed.insert(0, annotation)

        if annotation_command == _AnnotationCommand.INSERT and element.tag != f"{{{TEI_NS}}}milestone":
            # The notes went in at the head of the sequence, ahead of the element's
            # heading and its first alignment boundary. Anchor them on its first words
            # instead, now that their ids have been rewritten as top-level members.
            movable = [note for note in annotations if note.get("type") not in RUBRIC_NOTE_TYPES]
            if movable:
                for note in movable:
                    processed.remove(note)
                if not place_structural_annotations(processed, movable, container=processed):
                    for note in reversed(movable):
                        processed.insert(0, note)

        self._update_processing_context_after(element)
        return processed

    def process(self, root: Optional[ElementBase] = None) -> list[ElementBase]:
        if root is None:
            root = self.root_tree
        self._gather_file_credits()

        # Root parallel trigger
        is_root = len(self.linear_data.processing_context) == 0
        def _reconstruct_if_needed(processed: list[ElementBase]) -> None:
            if processed and doc_needs_marker_reconstruction(processed[0]):
                reconstruct_markered_document(processed[0])

        if is_root and self.linear_data.parallel_projects and not self._in_parallel_compilation:
            processed = self._process_parallel_root()
            if processed is not None:
                _reconstruct_if_needed(processed)
                return processed
            # No counterpart document: fall through to the normal path, which leaves
            # parallel_compilation_depth at 0 so that _transclude_parallel pairs each
            # external transclusion individually. A project that only arranges transclusions
            # (a humash built from Tanakh verses) has no document-level counterpart at all --
            # its correspondence with the parallel project lives entirely in its targets.

        # A p:parallel must end up a flat sibling of the surrounding flow, never wrapped in a
        # tei:div (specs/COMPILER_SPECIFICATION.md, "Parallel Compilation"). That only holds
        # if the containers *above* the parallel-triggering transclusion are marker pairs
        # too: _split_at_milestones can then suspend them at each alignment boundary and
        # marker_reconstruct rebuilds them inside each column, stamped with p:part.
        #
        # Marker mode used to begin at _transclude_parallel, so everything above the first
        # parallel transclusion stayed ordinary nested elements. Real books came out as
        # body/div/transclude/div[book]/transclude/div/transclude/p:parallel, and the TeX
        # stage -- which groups on p:parallel among the top-level nodes -- never saw a single
        # block, emitted no \begin{pairs}, and ran both columns together into one numbered
        # stream.
        if is_root and self.linear_data.parallel_projects and not self._in_parallel_compilation:
            if self.marker_stack is None:
                self.marker_stack = []

        # set the root language to the language of the deepest common ancestor if present, else root
        self.root_language = self._get_in_scope_language(
            self.deepest_common_ancestor if self.deepest_common_ancestor is not None else root)

        with self._conditional_settings_checkpoint(), self._processing_frame(_ProcessingContext(
                project=self.project,
                file_name=self.file_name,
                from_start=self.from_start,
                to_end=self.to_end,
                before_start=self.from_start is not None,
                after_end=False,  # We haven't processed anything yet, so we're not after end
                include_tail_after_end=False,
                command=_ProcessingCommand.RECURSE,
                inside_deepest_common_ancestor=False,
        )):
            processed = self._process_element(root, root)
            # Owed only when the range ended on the root itself, with no parent loop
            # to place them in.
            self._flush_closers_due(processed)

        place_milestone_annotations(processed)

        # When processing the full file (not a range transclusion), mark the file source on the root element
        # so that get_file_references() can find source files for metadata extraction
        if self.from_start is None and processed:
            self._mark_file_source(
                processed[0], enclosing=self._enclosing_source(own_frame_on_stack=False))

        # Only the outermost compilation reconstructs. A parallel sub-compilation also sees an
        # empty processing context, so `is_root` alone would reconstruct its raw marker stream
        # before assembly.
        if is_root and self.linear_data.parallel_compilation_depth == 0:
            _reconstruct_if_needed(processed)

        return processed
