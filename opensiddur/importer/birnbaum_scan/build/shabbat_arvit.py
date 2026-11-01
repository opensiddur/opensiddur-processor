"""Shabbat and festival Arvit, printed 257–284, ending after Adon Olam."""
import re
from .common import PRAYER, POEM, SIDDUR, PROJECT_HE, AGG, SERVICE, RECITATION, feature, cond, endcond, pb
from .conclusion import BIBLE, instruction, transclude, text_xml, MINYAN, ELUL_SEASON, SEASON_RUBRIC, URNS as CONCLUSION
from .avinu_malkenu import TEN_DAYS
from .tachanun_conditions import holiday
from .milestones import marked
from .shacharit_end import editorial_head
from .arvit import URNS as ARVIT
from . import shabbat_arvit_data as data

ROOT = SIDDUR+'shabbat/arvit'
SIGIL = '1949 shabbat/arvit'
SHABBAT = feature(AGG,'shabbat')
FESTIVAL = feature(AGG,'yom-tov')
SHABBAT_AMIDAH = '<j:all>'+SHABBAT+'<j:none>'+FESTIVAL+'</j:none></j:all>'
REGALIM = '<j:all>'+FESTIVAL+'<j:any>'+holiday('pesah',8)+holiday('shavuot',2)+holiday('sukkot',7)+holiday('shmini-atzeret',2)+'</j:any></j:all>'
URNS = {'hashkivenu': PRAYER+'hashkivenu/hapores_sukkat_shalom',
        'veshamru':ROOT+'/verses/veshamru', 'vaydaber':BIBLE+'leviticus/23/44',
        'tiqu':ROOT+'/verses/tiqu', 'attah':PRAYER+'amidah/attah_qidashta_et',
        'vaykhulu':ROOT+'/vaykhulu', 'retzeh':PRAYER+'amidah/retzeh_vimnuchatenu',
        'mein':PRAYER+'meein_sheva', 'kiddush':PRAYER+'kiddush/asher_qiddeshanu',
        'wine':PRAYER+'borei_peri_hagafen'}


def conditional(cid,rubric,fs,content,*,negate=False,marked=False):
    return (cond('shabbat_arvit_'+cid,note=rubric,fs=fs,negate=negate,marked=marked)
            +content+endcond('shabbat_arvit_'+cid))


def xml(text):
    return text_xml(text,SIGIL).replace('{reader}',instruction('Reader'))


def prayers(lang,earlier):
    side=int(lang=='en'); result=[]
    seen=set(re.findall(r'corresp="([^"]+)"',''.join(p['body'] for p in earlier)))
    def add(key,he,en,first,last,body):
        urn=URNS[key]
        result.append(dict(name='shabbat_arvit_'+key+'_text',urn=urn,title=(he,en)[side],first=first+side,last=last+side,
                           body=f'<tei:div corresp="{urn}">'+body+'</tei:div>'))
    def para(key,text):
        return '<tei:p>'+marked(URNS[key]+'/text',xml(text))+'</tei:p>'
    def verses(key,rows):
        parts=[]
        for ref,he,en in rows:
            source=BIBLE+ref
            target=source if source not in seen else URNS[key]+'/'+ref.replace('/','_')
            value=xml((he,en)[side])
            if target!=source:value=f'<tei:seg source="{source}">{value}</tei:seg>'
            # A single-verse file already addresses the entire verse on its div.
            parts.append(value if target==URNS[key] else marked(target,value,unit='verse'))
            seen.add(target)
        return '<tei:p>'+' '.join(parts)+'</tei:p>'
    add('hashkivenu','הפורש סכת שלום','Who spreadest the shelter of peace',263,263,para('hashkivenu',data.HASHKIVENU_SEAL[side]))
    add('veshamru','ושמרו','The children of Israel shall keep the Sabbath',263,263,verses('veshamru',data.VESHAMRU))
    add('vaydaber','וידבר משה','Moses announced the festivals',263,263,verses('vaydaber',data.VAYDABER))
    add('tiqu','תקעו בחדש שופר','Sound the Shofar',263,263,verses('tiqu',data.TIKU))
    add('attah','אתה קדשת','Thou hast sanctified',267,267,para('attah',data.ATAH_KIDASHTA[side]))
    add('vaykhulu','ויכלו','Thus the heavens and the earth were finished',267,267,verses('vaykhulu',data.VAYKHULU))
    result[-1]['printings']=((273+side,273+side),)
    add('retzeh','רצה במנוחתנו','Be pleased with our rest',267,267,para('retzeh',(data.RETZEH_HE,data.RETZEH_EN)[side]))
    # Only the substituted word is conditional; the remainder of the paragraph
    # follows both readings once, outside their scopes.
    magen=xml(data.MAGEN_PREFIX[side])
    # The book stars הָאֵל and gives הַמֶּלֶךְ in the starred note: both are marked.
    magen+=conditional('magen_el','',TEN_DAYS,'הָאֵל' if not side else 'God',negate=True,marked=True)
    magen+=conditional('magen_melekh','',TEN_DAYS,'הַמֶּֽלֶךְ' if not side else 'King',marked=True)
    magen+=xml(data.MAGEN_REMAINDER[side])
    substitution = ('<tei:foreign xml:lang="he">הַמֶּֽלֶךְ</tei:foreign> for '
                    '<tei:foreign xml:lang="he">הָאֵל</tei:foreign>.'
                    if not side else '“holy King” for “holy God”.')
    congregation = ('<tei:note type="instruction" xml:lang="en">Congregation: '
                    'Between Rosh Hashanah and Yom Kippur substitute '
                    + substitution + '</tei:note>')
    mein=(instruction('Reader:')+'<tei:p>'+marked(PRAYER+'amidah/birkat_petichah_lemeein_sheva',xml(data.MEIN_OPENING[side]))+'</tei:p>'
          +congregation+'<tei:p>'+marked(PRAYER+'amidah/magen_avot',magen)+'</tei:p>'
          +instruction('Reader:')+'<tei:p>'+marked(URNS['mein']+'/retzeh',xml((data.RETZEH_HE,data.MEIN_RETZEH_EN)[side]))+'</tei:p>')
    add('mein','ברכה מעין שבע','Blessing embodying the seven blessings',273,275,mein)
    add('wine','בורא פרי הגפן','Who createst the fruit of the vine',277,277,para('wine',data.WINE[side]))
    add('kiddush','קידוש','Kiddush',277,277,para('kiddush',data.KIDDUSH[side]))
    return result


def shared(lang,prayers):
    result=[dict(p) for p in prayers]
    # Expose the meditation without its weekday-specific instruction. Its
    # Sabbath caller supplies the printed “After the Amidah” rubric exactly once.
    p=next(p for p in result if p['name']=='amidah_elohai_netzor')
    p['body']=re.sub(r'<tei:p>(.*?)</tei:p>',
        lambda m:'<tei:p>'+marked(PRAYER+'amidah/elohai_netzor/text',m[1])+'</tei:p>',
        p['body'],count=1,flags=re.S)
    from .shabbat_arvit_printings import apply
    return apply(lang,result)


def declaration():
    # Common Arvit serves both Shabbat and festivals: do not force either date.
    svc=''.join(f'<tei:f name="{n}"><tei:binary value="{str(n=="maariv").lower()}"/></tei:f>'
                for n in ('shaharit','minha','maariv','musaf','neila','slihot'))
    return (f'<j:declare xml:id="shabbat_arvit_service"><tei:fs type="{SERVICE}">{svc}</tei:fs>'
            f'<tei:fs type="{RECITATION}"><tei:f name="silent"><tei:binary value="true"/></tei:f>'
            '<tei:f name="repetition"><tei:binary value="false"/></tei:f></tei:fs></j:declare>')


def kaddish(cid,*,full=False,mourner=False):
    text='' if mourner else '<tei:p>'+instruction('Reader:')+'</tei:p>'
    text+=''.join(transclude(PRAYER+'kaddish/'+k) for k in ('yitgaddal','yehe_shemeh','yitbarakh'))
    if full:text+=transclude(PRAYER+'kaddish/titqabbal')
    if full or mourner:text+=''.join(transclude(PRAYER+'kaddish/yatom/'+k) for k in ('yehe_shelama','oseh_shalom'))
    return conditional(cid,'When a minyan holds service:',MINYAN,text)


def amidah(lang,by_name):
    text=instruction('The Amidah is recited in silent devotion while standing, facing east.')
    for name in ('amidah_adonai_sefatai','amidah_avot','amidah_gevurot','amidah_qedushat_hashem'):
        text+=transclude(by_name[name]['urn'])
    text+=''.join(transclude(URNS[k]) for k in ('attah','vaykhulu','retzeh'))
    text+=transclude(PRAYER+'amidah/avodah')
    # The Shabbat printing has only the Hanukkah insert, not the weekday Purim
    # insert; assemble its thanksgiving from the shared parts accordingly.
    text+=transclude(PRAYER+'amidah/hodaah/modim')
    text+=conditional('chanukah','On Ḥanukkah add:',holiday('hanukkah',8),transclude(PRAYER+'al_hanissim/chanukah'))
    text+=transclude(PRAYER+'amidah/hodaah/veal_kullam')
    text+=conditional('ukhetov','Between Rosh Hashanah and Yom Kippur add:',TEN_DAYS,transclude(PRAYER+'amidah/hodaah/ukhetov'))
    # The printed English here says “O God” where the shared weekday text says
    # “O Lord”. Local realization in both languages keeps parallel alignment.
    target=PRAYER+'amidah/hodaah/hatov_shimkha'
    original=next(p['body'] for p in by_name.values()
                  if '<tei:div corresp="'+target+'">' in p['body'])
    value=re.search(r'<tei:div corresp="'+re.escape(target)+r'">\s*<tei:p>(.*?)</tei:p>',original,re.S)[1]
    if lang=='en':value=value.replace('O Lord, Beneficent','O God, Beneficent')
    text+='<tei:p>'+marked(ROOT+'/amidah/hatov_shimkha',f'<tei:seg source="{target}">{value}</tei:seg>')+'</tei:p>'
    text+=transclude(PRAYER+'amidah/shalom_rav_al')
    text+=conditional('peace_seal','Except during the Ten Days of Repentance:',TEN_DAYS,transclude(PRAYER+'amidah/shalom/hamevarekh'),negate=True)
    text+=conditional('peace_ten_days','Between Rosh Hashanah and Yom Kippur say:',TEN_DAYS,transclude(PRAYER+'amidah/shalom/besefer_chayyim'))
    text+=instruction('After the Amidah add the following meditation:')
    text+=f'<tei:div corresp="{ROOT}/amidah/meditation">'+transclude(PRAYER+'amidah/elohai_netzor/text')+'</tei:div>'+transclude(PRAYER+'amidah/yehi_ratzon')
    return text


def units(project,by_name):
    lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');result=[]
    def unit(key,he,en,first,last,content,*,printed=False):
        urn=ROOT+('/'+key if key else '')
        head=f'<tei:head xml:lang="{lang}">{(he,en)[side]}</tei:head>' if printed else editorial_head(lang,he,en)
        if key=='shema':head=''  # The shared Shema supplies its printed heading.
        body=f'<tei:div corresp="{urn}">'+head+declaration()+pb(first+side,sigil=SIGIL)+content+'<j:endDeclare target="#shabbat_arvit_service"/></tei:div>'
        result.append(dict(name='shabbat_arvit'+('_'+key if key else ''),urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=body))
    unit('blessings_before_shema','ברכות לפני קריאת שמע','Blessings before Shema',257,257,
         conditional('barekhu','When a minyan holds service:',MINYAN,transclude(PRAYER+'barekhu'))+transclude(ARVIT['maariv'])+transclude(ARVIT['ahavat']))
    unit('shema','קריאת שמע','Shema',257,261,transclude(PRAYER+'shema'))
    after=''.join(transclude(ARVIT['emet']+'/'+part) for part in ('opening','mosheh','mi_khamokhah','malkhutekha','yimlokh'))
    # This printing corrects the numbered Jeremiah citation to 31:11. Isolate
    # its occurrence so the earlier 31:10 apparatus does not follow it here.
    seal_urn=ARVIT['emet']+'/seal'
    seal=re.search(r'<tei:milestone unit="prayer-part" corresp="'+re.escape(seal_urn)+r'"/>(.*?)<tei:milestone unit="prayer-part"/>',by_name['arvit_emet']['body'],re.S)[1]
    after+='<tei:p>'+marked(ROOT+'/blessings_after_shema/emet_seal',f'<tei:seg source="{seal_urn}">{seal}</tei:seg>')+'</tei:p>'
    after+=transclude(ARVIT['hashkivenu']+'/opening')+transclude(URNS['hashkivenu'])
    after+=conditional('veshamru','On the Sabbath, Congregation and Reader:',SHABBAT,transclude(URNS['veshamru']))
    after+=conditional('regalim','On Pesaḥ, Shavuoth and Sukkoth:',REGALIM,transclude(URNS['vaydaber']))
    after+=conditional('rosh_hashanah','On Rosh Hashanah:',holiday('rosh-hashana',2),transclude(URNS['tiqu']))
    unit('blessings_after_shema','ברכות לאחר קריאת שמע','Blessings after Shema',261,263,after+kaddish('half_kaddish'))
    unit('amidah','תפילת העמידה לשבת','Amidah for the Sabbath',265,273,amidah(lang,by_name))
    unit('after_amidah','ויכלו וברכה מעין שבע','Vaykhullu and Me‘ein Sheva',273,275,
         conditional('vaykhulu','On the Sabbath, Reader and Congregation:',SHABBAT,transclude(URNS['vaykhulu']))
         +conditional('mein','On the Sabbath, when a minyan holds service:', '<j:all>'+SHABBAT+MINYAN+'</j:all>',transclude(URNS['mein'])))
    unit('kaddish','קדיש שלם','Full Kaddish',275,275,kaddish('full_kaddish',full=True))
    kiddush='<tei:p>'+instruction('The Reader recites the following Kiddush over wine.')+'</tei:p>'
    # The English print omits the spoken invitation, rather than translating it.
    kiddush+='<tei:p>'+marked(ROOT+'/kiddush/savri','סַבְרִי מָרָנָן וְרַבּוֹתַי.' if not side else '')+'</tei:p>'
    kiddush+=transclude(URNS['wine'])+transclude(URNS['kiddush'])
    unit('kiddush','קידוש בבית הכנסת','Kiddush in the synagogue',277,277,
         conditional('kiddush','On the Sabbath, except on festivals, when a minyan holds service:',
                     '<j:all>'+SHABBAT_AMIDAH+MINYAN+'</j:all>',kiddush))
    conclusion=transclude(CONCLUSION['aleinu'])+'<tei:div>'+editorial_head(lang,'קדיש יתום','MOURNERS’ KADDISH')+kaddish('mourner',mourner=True)+'</tei:div>'+transclude(CONCLUSION['al_tira'])
    unit('conclusion','עלינו וסיום התפילה','Alenu and conclusion',277,279,conclusion)
    unit('psalm27','לדוד יי אורי','Psalm 27 for the season of repentance',281,281,
         conditional('psalm27',SEASON_RUBRIC,ELUL_SEASON,transclude(CONCLUSION['psalm_27'])+kaddish('psalm27_kaddish',mourner=True)))
    unit('adon_olam','אדון עולם','ADON OLAM',281,283,transclude(POEM+'adon_olam'),printed=True)
    sequence=''
    for u in result:
        if u['name']=='shabbat_arvit_amidah':
            sequence+=instruction(f'The Amidah for festivals begins on page {585+side}.')
            sequence+=conditional('sabbath_amidah','On the Sabbath, except on festivals:',SHABBAT_AMIDAH,transclude(u['urn']))
        else:sequence+=transclude(u['urn'])
    unit('','עַרְבִית לְשַׁבָּת וְיוֹם טוֹב','EVENING SERVICE FOR SABBATHS AND FESTIVALS',257,283,sequence,printed=True)
    return tuple(result)
