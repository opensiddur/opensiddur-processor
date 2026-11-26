"""Measure the final circumcision recension and the book's final boundary."""
import argparse
import copy
import subprocess
import tempfile
from pathlib import Path

from opensiddur.importer.scan.pdf import strip_numeric_markers
from opensiddur.importer.scan.pdf_direction import base

from .check_fast_pdf import glyph_rows
from .check_pdf import MAX_BASELINE_DIFFERENCE, load_glyphs, plain

ANCHORS=[('זכורברית','Remember the covenant'),('אותברית','It is a sign'),('רחמיךזכור','Remember thy mercy'),('מפיאוהביך','The blood of thy'),('דורשדמים','O thou, who avengest')]

def marker_chars(tree):
    result=[]
    for number,page in enumerate(tree.findall('page'),1):
        left,right=(288,487) if number%2 else (324,523)
        for font in page.findall('.//font'):
            if float(font.get('size','100'))>=9:continue
            result.extend(c for c in font.findall('char') if c.get('c')=='1' and left<float(c.get('x'))<right and float(c.get('y'))>100)
    return result


def check(tree,expanded=False):
    he,en,_=glyph_rows(tree);previous=(0,0);deltas=[]
    for ha,ea in ANCHORS:
        h=next((r for r in he if r[2].startswith(ha) and r[:2]>previous),None)
        e=next((r for r in en if ea in r[2] and r[:2]>previous),None)
        if h is None or e is None:raise ValueError('Missing final-poem stanza: '+str((ha,ea)))
        if h[0]!=e[0] or abs(h[1]-e[1])>MAX_BASELINE_DIFFERENCE:raise ValueError('Final-poem stanza misaligned: '+str((h,e)))
        deltas.append(round(abs(h[1]-e[1]),2));previous=max(h[:2],e[:2])
    words=strip_numeric_markers(plain(' '.join(r[2] for r in en)))
    if words.count('When a Circumcision')!=2:
        # The Hebrew-side English rubric lies in the left column, outside en.
        text=' '.join(l.get('text','') for l in tree.findall('.//line'))
        if text.count('When a Circumcision')!=2:raise ValueError('Circumcision performance instructions changed')
    if words.count('and bring back the captives of the tents of Jacob, and save us for the sake of thy name.')!=2:raise ValueError('Final English refrain missing or repeated')
    if len(marker_chars(tree))!=1:raise ValueError('Unresolved final note marker missing or duplicated')
    hebrew=''.join(r[2] for r in he)
    if hebrew.count('מפיאוהביךעדבינךוביןידידיך')!=1:
        raise ValueError('Restored cross-page verse missing or repeated')
    if 'דםידידיך' in hebrew:raise ValueError('Invented blood wording remains in Hebrew')
    def consonants(s):return ''.join(base(c)or'' for c in s)
    for text,count in [('והשב שבות אהלי יעקב והושיענו למען שמך',3 if expanded else 2),('ושוב ברחמים על שארית ישראל והושיענו למען שמך',2 if expanded else 1)]:
        if hebrew.count(consonants(text))!=count:raise ValueError('Final Hebrew refrain selection changed: '+text)
    text=' '.join(l.get('text','') for l in tree.findall('.//line'))
    if ('Wherever the words' in text)==expanded:raise ValueError('Final fulfilled-repeat instruction polarity changed')
    if 'A Mourner says Kaddish' in text or 'May the prayers and supplications' in text:raise ValueError('Previous service entered final poem')
    print('Circumcision: five stanza baseline deltas '+str(deltas)+'; alternating Hebrew refrains, English omission, unresolved marker and final boundary checked')
    return he,en


def controls(tree,expanded=False):
    _,rows=check(tree,expanded)
    broken=copy.deepcopy(tree)
    for c in marker_chars(broken):c.getparent().remove(c)
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Deleted unresolved marker escaped detection')
    broken=copy.deepcopy(tree);page,y=next((p,y) for p,y,t in rows if 'It is a sign' in t)
    for n,p in enumerate(broken.findall('page'),1):
        for c in p.findall('.//char'):
            if n==page and round(float(c.get('y')),2)==y and float(c.get('x'))>(288 if n%2 else 324):c.set('y',str(float(c.get('y'))+50))
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Shifted final stanza escaped detection')
    broken=copy.deepcopy(tree)
    page,y=next((p,y) for p,y,t in glyph_rows(tree)[0] if t.startswith('מפיאוהביך'))
    for n,p in enumerate(broken.findall('page'),1):
        for c in list(p.findall('.//char')):
            if n==page and round(float(c.get('y')),2)==y and float(c.get('x'))<(288 if n%2 else 324):c.getparent().remove(c)
    try:check(broken,expanded)
    except ValueError:pass
    else:raise AssertionError('Deleted restored verse escaped detection')
    print('Circumcision: missing-marker, shifted-stanza and missing-restored-verse controls rejected')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('pdf');p.add_argument('--expanded',action='store_true');p.add_argument('--control',action='store_true');a=p.parse_args(argv)
    with tempfile.TemporaryDirectory()as tmp:
        xml=Path(tmp)/'g.xml';subprocess.run(['mutool','draw','-F','stext','-o',str(xml),a.pdf],check=True,capture_output=True);tree=load_glyphs(xml);check(tree,a.expanded)
        if a.control:controls(tree,a.expanded)
    return 0
if __name__=='__main__':raise SystemExit(main())
