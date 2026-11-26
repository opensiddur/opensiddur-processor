"""Build only the opening documentary witnesses, explicitly as unaccepted drafts.

This builder writes a volume-specific index.xml. It never writes
day-one projects. Full service assembly follows image adjudication.
"""
import argparse
import hashlib
import json
from pathlib import Path

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.scan.authoring import (
    TEI,
    XML,
    J,
    append_words,
    conditional_scope,
    element,
    write_documents,
)
from opensiddur.importer.util.internet_archive import page_image_url
from opensiddur.importer.util.validation import validate

from . import BOOK, IDENTIFIER, PROJECTS, ROOT_URN, SOURCE_RECORD


def source_lines(parent, lines, indices):
    for number, index in enumerate(indices):
        if number:
            element(parent, 'lb')
        append_words(parent, lines[index])


def opening_document(lang, pages, layouts):
    project = PROJECTS[lang]
    root = etree.Element(f'{{{TEI}}}TEI', nsmap={'tei': TEI, 'j': J}, attrib={XML+'lang': lang})
    desc = element(element(root, 'teiHeader'), 'fileDesc')
    title = element(desc, 'titleStmt')
    element(title, 'title', 'Prayerbook for the New Year — second day', type='main')
    for key, description in [('trc', 'AI-assisted image transcription'),
                             ('mrk', 'JLPTEI markup')]:
        resp = element(title, 'respStmt')
        element(resp, 'resp', description, key=key)
        element(resp, 'name', 'Codex', ref='urn:x-opensiddur:contributor:opensiddur.org/codex')
    element(element(desc, 'editionStmt'), 'edition',
            'DRAFT volume: opening front matter only. Per-scan acceptance and review '
            'evidence are recorded in sources/marmorstein_rosh_hashanah_2/batches/.')
    pub = element(desc, 'publicationStmt')
    element(element(pub, 'distributor'), 'ref', 'Open Siddur Project', target='https://opensiddur.org')
    element(pub, 'idno', ROOT_URN+'@'+project, type='urn')
    element(element(pub, 'availability', status='free'), 'licence', 'Creative Commons Zero (Public Domain Dedication)',
            target='http://www.creativecommons.org/publicdomain/zero/1.0')
    source = element(desc, 'sourceDesc')
    bibl = element(source, 'bibl')
    bibl.set(XML+'id', 'day_two_source_bibl')
    element(bibl, 'title', 'Prayerbook for the New Year [Second Day]')
    element(bibl, 'editor', 'Wolf Heidenheim', role='arranger')
    element(bibl, 'editor', 'Jenny Marmorstein', role='translator')
    element(bibl, 'publisher', 'Victor Goldschmidt Publishers')
    element(bibl, 'pubPlace', 'Basle')
    element(bibl, 'date', '1965', when='1965')
    element(bibl, 'idno', f'https://archive.org/details/{IDENTIFIER}', type='url')
    element(bibl, 'idno', IDENTIFIER, type='internet_archive')
    element(bibl, 'date', '2026-11-25', type='accessed', when='2026-11-25')
    element(bibl, 'ref', 'Open Siddur source record', target=SOURCE_RECORD)
    element(bibl, 'note', 'Digital imaging and document preparation: Aharon N. Varady.')
    element(bibl, 'note', 'WH transcribes the cover monogram; the adjacent Hebrew text is its legend. '
            'The website preface from volume one is not part of this source transcription.', type='encoding')
    front = element(element(root, 'text'), 'front')
    for page in pages:
        # Paratext belongs to the physical volume, including its other-language
        # title pages. Parallel assembly does not supply a counterpart's front.
        element(front, 'pb', facs=page_image_url(IDENTIFIER, page['scan_page']-1))
        gate = f"day_two_front_s{page['scan_page']}"
        conditional_scope(front, gate, True, fs_type='opensiddur:paratext', feature='title-page')
        if page['kind'] == 'title':
            title_page = element(front, 'titlePage')
            title_page.set(XML+'id', f"day_two_s{page['scan_page']}")
            title_page.set(XML+'lang', page['language'])
            doc_title = element(title_page, 'docTitle')
            layout = layouts[str(page['scan_page'])]
            groups = [layout['main'], layout.get('sub', []), *layout['bylines'], layout['imprint']]
            if [index for group in groups for index in group] != list(range(len(page['lines']))):
                raise ValueError('Title layout must cover each printed line once, in source order')
            source_lines(element(doc_title, 'titlePart', type='main'), page['lines'], layout['main'])
            if layout.get('sub'):
                source_lines(element(doc_title, 'titlePart', type='sub'), page['lines'], layout['sub'])
            for indices in layout['bylines']:
                source_lines(element(title_page, 'byline'), page['lines'], indices)
            source_lines(element(title_page, 'docImprint'), page['lines'], layout['imprint'])
        elif page['kind'] == 'copyright':
            title_page = element(front, 'titlePage')
            title_page.set(XML+'lang', page['language'])
            title_page.set(XML+'id', f"day_two_s{page['scan_page']}")
            paragraph = element(title_page, 'docImprint')
            for number, line in enumerate(page['lines']):
                if number:
                    element(paragraph, 'lb')
                append_words(paragraph, line)
        else:
            division = element(front, 'div')
            division.set(XML+'id', f"day_two_s{page['scan_page']}")
            division.set(XML+'lang', page['language'])
            for number, line in enumerate(page['lines']):
                paragraph = element(division, 'p')
                language = page.get('line_languages', {}).get(str(number), page['language'])
                if language != page['language']:
                    paragraph = element(paragraph, 'foreign')
                    paragraph.set(XML+'lang', language)
                paragraph.text = line
        element(front, 'j:endConditional', target='#'+gate)
    element(element(front.getparent(), 'body'), 'div', corresp=ROOT_URN)
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument('--draft', action='store_true', required=True,
                        help='Required: opening witnesses have not been accepted.')
    args = parser.parse_args(argv)
    source = args.source_root/BOOK
    reading_path = source/'front_resolved.json'
    reading = json.loads(reading_path.read_text(encoding='utf-8'))
    checklist = json.loads((source/'batches/front_matter_s1_s4/checklist.json').read_text(encoding='utf-8'))
    if hashlib.sha256(reading_path.read_bytes()).hexdigest() != checklist['gates']['adjudication']['resolved_sha256']:
        raise ValueError('Stale front-matter adjudication hash')
    layouts = json.loads((source/'front_layout.json').read_text(encoding='utf-8'))
    documents = {lang: opening_document(lang, reading['pages'], layouts) for lang in PROJECTS}
    targets = [(args.project_directory/PROJECTS[lang]/'index.xml', root)
               for lang, root in documents.items()]
    for path in write_documents(targets, validator=validate):
        print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
