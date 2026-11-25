"""The complete image-read second penitential day service, printed 104–115 (n209–n232)."""
from opensiddur.importer.scan.authoring import printed_text

from opensiddur.importer.scan.authoring import wrap_hebrew

import copy
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from lxml import etree
from .build import TEI, XML, PRAYER, document, element, pb, marker, choice, spelled_name, spelled_urn
from .first_day import poetic_lines, words_with_notes, mixed_words, expansion_scope, append_words, verify_half_kaddish
from .erev_rosh_hashanah import printed as ordinary_printed, targets
from .identities import project_name
from .printings import is_declaration, printing

PENITENTIAL_SECOND_DAY = 'urn:x-opensiddur:text:siddur:selichot/penitential_second_day'
J = 'http://jewishliturgy.org/ns/jlptei/2'


def verify_compiled(tree):
    """The four page-52 petition lists remain aligned to their English ranges."""
    ns='http://jewishliturgy.org/ns/processing'
    seen=[]
    for block in tree.findall('.//{'+ns+'}parallel'):
        primary=block.find('{'+ns+'}parallelItem[@role="primary"]')
        if primary is None:continue
        markers=[n.get('corresp') for n in primary.findall('.//{'+TEI+'}milestone')
                 if (n.get('corresp') or '').startswith(PENITENTIAL_SECOND_DAY+'/verses_after_') and n.get('corresp').endswith('/expanded')]
        if not markers:continue
        parallel=block.find('{'+ns+'}parallelItem[@role="parallel"]')
        if parallel is None:raise ValueError('Missing bilingual second penitential day petition expansion')
        english=' '.join(''.join(parallel.itertext()).split())
        if not all(word in english for word in ['Thy mercy is great', 'Like a father hath compassion', 'for we do not presume', 'for thy own sake']):
            raise ValueError('second penitential day petition expansion paired with unrelated English')
        if markers!=[n.get('corresp') for n in parallel.findall('.//{'+TEI+'}milestone') if n.get('corresp') in markers]:
            raise ValueError('second penitential day expanded petition alignment identity differs')
        seen.extend(markers)
    if len(seen)!=4 or len(set(seen))!=4:raise ValueError('Missing or duplicate second penitential day petition passages')
    service=tree.find('.//{'+ns+'}transclude[@target="'+PENITENTIAL_SECOND_DAY+'"]')
    verify_half_kaddish(service, ten_days=True)
    kaddish=service.findall('.//{'+ns+'}transclude[@target="'+PRAYER+'kaddish/shalem"]') if service is not None else []
    if len(kaddish)!=1:raise ValueError('Missing or duplicate second penitential day Full Kaddish')
    words=''.join(''.join(n.itertext()) for n in kaddish[0].findall('.//{'+ns+'}parallelItem[@role="primary"]'))
    letters=''.join(c for c in unicodedata.normalize('NFD',words) if '\u05d0'<=c<='\u05ea')
    if letters.count('לעלאלעלאמןכלברכתא')!=1:raise ValueError('second penitential day Full Kaddish lost its Ten Days reading')
    if 'During the Ten Days of Repentance, add' in ''.join(kaddish[0].itertext()):raise ValueError('Fulfilled secondary Kaddish rubric remains')
    print('Compiled second penitential day: four bilingual petition expansions, Ten Days Full Kaddish and omitted fulfilled rubric checked')


def readings(source):
    manifest = json.loads((source/'penitential-second-day.json').read_text())
    units = [json.loads((source/name).read_text()) for name in manifest['readings']]
    if not manifest['complete'] or units[0]['id'] != 'opening_instruction' or units[-1]['id'] != 'conclusion':
        raise ValueError('second penitential day reading boundaries are incomplete')
    for lang,start in [('he',210),('en',211)]:
        pages=[int(f[lang]['scan'][1:]) for u in units for f in u['fragments'] if f[lang]['text']]
        if pages != sorted(pages) or set(pages) != set(range(start,234,2)):
            raise ValueError('second penitential day must cover every source page in verified order')
    return manifest,units


def pizmon(parent, reading, lang, context):
    """Keep the Hebrew-only internal cue in the combined surety/petition unit."""
    unit=element(parent,'div',corresp=context)
    first=reading['fragments'][0][lang];pb(unit,first['scan'],first['printed_page'])
    previous=first['scan']
    cue_pattern=r'בין כסה(?: וכו׳)?' if lang=='he' else r'\(Between, &c\.\)'
    for number,stanza in enumerate(reading['stanzas'],1):
        fragments=stanza['fragments'];first=fragments[0][lang]
        if first['scan']!=previous:pb(unit,first['scan'],first['printed_page'])
        marker(unit,context+'/stanza_'+str(number))
        block=element(unit,'lg' if lang=='he' else 'p')
        if lang=='he':
            # One call retains an unfinished verse across the printed page break.
            prepared=copy.deepcopy(fragments);cues=[]
            def cue_token(match):
                cues.append(match.group(0))
                return '__CUE_'+str(len(cues)-1)+'__|'
            for fragment in prepared:
                fragment['he']['text']=re.sub(cue_pattern,cue_token,fragment['he']['text'])
            poetic_lines(block,prepared,{'line_stops':'·׃|'})
            for line in block.findall(f'{{{TEI}}}l'):
                if line.text and re.fullmatch(r'__CUE_\d+__\|',line.text):
                    cue=cues[int(line.text.split('_')[3])];line.text=None
                    choice(element(line,'seg',type='refrain'),cue,reading['refrain'][lang])
        else:
            for index,fragment in enumerate(fragments):
                data=fragment[lang]
                if index:pb(block,data['scan'],data['printed_page'])
                for piece in re.split('('+cue_pattern+')',data['text']):
                    if not piece:continue
                    if re.fullmatch(cue_pattern,piece):
                        choice(element(block,'seg',type='refrain'),piece,reading['refrain'][lang])
                    else:words_with_notes(block,piece,fragment['notes'][lang],lang)
                    append_words(block,' ')
        previous=fragments[-1][lang]['scan']
        if lang=='he' and number==1:
            for line in block.findall(f'{{{TEI}}}l'):
                if line.text:
                    words=line.text;line.text=None;children=list(line)
                    segment=element(line,'seg',words,type='refrain')
                    for child in children:segment.append(child)
        block.tail=' '
    element(unit,'milestone',unit='stanza')
    return unit


def printed(parent,reading,lang,context):
    if reading['kind']=='pizmon':return pizmon(parent,reading,lang,context)
    reading=copy.deepcopy(reading)
    if reading['kind']=='poem':reading['line_stops']='·׃'
    unit=ordinary_printed(parent,reading,lang,context)
    if reading['id']=='shaarei_shamayim' and lang=='he':
        for line in unit.findall(f'.//{{{TEI}}}l'):
            if line.text and line.text.startswith('וְתַעַל'):
                words=line.text;line.text=None;element(line,'seg',words,type='refrain')
    if lang=='en':wrap_hebrew(unit)
    return unit


def full_kaddish(parent):
    declaration=element(parent,'j:declare');declaration.set(XML+'id','penitential_second_day_kaddish')
    for typ,name,value in [('asher:selichot','first_day','false'),('opensiddur:holiday-aggregate','aseret-ymei-tshuva','true')]:
        fs=element(declaration,'fs',type=typ);f=element(fs,'f');f.set('name',name);element(f,'binary',value=value)
    element(parent,'j:transclude',target=PRAYER+'kaddish/shalem')
    element(parent,'j:endDeclare',target='#penitential_second_day_kaddish')


def expanded_rubric(parent,reading,lang):
    if reading['id'].startswith('verses_after_'):
        # As on Erev, the two language lists belong to one paired prose block.
        div=element(parent,'div');element(div,'milestone',unit='prayer',corresp=PENITENTIAL_SECOND_DAY+'/'+reading['id']+'/expanded')
        block=element(div,'p')
        for target in targets(reading,lang):element(block,'j:transclude',target=target,type='inline').tail=' '
        element(div,'milestone',unit='prayer')
    else:
        opening=reading['id']=='opening_instruction'
        if opening:
            declaration=element(parent,'j:declare');declaration.set(XML+'id','penitential_second_day_opening_ten_days')
            fs=element(declaration,'fs',type='opensiddur:holiday-aggregate')
            feature=element(fs,'f');feature.set('name','aseret-ymei-tshuva');element(feature,'binary',value='true')
        for target in targets(reading,lang):
            if reading.get('supply_kaddish') and target==PRAYER+'kaddish/shalem':full_kaddish(parent)
            else:element(parent,'j:transclude',target=target)
        if opening:element(parent,'j:endDeclare',target='#penitential_second_day_opening_ten_days')
        # Preserve any printed apparatus attached to a fulfilled instruction.
        for note in reading['fragments'][0]['notes'][lang]:
            block=element(element(parent,'div'),'p');node=element(block,'note',type='commentary')
            node.set(XML+'lang',note.get('language',lang));node.text=note['text']


def documents(source):
    manifest,units=readings(source)
    for lang in ['he','en']:
        project=project_name(lang)
        root,text=document(lang,project,manifest['heading'][lang],PENITENTIAL_SECOND_DAY)
        service=element(element(text,'body'),'div',corresp=PENITENTIAL_SECOND_DAY)
        first=units[0]['fragments'][0][lang];pb(service,first['scan'],first['printed_page'])
        element(service,'head',manifest['heading'][lang])
        for reading in units:
            context=reading.get('urn',PENITENTIAL_SECOND_DAY+'/'+reading['id'])
            if reading.get('filename'):
                module,body=document(lang,project,reading['filename'].replace('_',' '),context)
                printed(element(body,'body'),reading,lang,context)
                yield project,reading['filename']+'.xml',module
                element(service,'j:transclude',target=context)
            elif reading['kind']=='rubric' and (targets(reading,lang) or reading.get('refrain_instruction')):
                unit=element(service,'div',corresp=context)
                if reading.get('heading_before',{}).get(lang):element(unit,'head',reading['heading_before'][lang])
                feature='refrains_present' if reading.get('refrain_instruction') else 'prayers_present'
                stem='penitential_second_day_'+reading['id']
                expansion_scope(unit,stem+'_printed',False,feature=feature)
                printed(unit,reading,lang,context+'/printed');element(unit,'j:endConditional',target='#'+stem+'_printed')
                if not reading.get('refrain_instruction'):
                    expansion_scope(unit,stem+'_expanded',True,feature=feature)
                    expanded_rubric(unit,reading,lang);element(unit,'j:endConditional',target='#'+stem+'_expanded')
            else:printed(service,reading,lang,context)
        yield project,'penitential_second_day.xml',root


def verify_evidence(source,units):
    records=json.loads((source.parent/'penitential-second-day-proofreading.json').read_text())['readings']
    if [r['id'] for r in records]!=[u['id'] for u in units]:raise ValueError('Stale second penitential day proofreading scope')
    for r in records:
        for key,prefix in [('initial_sha256','initial/'),('assembled_sha256','assembled-first-pass/'),('working_sha256','')]:
            path=source/'penitential-second-day'/(prefix+r['id']+'.json')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=r[key]:raise ValueError('Stale second penitential day evidence: '+r['id'])


def verify_readings(source,project_directory):
    from opensiddur.importer.scan.reverse import streams,check
    normalize=lambda s:' '.join(unicodedata.normalize('NFKD',s).split())
    manifest,units=readings(source);verify_evidence(source,units)
    for lang in ['he','en']:
        project=project_directory/project_name(lang)
        service=etree.parse(str(project/'penitential_second_day.xml')).find(f'.//{{{TEI}}}body/{{{TEI}}}div')
        if normalize(service.find(f'{{{TEI}}}head').text)!=normalize(manifest['heading'][lang]):raise ValueError('second penitential day heading changed')
        nodes=[n for n in service if n.tag not in [f'{{{TEI}}}head',f'{{{TEI}}}pb'] and not is_declaration(n)]
        if len(nodes)!=len(units):raise ValueError('second penitential day source order changed')
        for reading,node in zip(units,nodes):
            context=spelled_urn(reading.get('urn',PENITENTIAL_SECOND_DAY+'/'+reading['id']))
            if reading.get('filename'):
                if node.get('target')!=context:raise ValueError('second penitential day module order changed')
                node=printing(project,spelled_name(reading['filename']))
            elif node.get('corresp')!=context:raise ValueError('second penitential day inline order changed')
            node=copy.deepcopy(node)
            scopes=node.findall(f'{{{J}}}conditional')
            if scopes:
                if [s.find(f'{{{TEI}}}fs/{{{TEI}}}f/{{{TEI}}}binary').get('value') for s in scopes]!=(['false'] if reading.get('refrain_instruction') else ['false','true']):raise ValueError('second penitential day expansion polarity changed')
                if len(scopes)==2:
                    if [n.get('target') for n in node.findall(f'.//{{{J}}}transclude')]!=[spelled_urn(t) for t in targets(reading,lang)]:raise ValueError('second penitential day expansion range changed')
                    if reading.get('supply_kaddish'):
                        declaration=node.find(f'{{{J}}}declare')
                        if [n.get('value') for n in declaration.findall(f'.//{{{TEI}}}binary')]!=['false','true']:raise ValueError('second penitential day Kaddish must use Ten Days context')
                    start=scopes[1];end=node.find(f'{{{J}}}endConditional[@target="#{start.get(XML+"id")}"]');children=list(node)
                    for child in children[children.index(start):children.index(end)+1]:node.remove(child)
            notes=node.findall(f'.//{{{TEI}}}note[@type="commentary"]')
            wanted=[n['text'] for f in reading['fragments'] for n in f['notes'][lang]]
            if list(map(normalize,(printed_text(n) for n in notes)))!=list(map(normalize,wanted)):raise ValueError('second penitential day footnote changed: '+reading['id'])
            for n in notes+node.findall(f'{{{TEI}}}head'):
                parent=n.getparent();prev=n.getprevious()
                if prev is None:parent.text=(parent.text or '')+(n.tail or '')
                else:prev.tail=(prev.tail or '')+(n.tail or '')
                parent.remove(n)
            if reading['kind']=='pizmon':
                choices=node.findall(f'.//{{{TEI}}}choice[{{{TEI}}}abbr]')
                if len(choices)!=(7 if lang=='he' else 6) or any(normalize(''.join(c.find(f'{{{TEI}}}expan').itertext()))!=normalize(reading['refrain'][lang]) for c in choices):raise ValueError('second penitential day verified refrain changed')
                milestones=node.findall(f'{{{TEI}}}milestone[@corresp]')
                if len(milestones)!=7:raise ValueError('second penitential day stanza alignment changed')
            mixed_rubric=lang=='he' and reading['kind']=='rubric' and re.search('[A-Za-z]',reading['fragments'][0]['he']['text'])
            if not mixed_rubric:
                for foreign in node.findall(f'.//{{{TEI}}}foreign'):foreign.attrib.pop(XML+'lang',None)
            node.set(XML+'lang',lang)
            expected=defaultdict(list)
            for f in reading['fragments']:
                data=f[lang];words=data['text']
                if mixed_rubric:
                    expected[data['scan'],'he'].append(' '.join(re.findall(r'[\u0590-\u05ff]+',words)))
                    expected[data['scan'],'en'].append(re.sub(r'[\u0590-\u05ff]+','',words).replace(' · ',' '))
                else:expected[data['scan'],lang].append(words)
            if mixed_rubric:
                node.set(XML+'lang','en')
            actual={k:normalize(v) for k,v in streams(node,include_notes=True).items() if v.strip()}
            expected={k:normalize(' '.join(v)) for k,v in expected.items() if normalize(' '.join(v))}
            differences=check(actual,expected)
            if differences:raise ValueError(f'{reading["id"]}: {differences}')
    print(f'second penitential day: {len(units)} source-ordered bilingual units, 7 shared pizmon units, 7 Hebrew / 6 English refrain choices, footnotes and Ten Days Kaddish checked')


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Verify compiled second penitential day bilingual petition pairings.')
    parser.add_argument('compiled_xml')
    args=parser.parse_args()
    verify_compiled(etree.parse(args.compiled_xml))
