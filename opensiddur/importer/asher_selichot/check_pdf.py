"""Check Asher poem PDF content, bilingual stanza geometry, and broken controls."""


import argparse
import copy
import json
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from lxml import etree
from opensiddur.importer.scan.pdf_direction import base

HEBREW_FRAGMENT = re.compile(r'[\u0590-\u05ff\ufb1d-\ufb4f·∙\s,.;:!?()\-]*[\u05d0-\u05ea\ufb1d-\ufb4f][\u0590-\u05ff\ufb1d-\ufb4f·∙\s,.;:!?()\-]*')
WORD_GAP = 20


def load_glyphs(path):
    """mutool's glyph XML for a PDF, with each Hebrew line whole again.

    With some faces (Ezra SIL) mutool ends a line at every Hebrew word, and a check that
    looks for a phrase within a line finds none. Adjacent all-Hebrew fragments on one row,
    nearer each other than a word gap, are joined back into the first: right to left, as
    they are read. English lines, margin line numbers and Hebrew set inside an English line
    keep the lines mutool gave them.
    """
    root = etree.parse(str(path)).getroot()
    for page in root.findall('page'):
        fragments = []
        for line in page.findall('.//line'):
            text = line.get('text', '')
            if HEBREW_FRAGMENT.fullmatch(text) and not any(ch.isdigit() for ch in text):
                x0, y0, x1, y1 = map(float, line.get('bbox').split())
                fragments.append([line, x0, y0, x1, y1])
        fragments.sort(key=lambda f: -f[3])
        joined = set()
        for i, first in enumerate(fragments):
            if id(first[0]) in joined:
                continue
            for other in fragments[i + 1:]:
                if id(other[0]) in joined:
                    continue
                overlap = min(first[4], other[4]) - max(first[2], other[2])
                if (overlap > 0.5 * min(first[4] - first[2], other[4] - other[2])
                        and first[1] - other[3] < WORD_GAP):
                    line, more = first[0], other[0]
                    for child in list(more):
                        line.append(child)
                    line.set('text', line.get('text', '') + ' ' + more.get('text', ''))
                    first[1], first[2], first[4] = other[1], min(first[2], other[2]), max(first[4], other[4])
                    line.set('bbox', ' '.join(str(v) for v in (first[1], first[2], first[3], first[4])))
                    more.getparent().remove(more)
                    joined.add(id(more))
    return root


def hebrew_rows(page, gutter):
    """(baseline, letters) for each row of the Hebrew column, read right to left.

    Grouped by each letter's own baseline, not by mutool's lines: with some faces a row
    comes out as several lines, one holding a margin line number, another joined to the
    English column's line.
    """
    rows = {}
    for char in page.iter('char'):
        if float(char.get('x')) < gutter and base(char.get('c', ' ')):
            rows.setdefault(round(float(char.get('y')), 1), []).append(char)
    return [(y, ''.join(base(c.get('c')) for c in sorted(chars, key=lambda c: float(c.get('x')), reverse=True)))
            for y, chars in sorted(rows.items())]


def strip_line_numbers(text):
    """Body text without reledmac's margin line numbers, which extraction runs into the line:
    after a word ("mercy 10 when") or standing alone after a comma ("Lord, 15 be").
    A number before punctuation after a comma, as in "pp. 11, 12.", is a citation and stays."""
    text = re.sub(r'(?<=[A-Za-z])\s*\d+(?=[,.;!?]|\s)', '', text)
    return re.sub(r'(?<=,)\s+\d+(?=\s)', '', text)


def corrected(text, asher_source):
    """Reading text as the PDF sets it: each misprint in corrections.json read corrected,
    the exporter's default. `asher_source` is sourcetexts' sources/asher_selichot."""
    path = Path(asher_source) / 'scan_reading/corrections.json'
    for c in (json.loads(path.read_text(encoding="utf-8"))['corrections'] if path.exists() else []):
        if 'follows' in c or c.get('exact'):
            continue
        before, after = c.get('before', ''), c.get('after', '')
        text = text.replace(before + c['sic'] + after, before + c['corr'] + after)
    return text


HEBREW = ['במוצאי', 'אתימין', 'דרוש', 'זוחלים', 'יוצר', 'מרוםאם', 'פנה', 'רצה']
ENGLISH = ['On the outgoing', 'O raise', 'O seek', 'They tremble',
           'Thou, who hast formed', 'If the misdeeds', 'Turn, we beseech', 'Be pleased']
# One Hebrew line, the most a paired stanza start may differ by: the first stanza begins
# one line higher in Hebrew after the unequal-length bilingual rubrics. Measured from the
# release face, Ezra SIL at 12pt, whose pointed rows are 17.5-18.3pt apart (SBL Hebrew's
# were 14.5pt).
MAX_BASELINE_DIFFERENCE = 19


def plain(text):
    text = text.replace('\ue049', 'Th').replace('\ue04a', 'Th')
    return unicodedata.normalize('NFKC', text)


def check(tree, expanded, complete=False):
    english = []
    hebrew = []
    for page_no, page in enumerate(tree.findall('page'), 1):
        gutter = 288 if page_no % 2 else 324
        hebrew.extend((page_no, y, letters) for y, letters in hebrew_rows(page, gutter))
        for line in page.findall('.//line'):
            chars = list(line.findall('.//char'))
            en = [c for c in chars if float(c.get('x')) > gutter]
            if en:
                english.append((page_no, float(en[0].get('y')), plain(''.join(c.get('c') for c in en)), en))
    rows = []
    he_start = en_start = (0, 0)
    for he_anchor, en_anchor in zip(HEBREW, ENGLISH):
        h = next((r for r in hebrew if he_anchor in r[2] and r[:2] >= he_start), None)
        e = next((r for r in english if en_anchor in r[2] and r[:2] >= en_start), None)
        if h is None or e is None:
            raise ValueError(f'Missing stanza anchor: {he_anchor} / {en_anchor}')
        latin_x = [float(c.get('x')) for c in e[3] if c.get('c').isascii() and c.get('c').isalpha()]
        if latin_x != sorted(latin_x):
            raise ValueError(f'Latin direction failed: {en_anchor}')
        delta = abs(h[1] - e[1])
        if h[0] != e[0] or delta > MAX_BASELINE_DIFFERENCE:
            raise ValueError(f'Stanza alignment failed: {he_anchor}: {h[:2]} / {e[:2]}')
        rows.append(round(delta, 2))
        he_start, en_start = h[:2], e[:2]
    text = plain(' '.join(line.get('text', '') for line in tree.findall('.//line')))
    if text.count('Appease thy anger and pardon our sins.') != 1:
        raise ValueError('Footnote must occur exactly once')
    if ('Wherever the word' in text) == expanded:
        raise ValueError('Refrain instructions must appear only in documentary view')
    if ('Say “Omnipotent King,”' in text) == expanded:
        raise ValueError('Prayer expansion instructions must appear only in documentary view')
    if complete:
        if text.count('Omnipotent King, who') != (4 if expanded else 1):
            raise ValueError('Missing or duplicated El Melekh occurrence in the first day')
    else:
        if ('Omnipotent King, who' in text) != expanded:
            raise ValueError('El Melekh expansion boundary failed')
        if ('And the Eternal passed by before him' in text) != expanded:
            raise ValueError('Vayaavor expansion boundary failed')
        if 'The hope of Israel' in text:
            raise ValueError('Adjacent prayer outside reference boundary')
    if ('(Hearken,' in text) == expanded:
        raise ValueError('Wrong abbreviation branch')
    return rows


def controls(tree, expanded, complete=False):
    broken = copy.deepcopy(tree)
    note = next(l for l in broken.findall('.//line') if 'Appease thy anger' in l.get('text', ''))
    note.getparent().append(copy.deepcopy(note))
    try:
        check(broken, expanded, complete)
    except ValueError:
        pass
    else:
        raise AssertionError('Duplicate footnote control escaped detection')
    broken = copy.deepcopy(tree)
    for line in broken.findall('.//line'):
        if 'O seek' in plain(line.get('text', '')):
            for char in line.findall('.//char'):
                if float(char.get('x')) > 288:
                    char.set('y', str(float(char.get('y')) + 50))
    try:
        check(broken, expanded, complete)
    except ValueError:
        pass
    else:
        raise AssertionError('Shifted stanza control escaped detection')
    try:
        check(tree, not expanded, complete)
    except ValueError:
        pass
    else:
        raise AssertionError('Wrong expansion control escaped detection')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('pdf', type=Path)
    p.add_argument('--expanded', action='store_true')
    p.add_argument('--complete', action='store_true', help='Check the poem within the complete first day.')
    p.add_argument('--control', action='store_true')
    args = p.parse_args(argv)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)/'text.xml'
        subprocess.run(['mutool', 'draw', '-F', 'stext', '-o', str(path), str(args.pdf)], check=True, capture_output=True)
        tree = load_glyphs(path)
        rows = check(tree, args.expanded, args.complete)
        if args.control:
            controls(tree, args.expanded, args.complete)
        print(f'8 stanza pairs aligned (baseline deltas {rows}); footnote once; abbreviation and prayer boundaries correct; controls={args.control}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
