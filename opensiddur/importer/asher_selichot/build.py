"""Encode the image-adjudicated Asher edition, retaining printed and expanded forms.

Reads the committed scan reading, not OCR. Dependency ranges are authored from
this edition, never substituted from another project's prayer text.
"""

from opensiddur.importer.scan.authoring import element, marker, choice, italicize, conditional_scope, write_documents, apply_corrections, apply_editorial_notes

import argparse
import functools
import json
from pathlib import Path
from lxml import etree
from opensiddur.common.constants import SOURCETEXTS_ROOT, PROJECT_DIRECTORY
from opensiddur.common.urn_registry import SCHEME
import yaml
from opensiddur.common.validate_names import URN_PATH, Spellings, load_spellings, respell
from opensiddur.importer.util.validation import validate
from .identities import project_name

TEI='http://www.tei-c.org/ns/1.0'
J='http://jewishliturgy.org/ns/jlptei/2'
XML='{http://www.w3.org/XML/1998/namespace}'
POEM='urn:x-opensiddur:text:poem:bemotzaei_menuhah'
PRAYER='urn:x-opensiddur:text:prayer:'
IA='https://archive.org/details/selichothdavidasher1912'


def document(lang, project, title, urn, *, index=False):
    root=etree.Element(f'{{{TEI}}}TEI',nsmap={'tei':TEI,'j':J},attrib={XML+'lang':lang})
    header=element(root,'teiHeader');file=element(header,'fileDesc');titles=element(file,'titleStmt')
    element(titles,'title',title,type='main')
    resp=element(titles,'respStmt');element(resp,'resp','AI-assisted scan reading and encoding by',key='trc')
    element(resp,'name','Codex',ref='urn:x-opensiddur:contributor:opensiddur.org/codex')
    editions=element(file,'editionStmt');element(editions,'edition','Read from the scanned 1912–5672 printing; editorial expansions recorded in the source README.')
    pub=element(file,'publicationStmt');distributor=element(pub,'distributor')
    element(distributor,'ref','Open Siddur Project',target='https://opensiddur.org')
    element(pub,'idno',urn+'@'+project,type='urn')
    availability=element(pub,'availability',status='free')
    element(availability,'licence','Creative Commons Attribution-ShareAlike 4.0 International',target='https://creativecommons.org/licenses/by-sa/4.0/')
    source=element(file,'sourceDesc')
    if index:
        bibl=element(source,'bibl');element(bibl,'title','Selichoth for the Propitiatory and Penitential Days, and for the Minor Fasts')
        element(bibl,'editor','David Asher',role='translator');element(bibl,'publisher','Vallentine & Sons')
        element(bibl,'pubPlace','London');element(bibl,'date','1912–5672',when='1912')
        element(bibl,'idno',IA,type='url');element(bibl,'note','The scan is the source. First publication was 1866; this encoding follows the 1912 reprint. Asher-specific expansions and reference ranges are documented in sources/asher_selichot/README.md.')
    else:
        p=element(source,'p');element(p,'ref','Asher Selichoth, 1912 source metadata',target='index.xml')
    return root,element(root,'text')


def pb(parent, scan, printed):
    return element(parent,'pb',n=printed,ed='1912',facs=f'https://archive.org/download/selichothdavidasher1912/page/n{int(scan[1:])-1}_medium.jpg')


def expansion_instruction(parent, identity, feature):
    """Keep the printed rubric unless this view supplies the requested text."""
    conditional_scope(parent, identity, False, fs_type='asher:expansions', feature=feature)
    note = element(parent, 'note', type='instruction')
    element(parent, 'j:endConditional', target='#'+identity)
    return note


def poem(lang,project,data):
    root,text=document(lang,project,'במוצאי מנוחה' if lang=='he' else 'On the outgoing of the Sabbath',POEM)
    div=element(element(text,'body'),'div',corresp=POEM)
    pb(div,'s32' if lang=='he' else 's33','15')
    if lang=='he':element(div,'head','פזמון')
    marker(div,POEM+'/rubric')
    rubric=expansion_instruction(div, 'refrain_instruction', 'refrains_present')
    rubric.set(XML+'lang','en')
    if lang=='he':
        rubric.text='Wherever the word '
        f=element(rubric,'foreign','לשמוע');f.set(XML+'lang','he');f.tail=' occurs at the end of the verse, repeat from '
        f=element(rubric,'foreign','לִשְׁמֹעַ');f.set(XML+'lang','he');f.tail=' till '
        f=element(rubric,'foreign','וְאֶל־הַתְּפִלָּה');f.set(XML+'lang','he');f.tail='.'
    else:
        rubric.text=data['rubric']
    he_refrain='לִשְׁמֹעַ אֶל־הָרִנָּה וְאֶל־הַתְּפִלָּה׃'
    en_refrain='to hearken unto our hymns of praise, and unto our supplication.'
    for n,stanza in enumerate(data['stanzas'],1):
        marker(div,POEM+f'/{n}')
        if lang=='he':
            lg=element(div,'lg')
            # Raised dots and two-dot stops delimit verse phrases. Physical wrapping
            # runs across these units and is retained separately in image evidence.
            stanza=' '.join(stanza)
            phrases=stanza.split(' · ')
            for i,phrase in enumerate(phrases):
                element(lg,'l',phrase+(' ·' if i<len(phrases)-1 else ''))
            if 2<=n<=7:
                line=element(lg,'l');choice(line,'לשמוע',he_refrain)
            if n==8:
                element(lg,'l',he_refrain)
                line=element(lg,'l');choice(line,data['final_hebrew_rubric'],' '.join(data['stanzas'][0]))
        else:
            p=element(div,'p',stanza)
            if n==2:
                before,after=stanza.split('mighty deed;',1)
                p.text=before+'mighty deed;'
                note=element(p,'note',data['footnote'],type='commentary');note.tail=after
            cue=data['cues'].get(str(n))
            if cue:
                p.text=(p.text or '')+' '
                choice(p,cue,en_refrain)
            if n==8:
                p.text+=' ';choice(p,data['final_cue'],data['stanzas'][0])
    marker(div,POEM+'/conclusion')
    note=expansion_instruction(div, 'prayer_instruction', 'prayers_present');note.set(XML+'lang','en')
    if lang=='he':
        note.text='Say '
        f=element(note,'foreign','אֵל מֶלֶךְ');f.set(XML+'lang','he');f.tail=' and '
        f=element(note,'foreign','וַיַּעֲבֹר');f.set(XML+'lang','he')
    else:
        note.text=data['conclusion']
    supplied = element(div, 'j:conditional')
    supplied.set(XML+'id', 'prayer_instruction_expanded')
    fs = element(supplied, 'fs', type='asher:expansions')
    f = element(fs, 'f'); f.set('name', 'prayers_present')
    element(f, 'binary', value='true')
    for name in ['el_melekh_yoshev', 'vayaavor']:
        element(div, 'j:transclude', target=PRAYER+name)
    element(div, 'j:endConditional', target='#prayer_instruction_expanded')
    return root


def dependency(lang,project,name,pages):
    urn=PRAYER+name
    root,text=document(lang,project,name.replace('_',' '),urn)
    div=element(element(text,'body'),'div',corresp=urn)
    p=None
    for scan,words in pages.items():
        if p is None:
            pb(div,scan,'11');p=element(div,'p',words)
            if lang == 'en' and name == 'el_melekh_yoshev':
                italicize(p, ['by causing', 'charitably', 'of thy mercy', 'we beseech thee', 'attributes,'])
        else:
            brk=pb(p,scan,'12');brk.tail=' '+words
    return root


def build(source_root,project_directory):
    data=json.loads((Path(source_root)/'asher_selichot/scan_reading/refrain-and-prayers.json').read_text())
    documents=[]
    for lang in ['he','en']:
        project=project_name(lang);out=Path(project_directory)/project
        docs={'bemotzaei_menuhah.xml':poem(lang,project,data[lang]['poem'])}
        for name,pages in data[lang]['prayers'].items():
            docs[name+'.xml']=dependency(lang,project,name,pages)
        for name,root in docs.items():
            documents.append((out/name, root))
    from .first_day import documents as first_day_documents, OBSOLETE_ASSEMBLIES
    readings = Path(source_root)/'asher_selichot/scan_reading'
    authored = list(first_day_documents(readings))
    if (readings/'second-day.json').exists():
        from .second_day import documents as second_day_documents
        authored.extend(second_day_documents(readings))
    if (readings/'third-day.json').exists():
        from .third_day import documents as third_day_documents
        authored.extend(third_day_documents(readings))
    from .second_day import numbered_documents
    for day_name in ['fourth', 'fifth', 'sixth', 'seventh']:
        if (readings/(day_name+'-day.json')).exists():
            authored.extend(numbered_documents(readings, day_name))
    if (readings/'erev-rosh-hashanah.json').exists():
        from .erev_rosh_hashanah import documents as erev_documents
        authored.extend(erev_documents(readings))
    if (readings/'tzom-gedaliah.json').exists():
        from .tzom_gedaliah import documents as gedaliah_documents
        authored.extend(gedaliah_documents(readings))
    if (readings/'penitential-second-day.json').exists():
        from .penitential_second_day import documents as penitential_documents
        authored.extend(penitential_documents(readings))
    from .penitential_days import SERVICES, manifest_name, documents as later_penitential_documents
    for day in SERVICES:
        if (readings/(manifest_name(day)+'.json')).exists():
            authored.extend(later_penitential_documents(readings,day))
    documents.extend((Path(project_directory)/project/name, root)
                     for project, name, root in authored)
    by_path = {f'{path.parent.name}/{path.name}': root for path, root in documents}
    corrections = readings/'corrections.json'
    if corrections.exists():
        apply_corrections(by_path, json.loads(corrections.read_text())['corrections'])
    editorial = readings/'editorial_notes.json'
    if editorial.exists():
        apply_editorial_notes(by_path, json.loads(editorial.read_text())['notes'])
    documents, renamed = respelled(documents)
    obsolete = [Path(project_directory)/project_name(lang)/(name+'.xml')
                for lang in ['he', 'en'] for name in OBSOLETE_ASSEMBLIES] + renamed
    return write_documents(documents, validator=validate, obsolete_paths=obsolete)


#: Respellings for this book alone, on top of specs/naming/spellings.yaml.
BOOK_SPELLINGS = Path(__file__).with_name('spellings.yaml')


@functools.cache
def _book():
    """This book's spellings (the shared list with its own added) and its whole-name renames."""
    shared, own = load_spellings(), load_spellings(BOOK_SPELLINGS)
    renames = yaml.safe_load(BOOK_SPELLINGS.read_text(encoding='utf-8')).get('renames') or {}
    standards = set(shared.variants.values()) | shared.exceptions
    for variant, standard in own.variants.items():
        if variant in shared.variants or variant in standards or standard in shared.variants:
            raise ValueError(f'{BOOK_SPELLINGS}: {variant!r}: {standard!r} repeats or contradicts '
                             'the shared spelling list')
    return Spellings(shared.exceptions, {**shared.variants, **own.variants}), renames


def book_spellings():
    """The shared spelling list with this book's own respellings added to it."""
    return _book()[0]


def spelled_name(name):
    """The name a file the readings know as ``name`` has in the book (see :func:`respelled`):
    respelled word by word, then renamed whole, part by part of a URN path."""
    spellings, renames = _book()
    return '/'.join(renames.get(part, part) for part in respell(name, spellings).split('/'))


def spelled_urn(text):
    """``text`` with the path of every URN in it named as the book names it (see
    :func:`respelled`)."""
    return URN_PATH.sub(lambda m: SCHEME + m.group(1) + spelled_name(m.group(2)), text)


def respelled(documents):
    """The documents with their file names and URNs spelled by specs/naming/spellings.yaml and
    this book's own list, ``spellings.yaml`` beside this module, and the paths they were renamed
    from.

    The readings' IDs and file names are evidence, and keep the spelling they were made under;
    the book's names are respelled here, once everything else has located its files by them.
    """
    out, renamed = [], []
    for path, root in documents:
        new = path.with_name(spelled_name(path.stem) + path.suffix)
        if new != path:
            renamed.append(path)
        for node in root.iter():
            if not isinstance(node.tag, str):
                continue
            for key, value in node.attrib.items():
                if SCHEME in value:
                    node.set(key, spelled_urn(value))
            if node.text and SCHEME in node.text:
                node.text = spelled_urn(node.text)
        out.append((new, root))
    return out, renamed


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory',type=Path,default=PROJECT_DIRECTORY)
    args=parser.parse_args(argv)
    for path in build(args.source_root,args.project_directory):print(path)
    return 0


if __name__=='__main__':raise SystemExit(main())
