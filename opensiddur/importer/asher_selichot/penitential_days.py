"""Manifest-driven authoring and reverse verification of later selichot services."""
from opensiddur.importer.scan.authoring import printed_text
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
from .penitential_second_day import wrap_hebrew
from .identities import project_name
from .printings import is_declaration, printing, text_urn

SERVICE_PREFIX = 'urn:x-opensiddur:text:siddur:selichot/penitential_'
DAYS = ('third', 'fourth', 'fifth')
FAST_SERVICES = ('monday-fast', 'thursday-fast', 'last-monday-fast', 'tenth-tevet', 'esther-fast', 'tammuz-fast', 'yom-kippur-katan')
SERVICES = DAYS + ('erev-yom-kippur',) + FAST_SERVICES + ('circumcision',)

def manifest_name(day):
    if day not in SERVICES: raise ValueError('Unsupported selichot service: '+day)
    return 'penitential-'+day+'-day' if day in DAYS else day

def service_filename(day):
    return manifest_name(day).replace('-', '_')+'.xml'

def service_urn(day):
    if day=='erev-yom-kippur': return 'urn:x-opensiddur:text:siddur:selichot/erev_yom_kippur'
    if day in FAST_SERVICES or day=='circumcision': return 'urn:x-opensiddur:text:siddur:selichot/'+day.replace('-', '_')
    if day not in DAYS: raise ValueError('Unsupported penitential day: '+day)
    return SERVICE_PREFIX+day+'_day'
J = 'http://jewishliturgy.org/ns/jlptei/2'


def readings(source,day):
    manifest=json.loads((source/(manifest_name(day)+'.json')).read_text())
    units=[json.loads((source/name).read_text()) for name in manifest['readings']]
    starts=('performance_instruction',) if day=='circumcision' else ('opening_instruction','weekday_amidah')
    ends=('zekhor_berit_avraham_circumcision_recension',) if day=='circumcision' else ('conclusion','conclusion_repeat')
    if not manifest['complete'] or units[0]['id'] not in starts or units[-1]['id'] not in ends:
        raise ValueError(day+' penitential day boundaries are incomplete')
    for unit in units:
        if unit['kind']=='poem':
            for lang,prefix in [('he','אלהינו ואלהי אבותינו'),('en','Our God, and the God of our fathers')]:
                if unit['fragments'][0][lang]['text'].count(prefix)>1:
                    raise ValueError('Duplicated invocation in '+unit['id'])
    first,last=manifest['requested_leaves']
    for lang,offset in [('he',1),('en',2)]:
        pages=[int(f[lang]['scan'][1:]) for u in units for f in u['fragments'] if f[lang]['text']]
        if pages!=sorted(pages) or set(pages)!=set(range(first+offset,last+offset,2)):
            raise ValueError(day+' penitential day must cover every source page in order')
    return manifest,units


def pizmon(parent, reading, lang, context):
    """Preserve independent printed cues within shared bilingual semantic units."""
    unit=element(parent,'div',corresp=context)
    first=reading['fragments'][0][lang];pb(unit,first['scan'],first['printed_page'])
    if reading.get('heading',{}).get(lang):element(unit,'head',reading['heading'][lang])
    previous=first['scan']
    cue_pattern=reading['refrain_cues'][lang]
    opening_cue=reading.get('opening_cue',{}).get(lang)
    opening_pattern=re.escape(opening_cue)+r'(?=\s*$)' if opening_cue else None
    opening=' '.join(f[lang]['text'] for f in reading['stanzas'][0]['fragments'])
    for number,stanza in enumerate(reading['stanzas'],1):
        fragments=[f for f in stanza['fragments'] if f[lang]['text']];first=fragments[0][lang]
        if first['scan']!=previous:pb(unit,first['scan'],first['printed_page'])
        marker(unit,context+'/stanza_'+str(number))
        block=element(unit,'lg' if lang=='he' and not stanza.get('prose') else 'p')
        if lang=='he' and not stanza.get('prose'):
            # One call retains an unfinished verse across the printed page break.
            prepared=copy.deepcopy(fragments);cues=[]
            def cue_token(match):
                cues.append((match.group(0),opening if opening_cue and match.group(0)==opening_cue else reading.get('refrain_expansions',{}).get(lang,{}).get(match.group(0),reading['refrain'][lang])))
                return '__CUE_'+str(len(cues)-1)+'__|'
            for fragment in prepared:
                fragment['he']['text']=re.sub('(?:'+cue_pattern+')'+('|'+opening_pattern if opening_pattern else ''),cue_token,fragment['he']['text'])
            poetic_lines(block,prepared,{'line_stops':'·׃|'})
            for line in block.findall(f'{{{TEI}}}l'):
                if line.text and re.fullmatch(r'__CUE_\d+__\|',line.text):
                    cue,expansion=cues[int(line.text.split('_')[3])];line.text=None
                    choice(element(line,'seg',type='refrain'),cue,expansion)
        else:
            pattern='(?:'+cue_pattern+')'+('|'+opening_pattern if opening_pattern else '')
            for index,fragment in enumerate(fragments):
                data=fragment[lang]
                if index:pb(block,data['scan'],data['printed_page'])
                pieces=re.split('('+pattern+')',data['text'])
                for piece_index,piece in enumerate(pieces):
                    if not piece:continue
                    if re.fullmatch(pattern,piece):
                        choice(element(block,'seg',type='refrain'),piece,opening if piece==opening_cue else reading.get('refrain_expansions',{}).get(lang,{}).get(piece,reading['refrain'][lang]))
                    else:
                        full_pattern=reading.get('full_refrain_pattern',{}).get(lang)
                        if full_pattern:
                            for part in re.split('('+full_pattern+')',piece):
                                if re.fullmatch(full_pattern,part):element(block,'seg',part,type='refrain')
                                else:words_with_notes(block,part,[n for n in fragment['notes'][lang] if n['anchor'] in part],lang)
                        else:words_with_notes(block,piece,fragment['notes'][lang],lang)
                if not data.get('join_next'):append_words(block,' ')
        if lang=='en' and reading.get('literal_superscript_markers'):
            for owner in list(block.iter()):
                for attr in ('text','tail'):
                    value=getattr(owner,attr)
                    if not value:continue
                    for glyph in reading['literal_superscript_markers']:
                        if glyph not in value:continue
                        before,after=value.split(glyph,1);setattr(owner,attr,before)
                        mark=etree.Element('{'+TEI+'}hi',rend='superscript');mark.text=unicodedata.normalize('NFKD',glyph);mark.tail=after
                        if attr=='text':owner.insert(0,mark)
                        else:owner.addnext(mark)
        previous=fragments[-1][lang]['scan']
        if lang=='he':
            for line in block.findall(f'{{{TEI}}}l'):
                if line.text and (line.text.strip()==reading['refrain'][lang] or re.fullmatch(reading.get('full_refrain_pattern',{}).get(lang,'(?!)'),line.text.strip())):
                    words=line.text;line.text=None;element(line,'seg',words,type='refrain')
        block.tail=' '
    element(unit,'milestone',unit='stanza')
    return unit


def printed(parent,reading,lang,context,day=None):
    if not any(f[lang]['text'] for f in reading['fragments']):
        return element(parent,'div',corresp=context)
    if reading['kind']=='pizmon':return pizmon(parent,reading,lang,context)
    reading=copy.deepcopy(reading)
    if reading['kind']=='poem':reading['line_stops']='·׃'
    unit=ordinary_printed(parent,reading,lang,context)
    if lang=='he' and reading.get('bracketed_responses'):
        for line in unit.findall(f'.//{{{TEI}}}l'):
            if (line.text or '').startswith('[') and ''.join(line.itertext()).rstrip().endswith(']'):
                words=line.text;children=list(line);line.text=None
                response=element(line,'seg',words,type='refrain')
                for child in children:line.remove(child);response.append(child)
    for item in reading.get('interleaved_rubrics',[]):
        rubric=item['reading']
        if not rubric['fragments'][0][lang]['text']:continue
        blocks=unit.findall(f'{{{TEI}}}p')
        block=blocks[item['before_fragment']]
        insertion=element(unit,'div',corresp=context+'/'+rubric['id'])
        unit.remove(insertion);unit.insert(unit.index(block),insertion)
        stem=day.replace('-','_')+'_'+rubric['id']
        expansion_scope(insertion,stem+'_printed',False)
        ordinary_printed(insertion,rubric,lang,context+'/'+rubric['id']+'/printed')
        element(insertion,'j:endConditional',target='#'+stem+'_printed')
        expansion_scope(insertion,stem+'_expanded',True)
        expanded_rubric(insertion,rubric,lang,day)
        element(insertion,'j:endConditional',target='#'+stem+'_expanded')
    if reading.get('interleaved_rubrics') and unit.find(f'{{{TEI}}}div') is not None:
        for block in list(unit.findall(f'{{{TEI}}}p')):
            position=unit.index(block);unit.remove(block)
            wrapper=element(unit,'div');unit.remove(wrapper);unit.insert(position,wrapper);wrapper.append(block)
    if lang=='en':wrap_hebrew(unit)
    elif reading.get('reader_label'):
        block=unit.find(f'{{{TEI}}}p')
        if block is None or not (block.text or '').startswith('Reader '):raise ValueError('Printed Reader label absent')
        words=block.text[len('Reader '):];block.text=None
        label=element(block,'foreign','Reader');label.set(XML+'lang','en');label.tail=' '+words
    return unit


def full_kaddish(parent,day,target=PRAYER+'kaddish/shalem',stem=None):
    stem=stem or 'penitential_'+day+'_day_kaddish'
    declaration=element(parent,'j:declare');declaration.set(XML+'id',stem)
    for typ,name,value in [('asher:selichot','first_day','false'),('opensiddur:holiday-aggregate','aseret-ymei-tshuva','false' if day in FAST_SERVICES else 'true')]:
        fs=element(declaration,'fs',type=typ);f=element(fs,'f');f.set('name',name);element(f,'binary',value=value)
    element(parent,'j:transclude',target=target)
    element(parent,'j:endDeclare',target='#'+stem)


def expanded_rubric(parent,reading,lang,day):
    context=service_urn(day)
    if reading.get('performance_instruction',{}).get(lang):
        role=element(element(parent,'div'),'note',reading['performance_instruction'][lang],type='instruction');role.set(XML+'lang','en')
    if reading['id'].startswith(('verses_after_', 'verses_before_')) or reading.get('paired_inline'):
        # As on Erev, the two language lists belong to one paired prose block.
        div=element(parent,'div');element(div,'milestone',unit='prayer',corresp=context+'/'+reading['id']+'/expanded')
        block=element(div,'p')
        for target in targets(reading,lang):element(block,'j:transclude',target=target,type='inline').tail=' '
        element(div,'milestone',unit='prayer')
    else:
        opening=reading['id']=='opening_instruction'
        if opening:
            declaration=element(parent,'j:declare');declaration.set(XML+'id','penitential_'+day+'_day_opening_ten_days')
            fs=element(declaration,'fs',type='opensiddur:holiday-aggregate')
            feature=element(fs,'f');feature.set('name','aseret-ymei-tshuva');element(feature,'binary',value='false' if day in FAST_SERVICES else 'true')
        for target in targets(reading,lang):
            if reading.get('performance_before_target',{}).get(target):
                role=element(element(parent,'div'),'note',reading['performance_before_target'][target],type='instruction');role.set(XML+'lang','en')
            if reading.get('supply_kaddish') and target in (PRAYER+'kaddish/shalem',PRAYER+'kaddish/chatzi',PRAYER+'kaddish/yatom'):full_kaddish(parent,day,target,'penitential_'+day+'_'+reading['id']+'_kaddish')
            else:element(parent,'j:transclude',target=target)
        if opening:element(parent,'j:endDeclare',target='#penitential_'+day+'_day_opening_ten_days')
        # Preserve any printed apparatus attached to a fulfilled instruction.
        for note in reading['fragments'][0]['notes'][lang]:
            block=element(element(parent,'div'),'p');node=element(block,'note',type='commentary')
            node.set(XML+'lang',note.get('language',lang));node.text=note['text']


def documents(source,day):
    manifest,units=readings(source,day)
    context_urn=service_urn(day)
    for lang in ['he','en']:
        project=project_name(lang)
        root,text=document(lang,project,manifest['heading'][lang],context_urn)
        service=element(element(text,'body'),'div',corresp=context_urn)
        first=units[0]['fragments'][0][lang];pb(service,first['scan'],first['printed_page'])
        element(service,'head',manifest['heading'][lang])
        for reading in units:
            context=reading.get('urn',context_urn+'/'+reading['id'])
            if reading.get('filename'):
                module,body=document(lang,project,reading['filename'].replace('_',' '),context)
                printed(element(body,'body'),reading,lang,context,day)
                yield project,reading['filename']+'.xml',module
                element(service,'j:transclude',target=context)
            elif reading['kind']=='rubric' and (any(targets(reading,language) for language in ('he','en')) or reading.get('refrain_instruction')):
                unit=element(service,'div',corresp=context)
                if reading.get('heading_before',{}).get(lang):element(unit,'head',reading['heading_before'][lang])
                feature='refrains_present' if reading.get('refrain_instruction') else 'prayers_present'
                stem='penitential_'+day+'_day_'+reading['id']
                expansion_scope(unit,stem+'_printed',False,feature=feature)
                printed(unit,reading,lang,context+'/printed');element(unit,'j:endConditional',target='#'+stem+'_printed')
                if not reading.get('refrain_instruction'):
                    expansion_scope(unit,stem+'_expanded',True,feature=feature)
                    expanded_rubric(unit,reading,lang,day);element(unit,'j:endConditional',target='#'+stem+'_expanded')
            else:printed(service,reading,lang,context)
        yield project,service_filename(day),root


def verify_evidence(source,units,day):
    folder=manifest_name(day)
    records=json.loads((source.parent/(folder+'-proofreading.json')).read_text())['readings']
    if [r['id'] for r in records]!=[u['id'] for u in units]:raise ValueError('Stale penitential day proofreading scope')
    for r in records:
        for key,prefix in [('initial_sha256','initial/'),('assembled_sha256','assembled-preocr/'),('working_sha256','')]:
            path=source/folder/(prefix+r['id']+'.json')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=r[key]:raise ValueError('Stale penitential day evidence: '+r['id'])


def verify_readings(source,project_directory,day):
    context_urn=service_urn(day)
    from opensiddur.importer.scan.reverse import streams,check
    normalize=lambda s:' '.join(unicodedata.normalize('NFKD',s).split())
    manifest,units=readings(source,day);verify_evidence(source,units,day)
    for lang in ['he','en']:
        project=project_directory/project_name(lang)
        service=etree.parse(str(project/(service_filename(day)))).find(f'.//{{{TEI}}}body/{{{TEI}}}div')
        if normalize(service.find(f'{{{TEI}}}head').text)!=normalize(manifest['heading'][lang]):raise ValueError('penitential day heading changed')
        nodes=[n for n in service if n.tag not in [f'{{{TEI}}}head',f'{{{TEI}}}pb'] and not is_declaration(n)]
        if len(nodes)!=len(units):raise ValueError('penitential day source order changed')
        for reading,node in zip(units,nodes):
            context=spelled_urn(reading.get('urn',context_urn+'/'+reading['id']))
            if reading.get('filename'):
                if node.get('target')!=text_urn(context):raise ValueError('penitential day module order changed')
                node=printing(project,spelled_name(reading['filename']))
            elif node.get('corresp')!=context:raise ValueError('penitential day inline order changed')
            node=copy.deepcopy(node)
            for item in reading.get('interleaved_rubrics',[]):
                rubric=item['reading'];embedded=node.find(f'{{{TEI}}}div[@corresp="{context}/{rubric["id"]}"]')
                words=rubric['fragments'][0][lang]['text']
                if not words:
                    if embedded is not None:raise ValueError('Invented counterpart rubric')
                    continue
                if embedded is None:raise ValueError('Missing interleaved source rubric')
                printed_note=embedded.find(f'.//{{{TEI}}}note[@type="instruction"]')
                if normalize(printed_text(printed_note))!=normalize(words):raise ValueError('Interleaved rubric wording changed')
                if [n.get('target') for n in embedded.findall(f'.//{{{J}}}transclude')]!=[spelled_urn(t) for t in targets(rubric,lang)]:raise ValueError('Interleaved expansion targets changed')
                node.remove(embedded)
            scopes=node.findall(f'{{{J}}}conditional')
            if scopes:
                if [s.find(f'{{{TEI}}}fs/{{{TEI}}}f/{{{TEI}}}binary').get('value') for s in scopes]!=(['false'] if reading.get('refrain_instruction') else ['false','true']):raise ValueError('penitential day expansion polarity changed')
                if len(scopes)==2:
                    if [n.get('target') for n in node.findall(f'.//{{{J}}}transclude')]!=[spelled_urn(t) for t in targets(reading,lang)]:raise ValueError('penitential day expansion range changed')
                    if reading.get('supply_kaddish'):
                        declaration=node.find(f'{{{J}}}declare')
                        if [n.get('value') for n in declaration.findall(f'.//{{{TEI}}}binary')]!=['false','false' if day in FAST_SERVICES else 'true']:raise ValueError('Service Kaddish seasonal context changed')
                    start=scopes[1];end=node.find(f'{{{J}}}endConditional[@target="#{start.get(XML+"id")}"]');children=list(node)
                    for child in children[children.index(start):children.index(end)+1]:node.remove(child)
            notes=node.findall(f'.//{{{TEI}}}note[@type="commentary"]')
            wanted=[n['text'] for f in reading['fragments'] for n in f['notes'][lang]]
            if list(map(normalize,(printed_text(n) for n in notes)))!=list(map(normalize,wanted)):raise ValueError('penitential day footnote changed: '+reading['id'])
            markers=node.findall(f'.//{{{TEI}}}hi[@rend="superscript"]') if reading.get('note_markers') and lang=='en' else []
            wanted_markers=[str(n) for page,anchors in reading.get('note_markers',{}).items() for n in range(reading.get('note_marker_start',{}).get(page,1),reading.get('note_marker_start',{}).get(page,1)+len(anchors))] if lang=='en' else []
            if markers and [n.text for n in markers]!=wanted_markers:raise ValueError('Printed unresolved note marker changed')
            if wanted_markers and not markers:raise ValueError('Missing printed unresolved note markers')
            for n in notes+markers+node.findall(f'{{{TEI}}}head'):
                parent=n.getparent();prev=n.getprevious()
                if prev is None:parent.text=(parent.text or '')+(n.tail or '')
                else:prev.tail=(prev.tail or '')+(n.tail or '')
                parent.remove(n)
            if reading['kind']=='pizmon':
                source_pages=[f[lang]['scan'] for f in reading['fragments'] if f[lang]['text']]
                actual_pages=['s'+str(int(re.search(r'/n(\d+)',n.get('facs')).group(1))+1) for n in node.findall(f'.//{{{TEI}}}pb')]
                if actual_pages!=source_pages:raise ValueError('Pizmon facsimile source order changed')
                choices=node.findall(f'.//{{{TEI}}}choice[{{{TEI}}}abbr]')
                if len(choices)!=reading['choice_counts'][lang]:raise ValueError(day+' penitential day refrain count changed')
                opening=' '.join(f[lang]['text'] for f in reading['stanzas'][0]['fragments'])
                for c in choices:
                    cue=printed_text(c.find(f'{{{TEI}}}abbr'))
                    wanted=opening if cue==reading.get('opening_cue',{}).get(lang) else reading.get('refrain_expansions',{}).get(lang,{}).get(cue,reading['refrain'][lang])
                    if normalize(''.join(c.find(f'{{{TEI}}}expan').itertext()))!=normalize(wanted):raise ValueError('Refrain expansion changed')
                milestones=node.findall(f'{{{TEI}}}milestone[@corresp]')
                if len(milestones)!=len(reading['stanzas']):raise ValueError('Stanza alignment changed')
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
    print(f'{day} penitential day: {len(units)} bilingual units; documentary branches, refrains, notes, source order and expansion ranges checked')


def verify_compiled(tree,day,expected_petitions):
    """Check each supplied petition pair and both seasonal Kaddishes."""
    context=service_urn(day);ns='http://jewishliturgy.org/ns/processing'
    service=tree.find('.//{'+ns+'}transclude[@target="'+context+'"]')
    # A single-day file can be the compiler root rather than a transclusion.
    if service is None:service=tree.getroot() if hasattr(tree,'getroot') else tree
    verify_half_kaddish(service,ten_days=True)
    kaddishes=service.findall('.//{'+ns+'}transclude[@target="'+PRAYER+'kaddish/shalem"]')
    if len(kaddishes)!=1:raise ValueError('Missing or duplicate '+day+' penitential day Full Kaddish')
    words=''.join(''.join(n.itertext())for n in kaddishes[0].findall('.//{'+ns+'}parallelItem[@role="primary"]'))
    letters=''.join(c for c in unicodedata.normalize('NFD',words)if '\u05d0'<=c<='\u05ea')
    if letters.count('לעלאלעלאמןכלברכתא')!=1:raise ValueError('Full Kaddish lost Ten Days reading')
    seen=[]
    for block in service.findall('.//{'+ns+'}parallel'):
        primary=block.find('{'+ns+'}parallelItem[@role="primary"]')
        if primary is None:continue
        marks=[n.get('corresp')for n in primary.findall('.//{'+TEI+'}milestone')if (n.get('corresp')or'').startswith(context+'/verses_after_')and n.get('corresp').endswith('/expanded')]
        if not marks:continue
        parallel=block.find('{'+ns+'}parallelItem[@role="parallel"]')
        if parallel is None:raise ValueError('Missing bilingual petition expansion')
        if marks!=[n.get('corresp')for n in parallel.findall('.//{'+TEI+'}milestone')if n.get('corresp')in marks]:raise ValueError('Unpaired petition expansion')
        words=' '.join(''.join(parallel.itertext()).split())
        if not all(v in words for v in ['Like a father hath compassion','for thy own sake']):raise ValueError('Wrong English petition range')
        seen.extend(marks)
    if len(seen)!=expected_petitions or len(set(seen))!=expected_petitions:raise ValueError('Missing or duplicate penitential petition expansion')
    print(f'Compiled {day} penitential day: {len(seen)} bilingual petition ranges and seasonal Half/Full Kaddish checked')
