"""Build documentary and expanded second-day morning sequences, scans25–45."""
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path

import yaml
from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.importer.marmorstein_rosh_hashanah_1.build import words
from opensiddur.importer.scan.authoring import TEI, XML, element, write_documents
from opensiddur.importer.util.internet_archive import page_image_url
from opensiddur.importer.util.validation import validate

from . import BOOK, IDENTIFIER, PROJECTS, ROOT_URN
from .morning_shared import (
    BARUKH_TRANSLATION,
    approved_readings,
    declaration,
    expressions,
    feature,
)
from .morning_witnesses import witness_header

T = '{'+TEI+'}'
EXPANDED = 'machzor_expanded-opensiddur-he'
EXPANDED_URN = 'urn:x-opensiddur:text:siddur:machzor_expanded/rosh_hashanah/day_two/shacharit'
MORNING_URN = ROOT_URN+'/shacharit'


def transclude(parent, target, *, project=None):
    return element(parent, 'j:transclude', type='external',
                   target=target+(('@'+project) if project else ''))


def conditional(parent, identifier, condition, *, label=None):
    node = element(parent, 'j:conditional')
    node.set(XML+'id', identifier)
    if label:
        note = element(node, 'note', type='instruction', resp='urn:x-opensiddur:contributor:opensiddur.org/codex')
        for lang, text in label.items():
            phrase = element(note, 'foreign', text)
            phrase.set(XML+'lang', lang)
    operator = element(node, 'j:none' if condition=='not_german' else 'j:all')
    types = {'german': ('opensiddur:rite','german',True),
             'not_german': ('opensiddur:rite','german',True),
             'male': ('opensiddur:person','gender','male'),
             'female': ('opensiddur:person','gender','female'),
             'shabbat': ('opensiddur:holiday-aggregate','shabbat',True)}
    kind, name, value = types[condition]
    fs = element(operator, 'fs', type=kind)
    field = element(fs, 'f')
    field.set('name', name)
    if isinstance(value, bool):
        element(field, 'binary', value='true')
    else:
        element(field, 'symbol', value=value)
    return node


def instruction(parent, item, lang, *, expanded):
    source = item['source']
    if not expanded and lang not in source['witnesses']:
        return
    node = element(parent, 'note', type=source.get('type', 'instruction'))
    node.set(XML+'lang', source['language'])
    node.set('facs', page_image_url(IDENTIFIER, int(source['scan'][1:])-1, size=''))
    text = source['text']
    navigation = item.get('documentary_navigation')
    if navigation:
        match = re.search(r'\((?:P\. |page )\d+\.?\)', text)
        if match is None:
            raise ValueError('Expected exact printed page clause')
        words(node, text[:match.start()], source['language'])
        segment = element(node, 'seg', type='optional-page-reference')
        segment.text = '(P. ' if 'P.' in match[0] else '(page '
        reference = element(segment, 'ref', type='page', target=navigation['target_by_language'][lang])
        reference.tail = '.)' if 'P.' in match[0] else ')'
        segment.tail = text[match.end():]
    else:
        words(node, text, source['language'])


def sequence_document(plan, units, shared, features, lang, *, expanded=False, expanded_index=None):
    if expanded:
        root = deepcopy(expanded_index)
        for child in list(root):
            if child.tag != T+'teiHeader':
                root.remove(child)
        desc = root.find(T+'teiHeader/'+T+'fileDesc')
        desc.find(T+'titleStmt/'+T+'title').text = 'Second-day morning prayers'
        desc.find(T+'editionStmt/'+T+'edition').text = (
            'Expanded second-day morning sequence. Source, encoding and presentation '
            'review records are in sources/marmorstein_rosh_hashanah_2/batches/morning_s25_s45/.')
        desc.find(T+'publicationStmt/'+T+'idno').text = EXPANDED_URN+'@'+EXPANDED
        source = desc.find(T+'sourceDesc')
        source.clear()
        for project in PROJECTS.values():
            element(element(source,'bibl'),'ptr',target='/'+project+'/index#day_two_source_bibl')
        body = element(element(root, 'text'), 'body')
        div = element(body, 'div', corresp=EXPANDED_URN)
    else:
        title = 'תְּפִלַּת שַׁחֲרִית' if lang=='he' else 'Morning Prayer'
        root, body = witness_header(lang, PROJECTS[lang], title, MORNING_URN, draft=True)
        div = element(body, 'div', corresp=MORNING_URN)
    declaration(div, 'morning_printings', expressions(features, 'morning'))
    if expanded:
        selection = element(div, 'j:conditional')
        selection.set(XML+'id', 'second_day_morning_selection')
        all_conditions = element(selection, 'j:all')
        for fs_type, name, value in [('opensiddur:holiday','rosh-hashana',2), ('opensiddur:service-time','shaharit',True)]:
            field = element(element(all_conditions,'fs',type=fs_type),'f')
            field.set('name',name)
            element(field,'binary' if isinstance(value,bool) else 'numeric',value=str(value).lower())
    instructions = plan['local_instructions']
    documentary = {i['key']: i for i in plan['documentary_order']}
    shared_units = set(shared['units'])
    sections = {}
    current = div

    def section(key):
        nonlocal current
        group = 'tallit' if key.startswith('tallith_') else ('preliminaries' if key in [i['key'] for i in plan['documentary_order'][4:9]] else 'blessings')
        if group in sections:
            current = sections[group]
            return
        current = element(div, 'div')
        current.set(XML+'id','morning_'+group)
        sections[group] = current
        headings = {'tallit':['morning_tallit_heading'], 'preliminaries':['morning_prayers_heading_he','morning_prayers_heading_en'], 'blessings':['blessings_heading_he','blessings_heading_en']}[group]
        for item in instructions:
            if item['key'] in headings and (expanded or lang in item['source']['witnesses']):
                heading = element(current,'head',item['source']['text'])
                heading.set(XML+'lang',item['source']['language'])
        if expanded and group=='tallit':
            head = element(current,'head','Wrapping in the tallit', resp='urn:x-opensiddur:contributor:opensiddur.org/codex')
            head.set(XML+'lang','en')

    def notes(parent,key,relation):
        seen = set()
        for item in instructions:
            if item['placement']['relation'] != relation or item['placement']['unit_or_group'] != key:
                continue
            if expanded and item.get('documentary_navigation'):
                continue
            if not expanded and lang not in item['source']['witnesses']:
                continue
            signature=(item['source']['text'],item['source']['language'])
            if expanded and signature in seen:
                continue
            seen.add(signature)
            instruction(parent,item,lang,expanded=expanded)

    def call(parent,key):
        unit = units[key]
        if not expanded and lang not in unit['languages']:
            return
        notes(parent,key,'before')
        if expanded and key in ('morning_entrance_verses','morning_before_prayer'):
            occurrence = element(parent,'div')
            occurrence.set(XML+'id','expanded_'+key)
            for index, target in enumerate(documentary[key]['canonical_targets']):
                if key=='morning_before_prayer' and index==14:
                    values={feature(target,p):p=='repeat' for p in ('night','morning','repeat')}
                    declaration(occurrence,'repeated_psalm_printing',values)
                transclude(occurrence,target)
                if key=='morning_before_prayer' and index==14:
                    element(occurrence,'j:endDeclare',target='#repeated_psalm_printing')
        elif expanded and key=='qorbanot_barukh_shem':
            target=unit['urn']
            declaration(parent,'qorbanot_barukh_shem_printing', {
                **{feature(target,p):p=='qorbanot' for p in ('night','morning','qorbanot')}, BARUKH_TRANSLATION:False})
            transclude(parent,target)
            element(parent,'j:endDeclare',target='#qorbanot_barukh_shem_printing')
        else:
            if not expanded and key in shared_units:
                target=ROOT_URN+'/morning_occurrences/'+key
            elif not expanded and documentary[key].get('documentary_target'):
                target=documentary[key]['documentary_target']
            else:
                target=documentary[key]['canonical_target']
            transclude(parent,target,project=None if expanded else PROJECTS[lang])
        notes(parent,key,'after')

    source_conditions = {'qorbanot_musaf_shabbat':'shabbat',
                         'birkhot_hashachar_shelo_asani_ishah':'male',
                         'birkhot_hashachar_sheasani_kirtzono':'female'}
    items = plan['expanded_order'] if expanded else [{'key':i['key'], 'condition':source_conditions.get(i['key'])}for i in plan['documentary_order']]
    for item in items:
        if 'group' in item:
            label=({'he':'שלא כמנהג אשכנז','en':'Outside the German rite'} if item['condition']=='not_german' else {'he':'למנהג אשכנז','en':'In the German rite'})
            conditional(current,item['group'],item['condition'],label=label)
            for key in item['keys']:
                call(current,key)
            element(current,'j:endConditional',target='#'+item['group'])
            continue
        key = item['key']
        if not expanded and lang not in units[key]['languages']:
            continue
        section(key)
        condition=item.get('condition')
        if condition:
            identifier='morning_'+key+'_condition'
            label=None
            if condition=='male' and expanded:
                label={'he':'לזכר','en':'Men'}
            control=conditional(current,identifier,condition,label=label)
            if expanded and condition=='shabbat':
                note=element(control,'note',type='instruction',resp='urn:x-opensiddur:contributor:opensiddur.org/codex')
                for language,label in [('he','בשבת'),('en','On Shabbat')]:
                    element(note,'foreign',label).set(XML+'lang',language)
            else:
                notes(control,key,'conditional_note')
            if expanded and condition=='female':
                for note in control.findall(T+'note'):
                    text=note.text
                    note.text=None
                    note.attrib.pop(XML+'lang',None)
                    element(note,'foreign','לנשים, במקום הברכה הקודמת:',resp='urn:x-opensiddur:contributor:opensiddur.org/codex').set(XML+'lang','he')
                    element(note,'foreign',text).set(XML+'lang','en')
            for note in list(control.findall(T+'note')):
                control.remove(note)
                control.insert(0,note)
        else:
            notes(current,key,'conditional_note')
        call(current,key)
        if condition:
            element(current,'j:endConditional',target='#'+identifier)
    if expanded:
        element(div,'j:endConditional',target='#second_day_morning_selection')
    element(div,'j:endDeclare',target='#morning_printings')
    return root


def write_profiles(settings_directory):
    """Keep book profiles reproducible after the earlier evening build stage."""
    he = settings_directory/PROJECTS['he']
    for variant in ['documentary_hebrew', 'documentary_parallel']:
        path = he/(variant+'.yaml')
        values = yaml.safe_load(path.read_text())
        values['requires_processor'] = '>=0.9.0.dev0'
        values['book']['title'] = 'Prayerbook for the New Year — second day'
        values['description'] = 'Second-day volume. Current per-scan acceptance is recorded in the source batch ledger.'
        path.write_text(yaml.safe_dump(values, sort_keys=False, allow_unicode=True))
    path = settings_directory/EXPANDED/'second_day_evening.yaml'
    values = yaml.safe_load(path.read_text())
    values['requires_processor'] = '>=0.9.0.dev0'
    path.write_text(yaml.safe_dump(values, sort_keys=False, allow_unicode=True))
    values = deepcopy(values)
    values['book']['file_name'] = 'second_day_morning.xml'
    values['book']['title'] = 'Prayerbook for the New Year — second-day morning prayers'
    values['description'] = 'Expanded second-day morning sequence using source-attested printings and canonical prayer transclusions.'
    values['declarations']['opensiddur:service-time']['maariv'] = False
    values['declarations']['opensiddur:service-time']['shaharit'] = True
    (path.parent/'second_day_morning.yaml').write_text(yaml.safe_dump(values, sort_keys=False, allow_unicode=True))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory',type=Path,default=PROJECT_DIRECTORY)
    args=parser.parse_args(argv)
    batch=args.source_root/BOOK/'batches/morning_s25_s45'
    plan=json.loads((batch/'morning_order.json').read_text())
    units={u['stem']:u for u in approved_readings(batch,plan)['units']}
    shared=json.loads((batch/'shared_printings.json').read_text())
    features=json.loads((batch/'shared_features.json').read_text())
    index=etree.parse(str(args.project_directory/EXPANDED/'index.xml')).getroot()
    documents=[(args.project_directory/PROJECTS[lang]/'morning.xml',sequence_document(plan,units,shared,features,lang))for lang in ('he','en')]
    documents.append((args.project_directory/EXPANDED/'second_day_morning.xml',sequence_document(plan,units,shared,features,'he',expanded=True,expanded_index=index)))
    for project in PROJECTS.values():
        path=args.project_directory/project/'index.xml'
        root=etree.parse(str(path)).getroot()
        root.find('.//'+T+'editionStmt/'+T+'edition').text = (
            'JLPTEI source volume in progress. Current encoded scope and per-scan '
            'acceptance are recorded in sources/marmorstein_rosh_hashanah_2/progress.json.')
        div=root.find('.//'+T+'body/'+T+'div')
        target=MORNING_URN+'@'+project
        if not any(node.get('target')==target for node in div):
            transclude(div,MORNING_URN,project=project)
        documents.append((path,root))
    for path in write_documents(documents,validator=validate):
        print(path)
    write_profiles(args.project_directory.parent/'settings')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
