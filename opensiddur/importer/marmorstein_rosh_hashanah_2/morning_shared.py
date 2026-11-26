"""Source-attested printings of canonical texts shared with the night service.

Canonical mappings stay outside the printing choices. Documentary occurrences
retain their own literal layout; expanded calls select the same canonical homes.
"""
import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.marmorstein_rosh_hashanah_1.build import words
from opensiddur.importer.scan.authoring import (
    TEI,
    XML,
    J,
    apply_corrections,
    element,
    write_documents,
)
from opensiddur.importer.util.internet_archive import page_image_url
from opensiddur.importer.util.validation import validate

from . import BOOK, IDENTIFIER, PROJECTS, ROOT_URN
from .morning_witnesses import witness_document, witness_header

T = '{'+TEI+'}'
N = {'tei': TEI, 'j': J}
TRANSLATION = 'urn:x-opensiddur:condition:siddur:rosh_hashanah/day_two/morning_translations'
BARUKH_TRANSLATION = 'urn:x-opensiddur:condition:prayer:shema/barukh_shem/second_day_printed_translation'


def feature(identity, printing):
    return identity.replace(':text:', ':condition:', 1)+'/second_day_'+printing+'_printing'


def expressions(features, printing, *, translated=True, barukh_translated=True):
    result = {key: key.endswith('/second_day_'+printing+'_printing') for key in features}
    result[TRANSLATION] = translated
    result[BARUKH_TRANSLATION] = barukh_translated
    return result


def declaration(parent, identifier, values):
    node = element(parent, 'j:declare')
    node.set(XML+'id', identifier)
    fs = element(node, 'fs', type='opensiddur:variant')
    for key, value in sorted(values.items()):
        field = element(fs, 'f')
        field.set('name', key)
        element(field, 'binary', value=str(value).lower())
    return node


def guard(parent, identifier, condition):
    node = element(parent, 'j:conditional')
    node.set(XML+'id', identifier)
    fs = element(element(node, 'j:all'), 'fs', type='opensiddur:variant')
    field = element(fs, 'f')
    field.set('name', condition)
    element(field, 'binary', value='true')
    return node


def fragments(parent, parts, lang):
    for index, fragment in enumerate(parts):
        if index or fragment.get('scan'):
            attrs = {'ed': '1965', 'facs': page_image_url(IDENTIFIER, int(fragment['scan'][1:])-1, size='')}
            if fragment.get('printed_page') is not None:
                attrs['n'] = fragment['printed_page']
            element(parent, 'pb', **attrs)
        words(parent, fragment['text'], lang)
        if index+1 < len(parts) and not fragment.get('join_next'):
            if len(parent):
                parent[-1].tail = (parent[-1].tail or '')+' '
            else:
                parent.text = (parent.text or '')+' '


def take_content(node):
    payload = etree.Element(T+'seg')
    # Poetry's mapping markers belong outside the alternatives, just as the
    # prose mappings immediately preceding a quoted span do.
    markers = [c for c in node if c.tag == T+'milestone']
    if markers:
        if node.text and node.text.strip():
            raise ValueError('Unexpected words before the poetry mapping')
        start = markers[0]
        payload.text, start.tail = start.tail, None
        for child in list(node)[list(node).index(start)+1:]:
            if child.tag == T+'milestone':
                continue
            payload.append(child)
    else:
        payload.text, node.text = node.text, None
        for child in list(node):
            payload.append(child)
    return payload


def install_payload(node, readings):
    if len(readings) == 1:
        result = readings[0][1]
        if len(node) and node[0].tag == T+'milestone':
            index = 1
        else:
            index = 0
        if result.text:
            if index:
                node[index-1].tail = result.text
            else:
                node.text = result.text
        for child in list(result):
            node.insert(index, child)
            index += 1
        return
    choice = etree.Element(T+'choice')
    for condition, payload in readings:
        option = element(choice, 'j:option', corresp=condition)
        option.text = payload.text
        option.extend(payload)
    index = 1 if len(node) and node[0].tag == T+'milestone' else 0
    node.insert(index, choice)


def contextual_document(unit, lang):
    unit = deepcopy(unit)
    unit.pop('reuse', None)
    context = ROOT_URN+'/morning_occurrences/'+unit['stem']
    unit['publication_context'] = context
    unit['map_root'] = False
    for part in unit['languages'][lang]:
        if unit['stem'] == 'morning_mah_tovu' and part.get('source', '').startswith('urn:x-opensiddur:text:bible:'):
            book, chapter, verse = part['source'].rsplit(':', 1)[-1].split('/')
            original = part.get('corresp')
            base = (context+'/quote/'+original.split(':text:', 1)[1].replace(':', '/')
                    if original else context)
            part['source_reference'] = part['source']
            part['chapter_corresp'] = base+'/quotation/'+book+'/'+chapter
            part['source_reference_corresp'] = part['chapter_corresp']+'/'+verse
        if part.get('reference_unit') == 'occurrence' and part.get('source', '').startswith('urn:x-opensiddur:text:bible:'):
            part['source_reference'] = part['source']
            part['chapter_corresp'] = context+'/repeat/quote/psalms/17'
            part['source_reference_corresp'] = context+'/repeat/quote/psalms/17/6'
    root = witness_document(unit, lang)
    # Literal documentary copies carry bounded contextual identities while the
    # shared libraries below supply each canonical identity exactly once.
    for node in root.iter():
        if node.tag == T+'milestone' and node.get('corresp'):
            canonical = node.get('corresp')
            if canonical.startswith(context+'/'):
                continue
            node.set('corresp', context+'/quote/'+canonical.split(':text:', 1)[1].replace(':', '/'))
            node.set('source', canonical)
    return root


def approved_readings(batch, recipe):
    raw = (batch/'working/readings.json').read_bytes()
    approval = (batch/'source_approval.json').read_bytes()
    if (hashlib.sha256(raw).hexdigest() != recipe.get('readings_sha256') or
            hashlib.sha256(approval).hexdigest() != recipe.get('source_approval_sha256')):
        raise ValueError('Stale approved morning source binding')
    record = json.loads(approval)
    if (record['status'] != 'approved_source_only' or
            record['working_readings_sha256'] != recipe['readings_sha256']):
        raise ValueError('Morning source approval is not current')
    return json.loads(raw)


def safe_stem(value):
    if not re.fullmatch(r'[a-z]+(?:_[a-z0-9]+)*', value) or value == 'index':
        raise ValueError('Unsafe shared witness stem')
    return value


def shared_documents(recipe, units):
    documents, features = [], set()
    for item in recipe['libraries']:
        unit = units[item['unit']]
        for lang in unit['languages']:
            baseline = item['templates'].get(lang) or item['templates']['he']
            if hashlib.sha256(baseline['xml'].encode()).hexdigest() != baseline['sha256']:
                raise ValueError('Changed accepted printing template')
            root = etree.fromstring(baseline['xml'].encode())
            original_div = root.find('.//'+T+'body/'+T+'div')
            div = deepcopy(original_div)
            if lang not in item['templates'] or baseline.get('donor'):
                root, body = witness_header(lang, PROJECTS[lang], unit['title'][lang], item['urn'], draft=True)
                body.append(div)
            body = root.find(T+'text/'+T+'body')
            if lang in item['templates'] and not baseline.get('donor'):
                body.replace(original_div, div)
            # Structural carriers may have an outer source attribute, but their
            # selected printing alone owns page provenance.
            for node in div.iter():
                if node.tag != T+'pb':
                    node.attrib.pop('facs', None)
            pages = list(div.iter(T+'pb'))
            night_page = deepcopy(pages[0]) if pages else None
            for page in pages:
                parent = page.getparent()
                previous = page.getprevious()
                if page.tail:
                    if previous is None:
                        parent.text = (parent.text or '')+page.tail
                    else:
                        previous.tail = (previous.tail or '')+page.tail
                parent.remove(page)
            nodes = div.xpath(item['xpath'], namespaces=N)
            parts = unit['languages'][lang]
            if item['unit'] == 'morning_mah_tovu':
                for node in nodes:
                    previous = node.getprevious()
                    if previous is not None and previous.tag == T+'milestone' and previous.get('unit') == 'verse':
                        continue
                    source = node.get('source')
                    book, chapter, verse = source.rsplit(':', 1)[-1].split('/')
                    base = item['urn']+'/varani/quotation/'+book+'/'+chapter
                    for unit_name, label, identity in [('chapter', chapter, base), ('verse', verse, base+'/'+verse)]:
                        marker = etree.Element(T+'milestone', unit=unit_name, n=label, corresp=identity, source=source)
                        node.addprevious(marker)
                    end_chapter = etree.Element(T+'milestone', unit='chapter')
                    node.addnext(end_chapter)
                    node.addnext(etree.Element(T+'milestone', unit='verse'))
            if len(nodes) != len(parts):
                raise ValueError('Shared template/source segment count mismatch: '+item['unit'])
            for index, (node, part) in enumerate(zip(nodes, parts)):
                old = take_content(node)
                identity = item.get('segment_identities', [])[index] if item.get('segment_identities') else item['urn']
                alternatives = []
                if lang in item['templates']:
                    if night_page is not None:
                        page = deepcopy(night_page)
                        page.tail = (page.tail or '')+(old.text or '')
                        old.text = None
                        old.insert(0, page)
                    condition = feature(identity, 'night')
                    features.add(condition)
                    alternatives.append((condition, old))
                payload = etree.Element(T+'seg')
                fragments(payload, part['fragments'], lang)
                condition = feature(identity, 'morning')
                features.add(condition)
                alternatives.append((condition, payload))
                if item['unit'] == 'morning_before_prayer' and index == 0:
                    repeated = etree.Element(T+'seg')
                    fragments(repeated, parts[14]['fragments'], lang)
                    condition = feature(identity, 'repeat')
                    features.add(condition)
                    alternatives.append((condition, repeated))
                if item['unit'] == 'morning_barukh_shem' and lang == 'he':
                    repeated = etree.Element(T+'seg')
                    fragments(repeated, units['qorbanot_barukh_shem']['languages']['he'][0]['fragments'], lang)
                    condition = feature(identity, 'qorbanot')
                    features.add(condition)
                    alternatives.append((condition, repeated))
                install_payload(node, alternatives)
            if item['unit'] == 'yigdal':
                caption = div.find(T+'p')
                if lang == 'en':
                    if caption is not None:
                        div.remove(caption)
                    caption = etree.Element(T+'p')
                    page = parts[0]['fragments'][0]
                    element(caption, 'pb', ed='1965', n=page['printed_page'],
                            facs=page_image_url(IDENTIFIER,int(page['scan'][1:])-1,size=''))
                    for reading in unit.get('instructions', []):
                        if lang in reading.get('witnesses', []):
                            note = element(caption, 'note', reading['text'], type=reading.get('type','description'))
                            note.set(XML+'lang',reading['language'])
                    div.insert(0,caption)
                elif caption is not None:
                    choice = etree.Element(T+'choice')
                    for printing in ['night','morning']:
                        option = element(choice,'j:option',corresp=feature(item['urn'],printing))
                        if printing == 'night':
                            option.append(deepcopy(night_page))
                        else:
                            page = parts[0]['fragments'][0]
                            element(option,'pb',ed='1965',n=page['printed_page'],
                                    facs=page_image_url(IDENTIFIER,int(page['scan'][1:])-1,size=''))
                    caption.insert(0,choice)
            # New English witnesses must not fill the night edition's gaps.
            if item.get('new_english') and lang == 'en':
                control = guard(div, 'printed_translation', TRANSLATION)
                div.insert(0, control)
                element(div, 'j:endConditional', target='#printed_translation')
            if item['unit'] == 'morning_barukh_shem' and lang == 'en':
                control = guard(div, 'printed_translation', BARUKH_TRANSLATION)
                div.insert(0, control)
                element(div, 'j:endConditional', target='#printed_translation')
            # Night-only printed citation labels must not be invented at morning.
            for note in root.findall(T+'standOff/'+T+'note'):
                control = etree.Element('{'+J+'}condition')
                fs = element(element(control, 'j:all'), 'fs', type='opensiddur:variant')
                field = element(fs, 'f')
                field.set('name', feature(item['urn'], 'night'))
                element(field, 'binary', value='true')
                note.insert(0, control)
            if item['unit'] == 'yigdal':
                source = root.find(T+'teiHeader/'+T+'fileDesc/'+T+'sourceDesc')
                bibl = element(source, 'bibl')
                element(bibl, 'ptr', target='/prayerbook_for_the_new_year-heidenheim-1965-he/index#project_source_bibl')
                element(bibl, 'note', 'The night printing reuses the first-day Hebrew witness; the morning printing is from the second-day volume.')
            documents.append((Path(PROJECTS[lang])/(safe_stem(item['stem'])+'.xml'), root))
    for stem in recipe['units']:
        unit = units[stem]
        for lang in unit['languages']:
            documents.append((Path(PROJECTS[lang])/(safe_stem(recipe.get('context_stems', {}).get(stem, stem))+'.xml'), contextual_document(unit, lang)))
    for path, accepted_xml in recipe.get('night_callers', {}).items():
        if path not in {p+'/second_night.xml' for p in [*PROJECTS.values(), 'machzor_expanded-opensiddur-he']}:
            raise ValueError('Unsafe night caller path')
        root = etree.fromstring(accepted_xml.encode())
        div = root.find('.//'+T+'body/'+T+'div')
        node = declaration(div, 'second_day_night_printings', expressions(features, 'night', translated=False))
        div.insert(0, node)
        element(div, 'j:endDeclare', target='#second_day_night_printings')
        documents.append((Path(path), root))
    if len({path for path, root in documents}) != len(documents):
        raise ValueError('Shared recipes would overwrite another generated document')
    apply_corrections({str(path): root for path, root in documents}, recipe.get('corrections', []))
    return documents, sorted(features)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    args = parser.parse_args(argv)
    source = args.source_root/BOOK
    batch = source/'batches/morning_s25_s45'
    recipe = json.loads((batch/'shared_printings.json').read_text())
    readings = approved_readings(batch, recipe)
    units = {u['stem']: u for u in readings['units']}
    documents, features = shared_documents(recipe, units)
    write_documents([(args.project_directory/path, root) for path, root in documents], validator=validate)
    print(json.dumps({'documents': len(documents), 'features': features}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
