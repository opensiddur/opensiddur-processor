"""Measure Monday fast stanza starts, notes, asymmetric refrains and reference limits."""
import argparse
import copy
import re
from pathlib import Path

from lxml import etree

from opensiddur.importer.scan.pdf import strip_numeric_markers
from opensiddur.importer.scan.pdf_direction import base

from .check_first_day_pdf import latin_note_runs
from .check_pdf import MAX_BASELINE_DIFFERENCE, load_glyphs, plain

ANCHORS=[('מלאכירחמים','Angels of mercy!'),('אוליירחםשארית','Perchance he will have mercy on the remnant'),('אוליירחםמעני','Perchance he will have mercy on those who are afflicted'),('אוליירחםוירא','Perchance he will have mercy and look'),('אוליירחםאומרי','Perchance he will have mercy upon those who pray'),('אוליירחםלקתה','Perchance he will have mercy on those who are doubly'),('אוליירחםכבושי','Perchance he will have mercy on those who are ashamed'),('אוליירחםיחלץ','Perchance he will have mercy who delivereth')]

def check(tree, expanded=False):
    text=plain(' '.join(n.get('text','') for n in tree.findall('.//line')))
    for phrase,count in [('The concluding sentence is a quotation',1),('Lev. xxvi',3),('Deut. xxx.',3),('Deut. iv.',2),('Isaiah xliv. 22.',1),('Isaiah xliii. 25.',1),('Isaiah i. 18.',1),('Isaiah lvi. 7.',1),('Ezek. xxxvi. 25.',2)]:
        if text.count(phrase)!=count:raise ValueError('Monday footnote missing or duplicated: '+phrase)
    runs=latin_note_runs(tree)
    if not runs:raise ValueError('No Monday apparatus glyph runs measured')
    for chars in runs.values():
        xs=[float(c.get('x')) for c in chars]
        if any(b<a-0.05 for a,b in zip(xs,xs[1:])):raise ValueError('Reversed Monday Latin apparatus')
    he,en,headings=[],[],[]
    for number,page in enumerate(tree.findall('page'),1):
        gutter=288 if number%2 else 324
        hrows,erows={},{}
        for line in page.findall('.//line'):
            chars=line.findall('.//char')
            hebrew=''.join(base(c.get('c',' ')) or '' for c in sorted(chars,key=lambda c:float(c.get('x')),reverse=True))
            if hebrew=='פזמון' and not any(c.get('c','').isdigit() for c in chars):headings.append((number,min(float(c.get('y')) for c in chars)))
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
        h=next((r for r in he if h_anchor in r[2] and r[:2]>previous),None)
        prefix=e_anchor if e_anchor=='Angels of mercy!' else 'Perchance he will have mercy'
        matches=[r for r in en if prefix in r[2] and r[:2]>previous]
        e=min(matches,key=lambda r:abs(r[0]-h[0])*1000+abs(r[1]-h[1])) if matches and h else None
        if h is None or e is None:raise ValueError('Missing Monday stanza: '+e_anchor)
        if not deltas and not any(r[0]==h[0] and r[1]<h[1] for r in headings):raise ValueError('Monday pizmon heading stranded or absent')
        if h[0]!=e[0] or abs(h[1]-e[1])>MAX_BASELINE_DIFFERENCE:raise ValueError('Monday stanza misaligned: '+str((h[:2],e[:2])))
        deltas.append(round(abs(h[1]-e[1]),2));previous=max(h[:2],e[:2])
    body=re.sub(r'(?<=\w)-\s+(?=\w)','',' '.join(r[2]for r in en))
    body=strip_numeric_markers(body)
    if body.count('Angels of mercy! servants of the Most High!')!=1:raise ValueError('Unprinted English opening repeat')
    for phrase in ['The Reader continues the Ameedah','The Reader says Kaddish','Conclude the service as on other week-days.']:
        if body.count(phrase)!=1:raise ValueError('Unsupplied performance instruction lost: '+phrase)
    if 'May the prayers and supplications' in body:raise ValueError('Unrequested Full Kaddish supplied')
    if 'PROPITIATORY PRAYERS FOR THE FIFTH FAST' in body:raise ValueError('Following service entered Monday')
    if body.count('Thy righteous anointed declared')!=1 or body.count('abundant to pardon.')!=1:raise ValueError('Monday closing range missing or duplicated')
    if expanded:
        for cue in ['Say ', 'Wherever the words', '(Perchance, &c.)']:
            if cue in body:raise ValueError('Fulfilled Monday cue remains: '+cue)
        if body.count('Omnipotent King, who')!=3 or body.count('take us for thy heritage.')!=4:raise ValueError('Monday prayer-pair boundaries changed')
        if body.count('perchance he will spare a poor and needy people')!=7:raise ValueError('Monday English refrain expansion count')
        if ''.join(r[2] for r in he).count('מלאכירחמיםמשרתיעליון')!=2:raise ValueError('Monday Hebrew opening repeat absent or duplicated')
    elif body.count('(Perchance, &c.)')!=6 or body.count('perchance he will spare a poor and needy people')!=1:raise ValueError('Documentary Monday refrain cues changed')
    print('Monday fast PDF: 15 notes, asymmetric refrains, performance rubrics and boundaries checked; 8 stanza deltas '+str(deltas))


def controls(tree,expanded):
    for phrase in ['The concluding sentence is a quotation','The Reader continues the Ameedah']:
        broken=copy.deepcopy(tree);line=next(n for n in broken.findall('.//line')if phrase in plain(n.get('text','')));line.getparent().remove(line)
        try:check(broken,expanded)
        except ValueError:pass
        else:raise AssertionError('Missing Monday text escaped detection')
    broken=copy.deepcopy(tree)
    shifted=0
    for number,page in enumerate(broken.findall('page'),1):
        gutter=288 if number%2 else 324
        for line in page.findall('.//line'):
            hchars=[c for c in line.findall('.//char')if float(c.get('x'))<gutter and base(c.get('c',' '))]
            letters=''.join(base(c.get('c'))for c in sorted(hchars,key=lambda c:float(c.get('x')),reverse=True))
            if 'אוליירחםוירא' in letters:
                y=float(hchars[0].get('y'))
                for c in page.findall('.//char'):
                    if float(c.get('x'))>gutter and abs(float(c.get('y'))-y)<.1:c.set('y',str(float(c.get('y'))+50));shifted+=1
    if not shifted:raise AssertionError('Monday shifted control found no aligned glyphs')
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Shifted Monday stanza escaped detection')
    broken=copy.deepcopy(tree);etree.SubElement(broken.find('page'),'line',text='Ezek. xxxvi. 25.')
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Duplicate Monday footnote escaped detection')
    print('Monday fast broken controls rejected')


def main(argv=None):
    import subprocess
    import tempfile
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('pdf');p.add_argument('--expanded',action='store_true');p.add_argument('--control',action='store_true');a=p.parse_args(argv)
    with tempfile.TemporaryDirectory()as tmp:
        xml=Path(tmp)/'glyphs.xml';subprocess.run(['mutool','draw','-F','stext','-o',str(xml),a.pdf],check=True,capture_output=True);tree=load_glyphs(xml);check(tree,a.expanded)
        if a.control:controls(tree,a.expanded)
    return 0
if __name__=='__main__':raise SystemExit(main())
