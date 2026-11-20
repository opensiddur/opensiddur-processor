"""Download source metadata and OCR candidates; never promote OCR to verified readings."""
import argparse
import json
import os
from pathlib import Path

from lxml import etree

from opensiddur.common.constants import OUTPUT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.scan.metadata import derive_pages
from opensiddur.importer.scan.pages import fetch
from opensiddur.importer.util.internet_archive import (
    connect, download_file, fetch_metadata, resolve_agent_model, write_if_changed,
)
from . import profile


def regenerate(book):
    ia = book.source_directory / 'ia'
    corrections_path = book.source_directory / 'page_corrections.json'
    corrections = json.loads(corrections_path.read_text()) if corrections_path.exists() else {}
    result = derive_pages(book.archive_identifier, (ia / 'scandata.xml').read_bytes(),
                          json.loads((ia / 'page_numbers.json').read_text()), corrections)
    write_if_changed(book.page_map, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def download(book, archive):
    metadata = fetch_metadata(archive, book.archive_identifier)
    ia = book.source_directory / 'ia'
    ia.mkdir(parents=True, exist_ok=True)
    write_if_changed(ia / 'metadata.json', metadata.model_dump_json(indent=2) + '\n')
    for suffix, destination in [('_scandata.xml', ia / 'scandata.xml'),
                                ('_djvu.xml', book.cache_directory / 'ocr.xml')]:
        item = metadata.find_suffix(suffix)
        if item is None:
            raise ValueError(f'Archive lacks {suffix}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        download_file(archive, book.archive_identifier, item, destination)
    numbers = metadata.find_suffix('_page_numbers.json')
    if numbers is not None:
        download_file(archive, book.archive_identifier, numbers, ia / 'page_numbers.json')
    else:
        scan = etree.parse(str(ia / 'scandata.xml'))
        candidates = {'pages': [{'leafNum': int(p.get('leafNum')), 'pageNumber': p.findtext('pageNumber')}
                                 for p in scan.findall('.//pageData/page')]}
        write_if_changed(ia / 'page_numbers.json', json.dumps(candidates, indent=2) + '\n')
    objects = etree.parse(str(book.cache_directory / 'ocr.xml')).findall('.//OBJECT')
    result = regenerate(book)
    if len(objects) != len(result['pages']):
        raise ValueError('OCR and scan inventories differ; inspect scan identity before proceeding')
    ocr = ia / 'ocr'
    ocr.mkdir(exist_ok=True)
    for page, obj in zip(result['pages'], objects):
        lines = [' '.join(w.text or '' for w in line.findall('WORD')) for line in obj.findall('.//LINE')]
        write_if_changed(ocr / f"s{page['scan_page']}.txt", '\n'.join(lines) + '\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--output-root', type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument('--contact-email', default=os.getenv('OPENSIDDUR_CONTACT_EMAIL'))
    parser.add_argument('--agent-model', default=resolve_agent_model())
    parser.add_argument('--regenerate', action='store_true')
    parser.add_argument('--pages', nargs='*', default=[], help='Unique scan designations, e.g. s60 s61')
    args = parser.parse_args(argv)
    book = profile(args.source_root, args.output_root)
    if args.regenerate:
        result = regenerate(book)
    else:
        if not args.contact_email:
            parser.error('--contact-email or OPENSIDDUR_CONTACT_EMAIL is required')
        archive = connect(args.contact_email, model=args.agent_model)
        result = download(book, archive)
        for designation in args.pages:
            fetch(book, designation, archive=archive)
    print(f"{len(result['pages'])} scan leaves inventoried; OCR remains unverified")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
