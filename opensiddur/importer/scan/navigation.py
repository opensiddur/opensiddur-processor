"""Explicit, image-adjudicated navigation clauses shared by scan editions.

Callers supply passage identities and distinguish actions from navigation. Page
numbers are never guessed, nor are entire rubrics removed by a keyword search.
"""
from .authoring import XML, element, mixed_words


def append_instruction(parent, clauses, *, expanded=False):
    """Render action/text clauses and page-reference clauses in their source order.

    A navigation clause supplies ``before``, ``after``, ``target`` (edition-qualified
    URN), and ``expansion`` (canonical target/optional targetEnd dictionaries).
    Its optional ``replacement`` preserves an occasion or custom rubric in the
    expanded view. Each clause is removable independently of neighboring actions.
    """
    note = None
    def instruction():
        nonlocal note
        if note is None:
            note = element(parent, 'note', type='instruction')
            note.set(XML + 'lang', 'en')
        return note

    for clause in clauses:
        if 'text' in clause:
            mixed_words(instruction(), clause['text'])
            continue
        target = clause['target']
        if not target.startswith('urn:x-opensiddur:') or '@' not in target:
            raise ValueError('A documentary page reference needs an edition-qualified URN')
        if expanded:
            if not clause.get('expansion'):
                raise ValueError('A navigation clause must have an explicit expansion')
            if clause.get('replacement'):
                mixed_words(instruction(), clause['replacement'])
            note = None
            for reference in clause['expansion']:
                if '@' in reference['target']:
                    raise ValueError('Expanded targets must be edition-independent URNs')
                element(parent, 'j:transclude', type='external', **reference)
        else:
            segment = element(instruction(), 'seg', type='optional-page-reference')
            mixed_words(segment, clause['before'])
            ref = element(segment, 'ref', type='page', target=target)
            ref.tail = clause['after']
