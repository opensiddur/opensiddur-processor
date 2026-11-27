"""Render source-bound morning witnesses with volume-two bibliography and scans.

The recipe owns identities and interpretations. Rendering does not approve a
reading or add this incomplete service to the volume's accepted coverage.
"""
import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.marmorstein_rosh_hashanah_1.build import unit_document
from opensiddur.importer.scan.authoring import (
    TEI,
    apply_corrections,
    element,
    write_documents,
)
from opensiddur.importer.util.internet_archive import page_image_url
from opensiddur.importer.util.validation import validate

from . import BOOK, IDENTIFIER, PROJECTS
from .build import opening_document


def witness_header(lang, project, title, urn, *, draft):
    """Use this physical volume's credits and index, never a donor's header."""
    if project != PROJECTS[lang]:
        raise ValueError('Morning witness project disagrees with its language')
    root = opening_document(lang, [], {})
    desc = root.find(f'{{{TEI}}}teiHeader/{{{TEI}}}fileDesc')
    desc.find(f'{{{TEI}}}titleStmt/{{{TEI}}}title').text = title
    desc.find(f'{{{TEI}}}publicationStmt/{{{TEI}}}idno').text = urn+'@'+project
    desc.find(f'{{{TEI}}}editionStmt/{{{TEI}}}edition').text = (
        ('Draft source witness. ' if draft else 'JLPTEI source witness. ')+
        'Exact review scope and complete-scan acceptance are recorded in '
        'sources/marmorstein_rosh_hashanah_2/batches/.')
    source = desc.find(f'{{{TEI}}}sourceDesc')
    source.clear()
    element(element(source, 'bibl'), 'ptr', target=f'/{project}/index#day_two_source_bibl')
    text = root.find(f'{{{TEI}}}text')
    text.clear()
    return root, element(text, 'body')


def range_source_pages(unit, lang):
    """Bind each independently selectable identity to its first actual fragment."""
    pages = {}

    def bind(value, page, *, segment=False):
        for key in ('corresp', 'chapter_corresp', 'source_reference_corresp'):
            if value.get(key):
                pages.setdefault(value[key], page)
        # Top-level segment rendering emits this fallback. Nested quotation
        # rendering never does: a half-verse's parent verse is context only.
        if (segment and value.get('source_reference')
                and not value.get('source_reference_corresp')):
            pages.setdefault(value['source_reference'], page)
        part = value.get('source_reference_part')
        if part:
            pages.setdefault(part['corresp'], page)

    def visit(value, page):
        if isinstance(value, dict):
            if value.get('scan'):
                page = value
            for key, child in value.items():
                if key == 'quotations':
                    for quotation in child:
                        bind(quotation, page)
                visit(child, page)
        elif isinstance(value, list):
            for child in value:
                visit(child, page)

    for segment in unit['languages'][lang]:
        page = segment['fragments'][0]
        bind(segment, page, segment=True)
        visit(segment, page)
    for instruction in unit.get('instructions', []):
        if lang in instruction.get('witnesses', [lang]):
            visit(instruction, unit['languages'][lang][0]['fragments'][0])
    return pages


def retain_range_provenance(root, pages):
    """Keep provenance inside a selected milestone range, preserving text tails."""
    for marker in list(root.iter(f'{{{TEI}}}milestone')):
        if marker.get('corresp') not in pages:
            continue
        source = pages[marker.get('corresp')]
        facs = page_image_url(IDENTIFIER, int(source['scan'][1:])-1, size='')
        following = marker.getnext()
        if (following is not None and following.tag == f'{{{TEI}}}pb'
                and following.get('facs') == facs and not (marker.tail or '').strip()):
            continue
        attributes = {'ed': '1965', 'facs': facs}
        if source.get('printed_page') is not None:
            attributes['n'] = source['printed_page']
        page = element(marker.getparent(), 'pb', **attributes)
        marker.addnext(page)
        page.tail, marker.tail = marker.tail, None
    return root


def witness_document(unit, lang, *, draft=True):
    """Render actual words; explicit recipes decide reuse, scopes and variants."""
    if unit.get('reuse', {}).get(lang) or any(
            segment.get(key) for segment in unit['languages'][lang]
            for key in ('canonical', 'transclude', 'repeat')):
        raise ValueError('Literal morning witnesses must retain their own source words')
    unit = deepcopy(unit)
    unit.setdefault('opening_page', {})[lang] = True
    root = unit_document(unit, lang, draft, projects=PROJECTS,
                         identifier=IDENTIFIER, document_factory=witness_header)
    return retain_range_provenance(root, range_source_pages(unit, lang))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument('--recipe', type=Path,
                        default=Path('batches/morning_s25_s45/morning_units.json'))
    parser.add_argument('--draft', action='store_true', required=True)
    args = parser.parse_args(argv)
    source = args.source_root/BOOK
    recipe = json.loads((source/args.recipe).read_text(encoding='utf-8'))
    if not recipe['input_sha256']:
        raise ValueError('Morning witnesses must bind their source inputs')
    if not {recipe['readings'], recipe['source_approval']} <= recipe['input_sha256'].keys():
        raise ValueError('Morning recipe must bind both readings and source approval')
    for relative, expected in recipe['input_sha256'].items():
        if hashlib.sha256((source/relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Stale morning source input: '+relative)
    approval = json.loads((source/recipe['source_approval']).read_text(encoding='utf-8'))
    if (approval['status'] != 'approved_source_only' or
            recipe['input_sha256'].get(recipe['readings']) != approval['working_readings_sha256']):
        raise ValueError('Morning recipe lacks current source approval')
    protected = set(recipe['protected_files'])
    documents, seen = [], set()
    for unit in recipe['units']:
        stem = unit['stem']
        if (not re.fullmatch(r'[a-z]+(?:_[a-z0-9]+)*', stem)
                or stem == 'index' or stem in seen):
            raise ValueError('Unsafe or repeated morning file stem')
        seen.add(stem)
        for lang in unit['languages']:
            relative = PROJECTS[lang]+'/'+stem+'.xml'
            if relative in protected:
                raise ValueError('Morning recipe would overwrite an accepted file: '+relative)
            documents.append((args.project_directory/relative,
                              witness_document(unit, lang, draft=True)))
    apply_corrections({str(path.relative_to(args.project_directory)): root
                       for path, root in documents}, recipe.get('corrections', []))
    for path in write_documents(documents, validator=validate):
        print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
