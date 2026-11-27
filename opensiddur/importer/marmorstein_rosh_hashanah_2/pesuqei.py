"""Append source-approved Pesuqei deZimrah to second-day Shacharit.

Literal witnesses preserve this printing. The expanded spine calls canonical
identities and locally suppresses the unprinted English closing repetition.
"""
import argparse
import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path, PurePosixPath

import yaml
from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.exporter.urn import split_range
from opensiddur.importer.scan.authoring import (
    TEI,
    XML,
    apply_corrections,
    element,
    normalized_xml,
    write_documents,
)
from opensiddur.importer.util.validation import validate

from . import BOOK, EXPANDED, PROJECTS, ROOT_URN
from .morning_shared import approved_readings, declaration, guard, safe_stem
from .morning_witnesses import witness_document, witness_header

T = '{'+TEI+'}'
SERVICE_URN = ROOT_URN+'/shacharit/pesuqei_dezimrah'
RESP = 'urn:x-opensiddur:contributor:opensiddur.org/codex'
BATCH = 'pesuqei_s46_s63'


def translation_feature(target):
    if not re.fullmatch(r'urn:x-opensiddur:text:bible:[a-z_]+/\d+/\d+', target):
        raise ValueError('A Hebrew-only repetition must select one canonical verse')
    return target.replace(':text:', ':condition:', 1)+'/second_day_repetition_translation'


def call(parent, target, *, project=None):
    if not target.startswith('urn:x-opensiddur:text:') or '@' in target:
        raise ValueError('A service target must be an unqualified text URN')
    return element(parent, 'j:transclude', type='external',
                   target=target+('@'+project if project else ''))


def repeat_features(order):
    return {translation_feature(i['expanded_target']): True
            for i in order if i.get('hebrew_only_repeat')}


def guard_translation(root, correspondence):
    """Guard one explicitly terminated verse, retaining its mapping and source."""
    matches = root.xpath('.//tei:milestone[@corresp=$urn]',
                         namespaces={'tei': TEI}, urn=correspondence)
    if len(matches) != 1:
        raise ValueError('Translation guard needs one canonical verse boundary')
    marker = matches[0]
    if marker.get('unit') != 'verse':
        raise ValueError('Translation availability must wrap a canonical verse')
    parent = marker.getparent()
    following = list(parent)[parent.index(marker)+1:]
    # The importer emits a same-unit terminator. Never mistake a bare chapter
    # terminator for a verse endpoint or silently span another parent element.
    boundary = None
    for node in following:
        if node.tag != T+'milestone':
            continue
        if node.get('unit') in ('chapter', 'book') and node.get('corresp'):
            raise ValueError('Containing reference opens before the same-unit endpoint')
        if node.get('unit') == marker.get('unit'):
            boundary = node
            break
    if boundary is None:
        raise ValueError('Translation guard needs an explicit same-unit endpoint')
    identifier = 'second_day_'+correspondence.rsplit(':', 1)[-1].replace('/', '_')+'_translation'
    condition = guard(parent, identifier, translation_feature(correspondence))
    condition.tail, marker.tail = marker.tail, None
    marker.addnext(condition)
    boundary.addprevious(element(parent, 'j:endConditional', target='#'+identifier))
    return root


def service_document(units, order, lang):
    root, body = witness_header(lang, PROJECTS[lang],
                                'פסוקי דזמרה' if lang == 'he' else 'Verses of song',
                                SERVICE_URN, draft=True)
    section = element(body, 'div', corresp=SERVICE_URN)
    values = repeat_features(order)
    if values:
        declaration(section, 'pesuqei_printed_translations', values)
    for item in order:
        unit = units[item['key']]
        if item.get('hebrew_only_repeat') and 'en' in unit['languages']:
            raise ValueError('Documentary repetition must be a distinct Hebrew-only unit')
        if lang not in unit['languages']:
            continue
        scope = 'documentary_'+safe_stem(item['key'])+'_translation'
        if item.get('hebrew_only_repeat'):
            declaration(section, scope, {translation_feature(item['expanded_target']): False})
        if item.get('ranges'):
            for span in item['ranges']:
                if lang in span['witnesses']:
                    call(section, span['target'], project=PROJECTS[lang])
        else:
            call(section, item.get('documentary_target', unit.get('start', unit['urn'])),
                 project=PROJECTS[lang])
        if item.get('hebrew_only_repeat'):
            element(section, 'j:endDeclare', target='#'+scope)
    if values:
        element(section, 'j:endDeclare', target='#pesuqei_printed_translations')
    return root


def append_sequence(template, units, order, *, lang, expanded=False):
    root = deepcopy(template)
    parents = root.xpath('.//tei:div[@xml:id="morning_blessings"]',
                         namespaces={'tei': TEI, 'xml': XML[1:-1]})
    if len(parents) != 1:
        raise ValueError('The existing Shacharit section must be unique')
    parent = parents[0]
    titles = [''.join(h.itertext()) for h in parent.findall(T+'head')]
    bare = [''.join(c for c in unicodedata.normalize('NFD', title)
                    if not unicodedata.combining(c)).strip(' .') for title in titles]
    if not any(title in ('תפלת שחרית', 'Morning Prayer') for title in bare):
        raise ValueError('Continuation must belong beneath the actual Shacharit heading')
    if not expanded:
        call(parent, SERVICE_URN, project=PROJECTS[lang])
        return root
    existing = {n.get(XML+'id') for n in root.iter() if n.get(XML+'id')}

    def unique(node, identifier):
        if identifier in existing:
            raise ValueError('Expanded structural identity already exists: '+identifier)
        existing.add(identifier)
        node.set(XML+'id', identifier)

    section = element(parent, 'div')
    unique(section, 'second_day_pesuqei_dezimrah')
    for language, title in [('he', 'פסוקי דזמרה'), ('en', 'Verses of song')]:
        element(section, 'head', title, resp=RESP).set(XML+'lang', language)
    values = repeat_features(order)
    if values:
        if 'pesuqei_printed_translations' in existing:
            raise ValueError('Translation declaration identity already exists')
        existing.add('pesuqei_printed_translations')
        declaration(section, 'pesuqei_printed_translations', values)
    for item in order:
        if 'en' not in units[item['key']]['languages'] and not item.get('hebrew_only_repeat'):
            raise ValueError('An untranslated canonical call needs an explicit availability policy')
        if item.get('hebrew_only_repeat'):
            occurrence = element(section, 'div')
            identifier = 'pesuqei_'+safe_stem(item['key'])
            unique(occurrence, identifier)
            scope = identifier+'_translation'
            if scope in existing:
                raise ValueError('Repeated declaration identity already exists')
            existing.add(scope)
            declaration(occurrence, scope,
                        {translation_feature(item['expanded_target']): False})
            call(occurrence, item['expanded_target'])
            element(occurrence, 'j:endDeclare', target='#'+scope)
        elif item.get('ranges'):
            for span in item['ranges']:
                call(section, span['target'])
        else:
            call(section, item['expanded_target'])
    if values:
        element(section, 'j:endDeclare', target='#pesuqei_printed_translations')
    return root


def build_documents(recipe, units):
    order = recipe['order']
    keys = [i['key'] for i in order]
    if len(set(keys)) != len(keys) or set(keys) != units.keys():
        raise ValueError('Source units and unique documentary order disagree')
    for item in order:
        if item.get('ranges'):
            if item.get('hebrew_only_repeat'):
                raise ValueError('A repeated verse cannot also split a partial translation')
            for span in item['ranges']:
                if not span.get('witnesses') or not set(span['witnesses']) <= set(units[item['key']]['languages']):
                    raise ValueError('Range witnesses disagree with the source unit')
                call(etree.Element(T+'div'), span['target'])
    documents = []
    for unit in units.values():
        stem = safe_stem(unit['stem'])
        for lang in unit['languages']:
            documents.append((PROJECTS[lang]+'/'+stem+'.xml', witness_document(unit, lang)))
    # Correction helpers change literal text through sic/corr choices only.
    # Apply them before constructing translation guards; spines are not present.
    apply_corrections(dict(documents), recipe.get('corrections', []))
    by_path = dict(documents)
    for item in order:
        for span in item.get('ranges', []):
            endpoints = split_range(span['target']) or (span['target'],)
            actual = {lang for lang in units[item['key']]['languages']
                      if set(endpoints) <= {n.get('corresp') for n in
                         by_path[PROJECTS[lang]+'/'+units[item['key']]['stem']+'.xml'].iter()}}
            if actual != set(span['witnesses']):
                raise ValueError('Range witness availability disagrees with its actual boundaries')
            if 'en' not in span['witnesses'] and any(
                    n.get('corresp') in endpoints
                    for path, root in documents if path.startswith(PROJECTS['en']+'/')
                    for n in root.iter()):
                raise ValueError('An in-batch English provider would fill an untranslated range')

    # Bind every suppression to exactly one English canonical provider before
    # compilation. A false, selected provider must not invite another edition.
    for item in order:
        if not item.get('hebrew_only_repeat'):
            continue
        target = item['expanded_target']
        translation_feature(target)
        matches = [(root, node) for path, root in documents
                   if path.startswith(PROJECTS['en']+'/')
                   for node in root.iter() if node.get('corresp') == target]
        if len(matches) != 1 or matches[0][1].tag != T+'milestone':
            raise ValueError('Repetition needs exactly one guardable English canonical provider')
        guard_translation(matches[0][0], target)
    for lang in PROJECTS:
        documents.append((PROJECTS[lang]+'/pesuqei_service.xml',
                          service_document(units, order, lang)))
    spines = {p+'/morning_prayers_service.xml': (lang, False)
              for lang, p in PROJECTS.items()}
    spines[EXPANDED+'/second_day_morning.xml'] = ('he', True)
    templates = recipe['spine_templates']
    if len(templates) != len(spines) or {i['path'] for i in templates} != spines.keys():
        raise ValueError('Recipe must extend exactly the three morning service spines')
    for item in templates:
        raw = item['xml'].encode('utf-8')
        if (hashlib.sha256(raw).hexdigest() != item['sha256'] or
                not re.fullmatch('[0-9a-f]{40}', item.get('baseline_commit', ''))):
            raise ValueError('Changed or unbound accepted service template')
        lang, expanded = spines[item['path']]
        template = etree.fromstring(raw)
        idno = template.find('.//'+T+'publicationStmt/'+T+'idno[@type="urn"]')
        project = item['path'].split('/')[0]
        if (template.get(XML+'lang') != lang or idno is None
                or not (idno.text or '').endswith('@'+project)):
            raise ValueError('Service template language/publication disagrees with its path')
        documents.append((item['path'], append_sequence(template, units,
                          order, lang=lang, expanded=expanded)))
    paths = [path for path, _ in documents]
    if len(set(paths)) != len(paths) or set(paths) & set(recipe['protected_files']):
        raise ValueError('Repeated output or an accepted prayer file would be overwritten')
    return documents


def project_path(base, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or len(path.parts) != 2:
        raise ValueError('Unsafe project file path')
    return base/relative


def verify_existing_outputs(project_directory, documents, templates):
    baselines = {i['path']: i['sha256'] for i in templates}
    for relative, root in documents:
        path = project_path(project_directory, relative)
        if not path.exists():
            continue
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        generated = hashlib.sha256(normalized_xml(root).encode('utf-8')).hexdigest()
        if current not in (generated, baselines.get(relative)):
            raise ValueError('An existing target has unreviewed changes: '+relative)


def reject_existing_repeat_providers(project_directory, documents, order):
    """An older unguarded provider in this edition cannot fill the repetition."""
    targets = {i['expanded_target'] for i in order if i.get('hebrew_only_repeat')}
    targets.update(span['target'] for item in order for span in item.get('ranges', [])
                   if 'en' not in span['witnesses'])
    regenerated = {relative for relative, _ in documents}
    for path in (project_directory/PROJECTS['en']).rglob('*.xml'):
        if str(path.relative_to(project_directory)) in regenerated:
            continue
        root = etree.parse(str(path))
        if any(n.get('corresp') in targets for n in root.iter()):
            raise ValueError('Existing English provider would bypass the repeat guard: '+str(path))


def require_edition_parallel_profiles(directory, hashes):
    """Bind the shipped profiles that restrict counterparts to this translator."""
    paths = [PROJECTS['he']+'/documentary_parallel.yaml',
             EXPANDED+'/second_day_morning.yaml']
    if set(hashes) != set(paths):
        raise ValueError('Both parallel profiles must have reviewed hashes')
    for relative in paths:
        raw = project_path(directory, relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != hashes[relative]:
            raise ValueError('A reviewed parallel profile changed: '+relative)
        values = yaml.safe_load(raw)
        if values.get('parallel', {}).get('projects') != [PROJECTS['en']]:
            raise ValueError('Edition profiles must not fill missing translations from another project')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    args = parser.parse_args(argv)
    batch = args.source_root/BOOK/'batches'/BATCH
    recipe_path = batch/'pesuqei_units.json'
    recipe = json.loads(recipe_path.read_text(encoding='utf-8'))
    review = json.loads((batch/'recipe_approval.json').read_text(encoding='utf-8'))
    if (review.get('status') != 'approved_source_and_structure_only' or
            review.get('batch') != BATCH or not review.get('reviewer') or
            review.get('recipe_sha256') != hashlib.sha256(recipe_path.read_bytes()).hexdigest()):
        raise ValueError('The source/structure recipe lacks a current independent review')
    require_edition_parallel_profiles(args.project_directory.parent/'settings',
                                      recipe['settings_sha256'])
    readings = approved_readings(batch, recipe)
    raw_units = readings['units']
    units = {u['stem']: u for u in raw_units}
    approval = json.loads((batch/'source_approval.json').read_text(encoding='utf-8'))
    if (len(units) != len(raw_units) or approval.get('batch') != BATCH or
            approval.get('scan_pages') != list(range(46, 64)) or
            set(approval.get('unit_stems', [])) != units.keys()):
        raise ValueError('Source approval does not cover these unique batch units')
    for relative, expected in recipe['protected_files'].items():
        if hashlib.sha256(project_path(args.project_directory, relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Accepted prayer changed before extension: '+relative)
    documents = build_documents(recipe, units)
    reject_existing_repeat_providers(args.project_directory, documents, recipe['order'])
    verify_existing_outputs(args.project_directory, documents, recipe['spine_templates'])
    for path in write_documents([(project_path(args.project_directory, relative), root)
                                 for relative, root in documents], validator=validate):
        print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
