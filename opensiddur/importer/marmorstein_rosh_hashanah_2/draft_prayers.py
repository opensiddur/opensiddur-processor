"""Generate explicitly provisional prayer excerpts without changing the book index.

The versioned recipe binds its source inputs by hash. Missing translations produce
no counterpart; an excerpt never advertises a complete Biblical chapter.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.scan.authoring import TEI, XML, append_words, element, write_documents
from opensiddur.importer.util.internet_archive import page_image_url
from opensiddur.importer.util.validation import validate
from . import BOOK, IDENTIFIER, PROJECTS
from .build import opening_document


def excerpt_document(unit, lang, witness):
    """Use this volume's credits; put contextual rubrics in the later service spine."""
    root = opening_document(lang, [], {})
    desc = root.find(f'{{{TEI}}}teiHeader/{{{TEI}}}fileDesc')
    desc.find(f'{{{TEI}}}titleStmt/{{{TEI}}}title').text = unit['titles'][lang]
    desc.find(f'{{{TEI}}}editionStmt/{{{TEI}}}edition').text = (
        'DRAFT excerpt: batch transcription, encoding and presentation acceptance '
        'pending. Evidence: sources/marmorstein_rosh_hashanah_2/batches/.')
    desc.find(f'{{{TEI}}}publicationStmt/{{{TEI}}}idno').text = unit['urn']+'@'+PROJECTS[lang]
    source = desc.find(f'{{{TEI}}}sourceDesc')
    source.clear()
    bibl = element(source, 'bibl')
    element(bibl, 'ptr', target=f'/{PROJECTS[lang]}/index#day_two_source_bibl')
    element(bibl, 'biblScope', unit='pages', **{'from': witness['printed_page'], 'to': witness['printed_page']})
    standoff = element(root, 'standOff', type='notes')
    # Place standoff before text, following the document model and existing books.
    root.remove(standoff)
    root.insert(1, standoff)
    note = element(standoff, 'note', type='citation', target=unit['verse_urn'])
    element(element(note, 'p'), 'ref', witness['citation'], target=unit['verse_urn'])
    text = root.find(f'{{{TEI}}}text')
    text.clear()
    div = element(element(text, 'body'), 'div', corresp=unit['urn'])
    element(div, 'pb', ed='1965', n=witness['printed_page'],
            facs=page_image_url(IDENTIFIER, witness['scan_page']-1))
    paragraph = element(div, 'p')
    # The verse is complete; the chapter is not. Only the exact verse supplies a
    # canonical witness. The chapter milestone retains its bibliographic context.
    element(paragraph, 'milestone', unit='chapter', n=unit['chapter'])
    element(paragraph, 'milestone', unit='verse', n=unit['verse'], corresp=unit['verse_urn'])
    quotation = element(paragraph, 'seg', source=unit['verse_urn'])
    for part in witness['content']:
        if isinstance(part, str):
            append_words(quotation, part)
        elif set(part) == {'divine_name'}:
            element(quotation, 'j:divineName', part['divine_name'])
        elif set(part) == {'large_letter'}:
            element(quotation, 'c', part['large_letter'], rend='large')
        else:
            raise ValueError('Unsupported excerpt content')
    element(paragraph, 'milestone', unit='verse')
    element(paragraph, 'milestone', unit='chapter')
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument('--draft', action='store_true', required=True)
    args = parser.parse_args(argv)
    source = args.source_root/BOOK
    recipe = json.loads((source/'batches/maariv_s5_s24/draft_units.json').read_text(encoding='utf-8'))
    if not recipe['input_sha256']:
        raise ValueError('Draft excerpts must bind at least one source input')
    for relative, expected in recipe['input_sha256'].items():
        path = source/relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Stale excerpt input: '+relative)
    targets, obsolete, seen = [], [], set()
    for unit in recipe['units']:
        if not re.fullmatch(r'[a-z]+(?:_[a-z0-9]+)*', unit['file']) or unit['file'] == 'index':
            raise ValueError('Draft excerpts must have a safe non-index file stem')
        if unit['file'] in seen:
            raise ValueError('Duplicate draft excerpt file stem')
        seen.add(unit['file'])
        for lang in PROJECTS:
            witness = unit.get(lang)
            path = args.project_directory/PROJECTS[lang]/(unit['file']+'.xml')
            if witness is None:
                obsolete.append(path)
            else:
                targets.append((path,
                                excerpt_document(unit, lang, witness)))
    for path in write_documents(targets, validator=validate, obsolete_paths=obsolete):
        print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
