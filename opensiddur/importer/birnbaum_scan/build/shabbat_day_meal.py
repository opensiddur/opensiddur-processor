"""Sabbath morning Kiddush and table hymns, printed 423–436."""
from .common import cond, endcond, feature, AGG, SIDDUR, POEM, PROJECT_HE, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .milestones import marked
from .shacharit_end import editorial_head
from .shabbat_arvit import URNS as ARVIT
from .leil_shabbat import URNS as LEIL
from . import leil_shabbat_data as old
from . import shabbat_day_meal_data as data

ROOT = SIDDUR+'shabbat/day_meal'
SIGIL = '1949 shabbat/day_meal'
URNS = {key: POEM+key for key in ('barukh_adonai_yom_yom', 'barukh_el_elyon', 'yom_zeh_mekhubbad')}


def xml(value):
    return text_xml(value, SIGIL).replace('|', '<tei:lb/>')


def paragraph(urn, value, unit='stanza'):
    return '<tei:p>'+marked(urn, xml(value), unit=unit)+'</tei:p>'


def shared(lang, prayers):
    side=int(lang=='en'); result=[dict(p) for p in prayers]
    for p in result:
        pages={ARVIT['wine']:(423,423), ARVIT['veshamru']:(423,423),
               LEIL['yah_ribbon']:(433,435), LEIL['tzur_mishello']:(435,435)}
        if p['urn'] in pages:
            a,b=pages[p['urn']]
            p['printings']=(*p.get('printings',()),(a+side,b+side))
    return result


def prayers(lang, earlier):
    side=int(lang=='en'); result=[]
    def add(key,he,en,first,last,body):
        urn=URNS[key]
        result.append(dict(name='shabbat_day_'+key+'_text',urn=urn,title=(he,en)[side],
            first=first+side,last=last+side,body=f'<tei:div corresp="{urn}">'+
            editorial_head(lang,he,en)+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    def stanzas(key,rows,refrain=None,first_refrain=None):
        body=''
        for i,row in enumerate(rows,1):
            body+=paragraph(URNS[key]+'/'+str(i),row[side])
            if refrain:
                value=(first_refrain if i==1 and first_refrain else refrain)[side]
                body+=paragraph(URNS[key]+'/refrain/'+str(i),value)
        return body
    add('barukh_adonai_yom_yom','ברוך אדני יום יום','Barukh Adonai Yom Yom',425,427,
        stanzas('barukh_adonai_yom_yom',data.BARUKH_YOM))
    add('barukh_el_elyon','ברוך אל עליון','Barukh El Elyon',429,431,
        stanzas('barukh_el_elyon',data.BARUKH_EL,data.BARUKH_EL_SHORT,data.BARUKH_EL_REFRAIN))
    add('yom_zeh_mekhubbad','יום זה מכבד','Yom Zeh Mekhubad',431,433,
        paragraph(URNS['yom_zeh_mekhubbad']+'/refrain',data.YOM_ZEH_REFRAIN[side])+
        stanzas('yom_zeh_mekhubbad',data.YOM_ZEH,data.YOM_ZEH_SHORT))
    return result


def units(project):
    lang='he' if project==PROJECT_HE else 'en'; side=int(lang=='en'); result=[]
    def add(key,he,en,first,last,content,*,editorial=False,aramaic=False):
        urn=ROOT+('/'+key if key else '')
        head=editorial_head(lang,he,en) if editorial else f'<tei:head xml:lang="{lang}">{(he,en)[side]}</tei:head>'
        language=' xml:lang="arc-Hebr"' if aramaic and not side else ''
        result.append(dict(name='shabbat_day_meal'+('_'+key if key else ''),urn=urn,title_he=he,title_en=en,
            pages=(first+side,last+side),body=f'<tei:div corresp="{urn}"{language}>'+head+
            pb(first+side,sigil=SIGIL)+content+'</tei:div>'))
    citation=lambda he,en: f'<tei:note type="instruction" xml:lang="{lang}">{(he,en)[side]}</tei:note>'
    kiddush=citation('שמות לא, טז–יז','Exodus 31:16–17')
    kiddush+=f'<j:transclude type="external" target="{BIBLE}exodus/31/16" targetEnd="{BIBLE}exodus/31/17"/>'
    kiddush+=citation('שמות כ, ח–יא','Exodus 20:8–11')+'<tei:p>'
    # The earlier Decalogue has a commandment label, different divine-name
    # spelling and pointing. Retain this occurrence with biblical source spans.
    for ref,he,en in data.KIDDUSH:
        kiddush+=marked(ROOT+'/kiddush/'+ref.replace('/','_'),
            f'<tei:seg source="{BIBLE}{ref}">'+xml((he,en)[side])+'</tei:seg>',unit='verse')+' '
    kiddush+='</tei:p>'+transclude(ARVIT['wine'])
    add('kiddush','קִדּוּשׁ לְיוֹם הַשַּׁבָּת','KIDDUSH FOR SABBATH MORNING',423,423,kiddush)
    # Reuse matching stanza/refrain ranges; local variants carry the source URN
    # so neither translation nor the second printing silently alters the first.
    yah=''
    for i,row in enumerate(old.YAH,1):
        if i==5:yah+=pb(435+side,sigil=SIGIL)
        if i in data.YAH_VARIANTS_EN:
            value=(row[0],data.YAH_VARIANTS_EN[i])[side]
            yah+='<tei:p>'+marked(ROOT+'/yah_ribbon/'+str(i),
                f'<tei:seg source="{LEIL["yah_ribbon"]}/{i}">'+xml(value)+'</tei:seg>',unit='stanza')+'</tei:p>'
        else:yah+=transclude(LEIL['yah_ribbon']+'/'+str(i))
        yah+=transclude(LEIL['yah_ribbon']+'/refrain/'+str(i))
    add('yah_ribbon','יה רבון','Yah Ribbon',433,435,yah,editorial=True,aramaic=True)
    tzur=transclude(LEIL['tzur_mishello']+'/refrain')
    for i,row in enumerate(old.TZUR,1):
        if i==3:
            value=(data.TZUR_VARIANT_HE,row[1])[side]
            tzur+='<tei:p>'+marked(ROOT+'/tzur_mishello/3',
                f'<tei:seg source="{LEIL["tzur_mishello"]}/3">'+xml(value)+'</tei:seg>',unit='stanza')+'</tei:p>'
        else:tzur+=transclude(LEIL['tzur_mishello']+'/'+str(i))
        tzur+=transclude(LEIL['tzur_mishello']+'/refrain/'+str(i))
    add('tzur_mishello','צור משלו','Tzur Mishelo',435,435,tzur,editorial=True)
    add('zemirot','זְמִירוֹת לְשַׁבָּת','SABBATH HYMNS',425,435,
        instruction('Chanted at the table')+''.join(transclude(u) for u in URNS.values())+
        transclude(ROOT+'/yah_ribbon')+transclude(ROOT+'/tzur_mishello'))
    add('','סעודת יום השבת','Sabbath daytime meal',423,435,
        cond('day_meal_shabbat_kiddush', fs='<j:none>'+feature(AGG, 'yom-tov')+'</j:none>')+transclude(ROOT+'/kiddush')+endcond('day_meal_shabbat_kiddush')+transclude(ROOT+'/zemirot'),editorial=True)
    return tuple(result)
