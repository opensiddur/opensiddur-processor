"""Sabbath morning Amidah and its separate common Kaddish, printed 349–362."""
import re
from .common import PRAYER, SIDDUR, PROJECT_HE, RECITATION, feature, cond, endcond, pb
from .conclusion import instruction, transclude, text_xml, MINYAN
from .shacharit_end import editorial_head
from .shared_passages import detach_division
from .shabbat_arvit import SHABBAT_AMIDAH, URNS as ARVIT
from .avinu_malkenu import TEN_DAYS
from .tachanun_conditions import holiday
from . import shabbat_amidah_data as data

SERVICE = SIDDUR+'shabbat/shacharit'
ROOT = SERVICE+'/amidah'
KADDISH = SERVICE+'/kaddish'
SIGIL = '1949 shabbat/shacharit/amidah'
READER = '<j:all>'+MINYAN+feature(RECITATION,'repetition')+'</j:all>'
URNS = dict(az=PRAYER+'amidah/az_beqol_raash',
            mimeqomekha=PRAYER+'amidah/mimeqomekha_malkenu_tofia',
            yismach=PRAYER+'amidah/yismach_mosheh_bemattenat',
            velo_netatto=PRAYER+'amidah/velo_netatto_hashem')
RANGES = {'amidah_adonai_sefatai':(349,349),'amidah_avot':(349,349),
          'amidah_gevurot':(349,351),'amidah_qedushah':(351,351),
          'amidah_qedushat_hashem':(353,353),'shabbat_arvit_veshamru_text':(353,353),
          'shabbat_arvit_retzeh_text':(353,353),'amidah_avodah':(353,355),
          'yaaleh_veyavo':(353,355),'amidah_hodaah':(355,357),
          'al_hanissim_chanukah':(357,357),'amidah_birkat_kohanim':(357,357),
          'amidah_shalom':(359,359),'amidah_shalom_hamevarekh':(359,359),
          'amidah_shalom_besefer_chayyim':(359,359),'amidah_elohai_netzor':(359,359),
          'amidah_yehi_ratzon':(359,359),'conclusion_titqabbal':(361,361),
          'kaddish_derabbanan_yitgaddal':(361,361),'kaddish_derabbanan_yehe_shemeh':(361,361),
          'kaddish_derabbanan_yitbarakh':(361,361),'kaddish_yatom':(361,361)}


def conditional(cid,rubric,condition,body,*,negate=False):
    cid='shabbat_amidah_'+cid
    return cond(cid,note=rubric,fs=condition,negate=negate)+body+endcond(cid)


def shared(lang,prayers):
    result=[dict(p) for p in prayers];side=int(lang=='en');by_name={p['name']:p for p in result}
    for name,(first,last) in RANGES.items():
        p=by_name[name];p['printings']=(*p.get('printings',()),(first+side,last+side))
    for name,he,en,page in [('amidah_gevurot','מְכַלְכֵּל חַיִּים','Thou sustainest the living',351),
                             ('yaaleh_veyavo','וְזִכְרוֹן מָ','Jerusalem thy holy city',355)]:
        p=by_name[name];anchor=(he,en)[side]
        if p['body'].count(anchor)!=1:raise ValueError(f'Ambiguous Sabbath Amidah page turn: {name}')
        p['body']=p['body'].replace(anchor,pb(page+side,sigil=SIGIL)+anchor,1)
    # Transclusions inherit active conditions at their source. Move the common
    # responses outside the weekday gate; its caller retains the same gate.
    for part in ('qadosh','barukh_kevod','yimlokh','ledor_vador','hael_haqadosh','hamelekh_haqadosh'):
        result.append(detach_division(by_name['amidah_qedushah'],
            PRAYER+'amidah/qedushah/'+part, 'amidah_qedushah_'+part,
            first=(85 if part in ('ledor_vador','hael_haqadosh','hamelekh_haqadosh') else 83)+side,
            last=(85 if part in ('ledor_vador','hael_haqadosh','hamelekh_haqadosh') else 83)+side))
    for part in ('modim_derabbanan','ukhetov'):
        page=91 if part=='modim_derabbanan' else 93
        result.append(detach_division(by_name['amidah_hodaah'],
            PRAYER+'amidah/hodaah/'+part, 'amidah_hodaah_'+part,first=page+side,last=page+side))
    return result


def prayers(lang,earlier):
    side=int(lang=='en');result=[]
    for key,he,en in data.ROWS:
        page=351 if key in ('az','mimeqomekha') else 353
        urn=URNS[key]
        result.append(dict(name='shabbat_amidah_'+key+'_text',urn=urn,title=(he.split(',')[0],en.split(',')[0])[side],
            first=page+side,last=page+side,body=f'<tei:div corresp="{urn}">'+pb(page+side,sigil=SIGIL)+'<tei:p>'+text_xml((he,en)[side],SIGIL)+'</tei:p></tei:div>'))
    # The scan's English says "in the world", rather than the weekday "in this
    # world". Local correspondence aligns the variant with shared Hebrew.
    source=PRAYER+'amidah/qedushah/neqaddesh'
    original=next(p for p in earlier if p['name']=='amidah_qedushah')['body']
    he=re.search(r'<tei:div corresp="'+re.escape(source)+r'">\s*<tei:p>(.*?)</tei:p>',original,re.S)[1]
    urn=ROOT+'/qedushah/neqaddesh'
    value=text_xml(data.NEQADESH_EN,SIGIL) if side else f'<tei:seg source="{source}">{he}</tei:seg>'
    result.append(dict(name='shabbat_amidah_neqaddesh_text',urn=urn,title='Nekadesh',first=351+side,last=351+side,
        body=f'<tei:div corresp="{urn}"><tei:p>{value}</tei:p></tei:div>'))
    return result


def kedushah():
    parts=[transclude(ROOT+'/qedushah/neqaddesh'),transclude(PRAYER+'amidah/qedushah/qadosh'),
           transclude(URNS['az']),transclude(PRAYER+'amidah/qedushah/barukh_kevod'),
           transclude(URNS['mimeqomekha']),transclude(PRAYER+'amidah/qedushah/yimlokh'),
           transclude(PRAYER+'amidah/qedushah/ledor_vador')]
    for key,negate,rubric in [('hael_haqadosh',True,'Except during the Ten Days of Repentance:'),
                              ('hamelekh_haqadosh',False,'Between Rosh Hashanah and Yom Kippur substitute:')]:
        parts.append(conditional('qedushah_'+key,rubric,TEN_DAYS,transclude(PRAYER+'amidah/qedushah/'+key),negate=negate))
    return ''.join(parts)


def amidah(lang,by_name):
    text=instruction('The Amidah is recited in silent devotion while standing, facing east.')
    text+=instruction('The Reader repeats the Amidah aloud when a minyan holds service.')
    text+=''.join(transclude(by_name[n]['urn']) for n in ('amidah_adonai_sefatai','amidah_avot','amidah_gevurot'))
    text+=conditional('qedushah','When the Reader repeats the Amidah, the following Kedushah is said:',READER,transclude(ROOT+'/qedushah'))
    text+=conditional('attah_qadosh','In silent devotion:',READER,transclude(PRAYER+'amidah/qedushat_hashem'),negate=True)
    text+=transclude(URNS['yismach'])+transclude(ARVIT['veshamru'])+transclude(URNS['velo_netatto'])+transclude(ARVIT['retzeh'])
    text+=transclude(PRAYER+'amidah/avodah')
    text+=conditional('modim','When the Reader repeats the Amidah, the Congregation responds here by saying:',READER,transclude(PRAYER+'amidah/hodaah/modim_derabbanan'))
    text+=transclude(PRAYER+'amidah/hodaah/modim')
    text+=conditional('chanukah','On Ḥanukkah add:',holiday('hanukkah',8),transclude(PRAYER+'al_hanissim/chanukah'))
    text+=transclude(PRAYER+'amidah/hodaah/veal_kullam')
    text+=conditional('ukhetov','Between Rosh Hashanah and Yom Kippur add:',TEN_DAYS,transclude(PRAYER+'amidah/hodaah/ukhetov'))
    text+=transclude(PRAYER+'amidah/hodaah/hatov_shimkha')
    text+=conditional('kohanim','During the Reader’s repetition:',READER,transclude(PRAYER+'amidah/birkat_kohanim'))
    text+=transclude(PRAYER+'amidah/shalom')
    text+=conditional('meditation','After the Amidah add the following meditation:',READER,
        f'<tei:div corresp="{ROOT}/meditation">'+transclude(PRAYER+'amidah/elohai_netzor/text')+'</tei:div>',negate=True)+transclude(PRAYER+'amidah/yehi_ratzon')
    return text


def units(project,by_name):
    lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');result=[]
    def add(name,urn,he,en,first,last,body):
        result.append(dict(name=name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),
            body=f'<tei:div corresp="{urn}">'+editorial_head(lang,he,en)+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    add('shabbat_shacharit_amidah_qedushah',ROOT+'/qedushah','קדושה','KEDUSHAH',351,351,kedushah())
    add('shabbat_shacharit_amidah',ROOT,'תפילת העמידה לשבת','AMIDAH',349,359,amidah(lang,by_name))
    text='<tei:p>'+instruction('Reader:')+'</tei:p>'
    text+=''.join(transclude(PRAYER+'kaddish/'+k) for k in ('yitgaddal','yehe_shemeh','yitbarakh','titqabbal','yatom/yehe_shelama','yatom/oseh_shalom'))
    add('shabbat_shacharit_kaddish',KADDISH,'קדיש שלם','Full Kaddish',361,361,
        conditional('kaddish','When a minyan holds service:',MINYAN,text))
    return tuple(result)


def extend_service(units_,lang):
    result=[dict(u) for u in units_];side=int(lang=='en')
    for u in result:
        if u['urn']!=SERVICE:continue
        marker='<j:endDeclare target="#shabbat_shacharit_service"/>'
        if u['body'].count(marker)!=1:raise ValueError('Expected one Sabbath Shacharit declaration')
        addition=conditional('sabbath','On the Sabbath, including Ḥol ha-Mo‘ed, but not Yom Tov:',SHABBAT_AMIDAH,transclude(ROOT))
        addition+=instruction(f'Hallel (page {565+side}) is recited here on Rosh Ḥodesh, Ḥol ha-Mo‘ed and Ḥanukkah.')
        # This return point remains outside the Sabbath-Amidah gate: a future
        # festival Amidah will continue here, then on to the Torah service.
        addition+=transclude(KADDISH)
        u['body']=u['body'].replace(marker,addition+marker)
        u['pages']=(u['pages'][0],361+side)
    return tuple(result)
