"""Check fifth penitential day stanza alignment, apparatus, and fulfilled reference boundaries."""
import copy

from lxml import etree

from opensiddur.importer.scan.pdf import strip_numeric_markers
from opensiddur.importer.scan.pdf_direction import base

from .check_first_day_pdf import latin_note_runs
from .check_pdf import MAX_BASELINE_DIFFERENCE, load_glyphs, plain

ANCHORS = [('ייייאלרחום','The Eternal is the immutable'),
           ('אזכרהאלהיםואהמיה','I remember, O God'),
           ('מדתהרחמים','O mercy, divine attribute'),
           ('תמכתייתדותי','I rely on the thirteen'),
           ('יהירצוןמלפניך','O thou who hearest the voice')]



def check(tree, expanded=False):
    text=plain(' '.join(n.get('text','') for n in tree.findall('.//line')))
    # These long fingerprints remain distinctive even when a note wraps.
    for phrase in ['Which man has contracted towards God by his sins.', 'With allusion to Isa. i. 3.', 'Ps. cii. 28.', 'Gen. xii. 8.', 'See Jer. xxxi. 22.', 'With reference to Job xxxiii. 29.']:
        if text.count(phrase)!=1:raise ValueError('Penitential-day footnote missing or duplicated: '+phrase)
    note_runs=latin_note_runs(tree)
    if not note_runs:raise ValueError('No fifth penitential day Latin apparatus runs measured')
    for chars in note_runs.values():
        xs=[float(c.get('x')) for c in chars]
        if any(b<a-0.05 for a,b in zip(xs,xs[1:])):raise ValueError('Reversed fifth penitential day Latin apparatus')
    he,en=[],[]
    for number,page in enumerate(tree.findall('page'),1):
        gutter=288 if number%2 else 324
        hrows,erows={},{}
        for line in page.findall('.//line'):
            for c in line.findall('.//char'):
                x=float(c.get('x'));y=round(float(c.get('y')),2)
                if x<gutter and base(c.get('c',' ')):hrows.setdefault(y,[]).append(c)
                elif x>gutter:erows.setdefault(y,[]).append(c)
        he.extend((number,y,''.join(base(c.get('c')) for c in sorted(chars,key=lambda c:float(c.get('x')),reverse=True))) for y,chars in hrows.items())
        for y,chars in erows.items():
            words='';right=None
            for c in sorted(chars,key=lambda c:float(c.get('x'))):
                if right is not None and float(c.get('x'))-right>2 and words and not words[-1].isspace():words+=' '
                words+=c.get('c','');quad=list(map(float,c.get('quad').split()));right=max(quad[0::2])
            en.append((number,y,plain(words)))
    deltas=[];previous=(0,0)
    for h_anchor,e_anchor in ANCHORS:
        e=next((r for r in en if e_anchor in r[2] and r[:2]>=previous),None)
        matches=[r for r in he if h_anchor in r[2] and r[:2]>=previous]
        h=min(matches,key=lambda r:abs(r[0]-e[0])*1000+abs(r[1]-e[1])) if matches and e else None
        if h is None or e is None:raise ValueError('Missing fifth penitential day stanza: '+e_anchor)
        if h[0]!=e[0] or abs(h[1]-e[1])>MAX_BASELINE_DIFFERENCE:raise ValueError('fifth penitential day stanza alignment differs: '+e_anchor+': '+str((h[:2],e[:2])))
        deltas.append(round(abs(h[1]-e[1]),2));previous=max(h[:2],e[:2])
    body=' '.join(r[2] for r in en)
    body=strip_numeric_markers(body)
    if expanded:
        if ''.join(r[2] for r in he).count('לעלאלעלאמןכלברכתא')!=2:
            raise ValueError('Ten Days Half and Full Kaddishes must both double leela')
        opening=body.split('People of the Lord, let us be courageous',1)[0]
        if opening.count('Pardon us, our Father!')!=1:raise ValueError('fifth penitential day opening must include the following Selah lanu once')
        for cue in ['Conclude the Service from', 'Say ', 'Wherever the words', 'During the Ten Days of Repentance']:
            if cue in body:raise ValueError('Fulfilled fifth penitential day cue remains: '+cue)
        if body.count('May the prayers and supplications')!=1:raise ValueError('fifth penitential day requires one supplied Full Kaddish')
        # Nine supplied Vayaavor passages plus the printed and repeated opening.
        if body.count('being; an Omnipotent God')!=2 or body.count('take us for thy heritage.')!=11:raise ValueError('fifth penitential day must repeat the complete thirteen-attributes opening')
        if body.count('Omnipotent King, who')!=8:raise ValueError('fifth penitential day prayer-pair reference boundary changed')
    else:
        if 'Conclude the Service from' not in body:raise ValueError('Missing documentary fifth penitential day closing instruction')
        poem=body.partition('I remember, O God')[2]
        if poem.count('(The Eternal, &c.)')!=1 or body.count('being; an Omnipotent God')!=1:
            raise ValueError('Documentary fifth penitential day opening/repeat cue changed')
    print('fifth penitential day PDF: apparatus, fulfilled cues and reference boundaries checked; 5 stanza start deltas '+str(deltas))


def controls(tree,expanded):
    for phrase in ['Ps. cii. 28.', 'Gen. xii. 8.']:
        broken=copy.deepcopy(tree)
        line=next(n for n in broken.findall('.//line') if phrase in plain(n.get('text','')))
        line.getparent().remove(line)
        try:check(broken,expanded)
        except ValueError:pass
        else:raise AssertionError('Missing penitential note escaped detection')
    broken=copy.deepcopy(tree)
    for number,page in enumerate(broken.findall('page'),1):
        for line in page.findall('.//line'):
            if 'I remember, O God' in plain(line.get('text','')):
                # MuPDF can put both columns in one line: move only English.
                for char in line.findall('.//char'):
                    if float(char.get('x'))>(288 if number%2 else 324):
                        char.set('y',str(float(char.get('y'))+50))
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Shifted penitential stanza escaped detection')
    if expanded:
        broken=copy.deepcopy(tree)
        line=etree.SubElement(broken.find('page'),'line',text='לעלא לעלא מן כל ברכתא')
        font=etree.SubElement(line,'font',size='12')
        for i,char in enumerate('לעלאלעלאמןכלברכתא'):
            x=250-i*5
            etree.SubElement(font,'char',c=char,x=str(x),y='701',quad=f'{x} 690 {x+5} 690 {x} 705 {x+5} 705')
        try:check(broken,expanded)
        except ValueError:pass
        else:raise AssertionError('Wrong seasonal Kaddish count escaped detection')
    if expanded:
        broken=copy.deepcopy(tree)
        line=etree.SubElement(broken.find('page'),'line',text='Conclude the Service from')
        font=etree.SubElement(line,'font',size='12')
        for index,c in enumerate('Conclude the Service from'):
            etree.SubElement(font,'char',c=c,x=str(360+index*5),y='700',quad=f'{360+index*5} 690 {365+index*5} 690 {360+index*5} 705 {365+index*5} 705')
        try:check(broken,expanded)
        except ValueError:pass
        else:raise AssertionError('Fulfilled penitential cue escaped detection')
    if expanded:
        broken=copy.deepcopy(tree)
        lines=[n for n in broken.findall('.//line') if 'Omnipotent God' in plain(n.get('text',''))]
        if len(lines)!=2:raise AssertionError('Opening-repeat control cannot locate its two lines')
        lines[-1].getparent().remove(lines[-1])
        try:check(broken,expanded)
        except ValueError:pass
        else:raise AssertionError('Missing expanded opening escaped detection')
    broken=copy.deepcopy(tree)
    chars=next(iter(latin_note_runs(broken).values()))
    for index,char in enumerate(chars):char.set('x',str(600-index*5))
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Reversed Latin note escaped detection')
    print('Penitential PDF controls rejected missing notes, shifted stanza and fulfilled cue')


def main():
    import argparse
    import subprocess
    import tempfile
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf',type=Path);parser.add_argument('--expanded',action='store_true');parser.add_argument('--control',action='store_true')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'text.xml'
        subprocess.run(['mutool','draw','-F','stext','-o',str(path),str(args.pdf)],check=True,capture_output=True)
        tree=load_glyphs(path);check(tree,args.expanded)
        if args.control:controls(tree,args.expanded)


if __name__=='__main__':main()
