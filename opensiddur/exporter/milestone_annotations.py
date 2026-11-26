"""Place apparatus at the end of its milestone scope before parallel alignment."""

from opensiddur.exporter.constants import RUBRIC_NOTE_TYPES, TEI_NS
from opensiddur.exporter.refdb import milestone_terminates

MILESTONE = f"{{{TEI_NS}}}milestone"
NOTE = f"{{{TEI_NS}}}note"


def place_milestone_annotations(elements):
    """Move compiler-attached milestone notes after their last addressed text.

    The compiler temporarily carries these notes inside the milestone. Resolve
    their position while the whole source stream is available, before alignment
    splits it into rows. The final text slot can be inside a nested quotation or
    a later paragraph; paragraph boundaries do not terminate milestone scopes.
    Ignore note bodies themselves when finding the last words of a scope.
    """
    active = []
    placements = []

    def finish(item):
        milestone, notes, slot = item
        placements.append((slot or (milestone, 'tail'), notes))

    def text_slot(node, attr):
        if (getattr(node, attr) or '').strip():
            for item in active:
                item[2] = (node, attr)

    def walk(node):
        if node.tag == MILESTONE:
            for item in active[:]:
                if milestone_terminates(item[0], node):
                    active.remove(item)
                    finish(item)
            notes = [child for child in node if child.tag == NOTE and child.get("type") not in RUBRIC_NOTE_TYPES]
            if notes:
                active.append([node, notes, None])
        elif node.tag != NOTE and isinstance(node.tag, str):
            text_slot(node, 'text')
            for child in node:
                walk(child)
                text_slot(child, 'tail')

    for element in elements:
        walk(element)
        text_slot(element, 'tail')
    for item in active:
        finish(item)

    # Multiple overlapping scopes can end on the same words. Keep their notes
    # together and preserve their order without consuming one another's tails.
    grouped = {}
    for slot, notes in placements:
        grouped.setdefault(slot, []).extend(notes)
    for (node, attr), notes in grouped.items():
        value = getattr(node, attr) or ''
        stripped = value.rstrip()
        whitespace = value[len(stripped):]
        setattr(node, attr, stripped)
        for note in notes:
            note.getparent().remove(note)
        if attr == 'text':
            for index, note in enumerate(notes):
                node.insert(index, note)
        else:
            parent = node.getparent()
            if parent is None:
                # Range compilation can return the milestone itself as a root.
                index = elements.index(node) + 1
                elements[index:index] = notes
            else:
                index = parent.index(node) + 1
                for offset, note in enumerate(notes):
                    parent.insert(index + offset, note)
        notes[-1].tail = (notes[-1].tail or '') + whitespace
