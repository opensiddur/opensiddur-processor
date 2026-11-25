"""Inline compiler processor for processing text content between start and end markers."""

from typing import Optional
from lxml.etree import ElementBase

from opensiddur.exporter.compiler import (
    CompilerProcessor,
    _ProcessingCommand,
    _ProcessingContext,
    _AnnotationCommand,
)
from opensiddur.exporter.conditional_settings import CONDITIONAL_CONTROL_TAGS
from opensiddur.exporter.constants import (
    JLPTEI_NAMESPACE,
    PROCESSING_NAMESPACE,
    TEI_NS,
    is_element_node,
)
from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.linear import LinearData
from opensiddur.exporter.refdb import ReferenceDatabase
from lxml import etree


TEI_CHOICE = f"{{{TEI_NS}}}choice"
J_READ = f"{{{JLPTEI_NAMESPACE}}}read"
J_OPTION = f"{{{JLPTEI_NAMESPACE}}}option"


#: Elements that end a line or a block. Inline text has no lines or blocks, so words on either
#: side of one need a space between them if the source puts none; inline markup (a highlighted
#: letter, a divine name) joins exactly, since it can fall inside a word.
_LINE_OR_BLOCK_TAGS = frozenset(f"{{{TEI_NS}}}{name}" for name in (
    "lb", "pb", "cb", "l", "lg", "p", "ab", "head", "item", "list", "div"))


def _join(text: str, addition: str, boundary: bool) -> str:
    """``text`` + ``addition``, with a space between them across a line or block boundary."""
    if (boundary and text and addition
            and not text[-1].isspace() and not addition[0].isspace()):
        return text + " " + addition
    return text + addition


def _unread_choices(element: ElementBase, keep: tuple = (), options=None) -> set[ElementBase]:
    """The children of a tei:choice that inline text leaves out.

    Inline text has room for one reading of a word. A ketiv and a qere are two readings of one
    word, and the qere (j:read) is what is read; set side by side they would double the word.
    If wording settings leave several j:options possible, the first remaining option
    stands in, as it does where sub-verse boundaries are measured.
    """
    if element.tag != TEI_CHOICE:
        return set()
    if options is None:
        options = [child for child in element if child.tag == J_OPTION]
    readings = [child for child in element if child.tag == J_READ] or options[:1]
    if not readings:
        return set()
    # A reading that holds where the range starts or ends is read regardless: skipping it
    # would skip the start or the end itself.
    holds = {child for child in element
             if any(kept is not None and (kept is child or child in kept.iterancestors())
                    for kept in keep)}
    return {child for child in element
            if is_element_node(child) and child not in readings and child not in holds}


class InlineCompilerProcessor(CompilerProcessor):
    def __init__(
        self,
        project: str,
        file_name: str,
        from_start: str,
        to_end: str,
        include_tail_after_end: bool = False,
        linear_data: Optional[LinearData] = None,
        reference_database: Optional[ReferenceDatabase] = None):
        """ Process the given file/project.
        Only start from the given start and end, inclusive.
        Start and end must be in the same file
        """
        super().__init__(project, file_name, linear_data=linear_data, reference_database=reference_database)
        self.from_start = from_start
        self.to_end = to_end
        self.include_tail_after_end = include_tail_after_end
        self.start_element, self.end_element = self._get_start_and_end_elements_from_ranges(from_start, to_end)

    def _update_processing_context_before(self, element: ElementBase) -> _ProcessingContext:
        """
        Update the processing context for the given element, before the element has been processed.
        """
        context = self.linear_data.processing_context[-1]

        # always reset the include_tail_after_end flag
        context['include_tail_after_end'] = False

        context['element_path'] = element.getroottree().getpath(element)
        # Possible contexts:
        #    after end? SKIP
        #    before start?
        #       check if this element is start? if yes, set before_start to False and return COPY_TEXT_AND_RECURSE
        #       else RECURSE
        #    between start and end? COPY_TEXT_AND_RECURSE

        if context['after_end']:
            context['command'] = _ProcessingCommand.SKIP
            return context

        corresp = element.attrib.get("corresp", "")
        xml_id = element.attrib.get("{http://www.w3.org/XML/1998/namespace}id", "")

        # is start
        if corresp or xml_id:
            if element is self.start_element:
                context['before_start'] = False
                context['command'] = _ProcessingCommand.COPY_TEXT_AND_RECURSE
                self._open_scopes_at_start()
                return context

        # is after start?
        if context['before_start']:
            context['command'] = _ProcessingCommand.RECURSE
            return context

        # must be after start and before end
        context['command'] = _ProcessingCommand.COPY_TEXT_AND_RECURSE
        return context

    def _update_processing_context_after(self, element: ElementBase) -> _ProcessingContext:
        """
        Update the processing context for the given element, after the element has been processed.
        """
        context = self.linear_data.processing_context[-1]
        context['element_path'] = None
        context["include_tail_after_end"] = False
        if not context['before_start'] and not context['after_end']:
            # between start and end - check if this is the end element
            if element is self.end_element:
                context['after_end'] = True
                context["include_tail_after_end"] = self.include_tail_after_end
                # The scopes the range ends inside close where it ends, innermost first.
                self._closers_due = [
                    self._closer_for(xml_id) for xml_id in reversed(self._scopes_open_in_range)]
                self._scopes_open_in_range = []
        elif context['after_end']:
            # force exclusion of tails after the end element
            context["command"] = _ProcessingCommand.SKIP

        return context

    def _process_element(self, element: ElementBase, root: Optional[ElementBase] = None) -> ElementBase:
        """Process the given element, putting the markers of the scopes still open around
        the range's start in front of the start's text."""
        result = self._process_element_contents(element, root)
        if self._markers_at_start and element is self.start_element:
            # This element was the range's start: the scopes still open around it open here,
            # in front of its text.
            markers = self._markers_at_start
            self._markers_at_start = []
            if result.tag != f"{{{PROCESSING_NAMESPACE}}}transcludeInline":
                wrapper = etree.Element(f"{{{PROCESSING_NAMESPACE}}}transcludeInline", nsmap=self.ns_map)
                wrapper.text = ""
                wrapper.append(result)
                result = wrapper
            markers[-1].tail = (markers[-1].tail or "") + (result.text or "")
            result.text = ""
            for marker in reversed(markers):
                result.insert(0, marker)
        return result

    def _process_element_contents(self, element: ElementBase, root: Optional[ElementBase] = None) -> ElementBase:
        """
        Process the given element and return the text content.
        """
        if not is_element_node(element):
            # A comment or processing instruction contributes no text. Return the empty wrapper
            # without touching the processing context; the caller carries the tail.
            empty = etree.Element(f"{{{PROCESSING_NAMESPACE}}}transcludeInline", nsmap=self.ns_map)
            empty.text = ""
            return empty

        context = self._update_processing_context_before(element)
        preserve_name = (element.tag == f"{{{JLPTEI_NAMESPACE}}}divineName"
                         and context["command"] == _ProcessingCommand.COPY_TEXT_AND_RECURSE)

        text_element = etree.Element(f"{{{PROCESSING_NAMESPACE}}}transcludeInline", nsmap=self.ns_map)
        text_element.text = ""

        if context["command"] == _ProcessingCommand.SKIP:
            return text_element

        if (
            self._should_skip_conditional_content()
            and element.tag not in CONDITIONAL_CONTROL_TAGS
        ):
            self._update_processing_context_after(element)
            return text_element

        if self._handle_settings_element(element):
            self._update_processing_context_after(element)
            return text_element

        handled, conditional_copy = self._handle_conditional_element(element)
        if handled:
            # Placed before the context update: a closer can be the range's end element
            # itself, and the update is what settles which scopes the end leaves open.
            placed = self._place_conditional_marker(
                element, conditional_copy, context['before_start'])
            self._update_processing_context_after(element)
            return placed[0] if placed else text_element

        # Before the range's start, a transclusion or annotation must not be resolved at
        # all: resolving it here would leak content that RECURSE is meant to suppress
        # entirely (see #53), and would raise on an unresolvable target that will never
        # actually appear in the output.
        if context["command"] != _ProcessingCommand.RECURSE:
            # Check if this element itself is a transclusion
            transcluded = self._transclude(element, type_override='inline')
            if transcluded is not None:
                # Don't process children of j:transclude elements - just return the p:transclude
                # The tail will be handled by the parent's processing
                self._update_processing_context_after(element)
                return transcluded

            annotations, annotation_command = self._annotate(element, root)
        else:
            annotations, annotation_command = [], _AnnotationCommand.NONE

        if annotation_command == _AnnotationCommand.REPLACE:
            # This is a case of an instructional notation that needs to replace the current element
            # and *not* be treated as inline text
            self._update_processing_context_after(element)
            return annotations[0]
        elif annotation_command == _AnnotationCommand.KEEP:
            # This is a case of an instructional notation that needs to be kept as is
            processor = ExternalCompilerProcessor(
                self.project,
                self.file_name,
                linear_data=self.linear_data,
                reference_database=self._refdb
            )
            processed = processor.process(element)
            if not processed:
                raise ValueError(f"The instruction at {element.getroottree().getpath(element)} "
                                 f"in {self.project}/{self.file_name} compiled to nothing")
            processed_element = processed[0]
            context_lang = self._get_in_scope_language(element)
            if (processor.root_language
                and processor.root_language != context_lang
                and not processed_element.get('{http://www.w3.org/XML/1998/namespace}lang')):
                processed_element.set('{http://www.w3.org/XML/1998/namespace}lang', processor.root_language)
            self._update_processing_context_after(element)
            return processed_element

        element_lang = element.get('{http://www.w3.org/XML/1998/namespace}lang')
        if element_lang:
            text_element.set('{http://www.w3.org/XML/1998/namespace}lang', element_lang)

        if context["command"] == _ProcessingCommand.COPY_TEXT_AND_RECURSE:
            if element.text:
                text_element.text += element.text

        # the command is some kind of recursion now, COPY_TEXT_AND_RECURSE or RECURSE
        context_lang = self._get_in_scope_language(element)
        previous_child = None
        children = list(self._reading_children(element))
        unread = _unread_choices(element, (self.start_element, self.end_element),
                                 [child for child in children if child.tag == J_OPTION])
        for child in children:
            if child in unread:
                continue
            processed = self._process_element(child, root)
            # Check if this child has a language different from the root
            child_lang = self._get_in_scope_language(child)
            if processed.tag == f"{{{PROCESSING_NAMESPACE}}}transcludeInline":
                # If language differs, keep as nested element
                if child_lang and child_lang != context_lang:
                    text_element.append(processed)
                    previous_child = processed
                else:
                    # Extract text from nested p:transcludeInline elements. It follows
                    # whatever is already here, so it goes on the last child's tail if any:
                    # appended to the text, it would jump ahead of an earlier marker.
                    boundary = child.tag in _LINE_OR_BLOCK_TAGS
                    if previous_child is not None:
                        previous_child.tail = _join(
                            previous_child.tail or "", processed.text or "", boundary)
                    else:
                        text_element.text = _join(text_element.text, processed.text or "",
                                                  boundary)
                    # Also extract any p:transclude children (nested transclusions)
                    for nested_child in processed:
                        text_element.append(nested_child)
                        previous_child = nested_child
            elif processed.tag == f"{{{PROCESSING_NAMESPACE}}}transclude":
                # p:transclude elements are kept as children (for inline transclusions)
                # Add the p:transclude element as a child
                text_element.append(processed)
                previous_child = processed
            else:
                # Other element types (shouldn't normally happen in InlineCompilerProcessor)
                text_element.append(processed)
                previous_child = processed
            if (
                context["command"] == _ProcessingCommand.COPY_TEXT_AND_RECURSE
                or context["include_tail_after_end"]):
                # A child skipped by a false conditional scope takes its tail with it: that
                # tail is conditional text. See _carry_dropped_tail.
                if child.tail and not self._should_skip_conditional_content():
                    boundary = child.tag in _LINE_OR_BLOCK_TAGS
                    if previous_child is not None:
                        previous_child.tail = _join(
                            self._prefix_before_tail(previous_child.tail, child), child.tail, boundary)
                    else:
                        text_element.text = _join(
                            self._prefix_before_tail(text_element.text, child), child.tail, boundary)
            if self._closers_due:
                # The range ended at this child: close the scopes it ends inside, after the
                # end and its tail.
                self._flush_closers_due(text_element)
                previous_child = text_element[-1]

        if annotation_command == _AnnotationCommand.INSERT:
            for annotation in reversed(annotations):
                self._insert_first_element(text_element, annotation)

        self._update_processing_context_after(element)
        if preserve_name:
            # Flatten source paragraphs, but keep the semantic name so later
            # rendering can distinguish it from ordinary Hebrew words.
            name = etree.Element(element.tag, attrib=dict(element.attrib), nsmap=self.ns_map)
            name.text = text_element.text
            name.extend(text_element)
            return name
        return text_element

    def process(self, root: Optional[ElementBase] = None) -> ElementBase:
        if root is None:
            root = self.root_tree
        self._gather_file_credits()

        self.root_language = self._get_in_scope_language(root)

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
            element = self._process_element(root, root)
            # Owed only when the range ended on the root itself, with no parent loop
            # to place them in.
            self._flush_closers_due(element)

        return element
