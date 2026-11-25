"""Measure the bilingual fast services against their independently recorded scan readings."""

from opensiddur.importer.scan import pdf as measurements

import argparse
import copy
import json
import re
import subprocess
import tempfile
from pathlib import Path
from .check_pdf import MAX_BASELINE_DIFFERENCE, plain, load_glyphs
from .check_first_day_pdf import latin_note_runs
from opensiddur.importer.scan.pdf_direction import base
from opensiddur.common.constants import SOURCETEXTS_ROOT


def check(tree, day, source_root=SOURCETEXTS_ROOT, expanded=False):
    source=Path(source_root)/'asher_selichot/scan_reading'
    manifest=json.loads((source/(day+'.json')).read_text(encoding="utf-8"))
    units=[json.loads((source/name).read_text(encoding="utf-8"))for name in manifest['readings']]
    poem=next(u for u in units if u['kind']=='pizmon')
    he,en,headings=glyph_rows(tree)
    if not headings:
        raise ValueError('Fast service requires its one printed pizmon heading')
    deltas=[];previous=headings[-1]
    for stanza in poem['stanzas']:
        hwords=next(f['he']['text']for f in stanza['fragments']if f['he']['text']).split()
        ewords=next(f['en']['text']for f in stanza['fragments']if f['en']['text']).split()
        ha=''.join(base(c)or''for c in ' '.join(hwords[:2]))
        ea=plain(' '.join(ewords[:4]))
        h=next((r for r in he if ha in r[2]and r[:2]>previous),None)
        e=next((r for r in en if ea in r[2]and r[:2]>previous),None)
        if h is None or e is None:raise ValueError('Missing fast stanza: '+str((ha,ea)))
        if h[0]!=e[0]or abs(h[1]-e[1])>MAX_BASELINE_DIFFERENCE:raise ValueError('Misaligned fast stanza: '+str((h,e)))
        if not deltas and not any(r[0]==h[0]and r[1]<h[1]for r in headings):raise ValueError('Fast pizmon heading stranded')
        deltas.append(round(abs(h[1]-e[1]),2));previous=max(h[:2],e[:2])
    for chars in latin_note_runs(tree).values():
        xs=[float(c.get('x'))for c in chars]
        if any(b<a-.05 for a,b in zip(xs,xs[1:])):raise ValueError('Reversed fast Latin apparatus')
    text=plain(re.sub(r'(?<=\w)-\s+(?=\w)','',' '.join(''.join(c.get('c','')for font in line.findall('font')if float(font.get('size','100'))<=10 for c in font.findall('char')) for line in tree.findall('.//line'))))
    body=body_text(tree)
    notes=[(phrase,1) for phrase in ({'thursday-fast':['In rewarding the good','Viz., Ishmael.'],'last-monday-fast':['Ps. cii. 28.'],'tenth-tevet':['viz., The 8th, 9th, and 10th','Ptolomeus Philadelphus','The 9th of Tebeth','Ezekiel.','Ezek. xxiv. 1.','Tebeth is the tenth month','The daughter of Zion','Abi Sonoach','Nebusaradon.','Ezek. xxiv. 3.'],'esther-fast':['Haman.','See Deut. xxxi. 18.','Exod. xxx. 23.','Josh. v. 12.','Gen. iii. 11.','See Talmud Megillah, x.','Ezra iv. 6.','Megillah, xi. 2.','The following is an allegory','After his conference with Moses.','And might, therefore, be revoked','Thus far the legend taken from','In allusion to the gallows','i.e., the celebration of the festival','At the time of Manasseh','By Deut. xxv.','Mordecai and Esther.'],'tammuz-fast':['By a certain Appostemus','According to some this was done','In the time of the second temple.','See Taanith vi. 4.','According to a tradition','In allusion to Deut. i. 44.','See the preceding prayer.','The city being besieged','The King of Babylon.','Nebuchadnezzar and Sannacherib.','David.','Palestine.','Esau’s descendants.']}[day])]
    if day=='esther-fast':notes.append(('Ahasuerus.',2))
    if expanded:notes += [('Lev. xxvi',3),('Deut. xxx.',3),('Deut. iv.',2),('Isaiah xliv. 22.',1),('Isaiah xliii. 25.',1),('Isaiah i. 18.',1),('Isaiah lvi. 7.',1),('Ezek. xxxvi. 25.',2)]
    for fingerprint,count in notes:
        if text.count(fingerprint)!=count:raise ValueError('Fast footnote occurrence: '+fingerprint)
    if 'May the prayers and supplications' in body:raise ValueError('Unrequested Full Kaddish supplied')
    following={'thursday-fast':'LAST OF THE THREE FASTS','last-monday-fast':'FAST OF TEBETH','tenth-tevet':'FAST OF ESTHER','esther-fast':'FAST OF TAMMUZ','tammuz-fast':'DAY OF ATONEMENT'}[day]
    if following in body:raise ValueError('Following fast entered current service')
    if body.count('Prayers are said as on other week days')!=1:raise ValueError('Weekday Amidah performance rubric lost')
    if expanded:
        for cue in ['Say ', 'Continue from', 'Wherever the words', '(For thou art great, &c.)','(Israel is saved, &c.)']:
            if cue in (body.replace('Say unto Zion, arise;','') if day=='tammuz-fast' else body):raise ValueError('Fulfilled fast cue remains: '+cue)
        for phrase in ['The Reader continues the Ameedah','Conclude the service as on other week-days.']:
            if body.count(phrase)!=1:raise ValueError('Unsupplied performance instruction lost: '+phrase)
        if body.count('Omnipotent King, who')!=(2 if day=='esther-fast' else 3) or body.count('take us for thy heritage.')!=({'last-monday-fast':6,'esther-fast':3}.get(day,4)):raise ValueError('Fast prayer pair bounds changed')
    if day=='thursday-fast':
        if not expanded and (body.count('(For thou art great, &c.)')!=5 or body.count('(Israel is saved, &c.)')!=1):raise ValueError('Documentary fast cues changed')
        if body.count('Israel is saved by the Lord')!=(2 if expanded else 1):raise ValueError('Fast opening repeat count')
        if body.count('for thou art great in pardoning and full of compassion.')!=(7 if expanded else 2):raise ValueError('Fast full refrain count')
    elif day=='last-monday-fast':
        if body.count('(The Eternal, &c.)')!=(0 if expanded else 1):raise ValueError('Final Monday opening cue changed')
        if body.count('an Omnipotent God, merciful and gracious')!=(2 if expanded else 1):raise ValueError('Final Monday attributes count')
    if day=='tenth-tevet':
        # The printed unclosed cue is read corrected, closing the twelfth into a thirteenth.
        if body.count('(When, &c.)')!=(0 if expanded else 13):raise ValueError('Tevet closed cue count changed')
        if body.count('(When, &c.')!=(0 if expanded else 13):raise ValueError('Tevet cue count changed, including printed unclosed cue')
        if body.count('When our forefathers trusted')!=(13 if expanded else 1):raise ValueError('Tevet complete refrain count changed')
        if 'advanced towards the holy city' not in body:raise ValueError('Tevet facsimile word join lost')
    if day=='esther-fast':
        if body.count('We are but a few in number who implore thee')!=1:raise ValueError('Unprinted English refrain supplied')
        if expanded and '(We are but few, &c.)' in body:raise ValueError('Esther repeat instruction remains')
    if day=='tammuz-fast':
        if body.count('on the day, &c.')!=(0 if expanded else 1):raise ValueError('Tammuz short cue count changed')
        if body.count('on the day when the enemy prevailed and the city was taken.')!=(2 if expanded else 1):raise ValueError('Tammuz full refrain count changed')
        if body.count('on the day the enemy prevailed and the city was taken.')!=1:raise ValueError('Tammuz closing refrain variant changed')
        if 'dwelleth in heaven' not in body:raise ValueError('Tammuz facsimile word join lost')
    print(day+': '+str(len(notes))+' apparatus fingerprints; stanza start deltas '+str(deltas))
    return he,en


def controls(tree,day,source_root,expanded):
    check(tree,day,source_root,expanded)
    broken=copy.deepcopy(tree)
    fingerprint={'thursday-fast':'In rewarding the good','last-monday-fast':'Ps. cii. 28.','tenth-tevet':'The 9th of Tebeth','esther-fast':'After his conference with Moses.','tammuz-fast':'See the preceding prayer.'}[day]
    note=next(n for n in broken.findall('.//line')if fingerprint in n.get('text',''));note.getparent().remove(note)
    try:check(broken,day,source_root,expanded)
    except ValueError:pass
    else:raise AssertionError('Missing fast footnote escaped detection')
    broken=copy.deepcopy(tree);shifted=0
    manifest=json.loads((Path(source_root)/'asher_selichot/scan_reading'/(day+'.json')).read_text(encoding="utf-8"))
    poem=next(u for name in manifest['readings'] if (u:=json.loads((Path(source_root)/'asher_selichot/scan_reading'/name).read_text(encoding="utf-8")))['kind']=='pizmon')
    needle=plain(' '.join(poem['stanzas'][1]['fragments'][0]['en']['text'].split()[:4]))
    _,rows,heads=glyph_rows(tree)
    target=next((page,y)for page,y,words in rows if needle in words and (page,y)>heads[-1])
    for number,page in enumerate(broken.findall('page'),1):
        gutter=288 if number%2 else 324
        for c in page.findall('.//char'):
            if number==target[0] and round(float(c.get('y')),2)==target[1] and float(c.get('x'))>gutter:
                c.set('y',str(float(c.get('y'))+50));shifted+=1
    if not shifted:raise AssertionError('Fast control shifted no glyphs')
    try:check(broken,day,source_root,expanded)
    except ValueError:pass
    else:raise AssertionError('Shifted fast stanza escaped detection')
    print(day+': missing-note and shifted-stanza controls rejected')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('pdf');p.add_argument('--day',required=True,choices=['thursday-fast','last-monday-fast','tenth-tevet','esther-fast','tammuz-fast']);p.add_argument('--expanded',action='store_true');p.add_argument('--control',action='store_true');p.add_argument('--source-root',type=Path,default=SOURCETEXTS_ROOT);a=p.parse_args(argv)
    with tempfile.TemporaryDirectory()as tmp:
        xml=Path(tmp)/'glyphs.xml';subprocess.run(['mutool','draw','-F','stext','-o',str(xml),a.pdf],check=True,capture_output=True);tree=load_glyphs(xml);check(tree,a.day,a.source_root,a.expanded)
        if a.control:controls(tree,a.day,a.source_root,a.expanded)
    return 0


def _normalize(_form, text):
    return plain(text)


def glyph_rows(tree, minimum_font_size=None):
    return measurements.glyph_rows(tree, minimum_font_size, gutters=(288, 324),
                                   heading='פזמון', normalize=_normalize)


def body_text(tree):
    return measurements.body_text(tree, gutters=(288, 324), minimum_font_size=10,
                                  header_bottom=100, normalize=_normalize)

if __name__=='__main__':raise SystemExit(main())
