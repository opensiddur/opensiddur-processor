"""Numbered Asher services and their source-verified expansions."""
from opensiddur.importer.scan.authoring import printed_text
import json
import re
from .build import TEI, XML, PRAYER, document, element, pb, marker, choice, spelled_name, spelled_urn
from .first_day import (poetic_lines, words_with_notes, mixed_words, expansion_scope,
                        EXPANSION_TARGETS)
from .identities import text_urn, project_name
from .printings import is_declaration, printing

SECOND_DAY = 'urn:x-opensiddur:text:siddur:selichot/second_day'
PRAYERS = [PRAYER+'el_melekh_yoshev', PRAYER+'vayaavor']
OPENING = [PRAYER+name for name in ['ashrei', 'kaddish/selichot_preface',
    'kaddish/chatzi', 'lekha_adonai_hatsedaqah', 'shomea_tefillah',
    'selah_lanu_avinu', 'el_erekh_appayim_attah', 'vayaavor']]
VERSES = [PRAYER+'adonai_boqer_tishma_qoli/repeat', PRAYER+'hateh_elohai_oznekha/repeat']


def printed_unit(parent, reading, lang, context):
    unit = element(parent, 'div', corresp=context)
    first = reading['fragments'][0][lang]
    pb(unit, first['scan'], first['printed_page'])
    if reading['kind'] == 'poem' and lang == 'he':
        node = element(unit, 'lg')
        # Invocation remains body text and has its own introductory poetic line.
        fragments = json.loads(json.dumps(reading['fragments']))
        invocation, fragments[0]['he']['text'] = fragments[0]['he']['text'].split('\n', 1)
        element(node, 'l', invocation).tail = ' '
        poetic_lines(node, fragments, {'line_stops':'·׃'})
    else:
        node = element(unit, 'note' if reading['kind']=='rubric' else 'p')
        if reading['kind']=='rubric':
            node.set('type', 'instruction');node.set(XML+'lang', lang if lang=='he' and not re.search('[A-Za-z]', reading['fragments'][0][lang]['text']) else 'en')
        for i, fragment in enumerate(reading['fragments']):
            data = fragment[lang]
            if i:pb(node, data['scan'], data['printed_page'])
            if reading['kind']=='rubric' and lang=='he' and node.get(XML+'lang')=='en':mixed_words(node, data['text'])
            else:words_with_notes(node, data['text'], fragment['notes'][lang], lang)
            if not data.get('join_next'):
                if len(node):node[-1].tail=(node[-1].tail or '')+' '
                else:node.text=(node.text or '')+' '
    return unit


def pizmon(lang, project, reading, refrain):
    root, text = document(lang, project, reading.get('title_he', 'ישראל נושע'), reading['urn'])
    div = element(element(text,'body'),'div',corresp=reading['urn'])
    first = reading['stanzas'][0]['fragments'][0][lang]
    pb(div, first['scan'], first['printed_page'])
    if lang=='he' and not reading.get('heading_before_rubric'):element(div,'head','פזמון')  # No such heading is printed in English.
    opening = ' '.join(f[lang]['text'] for f in reading['stanzas'][0]['fragments'])+' '+refrain[lang]
    for stanza in reading['stanzas']:
        fragments = [f for f in stanza['fragments'] if f[lang]['text']]
        if not fragments:raise ValueError('Every stanza needs text in each language')
        first_fragment = fragments[0][lang]
        if stanza is not reading['stanzas'][0] and reading['stanzas'][reading['stanzas'].index(stanza)-1]['fragments'][-1][lang]['scan'] != first_fragment['scan']:
            pb(div, first_fragment['scan'], first_fragment['printed_page'])
        marker(div, reading['urn']+'/'+stanza['id'])
        block = element(div, 'lg' if lang=='he' else 'p')
        if lang=='he':poetic_lines(block, fragments, {'line_stops':'·׃'})
        else:
            for i,f in enumerate(fragments):
                if i:pb(block, f[lang]['scan'], f[lang]['printed_page'])
                words_with_notes(block,f[lang]['text']+('' if f[lang].get('join_next') else ' '),f['notes'][lang],lang)
        node = element(block,'l') if lang=='he' else block
        if stanza.get('cue'):
            segment = element(node,'seg',type='refrain')
            choice(segment, stanza['cue'][lang], refrain[lang])
        else:element(node,'seg',stanza['refrain'][lang],type='refrain')
        if stanza.get('trailing_cue', {}).get(lang):
            node = element(block, 'l') if lang=='he' else block
            if lang=='en':block[-1].tail=' '
            segment = element(node, 'seg', type='refrain')
            choice(segment, stanza['trailing_cue'][lang], refrain[lang])
        if stanza.get('opening_cue', {}).get(lang):
            node = element(block,'l') if lang=='he' else block
            if lang=='en':block[-1].tail=' '
            choice(node, stanza['opening_cue'][lang], opening)
        block.tail=' '
    element(div, 'milestone', unit='stanza')
    return root


def conclusion(parent, source, day_name="second"):
    """Transclude the closing prayers without importing a first-day heading/context."""
    closing = json.loads((source/'first-day-continuation.json').read_text(encoding="utf-8"))['sections']['closing']
    for group in closing:
        if group['id']=='reader_kaddish':continue
        if group['kind']=='rubric':
            for target in EXPANSION_TARGETS[group['id']]:element(parent,'j:transclude',target=target)
        else:element(parent,'j:transclude',target=text_urn(group['id']))
    declaration = element(parent,'j:declare');declaration.set(XML+'id',day_name+'_day_kaddish')
    fs = element(declaration,'fs',type='asher:selichot')
    f = element(fs,'f');f.set('name','first_day');element(f,'binary',value='false')
    # These numbered services copy this edition's first-day conclusion.
    fs = element(declaration,'fs',type='opensiddur:holiday-aggregate')
    f = element(fs,'f');f.set('name','aseret-ymei-tshuva');element(f,'binary',value='false')
    element(parent,'j:transclude',target=PRAYER+'kaddish/shalem')
    element(parent,'j:endDeclare',target='#'+day_name+'_day_kaddish')


def numbered_documents(source, day_name):
    day_urn = 'urn:x-opensiddur:text:siddur:selichot/'+day_name+'_day'
    data = json.loads((source/(day_name+'-day.json')).read_text(encoding="utf-8"))
    for lang in ['he','en']:
        project = project_name(lang)
        root, text = document(lang, project, data['heading'][lang], day_urn)
        service = element(element(text,'body'),'div',corresp=day_urn)
        first = data['units'][0]['fragments'][0][lang]
        pb(service, first['scan'], first['printed_page'])
        element(service,'head',data['heading'][lang])
        for reading in data['units']:
            if reading.get('filename'):
                if reading['kind']=='pizmon':module=pizmon(lang,project,reading,data['refrain'])
                else:
                    module, body = document(lang,project,reading['filename'].replace('_',' '),reading['urn'])
                    printed_unit(element(body,'body'),reading,lang,reading['urn'])
                yield project, reading['filename']+'.xml', module
                element(service,'j:transclude',target=reading['urn'])
            elif reading['kind']=='rubric':
                unit = element(service,'div',corresp=day_urn+'/'+reading['id'])
                if lang == 'he' and reading.get('heading_before'):
                    element(unit, 'head', reading['heading_before'])
                feature = 'refrains_present' if reading['id']=='refrain_instruction' else 'prayers_present'
                expansion_scope(unit,day_name+'_'+reading['id']+'_printed',False,feature=feature)
                printed_unit(unit,reading,lang,day_urn+'/'+reading['id']+'/printed')
                element(unit,'j:endConditional',target='#'+day_name+'_'+reading['id']+'_printed')
                if reading['id']=='refrain_instruction':continue
                expansion_scope(unit,day_name+'_'+reading['id']+'_expanded',True,feature=feature)
                if reading['id']=='conclusion_instruction':conclusion(unit,source,day_name)
                else:
                    targets = reading.get('expansion_targets', OPENING if reading['id']=='opening_instruction' else VERSES if reading['id']=='verses_instruction' else PRAYERS)
                    for target in targets:element(unit,'j:transclude',target=target)
                element(unit,'j:endConditional',target='#'+day_name+'_'+reading['id']+'_expanded')
            else:printed_unit(service,reading,lang,day_urn+'/'+reading['id'])
        yield project,day_name+'_day.xml',root


def verify_numbered_readings(source, project_directory, day_name):
    """Follow the printed service order and compare only documentary choice branches."""
    import copy
    import unicodedata
    from lxml import etree
    from opensiddur.importer.scan.reverse import streams, check
    normalize = lambda value: ' '.join(unicodedata.normalize('NFKD', value).split())
    day_urn = 'urn:x-opensiddur:text:siddur:selichot/'+day_name+'_day'
    data = json.loads((source/(day_name+'-day.json')).read_text(encoding="utf-8"))
    for lang in ['he', 'en']:
        project = project_directory/project_name(lang)
        root = etree.parse(str(project/(day_name+'_day.xml'))).getroot()
        service = root.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
        if service.get('corresp') != day_urn or normalize(service.find(f'{{{TEI}}}head').text) != normalize(data['heading'][lang]):
            raise ValueError('Numbered day needs its printed top-level heading')
        units = [n for n in service if n.tag not in [f'{{{TEI}}}pb', f'{{{TEI}}}head'] and not is_declaration(n)]
        if len(units) != len(data['units']):
            raise ValueError('Numbered-day boundary or source order changed')
        for reading, unit in zip(data['units'], units):
            if reading.get('filename'):
                if unit.tag != '{http://jewishliturgy.org/ns/jlptei/2}transclude' or unit.get('target') != spelled_urn(reading['urn']):
                    raise ValueError('Numbered-day independent poems must follow printed order')
                module = etree.parse(str(project/(spelled_name(reading['filename'])+'.xml')))
                if module.find(f'.//{{{TEI}}}idno[@type="urn"]').text != spelled_urn(reading['urn'])+'@'+project.name:
                    raise ValueError('Numbered-day canonical module identity changed')
                unit = printing(project, spelled_name(reading['filename']))
            elif unit.get('corresp') != spelled_urn(day_urn+'/'+reading['id']):
                raise ValueError('Numbered-day inline units are out of source order')
            unit = copy.deepcopy(unit)
            if reading['kind'] == 'rubric':
                scopes = unit.findall('{http://jewishliturgy.org/ns/jlptei/2}conditional')
                wanted = ['false'] if reading['id'] == 'refrain_instruction' else ['false', 'true']
                if [n.find(f'{{{TEI}}}fs/{{{TEI}}}f/{{{TEI}}}binary').get('value') for n in scopes] != wanted:
                    raise ValueError('Numbered-day instruction branch polarity changed')
                if len(scopes) == 2:
                    start = scopes[1]
                    end = unit.find('{http://jewishliturgy.org/ns/jlptei/2}endConditional[@target="#'+start.get(XML+'id')+'"]')
                    if end is None:raise ValueError('Unclosed numbered-day expansion')
                    if reading['id'] != 'conclusion_instruction':
                        expected_targets = reading.get('expansion_targets', OPENING if reading['id']=='opening_instruction' else VERSES if reading['id']=='verses_instruction' else PRAYERS)
                        if [n.get('target') for n in unit.findall('{http://jewishliturgy.org/ns/jlptei/2}transclude')] != [spelled_urn(t) for t in expected_targets]:
                            raise ValueError('Numbered-day referenced prayer range changed')
                    else:
                        closing = json.loads((source/'first-day-continuation.json').read_text(encoding="utf-8"))['sections']['closing']
                        expected_targets = []
                        for group in closing:
                            if group['id'] == 'reader_kaddish':continue
                            expected_targets.extend(EXPANSION_TARGETS[group['id']] if group['kind']=='rubric' else [text_urn(group['id'])])
                        expected_targets.append(PRAYER+'kaddish/shalem')
                        if [n.get('target') for n in unit.findall('{http://jewishliturgy.org/ns/jlptei/2}transclude')] != [spelled_urn(t) for t in expected_targets]:
                            raise ValueError('Numbered-day closing prayer range changed')
                        declaration = unit.find('{http://jewishliturgy.org/ns/jlptei/2}declare')
                        for typ, feature in [('asher:selichot','first_day'), ('opensiddur:holiday-aggregate','aseret-ymei-tshuva')]:
                            value = declaration.find(f'{{{TEI}}}fs[@type="{typ}"]/{{{TEI}}}f[@name="{feature}"]/{{{TEI}}}binary')
                            if value is None or value.get('value') != 'false':
                                raise ValueError('Numbered-day Kaddish must not inherit first-day or Ten Days context')
                    children=list(unit)
                    for n in children[children.index(start):children.index(end)+1]:unit.remove(n)
            expected = {}
            def append(page, language, words):
                key=(page,language);expected[key]=normalize(expected.get(key,'')+' '+words)
            parts = reading.get('stanzas', [reading])
            expected_notes=[]
            for part in parts:
                for fragment in part['fragments']:
                    value=fragment[lang];words=value['text'];page=value['scan']
                    if not words:continue
                    expected_notes.extend(n['text'] for n in fragment['notes'][lang])
                    if reading['kind']=='rubric' and lang=='he' and re.search('[A-Za-z]', reading['fragments'][0]['he']['text']):
                        append(page,'he',' '.join(re.findall(r'[\u0590-\u05ff]+',words)))
                        append(page,'en',re.sub(r'[\u0590-\u05ff]+','',words).replace(' · ',' '))
                    else:append(page,lang,words)
                if reading['kind']=='pizmon':
                    page = next(f[lang]['scan'] for f in reversed(part['fragments']) if f[lang]['text'])
                    append(page,lang,(part.get('cue') or part['refrain'])[lang])
                    if part.get('trailing_cue', {}).get(lang):append(page,lang,part['trailing_cue'][lang])
                    if part.get('opening_cue', {}).get(lang):append(page,lang,part['opening_cue'][lang])
            notes=unit.findall(f'.//{{{TEI}}}note[@type="commentary"]')
            if [normalize(printed_text(n,' ')) for n in notes] != list(map(normalize,expected_notes)):
                raise ValueError('Numbered-day printed footnotes changed')
            for n in notes+unit.findall(f'{{{TEI}}}head'):
                parent=n.getparent();prev=n.getprevious()
                if prev is None:parent.text=(parent.text or '')+(n.tail or '')
                else:prev.tail=(prev.tail or '')+(n.tail or '')
                parent.remove(n)
            unit.set(XML+'lang',lang)
            actual=streams(unit,include_notes=True)
            if reading['kind']=='rubric' and lang=='he' and re.search('[A-Za-z]', reading['fragments'][0]['he']['text']):actual={k:v.replace(' · ',' ') for k,v in actual.items()}
            differences=check(actual,expected)
            if differences:raise ValueError(f'{reading["id"]}: {differences}')
            if reading['kind']=='pizmon':
                choices=unit.findall(f'.//{{{TEI}}}choice[{{{TEI}}}abbr]')
                opening=' '.join(f[lang]['text'] for f in parts[0]['fragments'])+' '+data['refrain'][lang]
                expected_expansions = []
                for stanza in parts:
                    if stanza.get('cue'):expected_expansions.append(normalize(data['refrain'][lang]))
                    if stanza.get('trailing_cue', {}).get(lang):expected_expansions.append(normalize(data['refrain'][lang]))
                    if stanza.get('opening_cue', {}).get(lang):expected_expansions.append(normalize(opening))
                if [normalize(''.join(n.find(f'{{{TEI}}}expan').itertext())) for n in choices] != expected_expansions:
                    raise ValueError('Pizmon expansions must reproduce this edition’s verified refrain/opening')
                if lang=='he' and len(unit.findall(f'{{{TEI}}}lg'))!=len(parts):
                    raise ValueError('The pizmon must retain its source stanzas')
    print(day_name.title()+' day: printed order, page streams, footnotes and source refrain choices per language checked')


def documents(source):
    yield from numbered_documents(source, 'second')


def verify_readings(source, project_directory):
    return verify_numbered_readings(source, project_directory, 'second')
