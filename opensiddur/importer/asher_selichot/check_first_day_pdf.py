"""Check the first-day PDF, including the Latin citation direction."""

import argparse
import copy
import re
import subprocess
import tempfile
from pathlib import Path

from lxml import etree

from opensiddur.importer.scan.pdf import latin_note_runs as _latin_note_runs
from opensiddur.importer.scan.pdf_direction import base

from .check_pdf import MAX_BASELINE_DIFFERENCE, hebrew_rows, load_glyphs, plain

ANCHORS = [('אשרייושביביתך', 'Happy are they who dwell'),
           ('תהלתיי', 'My mouth shall utter'),
           ('יתגדלויתקדש', 'May his great name be exalted'),
           ('יהאשמהרבא', 'May his great name be blessed')]


def latin_note_runs(tree):
    return _latin_note_runs(tree, maximum_font_size=10)


def check_mi_sheanah(rows):
    starts = [row for row in rows if 'מישענה' in row[2]]
    if (len(starts) != 20 or len({row[:2] for row in starts}) != 20
            or any(row[2].count('מישענה') != 1 for row in starts)
            or ''.join(row[2] for row in rows).count('הואיעננו') != 20):
        raise ValueError('Mi Sheanah requires 20 distinct verse starts and 20 refrains')


def check(tree, complete=False, expanded=False):
    for key, chars in latin_note_runs(tree).items():
        xs = [float(c.get('x')) for c in chars]
        if any(right < left-0.05 for left, right in zip(xs, xs[1:])):
            raise ValueError(f'Reversed Latin note on PDF page {key[0]}')
    he_rows, en_rows, citation = [], [], []
    for page_no, page in enumerate(tree.findall('page'), 1):
        gutter = 288 if page_no % 2 else 324
        he_rows.extend((page_no, y, letters) for y, letters in hebrew_rows(page, gutter))
        for line in page.findall('.//line'):
            chars = list(line.findall('.//char'))
            en = [c for c in chars if float(c.get('x')) > gutter]
            he = [c for c in chars if base(c.get('c', ' ')) and float(c.get('x')) < gutter]
            if en:
                en_rows.append((page_no, float(en[0].get('y')), plain(''.join(c.get('c') for c in en))))
            left = [c for c in chars if float(c.get('x')) < gutter]
            left_text = ''.join(c.get('c') for c in left).strip()
            if any(c in ':׃' for c in left_text) and all(c.isspace() or c.isdigit() or c in ':׃' for c in left_text):
                raise ValueError(f'Stranded Hebrew punctuation on PDF page {page_no}')
            if page_no >= 5 and he and ':' in left_text and not any(c.isascii() and c.isalpha() for c in left_text):
                raise ValueError('Hebrew verse stop must be U+05C3 sof pasuq, not a colon')
            if 'Ps. cxlv.' in plain(''.join(c.get('c') for c in left)):
                citation.append(left)
    deltas=[]
    anchors=ANCHORS + ([('שמעקולנו','Hear our voice'),('ואנחנו לאנדע'.replace(' ',''),'We know not what to do')] if complete else [])
    for h_anchor, e_anchor in anchors:
        h=next((r for r in he_rows if h_anchor in r[2]),None)
        e=next((r for r in en_rows if e_anchor in r[2]),None)
        if not h or not e:raise ValueError(f'Missing prayer anchor {h_anchor} / {e_anchor}')
        delta=abs(h[1]-e[1])
        if h[0]!=e[0] or delta>MAX_BASELINE_DIFFERENCE:
            raise ValueError(f'Prayer alignment failed: {h[:2]} / {e[:2]}')
        deltas.append(round(delta,2))
    if len(citation)!=1:raise ValueError('Latin Psalm citation must occur once in the Hebrew column')
    x=[float(c.get('x')) for c in citation[0] if c.get('c').isascii() and c.get('c').isalpha()]
    if x!=sorted(x):raise ValueError('Latin Psalm citation is reversed')
    text=plain(' '.join(line.get('text','') for line in tree.findall('.//line')))
    if text.count('Ph. Dr.')!=1 or 'Budinger' not in text or '1912-5672.' not in text:
        raise ValueError('Missing or duplicated English title credits/imprint')
    if 'SECOND DAY' in text:
        raise ValueError('First-day output includes the second-day heading')
    if complete:
        check_mi_sheanah(he_rows)
        body_text=re.sub(r'\b\d+\b','',plain(' '.join(r[2] for r in en_rows)))
        body_text=' '.join(body_text.split())
        if 'expiation of our sins for the sake of thy name.' not in body_text:
            raise ValueError('Missing first-day conclusion')
        if expanded:
            if 'During the Ten Days of Repentance' in text:
                raise ValueError('First-day Selichot includes the Ten Days addition')
            if ''.join(row[2] for row in he_rows).count('לעלא') != 2:
                raise ValueError('First-day Kaddishes must each contain לעלא exactly once')
            for phrase, count in [('Omnipotent King, who', 4), ('Like a father hath compassion', 3),
                                  ('for we do not presume', 3), ('We have trespassed,', 3),
                                  ('May the prayers and supplications', 1), ('He who creates peace', 1)]:
                if body_text.count(phrase) != count:
                    raise ValueError(f'Missing or duplicated expansion: {phrase}')
            if 'The Reader says Kaddish.' in body_text or 'Say ' in body_text:
                raise ValueError('Expanded output retains a fulfilled instruction')
        elif 'The Reader says Kaddish.' not in body_text:
            raise ValueError('Missing final Reader’s Kaddish rubric')
        for phrase in ['Explained by some', 'Idolatry, fornication and murder.', 'From here down']:
            if text.count(phrase)!=1:raise ValueError(f'Missing or duplicated footnote: {phrase}')
    elif 'Omnipotent King, who' in text:
        raise ValueError('Partial opening contains material beyond its encoded range')
    return deltas


def controls(tree, complete=False, expanded=False):
    kinds=['direction','note-direction','alignment','boundary','punctuation','wrong-stop']
    if complete:kinds+=['conclusion','footnote','poetry-lineation']
    if expanded:kinds+=['repetition','fulfilled-instruction','ten-days','ten-days-word']
    for kind in kinds:
        broken=copy.deepcopy(tree)
        if kind=='direction':
            line=next(l for l in broken.findall('.//line') if 'Ps. cxlv.' in l.get('text','') and float(l.find('.//char').get('x'))<288)
            chars=[c for c in line.findall('.//char') if float(c.get('x'))<288 and c.get('c').isascii() and c.get('c').isalpha()]
            xs=[c.get('x') for c in chars]
            for c,x in zip(chars,reversed(xs)):c.set('x',x)
        elif kind=='note-direction':
            chars = max(latin_note_runs(broken).values(), key=len)
            xs = [c.get('x') for c in chars]
            for char, x in zip(chars, reversed(xs)):char.set('x', x)
        elif kind=='alignment':
            for line in broken.findall('.//line'):
                if 'May his great name be exalted' in plain(line.get('text','')):
                    for c in line.findall('.//char'):
                        if float(c.get('x'))>288:c.set('y',str(float(c.get('y'))+50))
        elif kind=='boundary':
            etree.SubElement(broken.find('page'),'line',text='SECOND DAY')
        elif kind=='punctuation':
            line=etree.SubElement(broken.findall('page')[4],'line',text='׃')
            etree.SubElement(line,'char',c='׃',x='250',y='400')
        elif kind=='conclusion':
            for line in list(broken.findall('.//line')):
                phrase = 'May the prayers and supplications' if expanded else 'The Reader says Kaddish.'
                if phrase in plain(line.get('text','')):line.getparent().remove(line)
        elif kind=='ten-days-word':
            line=etree.SubElement(broken.find('page'),'line',text='לעלא')
            for i, char in enumerate('לעלא'):
                etree.SubElement(line,'char',c=char,x=str(250-i*5),y='400')
        elif kind=='ten-days':
            etree.SubElement(broken.find('page'),'line',text='During the Ten Days of Repentance, add:')
        elif kind=='repetition':
            line=next(l for l in broken.findall('.//line') if 'We have trespassed,' in plain(l.get('text','')))
            line.getparent().remove(line)
        elif kind=='fulfilled-instruction':
            line=etree.SubElement(broken.find('page'),'line',text='Say the omitted prayer.')
            for i, char in enumerate('Say the omitted prayer.'):
                etree.SubElement(line,'char',c=char,x=str(600+i),y='400')
        elif kind=='footnote':
            line=next(l for l in broken.findall('.//line') if 'Explained by some' in l.get('text',''))
            line.getparent().append(copy.deepcopy(line))
        elif kind=='poetry-lineation':
            for page in broken.findall('page'):
                gutter = 288 if list(broken).index(page) % 2 == 0 else 324
                for line in page.findall('.//line'):
                    chars = [c for c in line.findall('.//char') if float(c.get('x')) < gutter]
                    words = ''.join(base(c.get('c','')) or '' for c in sorted(chars, key=lambda c:float(c.get('x')), reverse=True))
                    if 'מישענה' in words:
                        line.getparent().remove(line)
                        break
                else:
                    continue
                break
        else:
            stop=next(c for c in broken.findall('.//char') if c.get('c')=='׃')
            stop.set('c',':')
        try:check(broken,complete=complete,expanded=expanded)
        except ValueError:pass
        else:raise AssertionError(f'{kind} control escaped detection')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('pdf',type=Path);p.add_argument('--control',action='store_true')
    p.add_argument('--complete',action='store_true')
    p.add_argument('--expanded',action='store_true')
    args=p.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        xml=Path(tmp)/'text.xml'
        subprocess.run(['mutool','draw','-q','-F','stext','-o',str(xml),str(args.pdf)],check=True)
        tree=load_glyphs(xml)
    print('Prayer baseline differences:',check(tree,complete=args.complete,expanded=args.expanded))
    if args.control:
        controls(tree,complete=args.complete,expanded=args.expanded)
        additional = ('; Kaddish, first-day context, repetition, fulfilled-instruction and duplicate-footnote controls rejected'
                      if args.expanded else '; final rubric and duplicate-footnote controls rejected' if args.complete else '')
        print('Direction, alignment, section boundary and verse-stop controls rejected'+additional)
    return 0


if __name__=='__main__':raise SystemExit(main())
