"""Fetch and enlarge leaves using explicit book identity and verified page maps.

A printed label is not a primary key: bilingual books may repeat it on both sides.
Images are cached outside repositories, by scan identity, independently of labels.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

from opensiddur.common.constants import OUTPUT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.util.internet_archive import (
    connect,
    http_get,
    page_image_url,
    resolve_agent_model,
)


class ScanError(ValueError):
    """A map, designation, or image is missing or ambiguous."""


@dataclass(frozen=True)
class BookProfile:
    name: str
    archive_identifier: str
    source_directory: Path
    cache_directory: Path
    page_map: Path
    legacy_printed_cache: bool = False

    @classmethod
    def for_book(cls, name, source_root=SOURCETEXTS_ROOT, output_root=OUTPUT_DIRECTORY):
        identifiers = {
            'birnbaum_siddur': 'PhilipBirnbaumHaSiddurHaShalemTheDailyPrayerBook1949',
            'asher_selichot': 'selichothdavidasher1912',
        }
        if name not in identifiers:
            raise ScanError(f'Unknown book {name!r}; supply an explicit BookProfile in Python.')
        directory = Path(source_root) / name
        cache = 'birnbaum_scan' if name == 'birnbaum_siddur' else name
        return cls(name, identifiers[name], directory, Path(output_root) / cache, directory / 'pages.json', name == 'birnbaum_siddur')


@dataclass(frozen=True)
class PageRef:
    scan_page: int
    leaf: int
    printed_page: str | None
    language: str | None
    facing_scan_page: int | None
    facs: str

    @property
    def designation(self):
        return f's{self.scan_page}'


def load_pages(profile: BookProfile):
    payload = json.loads(profile.page_map.read_text(encoding='utf-8'))
    if payload.get('identifier', profile.archive_identifier) != profile.archive_identifier:
        raise ScanError('Page map belongs to a different Archive item.')
    result = {}
    for p in payload['pages']:
        ref = PageRef(p['scan_page'], p['ia_leaf'], p.get('printed_page'),
                      p.get('language', p.get('side')), p.get('facing_scan_page'), p['facs'])
        if ref.scan_page != ref.leaf + 1 or ref.designation in result:
            raise ScanError('Invalid or duplicate scan identity in page map.')
        result[ref.designation] = ref
    return result


def lookup(profile, designation):
    table = load_pages(profile)
    token = str(designation)
    if token in table:
        return table[token]
    matches = [p for p in table.values() if p.printed_page == token]
    if len(matches) == 1:
        return matches[0]
    raise ScanError(f'{token!r} is missing or ambiguous; address a leaf as sN.')


def cache_designation(profile, ref):
    """Birnbaum's existing printed-label cache stays shared with its legacy CLI."""
    return ref.printed_page if profile.legacy_printed_cache and ref.printed_page else ref.designation


def fetch(profile, designation, *, archive=None, contact_email=None, force=False):
    ref = lookup(profile, designation)
    destination = profile.cache_directory / 'pages' / f'{cache_designation(profile, ref)}.jpg'
    if destination.is_file() and not force:
        return destination
    if archive is None:
        email = contact_email or os.environ.get('OPENSIDDUR_CONTACT_EMAIL', '').strip()
        if not email:
            raise ScanError('Set OPENSIDDUR_CONTACT_EMAIL or pass --contact-email.')
        archive = connect(email, model=resolve_agent_model())
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.jpg.part')
    response = http_get(archive, page_image_url(profile.archive_identifier, ref.leaf, size=''), stream=True)
    try:
        with temporary.open('wb') as out:
            for chunk in response.iter_content(chunk_size=1 << 20):
                out.write(chunk)
        from PIL import Image
        with Image.open(temporary) as im:
            im.verify()
        temporary.replace(destination)
    finally:
        response.close()
        temporary.unlink(missing_ok=True)
    return destination


def cut_bands(source, destinations, *, count=4, overlap=.12, scale=3):
    """Overlapping bands keep seam lines intact; dimensions come from the image."""
    from PIL import Image
    if count < 1 or not 0 <= overlap < .5 or scale < 1:
        raise ValueError('Invalid band count, overlap, or enlargement.')
    with Image.open(source) as im:
        height = im.height / count
        for i in range(count):
            band = im.crop((0, max(0, round(i * height - height * overlap)),
                            im.width, min(im.height, round((i + 1) * height + height * overlap))))
            dest = destinations[i]
            dest.parent.mkdir(parents=True, exist_ok=True)
            band.resize((band.width * scale, band.height * scale), Image.Resampling.LANCZOS).save(dest)
    return destinations


def bands(profile, designation, *, count=4, overlap=.12, scale=3):
    ref = lookup(profile, designation)
    source = profile.cache_directory / 'pages' / f'{cache_designation(profile, ref)}.jpg'
    destinations = [profile.cache_directory / 'bands' / f'{cache_designation(profile, ref)}_{i}.png' for i in range(count)]
    return cut_bands(source, destinations, count=count, overlap=overlap, scale=scale)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('pages', nargs='+')
    parser.add_argument('--book', required=True)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--output-root', type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument('--contact-email')
    parser.add_argument('--no-bands', action='store_true')
    args = parser.parse_args(argv)
    profile = BookProfile.for_book(args.book, args.source_root, args.output_root)
    for page in args.pages:
        print(fetch(profile, page, contact_email=args.contact_email))
        if not args.no_bands:
            for path in bands(profile, page):
                print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
