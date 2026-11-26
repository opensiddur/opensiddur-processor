"""Content-bound corrections for shared words, with exact source attestations."""
from copy import deepcopy
from pathlib import Path

from . import PROJECTS
from .realizations import _range_segments, segment_identity, overlays
from opensiddur.importer.scan.authoring import apply_corrections


def _pattern(item):
    return item.get('follows', '') + item.get('before', '') + item['sic'] + item.get('after', '')


def _bind_printing_correction(readings, host, lang, item):
    """Bind a typo unique to one guarded, independently attested printing option."""
    from .canonical_printings import bindings as printing_bindings
    identity, wording = item.get('identity'), item['wording']
    if (not isinstance(wording, str) or not wording.startswith('urn:x-opensiddur:condition:')
            or any(c in wording for c in '\"\'')
            or item.get('xpath') != '//j:option[@corresp="'+wording+'"]'):
        raise ValueError('Printing correction requires its exact option locator')
    options = [(overlay, index, choice) for overlay in overlays(readings, host['stem'], lang)
               if overlay['identity'] == identity
               for index, choice in enumerate(overlay.get('readings', []))
               if choice.get('corresp') == wording]
    if len(options) != 1 or options[0][1] == 0 or not item.get('sic'):
        raise ValueError('Printing correction needs one non-default wording option')
    candidates = [overlay for overlay in overlays(readings, host['stem'], lang)
                  if overlay['identity'] == identity]
    parts = [part for part in host['languages'][lang] if segment_identity(part) == identity]
    if (len(candidates) != 1 or len(parts) != 1 or len(parts[0]['fragments']) != 1
            or candidates[0]['printed'] != parts[0]['fragments'][0]['text']):
        raise ValueError('Printing correction requires one whole-fragment wording overlay')
    pattern = _pattern(item)
    if options[0][2]['text'].count(pattern) != 1:
        raise ValueError('Printing correction context must occur once in its option')
    other_texts = [f['text'] for ss in host['languages'].values() for part in ss for f in part['fragments']]
    other_texts += [choice['text'] for overlay in overlays(readings, host['stem'], lang)
                   for choice in overlay.get('readings', []) if choice.get('corresp') != wording]
    if any(pattern in text for text in other_texts):
        raise ValueError('Printing correction must be unique to its non-default option')
    owners = {record['caller'] for record in printing_bindings(readings)
              if record['host'] == host['stem'] and record['lang'] == lang
              and record['identity'] == identity}
    expected = set()
    for unit in readings['units']:
        settings = {key:value for fs in unit.get('wording_selection', [])
                    if fs['type'] == 'opensiddur:variant' for key,value in fs['features'].items()}
        if settings.get(wording) is not True:
            continue
        if unit['stem'] not in owners or lang not in unit['languages']:
            raise ValueError('Printing correction wording selected outside its guarded caller')
        parts = unit['languages'][lang]
        if not any(part.get('canonical') == identity for part in parts):
            raise ValueError('Printing correction caller must target the exact corrected part')
        fragments = [f for part in parts for f in part['fragments']]
        matches = [f for f in fragments if f['text'].count(pattern) == 1]
        if len(matches) != 1 or sum(f['text'].count(pattern) for f in fragments) != 1:
            raise ValueError('Printing correction caller must attest the exact source context')
        expected.add((unit['stem'], matches[0]['scan']))
    actual = [(a['unit'], a['scan']) for a in item.get('attestations', [])]
    if not expected or len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('Printing correction attestations must cover its guarded callers exactly')
    return dict(item=deepcopy(item), host=host['stem'], language=lang,
                attesters=sorted(expected), unaffected_witnesses=[host['stem']])


def bind_corrections(readings, items):
    """Reject edits to contextual callers; bind home edits to all literal witnesses."""
    homes, guarded, contexts = {}, set(), {}
    for unit in readings['units']:
        realized = (overlays(readings, unit['stem']) or unit.get('wording_selection')
                    or unit.get('canonical_whole') or unit.get('text_corresp')
                    or unit.get('canonical_home') or unit.get('canonical_parts')
                    or any(s.get('canonical') for ss in unit['languages'].values() for s in ss))
        for lang in unit['languages']:
            path = PROJECTS[lang] + '/' + unit['stem'] + '.xml'
            contexts[path] = (unit, lang)
            if realized:
                guarded.add(path)
            if config := unit.get('canonical_home'):
                home_path = PROJECTS[lang] + '/' + config['file'] + '.xml'
                if home_path in homes:
                    raise ValueError('Duplicate canonical correction home file')
                homes[home_path] = (unit, lang)
                guarded.add(home_path)
    literal_paths = set()
    # Explicit part bindings preserve old corrections in mixed files without
    # exempting any newly shared literal text from attestation checks.
    for item in items or []:
        if 'literal_provider' not in item:
            continue
        path = item['file']
        if item['literal_provider'] is not True or path not in contexts or (path in homes and path not in literal_paths):
            raise ValueError('Literal provider correction requires one explicit source file')
        owner, language = contexts[path]
        parts = [part for part in owner['languages'][language]
                 if segment_identity(part) == item.get('identity')]
        if (not item.get('identity') or len(parts) != 1
                or owner.get('canonical_home') or owner.get('canonical_whole') or owner.get('reuse')
                or any(parts[0].get(key) for key in ('canonical','transclude','repeat'))):
            raise ValueError('Literal provider correction requires one identified literal part')
        homes[path] = (owner, language)
        literal_paths.add(path)
    bound = []
    for item in items or []:
        path = item['file']
        if path in literal_paths and item.get('literal_provider') is not True:
            raise ValueError('Literal provider correction requires one explicit source file')
        if path not in homes:
            if path in guarded or item.get('identity') or item.get('attestations') or item.get('wording'):
                raise ValueError('Canonical corrections must target an explicit shared home')
            continue
        host, lang = homes[path]
        if item.get('wording'):
            bound.append(_bind_printing_correction(readings, host, lang, item))
            continue
        identity = item.get('identity')
        segments = [s for s in host['languages'][lang] if segment_identity(s) == identity]
        if not identity or len(segments) != 1 or not item.get('sic'):
            raise ValueError('Canonical correction needs one identified source part')
        pattern = _pattern(item)
        found = [(index, fragment) for index, fragment in enumerate(segments[0]['fragments'])
                 if fragment['text'].count(pattern) == 1]
        whole = [f for s in host['languages'][lang] for f in s['fragments']]
        if len(found) != 1 or sum(f['text'].count(pattern) for f in whole) != 1:
            raise ValueError('Canonical correction context must match exactly once in its source part')
        index, fragment = found[0]
        start = fragment['text'].index(pattern)
        stop = start + len(pattern)
        for overlay in overlays(readings, host['stem'], lang):
            if overlay['identity'] != identity or overlay.get('fragment', 0) != index:
                continue
            printed = overlay['printed']
            if fragment['text'].count(printed) != 1:
                raise ValueError('Canonical correction cannot bind an ambiguous wording overlay')
            left = fragment['text'].index(printed)
            if max(start, left) < min(stop, left + len(printed)):
                raise ValueError('Canonical correction cannot overlap a wording option')
        attesters = [host]
        for caller in readings['units']:
            if caller is host or lang not in caller['languages']:
                continue
            targets = [(s['canonical'], s.get('canonical_end'))
                       for s in caller['languages'][lang] if s.get('canonical')]
            if caller.get('canonical_whole'):
                targets.append((caller['canonical_whole'], None))
            for target, endpoint in targets:
                owner, selected = _range_segments(readings, lang, target, endpoint)
                if owner is host and identity in {segment_identity(s) for s in selected}:
                    attesters.append(caller)
                    break
        expected = set()
        for attester in attesters:
            fragments = [f for s in attester['languages'][lang] for f in s['fragments']]
            matches = [f for f in fragments if f['text'].count(pattern) == 1]
            if len(matches) != 1 or sum(f['text'].count(pattern) for f in fragments) != 1:
                raise ValueError('Every canonical correction attester must print the exact source context')
            expected.add((attester['stem'], matches[0]['scan']))
        actual = [(a['unit'], a['scan']) for a in item.get('attestations', [])]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError('Canonical correction attestations must exactly cover host and callers')
        bound.append(dict(item=deepcopy(item), host=host['stem'], language=lang,
                          attesters=sorted(expected)))
    def touches(target, endpoint, binding):
        from opensiddur.exporter.urn import split_range
        target = target.partition('@')[0]
        endpoint = endpoint.partition('@')[0] if endpoint else None
        parsed = split_range(target)
        if parsed:
            if endpoint:
                raise ValueError('A corrected reference cannot combine range syntaxes')
            target, endpoint = parsed
        owner = next(u for u in readings['units'] if u['stem'] == binding['host'])
        if target in (owner.get('canonical_home', {}).get('urn', owner['urn']), owner['urn'],
                      owner.get('text_corresp'), owner.get('canonical_home', {}).get('text_corresp'),
                      binding['item']['identity']):
            return True
        identities = {segment_identity(s) for s in owner['languages'][binding['language']]}
        if target in identities:
            host, selected = _range_segments(readings, binding['language'], target, endpoint)
            return host is owner and binding['item']['identity'] in {segment_identity(s) for s in selected}
        return False
    for binding in bound:
        for unit in readings['units']:
            for target in unit.get('reuse', {}).values():
                if touches(target, None, binding):
                    raise ValueError('Corrected shared words require attested canonical pointers, not reuse')
            for segments in unit['languages'].values():
                for segment in segments:
                    for key in ('repeat', 'transclude'):
                        if segment.get(key) and touches(segment[key], None, binding):
                            raise ValueError('Corrected shared words require attested canonical pointers')
        def check_spine(order, binding=binding):
            for occurrence in order:
                reference = occurrence.get('reference')
                if reference and touches(reference['target'], reference.get('targetEnd'), binding):
                    attesters = {stem for stem, _ in binding['attesters']} | set(binding.get('unaffected_witnesses', []))
                    if occurrence.get('source_witness') not in attesters:
                        raise ValueError('A corrected spine reference must name its reviewed source witness')
                check_spine(occurrence.get('order', []))
        for key in ('expanded_order', 'source_order'):
            check_spine(readings.get(key, []))
    return bound


def corrected_text(text, bindings):
    for binding in bindings:
        item = binding['item']
        pattern = _pattern(item)
        if text.count(pattern) != 1:
            raise ValueError('Resolved correction context is missing or ambiguous')
        text = text.replace(pattern, item.get('follows', '') + item.get('before', '') + item['corr'] + item.get('after', ''), 1)
    return text


def _projection(node, corrected):
    if node.tag == '{http://www.tei-c.org/ns/1.0}choice':
        selected = node.find('{http://www.tei-c.org/ns/1.0}' + ('corr' if corrected else 'sic'))
        if selected is not None:
            return _projection(selected, corrected)
    return (node.text or '') + ''.join(_projection(child, corrected) + (child.tail or '') for child in node)


def apply_bound_corrections(documents, readings, items):
    bindings = bind_corrections(readings, items)
    by_path = {str(Path(path.parent.name)/path.name): root for path, root in documents}
    before = {}
    for binding in bindings:
        file = binding['item']['file']
        if file not in by_path:
            raise ValueError('Canonical correction home was not generated')
        before.setdefault(file, _projection(by_path[file], False))
    apply_corrections(by_path, items)
    for file, original in before.items():
        root = by_path[file]
        selected = [b for b in bindings if b['item']['file'] == file]
        if _projection(root, False) != original:
            raise ValueError('Canonical correction altered its source-printed projection')
        if _projection(root, True) != corrected_text(original, selected):
            raise ValueError('Canonical correction altered words outside its corrected projection')
