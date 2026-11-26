"""Verify encoded days, the contents page and the bookmark hierarchy."""

from opensiddur.importer.scan import pdf as measurements
from opensiddur.importer.scan.pdf import outline_rows

import argparse
import copy
import json
import re
from collections import Counter
from opensiddur.common.constants import SOURCETEXTS_ROOT
import subprocess
import tempfile
from pathlib import Path
from lxml import etree
from pypdf import PdfReader
from .check_pdf import MAX_BASELINE_DIFFERENCE, check as check_poem, controls as poem_controls, corrected, hebrew_rows, plain, load_glyphs
from .check_first_day_pdf import check as check_first, controls as first_controls, latin_note_runs


def day_bookmarks(rows, captions=("FIRST DAY", "SECOND DAY")):
    return measurements.day_bookmarks(rows, captions, child_caption='פזמון')


def check_contents(tree, rows, page_labels):
    return measurements.check_contents(tree, rows, page_labels,
                                       number_columns=(475, 511), caption='Contents')


def slice_day(tree, start, end=None, keep_titles=False, trailing_note_texts=(), prior_note_texts=()):
    return measurements.slice_day(tree, start, end, keep_titles, trailing_note_texts,
                                  prior_note_texts, title_pages=4, maximum_note_size=10,
                                  boundary_tolerance=2)


def second_day_check(tree, expanded):
    for chars in latin_note_runs(tree).values():
        xs=[float(c.get('x')) for c in chars]
        if any(b<a-0.05 for a,b in zip(xs,xs[1:])):
            raise ValueError('Reversed second-day Latin footnote')
    he,en=[],[]
    for number,page in enumerate(tree.findall('page'),1):
        gutter=288 if number%2 else 324
        he.extend((number,y,letters) for y,letters in hebrew_rows(page,gutter))
        for line in page.findall('.//line'):
            if plain(line.get('text','')).strip().isdigit():continue  # Reledmac line numbers are not prayer words.
            chars=line.findall('.//char')
            e=[c for c in chars if float(c.get('x'))>gutter]
            if e:en.append((number,float(e[0].get('y')),plain(''.join(c.get('c') for c in e))))
    anchors=[('ישראלנושע','Israel is saved'),('שעריך','They knock'),('פחודים','They are intimidated'),
             ('טובותיך','Anticipate them'),('יושעו','Let them be saved'),('הקשיבה','Attend, O Lord')]
    deltas=[];previous=(0,0)
    for ha,ea in anchors:
        h=next((r for r in he if ha in r[2] and r[:2]>=previous),None)
        e=next((r for r in en if ea in r[2] and r[:2]>=previous),None)
        if h is None or e is None:raise ValueError('Missing second-day stanza '+ha+' / '+ea)
        if h[0]!=e[0] or abs(h[1]-e[1])>MAX_BASELINE_DIFFERENCE:raise ValueError('Second-day stanza alignment failed: '+str((h,e)))
        deltas.append(round(abs(h[1]-e[1]),2));previous=max(h[:2],e[:2])
    text=plain(' '.join(l.get('text','') for l in tree.findall('.//line')))
    # The closing transclusion adds its own Deut. iv. 31 note in expanded output.
    # Two separate new notes deliberately have the same patriarchs wording.
    for phrase,count in [('Deut. iv. 31.',2 if expanded else 1),('Jacob.',1),('During the Crusades.',1),
                         ('The three patriarchs.',2),('In allusion to the mixed races',1),('Viz., Ishmael.',1)]:
        if text.count(phrase)!=count:raise ValueError('Second-day footnote occurrence: '+phrase)
    if 'THIRD DAY' in text:raise ValueError('Third-day material is outside the encoded boundary')
    body=' '.join(' '.join(r[2] for r in en).split())
    if expanded:
        for phrase in ['Say ', 'Conclude the Service', 'Wherever the words','(For thou art great,','(Israel is saved,']:
            if phrase in body:raise ValueError('Expanded second day retains a fulfilled cue: '+phrase)
        if body.count('Omnipotent King, who')!=3:raise ValueError('Second day requires three prayer-pair expansions')
        if body.count('May the prayers and supplications')!=1:raise ValueError('Second day requires one closing Full Kaddish')
    else:
        if 'Conclude the Service as on the first day' not in body:raise ValueError('Missing second-day closing rubric')
        if body.count('(For thou art great,')!=5:raise ValueError('Expected four printed refrain cues plus the rubric’s quoted cue')
    return deltas


def third_day_check(tree, expanded):
    for chars in latin_note_runs(tree).values():
        xs=[float(c.get('x')) for c in chars]
        if any(b<a-0.05 for a,b in zip(xs,xs[1:])):
            raise ValueError('Reversed third-day Latin footnote')
    he,en=[],[]
    for number,page in enumerate(tree.findall('page'),1):
        gutter=288 if number%2 else 324
        he.extend((number,y,letters) for y,letters in hebrew_rows(page,gutter))
        for line in page.findall('.//line'):
            if plain(line.get('text','')).strip().isdigit():continue  # Reledmac line numbers are not prayer words.
            chars=line.findall('.//char')
            e=[c for c in chars if float(c.get('x'))>gutter]
            if e:en.append((number,float(e[0].get('y')),plain(''.join(c.get('c') for c in e))))
    anchors=[('שחרקמתי','At dawn of day I'),('לפניםזאת','In former days'),('מזבח','While the altar'),
             ('הןבהיות','Lo, when the service'),('הןקדם','Formerly the clean priests'),('חזהקדוש','Behold, O most holy One')]
    deltas=[];previous=(0,0)
    for ha,ea in anchors:
        h=next((r for r in he if ha in r[2] and r[:2]>=previous),None)
        e=next((r for r in en if ea in r[2] and r[:2]>=previous),None)
        if h is None or e is None:raise ValueError('Missing third-day stanza '+ha+' / '+ea)
        if h[0]!=e[0] or abs(h[1]-e[1])>MAX_BASELINE_DIFFERENCE:raise ValueError('Third-day stanza alignment failed: '+str((h,e)))
        deltas.append(round(abs(h[1]-e[1]),2));previous=max(h[:2],e[:2])
    text=plain(' '.join(l.get('text','') for l in tree.findall('.//line')))
    for phrase,count in [('this prayer is intended for the Reader.',1),('During the crusades.',1),
                         ('The time of our redemption.',1),('our brethren in Palestine.',1),
                         ('Of the whole nation.',1),('before the destruction of the temple.',1),
                         ('See Joma ii. 2.',1),('Joma xxv.',1)]:
        if text.count(phrase)!=count:raise ValueError('Third-day footnote occurrence: '+phrase)
    if 'FOURTH DAY' in text:raise ValueError('Fourth-day material is outside the encoded boundary')
    body=' '.join(' '.join(r[2] for r in en).split())
    if expanded:
        for phrase in ['Say ', 'Conclude the Service', 'Wherever the words','(Let my life,','(At dawn of day &c.)']:
            if phrase in body:raise ValueError('Expanded third day retains a fulfilled cue: '+phrase)
        if body.count('Omnipotent King, who')!=3:raise ValueError('Third day requires three prayer-pair expansions')
        if body.count('May the prayers and supplications')!=1:raise ValueError('Third day requires one closing Full Kaddish')
    else:
        if 'Conclude the Service as on the first day' not in body:raise ValueError('Missing third-day closing rubric')
        if body.count('(Let my life,')!=5:raise ValueError('Expected four printed refrain cues plus the rubric’s quoted cue')
    return deltas


def numbered_day_check(tree, expanded, data, scope, asher_source=None):
    """Measure the independently recorded stanza anchors and printed apparatus."""
    he,en=[],[]
    for number,page in enumerate(tree.findall('page'),1):
        gutter=288 if number%2 else 324
        he.extend((number,y,letters) for y,letters in hebrew_rows(page,gutter))
        for line in page.findall('.//line'):
            if plain(line.get('text','')).strip().isdigit():continue
            chars=line.findall('.//char')
            e=[c for c in chars if float(c.get('x'))>gutter]
            if e:en.append((number,float(e[0].get('y')),plain(''.join(c.get('c') for c in e))))
    deltas=[];previous=(0,0)
    for anchor in scope['pizmon_stanza_anchors']:
        h=next((r for r in he if anchor['he'] in r[2] and r[:2]>=previous),None)
        e=next((r for r in en if anchor['en'] in r[2] and r[:2]>=previous),None)
        if h is None or e is None:raise ValueError('Missing numbered-day stanza '+str(anchor))
        if h[0]!=e[0] or abs(h[1]-e[1])>MAX_BASELINE_DIFFERENCE:raise ValueError('Numbered-day stanza alignment failed: '+str((h,e)))
        deltas.append(round(abs(h[1]-e[1]),2));previous=max(h[:2],e[:2])
    normalize=lambda s:' '.join(re.sub(r'-\s+','',re.sub(r'[\u0590-\u05ff]', '', plain(s))).split())
    text=normalize(' '.join(l.get('text','') for l in tree.findall('.//line')))
    notes=Counter(normalize(corrected(n['text'],asher_source) if asher_source else n['text']) for u in data['units'] for part in u.get('stanzas',[u]) for f in part['fragments'] for n in f['notes']['en'])
    for phrase,count in notes.items():
        if text.count(phrase)!=count:raise ValueError('Numbered-day footnote occurrence: '+phrase)
    for chars in latin_note_runs(tree).values():
        xs=[float(c.get('x')) for c in chars]
        if any(b<a-0.05 for a,b in zip(xs,xs[1:])):raise ValueError('Reversed numbered-day Latin footnote')
    body=normalize(' '.join(r[2] for r in en))
    if expanded:
        for phrase in ['Say ', 'Conclude the Service', 'Wherever the words', 'Wherever the word']:
            if phrase in body:raise ValueError('Expanded service retains a fulfilled cue: '+phrase)
        pair_count=sum(u['id'].endswith('prayer_cue') for u in data['units'])
        if body.count('Omnipotent King, who')!=pair_count:raise ValueError('Numbered-day prayer-pair expansion count')
        if body.count('May the prayers and supplications')!=1:raise ValueError('Numbered day requires one Full Kaddish')
    elif 'Conclude the Service as on the first day' not in body:
        raise ValueError('Missing numbered-day closing rubric')
    return deltas


def check_phrase_dots(tree):
    """A wrapped Hebrew verse must not leave its terminal phrase dot alone."""
    for number,page in enumerate(tree.findall('page'),1):
        gutter=288 if number%2 else 324
        for line in page.findall('.//line'):
            left=''.join(c.get('c','') for c in line.findall('.//char')
                         if float(c.get('x'))<gutter).strip()
            if any(c in '·∙' for c in left) and all(c.isspace() or c.isdigit() or c in '·∙' for c in left):
                raise ValueError('Stranded Hebrew phrase dot on PDF page '+str(number))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf',type=Path);parser.add_argument('--expanded',action='store_true');parser.add_argument('--control',action='store_true')
    parser.add_argument('--source-root',type=Path,default=SOURCETEXTS_ROOT)
    args=parser.parse_args(argv)
    reader=PdfReader(args.pdf);rows=outline_rows(reader)
    captions=[word+' DAY' for word in ['FIRST','SECOND','THIRD','FOURTH','FIFTH','SIXTH','SEVENTH'] if any(word+' DAY' in r[1] for r in rows)]
    if any('DAY BEFORE NEW YEAR' in r[1] for r in rows):captions.append('DAY BEFORE NEW YEAR')
    if any('FAST OF GEDALIAH' in r[1] for r in rows):captions.append('FAST OF GEDALIAH')
    if any('2nd OF THE PENITENTIAL DAYS' in r[1] for r in rows):captions.append('2nd OF THE PENITENTIAL DAYS')
    for caption in ['3rd OF THE PENITENTIAL DAYS','FOURTH OF THE PENITENTIAL DAYS','FIFTH OF THE PENITENTIAL DAYS','DAY BEFORE THE DAY OF ATONEMENT','SECOND FAST','FIFTH FAST','LAST OF THE THREE FASTS','FAST OF TEBETH','FAST OF ESTHER','FAST OF TAMMUZ','PRAYERS FOR THE DAY BEFORE NEW MOON']:
        if any(caption in r[1] for r in rows):captions.append(caption)
    days=day_bookmarks(rows,captions)
    final=[r for r in rows if r[0]==0 and 'SAID AT CIRCUMCISIONS' in r[1]]
    if final:
        if len(final)!=1:raise ValueError('Final circumcision section requires one bookmark')
        days.extend(final)
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'text.xml'
        subprocess.run(['mutool','draw','-F','stext','-o',str(path),str(args.pdf)],check=True,capture_output=True)
        tree=load_glyphs(path)
        text=' '.join(l.get('text','') for l in tree.findall('.//line'))
        if 'Contents' not in text:raise ValueError('Missing generated contents page')
        check_contents(tree,rows,reader.page_labels)
        check_phrase_dots(tree)
        first=slice_day(tree,days[0],days[1],keep_titles=True);second=slice_day(tree,days[1],days[2] if len(days)>2 else None)
        third=slice_day(tree,days[2],days[3] if len(days)>3 else None) if len(days)>2 else None
        first_deltas=check_first(first,complete=True,expanded=args.expanded)
        poem_deltas=check_poem(first,args.expanded,complete=True)
        second_deltas=second_day_check(second,args.expanded)
        third_deltas=third_day_check(third,args.expanded) if third is not None else []
        later_deltas={}
        def note_openings(day_name):
            # A note's opening words, up to any Hebrew, identify its apparatus line wherever the
            # page puts it: a day's last notes can fall below the next day's heading.
            path=args.source_root/'asher_selichot'/'scan_reading'/(day_name+'-day.json')
            if not path.exists():return ()
            day=json.loads(path.read_text(encoding="utf-8"))
            openings=(re.split(r'[\u0590-\u05ff]',n['text'])[0].strip()[:25] for u in day['units']
                      for part in u.get('stanzas',[u]) for f in part['fragments'] for n in f['notes']['en'])
            return tuple(o for o in openings if len(o)>=8)
        for i,day_name in enumerate(['fourth','fifth','sixth','seventh'],3):
            if i>=len(days):break
            source=args.source_root/'asher_selichot'
            data=json.loads((source/'scan_reading'/(day_name+'-day.json')).read_text(encoding="utf-8"))
            scope=json.loads((source/(day_name+'-day-scope.json')).read_text(encoding="utf-8"))
            previous=['third','fourth','fifth','sixth'][i-3]
            portion=slice_day(tree,days[i],days[i+1] if i+1<len(days) else None,
                              trailing_note_texts=note_openings(day_name),prior_note_texts=note_openings(previous))
            later_deltas[day_name]=numbered_day_check(portion,args.expanded,data,scope,source)
            if args.control:
                broken=copy.deepcopy(portion)
                phrase=next(n['text'] for u in data['units'] for part in u.get('stanzas',[u]) for f in part['fragments'] for n in f['notes']['en'])
                fingerprint=' '.join(re.sub(r'[\u0590-\u05ff]', '', phrase).split())[:25]
                line=next(l for l in broken.findall('.//line') if fingerprint in plain(l.get('text','')))
                duplicate=copy.deepcopy(line);duplicate.set('text',phrase)
                line.getparent().append(duplicate)
                try:numbered_day_check(broken,args.expanded,data,scope,source)
                except ValueError:pass
                else:raise AssertionError('Duplicate numbered-day note escaped detection')
                broken=copy.deepcopy(portion);anchor=scope['pizmon_stanza_anchors'][1]['en']
                for number,page in enumerate(broken.findall('page'),1):
                    for line in page.findall('.//line'):
                        if anchor in plain(line.get('text','')):
                            for char in line.findall('.//char'):
                                if float(char.get('x'))>(288 if number%2 else 324):
                                    char.set('y',str(float(char.get('y'))+50))
                try:numbered_day_check(broken,args.expanded,data,scope,source)
                except ValueError:pass
                else:raise AssertionError('Shifted numbered-day stanza escaped detection')
        if len(days)>7:
            from .check_erev_pdf import check as erev_check, controls as erev_controls
            erev_portion=slice_day(tree,days[7],days[8] if len(days)>8 else None)
            erev_check(erev_portion,args.expanded)
            if args.control:erev_controls(erev_portion,args.expanded)
        if len(days)>8:
            from .check_gedaliah_pdf import check as gedaliah_check, controls as gedaliah_controls
            gedaliah_portion=slice_day(tree,days[8],days[9] if len(days)>9 else None,
                                       trailing_note_texts=('עשרה הרוגי מלכות',))
            gedaliah_check(gedaliah_portion,args.expanded)
            if args.control:gedaliah_controls(gedaliah_portion,args.expanded)
        if len(days)>9:
            from .check_penitential_pdf import check as penitential_check, controls as penitential_controls
            portion=slice_day(tree,days[9],days[10] if len(days)>10 else None,
                              trailing_note_texts=('With reference to Ps. xlii. 9.',),
                              prior_note_texts=('עשרה הרוגי מלכות',))
            penitential_check(portion,args.expanded)
            if args.control:penitential_controls(portion,args.expanded)
        if len(days)>10:
            from .check_penitential_third_pdf import check as third_penitential_check, controls as third_penitential_controls
            third_last_notes=('Joseph. (Deut. xxxiii. 17.)', 'Ezek. xxxiv. 31.',
                              'Exod. xix. 4.', 'Names of angels.')
            portion=slice_day(tree,days[10],days[11] if len(days)>11 else None,
                              trailing_note_texts=third_last_notes,
                              prior_note_texts=('With reference to Ps. xlii. 9.',))
            third_penitential_check(portion,args.expanded)
            if args.control:third_penitential_controls(portion,args.expanded)
        if len(days)>11:
            from .check_penitential_fourth_pdf import check as fourth_penitential_check, controls as fourth_penitential_controls
            portion=slice_day(tree,days[11],days[12] if len(days)>12 else None,
                              prior_note_texts=third_last_notes)
            fourth_penitential_check(portion,args.expanded)
            if args.control:fourth_penitential_controls(portion,args.expanded)
        if len(days)>12:
            from .check_penitential_fifth_pdf import check as fifth_penitential_check, controls as fifth_penitential_controls
            portion=slice_day(tree,days[12],days[13] if len(days)>13 else None)
            fifth_penitential_check(portion,args.expanded)
            if args.control:fifth_penitential_controls(portion,args.expanded)
        if len(days)>13:
            from .check_erev_yom_kippur_pdf import check as yk_check, controls as yk_controls
            portion=slice_day(tree,days[13],days[14] if len(days)>14 else None, trailing_note_texts=('Ezek. xxxvi. 25.',))
            yk_check(portion,args.expanded)
            if args.control:yk_controls(portion,args.expanded)
        if len(days)>14:
            from .check_monday_fast_pdf import check as monday_check, controls as monday_controls
            portion=slice_day(tree,days[14],days[15] if len(days)>15 else None,
                              prior_note_texts=('Ezek. xxxvi. 25.',), trailing_note_texts=('Ezek. xxxvi. 25.',))
            monday_check(portion,args.expanded)
            if args.control:monday_controls(portion,args.expanded)
        if len(days)>15:
            from .check_fast_pdf import check as fast_check, controls as fast_controls
            portion=slice_day(tree,days[15],days[16] if len(days)>16 else None,
                              prior_note_texts=('Ezek. xxxvi. 25.',),
                              trailing_note_texts=('Viz., Ishmael. See Gen. xxviii. 9.',))
            fast_check(portion,'thursday-fast',args.source_root,args.expanded)
            if args.control:fast_controls(portion,'thursday-fast',args.source_root,args.expanded)
        if len(days)>16:
            from .check_fast_pdf import check as fast_check, controls as fast_controls
            portion=slice_day(tree,days[16],days[17] if len(days)>17 else None,
                              prior_note_texts=('Viz., Ishmael. See Gen. xxviii. 9.',))
            fast_check(portion,'last-monday-fast',args.source_root,args.expanded)
            if args.control:fast_controls(portion,'last-monday-fast',args.source_root,args.expanded)
        if len(days)>17:
            from .check_fast_pdf import check as fast_check, controls as fast_controls
            portion=slice_day(tree,days[17],days[18] if len(days)>18 else None)
            fast_check(portion,'tenth-tevet',args.source_root,args.expanded)
            if args.control:fast_controls(portion,'tenth-tevet',args.source_root,args.expanded)
        if len(days)>18:
            from .check_fast_pdf import check as fast_check, controls as fast_controls
            portion=slice_day(tree,days[18],days[19] if len(days)>19 else None)
            fast_check(portion,'esther-fast',args.source_root,args.expanded)
            if args.control:fast_controls(portion,'esther-fast',args.source_root,args.expanded)
        if len(days)>19:
            portion=slice_day(tree,days[19],days[20] if len(days)>20 else None)
            fast_check(portion,'tammuz-fast',args.source_root,args.expanded)
            if args.control:fast_controls(portion,'tammuz-fast',args.source_root,args.expanded)
        if len(days)>20:
            from .check_yom_kippur_katan_pdf import check as monthly_check,controls as monthly_controls
            portion=slice_day(tree,days[20],days[21] if len(days)>21 else None)
            monthly_check(portion,args.source_root,args.expanded)
            if args.control:monthly_controls(portion,args.source_root,args.expanded)
        if len(days)>21:
            from .check_circumcision_pdf import check as final_check, controls as final_controls
            portion=slice_day(tree,days[21])
            final_check(portion,args.expanded)
            if args.control:final_controls(portion,args.expanded)
        if args.control:
            broken_dot=copy.deepcopy(tree)
            line=etree.SubElement(broken_dot.find('page'),'line')
            etree.SubElement(line,'char',c='∙',x='150',y='150')
            try:check_phrase_dots(broken_dot)
            except ValueError:pass
            else:raise AssertionError('Stranded phrase-dot control escaped detection')
            broken=copy.deepcopy(tree)
            toc=next(p for p in broken.findall('page') if any('Contents' in l.get('text','') for l in p.findall('.//line')))
            digit=next(c for c in toc.findall('.//char') if c.get('c','').isdigit() and float(c.get('x'))>=475)
            digit.set('c','9' if digit.get('c')!='9' else '8')
            try:check_contents(broken,rows,reader.page_labels)
            except ValueError:pass
            else:raise AssertionError('Stale TOC page escaped detection')
            first_controls(first,complete=True,expanded=args.expanded);poem_controls(first,args.expanded,complete=True)
            broken=[(1 if 'SECOND DAY' in r[1] else r[0],*r[1:]) for r in rows]
            try:day_bookmarks(broken)
            except ValueError:pass
            else:raise AssertionError('Wrong bookmark depth escaped detection')
            broken=copy.deepcopy(second)
            note=next(l for l in broken.findall('.//line') if 'Viz., Ishmael.' in l.get('text',''))
            note.getparent().append(copy.deepcopy(note))
            try:second_day_check(broken,args.expanded)
            except ValueError:pass
            else:raise AssertionError('Duplicate second-day note escaped detection')
            broken=copy.deepcopy(second)
            for number,page in enumerate(broken.findall('page'),1):
                gutter=288 if number%2 else 324
                for line in page.findall('.//line'):
                    if 'They knock' in plain(line.get('text','')):
                        for char in line.findall('.//char'):
                            if float(char.get('x'))>gutter:char.set('y',str(float(char.get('y'))+50))
            try:second_day_check(broken,args.expanded)
            except ValueError:pass
            else:raise AssertionError('Shifted second-day stanza escaped detection')
        if args.control and third is not None:
            broken=copy.deepcopy(third)
            note=next(l for l in broken.findall('.//line') if 'Of the whole nation.' in l.get('text',''))
            note.getparent().append(copy.deepcopy(note))
            try:third_day_check(broken,args.expanded)
            except ValueError:pass
            else:raise AssertionError('Duplicate third-day note escaped detection')
            broken=copy.deepcopy(third)
            for number,page in enumerate(broken.findall('page'),1):
                gutter=288 if number%2 else 324
                for line in page.findall('.//line'):
                    if 'In former days' in plain(line.get('text','')):
                        for char in line.findall('.//char'):
                            if float(char.get('x'))>gutter:char.set('y',str(float(char.get('y'))+50))
            try:third_day_check(broken,args.expanded)
            except ValueError:pass
            else:raise AssertionError('Shifted third-day stanza escaped detection')
        print(f'{len(reader.pages)} pages; contents generated; day bookmarks above pizmons; first-day prayers {first_deltas}; first pizmon {poem_deltas}; second pizmon {second_deltas}; third pizmon {third_deltas}; later pizmons {later_deltas}; footnotes and expansion boundaries checked; controls={args.control}')
    return 0


if __name__=='__main__':raise SystemExit(main())
