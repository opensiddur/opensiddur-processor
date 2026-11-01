"""The study and Kaddish closing Kabbalat Shabbat, printed 251–256."""
import re
from .common import PRAYER, SIDDUR, PROJECT_HE, pb
from .conclusion import BIBLE, instruction, transclude, text_xml, MINYAN
from .milestones import marked
from .shacharit_end import editorial_head
from .bameh_madlikin_data import HE, EN, ELAZAR_HE, ELAZAR_EN, VERSES

MISHNAH = 'urn:x-opensiddur:text:mishnah:shabbat/2'
TALMUD = 'urn:x-opensiddur:text:talmud:berakhot/64a/amar_rabbi_elazar'
ROOT = SIDDUR+'shabbat/qabbalat_shabbat'
SIGIL = '1949 shabbat/qabbalat_shabbat'
KADDISH_PARTS = ('yitgaddal','yehe_shemeh','yitbarakh','al_yisrael','yehe_shelama','oseh_shalom')
RUBRIC = 'The following chapter is omitted on festivals.'


def citation(text, lang):
    return f'<tei:note type="instruction" xml:lang="{lang}">{text}</tei:note>'


def chapter_body(lang, readings=None):
    side=int(lang=='en')
    readings=(HE if not side else EN).splitlines() if readings is None else readings
    heading='משנה שבת, פרק ב' if not side else 'Mishnah Shabbath, Chapter 2'
    parts=[f'<tei:div corresp="{MISHNAH}">', editorial_head(lang,'במה מדליקין','Bameh Madlikin'),
           pb(251+side,sigil=SIGIL),citation(heading, lang)]
    for n,text in enumerate(readings,1):
        label=str(n) if side else 'אבגדהוז'[n-1]
        parts.append('<tei:p>'+marked(MISHNAH+'/'+str(n),label+'. '+text_xml(text,SIGIL),unit='mishnah')+'</tei:p>')
    return '\n'.join(parts+['</tei:div>'])


def elazar_body(lang):
    side=int(lang=='en')
    intro,quote,interpretation=ELAZAR_EN if side else ELAZAR_HE
    head='מסכת ברכות סד, א' if not side else 'Talmud Berakhoth 64a'
    body=f'<tei:div corresp="{TALMUD}">'+pb(253+side,sigil=SIGIL)+citation(head, lang)
    body+='<tei:p>'+marked(TALMUD+'/opening',text_xml(intro,SIGIL))
    body+=marked(TALMUD+'/isaiah_54_13',f'<tei:seg source="{BIBLE}isaiah/54/13">'+text_xml(quote,SIGIL)+'</tei:seg>')
    body+=marked(TALMUD+'/al_tiqra',text_xml(interpretation,SIGIL))
    if side: body+='</tei:p><tei:p>'
    for source,he,en in VERSES:
        if not side and source=='psalms/122/8': body+=instruction('Reader')
        body+=marked(TALMUD+'/'+source.replace('/','_'),
                     f'<tei:seg source="{BIBLE+source}">'+text_xml(en if side else he,SIGIL)+'</tei:seg>')+' '
    return body.rstrip()+'</tei:p></tei:div>'


def prayers(lang):
    side=int(lang=='en')
    return [dict(name='bameh_madlikin',urn=MISHNAH,title='Mishnah Shabbath, Chapter 2' if side else 'במה מדליקין',
                 first=251+side,last=253+side,body=chapter_body(lang)),
            dict(name='amar_rabbi_elazar',urn=TALMUD,title='Rabbi Elazar said' if side else 'אמר רבי אלעזר',
                 first=253+side,last=255+side,body=elazar_body(lang))]


def shared(lang, prayers):
    result=[dict(p) for p in prayers]
    for p in result:
        if p['name'] in {'kaddish_derabbanan_'+part for part in KADDISH_PARTS}:
            # The English peace petition here says "a happy life", unlike p. 48.
            if lang=='en' and p['name']=='kaddish_derabbanan_yehe_shelama': continue
            page=255+int(lang=='en')
            p['printings']=(*p.get('printings',()),(page,page))
    return result


def units(project):
    from .kabbalat_shabbat import conditional, FESTIVAL, FULL
    lang='he' if project==PROJECT_HE else 'en'
    side=int(lang=='en')
    occasion='<j:all><j:none>'+FESTIVAL+'</j:none>'+FULL+'</j:all>'
    body=conditional('bameh_festival',RUBRIC,occasion,transclude(MISHNAH))
    body+=transclude(TALMUD)
    kad=''
    for part in KADDISH_PARTS:
        if part=='yehe_shelama':
            # Draw the local realization from the shared reading. Keeping its
            # paragraph inline under one correspondence aligns both languages;
            # transcluding a whole addressed div here creates nested segments.
            from .he_ishmael import PRAYERS as HE_SHARED
            from .en_ishmael import PRAYERS as EN_SHARED
            original=next(p for p in (EN_SHARED if side else HE_SHARED)
                          if p['name']=='kaddish_derabbanan_yehe_shelama')
            text=re.search(r'<tei:p>(.*?)</tei:p>',original['body'],re.S).group(1)
            if side: text=text.replace('and life', 'and a happy life')
            kad+='<tei:p>'+marked(ROOT+'/study_kaddish/yehe_shelama',
                f'<tei:seg source="{PRAYER}kaddish/derabbanan/yehe_shelama">'+text+'</tei:seg>')+'</tei:p>'
        else: kad+=transclude(PRAYER+'kaddish/derabbanan/'+part)
    kad=(pb(255+side,sigil=SIGIL)+f'<tei:div corresp="{ROOT}/study_kaddish">'
         +f'<tei:head xml:lang="{lang}">'+('קַדִּישׁ דְּרַבָּנָן' if not side else 'KADDISH D’RABBANAN')+'</tei:head>'
         +conditional('study_minyan','When a minyan holds service:',MINYAN,instruction('Mourners:')+kad)+'</tei:div>')
    # Separate the closing Kaddish from the Mishnah chapter and study passage.
    body+=transclude(ROOT+'/study_kaddish')
    return (dict(name='qabbalat_study',urn=ROOT+'/study',title_he='לימוד לקבלת שבת',title_en='Study for Kabbalat Shabbat',
                 pages=(251+side,255+side),body=f'<tei:div corresp="{ROOT}/study">'+body+'</tei:div>'),
            dict(name='qabbalat_study_kaddish',urn=ROOT+'/study_kaddish',title_he='קדיש דרבנן',title_en='Kaddish d’Rabbanan',
                 pages=(255+side,255+side),body=kad))
