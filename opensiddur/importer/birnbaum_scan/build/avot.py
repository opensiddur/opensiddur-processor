"""Pirkei Avot, independently addressable and selectable chapter by chapter."""
from html import escape
from .common import SIDDUR, PROJECT_HE, pb, cond, endcond, feature
from .conclusion import transclude
from .milestones import Correspondences
from .avot_data import READINGS

ROOT = SIDDUR+'pirqei_avot'
MISHNAH = 'urn:x-opensiddur:text:mishnah:avot'
OPENING = 'urn:x-opensiddur:text:mishnah:sanhedrin/10/1/kol_yisrael'
CLOSING = 'urn:x-opensiddur:text:mishnah:makkot/3/16'
SIGIL = '1949 pirkei_avot'
FS = 'opensiddur:pirkei-avot'
#: Who wrote the weekly-cycle rubrics, which are the edition's own, not Birnbaum's.
EDITORIAL = 'urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein'

#: When a chapter, or Avot at all, is read. Each is its j:conditional's own rubric, so a
#: condition known to hold -- a date that selects the chapter, or a volume that sets every
#: chapter to print the whole text -- prints the passage without it.
SEASON_RUBRIC = 'Recited on the Sabbaths between <tei:hi rend="italic">Pesaḥ</tei:hi> and <tei:hi rend="italic">Rosh Hashanah</tei:hi>'
CHAPTER_HE = ('רִאשׁוֹן','שֵׁנִי','שְׁלִישִׁי','רְבִיעִי','חֲמִישִׁי','שִׁשִּׁי')
CHAPTER_EN = ('One','Two','Three','Four','Five','Six')
# Each entry maps a printed paragraph to the standard Mishnah division. Birnbaum
# divides several mishnayot into multiple numbered paragraphs; preserve both.
NUMBERS = {
 1:list(range(1,19)),
 2:[1,2,3,4,4,5,6,7,8,8,8,8,9,9,10,11,12,13,14,15,16],
 3:[1,2,2,3,4,5,6,7,7,8,9,9,10,10,11,12,13,14,15,16,17,17,18],
 4:[1,2,3,4,4,5,5,6,7,8,9,10,11,11,12,13,13,14,15,15,16,17,18,19,20,20,20,21,22],
 5:[1,2,2,3,4,4,5,6,7,8,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23],
 6:list(range(1,12)),
}


def reference(key):
    if key=='6.intro': return MISHNAH+'/6/1'
    if key=='5.23prayer': return MISHNAH+'/5/20'
    chapter,number=map(int,key.rstrip('+').split('.'))
    return f'{MISHNAH}/{chapter}/{NUMBERS[chapter][number-1]}'


def text_xml(text):
    return (escape(text).replace('&lt;i&gt;','<tei:hi rend="italic">')
            .replace('&lt;/i&gt;','</tei:hi>').replace('&lt;he&gt;','<tei:foreign xml:lang="he">')
            .replace('&lt;/he&gt;','</tei:foreign>'))


def records(lang):
    """Page-keyed direct readings, preserving paragraph continuations."""
    result=[]
    chapter=1
    previous={}
    for page,pair in READINGS.items():
        page=int(page)+int(lang=='en')
        for line in pair[lang].splitlines():
            if '|' not in line:
                if line: result[-1]['text']+='\n\n'+line
                continue
            key,text=line.split('|',1)
            if key in ('opening','closing'):
                if text=='=':text=previous[key]
                else:previous[key]=text
                result.append(dict(key=key,chapter=chapter,page=page,text=text))
                if key=='closing':chapter+=1
            else:
                result.append(dict(key=key,chapter=int(key[0]),page=page,text=text))
    return result


def hebrew_number(n):
    if n<10:return 'אבגדהוזחט'[n-1]
    if n in (15,16):return {15:'טו',16:'טז'}[n]
    tens,ones=divmod(n,10)
    return 'יכ'[tens-1]+('אבגדהוזחט'[ones-1] if ones else '')


def chapter_body(chapter, lang, rows):
    urn=f'{MISHNAH}/{chapter}'
    parts=[f'<tei:div corresp="{urn}">']
    marks=Correspondences();last=None;page=None
    for idx, row in enumerate(rows):
        key=row['key'];ref=reference(key);text=row['text']
        continued=key.endswith('+')
        if not continued:parts.append('<tei:p>')
        if row['page']!=page:
            page=row['page'];parts.append(pb(page,sigil=SIGIL))
        if ref!=last:
            parts.append(marks.start(ref,unit='mishnah'));last=ref
        label=''
        if key not in ('6.intro','5.23prayer') and not continued:
            number=int(key.split('.')[1]);label=(str(number) if lang=='en' else hebrew_number(number))+'. '
        # The printed paragraph 5.11 straddles the standard 5:8/5:9 boundary.
        boundary='חַיָּה רָעָה' if lang=='he' else 'Wild beasts'
        chunks=text.split(boundary,1) if key=='5.11' else [text]
        parts.append(label+text_xml(chunks[0]).replace('\n\n','</tei:p><tei:p>'))
        if len(chunks)==2:
            last=MISHNAH+'/5/9'
            parts.append(marks.start(last,unit='mishnah')+text_xml(boundary+chunks[1]))
        # Keep a page turn inside its original paragraph, in each language.
        if idx+1<len(rows) and rows[idx+1]['key']==key.rstrip('+')+'+':parts.append(' ')
        else:parts.append('</tei:p>')
    parts.append(marks.close()+'</tei:div>')
    return '\n'.join(parts)


def prayers(lang):
    rows=records(lang);result=[]
    for chapter in range(1,7):
        body_rows=[r for r in rows if r['chapter']==chapter and r['key'] not in ('opening','closing')]
        title=f'Pirkei Avot, Chapter {chapter}' if lang=='en' else f'פרקי אבות, פרק {hebrew_number(chapter)}'
        result.append(dict(name=f'avot_text_{chapter}',urn=f'{MISHNAH}/{chapter}',title=title,
                           first=body_rows[0]['page'],last=body_rows[-1]['page'],
                           body=chapter_body(chapter,lang,body_rows)))
    for key,urn in [('opening',OPENING),('closing',CLOSING)]:
        copies=[r for r in rows if r['key']==key]
        result.append(dict(name='avot_'+key,urn=urn,title='Kol Yisrael' if key=='opening' else 'Rabbi Hananya ben Akashya',
            first=copies[0]['page'],last=copies[0]['page'],printings=tuple((r['page'],r['page']) for r in copies[1:]),
            body=f'<tei:div corresp="{urn}"><tei:p>'+text_xml(copies[0]['text'])+'</tei:p></tei:div>'))
    return result


def units(project):
    lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');rows=records(lang)
    result=[];body=f'<tei:div corresp="{ROOT}"><tei:head xml:lang="{lang}">'+('Ethics of the Fathers' if side else 'פִּרְקֵי אָבוֹת')+'</tei:head>'
    for c in range(1,7):
        urn=f'{ROOT}/{c}'
        cid=f'avot_chapter_{c}'
        rubric=f'Read Chapter {c} when it is assigned in the weekly Pirkei Avot cycle.'
        body+=cond(cid,note=rubric,note_resp=EDITORIAL,fs=feature(FS,f'chapter-{c}'))+transclude(urn)+endcond(cid)
        first=next(r for r in rows if r['chapter']==c and r['key']=='opening')
        last=next(r for r in rows if r['chapter']==c and r['key']=='closing')
        title=('Chapter '+CHAPTER_EN[c-1]) if side else 'פֶּרֶק '+CHAPTER_HE[c-1]
        chapter=f'<tei:div corresp="{urn}"><tei:head xml:lang="{lang}">{title}</tei:head>'
        for key,row,shared in [('opening',first,OPENING),('closing',last,CLOSING)]:
            if key=='closing':chapter+=transclude(f'{MISHNAH}/{c}')
            content='<tei:p><tei:seg source="'+shared+'">'+text_xml(row['text'])+'</tei:seg></tei:p>'
            chapter+=f'<tei:div corresp="{urn}/{key}">'+pb(row['page'],sigil=SIGIL)+content+'</tei:div>'
        chapter+='</tei:div>'
        result.append(dict(name=f'avot_chapter_{c}',urn=urn,title_he='פרקי אבות '+str(c),title_en='Pirkei Avot '+str(c),pages=(first['page'],last['page']),body=chapter))
    result.append(dict(name='pirqei_avot',urn=ROOT,title_he='פרקי אבות',title_en='Pirkei Avot',pages=(477+side,533+side),body=body+'</tei:div>'))
    return tuple(result)


def caller():
    """The seasonal rubric belongs to the siddur, never the reusable Avot file."""
    available='<j:any>'+''.join(feature(FS,f'chapter-{n}') for n in range(1,7))+'</j:any>'
    scope='<j:all>'+feature(FS,'season')+available+'</j:all>'
    return cond('avot_season',note=SEASON_RUBRIC,fs=scope)+transclude(ROOT)+endcond('avot_season')
