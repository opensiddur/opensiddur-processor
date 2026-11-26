"""The image-read Erev Rosh Hashanah service and its bilingual cue ranges."""
from opensiddur.importer.scan.authoring import printed_text
import copy
import hashlib
import json
import re
import unicodedata
from lxml import etree
from .build import TEI, XML, PRAYER, document, element, pb, marker, choice, spelled_name, spelled_urn
from .first_day import (poetic_lines, words_with_notes, mixed_words,
                        append_words, expansion_scope)
from .identities import RENAMED_URNS, project_name
from .printings import is_declaration, printing

EREV = 'urn:x-opensiddur:text:siddur:selichot/erev_rosh_hashanah'
EXTRA = PRAYER+'selichot/rahamekha_rabbim'
J = 'http://jewishliturgy.org/ns/jlptei/2'


def verify_compiled(tree):
    """Different petition lists must remain one bilingual prose passage."""
    ns={'p':'http://jewishliturgy.org/ns/processing','t':TEI}
    seen=[]
    for block in tree.findall('.//{'+ns['p']+'}parallel'):
        primary=block.find('{'+ns['p']+'}parallelItem[@role="primary"]')
        if primary is None:continue
        markers=[n.get('corresp') for n in primary.findall('.//{'+TEI+'}milestone')
                 if (n.get('corresp') or '').startswith(EREV+'/verses_after_') and n.get('corresp').endswith('/expanded')]
        if not markers:continue
        parallel=block.find('{'+ns['p']+'}parallelItem[@role="parallel"]')
        if parallel is None:raise ValueError('Missing bilingual Erev petition expansion')
        english=' '.join(''.join(parallel.itertext()).split())
        if 'Like a father hath compassion' not in english:
            raise ValueError('Erev petition expansion paired with unrelated English')
        if markers!=[n.get('corresp') for n in parallel.findall('.//{'+TEI+'}milestone')
                     if n.get('corresp') in markers]:
            raise ValueError('Erev expanded petition alignment identity differs')
        if markers[0].endswith('/verses_after_mah_enosh/expanded') and not all(s in english for s in ['Thy mercy is great','Selah! O Lord of Hosts! Happy','for thy own sake']):
            raise ValueError('Page-52 reprinted wording lost in expanded output')
        seen.extend(markers)
    if len(seen)!=12 or len(set(seen))!=12:
        raise ValueError('Missing or duplicate Erev expanded petition passages')
    print('Compiled Erev: 12 bilingual petition expansions and page-52 wording checked')


def readings(source):
    manifest = json.loads((source/'erev-rosh-hashanah.json').read_text(encoding="utf-8"))
    if not manifest['complete']:
        raise ValueError('Erev service must have a contiguous complete reading')
    units=[json.loads((source/name).read_text(encoding="utf-8")) for name in manifest['readings']]
    if units[0]['id']!='opening_instruction' or units[-1]['id']!='reader_kaddish':
        raise ValueError('Erev reading boundaries must end before Gedaliah')
    for lang,start in [('he',100),('en',101)]:
        pages=[int(f[lang]['scan'][1:]) for u in units for f in u['fragments'] if f[lang]['text']]
        if pages!=sorted(pages) or set(pages)!=set(range(start,186,2)):
            raise ValueError('Erev readings must cover every verified source page in order')
    return manifest,units


def targets(reading, lang):
    value = reading.get('expansion_targets', [])
    value = value.get(lang, []) if isinstance(value, dict) else value
    return [RENAMED_URNS.get(target, target) for target in value]


def body_words(parent, words, notes, lang):
    # The English Tamid description and a Hebrew-page performance cue contain
    # foreign-language words in the body, independently of the footnotes.
    if lang == 'en' and re.search('[\u05d0-\u05ea]', words) and not notes:
        mixed_words(parent, words)
    elif lang == 'he' and 'Cong.' in words:
        before, after = words.split('Cong.', 1)
        words_with_notes(parent, before, notes, lang)
        element(parent, 'foreign', 'Cong.').set(XML+'lang', 'en')
        append_words(parent, after)
    else:
        words_with_notes(parent, words, notes, lang)


def printed(parent, reading, lang, context):
    unit = element(parent, 'div', corresp=context)
    first = reading['fragments'][0][lang]
    pb(unit, first['scan'], first['printed_page'])
    if reading.get('heading', {}).get(lang):
        element(unit, 'head', reading['heading'][lang])
    if reading['kind'] == 'pizmon':
        opening = reading['stanzas'][0][lang]
        for i, stanza in enumerate(reading['stanzas']):
            marker(unit, context+'/stanza_'+str(i+1))
            block = element(unit, 'lg' if lang=='he' else 'p')
            words = stanza[lang]
            cue = stanza.get('cue', {}).get(lang)
            if stanza.get('opening_cue'):
                cue = words
                expansion = opening
            elif cue:
                expansion = (reading.get('refrains') or [reading['refrain']])[i%2 if reading.get('refrains') else 0][lang]
            if cue:words=words[:-len(cue)].rstrip()
            notes = [n for n in reading['fragments'][0]['notes'][lang] if n['anchor'] in words]
            if lang=='he':
                fragment = {'he':dict(first, text=words), 'notes':{'he':notes}}
                poetic_lines(block,[fragment],{'line_stops':'·׃'})
                node=element(block,'l') if cue else None
            else:
                body_words(block,words+(' ' if cue and words else ''),notes,lang)
                node=block
            if cue:
                segment=element(node,'seg',type='refrain') if not stanza.get('opening_cue') else node
                choice(segment,cue,expansion)
            block.tail=' '
        element(unit,'milestone',unit='stanza')
        return unit
    poetic = lang=='he' and reading['kind'] in ['poem','verse','litany']
    node=element(unit,'lg' if poetic else 'note' if reading['kind']=='rubric' else 'p')
    if reading['kind']=='rubric':
        node.set('type','instruction')
        node.set(XML+'lang','en' if re.search('[A-Za-z]',first['text']) else lang)
    if poetic:
        fragments=copy.deepcopy(reading['fragments'])
        if reading.get('prose_introduction'):
            before,after=fragments[0]['he']['text'].split(reading['prose_introduction'],1)
            intro=element(unit,'p',before);unit.remove(intro);unit.insert(unit.index(node),intro)
            fragments[0]['he']['text']=reading['prose_introduction']+after

        if reading.get('invocation',True) and '\n' in fragments[0]['he']['text'] and fragments[0]['he']['text'].startswith('אלהינו'):
            invocation,fragments[0]['he']['text']=fragments[0]['he']['text'].split('\n',1)
            element(node,'l',invocation).tail=' '
        poetic_lines(node,fragments,{'line_stops':reading.get('line_stops', '׃' if reading['kind']=='poem' and reading['id'] not in ['el_rahum_shemekha','ukhshehatau_yisrael'] else '·׃'),
                                    **({'refrain':'הוּא יַעֲנֵנוּ'} if reading['kind']=='litany' else {'refrain':'עֲנֵנוּ'} if reading['id']=='anenu' else {'refrain':'עֲנֵינָא'} if reading['id']=='rahmana' else {})})
        for line in node.findall(f'{{{TEI}}}l'):
            if reading.get('bracketed_responses') and line.text and '[' in line.text:
                before,response=line.text.split('[',1)
                if response.endswith(']'):
                    line.text=before
                    element(line,'seg','['+response,type='refrain')
            if line.text and 'Cong.' in line.text:
                before, after = line.text.split('Cong.',1);line.text=before
                foreign=element(line,'foreign','Cong.');foreign.set(XML+'lang','en');foreign.tail=after
    else:
        for i, fragment in enumerate(reading['fragments']):
            data=fragment[lang]
            if fragment.get('paragraph_start'):node=element(unit,'p')
            if i and data['scan']!=reading['fragments'][i-1][lang]['scan']:pb(node,data['scan'],data['printed_page'])
            if reading['id']=='adonai_boqer_tishma_qoli':
                prefix='רַחֲמֶיךָ' if lang=='he' else 'Thy mercy is great'
                before,after=data['text'].split(prefix,1)
                body_words(node,before,[],lang);element(node,'milestone',unit='prayer',corresp=EXTRA)
                stop='אַל תָּבוֹא' if lang=='he' else 'Enter not into judgment'
                mercy,judgment=(prefix+after).split(stop,1)
                body_words(node,mercy,[],lang)
                element(node,'milestone',unit='prayer',corresp=EXTRA+'/al_tavo')
                body_words(node,stop+judgment,fragment['notes'][lang],lang)
                element(node,'milestone',unit='prayer')
                element(node,'milestone',unit='prayer')
            elif reading.get('range_urn'):
                prefix = ('כִּי לֹא' if lang=='he' else 'for we do not presume') if reading['id']=='hateh_elohai' else ''
                before, after = data['text'].split(prefix,1) if prefix else ('',data['text'])
                body_words(node,before,[],lang)
                element(node,'milestone',unit='prayer',corresp=reading['range_urn'])
                body_words(node,prefix+after,fragment['notes'][lang],lang)
                element(node,'milestone',unit='prayer')
            elif reading['kind']=='rubric' and node.get(XML+'lang')=='en' and lang=='he':mixed_words(node,data['text'])
            elif lang=='en' and reading.get('note_markers',{}).get(data['printed_page']):
                rest=data['text'];offset=sum(len(v) for k,v in reading['note_markers'].items() if int(k)<int(data['printed_page']))
                for n,anchor in enumerate(reading['note_markers'][data['printed_page']],reading.get('note_marker_start',{}).get(data['printed_page'],offset+1)):
                    before,rest=rest.split(anchor,1)
                    body_words(node,before+anchor,[],lang)
                    element(node,'hi',str(n),rend='superscript')
                body_words(node,rest,[],lang)
            else:body_words(node,data['text'],fragment['notes'][lang],lang)
            if not data.get('join_next'):append_words(node,' ')
    return unit


def kaddish(parent):
    declaration=element(parent,'j:declare');declaration.set(XML+'id','erev_rosh_hashanah_kaddish')
    for typ,name in [('asher:selichot','first_day'),('opensiddur:holiday-aggregate','aseret-ymei-tshuva')]:
        fs=element(declaration,'fs',type=typ);f=element(fs,'f');f.set('name',name);element(f,'binary',value='false')
    element(parent,'j:transclude',target=PRAYER+'kaddish/shalem')
    element(parent,'j:endDeclare',target='#erev_rosh_hashanah_kaddish')


def expanded_rubric(parent, reading, lang):
    if reading['id'].startswith('verses_after_'):
        # One paired prose passage: the languages can have different lists of
        # petitions. Flatten their source markers rather than shifting every
        # subsequent alignment unit by the Hebrew-only introductory petitions.
        parent=element(parent,'div')
        element(parent,'milestone',unit='prayer',corresp=EREV+'/'+reading['id']+'/expanded')
        block=element(parent,'p')
        for target in targets(reading,lang):
            element(block,'j:transclude',target=target,type='inline').tail=' '
        element(parent,'milestone',unit='prayer')
        return
    kept=reading.get('retained_instruction',{}).get(lang)
    position=reading.get('instruction_position',{}).get(lang,'before')
    def retain():
        if kept:element(parent,'note',kept,type='instruction').set(XML+'lang','en')
    if kept and position=='before' and not reading.get('instruction_between_targets'):retain()
    if reading['id']=='reader_kaddish':kaddish(parent)
    else:
        for i,target in enumerate(targets(reading,lang)):
            element(parent,'j:transclude',target=target)
            if i==0 and reading.get('instruction_between_targets'):retain()
    if kept and position=='after':retain()


def documents(source):
    manifest, units=readings(source)
    for lang in ['he','en']:
        project=project_name(lang)
        root,text=document(lang,project,manifest['heading'][lang],EREV)
        service=element(element(text,'body'),'div',corresp=EREV)
        first=units[0]['fragments'][0][lang];pb(service,first['scan'],first['printed_page'])
        element(service,'head',manifest['heading'][lang])
        for reading in units:
            context=reading.get('urn',EREV+'/'+reading['id'])
            if reading.get('filename'):
                module,body=document(lang,project,reading['filename'].replace('_',' '),context)
                printed(element(body,'body'),reading,lang,context)
                yield project,reading['filename']+'.xml',module
                element(service,'j:transclude',target=context)
            elif reading['kind']=='rubric' and reading.get('editorial_expansion',True) and (targets(reading,lang) or reading.get('refrain_instruction')):
                unit=element(service,'div',corresp=context)
                if reading.get('heading_before',{}).get(lang):element(unit,'head',reading['heading_before'][lang])
                feature='refrains_present' if reading.get('refrain_instruction') else 'prayers_present'
                stem='erev_'+reading['id']
                expansion_scope(unit,stem+'_printed',False,feature=feature)
                printed(unit,reading,lang,context+'/printed')
                element(unit,'j:endConditional',target='#'+stem+'_printed')
                if not reading.get('refrain_instruction'):
                    expansion_scope(unit,stem+'_expanded',True,feature=feature)
                    expanded_rubric(unit,reading,lang)
                    element(unit,'j:endConditional',target='#'+stem+'_expanded')
            else:printed(service,reading,lang,context)
        yield project,'erev_rosh_hashanah.xml',root


def verify_evidence(source, units):
    """A reading edit invalidates its older proofreading record, including initial evidence."""
    path=source.parent/'erev-rosh-hashanah-proofreading.json'
    if not path.exists():raise ValueError('Missing Erev proofreading provenance')
    records=json.loads(path.read_text(encoding="utf-8"))['readings']
    if [r['id'] for r in records]!=[u['id'] for u in units]:raise ValueError('Erev proofreading scope is stale')
    for record in records:
        for key,prefix in [('initial_sha256','initial/'),('working_sha256','')]:
            path=source/'erev-rosh-hashanah'/(prefix+record['id']+'.json')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=record[key]:
                raise ValueError('Stale Erev proofreading evidence: '+record['id'])


def verify_readings(source, project_directory):
    """Compare the documentary XML against page-ordered readings, excluding additions."""
    from opensiddur.importer.scan.reverse import streams,check
    normalize=lambda s:' '.join(unicodedata.normalize('NFKD',s).split())
    manifest,read=readings(source)
    verify_evidence(source,read)
    for lang in ['he','en']:
        project=project_directory/project_name(lang)
        service=etree.parse(str(project/'erev_rosh_hashanah.xml')).find(f'.//{{{TEI}}}body/{{{TEI}}}div')
        if normalize(service.find(f'{{{TEI}}}head').text)!=normalize(manifest['heading'][lang]):raise ValueError('Missing Erev heading')
        nodes=[n for n in service if n.tag not in [f'{{{TEI}}}head',f'{{{TEI}}}pb'] and not is_declaration(n)]
        if len(nodes)!=len(read):raise ValueError('Erev source order or boundary changed')
        for reading,node in zip(read,nodes):
            context=spelled_urn(reading.get('urn',EREV+'/'+reading['id']))
            if reading.get('filename'):
                if node.get('target')!=context:raise ValueError('Erev module order changed')
                node=printing(project,spelled_name(reading['filename']))
            elif node.get('corresp')!=context:raise ValueError('Erev inline order changed')
            node=copy.deepcopy(node)
            if reading.get('range_urn'):
                boundaries=node.findall(f'.//{{{TEI}}}milestone[@unit="prayer"]')
                if [n.get('corresp') for n in boundaries]!=[spelled_urn(reading['range_urn']),None]:
                    raise ValueError('Reprinted prayer range boundaries changed')
                prefix=('כִּי לֹא' if lang=='he' else 'for we do not presume') if reading['id']=='hateh_elohai' else ''
                words=reading['fragments'][0][lang]['text']
                expected=prefix+words.split(prefix,1)[1] if prefix else words
                if normalize(boundaries[0].tail or '')!=normalize(expected):
                    raise ValueError('Reprinted prayer range wording changed')
            if reading['kind']=='pizmon':
                expansions=[]
                for i,stanza in enumerate(reading['stanzas']):
                    if stanza.get('opening_cue'):expansions.append(normalize(reading['stanzas'][0][lang]))
                    elif stanza.get('cue'):expansions.append(normalize((reading.get('refrains') or [reading['refrain']])[i%2 if reading.get('refrains') else 0][lang]))
                actual_expansions=[normalize(''.join(n.itertext())) for n in node.findall(f'.//{{{TEI}}}expan')]
                if actual_expansions!=expansions:raise ValueError('Erev verified refrain expansion changed')

            scopes=node.findall(f'{{{J}}}conditional')
            if scopes:
                if [s.find(f'{{{TEI}}}fs/{{{TEI}}}f/{{{TEI}}}binary').get('value') for s in scopes]!=([ 'false'] if reading.get('refrain_instruction') else ['false','true']):raise ValueError('Erev branch polarity changed')
                if len(scopes)==2:
                    if [n.get('target') for n in node.findall(f'.//{{{J}}}transclude')]!=[spelled_urn(t) for t in targets(reading,lang)]:raise ValueError('Erev language-specific targets changed')
                    if reading['id']=='reader_kaddish':
                        declaration=node.find(f'{{{J}}}declare')
                        if [n.get('value') for n in declaration.findall(f'.//{{{TEI}}}binary')]!=['false','false']:raise ValueError('Erev Kaddish calendar changed')
                    start=scopes[1];end=node.find(f'{{{J}}}endConditional[@target="#{start.get(XML+"id")}"]');children=list(node)
                    for child in children[children.index(start):children.index(end)+1]:node.remove(child)
            notes=node.findall(f'.//{{{TEI}}}note[@type="commentary"]')
            expected_notes=[n['text'] for f in reading['fragments'] for n in f['notes'][lang]]
            if [normalize(printed_text(n)) for n in notes]!=list(map(normalize,expected_notes)):raise ValueError('Erev note text changed: '+reading['id'])
            references=node.findall(f'.//{{{TEI}}}hi[@rend="superscript"]')
            expected_references=[str(n) for n in range(1,sum(map(len,reading.get('note_markers',{}).values()))+1)] if lang=='en' else []
            if [n.text for n in references]!=expected_references:raise ValueError('Tamid reference markers changed')
            for n in notes+references+node.findall(f'{{{TEI}}}head'):
                parent=n.getparent();prev=n.getprevious()
                if prev is None:parent.text=(parent.text or '')+(n.tail or '')
                else:prev.tail=(prev.tail or '')+(n.tail or '')
                parent.remove(n)
            expected={}
            for fragment in reading['fragments']:
                d=fragment[lang];words=d['text'];page=d['scan']
                if not words:continue
                if reading['kind']=='rubric' and lang=='he' and re.search('[A-Za-z]',words):
                    expected[page,'he']=normalize(' '.join(re.findall(r'[\u0590-\u05ff]+',words)))
                    expected[page,'en']=normalize(re.sub(r'[\u0590-\u05ff]+','',words).replace(' · ',' '))
                else:expected[page,lang]=normalize(words)
            # For explicit foreign body spans retain a single original-language
            # text comparison, while direction is checked separately in the PDF.
            for foreign in node.findall(f'.//{{{TEI}}}foreign'):foreign.attrib.pop(XML+'lang',None)
            node.set(XML+'lang',lang)
            if reading['kind']=='rubric' and lang=='he' and any(re.search('[A-Za-z]',f['he']['text']) for f in reading['fragments']):
                # Preserve the rubric's separately authored language streams.
                for foreign in node.findall(f'.//{{{TEI}}}foreign'):foreign.set(XML+'lang','he')
            actual={k:v for k,v in streams(node,include_notes=True).items() if v.strip()}
            if reading['kind']=='rubric' and lang=='he' and re.search('[A-Za-z]',reading['fragments'][0]['he']['text']):actual={k:v.replace(' · ',' ') for k,v in actual.items()}
            expected={k:v for k,v in expected.items() if v.strip()}
            diff=check(actual,expected)
            if diff:raise ValueError(f'{reading["id"]}: {diff}')
    print(f'Erev Rosh Hashanah: {len(read)} source-ordered units, documentary branches, notes and bilingual expansion targets checked')


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Verify compiled Erev bilingual petition pairings.')
    parser.add_argument('compiled_xml')
    args=parser.parse_args()
    verify_compiled(etree.parse(args.compiled_xml))
