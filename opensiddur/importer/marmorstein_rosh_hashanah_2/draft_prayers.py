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


def append_content(parent, content):
    """Keep a page boundary inside its verse without changing word spacing."""
    last_page = None
    for part in content:
        if isinstance(part, str):
            append_words(parent, part)
        elif set(part) == {'divine_name'}:
            element(parent, 'j:divineName', part['divine_name'])
        elif set(part) == {'large_letter'}:
            element(parent, 'c', part['large_letter'], rend='large')
        elif set(part) == {'page_break'}:
            page = part['page_break']
            if not isinstance(page['scan_page'], int) or page['scan_page'] < 1:
                raise ValueError('Page-break scan page must be positive')
            element(parent, 'pb', ed='1965', n=page['printed_page'],
                    facs=page_image_url(IDENTIFIER, page['scan_page']-1))
            last_page = page['scan_page']
        else:
            raise ValueError('Unsupported excerpt content')
    return last_page


def excerpt_header(unit, lang, witness):
    """Share source credits and volume-specific bibliography across draft modules."""
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
    element(bibl, 'biblScope', unit='pages', **{
        'from': witness['printed_page'],
        'to': witness.get('printed_page_end', witness['printed_page'])})
    return root


def append_prayer_content(parent, content, scan_page):
    """Keep Biblical scopes bounded independently of a prayer's alignment parts."""
    for item in content:
        if isinstance(item, dict) and set(item) == {'quotation'}:
            quote = item['quotation']
            if set(quote) != {'urn', 'chapter', 'verse', 'content'}:
                raise ValueError('Unsupported prayer quotation')
            if not quote['urn'].endswith('/'+str(quote['chapter'])+'/'+str(quote['verse'])):
                raise ValueError('Quotation chapter/verse disagrees with its URN')
            start_page = scan_page
            for piece in quote['content']:
                if isinstance(piece, str) and not piece.strip():
                    continue
                if isinstance(piece, dict) and set(piece) == {'page_break'}:
                    start_page = piece['page_break']['scan_page']
                    continue
                break
            element(parent, 'milestone', unit='chapter', n=quote['chapter'])
            element(parent, 'milestone', unit='verse', n=quote['verse'],
                    corresp=quote['urn'])
            span = element(parent, 'seg', source=quote['urn'],
                           facs=page_image_url(IDENTIFIER, start_page-1))
            last_page = append_content(span, quote['content'])
            if last_page is not None:
                scan_page = last_page
            element(parent, 'milestone', unit='verse')
            element(parent, 'milestone', unit='chapter')
        else:
            last_page = append_content(parent, [item])
            if last_page is not None:
                scan_page = last_page
    return scan_page


def prayer_document(unit, lang, witness):
    """Preserve source paragraphs while aligning reusable canonical prayer parts."""
    parts = witness['parts']
    if not parts:
        raise ValueError('A prayer needs at least one part')
    root = excerpt_header(unit, lang, witness)
    text = root.find(f'{{{TEI}}}text')
    text.clear()
    div = element(element(text, 'body'), 'div', corresp=unit['urn'])
    element(div, 'pb', ed='1965', n=witness['printed_page'],
            facs=page_image_url(IDENTIFIER, witness['scan_page']-1))
    paragraph = None
    seen_parts = set()
    current_page = witness['scan_page']
    for part in parts:
        urn = part.get('urn')
        if urn is None and not seen_parts:
            raise ValueError('A prayer must begin with a canonical part')
        if urn in seen_parts:
            raise ValueError('Duplicate prayer part')
        if urn is not None:
            seen_parts.add(urn)
        if paragraph is None or part.get('new_paragraph', False):
            paragraph = element(div, 'p')
            if witness.get('text_language'):
                paragraph.set(XML+'lang', witness['text_language'])
        if urn is not None:
            element(paragraph, 'milestone', unit='prayer-part', corresp=urn)
        current_page = append_prayer_content(paragraph, part['content'], current_page)
    element(paragraph, 'milestone', unit='prayer-part')
    return root


def excerpt_document(unit, lang, witness):
    """Use this volume's credits; put contextual rubrics in the later service spine."""
    if 'parts' in witness:
        return prayer_document(unit, lang, witness)
    is_range = 'verses' in witness
    verses = witness['verses'] if is_range else [{
        'verse': unit['verse'], 'verse_urn': unit['verse_urn'],
        'content': witness['content']}]
    if not verses:
        raise ValueError('An excerpt needs at least one verse')
    root = excerpt_header(unit, lang, witness)
    if 'citation' in witness:
        standoff = element(root, 'standOff', type='notes')
        # Place standoff before text, following the document model and existing books.
        root.remove(standoff)
        root.insert(1, standoff)
        note = element(standoff, 'note', type='citation', target=verses[0]['verse_urn'])
        element(element(note, 'p'), 'ref', witness['citation'], target=verses[0]['verse_urn'])
    text = root.find(f'{{{TEI}}}text')
    text.clear()
    attributes = {} if is_range or unit['urn'] == verses[0]['verse_urn'] else {'corresp': unit['urn']}
    div = element(element(text, 'body'), 'div', **attributes)
    element(div, 'pb', ed='1965', n=witness['printed_page'],
            facs=page_image_url(IDENTIFIER, witness['scan_page']-1))
    paragraph = element(div, 'p')
    # The verse is complete; the chapter is not. Only the exact verse supplies a
    # canonical witness. The chapter milestone retains its bibliographic context.
    element(paragraph, 'milestone', unit='chapter', n=unit['chapter'])
    seen_verses = set()
    current_page = witness['scan_page']
    for index, verse in enumerate(verses):
        if verse['verse_urn'] in seen_verses:
            raise ValueError('Duplicate excerpt verse')
        seen_verses.add(verse['verse_urn'])
        if index:
            append_words(paragraph, ' ')
        element(paragraph, 'milestone', unit='verse', n=verse['verse'],
                corresp=verse['verse_urn'])
        attributes = {'source': verse['verse_urn']}
        # A verse selected without its preceding page marker must retain
        # its own starting source, including after an earlier verse's break.
        start_page = current_page
        for part in verse['content']:
            if isinstance(part, str) and not part.strip():
                continue
            if isinstance(part, dict) and set(part) == {'page_break'}:
                start_page = part['page_break']['scan_page']
                continue
            break
        attributes['facs'] = page_image_url(IDENTIFIER, start_page-1)
        quotation = element(paragraph, 'seg', **attributes)
        last_page = append_content(quotation, verse['content'])
        if last_page is not None:
            current_page = last_page
    element(paragraph, 'milestone', unit='verse')
    element(paragraph, 'milestone', unit='chapter')
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument('--recipe', type=Path,
                        default=Path('batches/maariv_s5_s24/draft_units.json'))
    parser.add_argument('--draft', action='store_true', required=True)
    args = parser.parse_args(argv)
    source = args.source_root/BOOK
    recipe = json.loads((source/args.recipe).read_text(encoding='utf-8'))
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
