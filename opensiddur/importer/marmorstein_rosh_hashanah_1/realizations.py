"""Reviewed canonical realizations without replacing the literal image evidence."""
from copy import deepcopy
import json
import hashlib


PLAIN_FRAGMENT_KEYS = {'scan','printed_page','text','page_start','join_next'}
PLAIN_SEGMENT_KEYS = {'paragraph','fragments','corresp','source','source_reference',
                     'source_reference_corresp','chapter_corresp','reference_unit',
                     'end_reference','source_reference_end','source_reference_part'}


def join_source_fragments(fragments):
    text = ''
    previous = None
    for fragment in fragments:
        addition = fragment['text']
        if (text and addition and not text[-1].isspace() and not addition[0].isspace()
                and addition[0] not in ',.;:!?)]' and not text.endswith('־')
                and not (previous and previous.get('join_next'))):
            text += ' '
        text += addition
        previous = fragment
    return text


def source_text(segments):
    return join_source_fragments([f for segment in segments for f in segment['fragments']])


def segment_identity(segment):
    return (segment.get('corresp') or segment.get('source_reference_corresp')
            or segment.get('source_reference'))


def overlays(readings, stem, lang=None):
    return [item for item in readings.get('wording_variants', [])
            if item['host'] == stem and (lang is None or item['lang'] == lang)]


def selection(readings, stem):
    """Select the host's printed reading at the caller, never inside its ranges."""
    features = {}
    for item in overlays(readings, stem):
        if item.get('kind') == 'optional':
            continue
        for index, reading in enumerate(item['readings']):
            value = index == 0
            identity = reading['corresp']
            if identity in features and features[identity] != value:
                raise ValueError('Inconsistent host wording: '+identity)
            features[identity] = value
    return [{'type': 'opensiddur:variant', 'features': features}] if features else []


def validate_pure_parts(unit):
    """A parts library is not a service occurrence or a whole canonical work."""
    allowed = {'stem', 'urn', 'title', 'title_languages', 'languages',
               'canonical_parts', 'map_root', 'omit_publication_urn'}
    if set(unit) - allowed:
        raise ValueError('Pure canonical parts cannot inherit occurrence controls')
    if not unit['languages']:
        raise ValueError('Pure canonical parts require a language witness')
    for segments in unit['languages'].values():
        if not segments:
            raise ValueError('Pure canonical parts require identified words')
        for segment in segments:
            if (set(segment) - PLAIN_SEGMENT_KEYS or not segment_identity(segment)
                    or not segment.get('fragments')):
                raise ValueError('Pure canonical parts need plain identified segments')
            if any(set(fragment) - PLAIN_FRAGMENT_KEYS for fragment in segment['fragments']):
                raise ValueError('Pure canonical parts cannot carry source interpretations')


def overlay_fragment(unit, segment, item):
    fragments = segment['fragments']
    if len(fragments) == 1:
        if 'fragment' in item:
            raise ValueError('Single-fragment overlay cannot specify a fragment index')
        return 0, fragments[0]
    if (unit.get('canonical_home', {}).get('context') != 'literal'
            or type(item.get('fragment')) is not int
            or not 0 <= item['fragment'] < len(fragments)):
        raise ValueError('Multi-fragment overlay requires a literal-context home and explicit fragment index')
    return item['fragment'], fragments[item['fragment']]


def prepare_unit(unit, readings):
    """Overlay options on a copy; never edit the accepted source fragments."""
    if unit.get('canonical_parts'):
        validate_pure_parts(unit)
    result = deepcopy(unit)
    if unit.get('canonical_parts'):
        result['map_root'] = False
        result['omit_publication_urn'] = True
        for segments in result['languages'].values():
            for segment in segments:
                for fragment in segment['fragments']:
                    fragment['page_start'] = False
    for lang, segments in result['languages'].items():
        for item in overlays(readings, unit['stem'], lang):
            matching = [s for s in segments if segment_identity(s) == item['identity']]
            if len(matching) != 1:
                raise ValueError('Wording overlay needs one identified segment')
            fragment_index, fragment = overlay_fragment(unit, matching[0], item)
            if set(fragment)-PLAIN_FRAGMENT_KEYS-{'alternatives','optional_spans'}:
                raise ValueError('Wording overlay cannot overlap source interpretations')
            spans = [v for v in overlays(readings, unit['stem'], lang)
                     if v['identity'] == item['identity'] and v.get('fragment', 0) == fragment_index]
            if len(spans) != 1:
                raise ValueError('Use one nonoverlapping wording overlay per source segment')
            if item.get('kind') == 'optional':
                if item['printed'] != '('+item['text']+')' or fragment['text'].count(item['printed']) != 1:
                    raise ValueError('Optional wording must match one parenthesized source word')
                fragment.setdefault('optional_spans', []).append(deepcopy(item))
                continue
            if (not item['printed'] or fragment['text'].count(item['printed']) != 1
                    or len(item['readings']) < 2 or item['readings'][0]['text'] != item['printed']):
                raise ValueError('Wording overlay must preserve one exact printed reading first')
            if any(not v['text'] or not v['corresp'].startswith('urn:x-opensiddur:condition:')
                   for v in item['readings']):
                raise ValueError('Wording options need nonempty words and condition URNs')
            fragment.setdefault('alternatives', []).append(dict(
                printed=item['printed'], readings=deepcopy(item['readings'])))
        if target := unit.get('canonical_whole'):
            # A complete short formula can share one range while its literal
            # source inventory retains the verse/invocation boundary.
            first = segments[0]
            if (len({s.get('paragraph', 1) for s in segments}) != 1
                    or len({f['scan'] for s in segments for f in s['fragments']}) != 1
                    or any(set(s)-PLAIN_SEGMENT_KEYS for s in segments)
                    or any(set(f)-{'scan','printed_page','text','page_start','join_next'}
                           for s in segments for f in s['fragments'])):
                raise ValueError('Whole canonical occurrence requires one plain source paragraph')
            fragment = deepcopy(first['fragments'][0])
            fragment['text'] = source_text(segments)
            result['languages'][lang] = [dict(paragraph=first.get('paragraph', 1),
                                             canonical=target, fragments=[fragment])]
    result['source_printings'] = {lang: list(unit.get('additional_printings', {}).get(lang, [])) + [printing for item in overlays(readings, unit['stem'], lang)
                                        for printing in item.get('printings', [])]
                                  for lang in unit['languages']}
    return result


def _range_segments(readings, lang, target, target_end=None):
    matches = []
    for unit in readings['units']:
        if lang not in unit['languages']:
            continue
        if unit.get('reuse', {}).get(lang):
            continue
        segments = unit['languages'][lang]
        if unit.get('canonical_parts') and target_end and any(segment_identity(v) == target for v in segments):
            raise ValueError('Noncontiguous canonical parts cannot be a range')
        if target == unit.get('text_corresp', unit.get('canonical_home', {}).get('text_corresp')):
            if target_end:
                raise ValueError('A whole-text identity cannot take a second endpoint')
            matches.append((unit, segments))
            continue
        starts = [i for i, s in enumerate(segments) if segment_identity(s) == target]
        for start in starts:
            ends = [i for i, s in enumerate(segments)
                    if i >= start and segment_identity(s) == (target_end or target)]
            if len(ends) != 1:
                raise ValueError('Canonical range needs one ordered endpoint')
            matches.append((unit, segments[start:ends[0]+1]))
    if len(matches) != 1:
        raise ValueError('Canonical range needs one host: '+target)
    return matches[0]


def canonical_text(readings, lang, target, settings, target_end=None):
    host, segments = _range_segments(readings, lang, target, target_end)
    result = []
    for segment in segments:
        if set(segment)-PLAIN_SEGMENT_KEYS:
            raise ValueError('Canonical host must contain only plain reviewed words and identities')
        for fragment_index, fragment in enumerate(segment['fragments']):
            if set(fragment)-PLAIN_FRAGMENT_KEYS:
                raise ValueError('Canonical host fragment cannot carry unmodeled interpretations')
            if (fragment['scan'] != segments[0]['fragments'][0]['scan'] and fragment.get('page_start', True)
                    and host.get('canonical_home', {}).get('context') != 'literal'):
                raise ValueError('Canonical range crosses a printed source page')
            text = fragment['text']
            for item in overlays(readings, host['stem'], lang):
                if item['identity'] != segment_identity(segment):
                    continue
                selected_index, _ = overlay_fragment(host, segment, item)
                if selected_index != fragment_index:
                    continue
                if item.get('kind') == 'optional':
                    value = settings.get(item['condition'])
                    text = text.replace(item['printed'], item['text'] if value is True else '' if value is False else item['printed'], 1)
                    continue
                if any(v['corresp'] not in settings for v in item['readings']):
                    raise ValueError('Canonical occurrence must declare every wording option')
                chosen = [v for v in item['readings'] if settings.get(v['corresp']) is True]
                if len(chosen) != 1:
                    raise ValueError('Canonical occurrence must select exactly one known wording')
                if text.count(item['printed']) != 1:
                    raise ValueError('Canonical wording span is missing or ambiguous')
                text = text.replace(item['printed'], chosen[0]['text'], 1)
            result.append(dict(fragment, text=text))
    return join_source_fragments(result)


def validate_occurrences(readings):
    """Every transclusion must reproduce its own image reading, even in draft."""
    by_stem = {u['stem']: u for u in readings['units']}
    if len(by_stem) != len(readings['units']):
        raise ValueError('Duplicate unit stem')
    ids = [v['id'] for v in readings.get('wording_variants', [])]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate wording overlay id')
    for item in readings.get('wording_variants', []):
        if item['host'] not in by_stem or item['lang'] not in by_stem[item['host']]['languages']:
            raise ValueError('Wording overlay has no source host/language')
    for unit in readings['units']:
        if unit.get('canonical_parts'):
            validate_pure_parts(unit)
        if any(fs['type'] != 'opensiddur:variant' for fs in unit.get('wording_selection', [])):
            raise ValueError('Wording selection may use only opensiddur:variant')
        if unit.get('text_corresp') or unit.get('canonical_home', {}).get('text_corresp'):
            if any(segment_identity(s) and not segment_identity(s).startswith('urn:x-opensiddur:text:bible:')
                   for ss in unit['languages'].values() for s in ss):
                raise ValueError('Whole formula identity cannot contain nested prayer-part milestones')
        effective, _ = prepare_documents(unit, readings)
        settings = {key: value for fs in effective.get('wording_selection', [])
                    if fs['type'] == 'opensiddur:variant' for key, value in fs['features'].items()}
        used_features = set()
        for lang, segments in effective['languages'].items():
            for segment in segments:
                if not segment.get('canonical'):
                    continue
                host, source_segments = _range_segments(readings, lang, segment['canonical'], segment.get('canonical_end'))
                source_ids = {segment_identity(s) for s in source_segments}
                for item in overlays(readings, host['stem'], lang):
                    if item['identity'] in source_ids:
                        used_features.update([item['condition']] if item.get('kind') == 'optional' else
                                             [reading['corresp'] for reading in item['readings']])
        if set(settings)-used_features or any(not isinstance(v, bool) for v in settings.values()):
            raise ValueError('Wording selection contains unused or nonboolean features')
        for lang, segments in effective['languages'].items():
            for segment in segments:
                target = segment.get('canonical')
                if not target:
                    continue
                fragments = segment['fragments']
                if (len(fragments) != 1 or any(segment.get(k) for k in
                        ('corresp','source_reference','source','repeat','transclude','conditions'))
                        or set(fragments[0]) - PLAIN_FRAGMENT_KEYS):
                    raise ValueError('Canonical occurrence must be one plain source fragment')
                actual = canonical_text(readings, lang, target, settings, segment.get('canonical_end'))
                if ' '.join(actual.split()) != ' '.join(fragments[0]['text'].split()):
                    raise ValueError('Canonical occurrence differs from its image reading: '+unit['stem']+'/'+lang)


    for unit in readings['units']:
        if not unit.get('canonical_parts'):
            continue
        for lang, segments in unit['languages'].items():
            for segment in segments:
                identity = segment_identity(segment)
                attestations = [s for occurrence in readings['units']
                                if occurrence is not unit
                                for s in occurrence['languages'].get(lang, [])
                                if s.get('canonical') == identity and not s.get('canonical_end')]
                for fragment in segment['fragments']:
                    if not any(all(fragment.get(k) == witness.get(k)
                                   for k in ('text', 'scan', 'printed_page'))
                               for attestation in attestations for witness in attestation['fragments']):
                        raise ValueError('Pure canonical part lacks a literal attestation: ' + identity)
    pure_roots = {u['urn'] for u in readings['units'] if u.get('canonical_parts')}
    pure_ids = {segment_identity(s) for u in readings['units'] if u.get('canonical_parts')
                for ss in u['languages'].values() for s in ss}
    def target_bounds(raw, endpoint=None):
        from opensiddur.exporter.urn import split_range
        target = raw.partition('@')[0]
        parsed = split_range(target)
        return (parsed[0], parsed[1]) if parsed else (target, endpoint.partition('@')[0] if endpoint else None)
    def check_target(raw, endpoint=None, literal=False):
        first, last = target_bounds(raw, endpoint)
        if first in pure_roots or last in pure_roots:
            raise ValueError('Pure canonical parts have no whole-library target')
        if last and (first in pure_ids or last in pure_ids):
            raise ValueError('Noncontiguous canonical parts cannot be a range')
        if literal and first in pure_ids:
            raise ValueError('Printed pure-part occurrences require attested canonical pointers')
    for unit in readings['units']:
        for target in unit.get('reuse', {}).values():
            check_target(target, literal=True)
        for segments in unit['languages'].values():
            for segment in segments:
                for key in ('repeat', 'transclude'):
                    if segment.get(key):
                        check_target(segment[key], literal=True)
                cue = segment.get('repeat_cue', {})
                for key in ('target', 'corresp'):
                    if cue.get(key):
                        check_target(cue[key], literal=True)
    def check_order(order):
        for occurrence in order:
            if occurrence.get('unit') in by_stem and by_stem[occurrence['unit']].get('canonical_parts'):
                raise ValueError('Pure canonical parts cannot be a service occurrence')
            if reference := occurrence.get('reference'):
                # A single part is a supported canonical recitation reference;
                # it is backed by the library's checked literal attestation.
                check_target(reference['target'], reference.get('targetEnd'))
            check_order(occurrence.get('order', []))
    for key in ('source_order', 'expanded_order'):
        check_order(readings.get(key, []))


def review_payloads(readings, corrections=None):
    """Bind every output-affecting unit field, separately from literal reading review."""
    from .canonical_corrections import bind_corrections, corrected_text
    bindings = bind_corrections(readings, corrections or [])
    for unit in readings['units']:
        if not (overlays(readings, unit['stem']) or unit.get('wording_selection')
                or unit.get('review_encoding') or unit.get('canonical_parts') or unit.get('canonical_whole') or unit.get('text_corresp') or unit.get('canonical_home')
                or any(s.get('canonical') for ss in unit['languages'].values() for s in ss)):
            continue
        for lang, segments in unit['languages'].items():
            witness = deepcopy(unit)
            witness['languages'] = {lang: segments}
            witness['citations'] = {lang: unit.get('citations', {}).get(lang, [])}
            witness['instructions'] = [i for i in unit.get('instructions', [])
                                       if lang in i.get('witnesses', [lang])]
            effective, _ = prepare_documents(unit, readings)
            settings = {key: value for fs in effective.get('wording_selection', [])
                        if fs['type'] == 'opensiddur:variant' for key, value in fs['features'].items()}
            fidelity = []
            for segment in effective['languages'][lang]:
                if not segment.get('canonical'):
                    continue
                target, endpoint = segment['canonical'], segment.get('canonical_end')
                actual = canonical_text(readings, lang, target, settings, endpoint)
                literal = source_text([segment])
                owner, selected = _range_segments(readings, lang, target, endpoint)
                selected_ids = {segment_identity(v) for v in selected}
                range_corrections = [b for b in bindings if b['host'] == owner['stem']
                                     and b['language'] == lang and b['item']['identity'] in selected_ids]
                corrected = corrected_text(actual, range_corrections)
                normal = lambda text: ' '.join(text.split())
                fidelity.append(dict(target=target, target_end=endpoint, settings=settings,
                                     corrections=[b['item'] for b in range_corrections],
                                     corrected_sha256=hashlib.sha256(normal(corrected).encode()).hexdigest(),
                                     resolved_sha256=hashlib.sha256(normal(actual).encode()).hexdigest(),
                                     literal_sha256=hashlib.sha256(normal(literal).encode()).hexdigest()))
            relevant_corrections = [b['item'] for b in bindings if b['language'] == lang
                                    and (b['host'] == unit['stem'] or any(stem == unit['stem'] for stem, _ in b['attesters']))]
            from . import PROJECTS
            own_file = PROJECTS[lang] + '/' + unit['stem'] + '.xml'
            relevant_corrections += [deepcopy(c) for c in corrections or []
                                     if c['file'] == own_file and c not in relevant_corrections]
            payload = dict(unit=witness, source_fidelity=fidelity, corrections=relevant_corrections, variants=overlays(readings, unit['stem']), expanded_order_sha256=hashlib.sha256(json.dumps(readings.get('expanded_order', []), ensure_ascii=False, sort_keys=True).encode()).hexdigest())
            for key in ('source_order','documentary_instructions','navigation'):
                payload[key+'_sha256'] = hashlib.sha256(json.dumps(readings.get(key, {}), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            scans = sorted({f['scan'] for s in segments for f in s['fragments']} | {p['scan'] for v in overlays(readings, unit['stem'], lang) for p in v.get('printings', [])} | {p['scan'] for p in unit.get('additional_printings', {}).get(lang, [])})
            yield 'realization/'+unit['stem']+'/'+lang, json.dumps(payload, ensure_ascii=False, sort_keys=True), scans


def prepare_documents(unit, readings):
    """Keep contextual spines separate from the literal canonical home."""
    home_config = unit.get('canonical_home')
    if not home_config:
        return prepare_unit(unit, readings), None
    if any(unit.get(k) for k in ('conditions','marked','instructions','head','opening_page',
                                   'publication_context','reuse','text_corresp','canonical_whole','poetry','citations','wording_selection')):
        raise ValueError('Canonical home cannot inherit occurrence controls')
    for segments in unit['languages'].values():
        for segment in segments:
            if set(segment)-PLAIN_SEGMENT_KEYS or any(set(f)-PLAIN_FRAGMENT_KEYS for f in segment['fragments']):
                raise ValueError('Canonical home cannot inherit contextual interpretations')
    prepared = prepare_unit(unit, readings)
    home = {key: deepcopy(prepared[key]) for key in ('stem','languages','source_printings','source_notes') if key in prepared}
    allowed = {'file','urn','title','map_root','omit_publication_urn','text_corresp','join_source_fragments',
               'context', 'context_urn'}
    if set(home_config)-allowed:
        raise ValueError('Canonical home configuration contains occurrence controls')
    if home_config.get('context', 'canonical') not in ('canonical', 'literal'):
        raise ValueError('Unknown canonical home context mode')
    if home_config.get('context') == 'literal' and not all(
            any(right['scan'] != left['scan'] and right.get('page_start', True)
                for segment in segments for left, right in zip(segment['fragments'], segment['fragments'][1:]))
            for segments in unit['languages'].values()):
        raise ValueError('Literal home context requires a source page break inside a segment in each language')
    context_urn = home_config.get('context_urn', unit['urn'])
    if ':siddur:' not in context_urn or context_urn == home_config['urn']:
        raise ValueError('Canonical home needs a distinct structural context URN')
    home.update({k: deepcopy(v) for k, v in home_config.items() if k not in ('context', 'context_urn')})
    home['title'] = deepcopy(home_config['title'])
    # Canonical text ranges do not carry an older context's page break.
    for segments in home['languages'].values():
        for segment in segments:
            for fragment in segment['fragments']:
                fragment['page_start'] = False
    context = deepcopy(unit)
    context.pop('additional_printings', None)
    context['map_root'] = False
    context['publication_context'] = context_urn
    if home_config.get('context') == 'literal':
        context['wording_selection'] = []
        for segments in context['languages'].values():
            for segment in segments:
                for key in ('corresp','reference_unit','source','source_reference',
                            'source_reference_corresp','chapter_corresp','end_reference',
                            'source_reference_end','source_reference_part'):
                    segment.pop(key, None)
        return context, home
    context['wording_selection'] = selection(readings, unit['stem'])
    if home_config.get('text_corresp'):
        context['canonical_whole'] = home_config['text_corresp']
        context = prepare_unit(context, dict(readings, wording_variants=[]))
    else:
        for segments in context['languages'].values():
            for segment in segments:
                identity = segment_identity(segment)
                if not identity:
                    raise ValueError('Canonical home context requires identified source parts')
                for key in ('corresp','reference_unit','source','source_reference',
                            'source_reference_corresp','chapter_corresp','end_reference'):
                    segment.pop(key, None)
                segment['canonical'] = identity
    return context, home


def validate_generated(documents, readings):
    """Check actual range uniqueness and give every direct caller local defaults."""
    from lxml import etree
    from . import EXPANDED
    T = '{http://www.tei-c.org/ns/1.0}'
    J = '{http://jewishliturgy.org/ns/jlptei/2}'
    X = '{http://www.w3.org/XML/1998/namespace}'
    by_project = {}
    for path, root in documents:
        by_project.setdefault(path.parent.name, []).append(root)
    pure = {u['stem']: u for u in readings['units'] if u.get('canonical_parts')}
    for path, root in documents:
        if path.stem not in pure:
            continue
        if (root.xpath('.//tei:pb | .//tei:body//tei:note | .//tei:body//j:conditional | '
                       './/tei:body//j:declare | .//tei:body//j:transclude | .//tei:body//tei:head',
                       namespaces={'tei': T[1:-1], 'j': J[1:-1]})
                or any(node.get('corresp') for node in root.iter(T+'div'))
                or root.findall('.//'+T+'publicationStmt/'+T+'idno')):
            raise ValueError('Generated pure canonical parts must have no pages, roots or occurrence controls')
    identities = {s[k] for u in readings['units'] for ss in u['languages'].values()
                  for s in ss for k in ('canonical','canonical_end') if s.get(k)}
    identities.update(u['canonical_whole'] for u in readings['units'] if u.get('canonical_whole'))
    for unit in readings['units']:
        if unit.get('canonical_home'):
            context, home = prepare_documents(unit, readings)
            identities.update(segment_identity(v) for ss in home['languages'].values() for v in ss if segment_identity(v))
            if home.get('map_root', True):
                identities.add(home['urn'])
            if home.get('text_corresp'):
                identities.add(home['text_corresp'])
            identities.update(s['canonical'] for ss in context['languages'].values() for s in ss if s.get('canonical'))
    for unit in readings['units']:
        if not unit.get('canonical_home'):
            continue
        context, home = prepare_documents(unit, readings)
        config = unit['canonical_home']
        for path, root in documents:
            if path.stem == config['file']:
                if list(root.iter(T+'pb')):
                    raise ValueError('Generated canonical home must contain no source page breaks')
            if path.stem == unit['stem']:
                canonical_root = config['urn']
                if any(e.get('corresp') == canonical_root for e in root.iter(T+'div')):
                    raise ValueError('Canonical context duplicates the home identity')
                if config.get('context') == 'literal':
                    from opensiddur.importer.util.internet_archive import page_image_url
                    from . import IDENTIFIER
                    lang = root.get(X+'lang')
                    fragments, expected_pbs, previous_scan = [], [], None
                    for segment in unit['languages'][lang]:
                        for fragment in segment['fragments']:
                            if fragment['scan'] != previous_scan and fragment.get('page_start', True):
                                expected_pbs.append((fragment.get('printed_page'),
                                    page_image_url(IDENTIFIER, int(fragment['scan'][1:])-1, size=''),
                                    ' '.join(join_source_fragments(fragments).split())))
                            fragments.append(fragment)
                            previous_scan = fragment['scan']
                    actual_pbs, prefix = [], []
                    def walk(node):
                        if node.tag == T+'pb':
                            actual_pbs.append((node.get('n'), node.get('facs'), ' '.join(''.join(prefix).split())))
                        prefix.append(node.text or '')
                        for child in node:
                            walk(child)
                            prefix.append(child.tail or '')
                    body = root.find(T+'text/'+T+'body')
                    walk(body)
                    if actual_pbs != expected_pbs:
                        raise ValueError('Literal context must retain its raw source page breaks and positions')
        for lang in unit['languages']:
            from . import PROJECTS
            roots = by_project.get(PROJECTS[lang], [])
            if not roots:
                continue
            expected = 0 if config.get('omit_publication_urn') else 1
            count = sum(1 for root in roots for e in root.iter(T+'idno')
                        if (e.text or '').partition('@')[0] == config['urn'])
            if count != expected:
                raise ValueError('Canonical home needs exactly its declared publication identity')
    canonical = set(identities)
    canonical.update(u['canonical_home']['urn'] for u in readings['units'] if u.get('canonical_home'))
    context_stems = {u['stem'] for u in readings['units'] if u.get('canonical_home')}
    for path, root in documents:
        if path.stem in context_stems and any(e.get('corresp') in canonical for e in root.iter(T+'div')):
            raise ValueError('Canonical context duplicates a canonical identity')
    for project, roots in by_project.items():
        publication_ids = [e.text for root in roots for e in root.findall('.//'+T+'publicationStmt/'+T+'idno')
                           if e.get('type') == 'urn' and e.text]
        if len(publication_ids) != len(set(publication_ids)):
            raise ValueError('Duplicate generated publication URN in ' + project)
        if project.endswith('-he') or project.endswith('-en'):
            # The expanded spine intentionally contains no prayer-word home.
            if project == EXPANDED:
                continue
            language = project.rsplit('-', 1)[-1]
            present = {segment_identity(v) for u in readings['units']
                       for v in u['languages'].get(language, []) if segment_identity(v)}
            present.update(v[k] for u in readings['units'] for v in u['languages'].get(language, [])
                           for k in ('canonical', 'canonical_end') if v.get(k))
            present.update(u['canonical_whole'] for u in readings['units']
                           if language in u['languages'] and u.get('canonical_whole'))
            for u in readings['units']:
                if language in u['languages'] and u.get('canonical_home'):
                    _, home = prepare_documents(u, readings)
                    if home.get('map_root', True):
                        present.add(home['urn'])
                    if home.get('text_corresp'):
                        present.add(home['text_corresp'])
            for identity in identities & present:
                matches = [e for root in roots for e in root.iter() if e.get('corresp') == identity]
                if len(matches) != 1:
                    raise ValueError('Canonical target needs one generated home: '+project+' '+identity)
    by_stem = {u['stem']:u for u in readings['units']}
    groups = {}
    for item in readings.get('wording_variants', []):
        if item.get('kind') == 'optional':
            continue
        host = by_stem[item['host']]
        # Contextual files with a separate home declare their own selectors.
        targets = [item['identity']]
        if not host.get('canonical_home'):
            targets.append(host['urn'])
        if host.get('canonical_home') and host['canonical_home'].get('map_root', True):
            targets.append(host['canonical_home']['urn'])
        if host.get('canonical_home', {}).get('text_corresp'):
            targets.append(host['canonical_home']['text_corresp'])
        for target in targets:
            group = {r['corresp']:i == 0 for i,r in enumerate(item['readings'])}
            groups.setdefault(target, []).append(group)
    for _, root in documents:
        active = []
        counter = 0
        for node in list(root.iter()):
            if node.tag == J+'declare':
                features = {f.get('name'):f[0].get('value') == 'true'
                            for fs in node.iter(T+'fs') if fs.get('type') == 'opensiddur:variant'
                            for f in fs.findall(T+'f')}
                active.append((node.get(X+'id'),features))
            elif node.tag == J+'endDeclare':
                target = node.get('target','').lstrip('#')
                active = [(key,features) for key,features in active if key != target]
            elif node.tag == J+'transclude':
                from opensiddur.exporter.urn import split_range
                raw_target = node.get('target', '').partition('@')[0]
                parsed_range = split_range(raw_target)
                first = parsed_range[0] if parsed_range else raw_target
                if node.get('targetEnd') or (parsed_range and parsed_range[1]):
                    pure_ids = {segment_identity(s) for u in pure.values()
                                for ss in u['languages'].values() for s in ss}
                    if first in pure_ids:
                        raise ValueError('Noncontiguous canonical parts cannot be a transclusion range')
                target = node.get('target','').partition('@')[0]
                known = {key:value for _,features in active for key,value in features.items()}
                defaults = {}
                target_groups = list(groups.get(target, []))
                if node.get('targetEnd') and any(overlays(readings, u['stem']) and any(segment_identity(s) == target for s in u['languages'].get(root.get(X+'lang'), [])) for u in readings['units']):
                    end = node.get('targetEnd').partition('@')[0]
                    language = root.get(X+'lang')
                    host, segments = _range_segments(readings, language, target, end)
                    for segment in segments:
                        target_groups.extend(groups.get(segment_identity(segment), []))
                for group in target_groups:
                    present = set(group)&known.keys()
                    if present and present != set(group):
                        raise ValueError('Caller must decide every wording option: '+target)
                    if not present:
                        defaults.update(group)
                if defaults:
                    parent = node.getparent();index = parent.index(node)
                    identifier = 'canonical_caller_wording_'+str(counter);counter += 1
                    declare = etree.Element(J+'declare',attrib={X+'id':identifier})
                    fs = etree.SubElement(declare,T+'fs',type='opensiddur:variant')
                    for key,value in defaults.items():
                        etree.SubElement(etree.SubElement(fs,T+'f',name=key),T+'binary',value=str(value).lower())
                    parent.insert(index,declare)
                    end = etree.Element(J+'endDeclare',target='#'+identifier)
                    end.tail = node.tail;node.tail = None
                    parent.insert(index+2,end)
