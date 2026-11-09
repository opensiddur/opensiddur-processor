"""Build source witnesses and the expanded mahzor from image readings.

Unreviewed material requires --draft and is visibly labeled as such. Missing
English witnesses produce no English file and never acquire substitute words.
"""
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path

from lxml import etree
import yaml

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.common.urn_registry import load_registry, parse_urn
from opensiddur.importer.scan.authoring import (
    TEI, J, XML, element, mixed_words, append_words, write_documents,
)
from opensiddur.importer.scan.navigation import append_instruction
from opensiddur.importer.scan.review import review_is_current
from opensiddur.importer.util.internet_archive import page_image_url, write_if_changed
from opensiddur.importer.util.validation import validate
from . import BOOK, IDENTIFIER, PROJECTS, EXPANDED, ROOT_URN, EXPANDED_URN


def document(lang, project, title, urn, *, index=False, draft=False):
    root = etree.Element(f'{{{TEI}}}TEI', nsmap={'tei': TEI, 'j': J}, attrib={XML+'lang': lang})
    desc = element(element(root, 'teiHeader'), 'fileDesc')
    titles = element(desc, 'titleStmt')
    element(titles, 'title', title, type='main')
    responsibility = element(titles, 'respStmt')
    element(responsibility, 'resp', 'AI-assisted scan reading and JLPTEI encoding', key='trc')
    element(responsibility, 'name', 'Codex', ref='urn:x-opensiddur:contributor:opensiddur.org/codex')
    edition = element(desc, 'editionStmt')
    element(edition, 'edition', ('DRAFT: independent adjudication pending. ' if draft else '')
            + 'Pilot installment, not the complete volume. Independent image readings and '
              'adjudications are recorded in sources/marmorstein_rosh_hashanah_1/.')
    publication = element(desc, 'publicationStmt')
    element(element(publication, 'distributor'), 'ref', 'Open Siddur Project', target='https://opensiddur.org')
    element(publication, 'idno', urn+'@'+project, type='urn')
    availability = element(publication, 'availability', status='free')
    element(availability, 'licence', 'CC0 1.0 Universal', target='https://creativecommons.org/publicdomain/zero/1.0/')
    source = element(desc, 'sourceDesc')
    if index:
        bibl = element(source, 'bibl')
        bibl.set(XML+'id', 'project_source_bibl')
        element(bibl, 'title', 'Prayerbook for the New Year [First Day]')
        element(bibl, 'editor', 'Wolf Heidenheim', role='arranger')
        element(bibl, 'editor', 'Jenny Marmorstein', role='translator')
        element(bibl, 'publisher', 'Victor Goldschmidt Publishers')
        element(bibl, 'pubPlace', 'Basle')
        element(bibl, 'date', '1965', when='1965')
        element(bibl, 'idno', f'https://archive.org/details/{IDENTIFIER}', type='url')
        element(bibl, 'idno', IDENTIFIER, type='internet_archive')
        element(bibl, 'date', '2026-11-08', type='accessed', when='2026-11-08')
        element(bibl, 'ref', 'Open Siddur source record', target='https://opensiddur.org/?p=69112')
        element(bibl, 'note', 'Digital imaging and document preparation: Aharon N. Varady; '
                'copy held by the HUC-JIR Klau Library, Cincinnati. The scan is the source. '
                'Independent reader: Claude Opus 5.5, medium reasoning. '
                'No translations have been supplied for passages absent from the English edition.')
    else:
        element(element(source, 'bibl'), 'ptr', target=f'/{project}/index#project_source_bibl')
    return root, element(element(root, 'text'), 'body')


def words(parent, text, lang):
    if lang == 'en':
        mixed_words(parent, text)
    else:
        # Preserve the source spelling/pointing, including its abbreviated Name.
        end = 0
        for match in re.finditer(r'(?<![\u0590-\u05ff])([ובלמכש]?[\u0591-\u05c7]*)(י[\u0591-\u05c7]*י[\u0591-\u05c7]*)(?![\u0590-\u05ff])', text):
            append_words(parent, text[end:match.start()]+match[1])
            element(parent, 'j:divineName', match[2])
            end = match.end()
        append_words(parent, text[end:])


def unit_document(unit, lang, draft):
    project = PROJECTS[lang]
    root, body = document(lang, project, unit['title'][lang], unit['urn'], draft=draft)
    div = element(body, 'div', **({'corresp': unit['urn']} if unit.get('map_root', True) else {}))
    current_page = None
    citations = unit.get('citations', {}).get(lang, [])
    if citations:
        notes = element(root, 'standOff', type='notes')
        root.remove(notes)
        root.insert(list(root).index(body.getparent()), notes)
        for citation in citations:
            if citation['scan'] != unit['languages'][lang][0]['fragments'][0]['scan']:
                raise ValueError('Citation scan differs from the passage opening')
            note = element(notes, 'note', type='citation', target=unit.get('start', unit['urn']))
            element(note, 'p', citation['text'])
    paragraph = None
    current_paragraph = None
    for segment in unit['languages'][lang]:
        identity = segment.get('paragraph', 1)
        if paragraph is None or identity != current_paragraph:
            paragraph = element(div, 'p')
            current_paragraph = identity
        for index, fragment in enumerate(segment['fragments']):
            if fragment['scan'] != current_page:
                attributes = {'ed': '1965', 'facs': page_image_url(IDENTIFIER, int(fragment['scan'][1:])-1, size='')}
                if fragment.get('printed_page') is not None:
                    attributes['n'] = fragment['printed_page']
                element(paragraph, 'pb', **attributes)
                current_page = fragment['scan']
            if index == 0 and segment.get('corresp'):
                element(paragraph, 'milestone', unit='verse' if ':bible:' in segment['corresp'] else 'prayer',
                        corresp=segment['corresp'])
            words(paragraph, fragment['text'], lang)
            append_words(paragraph, ' ')
    return root


def unit_text(unit, lang):
    return ' '.join(fragment['text'] for segment in unit['languages'][lang] for fragment in segment['fragments'])


def reference(unit):
    return {'target': unit.get('start', unit['urn']),
            **({'targetEnd': unit['end']} if unit.get('end') else {})}


def front_text(page):
    return ' '.join(([page['head']] if page.get('head') else [])+page['paragraphs'])


def add_front(root, pages, *, expanded=False):
    text = root.find(f'{{{TEI}}}text')
    front = etree.Element(f'{{{TEI}}}front')
    text.insert(0, front)
    if expanded:
        title = element(front, 'titlePage')
        title.set(XML+'lang', 'en')
        titles = element(title, 'docTitle')
        element(titles, 'titlePart', 'Expanded Ashkenazi Mahzor', type='main')
        element(titles, 'titlePart', 'First day of Rosh ha-Shanah — pilot installment', type='sub')
        element(title, 'docEdition', 'An editorial arrangement of the reviewed Heidenheim–Marmorstein passages. Not a complete service.')
        return
    for page in pages:
        if page['kind'] not in ('title', 'copyright', 'preface'):
            continue
        facs = page_image_url(IDENTIFIER, int(page['scan'][1:])-1, size='')
        if page['kind'] == 'title':
            element(front, 'pb', ed='1965', facs=facs)
            title = element(front, 'titlePage')
            title.set(XML+'lang', page['language'])
            titles = element(title, 'docTitle')
            element(titles, 'titlePart', page['paragraphs'][0], type='main')
            for line in page['paragraphs'][1:3]:
                element(title, 'byline', line)
            imprint = element(title, 'docImprint')
            element(imprint, 'publisher', page['paragraphs'][3])
            element(imprint, 'pubPlace', page['paragraphs'][4])
        else:
            div = element(front, 'div')
            div.set(XML+'lang', page['language'])
            element(div, 'pb', ed='1965', facs=facs)
            if page.get('head'):
                element(div, 'head', page['head'])
            for paragraph in page['paragraphs']:
                element(div, 'p', paragraph)


def require_review(readings, reviews):
    for unit in readings['units']:
        for lang in unit['languages']:
            review = reviews.get(unit['stem']+'/'+lang, {})
            if not review_is_current(review, unit_text(unit, lang)):
                raise ValueError(f"Independent review pending or stale: {unit['stem']}/{lang}; use --draft for inspection")
            for index, citation in enumerate(unit.get('citations', {}).get(lang, [])):
                key = f"citation/{unit['stem']}/{lang}/{index}"
                if not review_is_current(reviews.get(key, {}), citation['text']):
                    raise ValueError('Independent citation review pending: '+key)
    for name, navigation in readings.get('navigation', {}).items():
        for lang in navigation['scan']:
            key = 'navigation/'+name+'/'+lang
            if not review_is_current(reviews.get(key, {}), navigation['raw']):
                raise ValueError(f'Independent navigation review pending or stale: {key}')


def build(source, project_directory, *, draft=False):
    readings = json.loads((source/'readings.json').read_text())
    reviews_path = source/'reviews.json'
    reviews = json.loads(reviews_path.read_text()) if reviews_path.exists() else {}
    front_path = source/'front.json'
    front_pages = json.loads(front_path.read_text())['pages'] if front_path.exists() else []
    if not draft:
        require_review(readings, reviews)
        for page in front_pages:
            if page['kind'] in ('title', 'copyright', 'preface'):
                if not review_is_current(reviews.get('front/'+page['scan'], {}), front_text(page)):
                    raise ValueError('Independent front-matter review pending: '+page['scan'])
    registry, problems = load_registry()
    if problems:
        raise ValueError('URN registry cannot be loaded cleanly')
    for unit in readings['units']:
        identities = [unit['urn']] + [s['corresp'] for segments in unit['languages'].values()
                                                   for s in segments if s.get('corresp')]
        for urn in identities:
            # Numeric scripture descendants can be implicit in the registered book.
            if registry.resolve(urn) != urn:
                raise ValueError(f'Use the existing canonical URN, not its alias: {urn}')
            parsed = parse_urn(urn)
            if parsed.governed and urn not in registry.records and str(parsed.without_numeric_tail()) not in registry.records:
                raise ValueError(f'Unregistered identity: {urn}')
    documents = []
    for lang, project in PROJECTS.items():
        root, body = document(lang, project, 'Prayerbook for the New Year — first day', ROOT_URN,
                              index=True, draft=draft)
        if front_pages:
            add_front(root, front_pages)
        div = element(body, 'div', corresp=ROOT_URN)
        element(div, 'head', 'First-day Rosh ha-Shanah — pilot installment').set(XML+'lang', 'en')
        by_stem = {unit['stem']: unit for unit in readings['units']}
        for occurrence in readings.get('source_order', [{'unit': unit['stem']} for unit in readings['units']]):
            if 'navigation' in occurrence:
                navigation = readings['navigation'][occurrence['navigation']]
                scan = navigation['scan'][lang]
                element(div, 'pb', ed='1965', n=navigation['printed_page'],
                        facs=page_image_url(IDENTIFIER, int(scan[1:])-1, size=''))
                clauses = deepcopy(navigation['clauses'])
                for clause in clauses:
                    if 'target' in clause:
                        clause['target'] = clause['target'].format(project=project)
                append_instruction(div, clauses)
            else:
                unit = by_stem[occurrence['unit']]
                if lang in unit['languages']:
                    element(div, 'j:transclude', type='external', **reference(unit))
        for unit in readings['units']:
            if lang in unit['languages']:
                documents.append((project_directory/project/(unit['stem']+'.xml'), unit_document(unit, lang, draft)))
        documents.append((project_directory/project/'index.xml', root))
    root, body = document('he', EXPANDED, 'Expanded Ashkenazi Mahzor', EXPANDED_URN, index=True, draft=draft)
    add_front(root, [], expanded=True)
    div = element(body, 'div', corresp=EXPANDED_URN)
    element(div, 'head', 'מחזור אשכנז מורחב').set(XML+'lang', 'he')
    element(div, 'head', 'Expanded Ashkenazi Mahzor').set(XML+'lang', 'en')
    element(div, 'note', 'Pilot passages only. Complete first-day service assembly remains in progress.', type='instruction').set(XML+'lang', 'en')
    # The same structural sequence drives Hebrew and any English counterparts.
    order = readings.get('expanded_order', [{'unit': unit['stem']} for unit in readings['units']])
    by_stem = {unit['stem']: unit for unit in readings['units']}
    for occurrence in order:
        if 'navigation' in occurrence:
            navigation = readings['navigation'][occurrence['navigation']]
            clauses = deepcopy(navigation['clauses'])
            for clause in clauses:
                if 'target' in clause:
                    clause['target'] = clause['target'].format(project=PROJECTS['he'])
            append_instruction(div, clauses, expanded=True)
        else:
            unit = by_stem[occurrence['unit']]
            element(div, 'j:transclude', type='external', **reference(unit))
    documents.append((project_directory/EXPANDED/'index.xml', root))
    # A language witness removed from the readings must not remain discoverable
    # through refdb merely because an earlier build wrote its file.
    obsolete = [project_directory/project/(unit['stem']+'.xml')
                for lang, project in PROJECTS.items() for unit in readings['units']
                if lang not in unit['languages']]
    paths = write_documents(documents, validator=validate, obsolete_paths=obsolete)
    settings_directory = project_directory.parent/'settings'
    for project, variant, parallel in [(PROJECTS['he'], 'documentary', False),
                                       (PROJECTS['he'], 'with_translation', True),
                                       (EXPANDED, 'undated', True)]:
        settings = {'description': 'Pilot installment; not a complete first-day service.',
                    'requires_processor': '>=0.8.0.dev0',
                    'book': {'project': project, 'file_name': 'index.xml', 'title': 'First-day Mahzor — pilot'},
                    'annotations': list(PROJECTS.values()) if parallel else [PROJECTS['he']],
                    'priority': {'transclusion': [project]+[p for p in PROJECTS.values() if p != project],
                                 'instructions': [project]+[p for p in PROJECTS.values() if p != project]},
                    'typography': {'instructions': {'from': 'both'}, 'line_numbers': {'enabled': False}}}
        if parallel:
            settings['parallel'] = {'projects': [PROJECTS['en']]}
        destination = settings_directory/project/(variant+'.yaml')
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_if_changed(destination, yaml.safe_dump(settings, allow_unicode=True, sort_keys=False))
    print(f'{len(paths)} validated JLPTEI files; ' + ('DRAFT review status' if draft else 'reviewed installment'))
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument('--draft', action='store_true')
    args = parser.parse_args(argv)
    build(args.source_root/BOOK, args.project_directory, draft=args.draft)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
