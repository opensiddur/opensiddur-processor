"""Continue existing Pesuqei deZimrah with source-approved closing witnesses.

The source recipe distinguishes documentary printings from recitation calls.
No source or export acceptance is inferred by this renderer.
"""
import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.exporter.urn import split_range
from opensiddur.importer.marmorstein_rosh_hashanah_1.build import rubric_words
from opensiddur.importer.scan.authoring import (
    TEI,
    XML,
    apply_corrections,
    element,
    write_documents,
)
from opensiddur.importer.util.validation import validate

from . import BOOK, EXPANDED, PROJECTS
from .morning_shared import approved_readings, declaration, safe_stem
from .morning_witnesses import witness_document
from .pesuqei import (
    SERVICE_URN,
    call,
    guard_translation,
    project_path,
    reject_existing_repeat_providers,
    repeat_features,
    require_edition_parallel_profiles,
    translation_feature,
    verify_existing_outputs,
)

T = '{'+TEI+'}'
BATCH = 'pesuqei_close_s64_s81'


def append_sequence(template, units, order, *, lang, expanded=False):
    """Append within the accepted section, retaining all preceding service words."""
    root = deepcopy(template)
    edition = root.find('.//'+T+'editionStmt/'+T+'edition')
    if edition is not None:
        edition.text = ('JLPTEI service arrangement. Exact review scope and complete-scan '
                        'acceptance are recorded in sources/marmorstein_rosh_hashanah_2/batches/.')
    query = ('.//tei:div[@xml:id="second_day_pesuqei_dezimrah"]' if expanded
             else './/tei:div[@corresp=$urn]')
    parents = root.xpath(query, namespaces={'tei': TEI, 'xml': XML[1:-1]},
                         urn=SERVICE_URN)
    if len(parents) != 1:
        raise ValueError('The existing Pesuqei deZimrah section must be unique')
    section = parents[0]
    if expanded and not section.xpath('ancestor::tei:div[@xml:id="morning_blessings"]',
                                     namespaces={'tei': TEI, 'xml': XML[1:-1]}):
        raise ValueError('Expanded continuation must remain beneath Shacharit')
    original_ids = {n.get(XML+'id') for n in root.iter() if n.get(XML+'id')}
    identifier = 'closing_pesuqei_printed_translations'
    if identifier in original_ids:
        raise ValueError('Closing sequence is already present')
    values = repeat_features(order)
    section = element(section, 'div')
    section.set(XML+'id', identifier)
    original_ids.add(identifier)
    if values:
        if identifier+'_settings' in original_ids:
            raise ValueError('Closing settings identity already exists')
        original_ids.add(identifier+'_settings')
        declaration(section, identifier+'_settings', values)
    def unique(parent, identity):
        if identity in original_ids:
            raise ValueError('Repeated structural identity: '+identity)
        original_ids.add(identity)
        node = element(parent, 'div')
        node.set(XML+'id', identity)
        return node
    for item in order:
        unit = units[item['key']]
        if item.get('ranges'):
            raise ValueError('Closing continuation does not accept range recipes')
        if (expanded and 'en' not in unit['languages'] and not
                (item.get('hebrew_only_repeat') or item.get('untranslated'))):
            raise ValueError('Untranslated expanded call needs an explicit policy')
        if not expanded and lang not in unit['languages']:
            continue
        seen_instructions = set()
        for instruction in item.get('instructions', []):
            if set(instruction)-{'text', 'language', 'witnesses', 'facs', 'language_spans'}:
                raise ValueError('Unsupported instruction fields')
            if not instruction['witnesses']:
                raise ValueError('Instruction needs a printed witness')
            if not set(instruction['witnesses']) <= set(unit['languages']):
                raise ValueError('Instruction witnesses require matching source content')
            signature = (instruction['language'], ' '.join(instruction['text'].split()),
                         json.dumps(instruction.get('language_spans', []), sort_keys=True))
            if expanded and signature in seen_instructions:
                continue
            seen_instructions.add(signature)
            if not expanded and lang not in instruction['witnesses']:
                continue
            note = element(section, 'note', type='instruction', facs=instruction['facs'])
            note.set(XML+'lang', instruction['language'])
            rubric_words(note, instruction, instruction['language'])
        repeat = item.get('hebrew_only_repeat', False)
        if repeat and 'en' in unit['languages']:
            raise ValueError('A documentary repeat must be explicitly Hebrew-only')
        scope = 'closing_pesuqei_'+safe_stem(item['key'])+'_translation'
        parent = unique(section, 'closing_pesuqei_'+safe_stem(item['key'])) if repeat else section
        if repeat:
            if item.get('expanded_calls'):
                raise ValueError('A Hebrew-only repeat requires exactly its canonical call')
            if scope in original_ids:
                raise ValueError('Repeated scope identity already exists')
            original_ids.add(scope)
            declaration(parent, scope,
                        {translation_feature(item['expanded_target']): False})
        targets = (item.get('expanded_calls', [item['expanded_target']]) if expanded
                   else [item.get('documentary_target', unit.get('start', unit['urn']))])
        if not targets:
            raise ValueError('Expanded occurrences require nonempty targets')
        for index, target in enumerate(targets):
            destination = (unique(parent, 'closing_pesuqei_'+safe_stem(item['key'])+
                                  '_occurrence_'+str(index+1))
                           if expanded and len(targets)>1 else parent)
            call(destination, target, project=None if expanded else PROJECTS[lang])
        if repeat:
            element(parent, 'j:endDeclare', target='#'+scope)
    if values:
        element(section, 'j:endDeclare', target='#'+identifier+'_settings')
    return root


def build_documents(recipe, units):
    order = recipe['order']
    keys = [item['key'] for item in order]
    if len(set(keys)) != len(keys) or set(keys) != set(units):
        raise ValueError('Unique source units and documentary order disagree')
    documents = [(PROJECTS[lang]+'/'+safe_stem(unit['stem'])+'.xml',
                  witness_document(unit, lang))
                 for unit in units.values() for lang in unit['languages']]
    apply_corrections(dict(documents), recipe.get('corrections', []))
    for item in order:
        if not item.get('hebrew_only_repeat'):
            continue
        target = item['expanded_target']
        translation_feature(target)
        matches = [(root, n) for path, root in documents
                   if path.startswith(PROJECTS['en']+'/')
                   for n in root.iter() if n.get('corresp') == target]
        if len(matches) != 1 or matches[0][1].tag != T+'milestone':
            raise ValueError('Repeated verse needs exactly one guardable English provider')
        guard_translation(matches[0][0], target)
    spines = {project+'/pesuqei_service.xml': (lang, False)
              for lang, project in PROJECTS.items()}
    spines[EXPANDED+'/second_day_morning.xml'] = ('he', True)
    templates = recipe['spine_templates']
    if len(templates) != len(spines) or {i['path'] for i in templates} != set(spines):
        raise ValueError('Recipe must extend exactly the three existing Pesuqei spines')
    for item in templates:
        raw = item['xml'].encode('utf-8')
        if (hashlib.sha256(raw).hexdigest() != item['sha256'] or
                not re.fullmatch('[0-9a-f]{40}', item.get('baseline_commit', ''))):
            raise ValueError('Changed accepted service template')
        template = etree.fromstring(raw)
        lang, expanded = spines[item['path']]
        idno = template.find('.//'+T+'publicationStmt/'+T+'idno[@type="urn"]')
        if (template.get(XML+'lang') != lang or idno is None or
                not (idno.text or '').endswith('@'+item['path'].split('/')[0])):
            raise ValueError('Service template publication or language disagrees with path')
        documents.append((item['path'], append_sequence(template, units, order,
                          lang=lang, expanded=expanded)))
    paths = [p for p, _ in documents]
    if len(set(paths)) != len(paths) or set(paths) & set(recipe['protected_files']):
        raise ValueError('Repeated output or protected accepted witness')
    for item in order:
        allowed = {'key', 'expanded_target', 'documentary_target', 'expanded_calls',
                   'hebrew_only_repeat', 'untranslated', 'instructions'}
        if set(item)-allowed:
            raise ValueError('Unsupported closing order fields')
        unit = units[item['key']]
        if item.get('untranslated') and (item.get('expanded_calls') or item.get('hebrew_only_repeat')):
            raise ValueError('Untranslated units require one explicit non-repeat call')
        actual = set()
        actual.update(n.get('corresp') for path, root in documents
                      if path == PROJECTS['he']+'/'+safe_stem(unit['stem'])+'.xml'
                      for n in root.iter() if n.get('corresp'))
        if item.get('untranslated') and 'en' in unit['languages']:
            raise ValueError('Untranslated policy requires a Hebrew-only source unit')
        documentary = item.get('documentary_target', unit.get('start', unit['urn']))
        for language in unit['languages']:
            available = {n.get('corresp') for path, root in documents
                         if path == PROJECTS[language]+'/'+safe_stem(unit['stem'])+'.xml'
                         for n in root.iter() if n.get('corresp')}
            if not set(split_range(documentary) or (documentary,)) <= available:
                raise ValueError('Documentary call lacks source witness boundaries')
        for target in item.get('expanded_calls', [item['expanded_target']]):
            endpoints = set(split_range(target) or (target,))
            if item.get('hebrew_only_repeat'):
                if unit.get('repeat_reference') != target:
                    raise ValueError('Repeated call disagrees with its source reference')
            elif not endpoints <= actual:
                raise ValueError('Expanded call is outside its source unit')
            if 'en' in unit['languages']:
                en_actual = {n.get('corresp') for path, root in documents
                             if path == PROJECTS['en']+'/'+safe_stem(unit['stem'])+'.xml'
                             for n in root.iter() if n.get('corresp')}
                if not endpoints <= en_actual:
                    raise ValueError('Expanded call lacks matching English boundaries')
    return documents


def check_existing_providers(directory, documents, recipe):
    """Prevent a new witness from replacing prior canonical or untranslated scopes."""
    regenerated = {path for path, _ in documents}
    untranslated = {item['expanded_target'] for item in recipe['order']
                    if item.get('untranslated')}
    repeats = {item['expanded_target'] for item in recipe['order']
               if item.get('hebrew_only_repeat')}
    earlier = set(recipe['earlier_untranslated_targets'])
    for target in earlier | untranslated:
        translation_feature(target)  # Only a single, explicit canonical verse is supported.
    old_by_language = {}
    for lang, project in PROJECTS.items():
        old_by_language[lang] = {n.get('corresp')
                                for path in (directory/project).glob('*.xml')
                                if str(path.relative_to(directory)) not in regenerated
                                for n in etree.parse(str(path)).iter() if n.get('corresp')}
    # Whole verses never resolve through their chapter. Check actual providers,
    # not lexical ancestors: an earlier verse and a new chapter may coexist.
    for language, project in PROJECTS.items():
        owners = {}
        for path, root in documents:
            if not path.startswith(project+'/') or path.endswith('/pesuqei_service.xml'):
                continue
            for urn in {n.get('corresp') for n in root.iter() if n.get('corresp')}:
                if urn in owners and owners[urn] != path:
                    raise ValueError('Two new witnesses claim one identity: '+urn)
                owners[urn] = path
        current = {n.get('corresp') for path, root in documents
                   if path.startswith(project+'/') and not path.endswith('/pesuqei_service.xml')
                   for n in root.iter() if n.get('corresp')}
        for path in (directory/project).glob('*.xml'):
            if str(path.relative_to(directory)) in regenerated:
                continue
            existing = {n.get('corresp') for n in etree.parse(str(path)).iter()}
            if language == 'en' and (untranslated | repeats) & existing:
                raise ValueError('Existing English provider would fill an untranslated call')
            if current & existing:
                raise ValueError('New witness duplicates an accepted provider: '+str(path))
        if language == 'en' and current & (old_by_language['he']-old_by_language['en']):
            raise ValueError('New English witness would fill an earlier Hebrew-only occurrence')
        if language == 'en' and current & (earlier | untranslated):
            raise ValueError('New English witness would fill an earlier translation gap')


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
        raise ValueError('Current independent source and structure approval required')
    earlier_path = batch.parent/'pesuqei_s46_s63'/'pesuqei_units.json'
    if hashlib.sha256(earlier_path.read_bytes()).hexdigest() != recipe['earlier_recipe_sha256']:
        raise ValueError('Earlier accepted translation-gap recipe changed')
    earlier_recipe = json.loads(earlier_path.read_text(encoding='utf-8'))
    gaps = {item['expanded_target'] for item in earlier_recipe['order']
            if item.get('hebrew_only_repeat')}
    gaps.update(span['target'] for item in earlier_recipe['order']
                for span in item.get('ranges', []) if 'en' not in span['witnesses'])
    if gaps != set(recipe['earlier_untranslated_targets']):
        raise ValueError('Earlier translation-gap inventory is incomplete')
    require_edition_parallel_profiles(args.project_directory.parent/'settings',
                                      recipe['settings_sha256'])
    readings = approved_readings(batch, recipe)
    units = {u['stem']: u for u in readings['units']}
    approval = json.loads((batch/'source_approval.json').read_text(encoding='utf-8'))
    if (len(units) != len(readings['units']) or approval.get('batch') != BATCH or
            approval.get('scan_pages') != list(range(64, 82)) or
            set(approval.get('unit_stems', [])) != set(units)):
        raise ValueError('Source approval does not cover all batch pages and units')
    for relative, expected in recipe['protected_files'].items():
        if hashlib.sha256(project_path(args.project_directory, relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Accepted witness changed before extension: '+relative)
    for item in recipe['spine_templates']:
        if not project_path(args.project_directory, item['path']).is_file():
            raise ValueError('Accepted continuation spine is missing')
    documents = build_documents(recipe, units)
    check_existing_providers(args.project_directory, documents, recipe)
    reject_existing_repeat_providers(args.project_directory, documents, recipe['order'])
    verify_existing_outputs(args.project_directory, documents, recipe['spine_templates'])
    for path in write_documents([(project_path(args.project_directory, name), root)
                                 for name, root in documents], validator=validate):
        print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
