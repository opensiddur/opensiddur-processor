"""Source boundaries, apparatus and cue replacements in the Erev PDF."""
import copy
import re

from opensiddur.importer.scan.pdf_direction import base

from .check_first_day_pdf import latin_note_runs
from .check_pdf import MAX_BASELINE_DIFFERENCE, plain, strip_line_numbers


def check(tree, expanded=False):
    text=strip_line_numbers(' '.join(plain(n.get('text','')) for n in tree.findall('.//line')))
    for phrase in ['Supreme Judge','Remember the covenant','Accept, O Lord','Guardian of Israel','glory of thy name']:
        if phrase not in text:raise ValueError('Missing Erev passage: '+phrase)
    if 'FAST OF GEDALIAH' in text:raise ValueError('Erev reference boundary crossed')
    for phrase in ['Alluding to Ezek. xxiv. 2.', 'Alluding to Job xxxiii. 24']:
        if text.count(phrase)!=1:raise ValueError('Erev footnote missing or duplicated: '+phrase)
    for chars in latin_note_runs(tree).values():
        xs=[float(c.get('x')) for c in chars]
        if any(b<a-0.05 for a,b in zip(xs,xs[1:])):raise ValueError('Reversed Erev Latin apparatus')
    he,en=[],[]
    for number,page in enumerate(tree.findall('page'),1):
        gutter=288 if number%2 else 324
        hrows,erows={},{}
        for line in page.findall('.//line'):
            chars=line.findall('.//char')
            h=[c for c in chars if float(c.get('x'))<gutter and base(c.get('c',' '))]
            e=[c for c in chars if float(c.get('x'))>gutter]
            if h:hrows.setdefault(round(float(h[0].get('y')),2),[]).extend(h)
            for c in e:erows.setdefault(round(float(c.get('y')),2),[]).append(c)
        he.extend((number,y,''.join(base(c.get('c')) for c in sorted(chars,key=lambda c:float(c.get('x')),reverse=True))) for y,chars in hrows.items())
        for y,chars in erows.items():
            words='';right=None
            for char in sorted(chars,key=lambda c:float(c.get('x'))):
                x=float(char.get('x'))
                if right is not None and x-right>2 and words and not words[-1].isspace():words+=' '
                words+=char.get('c','')
                quad=list(map(float,char.get('quad').split()));right=max(quad[0::2])
            words=plain(words)
            words=strip_line_numbers(words)
            words=re.sub(r'\s+([,.;!?])',r'\1',words)
            en.append((number,y,words))
    deltas=[]
    for h_anchor,e_anchor in [('אדוןכתקח','O Lord, when on the appointed'),('אדוןבשפטך','O Lord! when thou judgest'),('מלךאחד','One King shall'),('שפטכלהארץ','O Supreme Judge'),('זכורברית','Remember the covenant'),('תפלהתקח','Accept, O Lord')]:
        e=next((r for r in en if e_anchor in r[2]),None)
        matches=[r for r in he if h_anchor in r[2]]
        h=min(matches,key=lambda r:abs(r[0]-e[0])*1000+abs(r[1]-e[1])) if matches and e else None
        if h is None or e is None:raise ValueError('Missing Erev alignment anchor: '+e_anchor)
        if h[0]!=e[0] or abs(h[1]-e[1])>MAX_BASELINE_DIFFERENCE:raise ValueError('Erev start alignment differs: '+e_anchor+': '+str((h[:2],e[:2])))
        deltas.append(round(abs(h[1]-e[1]),2))
    cues=['The Reader says Kaddish.','Say “Omnipotent King,”','Say from “Like a father']
    if expanded:
        if any(cue in text for cue in cues):raise ValueError('Fulfilled Erev cue remains in expanded output')
        for phrase in ['May the prayers and supplications','The Ark is opened','close the Ark']:
            if phrase not in text:raise ValueError('Missing expanded Erev prayer or performance instruction: '+phrase)
    elif 'The Reader says Kaddish.' not in text:raise ValueError('Missing Erev closing instruction')
    print('Erev PDF: service boundaries, closing cue, retained Ark instructions and apparatus checked; start deltas '+str(deltas))


def controls(tree, expanded):
    broken=copy.deepcopy(tree)
    phrase='Alluding to Ezek. xxiv. 2.'
    line=next(n for n in broken.findall('.//line') if phrase in plain(n.get('text','')))
    line.getparent().append(copy.deepcopy(line))
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Duplicate Erev note escaped detection')
    broken=copy.deepcopy(tree)
    line=broken.find('.//line');line.set('text','FAST OF GEDALIAH')
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Gedaliah boundary control escaped detection')

    broken=copy.deepcopy(tree)
    for number,page in enumerate(broken.findall('page'),1):
        for line in page.findall('.//line'):
            if 'One King' in plain(line.get('text','')):
                for char in line.findall('.//char'):
                    if float(char.get('x'))>(288 if number%2 else 324):char.set('y',str(float(char.get('y'))+50))
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Shifted Erev alignment escaped detection')
