"""Derive scan identities, retaining machine labels separately from image evidence."""
from lxml import etree

from opensiddur.importer.util.internet_archive import page_image_url


def derive_pages(identifier, scandata, machine_numbers, corrections):
    """Machine labels remain candidates until an image reading verifies them."""
    root = etree.fromstring(scandata)
    candidates = {p['leafNum']: p.get('pageNumber') for p in machine_numbers['pages']}
    pages = []
    leaves = {int(p.get('leafNum')) for p in root.findall('.//pageData/page')}
    unknown = set(corrections) - {str(n) for n in leaves}
    if unknown:
        raise ValueError(f'Corrections refer to missing leaves: {unknown}')
    for leaf in sorted(leaves):
        correction = corrections.get(str(leaf), {})
        if correction and not correction.get('evidence'):
            raise ValueError('A correction must identify its image evidence.')
        facing = correction.get('facing_leaf')
        if facing is not None:
            other = corrections.get(str(facing), {})
            if other.get('facing_leaf') != leaf:
                raise ValueError('Verified translation pairing must be reciprocal.')
        pages.append({'scan_page': leaf + 1, 'ia_leaf': leaf,
            'printed_page': correction.get('printed_page'),
            'printed_label': correction.get('printed_label'),
            'language': correction.get('language'),
            'facing_scan_page': None if facing is None else facing + 1,
            'machine_page_candidate': candidates.get(leaf) or None,
            'evidence': correction.get('evidence'),
            'facs': page_image_url(identifier, leaf)})
    return {'identifier': identifier, 'pages': pages}
