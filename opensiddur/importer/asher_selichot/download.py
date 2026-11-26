"""Download Asher evidence and derive a page map from image-verified corrections."""

from opensiddur.importer.scan.metadata import derive_pages

import argparse
import json
import os
from pathlib import Path
from lxml import etree
from opensiddur.common.constants import SOURCETEXTS_ROOT, OUTPUT_DIRECTORY
from opensiddur.importer.scan.pages import BookProfile
from opensiddur.importer.util.internet_archive import (connect, download_file, fetch_metadata,
    page_image_url, resolve_agent_model, write_if_changed)


def regenerate(profile):
    ia = profile.source_directory / 'ia'
    corrections = json.loads((profile.source_directory / 'page_corrections.json').read_text(encoding="utf-8"))
    result = derive_pages(profile.archive_identifier, (ia / 'scandata.xml').read_bytes(),
                          json.loads((ia / 'page_numbers.json').read_text(encoding="utf-8")), corrections)
    write_if_changed(profile.page_map, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def download(profile, archive):
    metadata = fetch_metadata(archive, profile.archive_identifier)
    ia = profile.source_directory / 'ia'
    ia.mkdir(parents=True, exist_ok=True)
    write_if_changed(ia / 'metadata.json', metadata.model_dump_json(indent=2) + '\n')
    for suffix, name in [('_scandata.xml', 'scandata.xml'), ('_page_numbers.json', 'page_numbers.json')]:
        file = metadata.find_suffix(suffix)
        if file is None:
            raise ValueError(f'Archive lacks {suffix}')
        download_file(archive, profile.archive_identifier, file, ia / name)
    djvu = metadata.find_suffix('_djvu.xml')
    if djvu is None:
        raise ValueError('Archive lacks per-page OCR')
    cache = profile.cache_directory / 'ocr.xml'
    cache.parent.mkdir(parents=True, exist_ok=True)
    download_file(archive, profile.archive_identifier, djvu, cache)
    root = etree.parse(str(cache))
    objects = root.findall('.//OBJECT')
    for leaf in [24, 26, 32]:
        obj = objects[leaf]
        lines = [' '.join(w.text or '' for w in line.findall('WORD')) for line in obj.findall('.//LINE')]
        destination = ia / 'ocr' / f's{leaf + 1}.txt'
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_if_changed(destination, '\n'.join(lines) + '\n')
    return regenerate(profile)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--output-root', type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument('--contact-email', default=os.getenv('OPENSIDDUR_CONTACT_EMAIL'))
    parser.add_argument('--regenerate', action='store_true')
    args = parser.parse_args(argv)
    profile = BookProfile.for_book('asher_selichot', args.source_root, args.output_root)
    if args.regenerate:
        regenerate(profile)
    else:
        if not args.contact_email:
            parser.error('--contact-email or OPENSIDDUR_CONTACT_EMAIL is required')
        download(profile, connect(args.contact_email, model=resolve_agent_model()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
