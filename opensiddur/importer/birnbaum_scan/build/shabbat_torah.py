"""Torah reading on Sabbaths and festivals, printed 361–390.

Occurrence gates belong to these service units. Common prayer files remain
independently reusable, including the first Yekum Purkan said in private.
"""
from .common import PRAYER, SIDDUR, PROJECT_HE, PERSON, AGG, feature, cond, endcond, pb
from .conclusion import instruction, transclude, text_xml, MINYAN
from .shacharit_end import editorial_head
from .milestones import Correspondences
from .tachanun_conditions import holiday
from .torah import URNS as WEEKDAY, BIBLE, GOMEL_RUBRIC
from .shabbat_amidah import SERVICE
from .shabbat_torah_data import PASSAGES

BIBLICAL_ANCHORS = {('ein_kamokha','ein'), ('al_hakol','shiru')} | {('av_memorial', n) for n in ('harninu','veniqqeiti','lammah','doresh','yadin','minachal')}

def anchor(key,name,source):
    return BIBLE+source if (key,name) in BIBLICAL_ANCHORS else URNS[key]+'/'+name


ROOT = SERVICE+'/torah'
KADDISH = SERVICE+'/kaddish_before_musaf'
SIGIL = '1949 shabbat/shacharit/torah'
TORAH = 'opensiddur:torah-reading'
SHABBAT = feature(AGG,'shabbat')
YOM_TOV = feature(AGG,'yom-tov')
REGALIM = '<j:any>'+holiday('pesah',8)+holiday('shavuot',2)+holiday('sukkot',7)+holiday('shmini-atzeret',2)+'</j:any>'
WEEKDAY_FESTIVAL = '<j:all>'+YOM_TOV+'<j:none>'+SHABBAT+'</j:none></j:all>'
FESTIVAL_HAFTARAH = '<j:any>'+YOM_TOV+'<j:all>'+SHABBAT+feature(AGG,'chol-hamoed')+holiday('sukkot',7)+'</j:all></j:any>'
MEVARCHIM = '<j:all>'+SHABBAT+feature(TORAH,'shabbat-mevarchim')+'</j:all>'
AV_OMISSIONS = ('shabbat-rosh-hodesh','shabbat-shkalim','shabbat-zachor',
    'shabbat-parah','shabbat-hahodesh','shabbat-hagadol','shabbat-shuva',
    'shabbat-nahamu','shabbat-mevarchim')
AV_HARACHAMIM = '<j:all>'+SHABBAT+'<j:none>'+YOM_TOV+feature(AGG,'chol-hamoed')+''.join(feature(TORAH,n) for n in AV_OMISSIONS)+'</j:none></j:all>'
URNS = {key:PRAYER+p['urn'] for key,p in PASSAGES.items()}
RANGES = {'torah_vayehi_binsoa':(363,363),'torah_berikh_shemeh':(365,365),
 'torah_gaddelu':(365,365),'torah_lekha_adonai':(365,367),
 'torah_av_harachamim':(367,367),'torah_veattem':(369,369),
 'torah_barekhu':(369,369),'torah_asher_bachar':(369,369),'torah_asher_natan':(369,369),
 'torah_hagomel':(369,369),'torah_vezot_hatorah':(373,373),
 'torah_yehalelu':(387,387),'torah_psalm24':(387,389),'torah_uvenuchoh':(389,389),
 'qabbalat_psalm_29':(387,387),'ashrei':(383,387)}


def conditional(cid,rubric,condition,body,*,negate=False):
    cid='shabbat_torah_'+cid
    return cond(cid,note=rubric,fs=condition,negate=negate)+body+endcond(cid)


def shared(lang,prayers):
    result=[dict(p) for p in prayers];side=int(lang=='en')
    for p in result:
        if p['name'] in RANGES:
            first,last=RANGES[p['name']]
            p['printings']=(*p.get('printings',()),(first+side,last+side))
        if p['name'] in ('kaddish_derabbanan_yitgaddal','kaddish_derabbanan_yehe_shemeh','kaddish_derabbanan_yitbarakh'):
            p['printings']=(*p.get('printings',()),(373+side,373+side),(389+side,389+side))
        turns=[]
        if p['name']=='ashrei':
            for verse,page in ((1,385),(21,387)):
                turns.append((f'<tei:milestone unit="verse" corresp="{BIBLE}psalms/145/{verse}"/>',page,True))
        if p['name']=='torah_lekha_adonai':
            turns.append((f'<tei:milestone unit="prayer-part" corresp="{WEEKDAY["lekha_adonai"]}/romemu_hadom"/>',367,False))
        if p['name']=='torah_psalm24':
            # The print turns mid-verse (before the first "your heads" in Hebrew
            # and before "you ancient doors" in English).
            marker=('רָאשֵׁיכֶם','you ancient doors')[side]
            turns.append((marker,389,False))
        for marker,page,after in turns:
            if marker not in p['body']:
                raise ValueError('Missing Torah-service page-turn anchor: '+p['name'])
            p['body']=p['body'].replace(marker,(marker+pb(page+side,sigil=SIGIL)) if after else (pb(page+side,sigil=SIGIL)+marker),1)
    return result


def expand(value,lang,key,row):
    side=int(lang=='en');value=text_xml(value,SIGIL)
    value=value.replace('{name}','…'+instruction('The name is given.'))
    value=value.replace('{reader}',instruction('Reader:'))
    value=value.replace('{family}','(וְאֶת אִשְׁתִּי וּבָנַי וּבְנוֹתַי)')
    inserts={
      'festival_honor':(REGALIM,'On festivals:','וְלִכְבוֹד הָרֶגֶל',''),
      'festival_pilgrimage':(REGALIM,'On festivals:','וְיִזְכֶּה לַעֲלוֹת לָרֶגֶל','may he live to celebrate festivals in Jerusalem'),
      'shabbat_day':(SHABBAT,'On the Sabbath:','וְעַל יוֹם הַשַּׁבָּת הַזֶּה','for this Sabbath day'),
      'shabbat_rest':(SHABBAT,'On the Sabbath:','לִקְדֻשָּׁה וְלִמְנוּחָה','for holiness and rest,'),
      'shabbat_seal':(SHABBAT,'On the Sabbath:','הַשַּׁבָּת וְ','the Sabbath and'),
    }
    for marker,(condition,rubric,he,en) in inserts.items():
        value=value.replace('{'+marker+'}',conditional(key+'_'+row+'_'+marker,rubric,condition,(he,en)[side]))
    names=[('pesah',8,'חַג הַמַּצּוֹת','Passover'),('shavuot',2,'חַג הַשָּׁבֻעוֹת','Shavuoth'),
           ('sukkot',7,'חַג הַסֻּכּוֹת','Sukkoth'),('shmini-atzeret',2,'הַשְּׁמִינִי חַג הָעֲצֶרֶת','Shemini Atsereth')]
    choice=' '.join(conditional(key+'_'+row+'_'+name,'On '+en+':',holiday(name,days),(he,{'pesah':'the Feast of Unleavened Bread','shavuot':'the Feast of Weeks','sukkot':'the Feast of Tabernacles','shmini-atzeret':'the Eighth-Day Feast'}[name])[side]) for name,days,he,en in names)
    return value.replace('{festival_name}',choice)


def prayers(lang,earlier):
    side=int(lang=='en');result=[]
    for key,p in PASSAGES.items():
        if key == 'yequm_opening':
            continue
        urn=URNS[key];marks=Correspondences();parts=['<tei:p>']
        rows=p['rows']
        if key in ('yequm_scholars','yequm_congregation'):
            rows=[('opening',None,*PASSAGES['yequm_opening']['rows'][0][2:]),*rows]
        for name,source,he,en in rows:
            value=expand((he,en)[side],lang,key,name)
            ref=anchor(key,name,source)
            if source and not ref.startswith(BIBLE):
                value='<tei:seg source="'+' '.join(BIBLE+s for s in source.split())+'">'+value+'</tei:seg>'
            if parts != ['<tei:p>'] and (key in ('haftarah_after','haftarah_shabbat','haftarah_festival','government') or (key=='ribbono' and name in ('yehi','vaani'))):
                parts.append('</tei:p><tei:p>')
            parts.append(marks.start(ref)+value+' ')
        parts.extend([marks.close(),'</tei:p>'])
        attr=' xml:lang="'+p['language']+'"' if p['language'] and not side else ''
        result.append(dict(name='shabbat_torah_'+key+'_text',urn=urn,
          title=' '.join(p['rows'][0][2].split()[:3]) if not side else key.replace('_',' ').capitalize(),
          first=p['first']+side,last=p['last']+side,
          body=f'<tei:div corresp="{urn}"{attr}>'+pb(p['first']+side,sigil=SIGIL)+''.join(parts)+'</tei:div>'))
    return result


def units(project,by_name):
    lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');result=[]
    def new(key):return transclude(URNS[key])
    def old(key):return transclude(WEEKDAY[key])
    def local(key,body):return f'<tei:div corresp="{ROOT}/{key}">'+body+'</tei:div>'
    def add(key,he,en,first,last,body,urn=None):
        urn=urn or ROOT+'/'+key
        result.append(dict(name='shabbat_torah_'+key,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),
          body=f'<tei:div corresp="{urn}">'+editorial_head(lang,he,en)+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    opening=instruction('Congregation and Reader:')+new('ein_kamokha')+new('heitivah')
    opening+=instruction('The ark is opened. Reader and Congregation:')+local('opening/vayehi',old('vayehi_binsoa'))
    opening+=conditional('festival_opening','On festivals occurring on weekdays add:',WEEKDAY_FESTIVAL,new('attributes')+new('ribbono'))
    opening+=old('berikh_shemeh')+instruction('The Reader takes the Torah and says:')+new('shema')+new('echad')+old('gaddelu')
    opening+=instruction('Congregation:')+local('opening/lekha',old('lekha_adonai'))+new('al_hakol')+instruction('Reader:')+old('av_harachamim')
    opening+=instruction('The Torah is placed on the desk. The Reader unrolls it and says:')+new('vayaazor')
    add('opening','הוצאת ספר תורה','Taking out the Torah',361,367,conditional('public_opening','When a minyan holds service:',MINYAN,opening))
    reading=instruction('Congregation and Reader:')+local('reading/veattem',old('veattem'))+instruction('The person called to the Torah recites:')+old('barekhu')
    reading+=instruction('He repeats the response and continues:')+local('reading/blessings',old('asher_bachar'))+instruction('The Torah is read. Then he recites:')+old('asher_natan')
    reading+=conditional('hagomel',GOMEL_RUBRIC,feature(PERSON,'birkat-hagomel'),f'<tei:div>'+editorial_head(lang,'בִּרְכַת הַגּוֹמֵל','THANKSGIVING')+local('reading/hagomel',old('hagomel'))+'</tei:div>')
    reading+=conditional('bar_mitzvah','The father of a Bar-Mitzvah pronounces the following blessing:',feature(PERSON,'bar-mitzvah-father'),new('bar_mitzvah'))
    reading+=instruction('On behalf of each person called to the Torah:')+new('mi_aliyah')
    for key,label in [('mi_daughter','On the occasion of naming a new-born daughter:'),('mi_sick_man','On behalf of a sick man:'),('mi_sick_woman','On behalf of a sick woman:')]:
        reading+=conditional(key,label,feature(PERSON,{'mi_daughter':'naming-daughter','mi_sick_man':'prayer-for-sick-man','mi_sick_woman':'prayer-for-sick-woman'}[key]),new(key))
    reading+=instruction('After the reading of the Torah, the Reader recites:')+transclude(PRAYER+'kaddish/chatzi')
    reading+=instruction('The Torah is raised, and the Congregation recites:')+local('reading/vezot',old('vezot_hatorah'))
    add('reading','קריאת התורה וברכותיה','Torah reading and blessings',369,373,conditional('public_reading','When a minyan holds service:',MINYAN,reading))
    haftarah=instruction('Before reading the Haftarah, the Maftir chants:')+new('haftarah_before')
    haftarah+=instruction('After reading the Haftarah:')+new('haftarah_after')
    haftarah+=conditional('haftarah_shabbat','On Sabbaths, including Ḥol ha-Mo‘ed Passover:',FESTIVAL_HAFTARAH,new('haftarah_shabbat'),negate=True)
    haftarah+=conditional('haftarah_festival','On festivals, including Ḥol ha-Mo‘ed Sukkoth:',FESTIVAL_HAFTARAH,new('haftarah_festival'))
    add('haftarah','ברכות ההפטרה','Haftarah blessings',373,377,conditional('public_haftarah','When a minyan holds service:',MINYAN,haftarah))
    yekum=new('yequm_scholars')
    yekum+=conditional('yequm_public','When praying in private, omit the following two paragraphs:',MINYAN,new('yequm_congregation')+new('mi_community'))
    add('yequm_purqan','יקום פורקן','Yekum Purkan',377,379,conditional('yequm_shabbat','The following three paragraphs are recited on Sabbaths only.',SHABBAT,yekum))
    add('government','תפילה בשלומה של מלכות','Prayer for the Government',379,379,instruction('The Reader takes the Torah and recites:')+new('government'))
    month=new('month_yehi')+instruction('The Reader takes the Torah and recites:')+new('month_mi')+instruction('Announcing the day of Rosh Ḥodesh:')+new('month_announce')+instruction('Congregation and Reader:')+new('month_yechaddeshehu')
    add('month','ברכת החודש','Blessing of the New Month',381,381,conditional('month','Recited on the Sabbath preceding Rosh Ḥodesh:',MEVARCHIM,month))
    add('memorial','הזכרת נשמות הקדושים','Commemoration of Martyrs',383,383,conditional('memorial','Omitted on festivals, on Sabbaths occurring on Rosh Ḥodesh, and on all distinguished Sabbaths such as Parashath Shekalim.',AV_HARACHAMIM,new('av_memorial')))
    add('ashrei','אשרי','Ashrei',383,387,transclude(PRAYER+'ashrei'))
    returning=instruction('The Reader takes the Torah and recites:')+old('yehalelu')
    returning+=conditional('psalm29','On Sabbaths:',SHABBAT,transclude(BIBLE+'psalms/29'))
    returning+=conditional('psalm24','On festivals occurring on weekdays:',WEEKDAY_FESTIVAL,f'<tei:div corresp="{ROOT}/return/psalm24">'+old('psalm24')+'</tei:div>')
    returning+=instruction('While the Torah is being placed in the ark:')+local('return/uvenuchoh',old('uvenuchoh'))
    add('return','הכנסת ספר תורה','Returning the Torah',387,389,conditional('public_return','When a minyan holds service:',MINYAN,returning))
    add('service','קריאת התורה','READING OF THE TORAH',361,389,''.join(transclude(ROOT+'/'+key) for key in ('opening','reading','haftarah','yequm_purqan','government','month','memorial','ashrei','return')),urn=ROOT)
    add('kaddish','חצי קדיש','Half Kaddish',389,389,conditional('final_kaddish','Reader, when a minyan holds service:',MINYAN,transclude(PRAYER+'kaddish/chatzi')),urn=KADDISH)
    return tuple(result)


def extend_service(units_,lang):
    result=[dict(u) for u in units_];side=int(lang=='en')
    for u in result:
        if u['urn']!=SERVICE:continue
        marker='<j:endDeclare target="#shabbat_shacharit_service"/>'
        if u['body'].count(marker)!=1:raise ValueError('Expected one Sabbath Shacharit declaration')
        u['body']=u['body'].replace(marker,transclude(ROOT)+transclude(KADDISH)+instruction(f'On festivals, continue with Musaf on page {585+side}.')+marker)
        u['pages']=(u['pages'][0],389+side)
    return tuple(result)
