"""Encode the complete first day from scan-first documentary readings."""

from opensiddur.importer.scan.authoring import append_words, mixed_words, words_with_notes, conditional_scope
from opensiddur.importer.scan.authoring import poetic_lines as _poetic_lines

import json
import re
import unicodedata
from lxml import etree
from pathlib import Path
from .build import TEI, XML, PRAYER, POEM, document, element, pb
from .identities import TEXTS, text_urn, project_name

FIRST_DAY = 'urn:x-opensiddur:text:siddur:selichot/first_day'
OBSOLETE_ASSEMBLIES = ('first_day_opening', 'first_day_preface',
                       'first_day_before_piyyut', 'first_day_closing', 'first_day_expanded',
                       # renamed texts: Vayaavor is one text, and El Erekh Appayim Attah is
                       # not Tachanun's El Erekh Appayim
                       'vayaavor_preliminary', 'el_erekh_appayim')
#: Texts build.py writes from their full printing (pp. 11-12): a printing elsewhere transcludes them.
PRINTED_IN_FULL = ('el_melekh_yoshev', 'vayaavor')


def verify_half_kaddish(service, ten_days):
    """Check the selected Hebrew branch inside this compiled service."""
    ns='http://jewishliturgy.org/ns/processing'
    passages=service.findall('.//{'+ns+'}transclude[@target="'+PRAYER+'kaddish/chatzi"]') if service is not None else []
    if len(passages)!=1:raise ValueError('Missing or duplicate Half Kaddish')
    words=''.join(''.join(n.itertext()) for n in passages[0].findall('.//{'+ns+'}parallelItem[@role="primary"]'))
    letters=''.join(c for c in unicodedata.normalize('NFD',words) if 'א'<=c<='ת')
    expected='לעלאלעלאמןכלברכתא' if ten_days else 'לעלאמןכלברכתא'
    if letters.count('לעלא')!=(2 if ten_days else 1) or expected not in letters:
        raise ValueError('Half Kaddish seasonal reading differs')


def titles(front, readings):
    from opensiddur.importer.util.occasion import gate, title_page
    for lang in ['he', 'en']:
        data = readings[lang]
        pb(front, data['scan'], '[unnumbered]')
        opening, closing = gate('asher_title_page_'+lang, title_page())
        def marker(markup):
            wrapper = etree.fromstring(('<wrapper xmlns:tei="'+TEI+'" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">'+markup+'</wrapper>').encode())
            front.extend(wrapper)
        marker(opening)
        page = element(front, 'titlePage')
        page.set(XML+'lang', lang)
        title = element(page, 'docTitle')
        for i, words in enumerate(data['titles']):
            element(title, 'titlePart', words, type='main' if i == 0 else 'sub')
        element(page, 'docEdition', data['edition'])
        if data.get('byline'):
            element(page, 'byline', data['byline']+' '+data['credentials'])
        imprint = element(page, 'docImprint')
        for tag, key in [('pubPlace','place'),('publisher','publisher'),('pubPlace','address'),('docDate','date')]:
            element(imprint, tag, data[key])
        marker(closing)


def rubric(parent, parts):
    note = element(parent, 'note', type='instruction')
    note.set(XML+'lang', 'en')
    last = None
    for part in parts:
        if part['lang'] == 'en':
            if last is None:
                note.text = (note.text or '') + part['text']
            else:
                last.tail = (last.tail or '') + part['text']
        else:
            last = element(note, 'foreign', part['text'])
            last.set(XML+'lang', part['lang'])
    return note


def verse(parent, urn, words):
    node = element(parent, 'milestone', unit='verse', corresp=urn)
    node.tail = words+' '


def opening(lang, project, data):
    root, text = document(lang, project, 'First-day Selichot', FIRST_DAY)
    div = element(element(text, 'body'), 'div', corresp=FIRST_DAY)
    pb(div, data['start_scan'], '[unnumbered]')
    element(div, 'head', data['heading'])
    for parts in data['rubrics']:
        rubric(div, parts)
    ashrei = element(div, 'div', corresp=PRAYER+'ashrei')
    p = element(ashrei, 'p')
    for urn, words in zip(['psalms/84/5','psalms/144/15'], data['prelude']):
        verse(p, 'urn:x-opensiddur:text:bible:'+urn, words)
    p = element(ashrei, 'p', corresp=PRAYER+'ashrei/tehila_ledavid')
    for n, words in enumerate(data['psalm'], 1):
        verse(p, f'urn:x-opensiddur:text:bible:psalms/145/{n}', words)
        if n == 1 and data.get('psalm_label'):
            p[-1].tail = ''
            citation = element(p, 'foreign', data['psalm_label'])
            citation.set(XML+'lang','en')
            citation.tail = ' '+words+' '
        if n == 9:
            brk = pb(p, data['next_scan'], data['next_label'])
            brk.tail = data['verse_9_continuation']+' '
    element(ashrei, 'p', data['postlude'], corresp=PRAYER+'ashrei/quoted_115_18')
    for parts in data['kaddish_rubrics']:
        rubric(div, parts)
    p = element(element(div, 'div'), 'p')
    for urn, words in zip(['numbers/14/17','psalms/25/6'], data['kaddish_preface']):
        verse(p, 'urn:x-opensiddur:text:bible:'+urn, words)
    kad = element(div, 'div', corresp=PRAYER+'kaddish/chatzi')
    element(kad, 'p', data['kaddish'][0], corresp=PRAYER+'kaddish/yitgadal')
    p = element(kad, 'p')
    split = unicodedata.normalize('NFKD', 'יִתְבָּרַךְ') if lang == 'he' else 'and may his hallowed'
    words = unicodedata.normalize('NFKD',data['kaddish'][1])
    before, after = words.split(split, 1)
    verse(p, PRAYER+'kaddish/yehe_shmeh', before.rstrip())
    verse(p, PRAYER+'kaddish/yitbarakh', split+after)
    if lang=='he':
        # The scan prints one le'ela; the seasonal addition is editorial.
        node=p[-1];word=unicodedata.normalize('NFKD','לְעֵלָּא')
        prefix,suffix=node.tail.split(word,1);node.tail=prefix+word
        condition=element(p,'j:conditional');condition.set(XML+'id','asher_half_kaddish_ten_days')
        fs=element(condition,'fs',type='opensiddur:holiday-aggregate')
        feature=element(fs,'f');feature.set('name','aseret-ymei-tshuva')
        element(feature,'binary',value='true');condition.tail=' '+word
        element(p,'j:endConditional',target='#asher_half_kaddish_ten_days').tail=suffix
    return root


def entry(lang, project, title_data, expanded=False, *, book=False, include_second_day=False, include_third_day=False, additional_days=(), include_erev=False, include_gedaliah=False, include_penitential_second=False, penitential_days=(), include_erev_yom_kippur=False, remaining_services=()):
    urn = ('urn:x-opensiddur:text:siddur:selichot' + ('/expanded' if expanded else '')) if book else FIRST_DAY
    title = 'Asher Selichoth' if book else 'First-day Selichot'
    if expanded:
        title += ' — expanded edition'
    root, text = document(lang, project, title, urn, index=book)
    edition = root.find(f'.//{{{TEI}}}edition')
    edition.text = 'Complete first-day coverage through Archive leaves n51–52, ending before the second-day heading. Hebrew pointing awaits independent proofreading.'
    if book and include_second_day:
        edition.text = 'First and second days through Archive leaves n59–60, ending before the third-day heading. Hebrew pointing awaits independent proofreading; remaining days await encoding.'
    if book and include_third_day:
        edition.text = 'First three days through Archive leaves n67–68, ending before the fourth-day heading. Hebrew pointing awaits independent proofreading; remaining days await encoding.'
    if book and additional_days:
        edition.text = 'Complete services through the '+additional_days[-1]+' day. Hebrew pointing awaits independent proofreading; later services await encoding.'
    if include_erev:
        edition.text = 'First seven services and Erev Rosh Hashanah through Archive n183/n184, ending before the Fast of Gedaliah. Hebrew pointing awaits independent proofreading; later services await encoding.'
    if include_gedaliah:
        edition.text = 'Complete services through Tzom Gedaliah, Archive n207/n208 (printed 103). Hebrew pointing awaits independent proofreading; later services await encoding.'
    if include_penitential_second:
        edition.text = 'Complete services through the second penitential day, Archive n231/n232 (printed 115). Hebrew pointing awaits independent proofreading; later services await encoding.'
    if penitential_days:
        edition.text='Complete services through the '+penitential_days[-1]+' penitential day. Hebrew pointing awaits independent proofreading; later services await encoding.'
    if include_erev_yom_kippur:
        edition.text='Complete services through Erev Yom Kippur, Archive n319/n320 (printed 159), before the Second Fast. Hebrew pointing awaits independent proofreading; later services await encoding.'
    if remaining_services:
        edition.text='Complete services through '+remaining_services[-1].replace('-', ' ')+'. Hebrew pointing awaits independent proofreading; later services await encoding.'
    if 'circumcision' in remaining_services:
        edition.text='All services through the final circumcision pizmon, Archive n410 (printed204). Hebrew pointing awaits independent proofreading.'
    if expanded:
        edition.text += ' Repeated passages are supplied by transclusion; the unprinted Full Kaddish uses the secondary edition selected in export settings.'
    if book:
        titles(element(text, 'front'), title_data)
    div = element(element(text, 'body'), 'div', corresp=urn)
    if book:
        from .occasions import gated_transclusion
        from .penitential_days import service_urn
        services = [('first', FIRST_DAY)]
        if include_second_day:
            from .second_day import SECOND_DAY
            services.append(('second', SECOND_DAY))
        if include_third_day:
            from .third_day import THIRD_DAY
            services.append(('third', THIRD_DAY))
        services += [(day_name, 'urn:x-opensiddur:text:siddur:selichot/'+day_name+'_day') for day_name in additional_days]
        if include_erev:
            from .erev_rosh_hashanah import EREV
            services.append(('erev-rosh-hashanah', EREV))
        if include_gedaliah:
            from .tzom_gedaliah import GEDALIAH
            services.append(('tzom-gedaliah', GEDALIAH))
        if include_penitential_second:
            from .penitential_second_day import PENITENTIAL_SECOND_DAY
            services.append(('penitential-second', PENITENTIAL_SECOND_DAY))
        services += [('penitential-'+day, service_urn(day)) for day in penitential_days]
        if include_erev_yom_kippur:
            services.append(('erev-yom-kippur', service_urn('erev-yom-kippur')))
        services += [(day, service_urn(day)) for day in remaining_services]
        # Each service behind the day it is said on, declaring what that day fixes.
        markup=''.join(part for service, target in services for part in gated_transclusion(service, target))
        div.extend(etree.fromstring(('<wrapper xmlns:tei="'+TEI+'" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">'+markup+'</wrapper>').encode()))
        return root
    return root


def documents(source):
    include_second_day = (source/'second-day.json').exists()
    include_third_day = (source/'third-day.json').exists()
    additional_days = tuple(day for day in ['fourth','fifth','sixth','seventh'] if (source/(day+'-day.json')).exists())
    structure = source.parent/'poetry-structure.json'
    poetry = json.loads(structure.read_text(encoding="utf-8"))['units'] if structure.exists() else {}
    title_data = json.loads((source/'title-pages.json').read_text(encoding="utf-8"))
    reading = json.loads((source/'first-day-opening.json').read_text(encoding="utf-8"))
    continuation = json.loads((source/'first-day-continuation.json').read_text(encoding="utf-8"))['sections']
    for lang in ['he','en']:
        project = project_name(lang)
        yield project, 'index.xml', entry(lang, project, title_data, book=True, include_second_day=include_second_day, include_third_day=include_third_day, additional_days=additional_days, include_erev=(source/'erev-rosh-hashanah.json').exists(), include_gedaliah=(source/'tzom-gedaliah.json').exists(), include_penitential_second=(source/'penitential-second-day.json').exists(), penitential_days=tuple(d for d in ['third','fourth','fifth'] if (source/('penitential-'+d+'-day.json')).exists()), include_erev_yom_kippur=(source/'erev-yom-kippur.json').exists(), remaining_services=tuple(d for d in ['monday-fast','thursday-fast','last-monday-fast','tenth-tevet','esther-fast','tammuz-fast','yom-kippur-katan','circumcision'] if (source/(d+'.json')).exists()))
        yield project, 'expanded.xml', entry(lang, project, title_data, expanded=True, book=True, include_second_day=include_second_day, include_third_day=include_third_day, additional_days=additional_days, include_erev=(source/'erev-rosh-hashanah.json').exists(), include_gedaliah=(source/'tzom-gedaliah.json').exists(), include_penitential_second=(source/'penitential-second-day.json').exists(), penitential_days=tuple(d for d in ['third','fourth','fifth'] if (source/('penitential-'+d+'-day.json')).exists()), include_erev_yom_kippur=(source/'erev-yom-kippur.json').exists(), remaining_services=tuple(d for d in ['monday-fast','thursday-fast','last-monday-fast','tenth-tevet','esther-fast','tammuz-fast','yom-kippur-katan','circumcision'] if (source/(d+'.json')).exists()))
        service = entry(lang, project, title_data)
        service_div = service.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
        root = opening(lang, project, reading[lang])
        div = root.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
        units = [div.find(f'{{{TEI}}}div[@corresp="{PRAYER}ashrei"]'),
                 next(n for n in div.findall(f'{{{TEI}}}div') if not n.get('corresp')),
                 div.find(f'{{{TEI}}}div[@corresp="{PRAYER}kaddish/chatzi"]')]
        for unit, filename, urn, scan, label in zip(units,
                ['ashrei', 'kaddish_selichot_preface', 'kaddish_chatzi'],
                [PRAYER+'ashrei', PRAYER+'kaddish/selichot_preface', PRAYER+'kaddish/chatzi'],
                [reading[lang]['start_scan'], reading[lang]['next_scan'], reading[lang]['next_scan']],
                ['[unnumbered]', reading[lang]['next_label'], reading[lang]['next_label']]):
            unit.set('corresp', urn)
            position = div.index(unit)
            div.remove(unit)
            transclusion = element(div, 'j:transclude', target=urn)
            div.remove(transclusion); div.insert(position, transclusion)
            page = pb(unit, scan, label); unit.remove(page); unit.insert(0, page)
            module, module_text = document(lang, project, filename.replace('_', ' '), urn)
            element(module_text, 'body').append(unit)
            yield project, filename+'.xml', module
        service_div.extend(list(div))
        for name, groups in continuation.items():
            if name == 'before_piyyut':
                for prayer in ['el_melekh_yoshev', 'vayaavor']:
                    element(service_div, 'j:transclude', target=PRAYER+prayer)
            elif name == 'closing':
                element(service_div, 'j:transclude', target=POEM)
            root = section(lang, project, name, groups, poetry)
            div = root.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
            for unit, group in zip(list(div), groups):
                if group['kind'] == 'rubric':
                    continue
                filename, _ = TEXTS[group['id']]
                urn = text_urn(group['id'])
                position = div.index(unit)
                div.remove(unit)
                transclusion = element(div, 'j:transclude', target=urn)
                div.remove(transclusion); div.insert(position, transclusion)
                if filename in PRINTED_IN_FULL:
                    continue
                module, module_text = document(lang, project, group.get('incipit_he', filename.replace('_', ' ')), urn)
                if group.get('incipit_he'):
                    module.find(f'.//{{{TEI}}}title').set(XML+'lang', 'he')
                element(module_text, 'body').append(unit)
                yield project, filename+'.xml', module
            service_div.extend(list(div))
        yield project, 'first_day.xml', service


EXPANSION_TARGETS = {
    'after_first_selihah_rubric': [text_urn('morning_scriptural_petitions')+'/repeat', text_urn('daniel_petition')+'/repeat'],
    'after_second_selihah_verses': [text_urn('morning_scriptural_petitions')+'/repeat', text_urn('daniel_petition')+'/repeat'],
    'after_second_selihah_prayers': [PRAYER+'el_melekh_yoshev', PRAYER+'vayaavor'],
    'after_third_selihah_prayers': [PRAYER+'el_melekh_yoshev', PRAYER+'vayaavor'],
    'ashamnu_repeat': [PRAYER+'ashamnu'],
    'ashamnu_repeat_2': [PRAYER+'ashamnu'],
    'reader_kaddish': [PRAYER+'kaddish/shalem'],
}


def expansion_scope(parent, identity, present, *, feature='repetitions_present'):
    conditional_scope(parent, identity, present, fs_type='asher:expansions', feature=feature)


def section(lang, project, name, groups, poetry=None):
    urn = FIRST_DAY+'/'+name
    root, text = document(lang, project, 'First day: '+name.replace('_',' '), urn)
    div = element(element(text,'body'),'div',corresp=urn)
    for group in groups:
        context = text_urn(group['id']) if group['id'] in TEXTS else FIRST_DAY+'/'+group['id']
        unit = element(div,'div',corresp=context)
        first = group['fragments'][0][lang]
        pb(unit,first['scan'],first['printed_page'])
        kind = group['kind']
        poetic_rule = (poetry or {}).get(group['id']) if lang == 'he' else None
        targets = EXPANSION_TARGETS.get(group['id'])
        if targets:
            expansion_scope(unit, group['id']+'_printed', False)
        if kind == 'rubric':
            node = element(unit,'note',type='instruction');node.set(XML+'lang','en')
        elif poetic_rule or (kind == 'poem' and lang == 'he'):
            node = element(unit,'lg')
        else:
            node = element(unit,'p')
        if poetic_rule:
            poetic_lines(node, group['fragments'], poetic_rule)
        for i, fragment in enumerate([] if poetic_rule else group['fragments']):
            data = fragment[lang]
            if i:
                pb(node,data['scan'],data['printed_page'])
            words = data['text']
            if kind == 'rubric' and lang == 'he':
                mixed_words(node,words)
            elif kind == 'poem' and lang == 'he':
                # The printed invocation is an introductory verse, not a heading.
                if i == 0 and words.startswith('אלהינו ואלהי אבותינו\n'):
                    invocation, words = words.split('\n', 1)
                    element(node, 'l', invocation)
                # Printed verse stops delimit verses; middle dots remain phrase stops.
                for line in re.findall(r'[^׃]+׃|[^׃]+$',words):
                    element(node,'l',line.strip())
            elif kind == 'litany':
                for n,line in enumerate(words.splitlines(),1):
                    if n>1:element(node,'lb')
                    words_with_notes(node,line,fragment['notes'][lang] if n==8 else [],lang)
                    append_words(node,' ')
            else:
                if i == 0 and group.get('repeat_start'):
                    if fragment['notes'][lang]:
                        raise ValueError('Repeat boundary needs explicit footnote placement')
                    before, after = words.split(group['repeat_start'][lang], 1)
                    append_words(node, before)
                    milestone = element(node, 'milestone', unit='repeat-range', corresp=context+'/repeat')
                    milestone.tail = group['repeat_start'][lang]+after
                else:
                    words_with_notes(node,words,fragment['notes'][lang],lang)
            if not data.get('join_next'):
                append_words(node,' ')
        if group.get('repeat_start'):
            element(node, 'milestone', unit='repeat-range')
        if targets:
            element(unit, 'j:endConditional', target='#'+group['id']+'_printed')
            expansion_scope(unit, group['id']+'_expanded', True)
            if group['id'] == 'reader_kaddish':
                declaration = element(unit, 'j:declare')
                declaration.set(XML+'id', 'first_day_selichot_kaddish')
                fs = element(declaration, 'fs', type='asher:selichot')
                f = element(fs, 'f'); f.set('name', 'first_day')
                element(f, 'binary', value='true')
                fs = element(declaration, 'fs', type='opensiddur:holiday-aggregate')
                f = element(fs, 'f'); f.set('name', 'aseret-ymei-tshuva')
                element(f, 'binary', value='false')
            for target in targets:
                element(unit, 'j:transclude', target=target)
            if group['id'] == 'reader_kaddish':
                element(unit, 'j:endDeclare', target='#first_day_selichot_kaddish')
            element(unit, 'j:endConditional', target='#'+group['id']+'_expanded')
    return root


def poetic_lines(node, fragments, rule):
    """Apply this edition's facsimile convention to shared verse authoring."""
    return _poetic_lines(node, fragments, rule, page_break=pb)
