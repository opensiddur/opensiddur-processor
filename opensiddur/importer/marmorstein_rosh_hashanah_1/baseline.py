"""A fixed acceptance gate for pre-existing literal witnesses and source fragments."""
from copy import deepcopy
import hashlib
import json

UNIT_MAPPING_FIELDS = {'canonical_home', 'page_context', 'wording_selection'}
SEGMENT_MAPPING_FIELDS = {'corresp', 'reference_unit', 'source', 'source_reference',
    'source_reference_corresp', 'chapter_corresp', 'end_reference', 'source_reference_end',
    'source_reference_part', 'canonical', 'canonical_end'}


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def snapshot(readings):
    from .build import unit_review_text
    result = {}
    for unit in readings['units']:
        protected = {k: deepcopy(v) for k, v in unit.items() if k not in UNIT_MAPPING_FIELDS}
        for segments in protected['languages'].values():
            for segment in segments:
                for key in SEGMENT_MAPPING_FIELDS:
                    segment.pop(key, None)
        result[unit['stem']] = dict(protected_sha256=_hash(protected),
            literal_sha256={lang: hashlib.sha256(unit_review_text(unit, lang).encode()).hexdigest()
                            for lang in unit['languages']})
    return result


def validate_baseline(readings, baseline):
    current = snapshot(readings)
    for stem, accepted in baseline.items():
        if current.get(stem) != accepted:
            raise ValueError('Accepted source witness or protected raw fragment changed: ' + stem)


def validate_redirection(readings, stem, identities):
    """Before redirecting accepted parts, reject controls that a new pointer would lose."""
    units = [u for u in readings['units'] if u['stem'] == stem]
    if len(units) != 1:
        raise ValueError('Redirection needs one existing source unit')
    for identity in identities:
        matches = [s for ss in units[0]['languages'].values() for s in ss if s.get('corresp') == identity]
        if len(matches) != 1:
            raise ValueError('Redirection needs one source segment per identity')
        segment = matches[0]
        if (len(segment['fragments']) != 1 or segment.get('conditions') or segment.get('source_reference_part')
                or any(key in segment['fragments'][0] for key in
                       ('alternatives','quotations','qere_ketiv','expansion','abbreviations',
                        'enlarged_letters','uncertain_characters'))):
            raise ValueError('Redirection cannot discard source controls or fragment interpretations')
    def targets(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('condition_end_corresp','repeat','target','targetEnd','corresp') and isinstance(child,str):
                    yield key, child
                yield from targets(child)
        elif isinstance(value, list):
            for child in value:
                yield from targets(child)
    def names_redirected(target):
        from opensiddur.exporter.urn import split_range
        if not target.startswith('urn:x-opensiddur:'):
            return False
        target = target.partition('@')[0]
        parsed = split_range(target)
        return any(v in identities for v in parsed) if parsed else target in identities
    for unit in readings['units']:
        # A segment's own corresp is its definition, not a reference into it.
        for ss in unit['languages'].values():
            for segment in ss:
                for key in ('condition_end_corresp','repeat','transclude'):
                    if segment.get(key) and names_redirected(segment[key]):
                        raise ValueError('Redirection is named by an occurrence control')
                if any(names_redirected(target) for _, target in targets(segment.get('repeat_cue', {}))):
                    raise ValueError('Redirection is named by a repeat cue')
        if any(names_redirected(target) for _,target in targets(unit.get('citations', {}))):
            raise ValueError('Redirection is named by a citation')

    for order_key in ('source_order', 'expanded_order'):
        if any(names_redirected(target) for _, target in targets(readings.get(order_key, []))):
            raise ValueError('Redirection is named by a service reference')
