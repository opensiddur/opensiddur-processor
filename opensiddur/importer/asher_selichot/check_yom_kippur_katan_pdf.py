"""Measure monthly-service stanzas, apparatus and independently placed repeat cues."""
import argparse,copy,json,re,subprocess,tempfile
from pathlib import Path
from opensiddur.common.constants import SOURCETEXTS_ROOT
from opensiddur.importer.scan.pdf_direction import base
from .check_fast_pdf import glyph_rows,body_text
from .check_pdf import MAX_BASELINE_DIFFERENCE, corrected, plain, load_glyphs
from opensiddur.importer.scan.pdf import strip_numeric_markers
from .check_first_day_pdf import latin_note_runs


def check(tree,source_root=SOURCETEXTS_ROOT,expanded=False):
    source=Path(source_root)/'asher_selichot/scan_reading';manifest=json.loads((source/'yom-kippur-katan.json').read_text(encoding="utf-8"))
    units=[json.loads((source/name).read_text(encoding="utf-8")) for name in manifest['readings']]
    he,_,headings=glyph_rows(tree)
    en=glyph_rows(tree,minimum_font_size=10)[1];deltas=[]
    for poem in [u for u in units if u['kind']=='pizmon']:
        previous=(0,0)
        for stanza in poem['stanzas']:
            hwords=next(f['he']['text'] for f in stanza['fragments'] if f['he']['text']).split()
            ewords=next(f['en']['text'] for f in stanza['fragments'] if f['en']['text']).split()
            ha=''.join(base(c) or '' for c in ' '.join(hwords[:4]))
            # Repeated English invocations need the distinguishing patriarch clause.
            ea=plain(' '.join(ewords[:12 if poem['id']=='rahmana_adkar_lan' else 4]))
            h=None
            hcandidates=[r for r in he if r[:2]>previous]
            for index,row in enumerate(hcandidates):
                if ''.join(base(c) or '' for c in ' '.join(hwords[:2])) not in row[2]:continue
                combined=''.join(r[2] for r in hcandidates[index:index+3] if r[0]==row[0])
                if ha in combined:h=row;break
            candidates=[r for r in en if r[:2]>previous]
            e=None
            for index,row in enumerate(candidates):
                if plain(' '.join(ewords[:4])) not in row[2]:continue
                combined=strip_numeric_markers(re.sub(r'(?<=\w)-\s+(?=\w)','',' '.join(r[2] for r in candidates[index:index+3] if r[0]==row[0])))
                if ea in combined:e=row;break
            if h is None or e is None:raise ValueError('Missing monthly-service stanza: '+str((poem['id'],ha,ea)))
            if h[0]!=e[0] or abs(h[1]-e[1])>MAX_BASELINE_DIFFERENCE:raise ValueError('Monthly stanza misalignment: '+str((h,e)))
            deltas.append(round(abs(h[1]-e[1]),2));previous=max(h[:2],e[:2])
    for chars in latin_note_runs(tree).values():
        xs=[float(c.get('x')) for c in chars]
        if any(b<a-.05 for a,b in zip(xs,xs[1:])):raise ValueError('Reversed monthly-service apparatus')
    normalize=lambda text:strip_numeric_markers(plain(re.sub(r'(?<=\w)-\s+(?=\w)','',' '.join(text.split()))))
    apparatus=normalize(' '.join(''.join(c.get('c','') for font in line.findall('font') if float(font.get('size','100'))<=10 for c in font.findall('char')) for line in tree.findall('.//line')))
    notes=[corrected(n['text'],source.parent) for u in units for f in u['fragments'] for n in f['notes']['en']]
    for note in notes:
        if apparatus.count(normalize(note))!=1:raise ValueError('Monthly-service note occurrence: '+note)
    body=body_text(tree)
    for phrase in ['Say once','Say twice','Say seven times','The Ark is opened.','The Ark is closed.','After the repetition thereof']:
        if phrase not in body:raise ValueError('Monthly performance instruction lost: '+phrase)
    for cue,count in [('(Let, &c.)',4),('(Let the weight, &c.)',1),('(So let it be, &c.)',5),('for his sake, &c.',8)]:
        if body.count(cue)!=(0 if expanded else count):raise ValueError('Monthly refrain cue count changed: '+cue)
    for refrain,count in [('Let the weight of my sins be this day',5),('So let it be counted to us when we offer prayers instead of meat-offering!',5),('for his sake he will forgive.',9)]:
        if body.count(refrain)!=((count if expanded else 1)+(1 if refrain=='for his sake he will forgive.' else 0)):raise ValueError('Monthly refrain expansion changed: '+refrain)
    for cue in ['Say from “Like a father','Say “Omnipotent King','Say “We have trespassed','Say “It is incumbent']:
        if expanded and cue in body:raise ValueError('Fulfilled monthly cue remains: '+cue)
    if expanded:
        if body.count('Omnipotent King, who')!=5:raise ValueError('Monthly prayer-pair count changed')
        if body.count('May the prayers and supplications')!=1:raise ValueError('Monthly Full Kaddish missing or repeated')
        if 'Mourner.' not in body:raise ValueError('Monthly Mourner performance role lost')
    # The English petition rubric interrupts Samar at its facsimile break.
    start=body.index('Remember the bull') if 'Remember the bull' in body else body.index('Remember the')
    if 'Remember the bull' in body:raise ValueError('Monthly interleaved rubric omitted')
    middle=body.find('Like a father' if expanded else 'Say from “Like a father',start)
    end=body.find('bull whose blood',start)
    if not start<middle<end:raise ValueError('Monthly interleaved rubric moved out of source position')
    if 'When a Circumcision' in body:raise ValueError('Following circumcision poem entered monthly service')
    print('Yom Kippur Katan: '+str(len(notes))+' source notes; '+str(len(deltas))+' stanza deltas '+str(deltas))
    return he,en


def controls(tree,source_root,expanded):
    check(tree,source_root,expanded)
    broken=copy.deepcopy(tree)
    note=next(n for n in broken.findall('.//line') if 'A Hebrewism' in n.get('text',''));note.getparent().remove(note)
    try:check(broken,source_root,expanded)
    except ValueError:pass
    else:raise AssertionError('Deleted monthly footnote escaped detection')
    broken=copy.deepcopy(tree);_,rows,_=glyph_rows(tree)
    page,y=next((p,y) for p,y,t in rows if 'The faithful prince' in t)
    for number,p in enumerate(broken.findall('page'),1):
        gutter=288 if number%2 else 324
        for c in p.findall('.//char'):
            if number==page and round(float(c.get('y')),2)==y and float(c.get('x'))>gutter:c.set('y',str(float(c.get('y'))+50))
    try:check(broken,source_root,expanded)
    except ValueError:pass
    else:raise AssertionError('Shifted monthly stanza escaped detection')
    print('Yom Kippur Katan: missing-note and shifted-stanza controls rejected')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('pdf');p.add_argument('--source-root',type=Path,default=SOURCETEXTS_ROOT);p.add_argument('--expanded',action='store_true');p.add_argument('--control',action='store_true');a=p.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        xml=Path(tmp)/'g.xml';subprocess.run(['mutool','draw','-F','stext','-o',str(xml),a.pdf],check=True,capture_output=True);tree=load_glyphs(xml);check(tree,a.source_root,a.expanded)
        if a.control:controls(tree,a.source_root,a.expanded)
    return 0
if __name__=='__main__':raise SystemExit(main())
