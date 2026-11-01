"""Sabbath/festival Shema and blessings, printed 335–350, before the Amidah."""
import re
from .common import PRAYER, POEM, SIDDUR, PROJECT_HE, AGG, cond, endcond, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml, MINYAN
from .milestones import marked
from .shacharit_end import editorial_head
from .shema_data import ROWS
from . import shabbat_shema_data as data

SERVICE = SIDDUR+'shabbat/shacharit'
ROOT = SERVICE+'/shema'
YOTZER = ROOT+'/yotzer_or'
SIGIL = '1949 shabbat/shacharit/shema'
EL_ADON = POEM+'el_adon'
LAEL = PRAYER+'yotzer_or/lael_asher_shavat'
SHABBAT = feature(AGG,'shabbat')
FESTIVAL_WEEKDAY = '<j:all>'+feature(AGG,'yom-tov')+'<j:none>'+SHABBAT+'</j:none></j:all>'
OLD = {key:(he,en) for key,he,en in ROWS}
RANGES = {'barekhu':(335,335), 'yotzer_or':(337,343), 'ahavah_rabbah':(343,343),
          'shema':(343,345), 'emet_veyatziv':(347,349)}


def conditional(cid,rubric,condition,body):
    cid='shabbat_shema_'+cid
    return cond(cid,note=rubric,fs=condition)+body+endcond(cid)


def xml(value):
    return text_xml(value,SIGIL).replace('|','<tei:lb/>').replace('{reader}',instruction('Reader')+' ')


def shared_hebrew(key):
    # Local translation variants align on their occurrence URNs. Reuse the
    # established Hebrew reading here without importing the weekday alignment
    # address or its page turns into the new bilingual paragraph.
    value=xml(re.sub(r'\{pb:\d+\}', '', OLD[key][0]))
    return f'<tei:seg source="{PRAYER}{key}">'+value+'</tei:seg>'


def shared(lang,prayers):
    result=[dict(p) for p in prayers];side=int(lang=='en')
    by_name={p['name']:p for p in result}
    for name,(first,last) in RANGES.items():
        p=by_name[name];p['printings']=(*p.get('printings',()),(first+side,last+side))
    # The festival printing has its own El Barukh commentary. Address the words
    # separately so its caller does not inherit the weekday occurrence's note.
    p=by_name['yotzer_or'];urn=PRAYER+'yotzer_or/el_barukh'
    pattern=r'(<tei:div corresp="'+re.escape(urn)+r'"><tei:p>)(.*?)(</tei:p></tei:div>)'
    p['body'],count=re.subn(pattern,lambda m:m[1]+marked(urn+'/text',m[2])+m[3],p['body'],flags=re.S)
    if count!=1:raise ValueError('Expected one El Barukh paragraph')
    def before(name,he,en,page,*,scope=None):
        p=by_name[name];anchor=(he,en)[side]
        start=p['body'].index('corresp="'+scope+'"') if scope else 0
        end=p['body'].find('<tei:milestone',start+len('corresp="'+scope+'"')) if scope else len(p['body'])
        segment=p['body'][start:end]
        if segment.count(anchor)!=1:raise ValueError(f'Ambiguous page turn in {name}: {anchor}')
        p['body']=p['body'][:start]+segment.replace(anchor,pb(page+side,sigil=SIGIL)+anchor,1)+p['body'][end:]
    before('yotzer_or','חֲדָשׁוֹת,','sows justice',343)
    before('shema','בַדֶּֽרֶךְ,','when you lie down',345,scope=BIBLE+'deuteronomy/6/7')
    before('emet_veyatziv','וּפוֹדֶה עֲנָוִים','his people whenever',349)
    return result


def prayers(lang):
    side=int(lang=='en');result=[]
    def add(name,urn,he,en,first,last,body):
        result.append(dict(name='shabbat_shema_'+name+'_text',urn=urn,title=(he,en)[side],first=first+side,last=last+side,
                           body=f'<tei:div corresp="{urn}">'+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    value='<tei:p>'+(shared_hebrew('yotzer_or/hameir') if not side else xml(data.HAMEIR_FESTIVAL_EN))+'</tei:p>'
    add('festival_hameir',YOTZER+'/festival/hameir','המאיר','Ha-me’ir (weekday festival)',337,337,value)
    body=''
    for i,(key,he,en) in enumerate(data.OPENING):
        urn=YOTZER+'/shabbat_opening/hameir' if key=='hameir' else PRAYER+'yotzer_or/'+key
        if side or i==0:body+='<tei:p>'
        body+=marked(urn,xml((he,en)[side]))+' '
        if side or i==len(data.OPENING)-1:body+='</tei:p>'
    add('shabbat_opening',YOTZER+'/shabbat_opening','הכל יודוך','All shall thank thee',337,339,body)
    body=''.join('<tei:p>'+marked(EL_ADON+'/'+str(n),xml(row[side]),unit='stanza')+'</tei:p>' for n,row in enumerate(data.EL_ADON,1))
    add('el_adon',EL_ADON,'אל אדון','El Adon',339,339,body)
    value=xml(data.LAEL_ASHER_SHAVAT[side])
    a,b=('מִזְמוֹר שִׁיר','טוֹב לְהוֹדוֹת לַייָ.') if not side else ('A song of the Sabbath day','give thanks to the Lord.')
    start=value.index(a);end=value.index(b,start)+len(b)
    value=value[:start]+f'<tei:seg source="{BIBLE}psalms/92/1 {BIBLE}psalms/92/2">'+value[start:end]+'</tei:seg>'+value[end:]
    add('lael_asher_shavat',LAEL,'לאל אשר שבת','To God who rested',339,341,'<tei:p>'+value+'</tei:p>')
    # The Hebrew is common; both English paragraphs differ from printed 74–76.
    values=[re.sub(r'\{pb:\d+\}','',OLD['ahavah_rabbah/ahavah'][1]).replace('forebears','forefathers'),data.AHAVAH_END_EN]
    body='<tei:p>'
    for key,value in zip(('ahavah','vahavienu'),values):
        content=shared_hebrew('ahavah_rabbah/'+key) if not side else xml(value)
        body+=marked(ROOT+'/ahavah_rabbah/'+key,content)+' '
    body+='</tei:p>'
    add('ahavah_rabbah',ROOT+'/ahavah_rabbah','אהבה רבה','Ahavah Rabbah',343,343,body)
    return result


def units(project,by_name):
    lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');result=[]
    def add(key,he,en,first,last,body,*,head=True):
        urn=ROOT+('/'+key if key else '')
        title=editorial_head(lang,he,en) if head else ''
        result.append(dict(name='shabbat_shacharit_shema'+('_'+key.replace('/','_') if key else ''),urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),
            body=f'<tei:div corresp="{urn}">'+title+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    add('yotzer_or/festival/el_barukh','אל ברוך','El Barukh',337,337,transclude(PRAYER+'yotzer_or/el_barukh/text'),head=False)
    festival=transclude(YOTZER+'/festival/hameir')+transclude(YOTZER+'/festival/el_barukh')
    # Preserve the printed navigation as an instruction; the continuation is
    # implemented structurally, so no redundant parentheses are needed.
    continuation=('Continue <tei:foreign xml:lang="he">תִּתְבָּרַךְ</tei:foreign> on page 341.' if not side else 'Continue “Be thou blessed” on page 342.')
    festival+='<tei:p><tei:note type="instruction" xml:lang="en">'+continuation+'</tei:note></tei:p>'
    body=transclude(PRAYER+'yotzer_or/opening')
    body+=conditional('festival','On festivals occurring on weekdays say:',FESTIVAL_WEEKDAY,festival)
    body+=conditional('shabbat','On Sabbaths say:',SHABBAT,transclude(YOTZER+'/shabbat_opening')+transclude(EL_ADON)+transclude(LAEL))
    body+=''.join(transclude(PRAYER+'yotzer_or/'+key) for key in ('titbarakh','et_shem','qadosh','vehaofannim','barukh_kevod','lael_barukh','or_chadash'))
    add('yotzer_or','יוצר אור','Yotzer Or',337,343,body)
    add('blessings_before','ברכות לפני קריאת שמע','Blessings before Shema',335,343,
        conditional('barekhu','When a minyan holds service:',MINYAN,transclude(PRAYER+'barekhu'))
        +transclude(YOTZER)+transclude(ROOT+'/ahavah_rabbah'))
    add('recitation','קריאת שמע','Shema',343,345,transclude(PRAYER+'shema'),head=False)
    add('blessings_after','אמת ויציב','Emet Veyatziv',347,349,transclude(PRAYER+'emet_veyatziv'))
    add('','קריאת שמע וברכותיה','Shema and its blessings',335,349,
        ''.join(transclude(ROOT+'/'+key) for key in ('blessings_before','recitation','blessings_after'))
        +'<tei:p>'+instruction('The Amidah for festivals begins on page '+str(585+side)+'.')+'</tei:p>')
    return tuple(result)


def extend_service(units_):
    result=[dict(u) for u in units_]
    for u in result:
        if u['urn']==SERVICE:
            marker='<j:endDeclare target="#shabbat_shacharit_service"/>'
            if u['body'].count(marker)!=1:raise ValueError('Expected one morning service declaration')
            u['body']=u['body'].replace(marker,transclude(ROOT)+marker)
            u['pages']=(u['pages'][0],349+(u['pages'][0]%2==0))
    return tuple(result)
