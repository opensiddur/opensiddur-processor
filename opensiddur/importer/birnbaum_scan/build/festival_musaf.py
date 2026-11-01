"""Festival Musaf, priestly blessing, morning Kiddush and Tal, IA n633–660."""
import re
from .common import SIDDUR, PRAYER, PROJECT_HE, SERVICE, AGG, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .festival import conditional, HOLIDAYS, IN_SUKKAH
from .shabbat_arvit import SHABBAT, REGALIM
from .shabbat_amidah import READER
from .tachanun_conditions import holiday, ISRAEL, DIASPORA
from .shacharit_end import editorial_head
from .milestones import marked
from .festival_musaf_data import ROWS, PAGES

ROOT = SIDDUR+'regalim/musaf'
AMIDAH = ROOT+'/amidah'
KOHANIM = SIDDUR+'regalim/birkat_kohanim'
TAL = PRAYER+'tefillat_tal'
KIDDUSH = SIDDUR+'regalim/kiddush_morning'
SIGIL = '1949 festival musaf'
CHOL = feature(AGG,'chol-hamoed')
OCCASION = '<j:any>'+REGALIM+CHOL+'</j:any>'
MAJOR = '<j:any>'+REGALIM+SHABBAT+'</j:any>'
TAL_OCCASION = '<j:all>'+READER+holiday('pesah',1)+'</j:all>'
DUCHEN = '<j:all>'+READER+feature('opensiddur:practice','birkat-kohanim')+'</j:all>'
REPEAT = feature('opensiddur:practice','uminchatam-after-each-day')
URNS = {r['key']:ROOT+'/text/'+r['key'] for r in ROWS}
REUSE = {
 'veneeman':PRAYER+'amidah/gevurot/mechayyeh_hametim',
 'neqaddesh':SIDDUR+'shabbat/shacharit/amidah/qedushah/neqaddesh',
 'ledor':SIDDUR+'regalim/text/ledor',
 'attah_qadosh':SIDDUR+'regalim/text/attah_qadosh',
 **{'amidah_'+k:SIDDUR+'regalim/text/amidah_'+k for k in ('pesach','shavuot','sukkot','shemini')},
 'vetechezeinah':PRAYER+'amidah/avodah/vetechezeinah',
 'veal_kullam':PRAYER+'amidah/hodaah/veal_kullam',
 'hatov':PRAYER+'amidah/hodaah/hatov_shimkha',
 'wine':PRAYER+'borei_peri_hagafen',
}
URNS.update(REUSE)
URNS["tal_gevurot"]=URNS["gevurot"]


def shared(lang, prayers_):
    result=[dict(p) for p in prayers_]; side=int(lang=='en')
    for p in result:
        pages={r['page']+side for r in ROWS if REUSE.get(r['key'])==p['urn']}
        p['printings']=(*p.get('printings',()),*((n,n) for n in sorted(pages)))
    return result


# Repeating response units are bounded milestones, not hierarchical segments.
BIBLICAL = {'ki_shem':'deuteronomy/32/3','sefatai':'psalms/51/17',
 'qadosh_major':'isaiah/6/3','qadosh_chol':'isaiah/6/3',
 'barukh_major':'ezekiel/3/12','barukh_chol':'ezekiel/3/12',
 'shema':'deuteronomy/6/4','ani':'numbers/15/41',
 'yimlokh_major':'psalms/146/10','yimlokh_chol':'psalms/146/10',
 'shabbat_offering':'numbers/28/9','pesach_opening':'numbers/28/16',
 'pesach_offering':'numbers/28/19','shavuot_offering':'numbers/28/26',
 'sukkot_opening':'numbers/29/12','shemini_offering':'numbers/29/35',
 'shalosh_peamim':'deuteronomy/16/16','kiddush_shabbat':'exodus/31/16',
 'elleh_moadei':'leviticus/23/4','vayedaber':'leviticus/23/44'}
for d,v in ((2,17),(3,20),(4,23),(5,26),(6,29),(7,32)):
 for suffix in ('','_repeat'):BIBLICAL['sukkot_day'+str(d)+suffix]='numbers/29/'+str(v)
for group,refs in [(1,['psalms/134/3','psalms/8/10','psalms/16/1']),
 (2,['psalms/67/2','exodus/34/6','psalms/25/16','psalms/25/1','psalms/123/2']),
 (3,['psalms/24/5','isaiah/33/2','psalms/102/3','psalms/123/1','numbers/6/27','chronicles_1/29/11','isaiah/57/19'])]:
 for i,ref in enumerate(refs,1):BIBLICAL[f'kohanim_response_{group}_{i}']=ref

# Compound biblical paragraphs retain each verse boundary, including the
# cross-book pair in the response to Yissa and the Sabbath Kiddush anthology.
VERSE_GROUPS = {
 'shabbat_offering':['numbers/28/9','numbers/28/10'],
 'pesach_opening':['numbers/28/16','numbers/28/17','numbers/28/18'],
 'shavuot_offering':['numbers/28/26','numbers/28/27'],
 'sukkot_opening':['numbers/29/12','numbers/29/13'],
 'shemini_offering':['numbers/29/35','numbers/29/36'],
 'shalosh_peamim':['deuteronomy/16/16','deuteronomy/16/17'],
 'kiddush_shabbat':['exodus/31/16','exodus/31/17','exodus/20/11'],
 'kohanim_response_3_1':['psalms/24/5','proverbs/3/4'],
}


def c(key,rubric,expr,body,negate=False):
    return conditional('musaf_'+key,rubric,expr,body,negate=negate)


def prayers(lang):
    side=int(lang=='en');out=[]
    for r in ROWS:
        key=r['key']
        if key in REUSE or key=='tal_gevurot':continue
        raw=r[lang]
        if key in ('rain','yismechu','shabbat_offering','kiddush_shabbat','modim_derabbanan','kohanim_reader'):
            raw=raw.removeprefix('(').removesuffix(')')
        value=text_xml(raw,SIGIL).replace("\n","<tei:lb/>")
        if key in ('vattitten','miqra','musaf_intro','vehasi'):
            n=iter(range(20))
            value=re.sub(r'\(([^()]*)\)',lambda m:c(key+str(next(n)),'On the Sabbath:',SHABBAT,m[1]),value)
        if key in ('gevurot','attah_vechartanu'):
            source=PRAYER+('amidah/gevurot/attah_gibbor' if key=='gevurot' else 'amidah/attah_vechartanu_mikol')
            value=f'<tei:seg source="{source}">'+value+'</tei:seg>'
        if key in VERSE_GROUPS:
            chunks=re.split(r'(?<=\.)\s+',raw)
            refs=VERSE_GROUPS[key]
            if len(chunks)!=len(refs):raise ValueError((key,lang,chunks))
            value=' '.join(marked(URNS[key]+'/verse/'+str(i),
                f'<tei:seg source="{BIBLE+ref}">'+text_xml(chunk,SIGIL)+'</tei:seg>',unit='verse')
                for i,(ref,chunk) in enumerate(zip(refs,chunks),1))
        elif key in BIBLICAL:value=f'<tei:seg source="{BIBLE+BIBLICAL[key]}">'+value+'</tei:seg>'
        if key.startswith('kohanim_response_'):
            cue=text_xml(r['cue'],SIGIL)
            if lang=='en':cue='<tei:foreign xml:lang="he">'+cue+'</tei:foreign>'
            value=instruction('Kohanim:')+cue+' '+instruction('Congregation:')+value
        if key.startswith('tal_response_'):
            value=value.replace('אָמֵן.',instruction('Congregation:')+'אָמֵן.').replace('Amen.',instruction('Congregation:')+'Amen.')
            value=instruction('Congregation and Reader:')+value
        # Tal's printed verse lines remain lines; prose paragraphs remain prose.
        urn=URNS[key]
        body='<tei:p>'+pb(r['page']+side,sigil=SIGIL)+(value if key in VERSE_GROUPS else marked(urn,value,unit='verse' if key in BIBLICAL else 'prayer-part'))+'</tei:p>'
        if key in VERSE_GROUPS:body=f'<tei:div corresp="{urn}">'+body+'</tei:div>'
        last=max([r['page']+side]+[int(p) for p in re.findall(r'\{pb:(\d+)\}',raw)])
        out.append(dict(name='festival_musaf_'+key+'_text',urn=urn,title=key.replace('_',' '),first=r['page']+side,last=last,body=body))
    return out


def units(project):
    from .sukkot_rites import GESHEM, GESHEM_OCCASION
    side=int(project!=PROJECT_HE);lang=('he','en')[side];out=[]
    def p(k):return transclude(URNS[k])
    def seq(*keys):return ''.join(p(k) for k in keys)
    def add(name,urn,he,en,first,last,body,printed=False):
        head='<tei:head>'+((he,en)[side])+'</tei:head>' if printed else editorial_head(lang,he,en)
        out.append(dict(name='festival_musaf_'+name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+head+body+'</tei:div>'))
    major=('naaritzekha','qadosh_major','kevodo','barukh_major','mimeqomo','shema','hu_eloheinu','ani','addir','uvedivrei','yimlokh_major')
    add('qedushah_major',AMIDAH+'/qedushah/major','קדושה לימים טובים','KEDUSHAH FOR MAJOR FESTIVALS',609,611,seq(*major[:8])+instruction('Reader:')+seq(*major[8:]),True)
    add('qedushah_chol',AMIDAH+'/qedushah/chol_hamoed','קדושה לחול המועד','KEDUSHAH FOR ḤOL HA-MO‘ED',611,613,seq('neqaddesh','qadosh_chol','leummatam','barukh_chol','uvedivrei_chol','yimlokh_chol'),True)
    def alternatives(prefix):
        return ''.join(c(prefix+key,label,holiday(name,last),p(prefix+'_'+key)) for key,label,name,last in HOLIDAYS)
    offerings=c('shabbat_offering','On Sabbath:',SHABBAT,p('shabbat_offering'))
    first_pesach='<j:any><j:all>'+ISRAEL+holiday('pesah',1)+'</j:all><j:all>'+DIASPORA+holiday('pesah',2)+'</j:all></j:any>'
    offerings+=c('pesach_open','On the first two days of Pesaḥ (first day in Israel):',first_pesach,p('pesach_opening'))
    offerings+=c('pesach_all','On all the eight days of Pesaḥ (seven in Israel):',holiday('pesah',8),p('pesach_offering'))
    offerings+=c('shavuot_offer','On Shavuoth:',holiday('shavuot',2),p('shavuot_offering'))
    first_sukkot='<j:any><j:all>'+ISRAEL+holiday('sukkot',1)+'</j:all><j:all>'+DIASPORA+holiday('sukkot',2)+'</j:all></j:any>'
    offerings+=c('sukkot_open','On the first two days of Sukkoth (first day in Israel):',first_sukkot,p('sukkot_opening'))
    for d in range(2,8):
        today=feature('opensiddur:holiday','sukkot',f'<tei:numeric value="{d}"/>')
        offerings+=c('israel_sukkot_'+str(d),'In Israel, day '+str(d)+' of Sukkoth:','<j:all>'+ISRAEL+today+'</j:all>',p('sukkot_day'+str(d)))
        if d>=3:
            prev='sukkot_day'+str(d-1)+('_repeat' if d>=4 else '')
            body=p(prev)+c('repeat_'+str(d),'Some recite this after each day’s offering:',REPEAT,p('uminchatam'))+p('sukkot_day'+str(d))
            offerings+=c('diaspora_sukkot_'+str(d),'In the diaspora, '+('Hoshana Rabbah:' if d==7 else 'day '+str(d-2)+' of Ḥol ha-Mo‘ed Sukkoth:'),'<j:all>'+DIASPORA+today+'</j:all>',body)
    offerings+=c('shemini_offer','On Shemini Atsereth and Simḥath Torah:',holiday('shmini-atzeret',2),p('shemini_offering'))+p('uminchatam')
    add('offerings',AMIDAH+'/offerings','קרבנות המועדים','Festival offerings',615,619,offerings)
    middle=seq('attah_vechartanu','vattitten')+alternatives('amidah')+seq('miqra','umippenei','avinu_malkenu','musaf_intro')+alternatives('musaf')+p('naaseh')+transclude(AMIDAH+'/offerings')+c('yismechu','On Sabbath:',SHABBAT,p('yismechu'))+seq('melekh_rachaman','shalosh_peamim','vehasi')
    add('qedushat_hayom',AMIDAH+'/qedushat_hayom','קדושת היום','Sanctification of the festival',613,621,middle)
    modim=c('modim','When the Reader repeats the Amidah, the Congregation responds here by saying:',READER,p('modim_derabbanan'))+seq('modim','veal_kullam','hatov')
    add('hodaah',AMIDAH+'/hodaah','הודאה','Thanksgiving',623,623,modim)
    add('kohanim_retzeh',KOHANIM+'/avodah','ותערב','The priestly blessing: conclusion of Retzeh',625,627,instruction('Congregation:')+p('veteerav')+instruction('Reader:')+p('sheotekha'))
    ceremony=instruction('Congregation:')+p('kohanim_yehi')+instruction('Reader:')+p('kohanim_intro')+instruction('Congregation:')+p('am_qedoshekha')+instruction('Kohanim:')+p('kohanim_berakhah')
    for group,count in ((1,3),(2,5),(3,7)):
        ceremony+=''.join(p(f'kohanim_response_{group}_{i}') for i in range(1,count+1))
        if group==1:ceremony+=p('dream')
    ceremony+=instruction('Congregation:')+p('addir_bamarom')+instruction('Kohanim:')+p('kohanim_ribbon')
    add('kohanim',KOHANIM,'בִּרְכַּת כֹּהֲנִים','THE PRIESTLY BLESSING',627,631,ceremony,True)
    talbody=instruction('Chanted on the first day of Pesaḥ during Musaf')+instruction('Reader:')+seq('tal_avot','tal_bereshuto','tal_avot_end','tal_gevurot','tal_tehomot','tal_intro',*[f'tal_{i}' for i in range(1,7)],'tal_close',*[f'tal_response_{i}' for i in range(1,4)])
    add('tal',TAL,'תְּפִלַּת טַל','PRAYER FOR DEW',633,635,talbody,True)
    body=instruction('The Amidah is recited in silent devotion while standing, facing east.')+seq('ki_shem','sefatai')
    body+=c('tal','On the first day of Pesaḥ, during the Reader’s repetition:',TAL_OCCASION,transclude(TAL))
    body+=c('geshem','On Shemini Atsereth, during the Reader’s repetition:',GESHEM_OCCASION,transclude(GESHEM))
    normal=seq('avot','melekh','gevurot')+c('rain','On Shemini Atsereth and Simḥath Torah add:',holiday('shmini-atzeret',2),p('rain'))
    body+=c('ordinary_opening','Except during the prayers for dew and rain:','<j:any>'+TAL_OCCASION+GESHEM_OCCASION+'</j:any>',normal,True)+seq('mekhalkel','veneeman')
    body+=c('qedushah_major','During the Reader’s repetition on major festivals and Sabbaths:','<j:all>'+READER+MAJOR+'</j:all>',transclude(AMIDAH+'/qedushah/major'))
    body+=c('qedushah_chol','During the Reader’s repetition on weekday Ḥol ha-Mo‘ed:','<j:all>'+READER+CHOL+'<j:none>'+SHABBAT+'</j:none></j:all>',transclude(AMIDAH+'/qedushah/chol_hamoed'))
    body+=c('ledor','Reader:',READER,p('ledor'))+c('attah_qadosh','In silent devotion:',READER,p('attah_qadosh'),True)
    body+=transclude(AMIDAH+'/qedushat_hayom')+p('retzeh')
    body+=c('duchen_retzeh','When the Kohanim bless the congregation:',DUCHEN,transclude(KOHANIM+'/avodah'))+c('ordinary_retzeh','When the Kohanim do not bless the congregation:',DUCHEN,p('vetechezeinah'),True)
    body+=transclude(AMIDAH+'/hodaah')+c('duchen','When the Kohanim bless the congregation:',DUCHEN,transclude(KOHANIM))
    body+=c('reader_blessing','Priestly blessing recited by the Reader:','<j:all>'+READER+'<j:none>'+feature('opensiddur:practice','birkat-kohanim')+'</j:none></j:all>',p('kohanim_reader'))+p('sim_shalom')
    body+=c('meditation','After the Amidah add the following meditation:',READER,p('elohai_netzor'),True)+p('yehi_ratzon')
    add('amidah',AMIDAH,'מוּסָף לְשָׁלֹשׁ רְגָלִים','MUSAF FOR FESTIVALS',609,635,body,True)
    fields=''.join(f'<tei:f name="{k}"><tei:binary value="{str(k=="musaf").lower()}"/></tei:f>' for k in ('shaharit','minha','maariv','musaf','neila','slihot'))
    add('service',ROOT,'מוסף לשלש רגלים','Festival Musaf',609,635,'<j:declare xml:id="festival_musaf_context"><tei:fs type="'+SERVICE+'">'+fields+'</tei:fs></j:declare>'+c('occasion','On festivals and Ḥol ha-Mo‘ed:',OCCASION,transclude(AMIDAH))+'<j:endDeclare target="#festival_musaf_context"/>')
    kiddush=c('morning_shabbat','On Sabbath:',SHABBAT,p('kiddush_shabbat'))+seq('elleh_moadei','vayedaber','savri','wine')+c('morning_sukkah','In the Sukkah:','<j:all>'+holiday('sukkot',7)+IN_SUKKAH+'</j:all>',p('sukkah'))
    add('kiddush_morning',KIDDUSH,'קִדּוּשָׁא רַבָּה לְשָׁלֹשׁ רְגָלִים','MORNING KIDDUSH FOR FESTIVALS',631,631,kiddush,True)
    caller=SIDDUR+'regalim/morning_meal'
    out.append(dict(name='festival_musaf_morning_meal',urn=caller,
        title_he='קידוש היום לרגלים',title_en='Festival morning Kiddush',pages=(631+side,631+side),
        body=f'<tei:div corresp="{caller}">'+c('morning_occasion','On festivals:',REGALIM,transclude(KIDDUSH))+'</tei:div>'))
    return tuple(out)
