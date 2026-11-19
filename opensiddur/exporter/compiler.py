""" The JLPTEI compiler has the following responsibilities:

1. Take a single root file as input. This file will always be valid JLPTEI,
and may have transclusions.
2. Compile the file such that the output is a valid XML file that can be
processed linearly by the exporters. The output file need not be valid TEI.

The things that need to be done:
(1) process internal and external transclusions
(1a) remap xml:ids to make sure they are unique globally after being transcluded
(2) process conditions that result in yes/no answers. Leave maybe answers with
their instructions.
(3) process out of line annotations
(4) gather the contributor credits of every transcluded document into the compiled header.
Licences and sources stay in the files the book is compiled from, which the output stages read
through the p:project/p:file_name attributes (metadata.build_colophon).
"""

import argparse
from contextlib import contextmanager
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Literal, Optional, TypedDict
from lxml.etree import ElementBase
from lxml import etree

from opensiddur.exporter.constants import (
    RUBRIC_NOTE_TYPES,
    JLPTEI_NAMESPACE,
    PROCESSING_NAMESPACE,
    TEI_NS,
    is_element_node,
)

from opensiddur.exporter.client_settings import is_reader_supplied
from opensiddur.exporter.day_gates import is_day_gate
from opensiddur.exporter.derivation_graph import DERIVED_FS_TYPES, READ_FEATURES
from opensiddur.exporter.derived_settings import (
    STATIC_DEFAULTS,
    SettingChangeTrigger,
    get_active_setting_entry,
    recalculate_derived_settings,
    remove_derived_for_contributor,
)
from opensiddur.exporter.linear import (
    ConditionalScope,
    ConditionalSettingEntry,
    LinearData,
    get_linear_data,
    reset_linear_data,
)
from opensiddur.exporter.conditional_settings import (
    CONDITIONAL_CONTROL_TAGS,
    J_CONDITION,
    J_CONDITIONAL,
    J_DECLARE,
    J_END_CONDITIONAL,
    J_END_DECLARE,
    XML_ID,
    parse_declare_element,
)
from opensiddur.exporter.conditional_markers import check_pairing
from opensiddur.exporter.condition_eval import (
    TriState,
    condition_features,
    evaluate_condition,
    parse_condition_element,
    value_to_json,
)
from opensiddur.exporter.refdb import ReferenceDatabase, file_hash
from opensiddur.exporter.annotation_placement import place_structural_annotations_in_tree
from opensiddur.exporter.milestone_annotations import place_milestone_annotations
from opensiddur.exporter.urn import ResolvedUrnRange, UrnResolver, coarsen, split_project
from opensiddur.common.constants import PROJECT_DIRECTORY

logger = logging.getLogger(__name__)

class _ProcessingCommand(Enum):
    """ Possible ways the compiler can process an element """
    # copy the element and recurse into its children, copying its text content
    COPY_AND_RECURSE = "copy_and_recurse"
    # copy the element and recurse into its children, without copying its text content
    COPY_ELEMENT_AND_RECURSE = "copy_element_and_recurse"
    # recurse into the children without copying the element
    RECURSE = "recurse"
    # skip the element and its children
    SKIP = "skip"
    # copy the element's text content but not the element and recurse into its children
    COPY_TEXT_AND_RECURSE = "text_and_recurse"

class _AnnotationCommand(Enum):
    """ Possible ways the compiler can annotate an element """
    # insert the annotated element after the original element
    INSERT = "insert"
    # replace the original annotation with the annotated element
    REPLACE = "replace"
    # keep the element, despite instructions for inlining
    # outside of inline mode, equivalent to NONE
    KEEP = "keep"
    # no action needed
    NONE = "none"

class _ProcessingContext(TypedDict):
    project: str
    file_name: str
    element_path: Optional[str]
    from_start: Optional[str]
    to_end: Optional[str]
    before_start: bool
    after_end: bool
    include_tail_after_end: bool
    inside_deepest_common_ancestor: bool
    command: _ProcessingCommand
    
def _precedes(first: ElementBase, second: ElementBase) -> bool:
    """Whether ``first`` begins before ``second`` in document order, without containing it."""
    if first is second or any(ancestor is first for ancestor in second.iterancestors()):
        return False
    if any(ancestor is second for ancestor in first.iterancestors()):
        return False
    first_line, second_line = first.sourceline, second.sourceline
    if first_line is not None and second_line is not None and first_line != second_line:
        return first_line < second_line
    for element in first.getroottree().iter():
        if element is first:
            return True
        if element is second:
            return False
    return False


def transclusion_type_of(element: ElementBase) -> str:
    """A transclusion's type: its @type, or 'external' when that is absent or empty."""
    return element.get('type') or 'external'



class UnresolvedTarget(ValueError):
    """A transclusion target that no project in the priority list carries."""


class _TheDay:
    """The settings as the day gives them: a value declared, by the volume or a text, counts as
    unknown, and only what is derived -- from the date -- is known."""

    def __init__(self, processor):
        self._processor = processor

    def get_active_setting(self, fs_type: str, feature_name: str):
        entry = self._processor.get_active_setting_entry(fs_type, feature_name)
        if entry is None or entry.source != "derived":
            return None
        return entry.value


class CompilerProcessor:
    def __init__(
        self, 
        project: str,
        file_name: str,
        linear_data: Optional[LinearData] = None,
        reference_database: Optional[ReferenceDatabase] = None):
        """ Process the given file/project.
        Args:
            project: The project name
            file_name: The file name
            linear_data: The linear data (will use the default singleton if not given)
            reference_database: The reference database (will use the default if not given)
        
        Public data:
        self.root_tree: The root element of the tree being processed
        self.project: The project name
        self.file_name: The file name
        self.ns_map: The namespace map
        self.root_language: The language of the first processed element
            (if the processed text needs to be included in something, use this language)
        """
        self.linear_data = linear_data or get_linear_data()

        self.root_tree = self.linear_data.xml_cache.parse_xml(project, file_name)
        
        self.root_tree = self.root_tree.getroot()

        self.project = project
        self.file_name = file_name

        # The document's own prefixes, which the element paths stored for it use, plus the
        # three the compiler's own queries use. A default namespace has no prefix to use in
        # XPath, and lxml refuses a namespace map that carries one.
        document_prefixes = getattr(self.root_tree, 'nsmap', None) or {}
        self.ns_map = {prefix: uri for prefix, uri in document_prefixes.items() if prefix}
        self.ns_map.setdefault("tei", TEI_NS)
        self.ns_map.setdefault("j", JLPTEI_NAMESPACE)
        self.ns_map["p"] = PROCESSING_NAMESPACE

        self._refdb = reference_database or ReferenceDatabase()
        self._urn_resolver = UrnResolver(self._refdb)
        self._warn_if_index_is_stale()

        self.root_language = None

        # The markers of conditional scopes the range's bounds cut through. See
        # _place_conditional_marker.
        self._scopes_before_start: list[tuple[str, ElementBase]] = []
        self._markers_at_start: list[ElementBase] = []
        self._scopes_open_in_range: list[str] = []
        self._closers_due: list[ElementBase] = []

    def _warn_if_index_is_stale(self) -> None:
        """Warn, once per file, when the reference database was built from other contents.

        Element paths come from the database. A file edited since it was indexed resolves to
        whatever now stands at the old paths, which is wrong text rather than an error.
        """
        key = (self.project, self.file_name)
        if key in self.linear_data.index_checked:
            return
        self.linear_data.index_checked.add(key)
        indexed = self._refdb.indexed_hash(self.file_name, self.project)
        if not isinstance(indexed, str):
            return  # not indexed at all, which the resolver will report if it matters
        path = self.linear_data.xml_cache._path_of_file(self.project, self.file_name)
        if path.exists() and indexed != file_hash(path):
            logger.warning(
                "%s/%s has changed since it was indexed; references into it may resolve to "
                "the wrong text. Sync the reference database (python -m opensiddur.exporter.refdb).",
                self.project, self.file_name)

    @property
    def _in_parallel_compilation(self) -> bool:
        """True while any parallel sub-compilation is in progress, at any depth.

        Read from LinearData so it survives processor construction: nested processors are
        built in several places and none of them would think to forward a per-instance flag.
        """
        return self.linear_data.parallel_compilation_depth > 0

    def _get_in_scope_language(self, element: ElementBase) -> Optional[str]:
        """ Get the xml:lang attribute from the element or its ancestors.
        Returns the first xml:lang found walking up the ancestor chain, or None if not found.
        """
        lang_attr = '{http://www.w3.org/XML/1998/namespace}lang'
        for ancestor in [element] + list(element.iterancestors()):
            lang = ancestor.attrib.get(lang_attr)
            if lang:
                return lang
        return None

    def _get_path_hash(self, element: Optional[ElementBase] = None, length: int = 8) -> str:
        """ Get a hash of the path taken to get to the current processing context and element if available

        ``length`` hex digits: 8 suffice for an id, which need only differ from the other
        ids of one range; a parallel marker id is drawn from the whole book.
        """
        context_path_elements = []
        num_contexts = len(self.linear_data.processing_context)
        for i, context in enumerate(self.linear_data.processing_context):
            if i < num_contexts - 1:
                # For outer contexts include element_path (the range entry point)
                context_path_element = (
                    context['project'] + '/' +
                    context['file_name'] + ':' +
                    (context.get('element_path') or "")
                )
            else:
                # For the current context include project/file and the bounds of the range
                # being transcluded, but not element_path — element_path is reset per element
                # as it is processed and would break ID-rewriting consistency, since an
                # xml:id and a target pointing at it must hash alike. The range bounds are
                # fixed for the whole transclusion, so they are safe, and they are what
                # distinguishes two ranges of the same file transcluded into one document:
                # without them a humash pulling eleven ranges out of genesis.xml gives every
                # copy of an anchor the same rewritten id.
                context_path_element = (
                    context['project'] + '/' +
                    context['file_name'] + '@' +
                    (context.get('from_start') or "") + '-' +
                    (context.get('to_end') or "")
                )
            context_path_elements.append(context_path_element)
        if element is not None:
            element_path = element.getroottree().getpath(element)
            context_path_elements.append(':' + element_path)
        full_context_path ='+'.join(context_path_elements)
        path_hash = hashlib.sha256(full_context_path.encode('utf-8')).hexdigest()[:length]
        return path_hash

    def _rewrite_ids(self, element_or_list) -> ElementBase | list[ElementBase]:
        """ Rewrite the ids of the given element(s), rewrite local targets """
        if isinstance(element_or_list, list):
            # Handle list of elements (ExternalCompilerProcessor case)
            for element in element_or_list:
                self._rewrite_single_element_ids(element)
            return element_or_list
        else:
            # Handle single element (CompilerProcessor case)
            return self._rewrite_single_element_ids(element_or_list)
    
    def _rewrite_local_pointers(self, value: str, path_hash: str) -> str:
        """Each same-document pointer (``#id``) in ``value`` given ``path_hash``."""
        return ' '.join(
            part if not part.startswith('#') else f"{part}_{path_hash}"
            for part in re.split(r'\s+', value))

    def _repoint_targets(self, compiled: ElementBase, source: ElementBase) -> None:
        """Set ``compiled``'s pointers from ``source``'s, rewritten in the current context."""
        path_hash = self._get_path_hash()
        for attribute in ('target', 'targetEnd'):
            value = source.get(attribute)
            if value:
                compiled.set(attribute, self._rewrite_local_pointers(value, path_hash))

    def _rewrite_single_element_ids(self, element: ElementBase) -> ElementBase:
        """ Rewrite the ids of a single element """
        xml_id = element.attrib.get('{http://www.w3.org/XML/1998/namespace}id')
        target = element.attrib.get('target')
        target_end = element.attrib.get('targetEnd')
        if not xml_id and not target and not target_end:
            return element
        path_hash = self._get_path_hash()
        if xml_id:
            new_xml_id = f"{xml_id}_{path_hash}"
            element.set('{http://www.w3.org/XML/1998/namespace}id', new_xml_id)
        
        def rewrite_target(value: str) -> str:
            return self._rewrite_local_pointers(value, path_hash)

        if target:
            new_target = rewrite_target(target)
            element.set('target', new_target)
        if target_end:
            new_target_end = rewrite_target(target_end)
            element.set('targetEnd', new_target_end)
        return element

    def _get_start_and_end_elements_from_ranges(self,
        from_start: Optional[str] = None,
        to_end: Optional[str] = None
    ) -> tuple[Optional[ElementBase], Optional[ElementBase]]:
        """ Get the start and end elements from element XPath paths.
        Args:
            from_start: The start element path, if available
            to_end: The end element path, if available
        Returns:
            The start and end elements
        """
        if from_start:
            start_element = self.root_tree.xpath(from_start, namespaces=self.ns_map)
            if not start_element:
                raise ValueError(f"Start element {from_start=} not found")
            start_element = start_element[0]
        else:
            start_element = None

        if to_end:
            end_element = self.root_tree.xpath(to_end, namespaces=self.ns_map)
            if not end_element:
                raise ValueError(f"End element {to_end=} not found")
            end_element = end_element[0]
        else:
            end_element = None

        if (start_element is not None and end_element is not None
                and _precedes(end_element, start_element)):
            raise ValueError(
                f"Range in {self.project}/{self.file_name} ends before it starts: "
                f"{from_start} … {to_end}")

        return start_element, end_element

    @contextmanager
    def _transclusion_guard(self, project: str, file_name: str, start: str, end: str,
                            target: str):
        """Refuse a transclusion of a range that is already being transcluded.

        A range that transcludes itself, directly or through other files, would recurse until
        Python gave up with a RecursionError that says nothing of where the cycle is.
        """
        key = (project, file_name, start, end)
        chain = self.linear_data.transclusion_chain
        if key in chain:
            cycle = " -> ".join(f"{p}/{f}" for p, f, _s, _e in chain[chain.index(key):])
            raise ValueError(f"Transclusion cycle at {target}: {cycle} -> {project}/{file_name}")
        chain.append(key)
        try:
            yield
        finally:
            chain.pop()

    def _compile_transclusion(self, transclusion_type: str, transclude_range: ResolvedUrnRange,
                              end_element_path: str, processing_element: ElementBase):
        """Compile a transcluded range into ``processing_element``; return the processor."""
        if transclusion_type == 'external':
            from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
            processor = ExternalCompilerProcessor(
                transclude_range.start.project,
                transclude_range.start.file_name,
                from_start=transclude_range.start.element_path,
                to_end=end_element_path,
                include_tail_after_end=transclude_range.end.end_includes_tail,
                linear_data=self.linear_data,
                reference_database=self._refdb)
            # Propagate marker mode to nested processor
            if hasattr(self, 'marker_stack') and self.marker_stack is not None:
                processor.marker_stack = []
            processed_list = processor.process()
            # External transclusions should contribute textual content only (tei:text),
            # never teiHeader/sourceDesc metadata.
            tei_ns = self.ns_map.get("tei", "http://www.tei-c.org/ns/1.0")
            tei_root_tag = f"{{{tei_ns}}}TEI"
            # (Whoever digitised the words being taken is still credited: the processor
            # gathered its file's credits when it compiled it; see _gather_file_credits.)
            for processed in processed_list:
                if processed.tag == tei_root_tag:
                    text_el = processed.find(f"{{{tei_ns}}}text")
                    if text_el is None:
                        text_el = processed.find(f".//{{{tei_ns}}}text")
                    if text_el is not None:
                        for child in list(text_el):
                            processing_element.append(child)
                        continue
                    # fallback: older/invalid trees
                    body = processed.find(f"{{{tei_ns}}}text/{{{tei_ns}}}body")
                    if body is None:
                        body = processed.find(f".//{{{tei_ns}}}body")
                    if body is not None:
                        for child in list(body):
                            processing_element.append(child)
                    continue
                processing_element.append(processed)
        else:
            from opensiddur.exporter.inline_compiler import InlineCompilerProcessor
            processor = InlineCompilerProcessor(
                transclude_range.start.project,
                transclude_range.start.file_name,
                from_start=transclude_range.start.element_path,
                to_end=end_element_path,
                include_tail_after_end=transclude_range.end.end_includes_tail,
                linear_data=self.linear_data,
                reference_database=self._refdb)
            processed = processor.process()
            processing_element.text = processed.text
            for child in processed:
                processing_element.append(child)
        return processor

    def _transclude(self, 
        element: ElementBase, 
        type_override: Optional[Literal['external', 'inline']] = None
    ) -> Optional[ElementBase]:
        """
        Transclude a new root tree from the given transclusion element
        """

        if element.tag == f"{{{JLPTEI_NAMESPACE}}}transclude":
            target = element.get('target')
            target_end = element.get('targetEnd')
            # Default transclusion type is external (schema default)
            transclusion_type = type_override or transclusion_type_of(element)

            processing_element = etree.Element(f"{{{PROCESSING_NAMESPACE}}}transclude", nsmap=self.ns_map)
            
            processing_element.set('target', target)
            if target_end:
                processing_element.set('targetEnd', target_end)
            processing_element.set('type', transclusion_type)

            transclude_range = self._get_start_and_end_from_ranges(target, target_end)

            # Parallel trigger: delegate to subclass if parallel projects are configured
            if (transclusion_type == 'external'
                    and self.linear_data.parallel_projects
                    and not self._in_parallel_compilation
                    and hasattr(self, '_transclude_parallel')):
                # The primary column is guarded inside; a parallel column is another
                # project's text and may well transclude the very range it stands beside.
                result = self._transclude_parallel(element, transclude_range, transclusion_type)
                if result is not None:
                    return result
                # result is None → no parallel found, fall through to normal transclusion

            context_lang = self._get_in_scope_language(element)

            end_element_path = transclude_range.end.end_element_path or transclude_range.end.element_path
            with self._transclusion_guard(transclude_range.start.project,
                                          transclude_range.start.file_name,
                                          transclude_range.start.element_path,
                                          end_element_path, target):
                processor = self._compile_transclusion(
                    transclusion_type, transclude_range, end_element_path, processing_element)

            # Mark the file source using the transcluded file's project and file_name
            processing_element = processor._mark_file_source(
                processing_element, enclosing=(self.project, self.file_name))

            # Check if language differs and add xml:lang if needed
            # Get language of transcluded start element
            if processor.root_language and context_lang != processor.root_language:
                processing_element.set('{http://www.w3.org/XML/1998/namespace}lang', processor.root_language)
            
            return processing_element

    def _annotate(self, element: ElementBase, root: Optional[ElementBase] = None) -> tuple[list[ElementBase], _AnnotationCommand]:
        """
        Annotate the given element with the file source and project.

        There are two possible cases for what we need to do with annotations:
        1. If the element is an instructional note, we need to determine which project's
        instruction set should be used to provide the corresponding instruction. 
        If no other instruction set is available, we
        will continue to use this instruction as-is. 

        2. If the element has standoff annotation (a commentary or editorial note),
        we need to determine which project's commentary set should be used to provide
        the corresponding commentary. All selected commentaries should be loaded and
        returned.

        Args:
            element: The element to annotate
            root: The root element of the iteration, avoids infinite recursion
        Returns:
            A list of annotated elements,
            annotation command: one of INSERT or REPLACE

        """
        if root is element:  # avoid infinite recursion
            return [], _AnnotationCommand.NONE
        corresp = element.get("corresp")
        xml_id = element.get("{http://www.w3.org/XML/1998/namespace}id")

        # Assume a utility function (maybe xml namespace ns_map) is present
        tei_ns = self.ns_map.get("tei")
        tag_note = f"{{{tei_ns}}}note"
        is_note = (element.tag == tag_note)

        if not is_note and not corresp and not xml_id:
            return [], _AnnotationCommand.NONE
        project = self.project if xml_id else None
        file_name = self.file_name if xml_id else None

        # Determine whether this is an instructional note (tei:note with @type='instruction' and has a URN)
        # or otherwise select all annotations for corresp/xml_id.
        result_elements = []
        annotation_command = _AnnotationCommand.NONE

        is_instruction_note = (
            is_note
            and element.get("type") in RUBRIC_NOTE_TYPES
        )

        if is_instruction_note:
            # Find all instructional notes for this instruction URN
            # Find the highest priority instruction and select it
            if corresp:
                other_instruction_notes = self._urn_resolver.resolve(corresp)
                # need to make sure they are notes!
                prioritized_instruction = self._urn_resolver.prioritize_range(
                    other_instruction_notes, self.linear_data.instruction_priority)
                if prioritized_instruction:
                    # need to get the element, transclude it in place 
                    replacement_instruction = prioritized_instruction
                    replacement_processor = CompilerProcessor(
                        replacement_instruction.project,
                        replacement_instruction.file_name,
                        linear_data=self.linear_data,
                        reference_database=self._refdb
                    )
                    replacement_element = replacement_processor.root_tree.xpath(replacement_instruction.element_path, namespaces=self.ns_map)
                    if not replacement_element:
                        raise ValueError(f"Replacement instruction element {replacement_instruction.element_path=} not found")
                    replacement_element = replacement_element[0]
                    processed_replacement_element = replacement_processor.process(replacement_element)
                    if not(replacement_instruction.project == self.project and replacement_instruction.file_name == self.file_name):
                        self._mark_file_source(processed_replacement_element, project=replacement_instruction.project, file_name=replacement_instruction.file_name, enclosing=(self.project, self.file_name))
                    
                    # Check if language differs and add xml:lang if needed
                    annotation_lang = replacement_processor.root_language
                    insertion_context_lang = self._get_in_scope_language(element)
                    if annotation_lang and annotation_lang != insertion_context_lang:
                        processed_replacement_element.set('{http://www.w3.org/XML/1998/namespace}lang', annotation_lang)
                    
                    result_elements = [processed_replacement_element]
                    annotation_command = _AnnotationCommand.REPLACE
                else:
                    # No alternative found, keep as is
                    result_elements = []
                    annotation_command = _AnnotationCommand.KEEP
            else:
                result_elements = []
                annotation_command = _AnnotationCommand.KEEP
        elif corresp or xml_id:
            # For commentary/editorial notes, select all annotations for corresp or xml_id
            # May be standoff annotation, or inline.
            references = self._refdb.get_references_to(corresp, xml_id, project, file_name, element_tag=f"{{{TEI_NS}}}note")
            note_references = [r for r in references
                if r.element_tag =="{http://www.tei-c.org/ns/1.0}note"]
            limited_references = self._urn_resolver.prioritize_range(
                note_references, self.linear_data.annotation_projects, return_all=True)

            result_elements = []
            if limited_references:
                for reference in limited_references:
                    # A note of a print-once type is printed only where the book first reaches it
                    printed_key = (reference.project, reference.file_name, reference.element_path)
                    print_once = reference.element_type in self.linear_data.annotation_print_once_types
                    if print_once and printed_key in self.linear_data.printed_annotations:
                        continue
                    processor = CompilerProcessor(
                        reference.project,
                        reference.file_name,
                        linear_data=self.linear_data,
                        reference_database=self._refdb
                    )
                    reference_element = processor.root_tree.xpath(reference.element_path, namespaces=self.ns_map)
                    if not reference_element:
                        raise ValueError(f"Reference element {reference.element_path=} not found")
                    reference_element = reference_element[0]
                    if not self._annotation_condition_holds(reference_element):
                        # Out of context here. It has not been printed, so it keeps its print-once slot.
                        continue
                    processed_element = processor.process(reference_element)
                    # The note's own processor rewrote its pointers in the note's context, but
                    # what they point at is compiled here, in this one: point them at the ids
                    # this context gives, once, so that a note and its anchor still pair.
                    self._repoint_targets(processed_element, reference_element)
                    if not(reference.project == self.project and reference.file_name == self.file_name):
                        self._mark_file_source(processed_element, project=reference.project, file_name=reference.file_name, enclosing=(self.project, self.file_name))

                    annotation_lang = processor.root_language
                    insertion_context_lang = self._get_in_scope_language(element)
                    if annotation_lang and annotation_lang != insertion_context_lang:
                        processed_element.set('{http://www.w3.org/XML/1998/namespace}lang', annotation_lang)

                    result_elements.append(processed_element)
                    if print_once:
                        self.linear_data.printed_annotations.add(printed_key)
            if result_elements:
                annotation_command = _AnnotationCommand.INSERT
            else:
                annotation_command = _AnnotationCommand.NONE
        return result_elements, annotation_command

    @staticmethod
    def _insert_first_element(element: ElementBase, new_child: ElementBase) -> ElementBase:
        """
        Insert the new child as the first child of the element.
        Return the base element as modified.
        """
        element.insert(0, new_child)
        if element.text:
            if new_child.tail:
                new_child.tail = element.text + " " + new_child.tail
            else:
                new_child.tail = element.text
            element.text = None
        
        return element

    def _mark_file_source(self, element: ElementBase,
        project: Optional[str] = None,
        file_name: Optional[str] = None,
        *,
        enclosing: Optional[tuple[str, str]] = None,
        ) -> ElementBase:
        """Mark where ``element`` comes from, if that is not the file that encloses it.

        ``enclosing`` is the (project, file name) of the file it is set in; None means it is
        set in no file (the compiled document's root), and is always marked. The source is
        ``project``/``file_name``, defaulting to this processor's file.
        """
        source = (project or self.project, file_name or self.file_name)
        if enclosing is None or enclosing != source:
            element.set(f"{{{PROCESSING_NAMESPACE}}}file_name", source[1])
            element.set(f"{{{PROCESSING_NAMESPACE}}}project", source[0])
        return element

    def _enclosing_source(self, *, own_frame_on_stack: bool) -> Optional[tuple[str, str]]:
        """The (project, file) of the context enclosing this processor's, if any."""
        stack = self.linear_data.processing_context
        depth = len(stack) - (2 if own_frame_on_stack else 1)
        if depth < 0:
            return None
        return stack[depth]['project'], stack[depth]['file_name']

    def _resolve_or_coarsen(self, urn: str, project_priority: list[str]):
        """``urn`` resolved in the first project of ``project_priority`` that carries it.

        If none does, but a project carries the verse that contains a sub-verse point the URN
        names (see `coarsen`), that verse is taken instead, with a warning: the compiled text
        then covers more than was asked for, which is what happened before sub-verse URNs
        existed, and validate_urn_references reports the same thing ahead of a build.

        Returns (resolved, the URN it resolved as); raises ValueError if neither resolves.
        """
        resolver = self._urn_resolver
        resolved = resolver.resolve_range(urn)
        chosen = UrnResolver.prioritize_range(resolved, project_priority)
        if chosen:
            return chosen, urn
        coarser = coarsen(urn, resolves=lambda one: bool(UrnResolver.prioritize_range(
            resolver.resolve_range(one), project_priority)))
        coarsened = (UrnResolver.prioritize_range(resolver.resolve_range(coarser), project_priority)
                     if coarser else None)
        if coarsened:
            logger.warning(
                "%s/%s: no project in %s carries %s; falling back to %s, which covers "
                "more text than the reference asks for",
                self.project, self.file_name, project_priority, urn, coarser,
            )
            return coarsened, coarser
        if not resolved:
            raise UnresolvedTarget(f"Target URN {urn!r} not found")
        raise UnresolvedTarget(f"No prioritized URNs found: {urn!r} {project_priority=}")

    def _get_start_and_end_from_ranges(
        self,
        target: str,
        target_end: Optional[str] = None,
        project_priority: Optional[list[str]] = None,
        ) -> ResolvedUrnRange:
        """The start and end, inclusive, of what ``target`` (through ``target_end``) names.

        The one resolver of transclusion targets, for the primary text and for each parallel
        column alike (``project_priority`` is then the column's project).
        """
        if project_priority is None:
            project_priority = self.linear_data.project_priority
        named_project = split_project(target)[1]
        if named_project:
            # A target that names its project has chosen it; the priority list is for
            # targets that leave the choice open.
            project_priority = [named_project]

        range_start, target = self._resolve_or_coarsen(target, project_priority)

        if isinstance(range_start, ResolvedUrnRange):
            if target_end is not None:
                raise ValueError(f"If target {target=} is a range, target_end {target_end=} cannot be provided")
            return range_start
        start = range_start
        if target_end is None:
            return ResolvedUrnRange(start=start, end=start)
        # The end may name a division the start's project lacks just as the start may.
        end, _ = self._resolve_or_coarsen(target_end, [start.project])
        if isinstance(end, ResolvedUrnRange):
            raise ValueError(f"targetEnd {target_end!r} names a range; it must name one point")
        if start.file_name != end.file_name:
            raise ValueError(f"In a range, the start and end of a range must be in the same file: {start.file_name=} != {end.file_name=}")
        return ResolvedUrnRange(start=start, end=end)


    def _update_processing_context_before(self, element: ElementBase) -> _ProcessingContext:
        """
        Update the processing context for the given element, before the element has been processed.
        """
        context = self.linear_data.processing_context[-1]
        context['element_path'] = element.getroottree().getpath(element)
        context['command'] = _ProcessingCommand.COPY_AND_RECURSE
        return context
        
    def _update_processing_context_after(self, element: ElementBase) -> _ProcessingContext:
        """
        Update the processing context for the given element, after the element has been processed.
        """
        context = self.linear_data.processing_context[-1]
        context['element_path'] = None
        return context

    def _scoped_declare_id(self, xml_id: str, declare_element: ElementBase) -> str:
        """Path-scoped declaration identity, parallel to output ID rewriting."""
        return f"{xml_id}_{self._get_path_hash(declare_element)}"

    def _find_declare_element_by_xml_id(self, xml_id: str) -> ElementBase | None:
        for el in self.root_tree.iter(J_DECLARE):
            if el.get(XML_ID) == xml_id:
                return el
        return None

    def _find_conditional_element_by_xml_id(self, xml_id: str) -> ElementBase | None:
        for el in self.root_tree.iter(J_CONDITIONAL):
            if el.get(XML_ID) == xml_id:
                return el
        return None

    def _pin_known_values(self, retained: ElementBase, node, *, day_gate: bool = False) -> None:
        """Record on a retained conditional the values the compile knows for its condition.

        An electronic book resolves the condition again on the reader's device, which knows
        only the reader's settings. What the document itself declared where the condition
        stands -- a section that is Ma'ariv, a passage for a minyan -- and what was derived from
        it is part of the text, and goes with the condition, in p:pinned as JSON:
        {"<fs type>": {"<feature>": <value>}}, values as condition_eval.value_to_json, an
        explicit undefined as null.

        Pinned: the features the condition reads, and, where it reads anything the device
        derives, every feature a derivation reads (derivation_graph.READ_FEATURES) -- the device
        runs the derivations, so that a document's minyan reaches the device that derives a
        zimmun from it, and a document's Hebrew date, or a volume's place with its zone, the
        device that derives the holidays. Not pinned: the settings file's own values for the
        reader's settings, which are the book's defaults, the reader's to change.
        """
        features = set(condition_features(node))
        gate_features = set(features) if day_gate else set()
        if {fs for fs, _ in features} & DERIVED_FS_TYPES:
            features |= READ_FEATURES
        pinned: dict[str, dict[str, object]] = {}
        for fs_type, feature_name in sorted(features):
            entry = self.get_active_setting_entry(fs_type, feature_name)
            if entry is None or (entry.source == "init" and is_reader_supplied(fs_type)):
                continue
            if entry.source == "derived" and feature_name in STATIC_DEFAULTS.get(fs_type, {}):
                # A fixed default, which the device puts in place by itself.
                continue
            if (fs_type, feature_name) in gate_features and entry.source != "derived":
                # A gate is judged against the day, not against what is declared around it.
                continue
            pinned.setdefault(fs_type, {})[feature_name] = value_to_json(entry.value)
        if pinned:
            holder = etree.SubElement(retained, f"{{{PROCESSING_NAMESPACE}}}pinned")
            holder.text = json.dumps(pinned, ensure_ascii=False, sort_keys=True)

    def _copy_element_subtree(self, element: ElementBase) -> ElementBase:
        """Deep-copy an element subtree for retained conditional markers.

        The tail is excluded: it is the text following the marker in its parent, not part of
        the marker. Serialising it would put content after the root element, which cannot be
        parsed back as a document — which is what a retained mid-paragraph marker would do.
        The caller re-attaches the tail.
        """
        return etree.fromstring(etree.tostring(element, with_tail=False))

    def _push_conditional_scope(self, scoped_id: str, result: TriState) -> None:
        self.linear_data.conditional_scope_stack.append(
            ConditionalScope(scoped_id=scoped_id, result=result.value)
        )

    def _pop_conditional_scope(self, scoped_id: str) -> ConditionalScope:
        stack = self.linear_data.conditional_scope_stack
        for i in range(len(stack) - 1, -1, -1):
            if stack[i].scoped_id == scoped_id:
                return stack.pop(i)
        raise ValueError(f"No conditional scope found for scoped_id={scoped_id!r}")

    def _should_skip_conditional_content(self) -> bool:
        return any(
            scope.result == TriState.FALSE.value
            for scope in self.linear_data.conditional_scope_stack
        )

    def _carry_dropped_tail(self, append_to: ElementBase | list[ElementBase], child: ElementBase) -> None:
        """Carry the tail of a child that produced no output into the result.

        A conditional control element is stripped from the output, but the text around it is
        ordinary document text and must survive — mid-paragraph, that tail *is* the running
        text. Text inside a false conditional scope must not survive: it is the conditional
        text itself.

        Both cases reduce to one test, as long as it is made *after* the child has been
        processed: a ``j:conditional`` that just opened a false scope leaves that scope on the
        stack and so loses the text following it, while the ``j:endConditional`` that closes
        one has already popped it and so keeps the text following it.
        """
        if not child.tail or self._should_skip_conditional_content():
            return
        if isinstance(append_to, list):
            if append_to:
                append_to[-1].tail = (append_to[-1].tail or "") + child.tail
            return
        if len(append_to):
            append_to[-1].tail = (append_to[-1].tail or "") + child.tail
        else:
            append_to.text = (append_to.text or "") + child.tail

    def _push_declare(self, declare_id: str, entries: list[ConditionalSettingEntry]) -> None:
        """Push declared entries and trigger derived-settings recalculation."""
        self.linear_data.conditional_settings.extend(entries)
        recalculate_derived_settings(
            self.linear_data,
            trigger=SettingChangeTrigger.DECLARE,
            declare_id=declare_id,
        )

    def _end_declare(self, declare_id: str) -> None:
        """Remove declared entries for declare_id and invalidate dependent derivations."""
        declared = [
            e
            for e in self.linear_data.conditional_settings
            if e.source == "declared" and e.declare_id == declare_id
        ]
        if not declared:
            raise ValueError(f"No declared settings found for declare_id={declare_id!r}")

        self.linear_data.conditional_settings = [
            e
            for e in self.linear_data.conditional_settings
            if not (e.source == "declared" and e.declare_id == declare_id)
        ]
        remove_derived_for_contributor(self.linear_data, declare_id)
        recalculate_derived_settings(
            self.linear_data,
            trigger=SettingChangeTrigger.END_DECLARE,
            declare_id=declare_id,
        )

    @staticmethod
    def load_init_settings(
        linear_data: LinearData,
        entries: list[ConditionalSettingEntry],
    ) -> None:
        """Push YAML init entries onto linear_data (used before compile starts)."""
        linear_data.conditional_settings.extend(entries)
        recalculate_derived_settings(linear_data, trigger=SettingChangeTrigger.INIT)

    def get_active_setting_entry(
        self,
        fs_type: str,
        feature_name: str,
    ) -> ConditionalSettingEntry | None:
        """Return the winning stack entry for a feature (latest on stack)."""
        return get_active_setting_entry(self.linear_data, fs_type, feature_name)

    def get_active_setting(self, fs_type: str, feature_name: str) -> Any | None:
        """Return the active value for a feature, or None if not set."""
        entry = self.get_active_setting_entry(fs_type, feature_name)
        return entry.value if entry is not None else None

    def get_active_fs_settings(self, fs_type: str) -> dict[str, Any]:
        """Merged view of all features for an FS type."""
        feature_names: set[str] = set()
        for entry in self.linear_data.conditional_settings:
            if entry.fs_type == fs_type:
                feature_names.add(entry.feature_name)
        return {
            name: self.get_active_setting(fs_type, name)
            for name in feature_names
        }

    def _annotation_condition_holds(self, note: ElementBase) -> bool:
        """Evaluate a note's j:condition against the settings in scope where it would be inserted.

        The condition decides whether the note is printed at all: only FALSE omits it. A note
        without one always holds. (Conditioning part of a note's text is j:conditional's job.)
        """
        condition = note.find(J_CONDITION)
        if condition is None:
            return True
        return evaluate_condition(parse_condition_element(condition), self) != TriState.FALSE

    @contextmanager
    def _printed_annotations_rollback(self):
        """Forget what a compilation that fails registered: print-once notes and credits.

        A failed parallel counterpart is discarded, and the fallback that replaces it must
        still print the notes the counterpart had claimed -- and must not credit the people
        whose text it did not, after all, use.
        """
        saved = set(self.linear_data.printed_annotations)
        saved_credits = list(self.linear_data.credits)
        try:
            yield
        except BaseException:
            self.linear_data.printed_annotations = saved
            self.linear_data.credits = saved_credits
            raise

    @contextmanager
    def _processing_frame(self, context: _ProcessingContext):
        """Push a processing context for the duration of a ``process()`` call.

        The stack is cut back to where it was however the call ends. A parallel column that
        fails is caught and replaced by a fallback, which must not find the failed column's
        context still on top of the stack, tracking its own range on the wrong record.
        """
        stack = self.linear_data.processing_context
        depth = len(stack)
        stack.append(context)
        try:
            yield
        finally:
            del stack[depth:]

    @contextmanager
    def _conditional_settings_checkpoint(self):
        """Restore the settings and the scope stack as they were before processing a file.

        Nothing a transcluded file declares outlives it, even a j:declare whose j:endDeclare
        falls outside the range transcluded. The whole stack is restored rather than cut back to
        its old length: recalculating derived settings removes entries from anywhere in the
        stack and appends their new values, so the old length no longer marks where the file's
        own entries begin.
        """
        saved_settings = list(self.linear_data.conditional_settings)
        saved_scopes = list(self.linear_data.conditional_scope_stack)
        try:
            yield
        finally:
            self.linear_data.conditional_settings = saved_settings
            self.linear_data.conditional_scope_stack = saved_scopes

    def _handle_settings_element(self, element: ElementBase) -> bool:
        """Process j:declare / j:endDeclare. Returns True if handled (strip from output)."""
        if element.tag == J_DECLARE:
            xml_id = element.get(XML_ID)
            if not xml_id:
                raise ValueError("j:declare requires an xml:id attribute")
            scoped_id = self._scoped_declare_id(xml_id, element)
            entries = parse_declare_element(element, scoped_id)
            self._push_declare(scoped_id, entries)
            return True

        if element.tag == J_END_DECLARE:
            target = element.get("target")
            if not target or not target.startswith("#"):
                raise ValueError("j:endDeclare requires a fragment target attribute (e.g. #id)")
            bare_id = target[1:]
            declare_el = self._find_declare_element_by_xml_id(bare_id)
            if declare_el is None:
                raise ValueError(
                    f"j:endDeclare target {target!r} does not match a j:declare in this file"
                )
            scoped_id = self._scoped_declare_id(bare_id, declare_el)
            self._end_declare(scoped_id)
            return True

        return False

    # ── Conditional scopes cut by a range ───────────────────────────────────
    # Used by the range processors, ExternalCompilerProcessor and InlineCompilerProcessor.

    def _place_conditional_marker(
        self, element: ElementBase, marker: Optional[ElementBase], before_start: bool,
    ) -> list[ElementBase]:
        """Emit a conditional's marker so the range's scopes stay paired.

        A range transcluded from the middle of a file can start or end inside a conditional
        scope. The scope's text that falls in the range is still governed by it, so the
        range carries the scope's markers too -- but only those of scopes that overlap it:

        - a scope that opens before the start and closes before it governs nothing in the
          range, and neither its marker nor its rubric is emitted;
        - one still open at the start opens there (`_open_scopes_at_start`);
        - one the range ends inside closes where the range ends (`_closer_for`), since its
          own closer lies past the end and is never visited.

        Emitting the marker of every scope met before the start, as the compiler used to,
        left openers with no closer and rubrics for passages that were not there.
        """
        if marker is not None:
            marker = self._rewrite_ids(marker)
        if element.tag == J_CONDITIONAL:
            if marker is None:
                return []
            xml_id = element.get(XML_ID)
            if before_start:
                self._scopes_before_start.append((xml_id, marker))
                return []
            if marker.tag == J_CONDITIONAL:
                self._scopes_open_in_range.append(xml_id)
            return [marker]
        if element.tag == J_END_CONDITIONAL:
            xml_id = (element.get("target") or "").removeprefix("#")
            if before_start:
                self._scopes_before_start = [
                    scope for scope in self._scopes_before_start if scope[0] != xml_id]
                return []
            if xml_id in self._scopes_open_in_range:
                self._scopes_open_in_range.remove(xml_id)
        return [] if marker is None else [marker]

    def _open_scopes_at_start(self) -> None:
        """Open, at the range's start, the scopes still open around it.

        They count as open from this moment -- the start can also be the end, and the end
        must know to close them -- but their markers wait for the start element's output,
        which `_process_element` puts them in front of.
        """
        for xml_id, marker in self._scopes_before_start:
            if marker.tag == J_CONDITIONAL:
                self._scopes_open_in_range.append(xml_id)
            self._markers_at_start.append(marker)
        self._scopes_before_start = []

    def _closer_for(self, xml_id: str) -> ElementBase:
        """A `j:endConditional` for a scope whose own closer lies past the range's end.

        Rewritten in the same processing context as the opener, so the two still pair.
        """
        closer = etree.Element(J_END_CONDITIONAL, nsmap=self.ns_map)
        closer.set("target", f"#{xml_id}")
        self._rewrite_single_element_ids(closer)
        return closer

    def _flush_closers_due(self, append_to: ElementBase | list[ElementBase]) -> None:
        """Append the closers owed by a range that just ended, after the end and its tail."""
        if not self._closers_due:
            return
        for closer in self._closers_due:
            append_to.append(closer)
        self._closers_due = []

    def _handle_conditional_element(self, element: ElementBase) -> tuple[bool, ElementBase | None]:
        """Process j:conditional / j:endConditional, and strip j:condition.

        Returns (handled, result). result is None when stripped, or an element copy when retained.
        """
        if element.tag == J_CONDITION:
            # A note's own condition was evaluated when the note was selected; it is never text.
            return True, None
        if element.tag == J_CONDITIONAL:
            xml_id = element.get(XML_ID)
            if not xml_id:
                raise ValueError("j:conditional requires an xml:id attribute")
            scoped_id = self._scoped_declare_id(xml_id, element)
            node = parse_condition_element(element)
            day_gate = is_day_gate(element)
            # A section's kind-of-day gate (day_gates) is judged against the day -- the date and
            # what follows from it -- not against what an enclosing text or the volume declares,
            # which the section's own declaration overrides.
            result = evaluate_condition(node, _TheDay(self) if day_gate else self)
            if (result == TriState.UNDEFINED and day_gate
                    and not self.linear_data.defer_reader_settings):
                # A section's kind-of-day gate (day_gates) that print cannot decide keeps the
                # section, and prints nothing around it: it is the reader's device that
                # decides an undecided one.
                result = TriState.TRUE
            self._push_conditional_scope(scoped_id, result)
            # Nested controls must maintain the scope stack even in omitted
            # text, but their rubrics and brackets must not escape that scope.
            if self._should_skip_conditional_content():
                return True, None
            if result == TriState.UNDEFINED:
                retained = self._copy_element_subtree(element)
                if self.linear_data.defer_reader_settings:
                    self._pin_known_values(retained, node, day_gate=day_gate)
                return True, retained
            # A true condition is a passage that is simply said: the rubric telling when to
            # say it has nothing left to tell, and goes with the condition. A rubric telling
            # what the passage is belongs to the passage, and is encoded inside the scope.
            return True, None

        if element.tag == J_END_CONDITIONAL:
            target = element.get("target")
            if not target or not target.startswith("#"):
                raise ValueError("j:endConditional requires a fragment target attribute (e.g. #id)")
            bare_id = target[1:]
            conditional_el = self._find_conditional_element_by_xml_id(bare_id)
            if conditional_el is None:
                raise ValueError(
                    f"j:endConditional target {target!r} does not match a j:conditional in this file"
                )
            scoped_id = self._scoped_declare_id(bare_id, conditional_el)
            scope = self._pop_conditional_scope(scoped_id)
            if scope.result == TriState.UNDEFINED.value and not self._should_skip_conditional_content():
                return True, self._copy_element_subtree(element)
            return True, None

        return False, None

    def _wording_options(self, element):
        """Possible wordings at this choice, using occurrence-local variant settings.

        Unknown alternates keep their existing display. A known selection is exclusive;
        an explicit range inside an option still addresses that option's own words.
        """
        tag = f"{{{JLPTEI_NAMESPACE}}}option"
        options = [child for child in element if child.tag == tag]
        endpoints = (getattr(self, "start_element", None), getattr(self, "end_element", None))
        addressed = [option for option in options
                     if any(endpoint is not None and
                            (endpoint is option or option in endpoint.iterancestors())
                            for endpoint in endpoints)]
        if len(addressed) > 1:
            raise ValueError("A transclusion range crosses alternate wordings")
        if addressed:
            return addressed
        context = self.linear_data.processing_context[-1] if self.linear_data.processing_context else {}
        if context.get("before_start") or context.get("after_end"):
            # Traverse pre-range controls without validating choices whose words
            # are outside the requested passage.
            return options
        selected, possible = [], []
        for option in options:
            identity = option.get("corresp", "")
            value = (self.get_active_setting("opensiddur:variant", identity)
                     if identity.startswith("urn:x-opensiddur:condition:") else None)
            if value is True:
                selected.append(option)
            if value is not False:
                possible.append(option)
        if len(selected) > 1:
            raise ValueError(f"More than one alternate wording is selected in {self.project}/{self.file_name}")
        if selected:
            return selected
        if not possible:
            raise ValueError(f"No alternate wording is selected in {self.project}/{self.file_name}")
        return possible

    def _reading_children(self, element):
        """Visit only the selected form of an abbreviation or an edition error; never flatten
        both readings.

        Named wording options use opensiddur:variant. Unknown options retain their
        existing behavior. Source XML is not mutated.
        """
        tei = "{http://www.tei-c.org/ns/1.0}"
        if element.tag == tei + "choice":
            abbr, expan = element.find(tei + "abbr"), element.find(tei + "expan")
            if abbr is not None and expan is not None:
                yield expan if self.linear_data.abbreviation_reading == "expanded" else abbr
                return
            sic, corr = element.find(tei + "sic"), element.find(tei + "corr")
            if sic is not None and corr is not None:
                yield sic if self.linear_data.error_reading == "printed" else corr
                return
            option_tag = f"{{{JLPTEI_NAMESPACE}}}option"
            if element.find(option_tag) is not None:
                allowed = self._wording_options(element)
                # Preserve controls and other global markup between alternatives.
                yield from (child for child in element
                            if child.tag != option_tag or child in allowed)
                return
        yield from element

    def _process_element(self, element: ElementBase, root: Optional[ElementBase] = None) -> ElementBase:
        # Comments and processing instructions carry no JLPTEI meaning and cannot be rebuilt from
        # their tag. Drop them before the processing context sees them; the caller carries the tail.
        if not is_element_node(element):
            return None  # type: ignore[return-value]

        self._update_processing_context_before(element)

        if (
            self._should_skip_conditional_content()
            and element.tag not in CONDITIONAL_CONTROL_TAGS
        ):
            self._update_processing_context_after(element)
            return None  # type: ignore[return-value]

        if self._handle_settings_element(element):
            self._update_processing_context_after(element)
            return None  # type: ignore[return-value]

        handled, conditional_copy = self._handle_conditional_element(element)
        if handled:
            self._update_processing_context_after(element)
            if conditional_copy is not None:
                return self._rewrite_ids(conditional_copy)
            return None  # type: ignore[return-value]

        transcluded = self._transclude(element)
        if transcluded is not None:
            return transcluded

        annotated, annotation_command = self._annotate(element, root)
        if annotation_command == _AnnotationCommand.REPLACE:
            return annotated[0]

        copied = etree.Element(element.tag, nsmap=self.ns_map)
        
        # Copy attributes
        for key, value in element.attrib.items():
            copied.set(key, value)
        copied.text = element.text

        for child in self._reading_children(element):
            processed = self._process_element(child, root)
            if processed is None:
                self._carry_dropped_tail(copied, child)
                continue
            if child.tail:
                processed.tail = child.tail
            copied.append(processed)

        if annotation_command == _AnnotationCommand.INSERT:
            # Apparatus is anchored on the first words of the element it annotates, not
            # dropped in front of its heading and its first alignment boundary. Rubrics
            # are blocks of their own and keep the opening position; so does everything
            # else when the element has no text to anchor on. See annotation_placement.
            movable = [note for note in annotated if note.get("type") not in RUBRIC_NOTE_TYPES]
            anchored = (set() if not (movable and
                                      place_structural_annotations_in_tree(copied, movable))
                        else {id(note) for note in movable})
            for annotated_element in reversed(annotated):
                if id(annotated_element) not in anchored:
                    self._insert_first_element(copied, annotated_element)

        copied = self._rewrite_ids(copied)
        
        self._update_processing_context_after(element)
        return copied

    def _gather_file_credits(self) -> None:
        """Credit whoever digitised this file, whatever part of it is being compiled.

        The compiled document keeps the words a file contributes and drops its header, so the
        credits in that header are gathered here, by every processor that compiles a file: a
        whole-file transclusion, a range of verses, a parallel column or an inline quotation.
        Gathering them is what makes the compiled document self-describing: it can be printed,
        or turned into HTML, without reopening the sources it was built from.
        """
        header = self.root_tree.find(f"{{{TEI_NS}}}teiHeader")
        if header is not None:
            gather_credits(header, self.linear_data)

    def process(self, root: Optional[ElementBase] = None):
        """
        Recursively process elements and text nodes of root_tree as an identity transform.
        If root is not provided, use self.root_tree.
        Yields elements and string text nodes (identity traversal).

        Set the root language.
        """
        if root is None:
            root = self.root_tree
        self._gather_file_credits()

        self.root_language = self._get_in_scope_language(root)

        with self._conditional_settings_checkpoint(), self._processing_frame(_ProcessingContext(
                project=self.project,
                file_name=self.file_name,
                from_start=None,
                to_end=None,
                before_start=False,
                after_end=False,
                command=_ProcessingCommand.COPY_AND_RECURSE,
                inside_deepest_common_ancestor=False,
                include_tail_after_end=False,
        )):
            copied = self._process_element(root, root)
            place_milestone_annotations([copied])
            copied = self._mark_file_source(
                copied, enclosing=self._enclosing_source(own_frame_on_stack=True))

        return copied


TEI_NS = "http://www.tei-c.org/ns/1.0"


def gather_credits(element, linear_data) -> None:
    """Record every contributor credit in a document, before its header is dropped.

    A ``tei:respStmt`` says who *digitised* a text. The compiler takes a transcluded
    document's words and discards its header, so without this the credits of every file
    but the root are lost at the moment their words are used -- which is how a siddur
    built from two dozen files came to name the contributors of one of them.
    """
    for resp_stmt in element.iter(f"{{{TEI_NS}}}respStmt"):
        resp = resp_stmt.find(f"{{{TEI_NS}}}resp")
        name = resp_stmt.find(f"{{{TEI_NS}}}name")
        if resp is None or name is None:
            continue
        credit = (
            resp.get("key") or "",
            name.get("ref") or "",
            "".join(name.itertext()).strip(),
            "".join(resp.itertext()).strip(),
        )
        if credit not in linear_data.credits:
            linear_data.credits.append(credit)


TEI_DIV = f"{{{TEI_NS}}}div"
TEI_P = f"{{{TEI_NS}}}p"
TEI_L = f"{{{TEI_NS}}}l"


def _only_a_paragraph(element) -> bool:
    """An unnamed division holding one paragraph and nothing else.

    Unnamed because nothing in the source names it: :func:`tei.structure` gives words a
    division of their own where they find themselves beside a subdivision, and that
    division carries no URN because it addresses nothing.
    """
    return (element.tag == TEI_DIV and not element.attrib
            and len(element) == 1 and element[0].tag == TEI_P
            and not (element.text or "").strip()
            and not (element[0].tail or "").strip())


def join_split_paragraphs(root) -> None:
    """Close up a paragraph a resolved conditional had split.

    A conditional between two runs of words forces each into a division of its own, since
    a division may not hold words and subdivisions side by side. When the condition
    resolves false the passage between them goes, and the two halves of what the edition
    prints as one paragraph are left as two -- Birnbaum sets
    ``אַתָּה חוֹנֵן לְאָדָם דַּעַת`` and ``חׇנֵּנוּ מֵאִתְּךָ דֵּעָה`` as one (p.85), with the
    Havdalah that separates them said only at Ma'ariv.

    Only unnamed divisions are joined, and only to each other: one carries no address, so
    nothing refers to it and nothing is lost by its going. A division the source named
    keeps its own paragraph however short it is.
    """
    for parent in root.iter():
        run = list(parent)
        for element in run:
            if not _only_a_paragraph(element):
                continue
            following = element.getnext()
            while following is not None and _only_a_paragraph(following):
                head, tail = element[0], following[0]
                last = list(head)[-1] if len(head) else None
                if last is not None:
                    last.tail = ((last.tail or "") + " " + (tail.text or "")).rstrip() + " "
                else:
                    head.text = ((head.text or "") + " " + (tail.text or "")).strip() + " "
                for child in list(tail):
                    head.append(child)
                parent.remove(following)
                following = element.getnext()


def drop_empty_scopes(root) -> None:
    """Remove a conditional that governs nothing.

    A scope can be left empty by what it governs going elsewhere -- the Eretz Yisrael
    insert in the Gevurot belongs to the transcribers' project, so in Birnbaum's the marker
    pair is all that remains -- and an undecided empty scope prints as its own brackets or
    rule, offering the reader a choice between nothing and nothing.

    Only pairs in the same parent are considered, and only when what lies between them
    holds no words and no elements of its own. A scope spanning a division boundary is
    left alone: nothing here can see what it governs.
    """
    for parent in list(root.iter()):
        children = list(parent)
        opens = {child.get(XML_ID): index
                 for index, child in enumerate(children)
                 if child.tag == J_CONDITIONAL and child.get(XML_ID)}
        for index, child in enumerate(children):
            if child.tag != J_END_CONDITIONAL:
                continue
            start = opens.get((child.get("target") or "")[1:])
            if start is None or start > index:
                continue
            between = children[start + 1:index]
            if any(piece.tag not in CONDITIONAL_CONTROL_TAGS for piece in between):
                continue
            if any((piece.tail or "").strip() for piece in [children[start], *between]):
                continue
            parent.remove(children[start])
            parent.remove(child)


def close_up_whitespace(root) -> None:
    """Collapse the space a resolved conditional leaves behind.

    A scope removed from the middle of a phrase takes its words but not the space on
    either side of it, so what was on either side ends up two spaces apart -- visible in
    Birkat ha-Tzaddikim, Velirushalayim and Shema Koleinu, wherever an insert is not said
    today.

    Inside a paragraph or a line and nowhere else: there the whitespace is content, and
    everywhere else it is the indentation of the file. The newlines the importer sets after
    punctuation are left alone, being how a long verse is kept readable in the source and a
    single space to the typesetter either way.
    """
    for holder in list(root.iter(TEI_P, TEI_L)):
        for element in [holder, *holder.iter()]:
            for attribute in ("text", "tail"):
                value = getattr(element, attribute)
                if not value:
                    continue
                closed = re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", value))
                if closed != value:
                    setattr(element, attribute, closed)


def merge_credits(root, linear_data) -> None:
    """Put the gathered credits into the compiled document's own title statement.

    The root document's credits are already there; the ones gathered from everything it
    transcluded are appended, in the order they were met, without repeating any.
    """
    title_stmt = root.find(f".//{{{TEI_NS}}}titleStmt")
    if title_stmt is None:
        return
    gather_credits(root, linear_data)

    def identity(role: str, reference: str, name_text: str) -> tuple[str, str]:
        # A contributor is known by their URN. One without a URN is known only by name, or
        # every unnamed contributor of a role would be taken for the first.
        return role, reference or f"name:{name_text}"

    present = {
        identity(r.get("key") or "", n.get("ref") or "", "".join(n.itertext()).strip())
        for stmt in title_stmt.findall(f"{{{TEI_NS}}}respStmt")
        for r in [stmt.find(f"{{{TEI_NS}}}resp")] for n in [stmt.find(f"{{{TEI_NS}}}name")]
        if r is not None and n is not None
    }
    for role, reference, name_text, resp_text in linear_data.credits:
        key = identity(role, reference, name_text)
        if key in present:
            continue
        present.add(key)
        stmt = etree.SubElement(title_stmt, f"{{{TEI_NS}}}respStmt")
        resp = etree.SubElement(stmt, f"{{{TEI_NS}}}resp")
        resp.set("key", role)
        resp.text = resp_text
        name = etree.SubElement(stmt, f"{{{TEI_NS}}}name")
        if reference:
            name.set("ref", reference)
        name.text = name_text


def main(argv: list[str] | None = None):  # pragma: no cover
    parser = argparse.ArgumentParser(description="Compile a TEI file with external references to a single file.")
    parser.add_argument("--project", "-p", type=str,
                        help="The project name. Defaults to the settings file's book.project.")
    parser.add_argument("--file_name", "-f", type=str,
                        help="The file name (relative to the project). Defaults to the settings file's book.file_name.")
    parser.add_argument("--output_file", "-o", type=str, help="The output XML file.")
    parser.add_argument("--settings", "-s", type=Path, help="YAML file with compiler settings. See README.md for more details.")
    parser.add_argument(
        "--project-directory",
        type=Path,
        default=PROJECT_DIRECTORY,
        help="Base directory containing project subdirectories (default: <repo>/opensiddur-projects/project).",
    )
    parser.add_argument(
        "--destination",
        choices=("print", "electronic"),
        default="print",
        help="What the compiled file is for. 'electronic' leaves the settings a reader supplies "
             "undecided, for an electronic book to resolve on the reader's device.",
    )
    args = parser.parse_args(argv)

    from opensiddur.exporter.settings import load_default_settings, load_settings, read_settings

    project_directory = args.project_directory.resolve()
    if args.project is None or args.file_name is None:
        book = (
            read_settings(args.settings, project_directory=project_directory, resolve_fonts=False).book
            if args.settings else None
        )
        if book is None:
            parser.error("--project and --file_name are required unless the settings file names a book")
        args.project = args.project or book.project
        args.file_name = args.file_name or book.file_name
    reset_linear_data()
    linear_data = get_linear_data()
    linear_data.defer_reader_settings = args.destination == "electronic"

    if args.settings:
        linear_data = load_settings(
            args.settings,
            linear_data=linear_data,
            project_directory=project_directory,
        )
        if not linear_data.project_priority:
            # README: with no transclusion priority, the project of the file compiled is used.
            linear_data.project_priority = [args.project]
    else:
        linear_data = load_default_settings(
            args.project,
            args.file_name,
            linear_data=linear_data,
            project_directory=project_directory,
        )

    from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
    compiler = ExternalCompilerProcessor(args.project, args.file_name, linear_data=linear_data)
    compiled = compiler.process()
    if not compiled:
        raise ValueError(f"{args.project}/{args.file_name} compiled to nothing")
    result = compiled[0]
    drop_empty_scopes(result)
    close_up_whitespace(result)
    join_split_paragraphs(result)
    merge_credits(result, linear_data)
    if linear_data.defer_reader_settings:
        result.set(f"{{{PROCESSING_NAMESPACE}}}destination", "electronic")
    for problem in check_pairing(result):
        logger.warning("conditional markers do not pair: %s", problem)
    etree.ElementTree(result).write(
        args.output_file if args.output_file else sys.stdout.buffer,
        pretty_print=True,
        encoding='utf-8')


if __name__ == "__main__":  # pragma: no cover
    main()