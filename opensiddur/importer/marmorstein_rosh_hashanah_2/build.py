"""Build only the opening documentary witnesses, explicitly as unaccepted drafts.

This startup builder writes day_two.xml and never replaces day one's index.xml
or reusable prayer witnesses. Full service assembly follows image adjudication.
"""
import argparse
import json
from pathlib import Path

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.scan.authoring import TEI, J, XML, element, append_words, write_documents
from opensiddur.importer.util.internet_archive import page_image_url
from opensiddur.importer.util.validation import validate
from . import BOOK, IDENTIFIER, PROJECTS, ROOT_URN, SOURCE_RECORD


def opening_document(lang, pages):
    project = PROJECTS[lang]
    root = etree.Element(f'{{{TEI}}}TEI', nsmap={'tei': TEI, 'j': J}, attrib={XML+'lang': lang})
    desc = element(element(root, 'teiHeader'), 'fileDesc')
    title = element(desc, 'titleStmt')
    element(title, 'title', 'Prayerbook for the New Year — second day', type='main')
    resp = element(title, 'respStmt')
    element(resp, 'resp', 'AI-assisted image transcription and JLPTEI markup')
    element(resp, 'name', 'Codex', ref='urn:x-opensiddur:contributor:opensiddur.org/codex')
    element(element(desc, 'editionStmt'), 'edition',
            'DRAFT opening front matter only. Independent reading, adjudication and '
            'encoding/export acceptance pending; see sources/marmorstein_rosh_hashanah_2/.')
    pub = element(desc, 'publicationStmt')
    element(element(pub, 'distributor'), 'ref', 'Open Siddur Project', target='https://opensiddur.org')
    element(pub, 'idno', ROOT_URN+'@'+project, type='urn')
    element(element(pub, 'availability', status='free'), 'licence', 'CC0 Public Domain Dedication',
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
    element(bibl, 'ref', 'Open Siddur source record', target=SOURCE_RECORD)
    element(bibl, 'note', 'Digital imaging and document preparation: Aharon N. Varady. '
            'The website republishes a preface from volume one; it is not added to this transcription.')
    element(bibl, 'ref', 'Edition project', target=f'/{project}/index')
    front = element(element(root, 'text'), 'front')
    for page in pages:
        if page['language'] != lang:
            continue
        element(front, 'pb', facs=page_image_url(IDENTIFIER, page['scan_page']-1))
        if page['kind'] == 'title':
            title_page = element(front, 'titlePage')
            title_page.set(XML+'id', f"day_two_s{page['scan_page']}")
            doc_title = element(title_page, 'docTitle')
            main_lines = 3 if lang == 'he' else 2
            for number, line in enumerate(page['lines'][:main_lines]):
                element(doc_title, 'titlePart', line, type='main' if number == 0 else 'sub')
            for line in page['lines'][main_lines:-2]:
                element(title_page, 'byline', line)
            imprint = element(title_page, 'docImprint')
            for number, line in enumerate(page['lines'][-2:]):
                if number:
                    element(imprint, 'lb')
                append_words(imprint, line)
        elif page['kind'] == 'copyright':
            paragraph = element(element(front, 'titlePage'), 'docImprint')
            for number, line in enumerate(page['lines']):
                if number:
                    element(paragraph, 'lb')
                append_words(paragraph, line)
        else:
            division = element(front, 'div')
            division.set(XML+'id', f"day_two_s{page['scan_page']}")
            for line in page['lines']:
                element(division, 'p', line)
    element(element(front.getparent(), 'body'), 'div', corresp=ROOT_URN)
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument('--draft', action='store_true', required=True,
                        help='Required: opening witnesses have not been accepted.')
    args = parser.parse_args(argv)
    reading = json.loads((args.source_root/BOOK/'primary_opening_s1_s4.json').read_text(encoding='utf-8'))
    documents = {lang: opening_document(lang, reading['pages']) for lang in PROJECTS}
    targets = [(args.project_directory/PROJECTS[lang]/'day_two.xml', root)
               for lang, root in documents.items()]
    for path in write_documents(targets, validator=validate):
        print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
