"""Render source-bound morning witnesses with volume-two bibliography and scans.

The recipe owns identities and interpretations. Rendering does not approve a
reading or add this incomplete service to the volume's accepted coverage.
"""
from copy import deepcopy

from opensiddur.importer.marmorstein_rosh_hashanah_1.build import unit_document
from opensiddur.importer.scan.authoring import TEI, element
from opensiddur.importer.util.internet_archive import page_image_url

from . import IDENTIFIER, PROJECTS
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
