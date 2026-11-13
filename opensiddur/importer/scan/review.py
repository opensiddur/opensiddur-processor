"""Hash-bound records for independent image readings and explicit adjudication."""
import hashlib
import re
import unicodedata
from dataclasses import asdict

from .compare import compare


def reading_hash(text):
    """Whitespace and combining order do not change a word or logical pointing."""
    normalized = ' '.join(unicodedata.normalize('NFKD', text).split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def review_is_current(entry, text):
    """An affirmative flag alone cannot certify a changed or unresolved reading."""
    return bool(entry.get('complete') and entry.get('primary_model')
                and entry.get('independent_model')
                and entry['primary_model'] != entry['independent_model']
                and entry.get('primary_sha256') and entry.get('independent_sha256')
                and entry.get('evidence') and not entry.get('unresolved')
                and not entry.get('pending_ambiguities')
                and entry.get('final_sha256') == reading_hash(text))


def adjudicate_fragments(fragments, report):
    """Apply reviewed differences by token position, preserving scan boundaries.

    Replacing a word globally would corrupt its other occurrences: two identical
    words can have different punctuation, or only one may be an OCR error.
    Cross-fragment edits require manual placement rather than moving a page break.
    """
    if reading_hash(' '.join(fragments)) != report['primary_sha256']:
        raise ValueError('Stale primary reading')
    result = [unicodedata.normalize('NFKD', text) for text in fragments]
    positions = [(index, match.start(), match.end()) for index, text in enumerate(result)
                 for match in re.finditer(r'[^\s־]+', text)]
    edits = {}
    occupied = set()
    for difference in report['differences']:
        decision = report.get('decisions', {}).get(difference['key'], {})
        if decision.get('accepted') not in ('primary', 'independent') or not decision.get('evidence'):
            raise ValueError('Unresolved difference: '+difference['key'])
        if decision['accepted'] == 'primary':
            continue
        count = len(re.findall(r'[^\s־]+', difference['ours']))
        if not count:
            raise ValueError('Insertion needs explicit placement')
        start = difference['at']
        covered = set(range(start, start+count))
        if covered & occupied or start < 0 or start+count > len(positions):
            raise ValueError('Overlapping or invalid adjudication')
        occupied.update(covered)
        first, last = positions[start], positions[start+count-1]
        if first[0] != last[0]:
            raise ValueError('Adjudication crosses scan fragments; place manually')
        edits.setdefault(first[0], []).append((first[1], last[2], difference['theirs']))
    for index, changes in edits.items():
        for lo, hi, text in sorted(changes, reverse=True):
            result[index] = result[index][:lo]+text+result[index][hi:]
    return [' '.join(text.split()) for text in result]


def review(primary, independent, *, primary_model, independent_model, evidence, settlement=None):
    """A review is complete only for these exact readings and all disputed text.

    Settlement is an image adjudication containing both hashes and ``decisions``
    keyed by compare.Difference.key, each with ``accepted`` and ``evidence``.
    This function reports differences; it never chooses which reading is correct.
    """
    if not primary_model or not independent_model or primary_model == independent_model:
        raise ValueError('Record two distinct reader models')
    if not evidence:
        raise ValueError('A review must identify its scan evidence')
    result = {'primary_sha256': reading_hash(primary),
              'independent_sha256': reading_hash(independent),
              'primary_model': primary_model, 'independent_model': independent_model,
              'evidence': evidence}
    differences = compare(primary, independent).differences
    # Physical line wrap and Unicode combining order are not textual disputes.
    if result['primary_sha256'] == result['independent_sha256']:
        differences = []
    decisions = {}
    if settlement is not None:
        for name in ('primary_sha256', 'independent_sha256'):
            if settlement.get(name) != result[name]:
                raise ValueError('Stale adjudication: ' + name)
        decisions = settlement.get('decisions', {})
        unknown = set(decisions) - {d.key for d in differences}
        if unknown:
            raise ValueError('Adjudication names absent differences: ' + repr(unknown))
    unresolved = []
    for difference in differences:
        decision = decisions.get(difference.key, {})
        if decision.get('accepted') not in ('primary', 'independent') or not decision.get('evidence'):
            unresolved.append(difference.key)
    result.update(differences=[asdict(d) | {'key': d.key} for d in differences],
                  decisions=decisions, unresolved=unresolved, complete=not unresolved)
    return result
