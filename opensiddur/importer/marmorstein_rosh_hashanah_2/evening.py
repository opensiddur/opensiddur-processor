"""Assemble the source-bound second-night documentary and expanded sequences.

The sequence recipe holds order and contextual rubrics; prayer recipes own words.
No batch acceptance is inferred from generating a draft.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.scan.authoring import TEI, J, XML, element, write_documents
from opensiddur.importer.util.internet_archive import page_image_url
from opensiddur.importer.util.validation import validate
from . import BOOK, IDENTIFIER, PROJECTS, ROOT_URN
from .build import opening_document
from .draft_prayers import excerpt_header

EXPANDED = 'machzor_expanded-opensiddur-he'
EXPANDED_URN = 'urn:x-opensiddur:text:siddur:machzor_expanded/rosh_hashanah/day_two/maariv'
EVENING_URN = ROOT_URN+'/maariv'
FIRST_DAY = 'prayerbook_for_the_new_year-heidenheim-1965-he'


def settings(parent, expressions):
    """Use registered feature structures, with values retaining their actual kind."""
    for expression in expressions:
        fs = element(parent, 'fs', type=expression['type'])
        field = element(fs, 'f')
        field.set('name', expression['feature'])
        value = expression['value']
        if isinstance(value, bool):
            element(field, 'binary', value='true' if value else 'false')
        elif isinstance(value, int):
            element(field, 'numeric', value=str(value))
        else:
            raise ValueError('Sequence setting must be boolean or numeric')


def source_note(parent, reading, *, description=False):
    note = element(parent, 'note', reading['text'],
                   type='description' if description or reading.get('role') else 'instruction')
    note.set(XML+'lang', reading['language'])
    if reading.get('role'):
        note.set('corresp', 'urn:x-opensiddur:instruction:role/'+reading['role'])
    if reading.get('expansion'):
        note.text = None
        choice = element(note, 'choice')
        element(choice, 'abbr', reading['text'])
        element(choice, 'expan', reading['expansion'])
    if 'scan_page' in reading:
        note.set('facs', page_image_url(IDENTIFIER, reading['scan_page']-1))
    return note


def readings_for(item, lang, expanded):
    """Facing-page copies of one English rubric are one expanded instruction."""
    readings = item['readings'].values() if expanded else [item['readings'].get(lang)]
    seen = set()
    for reading in readings:
        if not reading:
            continue
        key = (reading['language'], reading['text'])
        if key not in seen:
            seen.add(key)
            yield reading


def render_sequence(parent, sequence, lang, *, expanded, units):
    for item in sequence:
        kind = item['kind']
        if kind == 'module':
            unit = units[item['file']]
            if not expanded and lang not in unit:
                continue
            if expanded:
                witness = unit['he']
                attributes = {'target': unit['urn']}
                if 'verses' in witness:
                    attributes = {'target': witness['verses'][0]['verse_urn'],
                                  'targetEnd': witness['verses'][-1]['verse_urn']}
            else:
                suffix = '@'+PROJECTS[lang]
                attributes = {'target': unit['urn']+suffix}
            element(parent, 'j:transclude', type='external', **attributes)
        elif kind == 'note':
            for reading in readings_for(item, lang, expanded):
                source_note(parent, reading, description=item.get('rubric_kind') == 'description')
        elif kind == 'direction':
            for reading in readings_for(item, lang, expanded):
                source_note(parent, reading, description=expanded)
            if expanded:
                for target in item['targets']:
                    element(parent, 'j:transclude', type='external', target=target)
        elif kind == 'condition':
            temporary = etree.Element(f'{{{TEI}}}div')
            render_sequence(temporary, item['items'], lang, expanded=expanded, units=units)
            if not len(temporary):
                continue
            scope = element(parent, 'j:conditional')
            scope.set(XML+'id', item['id'])
            rubrics = list(readings_for({'readings': item.get('rubrics', {})}, lang, expanded))
            if len(rubrics) == 1:
                source_note(scope, rubrics[0])
            elif rubrics:
                note = element(scope, 'note', type='instruction')
                for reading in rubrics:
                    phrase = element(note, 'foreign', reading['text'])
                    phrase.set(XML+'lang', reading['language'])
                    if 'scan_page' in reading:
                        phrase.set('facs', page_image_url(IDENTIFIER, reading['scan_page']-1))
            settings(element(scope, 'j:all'), item['expressions'])
            parent.extend(temporary)
            element(parent, 'j:endConditional', target='#'+item['id'])
        elif kind == 'declare':
            temporary = etree.Element(f'{{{TEI}}}div')
            render_sequence(temporary, item['items'], lang, expanded=expanded, units=units)
            if not len(temporary):
                continue
            scope = element(parent, 'j:declare')
            scope.set(XML+'id', item['id'])
            settings(scope, item['expressions'])
            parent.extend(temporary)
            element(parent, 'j:endDeclare', target='#'+item['id'])
        elif kind == 'section':
            # No empty documentary counterpart is made for Hebrew-only entrance.
            if not expanded and lang not in item['headings']:
                continue
            div = element(parent, 'div')
            div.set(XML+'id', item['id'])
            page = item.get('source_pages', {}).get(lang)
            if page:
                element(div, 'pb', ed='1965', n=page['printed_page'],
                        facs=page_image_url(IDENTIFIER, page['scan_page']-1))
            headings = (item.get('expanded_headings', item['headings']).items() if expanded
                        else [(lang, item['headings'][lang])])
            for language, heading in headings:
                node = element(div, 'head', heading)
                node.set(XML+'lang', language)
            render_sequence(div, item['items'], lang, expanded=expanded, units=units)
        else:
            raise ValueError('Unsupported sequence item: '+kind)


def sequence_document(recipe, units, lang, *, expanded=False, expanded_index=None,
                      documentary_urn=EVENING_URN):
    if expanded:
        root = etree.Element(f'{{{TEI}}}TEI', nsmap={'tei': TEI, 'j': J}, attrib={XML+'lang': 'he'})
        root.append(copy.deepcopy(expanded_index.find(f'{{{TEI}}}teiHeader')))
        desc = root.find(f'{{{TEI}}}teiHeader/{{{TEI}}}fileDesc')
        desc.find(f'{{{TEI}}}titleStmt/{{{TEI}}}title').text = 'Second-night Rosh ha-Shanah Maariv'
        desc.find(f'{{{TEI}}}publicationStmt/{{{TEI}}}idno').text = EXPANDED_URN+'@'+EXPANDED
        desc.find(f'{{{TEI}}}editionStmt/{{{TEI}}}edition').text = (
            'Expanded second-night sequence. Per-batch source, encoding and presentation '
            'acceptance is recorded in sources/marmorstein_rosh_hashanah_2/batches/.')
        source = desc.find(f'{{{TEI}}}sourceDesc')
        source.clear()
        for language, project in PROJECTS.items():
            bibl = element(source, 'bibl')
            element(bibl, 'ptr', target=f'/{project}/index#day_two_source_bibl')
            element(bibl, 'note', 'Second-day printed witness: '+language+'. Missing translations remain absent.')
        for dependency in recipe['dependencies']:
            bibl = element(source, 'bibl')
            element(bibl, 'ptr', target='/'+dependency['project']+'/index#project_source_bibl')
            element(bibl, 'note', dependency['reason']+' Borrowed units: '+
                    ', '.join(dependency['targets']))
        text = element(root, 'text')
    else:
        unit = {'urn': documentary_urn, 'titles': recipe['titles']}
        start = '1' if lang == 'he' and documentary_urn == EVENING_URN else '2'
        root = excerpt_header(unit, lang, {'printed_page': start,
                                         'printed_page_end': '11' if lang == 'he' else '10'})
        text = root.find(f'{{{TEI}}}text')
        text.clear()
    div = element(element(text, 'body'), 'div',
                  corresp=EXPANDED_URN if expanded else documentary_urn)
    if expanded:
        gate = element(div, 'j:conditional')
        gate.set(XML+'id', 'second_night_selection')
        settings(element(gate, 'j:all'), recipe['selection'])
        declaration = element(div, 'j:declare')
        declaration.set(XML+'id', 'second_night_settings')
        settings(declaration, recipe['context'])
    render_sequence(div, recipe['sequence'], lang, expanded=expanded, units=units)
    if expanded:
        element(div, 'j:endDeclare', target='#second_night_settings')
        element(div, 'j:endConditional', target='#second_night_selection')
    return root


def titqabbal_document(project_directory, expected_hash):
    """Expose an existing first-day text boundary without editing its accepted file."""
    path = project_directory/FIRST_DAY/'morning_full_kaddish.xml'
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError('Stale compatible first-day Titqabbal dependency')
    root = etree.parse(str(path)).getroot()
    urn = 'urn:x-opensiddur:text:prayer:kaddish/titqabbal/text'
    spans = root.xpath('//tei:seg[@source=$urn]', namespaces={'tei': TEI}, urn=urn)
    if len(spans) != 1:
        raise ValueError('Titqabbal dependency must have one exact source span')
    span = spans[0]
    pages = span.xpath('preceding::tei:pb[1]', namespaces={'tei': TEI})
    if not pages:
        raise ValueError('Titqabbal dependency needs its own scan provenance')
    desc = root.find(f'{{{TEI}}}teiHeader/{{{TEI}}}fileDesc')
    desc.find(f'{{{TEI}}}titleStmt/{{{TEI}}}title').text = 'תתקבל'
    desc.find(f'{{{TEI}}}publicationStmt/{{{TEI}}}idno').text = urn+'@'+EXPANDED
    desc.find(f'{{{TEI}}}editionStmt/{{{TEI}}}edition').text = (
        'Compatible first-day Hebrew dependency, not printed in the second-night batch. '
        'An exact existing text boundary is exposed without changing the accepted source witness.')
    source = desc.find(f'{{{TEI}}}sourceDesc')
    source.clear()
    bibl = element(source, 'bibl')
    element(bibl, 'ptr', target=f'/{FIRST_DAY}/index#project_source_bibl')
    element(bibl, 'note', 'Exact Titqabbal petition from morning_full_kaddish.xml; '
            'cantor/congregation directions and supplementary responses are not part of this unit.')
    body = root.find(f'{{{TEI}}}text')
    body.clear()
    div = element(element(body, 'body'), 'div', corresp=urn)
    page = copy.deepcopy(pages[0])
    page.tail = None
    div.append(page)
    paragraph = element(div, 'p')
    paragraph.set(XML+'lang', 'arc')
    copied = copy.deepcopy(span)
    copied.tail = None
    copied.set('facs', page.get('facs'))
    paragraph.append(copied)
    return root


def documentary_documents(recipe, units, lang):
    """Keep the shared evening preamble out of the untranslated entrance."""
    if len(recipe['sequence']) != 2:
        raise ValueError('Evening recipe needs entrance and service sections')
    service = sequence_document(dict(recipe, sequence=recipe['sequence'][1:]), units, lang,
                                documentary_urn=EVENING_URN+'/service')
    root = sequence_document(dict(recipe, sequence=recipe['sequence'][:1]), units, lang)
    entry = root.find(f'{{{TEI}}}text/{{{TEI}}}body/{{{TEI}}}div')
    element(entry, 'j:transclude', type='external',
            target=EVENING_URN+'/service@'+PROJECTS[lang])
    return root, service


def integrate_expanded_index(root, recipe):
    """Retain first-day children and select the new running order at its entry."""
    body = root.find(f'{{{TEI}}}text/{{{TEI}}}body/{{{TEI}}}div')
    holders = body.xpath('./*[@xml:id="section_second_night_maariv"]')
    if len(holders) > 1:
        raise ValueError('Duplicate expanded second-night section')
    for holder in holders:
        body.remove(holder)
    old_gates = body.xpath('./j:conditional[@xml:id="expanded_first_day_selection"]',
                          namespaces={'j': J})
    if not old_gates:
        gate = etree.Element(f'{{{J}}}conditional')
        gate.set(XML+'id', 'expanded_first_day_selection')
        body.insert(0, gate)
        element(body, 'j:endConditional', target='#expanded_first_day_selection')
    else:
        gate = old_gates[0]
        for child in list(gate):
            gate.remove(child)
    # Keep the original Erev RH services and appendices available. Exclude only
    # day two, whose own entrance/order must replace the first-volume sequence.
    settings(element(gate, 'j:none'), [{'type': 'opensiddur:holiday',
                                      'feature': 'rosh-hashana', 'value': 2}])
    holder = element(body, 'div')
    holder.set(XML+'id', 'section_second_night_maariv')
    gate = element(holder, 'j:conditional')
    gate.set(XML+'id', 'index_second_night_selection')
    settings(element(gate, 'j:all'), recipe['selection'])
    element(holder, 'j:transclude', type='external', target=EXPANDED_URN)
    element(holder, 'j:endConditional', target='#index_second_night_selection')
    desc = root.find(f'{{{TEI}}}teiHeader/{{{TEI}}}fileDesc')
    desc.find(f'{{{TEI}}}editionStmt/{{{TEI}}}edition').text = (
        'Expanded first-day maḥzor and second-night evening sequence. '
        'Independent evidence is recorded in both Marmorstein source projects; '
        'later second-day material is not yet included.')
    source = desc.find(f'{{{TEI}}}sourceDesc')
    if not source.xpath('./tei:bibl[@xml:id="expanded_second_day_sources"]',
                        namespaces={'tei': TEI}):
        bibl = element(source, 'bibl')
        bibl.set(XML+'id', 'expanded_second_day_sources')
        for project in PROJECTS.values():
            element(bibl, 'ptr', target=f'/{project}/index#day_two_source_bibl')
        element(bibl, 'note', 'Second-day evening witnesses; missing English remains absent. '
                'Compatible first-day Hebrew Kaddish ending parts and Yigdal retain their source credits.')
    for note in source.xpath('.//tei:note[@type="encoding"]', namespaces={'tei': TEI}):
        if note.text and 'this does not claim coverage of other volumes' in note.text:
            note.text = note.text.replace('this does not claim coverage of other volumes',
                                          'the second-night evening sequence now begins the second-day volume')
    for paragraph in root.xpath('./tei:text/tei:front//tei:p', namespaces={'tei': TEI}):
        if paragraph.text == 'First day of Rosh ha-Shanah':
            paragraph.text = 'Rosh ha-Shanah: first day and second-night evening service'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument('--draft', action='store_true', required=True)
    args = parser.parse_args(argv)
    source = args.source_root/BOOK
    path = source/'batches/maariv_s5_s24/evening_sequence.json'
    recipe = json.loads(path.read_text())
    for relative, expected in recipe['input_sha256'].items():
        if hashlib.sha256((source/relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Stale evening sequence input: '+relative)
    units = {}
    for relative in recipe['prayer_recipes']:
        prayer_recipe = json.loads((source/relative).read_text())
        for reading, expected in prayer_recipe['input_sha256'].items():
            if hashlib.sha256((source/reading).read_bytes()).hexdigest() != expected:
                raise ValueError('Stale prayer recipe input: '+reading)
        for unit in prayer_recipe['units']:
            if unit['file'] in units:
                raise ValueError('Prayer recipe ownership collision: '+unit['file'])
            units[unit['file']] = unit
    front_path = source/'front_resolved.json'
    front = json.loads(front_path.read_text())
    front_check = json.loads((source/'batches/front_matter_s1_s4/checklist.json').read_text())
    if hashlib.sha256(front_path.read_bytes()).hexdigest() != front_check['gates']['adjudication']['resolved_sha256']:
        raise ValueError('Stale front-matter adjudication')
    layouts = json.loads((source/'front_layout.json').read_text())
    targets = []
    for lang in PROJECTS:
        # Pair the evening heading only after the Hebrew-only entrance. A shared
        # transcluded service boundary prevents its English preamble drifting
        # onto the entrance when the two documentary roots are compiled together.
        root, service = documentary_documents(recipe, units, lang)
        targets.append((args.project_directory/PROJECTS[lang]/'maariv_service.xml', service))
        targets.append((args.project_directory/PROJECTS[lang]/'second_night.xml', root))
        index = opening_document(lang, front['pages'], layouts)
        index.find(f'{{{TEI}}}teiHeader/{{{TEI}}}fileDesc/{{{TEI}}}editionStmt/{{{TEI}}}edition').text = (
            'Volume in progress: front matter and second-night evening service. '
            'Per-scan acceptance and review evidence are recorded in '
            'sources/marmorstein_rosh_hashanah_2/batches/.')
        div = index.find(f'{{{TEI}}}text/{{{TEI}}}body/{{{TEI}}}div')
        element(div, 'j:transclude', type='external', target=EVENING_URN+'@'+PROJECTS[lang])
        targets.append((args.project_directory/PROJECTS[lang]/'index.xml', index))
    expanded_path = args.project_directory/EXPANDED/'index.xml'
    expanded_index = etree.parse(str(expanded_path)).getroot()
    root = sequence_document(recipe, units, 'he', expanded=True, expanded_index=expanded_index)
    targets.append((expanded_path.parent/'second_night.xml', root))
    targets.append((expanded_path.parent/'kaddish_titqabbal.xml',
                    titqabbal_document(args.project_directory, recipe['titqabbal_source_sha256'])))
    integrate_expanded_index(expanded_index, recipe)
    targets.append((expanded_path, expanded_index))
    for target in write_documents(targets, validator=validate):
        print(target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
