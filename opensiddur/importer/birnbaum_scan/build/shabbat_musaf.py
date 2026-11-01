"""Sabbath Musaf and its conclusion, printed 391–424 (before Kiddush)."""
import re
from .common import PRAYER, SIDDUR, POEM, PROJECT_HE, SERVICE, AGG, feature, cond, endcond, pb
from .conclusion import instruction, transclude, text_xml, MINYAN, BIBLE, ELUL_SEASON
from .shacharit_end import editorial_head
from .milestones import marked, Correspondences
from .shabbat_amidah import READER
from .shabbat_arvit import URNS as ARVIT
from .tachanun_conditions import holiday
from .avinu_malkenu import TEN_DAYS
from .bameh_madlikin import TALMUD as ELAZAR, citation
from . import shabbat_musaf_data as data

ROOT = SIDDUR+'shabbat/musaf'
SIGIL = '1949 shabbat/musaf'
RC = holiday('rosh-hodesh',2)
OCCASION = '<j:all>'+feature(AGG,'shabbat')+'<j:none>'+feature(AGG,'yom-tov')+feature(AGG,'chol-hamoed')+'</j:none></j:all>'
LEAP = feature('opensiddur:hebrew-date','leap-year')
ANIM = POEM+'anim_zemirot'
EIN = POEM+'ein_keloheinu'
TAMID = 'urn:x-opensiddur:text:mishnah:tamid/7/4'
TANA = 'urn:x-opensiddur:text:talmud:megillah/28b/tana_devei_eliyahu'
PITTUM = PRAYER+'pittum_haqetoret_hatzori'
RASHBAG = PRAYER+'pittum_haqetoret_hatzori/rashbag'
TIKANTA = PRAYER+'amidah/tiqqanta_shabbat'
YATZARTA = PRAYER+'amidah/attah_yatzarta'
YISMECHU = PRAYER+'amidah/yismechu_vemalkhutekha'
RC_END = PRAYER+'amidah/retzeh_vechaddesh'
URNS = {key:PRAYER+'amidah/qedushah/'+key for key,_,_,_ in data.KEDUSHAH}
# Its translation of וּבְדִבְרֵי ("the holy Scriptures") differs from the weekday Kedushah's ("thy
# holy Scriptures"), so this printing keeps a local address and points to the common passage
# by source.
URNS['uvedivrei'] = ROOT+'/amidah/qedushah/uvedivrei'
RANGES = {
 'minchah_ki_shem':[(391,391)], 'amidah_adonai_sefatai':[(391,391)],
 'amidah_avot':[(391,391)], 'amidah_gevurot':[(391,393)],
 'amidah_qedushat_hashem':[(393,393)], 'amidah_avodah':[(399,399)],
 'amidah_hodaah':[(399,401)],'amidah_hodaah_modim_derabbanan':[(399,401)],
 'amidah_hodaah_ukhetov':[(401,401)],'al_hanissim_chanukah':[(401,401)],
 'amidah_birkat_kohanim':[(403,403)],'amidah_shalom':[(403,403)],
 'amidah_shalom_hamevarekh':[(403,403)],'amidah_shalom_besefer_chayyim':[(403,403)],
 'amidah_elohai_netzor':[(403,403)],'amidah_yehi_ratzon':[(405,405)],
 'conclusion_titqabbal':[(405,405)],'shabbat_arvit_retzeh_text':[(395,395)],
 'conclusion_aleinu':[(413,413)],'conclusion_al_tira':[(415,415)],
 'qabbalat_psalm_92':[(419,421)],'conclusion_psalm_27':[(421,421)],
 'poem_adon_olam':[(423,423)], 'amar_rabbi_elazar':[(409,411)],
 'kaddish_derabbanan_yitgaddal':[(405,405),(411,411),(413,413)],
 'kaddish_derabbanan_yehe_shemeh':[(405,405),(411,411),(413,413)],
 'kaddish_derabbanan_yitbarakh':[(405,405),(411,411),(415,415)],
 'kaddish_derabbanan_al_yisrael':[(411,411)],'kaddish_derabbanan_oseh_shalom':[(411,411)],
 'kaddish_yatom':[(405,405),(415,415)],
}
for part in ('qadosh','barukh_kevod','yimlokh','ledor_vador','hael_haqadosh','hamelekh_haqadosh'):
    RANGES['amidah_qedushah_'+part]=[(393,393)]


def conditional(cid,rubric,condition,body,*,negate=False):
    cid='shabbat_musaf_'+cid
    return cond(cid,note=rubric,fs=condition,negate=negate)+body+endcond(cid)


def shared(lang,prayers):
    side=int(lang=='en');result=[dict(p) for p in prayers]
    turns={
      'amar_rabbi_elazar':(('בָּנָיִךְ.', 'of your children.”'),411),
      'amidah_gevurot':(('וְנֶאֱמָן אַתָּה','Thou art faithful'),393),
      'amidah_hodaah':(('נִפְלְאוֹתֶ','evening, morning'),401),
      'amidah_hodaah_modim_derabbanan':(('וְתֶאֱסוֹף','holy courts'),401),
      'qabbalat_psalm_92':(('עֵינִי בְּשׁוּרָי','ears have heard'),421),
    }
    for p in result:
        if p['name'] in RANGES:
            p['printings']=(*p.get('printings',()),*((a+side,b+side) for a,b in RANGES[p['name']]))
        if p['name'] in turns:
            anchors,page=turns[p['name']];anchor=anchors[side]
            # Ignore stress marks when locating the printed Hebrew page turn.
            pattern=''.join(re.escape(c)+'[\u05bd]*' for c in anchor)
            matches=list(re.finditer(pattern,p['body']))
            if len(matches)!=1:raise ValueError(f'Ambiguous Musaf page turn: {p["name"]}: {anchor}')
            i=matches[0].start();p['body']=p['body'][:i]+pb(page+side,sigil=SIGIL)+p['body'][i:]
    return result


def prayers(lang,earlier):
    side=int(lang=='en');result=[];seen=set()
    for p in earlier:seen.update(re.findall(r'corresp="([^"]+)"',p['body']))
    def add(name,urn,first,last,body,title=None):
        result.append(dict(name='shabbat_musaf_'+name+'_text',urn=urn,title=title or name.replace('_',' '),
          first=first+side,last=last+side,body=f'<tei:div corresp="{urn}">'+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    def paragraph(pair):return '<tei:p>'+text_xml(pair[side],SIGIL)+'</tei:p>'
    for key,page,he,en in data.KEDUSHAH:
        value=text_xml((he,en)[side],SIGIL)
        if key=='ani':value=f'<tei:seg source="{BIBLE}numbers/15/41">'+value+'</tei:seg>'
        if key=='uvedivrei':value=f'<tei:seg source="{PRAYER}amidah/qedushah/uvedivrei">'+value+'</tei:seg>'
        add('qedushah_'+key,URNS[key],page,page,'<tei:p>'+value+'</tei:p>')
    # This translation differs from the previously printed complete Shema verse.
    add('qedushah_shema',ROOT+'/amidah/qedushah/shema',393,393,paragraph((
      'שְׁמַע, יִשְׂרָאֵל, יְיָ אֱלֹהֵינוּ, יְיָ אֶחָד.',
      '“Hear, O Israel, the Lord is our God, the Lord is One.”')).replace('<tei:p>',f'<tei:p><tei:seg source="{BIBLE}deuteronomy/6/4">').replace('</tei:p>','</tei:seg></tei:p>'))
    for name,urn,page,pair in [('tiqqanta',TIKANTA,395,data.TIKANTA),('yatzarta',YATZARTA,397,data.ATAH_YATZARTA),
          ('uminchatam',PRAYER+'amidah/uminchatam_veniskeihem',397,data.UMINCHATAM),('yismechu',YISMECHU,395,data.YISMECHU),
          ('pittum',PITTUM,407,data.PITTUM),('rashbag',RASHBAG,407,data.RASHBAG)]:
        add(name,urn,page,page,paragraph(pair))
        if name == 'yismechu':
            result[-1]['printings']=((399+side,399+side),)
    rc=[]
    for key,he,en in data.ROSH_CHODESH_END:
        value=text_xml((he,en)[side],SIGIL).replace('{leap}',conditional('leap','During leap year:',LEAP,('וּלְכַפָּרַת פָּשַׁע','and atonement of transgression')[side]))
        rc.append('<tei:p>'+marked(RC_END+'/'+key,value)+'</tei:p>')
    add('rosh_chodesh_end',RC_END,399,399,''.join(rc))
    for key,rows,page in [('offerings',data.OFFERINGS,395),('qavveh',data.KAVEH,405),('anim_end',data.ANIM_END,419)]:
        urn=ROOT+'/'+key;marks=Correspondences();parts=[]
        for source,he,en in rows:
            reference=BIBLE+source;value=text_xml((he,en)[side],SIGIL)
            if reference in seen:
                ref=urn+'/'+source.replace('/','_');value=f'<tei:seg source="{reference}">'+value+'</tei:seg>'
            else:ref=reference;seen.add(ref)
            if key=='offerings' and source.endswith('/11'):
                parts.append(marks.close()+'</tei:p>'+pb(397+side,sigil=SIGIL)+'<tei:p>')
            parts.append(marks.start(ref)+value+' ')
        add(key,urn,page,397 if key=='offerings' else page,'<tei:p>'+''.join(parts)+marks.close()+'</tei:p>')
    ein=''.join('<tei:p>'+marked(EIN+'/'+k,text_xml((he,en)[side],SIGIL),unit='stanza')+'</tei:p>' for k,he,en in data.EIN)
    add('ein_keloheinu',EIN,407,407,ein,'En Kelohenu' if side else 'אין כאלהינו')
    tamid=[]
    for key,source,he,en in data.TAMID:
        value=text_xml((he,en)[side],SIGIL)
        if source:
            # The Mishnah introduces each quotation, and adds its own Sabbath gloss.
            prefix,quote=value.split(':',1)
            if key=='shabbat':
                delimiter=' It is a song' if side else ' מִזְמוֹר שִׁיר לֶעָתִיד'
                quote,gloss=quote.split(delimiter,1);gloss=delimiter+gloss
            else:gloss=''
            value=prefix+':'+f'<tei:seg source="{BIBLE+source}">'+quote+'</tei:seg>'+gloss
        tamid.append('<tei:p>'+marked(TAMID+'/'+key,value)+'</tei:p>')
    add('tamid',TAMID,409,409,citation(('משנה תמיד ז, ד','Mishnah Tamid 7:4')[side],lang)+''.join(tamid))
    value=text_xml(data.TANA[side],SIGIL)
    quote=('הֲלִיכוֹת עוֹלָם לוֹ.','“His ways are eternal.”')[side]
    value=value.replace(quote,f'<tei:seg source="{BIBLE}habakkuk/3/6">{quote}</tei:seg>',1)
    add('tana',TANA,409,409,citation(('מסכת מגילה כח, ב','Talmud Megillah 28b')[side],lang)+'<tei:p>'+value+'</tei:p>')
    # The Musaf gloss omits "the ideal of" in English, so preserve a local
    # realization while transcluding the other addressed parts of this passage.
    source=next(p for p in earlier if p['name']=='amar_rabbi_elazar')['body']
    from lxml import etree
    tree=etree.fromstring(('<r xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">'+source+'</r>').encode())
    marker=tree.xpath('//*[@corresp=$u]',u=ELAZAR+'/al_tiqra')[0]
    pieces=[marker.tail or '']
    for el in marker.itersiblings():
        if el.tag.endswith('milestone'):break
        if not el.tag.endswith('pb'):pieces.append(etree.tostring(el,encoding='unicode'))
    value=''.join(pieces).replace('the ideal of peace','peace')
    add('elazar_gloss',ROOT+'/study/elazar/al_tiqra',411,411,'<tei:p>'+value+'</tei:p>')
    poem=[];last_page=None
    for key,page,he,en in data.ANIM:
        if page!=last_page:poem.append(pb(page+side,sigil=SIGIL));last_page=page
        lines=(he,en)[side].split('|')
        poem.append('<tei:lg><tei:milestone unit="stanza" corresp="'+ANIM+'/'+key+'"/>'+''.join('<tei:l>'+text_xml(line,SIGIL)+'</tei:l>' for line in lines)+'<tei:milestone unit="stanza"/></tei:lg>')
    add('anim_zemirot',ANIM,415,419,''.join(poem),'Hymn of Glory' if side else 'שיר הכבוד')
    return result


def kedushah():
    def p(key):return transclude(PRAYER+'amidah/qedushah/'+key)
    body=p('naaritz')+p('qadosh')+p('kevodo')+p('barukh_kevod')+p('mimeqomo')
    body+=transclude(ROOT+'/amidah/qedushah/shema')+p('hu')+p('ani')+transclude(URNS['uvedivrei'])+p('yimlokh')+instruction('Reader:')+p('ledor_vador')
    for key,negate in [('hael_haqadosh',True),('hamelekh_haqadosh',False)]:
        body+=conditional(key,'Except during the Ten Days of Repentance:' if negate else 'Between Rosh Hashanah and Yom Kippur say:',TEN_DAYS,p(key),negate=negate)
    return body


def units(project,by_name):
    lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');result=[]
    def tr(name):return transclude(by_name[name]['urn'])
    def p(suffix):return transclude(PRAYER+suffix)
    def add(key,he,en,first,last,body,*,printed=False):
        urn=ROOT+('/'+key if key else '')
        head=f'<tei:head xml:lang="{lang}">{(he,en)[side]}</tei:head>' if printed else editorial_head(lang,he,en)
        if not key:
            head=cond('shabbat_musaf_heading', fs=OCCASION)+head+endcond('shabbat_musaf_heading')
        result.append(dict(name='shabbat_musaf'+('_'+key.replace('/','_') if key else ''),urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+head+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    add('amidah/qedushah','קדושה','KEDUSHAH',393,393,kedushah())
    add('amidah/ordinary','תכנת שבת','Ordinary Sabbath blessing',395,395,p('amidah/tiqqanta_shabbat')+transclude(BIBLE+'numbers/28/9')+transclude(BIBLE+'numbers/28/10')+transclude(YISMECHU)+transclude(ARVIT['retzeh']))
    add('amidah/rosh_chodesh','אתה יצרת','Sabbath–Rosh Hodesh blessing',397,399,transclude(YATZARTA)+transclude(BIBLE+'numbers/28/9')+transclude(BIBLE+'numbers/28/10')+transclude(BIBLE+'numbers/28/11')+p('amidah/uminchatam_veniskeihem')+pb(399+side,sigil=SIGIL)+transclude(YISMECHU)+transclude(RC_END))
    body=instruction('The Amidah is recited in silent devotion while standing, facing east.')+instruction('The Reader repeats the Amidah aloud when a minyan holds service.')
    body+=''.join(tr(n) for n in ('minchah_ki_shem','amidah_adonai_sefatai','amidah_avot','amidah_gevurot'))
    body+=conditional('qedushah','When the Reader repeats the Amidah, the following Kedushah is said:',READER,transclude(ROOT+'/amidah/qedushah'))
    body+=conditional('silent','In silent devotion:',READER,p('amidah/qedushat_hashem'),negate=True)
    body+=conditional('ordinary','On regular Sabbaths:',RC,transclude(ROOT+'/amidah/ordinary'),negate=True)
    body+=conditional('rosh_chodesh','On Sabbath–Rosh Ḥodesh:',RC,transclude(ROOT+'/amidah/rosh_chodesh'))
    # No Yaaleh Veyavo in Musaf, even on Rosh Hodesh.
    body+=p('amidah/avodah/retzeh')+p('amidah/avodah/vetechezeinah')
    body+=conditional('modim','When the Reader repeats the Amidah, the Congregation responds here by saying:',READER,p('amidah/hodaah/modim_derabbanan'))
    body+=p('amidah/hodaah/modim')
    body+=conditional('chanukah','On Ḥanukkah add:',holiday('hanukkah',8),p('al_hanissim/chanukah'))
    body+=p('amidah/hodaah/veal_kullam')+conditional('ukhetov','Between Rosh Hashanah and Yom Kippur add:',TEN_DAYS,p('amidah/hodaah/ukhetov'))+p('amidah/hodaah/hatov_shimkha')
    body+=conditional('kohanim','During the Reader’s repetition:',READER,p('amidah/birkat_kohanim'))+p('amidah/shalom')
    body+=conditional('meditation','After the Amidah add the following meditation:',READER,f'<tei:div corresp="{ROOT}/amidah/meditation">'+p('amidah/elohai_netzor/text')+'</tei:div>',negate=True)+p('amidah/yehi_ratzon')
    add('amidah','עמידה למוסף','Musaf Amidah',391,405,body)
    full=instruction('Reader:')+''.join(p('kaddish/'+k) for k in ('yitgaddal','yehe_shemeh','yitbarakh','titqabbal','yatom/yehe_shelama','yatom/oseh_shalom'))
    add('kaddish','קדיש שלם','Full Kaddish',405,405,conditional('full_kaddish','When a minyan holds service:',MINYAN,full))
    add('ein_keloheinu','אין כאלהינו','EN KELOHENU',405,407,transclude(ROOT+'/qavveh')+transclude(EIN))
    elazar=citation(('מסכת ברכות סד, א','Talmud Berakhoth 64a')[side],lang)
    for key in ('opening','isaiah_54_13','al_tiqra','psalms_119_165','psalms_122_7','psalms_122_8','psalms_122_9','psalms_29_11'):
        if key=='al_tiqra':elazar+=transclude(ROOT+'/study/elazar/al_tiqra')
        else:elazar+=transclude(ELAZAR+'/'+key)
    add('study/elazar','אמר רבי אלעזר','Rabbi Elazar',409,411,elazar)
    study=citation(('מסכת כריתות ו, א','Talmud Kerithoth 6a')[side],lang)+transclude(PITTUM)+transclude(RASHBAG)+transclude(TAMID)+transclude(TANA)+transclude(ROOT+'/study/elazar')
    add('study','פיטום הקטורת ולימוד','Incense and study readings',407,411,study)
    kad=instruction('Mourners:')
    for key in ('yitgaddal','yehe_shemeh','yitbarakh','al_yisrael','yehe_shelama','oseh_shalom'):
        if key=='yehe_shelama':kad+=transclude(SIDDUR+'shabbat/qabbalat_shabbat/study_kaddish/yehe_shelama')
        else:kad+=p('kaddish/derabbanan/'+key)
    add('study_kaddish','קדיש דרבנן','KADDISH D’RABBANAN',411,411,conditional('study_kaddish','When a minyan holds service:',MINYAN,kad),printed=True)
    add('aleinu','עלינו','ALENU',413,413,tr('conclusion_aleinu'))
    def mourner(key,page):
        add(key,'קדיש יתום','Mourners’ Kaddish',page,page,conditional(key,'When a minyan holds service:',MINYAN,p('kaddish/yatom')))
    mourner('aleinu_kaddish',413)
    add('anim_zemirot','שִׁיר הַכָּבוֹד','HYMN OF GLORY',415,419,instruction('Recited in responsive form')+instruction('The ark is opened.')+transclude(ANIM)+transclude(ROOT+'/anim_end'),printed=True)
    mourner('anim_kaddish',419)
    intro=('הַיּוֹם שַׁבָּת קֹדֶשׁ, שֶׁבּוֹ הָיוּ הַלְוִיִּם אוֹמְרִים בְּבֵית הַמִּקְדָּשׁ:','This is the holy Sabbath day, on which the Levites in the Temple used to recite:')[side]
    add('shir_shel_yom','שיר של יום','Psalm for the Sabbath',419,421,'<tei:p>'+marked(ROOT+'/shir_shel_yom/introduction',intro)+'</tei:p>'+transclude(BIBLE+'psalms/92'))
    mourner('psalm92_kaddish',421)
    add('psalm27','לדוד יי אורי','Seasonal Psalm 27',421,421,transclude(BIBLE+'psalms/27'))
    mourner('psalm27_kaddish',421)
    add('adon_olam','אדון עולם','ADON OLAM',423,423,tr('poem_adon_olam'))
    sequence=conditional('sabbath_amidah','On Sabbaths, including Rosh Ḥodesh, except on festivals and Ḥol ha-Mo‘ed:',OCCASION,transclude(ROOT+'/amidah'))
    # A future festival Musaf returns here; Kaddish is outside the Amidah.
    sequence+=''.join(transclude(ROOT+'/'+k) for k in ('kaddish','ein_keloheinu','study','study_kaddish','aleinu','aleinu_kaddish'))
    sequence+=tr('conclusion_al_tira')+''.join(transclude(ROOT+'/'+k) for k in ('anim_zemirot','anim_kaddish'))
    sequence+=conditional('sabbath_psalm','On the Sabbath:',feature(AGG,'shabbat'),transclude(ROOT+'/shir_shel_yom')+transclude(ROOT+'/psalm92_kaddish'))
    sequence+=conditional('elul','The following is recited from Rosh Ḥodesh Elul until Simḥath Torah.',ELUL_SEASON,transclude(ROOT+'/psalm27')+transclude(ROOT+'/psalm27_kaddish'))
    sequence+=transclude(ROOT+'/adon_olam')
    svc=''.join(f'<tei:f name="{n}"><tei:binary value="{str(n=="musaf").lower()}"/></tei:f>' for n in ('shaharit','minha','maariv','musaf','neila','slihot'))
    declaration=f'<j:declare xml:id="shabbat_musaf_service"><tei:fs type="{SERVICE}">{svc}</tei:fs></j:declare>'
    add('','מוּסָף לְשַׁבָּת','MUSAF SERVICE FOR SABBATHS',391,423,declaration+sequence+'<j:endDeclare target="#shabbat_musaf_service"/>',printed=True)
    return tuple(result)
