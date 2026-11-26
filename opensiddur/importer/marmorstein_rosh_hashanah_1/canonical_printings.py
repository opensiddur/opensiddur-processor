"""Verified pagination at a caller's boundaries inside one shared text."""
import re
from copy import deepcopy

from lxml import etree

T = '{http://www.tei-c.org/ns/1.0}'
X = '{http://www.w3.org/XML/1998/namespace}'
FIELDS = {'id', 'host', 'lang', 'identity', 'caller', 'fragment', 'scan',
          'printed_page', 'before'}


def bindings(readings):
    """Fail closed unless every multi-page caller boundary is source-attested."""
    from .realizations import (
        PLAIN_FRAGMENT_KEYS,
        _range_segments,
        canonical_text,
        join_source_fragments,
    )
    entries = readings.get('canonical_printings', [])
    if not isinstance(entries, list):
        raise ValueError('Canonical printings must be a list')
    units = {u['stem']: u for u in readings['units']}
    result, ids, grouped = [], set(), {}
    for item in entries:
        if (not isinstance(item, dict) or set(item) != FIELDS
                or any(not isinstance(item[k], str) or not item[k]
                       for k in ('id','host','lang','identity','caller','scan','before'))
                or type(item['fragment']) is not int or item['fragment'] < 1
                or not re.fullmatch(r's[1-9][0-9]*', item['scan'])
                or item['printed_page'] is not None and not isinstance(item['printed_page'], str)
                or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*', item['id'])
                or item['id'] in ids):
            raise ValueError('Canonical printing requires one complete, uniquely identified boundary')
        ids.add(item['id'])
        caller = units.get(item['caller'])
        if caller is None:
            raise ValueError('Canonical printing has no caller')
        matching = [s for s in caller['languages'].get(item['lang'], [])
                    if s.get('canonical') == item['identity']]
        if len(matching) != 1 or matching[0].get('canonical_end'):
            raise ValueError('Canonical printing must name one complete canonical occurrence')
        part = matching[0]
        if (len(caller['languages'][item['lang']]) != 1
                or set(part) != {'canonical', 'paragraph', 'fragments'}
                or caller.get('publication_context') or caller.get('start') or caller.get('end')):
            raise ValueError('Paginated canonical callers require one plain complete external occurrence')
        fragments = part['fragments']
        index = item['fragment']
        if (index >= len(fragments) or any(f.get('join_next') for f in fragments)
                or any(set(f)-PLAIN_FRAGMENT_KEYS for f in fragments)
                or fragments[index]['scan'] != item['scan']
                or fragments[index].get('printed_page') != item['printed_page']
                or any(not re.fullmatch(r's[1-9][0-9]*', f.get('scan','')) for f in fragments)
                or any(int(a['scan'][1:]) >= int(z['scan'][1:]) for a,z in zip(fragments,fragments[1:]))):
            raise ValueError('Canonical printing does not match its source fragment')
        host, _ = _range_segments(readings, item['lang'], item['identity'])
        if not host.get('canonical_home'):
            raise ValueError('Canonical printing requires a dedicated canonical home')
        if host['stem'] != item['host']:
            raise ValueError('Canonical printing names the wrong provider')
        settings = {k: v for fs in caller.get('wording_selection', [])
                    if fs['type'] == 'opensiddur:variant' for k,v in fs['features'].items()}
        text = canonical_text(readings, item['lang'], item['identity'], settings)
        normal = lambda s: ' '.join(s.split())
        text = normal(text)
        before = normal(item['before'])
        prefix = normal(join_source_fragments(fragments[:index]))
        if (text != normal(join_source_fragments(fragments)) or text.count(before) != 1
                or text[:text.index(before)].rstrip() != prefix
                or not normal(fragments[index]['text']).startswith(before)):
            raise ValueError('Canonical printing boundary is not at the attested word')
        context = caller.get('page_context') or caller['urn'].partition(':siddur:')[2]
        if not context or ':' in context or any(c.isspace() for c in context):
            raise ValueError('Canonical printing needs an unambiguous siddur printing context')
        record = deepcopy(item)
        record.update(file=host.get('canonical_home', {}).get('file', host['stem']), context=context)
        result.append(record)
        grouped.setdefault((item['caller'],item['lang'],item['identity']), []).append(index)
    for caller in readings['units']:
        for lang, parts in caller['languages'].items():
            for part in parts:
                if part.get('canonical') and len(part['fragments']) > 1:
                    indexes = grouped.get((caller['stem'],lang,part['canonical']), [])
                    if sorted(indexes) != list(range(1,len(part['fragments']))):
                        raise ValueError('Every canonical source page boundary needs one verified printing')
    return result


def apply(documents, readings):
    """Place only explicitly sigiled breaks, including inside a selected wording."""
    from opensiddur.importer.util.internet_archive import page_image_url

    from . import IDENTIFIER, PROJECTS
    for item in bindings(readings):
        roots = [root for path,root in documents
                 if path.stem == item['file'] and path.parent.name == PROJECTS[item['lang']]]
        if len(roots) != 1:
            raise ValueError('Canonical printing needs exactly one generated provider')
        root = roots[0]
        body = root.find(T+'text/'+T+'body')
        matches = [(node,slot) for node in body.iter() for slot in ('text','tail')
                   if item['before'] in (getattr(node,slot) or '')
                   and not any(a.tag == T+'note' for a in
                               ([node] if slot=='text' else [])+list(node.iterancestors()))]
        if sum(getattr(node,slot).count(item['before']) for node,slot in matches) != 1:
            raise ValueError('Canonical printing word is absent, split, or ambiguous in generated provider')
        node,slot = matches[0]
        caller = next(u for u in readings['units'] if u['stem'] == item['caller'])
        settings = {k:v for fs in caller.get('wording_selection', [])
                    if fs['type'] == 'opensiddur:variant' for k,v in fs['features'].items()}
        options = [a for a in ([node] if slot == 'text' else [])+list(node.iterancestors())
                   if a.tag == '{http://jewishliturgy.org/ns/jlptei/2}option']
        if len(options) != 1 or settings.get(options[0].get('corresp')) is not True:
            raise ValueError('Canonical printing must belong to one positively selected wording option')
        prefix = _selected_prefix(body, item['identity'], settings, node, slot, item['before'])
        part = caller['languages'][item['lang']][0]
        from .realizations import join_source_fragments
        expected_prefix = ' '.join(join_source_fragments(part['fragments'][:item['fragment']]).split())
        if prefix != expected_prefix:
            raise ValueError('Generated canonical printing is outside its selected range or attested offset')
        before,after = getattr(node,slot).split(item['before'],1)
        marker = etree.Element(T+'pb', ed='1965 '+item['context'],
            facs=page_image_url(IDENTIFIER,int(item['scan'][1:])-1,size=''))
        if item['printed_page'] is not None:
            marker.set('n',item['printed_page'])
        marker.set(X+'id','printing_'+item['id'])
        marker.tail = item['before']+after
        setattr(node,slot,before)
        if slot == 'text':
            node.insert(0,marker)
        else:
            node.addnext(marker)


def permitted_breaks(readings, stem, lang):
    from opensiddur.importer.util.internet_archive import page_image_url

    from . import IDENTIFIER
    return {('printing_'+v['id'],'1965 '+v['context'],v['printed_page'],
             page_image_url(IDENTIFIER,int(v['scan'][1:])-1,size=''))
            for v in bindings(readings) if v['file']==stem and v['lang']==lang}


def _selected_prefix(body, identity, settings, stop_node, stop_slot, needle):
    """Resolve options while checking the actual XML reference scope and offset."""
    J = '{http://jewishliturgy.org/ns/jlptei/2}'
    starts = [m for m in body.iter(T+'milestone') if m.get('corresp') == identity]
    if len(starts) != 1:
        raise ValueError('Canonical printing needs one generated reference scope')
    unit = starts[0].get('unit')
    active, found, pieces = False, False, []
    marked = []

    def slot(node, key):
        nonlocal found
        if not active:
            return
        value = getattr(node,key) or ''
        if node is stop_node and key == stop_slot:
            if marked:
                raise ValueError('Canonical page boundary cannot disappear inside optional words')
            pieces.append(value[:value.index(needle)])
            found = True
            raise StopIteration
        pieces.append(value)

    def walk(node):
        nonlocal active
        if node.tag == T+'note':
            return
        if node.tag == T+'milestone' and node.get('unit') == unit:
            active = node is starts[0]
        if node.tag == J+'option':
            value = settings.get(node.get('corresp'))
            if active and type(value) is not bool:
                raise ValueError('Printing scope has an unresolved wording option')
            if value is not True:
                return
        if active and node.tag == J+'conditional' and node.get('type') == 'marked':
            # Source fidelity retains the printed delimiters of an undecided
            # intrinsic addition; the compiler resolves them for each profile.
            marked.append(node.get(X+'id'))
            pieces.append('(')
        elif active and node.tag == J+'endConditional' and node.get('target','').lstrip('#') in marked:
            key = node.get('target').lstrip('#')
            if marked[-1] != key:
                raise ValueError('Canonical optional scopes must be properly nested')
            marked.pop()
            pieces.append(')')
        slot(node,'text')
        for child in node:
            walk(child)
            slot(child,'tail')

    try:
        walk(body)
    except StopIteration:
        pass
    return ' '.join(''.join(pieces).split()) if found else None


def guards(documents, readings):
    """The boundary's unique selected wording may only be used by its caller."""
    from . import PROJECTS
    J = '{http://jewishliturgy.org/ns/jlptei/2}'
    result=[]
    for item in bindings(readings):
        roots=[root for path,root in documents if path.stem==item['file'] and path.parent.name==PROJECTS[item['lang']]]
        if len(roots)!=1:
            raise ValueError('Printing guard needs one canonical home')
        markers=[pb for pb in roots[0].iter(T+'pb') if pb.get(X+'id')=='printing_'+item['id']]
        if len(markers)!=1:
            raise ValueError('Printing guard needs one declared page marker')
        options=[a for a in markers[0].iterancestors() if a.tag==J+'option']
        if len(options)!=1:
            raise ValueError('Printing guard requires one wording option')
        result.append(dict(item,feature=options[0].get('corresp')))
    return result
