"""Kabbalat Shabbat, printed 237–256; occasion gates belong to callers."""
import re
from .common import PRAYER, POEM, SIDDUR, PROJECT_HE, AGG, cond, endcond, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml, MINYAN
from .milestones import Correspondences, milestone, marked
from .shacharit_end import editorial_head
from .arvit import AFTER_FESTIVAL
from .kabbalat_shabbat_data import (HE, EN, EN_JOIN, PAGES, READER, REFRAIN,
    DODI_HE, DODI_EN, CONDOLENCE, CONDOLENCE_RUBRIC, STANZAS_RUBRIC, RISE_RUBRIC)

ROOT = SIDDUR+'shabbat/kabbalat_shabbat'
SIGIL = '1949 shabbat/kabbalat_shabbat'
DODI = POEM+'lecha_dodi'
ANA = POEM+'anna_bekhoach'
WELCOME = PRAYER+'nichum_avelim/hamakom_yenachem'
FESTIVAL = feature(AGG, 'yom-tov')
# The caller names the incoming Shabbat. AFTER_FESTIVAL uses that night's Hebrew
# date, so under the Shabbat scope it means a festival on the preceding Friday.
FULL = '<j:none>'+AFTER_FESTIVAL+'</j:none>'
PRESENT_MOURNERS = feature('opensiddur:service-context', 'mourners-present')
RUBRIC = ('The following Kabbalath Shabbath service is omitted on festivals which '
          'coincide with the Sabbath. The Ma‘ariv service for festivals begins on page {page}.')
FRIDAY_RUBRIC = 'When Friday is not a festival:'
OLD_REFERENCES = {
 'romemu': ('psalms/99/5','psalms/99/9'),
 'torah_vetiggaleh': ('psalms/29/11',),
 'conclusion_psalm_95_opening': ('psalms/95/1','psalms/95/2','psalms/95/3'),
}


def conditional(cid, rubric, fs, body, *, negate=False):
    return cond('kabbalat_'+cid,note=rubric,fs=fs,negate=negate)+body+endcond('kabbalat_'+cid)


def shared(lang, prayers):
    result=[dict(p) for p in prayers]
    for p in result:
        # Full chapters now own biblical verse URNs. The earlier collected verses
        # retain their exact edition wording and local addresses, with source spans.
        for source in OLD_REFERENCES.get(p['name'], ()):
            biblical=BIBLE+source
            local=p['urn']+'/'+source.replace('/','_')
            pattern=(r'(<tei:milestone\b[^>]*corresp="'+re.escape(biblical)
                     +r'"[^>]*/>)(.*?)(?=<tei:milestone\b)')
            def move(m):
                return m[1].replace(biblical,local)+f'<tei:seg source="{biblical}">'+m[2]+'</tei:seg>'
            p['body'], count=re.subn(pattern,move,p['body'],flags=re.S)
            if count!=1: raise ValueError(f'Expected one earlier occurrence of {biblical}')
        if p['name']=='poem_anna_bekhoach':
            count=0
            def line(m):
                nonlocal count
                count+=1
                return '<tei:l>'+marked(ANA+'/'+str(count),m[1],unit='stanza')+'</tei:l>'
            p['body']=re.sub(r'<tei:l>(.*?)</tei:l>',line,p['body'],flags=re.S)
            if count!=7: raise ValueError('Expected seven Ana Bekoach lines')
        page={'poem_anna_bekhoach':243, 'conclusion_psalm_93':249,
              'kaddish_derabbanan_yitgadal':249, 'kaddish_derabbanan_yehe_shmeh':249,
              'kaddish_derabbanan_yitbarakh':249, 'kaddish_yatom':249}.get(p['name'])
        if page:
            page+=int(lang=='en')
            p['printings']=(*p.get('printings',()),(page,page))
    return result


def psalm_body(number, lang, verses=None):
    verses=(HE if lang=='he' else EN)[number] if verses is None else verses
    urn=BIBLE+f'psalms/{number}'
    title=('תהלים '+{95:'צה',96:'צו',97:'צז',98:'צח',99:'צט',29:'כט',92:'צב'}[number]
           if lang=='he' else f'Psalm {number}')
    parts=[f'<tei:div corresp="{urn}"><tei:head xml:lang="{lang}">{title}</tei:head>',
           pb(PAGES[number][0]+int(lang=='en'),sigil=SIGIL),'<tei:p>']
    marks=Correspondences()
    for n,text in enumerate(verses.splitlines(),1):
        if lang=='en' and n>1 and n not in EN_JOIN.get(number,set()):
            parts.append('</tei:p><tei:p>')
        if lang=='he' and n==READER[number]:
            parts.append(marks.close()+instruction('Reader'))
        parts.append(marks.start(urn+'/'+str(n)))
        parts.append(text_xml(text,SIGIL).replace('{p}','</tei:p><tei:p>'))
    parts.append(marks.close()+'</tei:p></tei:div>')
    # Newlines separate verse words without trailing whitespace in generated XML.
    return '\n'.join(parts)


def refrain(occurrence, lang):
    # Repeated performances have local addresses and reference the one refrain.
    source=DODI+'/refrain'
    target=source if occurrence=='opening' else DODI+'/refrain/'+occurrence
    text=text_xml(REFRAIN[int(lang=='en')],SIGIL)
    if target!=source: text=f'<tei:seg source="{source}">{text}</tei:seg>'
    return '<tei:p>'+marked(target,text,unit='stanza')+'</tei:p>'


def dodi_body(lang):
    side=int(lang=='en')
    parts=[f'<tei:div corresp="{DODI}">',editorial_head(lang,'לכה דודי','Lecha Dodi'),
           pb(243+side,sigil=SIGIL),instruction('Reader and Congregation:'),refrain('opening',lang)]
    if lang=='he': parts.append(refrain('opening_repeat',lang))
    parts += [pb(245+side,sigil=SIGIL),instruction(STANZAS_RUBRIC)]
    for n,text in enumerate((DODI_HE if lang=='he' else DODI_EN).splitlines(),1):
        if n==8: parts.append(pb(247+side,sigil=SIGIL))
        if n==9: parts.append(instruction(RISE_RUBRIC))
        if lang=='he':
            lines=text.split('|')
            body='<tei:lg>'+milestone(DODI+'/'+str(n),unit='stanza')
            body+=''.join('<tei:l>'+text_xml(line,SIGIL)+'</tei:l>' for line in lines)
            body+=milestone(unit='stanza')+'</tei:lg>'
        else: body='<tei:p>'+marked(DODI+'/'+str(n),text_xml(text,SIGIL),unit='stanza')+'</tei:p>'
        parts += [body,refrain(str(n),lang)]
    return '\n'.join(parts+['</tei:div>'])


def prayers(lang):
    side=int(lang=='en')
    result=[dict(name=f'kabbalat_psalm_{n}',urn=BIBLE+f'psalms/{n}',title=f'Psalm {n}',
                 first=PAGES[n][0]+side,last=PAGES[n][1]+side,body=psalm_body(n,lang)) for n in HE]
    result.append(dict(name='lecha_dodi',urn=DODI,title='לכה דודי' if not side else 'Lecha Dodi',
                       first=243+side,last=247+side,body=dodi_body(lang)))
    result.append(dict(name='nichum_avelim',urn=WELCOME,title='המקום ינחם' if not side else 'Consoling the mourners',
        first=247+side,last=247+side,body='<tei:p>'+marked(WELCOME,text_xml(CONDOLENCE[side],SIGIL))+'</tei:p>'))
    return result


def units(project):
    lang='he' if project==PROJECT_HE else 'en'
    side=int(lang=='en')
    result=[]
    def add(name,urn,he,en,first,last,body,head=True):
        result.append(dict(name=name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),
            body=f'<tei:div corresp="{urn}">'+(editorial_head(lang,he,en) if head else '')+body+'</tei:div>'))
    ana=(pb(243+side,sigil=SIGIL)+transclude(ANA)
         +transclude(PRAYER+'shema/barukh_shem'))
    add('kabbalat_anna_bekhoach',ROOT+'/anna_bekhoach','אנא בכח','Ana Bekoach',243,243,ana)
    # Psalm 93 is already encoded in the psalm-of-the-day sequence.
    add('kabbalat_psalm_93',ROOT+'/psalm_93','תהלים צג','Psalm 93',249,249,
        pb(249+side,sigil=SIGIL)+transclude(BIBLE+'psalms/93'),head=False)
    kad=''.join(transclude(PRAYER+'kaddish/'+s) for s in
                ('yitgadal','yehe_shmeh','yitbarakh','yatom/yehe_shlama','yatom/oseh_shalom'))
    add('kabbalat_kaddish',ROOT+'/kaddish','קדיש יתום','MOURNERS’ KADDISH',249,249,
        pb(249+side,sigil=SIGIL)+conditional('minyan','When a minyan holds service:',MINYAN,kad))
    before=''.join(transclude(BIBLE+f'psalms/{n}') for n in (95,96,97,98,99,29))
    before+=transclude(ROOT+'/anna_bekhoach')+transclude(DODI)
    before+=conditional('mourners',CONDOLENCE_RUBRIC,PRESENT_MOURNERS,transclude(WELCOME))
    content=conditional('friday_festival',FRIDAY_RUBRIC,FULL,before)
    content+=instruction('If a festival occurs on Friday, the evening service begins here.')
    content+=transclude(BIBLE+'psalms/92')+transclude(ROOT+'/psalm_93')+transclude(ROOT+'/kaddish')
    content+=transclude(ROOT+'/study')
    add('kabbalat_shabbat',ROOT,'קַבָּלַת שַׁבָּת','WELCOMING THE SABBATH',237,255,content)
    # Whole-service omission is outside the reusable Kabbalat Shabbat file.
    body='<j:declare xml:id="shabbat_opening_day">'+feature(AGG,'shabbat')+'</j:declare>'
    body+=conditional('festival',RUBRIC.format(page=257+side),FESTIVAL,transclude(ROOT),negate=True)
    body+='<j:endDeclare target="#shabbat_opening_day"/>'
    add('shabbat_kabbalat_service',SIDDUR+'shabbat/kabbalat_service','קבלת שבת','Welcoming the Sabbath',237,255,body,head=False)
    return tuple(result)
