"""Verify the edition against independent documentary streams and its expansion policy."""
from opensiddur.importer.scan.authoring import printed_text

from opensiddur.importer.scan.authoring import check_poetry

import argparse
import json
import unicodedata
from pathlib import Path
from lxml import etree
from opensiddur.common.constants import SOURCETEXTS_ROOT, PROJECT_DIRECTORY
from opensiddur.importer.scan.reverse import streams, check
from opensiddur.importer.util.validation import validate
from .build import TEI, J, POEM, PRAYER, spelled_name, spelled_urn
from .identities import project_name


def verify(source_root, project_directory):
    source=Path(source_root)/'asher_selichot/scan_reading'
    payload=json.loads((source/'documentary-streams.json').read_text())
    expected={(page,lang):text for page,langs in payload.items() for lang,text in langs.items()}
    actual={}
    data=json.loads((source/'refrain-and-prayers.json').read_text())
    files=0
    for lang in ['he','en']:
        project=Path(project_directory)/project_name(lang)
        from .first_day import OBSOLETE_ASSEMBLIES
        if any((project/(spelled_name(name)+'.xml')).exists() for name in OBSOLETE_ASSEMBLIES):
            raise ValueError('Obsolete artificial grouping files must not remain')
        for path in sorted(project.glob('*.xml')):
            valid,errors=validate(path)
            if not valid:raise ValueError(f'{path}: {errors}')
            files+=1
        for name in ['bemotzaei_menuhah','el_melekh_yoshev','vayaavor']:
            root=etree.parse(str(project/(spelled_name(name)+'.xml'))).getroot()
            if name == 'bemotzaei_menuhah':
                check_poem_expansion(root)
            for key,text in streams(root,include_notes=True).items():
                actual[key]=(actual.get(key,'')+' '+text).strip()
        root=etree.parse(str(project/(spelled_name('bemotzaei_menuhah')+'.xml')))
        choices=root.findall(f'.//{{{TEI}}}choice[{{{TEI}}}abbr]')
        if len(choices)!=(7 if lang=='he' else 6):
            raise ValueError(f'{lang}: missing or duplicated refrain choices')
        for node in choices:
            abbr=node.find(f'{{{TEI}}}abbr');expan=node.find(f'{{{TEI}}}expan')
            if abbr is None or expan is None or not ''.join(expan.itertext()).strip():
                raise ValueError('Each refrain needs a printed cue and a nonempty expansion')
        if lang=='he':
            expected_final=' '.join(data['he']['poem']['stanzas'][0])
            refrain=data['he']['poem']['final_refrain']
        else:
            expected_final=data['en']['poem']['stanzas'][0]
            refrain='to hearken unto our hymns of praise, and unto our supplication.'
        normalize = lambda text: ' '.join(unicodedata.normalize('NFKD', text).split())
        if normalize(''.join(choices[-1].find(f'{{{TEI}}}expan').itertext()))!=normalize(expected_final):
            raise ValueError('Concluding cue must expand to the entire opening stanza')
        if any(normalize(''.join(c.find(f'{{{TEI}}}expan').itertext()))!=normalize(refrain) for c in choices[:-1]):
            raise ValueError('Short cue must expand to this edition’s printed refrain')
        from .first_day import FIRST_DAY
        targets = [FIRST_DAY]
        if (source/'second-day.json').exists():
            from .second_day import SECOND_DAY
            targets.append(SECOND_DAY)
        if (source/'third-day.json').exists():
            from .third_day import THIRD_DAY
            targets.append(THIRD_DAY)
        targets.extend('urn:x-opensiddur:text:siddur:selichot/'+day+'_day' for day in ['fourth','fifth','sixth','seventh'] if (source/(day+'-day.json')).exists())
        if (source/'erev-rosh-hashanah.json').exists():
            from .erev_rosh_hashanah import EREV
            targets.append(EREV)
        if (source/'tzom-gedaliah.json').exists():
            from .tzom_gedaliah import GEDALIAH
            targets.append(GEDALIAH)
        if (source/'penitential-second-day.json').exists():
            from .penitential_second_day import PENITENTIAL_SECOND_DAY
            targets.append(PENITENTIAL_SECOND_DAY)
        from .penitential_days import SERVICES,manifest_name,service_urn
        targets.extend(service_urn(d) for d in SERVICES if (source/(manifest_name(d)+'.json')).exists())
        for name in ['index.xml', 'expanded.xml']:
            entry=etree.parse(str(project/name))
            if [n.get('target') for n in entry.findall(f'.//{{{J}}}transclude')]!=[spelled_urn(t) for t in targets]:
                raise ValueError(f'{name}: unexpected reference expansion boundary')
    verify_opening(source, Path(project_directory))
    verify_continuation(source, Path(project_directory))
    if (source/'second-day.json').exists():
        from .second_day import verify_readings
        verify_readings(source, Path(project_directory))
    if (source/'third-day.json').exists():
        from .third_day import verify_readings
        verify_readings(source, Path(project_directory))
    from .second_day import verify_numbered_readings
    for day in ['fourth','fifth','sixth','seventh']:
        if (source/(day+'-day.json')).exists():verify_numbered_readings(source, Path(project_directory), day)
    if (source/'erev-rosh-hashanah.json').exists():
        from .erev_rosh_hashanah import verify_readings as verify_erev
        verify_erev(source,Path(project_directory))
    if (source/'tzom-gedaliah.json').exists():
        from .tzom_gedaliah import verify_readings as verify_gedaliah
        verify_gedaliah(source,Path(project_directory))
    if (source/'penitential-second-day.json').exists():
        from .penitential_second_day import verify_readings as verify_penitential
        verify_penitential(source,Path(project_directory))
    from .penitential_days import SERVICES, manifest_name, verify_readings as verify_later_penitential
    for day in SERVICES:
        if (source/(manifest_name(day)+'.json')).exists():
            verify_later_penitential(source,Path(project_directory),day)
    differences=check(actual,expected)
    if differences:raise ValueError(differences)
    print(f'{files} schema-valid files; {len(actual)} documentary page/language streams match; expansion targets and forms checked')
    return actual


def check_poem_expansion(root):
    """Audit the supplied prayers, then select the printed branch for comparison."""
    div=root.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
    scopes=[('prayer_instruction','false'),('prayer_instruction_expanded','true')]
    for identity,value in scopes:
        scope=div.find(f'{{{J}}}conditional[@xml:id="{identity}"]',
                       namespaces={'xml':'http://www.w3.org/XML/1998/namespace'})
        if scope is None:raise ValueError('Poem conclusion needs printed and supplied branches')
        binary=scope.find(f'{{{TEI}}}fs[@type="asher:expansions"]/{{{TEI}}}f[@name="prayers_present"]/{{{TEI}}}binary')
        if binary is None or binary.get('value')!=value:
            raise ValueError('Poem conclusion branch polarity changed')
        if div.find(f'{{{J}}}endConditional[@target="#{identity}"]') is None:
            raise ValueError('Unclosed poem conclusion branch')
    if [n.get('target') for n in div.findall(f'{{{J}}}transclude')] != [spelled_urn(PRAYER+'el_melekh_yoshev'),spelled_urn(PRAYER+'vayaavor')]:
        raise ValueError('Poem must supply exactly its referenced conclusion prayers')
    start=div.find(f'{{{J}}}conditional[@xml:id="prayer_instruction_expanded"]',
                   namespaces={'xml':'http://www.w3.org/XML/1998/namespace'})
    end=div.find(f'{{{J}}}endConditional[@target="#prayer_instruction_expanded"]')
    children=list(div)
    for child in children[children.index(start):children.index(end)+1]:div.remove(child)


def continuation_units(project, groups):
    """Follow the flat printed-day sequence, refusing invented section wrappers."""
    from .first_day import FIRST_DAY
    from .identities import TEXTS, text_urn
    root=etree.parse(str(project/'first_day.xml')).getroot()
    div=root.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
    if div.get('corresp')!=FIRST_DAY or (div.text or '').strip():
        raise ValueError('First-day assembly must represent the printed service')
    children=list(div)
    half=div.find(f'{{{J}}}transclude[@target="{PRAYER}kaddish/chatzi"]')
    if half is None:raise ValueError('First day must begin with Ashrei and Half Kaddish')
    cursor=children.index(half)+1
    result=[]
    for name,readings in groups.items():
        inserted = ([PRAYER+'el_melekh_yoshev', PRAYER+'vayaavor'] if name=='before_piyyut'
                    else [POEM] if name=='closing' else [])
        for target in inserted:
            if cursor>=len(children) or children[cursor].tag!=f'{{{J}}}transclude' or children[cursor].get('target')!=spelled_urn(target):
                raise ValueError('Printed prayers and poem must follow source order')
            cursor+=1
        for reading in readings:
            if cursor>=len(children):raise ValueError('Missing first-day unit')
            unit=children[cursor];cursor+=1
            identity=spelled_urn(text_urn(reading['id']) if reading['id'] in TEXTS else FIRST_DAY+'/'+reading['id'])
            if reading['kind']!='rubric':
                if unit.tag!=f'{{{J}}}transclude' or unit.get('target')!=identity:
                    raise ValueError('Independent texts must be directly transcluded in printed order')
                module=etree.parse(str(project/(spelled_name(TEXTS[reading['id']][0])+'.xml')))
                publication=module.find(f'.//{{{TEI}}}publicationStmt/{{{TEI}}}idno[@type="urn"]')
                if publication.text!=identity+'@'+project.name:
                    raise ValueError('Publication identity must match the canonical transclusion')
                unit=module.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
            elif unit.tag!=f'{{{TEI}}}div':
                raise ValueError('Printed rubric must remain in its actual service position')
            if unit.get('corresp')!=identity:raise ValueError('Units out of source order')
            result.append((reading,unit))
    if cursor!=len(children):raise ValueError('Extra text or artificial grouping after the first-day units')
    return result


def opening_documentary(project):
    """Follow opening assembly references while retaining its printed rubrics/order."""
    import copy
    root=etree.parse(str(project/'first_day.xml')).getroot()
    div=root.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
    targets=[PRAYER+'ashrei', PRAYER+'kaddish/selichot_preface', PRAYER+'kaddish/chatzi']
    half=div.find(f'{{{J}}}transclude[@target="{PRAYER}kaddish/chatzi"]')
    if half is None:raise ValueError('Missing opening Half Kaddish')
    for child in list(div)[div.index(half)+1:]:div.remove(child)
    references=div.findall(f'{{{J}}}transclude')
    if [n.get('target') for n in references] != [spelled_urn(t) for t in targets]:
        raise ValueError('Opening must use canonical Ashrei and Kaddish modules in source order')
    for reference,filename in zip(references,['ashrei','kaddish_selichot_preface','kaddish_chatzi']):
        module=etree.parse(str(project/(spelled_name(filename)+'.xml')))
        publication=module.find(f'.//{{{TEI}}}publicationStmt/{{{TEI}}}idno[@type="urn"]')
        if publication.text != reference.get('target')+'@'+project.name:
            raise ValueError('Opening text filename and publication identity disagree')
        unit=copy.deepcopy(module.find(f'.//{{{TEI}}}body/{{{TEI}}}div'))
        if unit.get('corresp') != reference.get('target'):
            raise ValueError('Opening correspondence must match its canonical identity')
        # Remove the documented editorial addition before checking printed words.
        seasonal=unit.find('.//{'+J+'}conditional[@xml:id="asher_half_kaddish_ten_days"]',namespaces={'xml':'http://www.w3.org/XML/1998/namespace'})
        if seasonal is not None:
            end=seasonal.getnext();parent=seasonal.getparent();previous=seasonal.getprevious()
            feature=seasonal.find('.//{'+TEI+'}fs[@type="opensiddur:holiday-aggregate"]/{'+TEI+'}f[@name="aseret-ymei-tshuva"]/{'+TEI+'}binary[@value="true"]')
            addition=unicodedata.normalize('NFKD',' לְעֵלָּא')
            if feature is None or seasonal.tail!=addition:raise ValueError('Unexpected seasonal Half Kaddish addition')
            if end is None or end.tag!='{'+J+'}endConditional' or end.get('target')!='#asher_half_kaddish_ten_days':raise ValueError('Unclosed seasonal Half Kaddish')
            previous.tail=(previous.tail or '')+(end.tail or '')
            parent.remove(seasonal);parent.remove(end)
        div.replace(reference,unit)
    return root


def verify_opening(source, project_directory):
    """Check the shared service opening, partial verse and printed title pages."""
    payload=json.loads((source/'opening-documentary-streams.json').read_text())
    expected={(page,lang):words for page,langs in payload.items() for lang,words in langs.items()}
    actual={}
    titles=json.loads((source/'title-pages.json').read_text())
    for lang in ['he','en']:
        project=project_directory/project_name(lang)
        root=opening_documentary(project)
        actual.update(streams(root,include_notes=True))
        urns=[el.get('corresp') for el in root.iter() if el.get('corresp')]
        if len(urns)!=len(set(urns)):
            raise ValueError('Repeated correspondence within the opening module')
        verses=root.findall(f'.//{{{TEI}}}milestone[@corresp="urn:x-opensiddur:text:bible:psalms/145/9"]')
        if len(verses)!=1 or verses[0].getnext().tag!=f'{{{TEI}}}pb':
            raise ValueError('Psalm 145:9 must continue across its printed page break')
        front=etree.parse(str(project/'index.xml')).find(f'.//{{{TEI}}}front')
        title_streams={key:words for key,words in streams(front,include_notes=True).items() if words.strip()}
        wanted={}
        for title_lang in ['he','en']:
            data=titles[title_lang]
            words=data['titles']+[data['edition']]
            if data.get('byline'):words+=[data['byline'],data['credentials']]
            words += [data[key] for key in ['place','publisher','address','date']]
            wanted[(data['scan'],title_lang)]=' '.join(words)
        if check(title_streams,wanted):raise ValueError('Title pages differ from scan readings')
    differences=check(actual,expected)
    if differences:raise ValueError(differences)
    print(f'{len(actual)} opening page/language streams match; both title pages and first-day entry boundaries checked')


def verify_continuation(source, project_directory):
    """Compare authored units to source readings and printed footnote evidence."""
    import re
    import unicodedata
    from .first_day import EXPANSION_TARGETS, PRINTED_IN_FULL
    from .identities import TEXTS
    groups=json.loads((source/'first-day-continuation.json').read_text())['sections']
    poetry=json.loads((source.parent/'poetry-structure.json').read_text())['units']
    count=0
    for lang in ['he','en']:
        project=project_directory/project_name(lang)
        for reading,unit in continuation_units(project,groups):
            if lang == 'he' and reading['id'] in poetry:
                rule = poetry[reading['id']]
                if rule['verified_scans'] != [f['he']['scan'] for f in reading['fragments']]:
                    raise ValueError('Poetry adjudication has stale scan provenance')
                check_poetry(unit, rule)
            targets = EXPANSION_TARGETS.get(reading['id'])
            actual_targets = [n.get('target') for n in unit.findall(f'{{{J}}}transclude')]
            if actual_targets != [spelled_urn(t) for t in (targets or [])]:
                raise ValueError(f'{reading["id"]}: unexpected editorial expansion targets')
            if targets:
                # Audit the true branch, then remove it before documentary comparison.
                scopes = unit.findall(f'{{{J}}}conditional')
                if len(scopes) != 2:
                    raise ValueError('Expansion requires distinct printed and supplied branches')
                for scope, value in zip(scopes, ['false', 'true']):
                    binary = scope.find(f'{{{TEI}}}fs/{{{TEI}}}f/{{{TEI}}}binary')
                    if binary is None or binary.get('value') != value:
                        raise ValueError('Expansion branch polarity changed')
                if reading['id'] == 'reader_kaddish':
                    declaration = scopes[1].getnext()
                    if declaration is None or declaration.tag != f'{{{J}}}declare':
                        raise ValueError('Full Kaddish needs scoped first-day Selichot context')
                    wanted = {'asher:selichot': ('first_day', 'true'),
                              'opensiddur:holiday-aggregate': ('aseret-ymei-tshuva', 'false')}
                    for fs_type, (feature, value) in wanted.items():
                        binary = declaration.find(f'{{{TEI}}}fs[@type="{fs_type}"]/{{{TEI}}}f[@name="{feature}"]/{{{TEI}}}binary')
                        if binary is None or binary.get('value') != value:
                            raise ValueError('First-day Selichot must exclude Ten Days additions')
                    end_declare = unit.find(f'{{{J}}}endDeclare[@target="#first_day_selichot_kaddish"]')
                    if end_declare is None:raise ValueError('Unclosed first-day Kaddish declaration')
                start = scopes[1]
                end = unit.find(f'{{{J}}}endConditional[@target="#{start.get("{http://www.w3.org/XML/1998/namespace}id")}"]')
                if end is None:raise ValueError('Unclosed expansion branch')
                children = list(unit)
                for child in children[children.index(start):children.index(end)+1]:unit.remove(child)
            if reading.get('incipit_he'):
                invocation = reading['fragments'][0][lang]['text'].split('\n', 1)[0]
                node = unit.find(f'{{{TEI}}}lg/{{{TEI}}}l' if lang == 'he' else f'{{{TEI}}}p')
                if unit.findall(f'{{{TEI}}}head') or node is None or not ''.join(node.itertext()).startswith(invocation):
                    raise ValueError(f'{reading["id"]}: piyyut invocation must remain in its opening text')
            expected_notes=[n['text'] for f in reading['fragments'] for n in f['notes'][lang]]
            notes=unit.findall(f'.//{{{TEI}}}note[@type="commentary"]')
            normalize=lambda text:' '.join(unicodedata.normalize('NFKD',text).split())
            if [normalize(printed_text(n,' ')) for n in notes]!=list(map(normalize,expected_notes)):
                raise ValueError(f'{reading["id"]}: missing or changed printed footnote')
            # Exclude apparatus after checking it separately, preserving surrounding body text.
            for note in notes:
                parent=note.getparent();previous=note.getprevious()
                if previous is None:parent.text=(parent.text or '')+(note.tail or '')
                else:previous.tail=(previous.tail or '')+(note.tail or '')
                parent.remove(note)
            expected={}
            for f in reading['fragments']:
                data=f[lang];page=data['scan'];words=data['text']
                if reading['kind']=='rubric' and lang=='he':
                    # Independent language separation: Hebrew letters/marks and attached punctuation
                    # belong to cues; English words belong to the instruction.
                    hebrew=' '.join(re.findall(r'[\u0590-\u05ff]+',words))
                    english=re.sub(r'[\u0590-\u05ff]+','',words).replace(' · ',' ')
                    expected[(page,'he')]=normalize(hebrew)
                    expected[(page,'en')]=normalize(english)
                else:expected[(page,lang)]=normalize(words)
            unit.set('{http://www.w3.org/XML/1998/namespace}lang',lang)
            actual=streams(unit,include_notes=True)
            if reading['kind']=='rubric' and lang=='he':
                # Preserve printed phrase dots in the Hebrew cue stream.
                actual={k:v.replace(' · ',' ') for k,v in actual.items()}
            if reading['id'] in TEXTS and TEXTS[reading['id']][0] in PRINTED_IN_FULL:
                # A text printed in full elsewhere (Vayaavor, pp. 11-12) and transcluded here: this
                # printing is that text, word for word, whatever its pages and punctuation.
                words_of=lambda streams:re.sub(r'[^\w\s]','',' '.join(v for (_,l),v in sorted(streams.items()) if l==lang)).split()
                if words_of(actual)!=words_of(expected):
                    raise ValueError(f'{reading["id"]}: not the words of the text printed in full')
                count+=1
                continue
            differences=check(actual,expected)
            if differences:raise ValueError(f'{reading["id"]}: {differences}')
            count+=1
        roots=[opening_documentary(project)]
        units=continuation_units(project,groups)
        # Interleave the separately printed prayers and poem at their scan positions.
        for reading,unit in units:
            if reading['id']==groups['before_piyyut'][0]['id']:
                for name in ['el_melekh_yoshev','vayaavor']:
                    roots.append(etree.parse(str(project/(spelled_name(name)+'.xml'))).getroot())
            if reading['id']==groups['closing'][0]['id']:
                roots.append(etree.parse(str(project/(spelled_name('bemotzaei_menuhah')+'.xml'))).getroot())
            if reading['id'] in TEXTS and TEXTS[reading['id']][0] in PRINTED_IN_FULL:
                continue  # its pages are where it is printed in full
            roots.append(unit)
        pages=[]
        for root in roots:
            pages.extend(int(re.search(r'/n(\d+)',n.get('facs')).group(1)) for n in root.findall(f'.//{{{TEI}}}pb'))
        required=set(range(5 if lang=='he' else 6, 52 if lang=='he' else 53, 2))
        if pages!=sorted(pages) or set(pages)!=required:
            raise ValueError('First-day facsimiles must follow source order through the final leaf')
        final=groups['closing'][-1]
        if final['id']!='reader_kaddish':raise ValueError('First day must end with Reader’s Kaddish instruction')
    print(f'{count} continuation units match documentary readings; footnotes and final n51/n52 boundary checked')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory',type=Path,default=PROJECT_DIRECTORY)
    args=parser.parse_args(argv)
    verify(args.source_root,args.project_directory)
    return 0


if __name__=='__main__':raise SystemExit(main())
