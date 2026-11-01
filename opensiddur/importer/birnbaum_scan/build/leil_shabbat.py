"""Friday-night home prayers and table hymns, printed 283–298."""
import re
from .common import cond, endcond, feature, AGG, PRAYER, POEM, SIDDUR, PROJECT_HE, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .milestones import marked
from .shacharit_end import editorial_head
from .shabbat_arvit import URNS as ARVIT
from . import leil_shabbat_data as data

ROOT = SIDDUR+'shabbat/leil_shabbat'
SIGIL = '1949 shabbat/leil_shabbat'
URNS = {key: POEM+key for key in ('shalom_aleikhem','kol_meqaddesh','menuchah_vesimchah','yah_ribbon','tzur_mishello')}
# This is a different prayer from the morning Ribbon kol ha‘olamim.
URNS['ribbon'] = PRAYER+'ribbon_kol_haolamim_adon_kol_haneshamot'
URNS['eshet'] = ROOT+'/eshet_chayil'
URNS['guard'] = ROOT+'/guarding_verses'


def xml(value):
    return text_xml(value, SIGIL).replace('|','<tei:lb/>')


def paragraph(urn,value,*,unit='prayer-part'):
    return '<tei:p>'+marked(urn,xml(value),unit=unit)+'</tei:p>'


def shared(lang,prayers):
    result=[dict(p) for p in prayers]; side=int(lang=='en')
    for p in result:
        if p['urn'] in (ARVIT['vaykhulu'],ARVIT['wine'],ARVIT['kiddush']):
            p['printings']=(*p.get('printings',()),(289+side,289+side))
    return result


def prayers(lang,earlier):
    side=int(lang=='en'); result=[]
    seen=set(re.findall(r'corresp="([^"]+)"',''.join(p['body'] for p in earlier)))
    def add(key,he,en,first,last,body,*,heading=True):
        urn=URNS[key]
        head=editorial_head(lang,he,en) if heading else ''
        language=' xml:lang="arc-Hebr"' if key=='yah_ribbon' and not side else ''
        result.append(dict(name='leil_shabbat_'+key+'_text',urn=urn,title=(he,en)[side],first=first+side,last=last+side,
                           body=f'<tei:div corresp="{urn}"{language}>'+head+body+'</tei:div>'))
    def stanzas(key,rows,*,refrain=None):
        body=''
        for i,row in enumerate(rows,1):
            value=xml(row[side])
            if key=='kol_meqaddesh':
                # Each final line is a biblical quotation, not a new Bible text.
                refs=('numbers/1/52','kings_1/8/56','psalms/118/24','genesis/2/2','exodus/12/47','psalms/36/9','samuel_1/14/41')
                he_starts=('אִישׁ עַל','בָּרוּךְ יְיָ','זֶה הַיּוֹם','וַיְכַל אֱלֹהִים','כָּל עֲדַת','יִרְוְיֻן','יְיָ אֱלֹהֵי')
                start=value.rfind('<tei:lb/>')+len('<tei:lb/>') if side else value.index(he_starts[i-1])
                value=value[:start]+f'<tei:seg source="{BIBLE}{refs[i-1]}">'+value[start:]+'</tei:seg>'
            body+='<tei:p>'+marked(URNS[key]+'/'+str(i),value,unit='stanza')+'</tei:p>'
            if refrain:
                body+=paragraph(URNS[key]+'/refrain/'+str(i),refrain[side],unit='stanza')
        return body
    add('shalom_aleikhem','שלום עליכם','Shalom Aleichem',283,283,stanzas('shalom_aleikhem',data.SHALOM))
    guard='<tei:p>'
    for ref,he,en in data.GUARD:
        source=BIBLE+ref; value=xml((he,en)[side])
        urn=source if source not in seen else URNS['guard']+'/'+ref.replace('/','_')
        if urn!=source:value=f'<tei:seg source="{source}">{value}</tei:seg>'
        guard+=marked(urn,value,unit='verse')+' '
    add('guard','כי מלאכיו יצוה לך','Verses of protection',283,283,guard+'</tei:p>',heading=False)
    add('ribbon','רבון כל העולמים','Meditation',283,287,
        ''.join(paragraph(URNS['ribbon']+'/'+str(i),row[side]) for i,row in enumerate(data.RIBBON,1)))
    eshet=(instruction('Proverbs 31:10–31') if side else
           '<tei:note type="instruction" xml:lang="he">משלי לא, י–לא</tei:note>')
    eshet+=''.join(paragraph(BIBLE+'proverbs/31/'+str(i),row[side],unit='verse') for i,row in enumerate(data.ESHET,10))
    add('eshet','אשת חיל','Eshet Ḥayil',287,289,eshet)
    add('kol_meqaddesh','כל מקדש','Kol Mekadesh',291,293,stanzas('kol_meqaddesh',data.KOL))
    add('menuchah_vesimchah','מנוחה ושמחה','Menuḥah Vesimḥah',293,293,stanzas('menuchah_vesimchah',data.MENUCHA))
    add('yah_ribbon','יה רבון','Yah Ribbon',295,295,stanzas('yah_ribbon',data.YAH,refrain=data.YAH_REFRAIN))
    add('tzur_mishello','צור משלו','Tzur Mishelo',297,297,
        paragraph(URNS['tzur_mishello']+'/refrain',data.TZUR_REFRAIN[side],unit='stanza')
        +stanzas('tzur_mishello',data.TZUR,refrain=data.TZUR_SHORT))
    return result


def units(project):
    lang='he' if project==PROJECT_HE else 'en'; side=int(lang=='en'); result=[]
    def add(key,he,en,first,last,content):
        urn=ROOT+('/'+key if key else '')
        result.append(dict(name='leil_shabbat'+('_'+key if key else ''),urn=urn,title_he=he,title_en=en,
                           pages=(first+side,last+side),body=f'<tei:div corresp="{urn}"><tei:head xml:lang="{lang}">{(he,en)[side]}</tei:head>'+pb(first+side,sigil=SIGIL)+content+'</tei:div>'))
    kiddush=instruction('Recited before the Sabbath meal.')
    # Genesis 1:31 is only a fragment here. Do not expose it as a complete verse.
    kiddush+='<tei:p>'+marked(ROOT+'/kiddush/opening',f'<tei:seg source="{BIBLE}genesis/1/31">'+xml(data.KIDDUSH_OPEN[side])+'</tei:seg>')+'</tei:p>'
    # Reuse the verses without importing the synagogue occurrence’s source note.
    kiddush+=''.join(transclude(BIBLE+'genesis/2/'+str(i)) for i in (1,2,3))
    if not side:kiddush+='<tei:p>'+marked(ROOT+'/kiddush/savri','סַבְרִי מָרָנָן וְרַבּוֹתַי.')+'</tei:p>'
    kiddush+=transclude(ARVIT['wine'])+transclude(ARVIT['kiddush'])
    add('kiddush','קִדּוּשׁ','KIDDUSH',289,289,kiddush)
    add('zemirot','זְמִירוֹת לְלֵיל שַׁבָּת','SABBATH EVE HYMNS',291,297,
        instruction('Chanted at the table')+''.join(transclude(URNS[k]) for k in ('kol_meqaddesh','menuchah_vesimchah','yah_ribbon','tzur_mishello')))
    add('','לליל שבת','FOR SABBATH EVE',283,297,
        instruction('Upon returning from synagogue:')
        +''.join(transclude(URNS[k]) for k in ('shalom_aleikhem','guard','ribbon','eshet'))
        +cond('night_meal_shabbat_kiddush', fs='<j:none>'+feature(AGG, 'yom-tov')+'</j:none>')+transclude(ROOT+'/kiddush')+endcond('night_meal_shabbat_kiddush')+transclude(ROOT+'/zemirot'))
    return tuple(result)
