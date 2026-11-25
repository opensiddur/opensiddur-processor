"""Apply reviewed source interpretations after ordinary TEI authoring.

Every directive is part of the unit's review payload. Approved source words
remain in the input fragments; punctuation, annotations and pagination are
interpreted only in the generated tree.
"""
from lxml import etree

T = 'http://www.tei-c.org/ns/1.0'
J = 'http://jewishliturgy.org/ns/jlptei/2'
XML = '{http://www.w3.org/XML/1998/namespace}'
NS = {'t': T, 'j': J}


def _keys(value, allowed, required=(), name='source interpretation'):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError('Unknown or missing '+name+' configuration')


def _one(elements, description):
    if len(elements) != 1:
        raise ValueError(description+' requires exactly one matching element')
    return elements[0]


def _notes(root, b):
    notes = root.find('{'+T+'}standOff[@type="notes"]')
    if notes is None:
        notes = b.element(root, 'standOff', type='notes')
        root.remove(notes)
        root.insert(list(root).index(root.find('{'+T+'}text')), notes)
    return notes


def _scope_end(condition):
    parent = condition.getparent()
    return _one([node for node in parent
                 if node.tag == '{'+J+'}endConditional'
                 and node.get('target') == '#'+condition.get(XML+'id')],
                'Optional source scope')


def _rule(rule, unit):
    common = {'stem', 'kind', 'xml_id', 'day', 'scan', 'physical_line',
              'canonical_part', 'text'}
    kinds = {'alternate': {'printed_annotation', 'choices', 'colon_after_choice'},
             'optional': {'condition', 'whole_line', 'missing_opener', 'inner_condition'}}
    kind = rule.get('kind') if isinstance(rule, dict) else None
    if kind not in kinds:
        raise ValueError('Unknown source interpretation kind')
    required = {'stem', 'kind', 'xml_id'} | (
        {'condition', 'missing_opener'} if kind == 'optional'
        else {'printed_annotation', 'choices', 'colon_after_choice'})
    _keys(rule, common | kinds[kind], required, 'source interpretation rule')
    if rule['stem'] != unit['stem']:
        raise ValueError('Source interpretation rule names a different unit')
    for key in ('missing_opener', 'whole_line', 'colon_after_choice'):
        if key in rule and type(rule[key]) is not bool:
            raise ValueError('Source interpretation flags must be booleans')
    if kind == 'alternate':
        if not isinstance(rule['choices'], list) or len(rule['choices']) < 2:
            raise ValueError('Source alternate requires at least two choices')
        for choice in rule['choices']:
            _keys(choice, {'text', 'corresp'}, {'text', 'corresp'}, 'source alternate')
    return kind


def _interpretations(root, unit, rules):
    from . import build as b
    if not isinstance(rules, list):
        raise ValueError('Source interpretations must be a list')
    for rule in rules:
        if _rule(rule, unit) == 'alternate':
            choice = _one(root.xpath('//t:choice[@xml:id=$identity]', namespaces={
                **NS, 'xml': XML[1:-1]}, identity=rule['xml_id']), 'Source alternate')
            options = list(choice)
            expected = rule['choices']
            if (len(options) != len(expected) or any(
                    node.tag != '{'+J+'}option' or node.get('corresp') != item['corresp']
                    or ''.join(node.itertext()) != item['text']
                    for node, item in zip(options, expected))):
                raise ValueError('Source alternate differs from its reviewed choices')
            if rule['colon_after_choice']:
                if (not rule['printed_annotation'].endswith(':)')
                        or any(item['text'].endswith(':') for item in expected)
                        or (choice.tail or '').lstrip().startswith(':')):
                    raise ValueError('Source colon normalization is ambiguous')
                choice.tail = ':'+(choice.tail or '')
            note = b.element(_notes(root, b), 'note', type='commentary',
                             target='#'+rule['xml_id'])
            note.set(XML+'lang', 'he')
            b.element(note, 'p', rule['printed_annotation'])
            continue

        condition = _one(root.xpath('//j:conditional[.//t:f[@name=$name]]',
                                    namespaces=NS, name=rule['condition']),
                         'Optional source condition')
        parent = condition.getparent()
        endpoint = _scope_end(condition)
        if parent.index(endpoint) <= parent.index(condition):
            raise ValueError('Optional source scope closes before it opens')
        if rule.get('inner_condition'):
            start, stop = parent.index(condition), parent.index(endpoint)
            divine_name = _one([node for node in list(parent)[start+1:stop]
                                if node.tag == '{'+J+'}divineName'],
                               'Nested optional Divine Name inside its outer scope')
            index = parent.index(divine_name)
            if index <= 0 or not (start < index < stop):
                raise ValueError('Nested Divine Name must lie inside its outer scope')
            preceding = parent[index-1]
            if (not (preceding.tail or '').endswith('(')
                    or not (divine_name.tail or '').startswith(')')):
                raise ValueError('Nested optional Divine Name lacks its source delimiters')
            preceding.tail = preceding.tail[:-1]
            tail = divine_name.tail[1:]
            divine_name.tail = None
            inner = b.element(parent, 'j:conditional', type='marked')
            inner.set(XML+'id', condition.get(XML+'id')+'_divine_name')
            parent.remove(inner)
            parent.insert(index, inner)
            b.feature_structures(b.element(inner, 'j:all'), [
                {'type': 'opensiddur:variant', 'features': {rule['inner_condition']: True}}])
            end = b.element(parent, 'j:endConditional', target='#'+inner.get(XML+'id'))
            parent.remove(end)
            parent.insert(parent.index(divine_name)+1, end)
            end.tail = tail
        if rule['missing_opener']:
            if (not rule.get('whole_line') or rule.get('text', '').startswith('(')
                    or not rule.get('text', '').endswith(')')):
                raise ValueError('Missing source opener requires a whole line with only its closer')
            anchor = b.element(parent, 'anchor')
            anchor.set(XML+'id', rule['xml_id']+'_source_error')
            parent.remove(anchor)
            parent.insert(parent.index(condition)+1, anchor)
            anchor.tail, condition.tail = condition.tail, None
            note = b.element(_notes(root, b), 'note', type='commentary',
                             target='#'+anchor.get(XML+'id'))
            note.set(XML+'lang', 'en')
            paragraph = b.element(note, 'p',
                                  'The printed line lacks its opening parenthesis. Supplied delimiter: ')
            choice = b.element(paragraph, 'choice')
            b.element(choice, 'sic')
            b.element(choice, 'corr', '(')


def apply_source_encoding(root, unit, lang):
    from . import build as b
    from opensiddur.importer.scan.authoring import printed_text
    config = unit.get('source_encoding', {}).get(lang, {})
    _keys(config, {'interpretations', 'reference_terminators_outside_container',
                  'remove_prayer_footnote_marker', 'commentary_pages',
                  'bibliography_page_range', 'continuous_quotation_chapter'})
    _interpretations(root, unit, config.get('interpretations', []))
    if 'reference_terminators_outside_container' in config:
        if type(config['reference_terminators_outside_container']) is not bool:
            raise ValueError('Reference terminator flag must be a boolean')
    if config.get('reference_terminators_outside_container'):
        before = printed_text(root)
        for marker in list(root.xpath(
                '//t:body//t:milestone[@unit="stanza"][not(@corresp)]', namespaces=NS)):
            holder = marker.getparent()
            if (holder.tag not in ('{'+T+'}l', '{'+T+'}p') or holder[-1] is not marker
                    or (marker.tail or '').strip()):
                raise ValueError('Reference terminator must end its source container')
            holder.getparent().insert(holder.getparent().index(holder)+1, marker)
        if printed_text(root) != before:
            raise ValueError('Moving a reference terminator changed source text')
    if item := config.get('remove_prayer_footnote_marker'):
        _keys(item, {'printed', 'text'}, {'printed', 'text'}, 'footnote marker')
        if (not isinstance(item['printed'], str) or not item['printed'].endswith('*')
                or item['printed'].count('*') != 1 or item['text'] != item['printed'][:-1]):
            raise ValueError('Only the printed footnote asterisk may be removed')
        body = root.find('.//{'+T+'}body')
        matches = [(node, slot) for node in body.iter() for slot in ('text', 'tail')
                   if item['printed'] in (getattr(node, slot) or '')]
        node, slot = _one(matches, 'Source footnote marker')
        text = getattr(node, slot)
        if text.count(item['printed']) != 1:
            raise ValueError('Source footnote marker is ambiguous')
        setattr(node, slot, text.replace(item['printed'], item['text'], 1))
    if limits := config.get('bibliography_page_range'):
        if not isinstance(limits, list) or len(limits) != 2 or not all(
                isinstance(value, str) and value for value in limits):
            raise ValueError('Source bibliography needs two printed page labels')
        scope = _one(root.xpath('//t:sourceDesc/t:bibl/t:biblScope[@unit="pages"]',
                               namespaces=NS), 'Source bibliography page range')
        scope.set('from', limits[0])
        scope.set('to', limits[1])
    commentaries = config.get('commentary_pages', [])
    if not isinstance(commentaries, list):
        raise ValueError('Paginated source commentaries must be a list')
    for item in commentaries:
        _keys(item, {'target', 'fragments'}, {'target', 'fragments'}, 'commentary pagination')
        if not isinstance(item['fragments'], list) or not item['fragments']:
            raise ValueError('Commentary pagination requires source fragments')
        for fragment in item['fragments']:
            _keys(fragment, {'scan', 'printed_page', 'text'},
                  {'scan', 'printed_page', 'text'}, 'commentary page fragment')
        note = _one(root.xpath('//t:note[@target=$target]', namespaces=NS,
                               target=item['target']), 'Paginated source commentary')
        paragraph = note.find('{'+T+'}p')
        expected = ''.join(fragment['text'] for fragment in item['fragments'])
        if paragraph is None or len(paragraph) or paragraph.text != expected:
            raise ValueError('Source commentary page fragments must exactly match its text')
        paragraph.text = None
        for fragment in item['fragments']:
            marker = b.element(paragraph, 'pb', ed='1965', n=fragment['printed_page'],
                               facs=b.page_image_url(b.IDENTIFIER, int(fragment['scan'][1:])-1, size=''))
            marker.tail = fragment['text']
        if ''.join(paragraph.itertext()) != expected:
            raise ValueError('Source commentary pagination changed its words')
    if context := config.get('continuous_quotation_chapter'):
        _keys(context, {'n', 'paragraphs', 'corresp'}, {'n', 'paragraphs', 'corresp'},
              'continuous quotation chapter')
        paragraphs = root.xpath('//t:body//t:p', namespaces=NS)
        if (len(paragraphs) != context['paragraphs'] or not paragraphs
                or (paragraphs[0].text or '').strip()):
            raise ValueError('Continuous quotation requires matching paragraphs without a leading prefix')
        markers = root.xpath('//t:body//t:milestone[@unit="chapter"]', namespaces=NS)
        if any(marker.get('corresp') not in (None, context['corresp'])
               or (marker.text or '').strip() or (marker.tail or '').strip()
               for marker in markers):
            raise ValueError('Continuous quotation cannot discard other chapter identities or words')
        spans = root.xpath('//t:body//t:seg[@source]', namespaces=NS)
        if any(span.get('type') not in (None, 'quotation') for span in spans):
            raise ValueError('Continuous quotation cannot overwrite other source semantics')
        for marker in markers:
            marker.getparent().remove(marker)
        for span in spans:
            span.set('type', 'quotation')
        marker = etree.Element('{'+T+'}milestone', unit='chapter',
                               n=context['n'], corresp=context['corresp'])
        paragraphs[0].insert(0, marker)
        etree.SubElement(paragraphs[-1], '{'+T+'}milestone', unit='chapter')
    return root
