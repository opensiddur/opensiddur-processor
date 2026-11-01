"""Rosh Hodesh Musaf Amidah, scan leaves n599–n608 (printed575–584)."""
import re
from .common import PRAYER,SIDDUR,PROJECT_HE,SERVICE,AGG,feature,cond,endcond,pb
from .conclusion import BIBLE,instruction,transclude,text_xml
from .shabbat_amidah import READER
from .shabbat_musaf import LEAP
from .tachanun_conditions import holiday
from .shacharit_end import editorial_head
from .milestones import marked
from .rosh_hodesh_musaf_data import ROWS,PAGES

ROOT=SIDDUR+'rosh_chodesh/musaf'
AMIDAH=ROOT+'/amidah'
SIGIL='1949 rosh_chodesh/musaf'
# Reuse only independently verified identical passages in BOTH languages.
REUSE={
 'sefatai':PRAYER+'amidah/adonai_sefatai',
 'gevurot_open':PRAYER+'amidah/gevurot/attah_gibbor',
 'mekhalkel':PRAYER+'amidah/gevurot/mekhalkel_chayyim',
 'hatov':PRAYER+'amidah/hodaah/hatov_shimkha',
 'yehi':PRAYER+'amidah/yehi_ratzon',
 'ki_shem':BIBLE+'deuteronomy/32/3',
 'avot':PRAYER+'amidah/avot/barukh_attah',
 'veneeman':PRAYER+'amidah/gevurot/mechayyeh_hametim',
 'neqaddesh':PRAYER+'amidah/qedushah/neqaddesh',
 'qadosh':PRAYER+'amidah/qedushah/qadosh',
 'leummatam':PRAYER+'amidah/qedushah/leummatam',
 'barukh':PRAYER+'amidah/qedushah/barukh_kevod',
 'uvedivrei':PRAYER+'amidah/qedushah/uvedivrei',
 'retzeh':PRAYER+'amidah/avodah/retzeh',
 'vetechezeinah':PRAYER+'amidah/avodah/vetechezeinah',
}
SOURCES={
 'sefatai':PRAYER+'amidah/adonai_sefatai','melekh':PRAYER+'amidah/avot/magen_avraham',
 'gevurot_open':PRAYER+'amidah/gevurot/attah_gibbor','rain':PRAYER+'amidah/gevurot/mashiv_haruach',
 'mekhalkel':PRAYER+'amidah/gevurot/mekhalkel_chayyim','yimlokh':BIBLE+'psalms/146/10',
 'ledor':PRAYER+'amidah/qedushah/ledor_vador','attah_qadosh':PRAYER+'amidah/qedushat_hashem',
 'offerings':BIBLE+'numbers/28/11','uminchatam':PRAYER+'amidah/uminchatam_veniskeihem',
 'modim':PRAYER+'amidah/hodaah/modim','modim_derabbanan':PRAYER+'amidah/hodaah/modim_derabbanan',
 'al_hanissim':PRAYER+'al_hanissim/chanukah/al_hanissim','bimei':PRAYER+'al_hanissim/chanukah/bimei',
 'veal_kullam':PRAYER+'amidah/hodaah/veal_kullam','hatov':PRAYER+'amidah/hodaah/hatov_shimkha',
 'kohanim':PRAYER+'amidah/birkat_kohanim','sim_shalom':PRAYER+'amidah/shalom',
 'elohai':PRAYER+'amidah/elohai_netzor/text','yehi':PRAYER+'amidah/yehi_ratzon',
}
UNIQUE={'rashei':PRAYER+'amidah/rashei_chodashim','chaddesh':PRAYER+'amidah/chaddesh_aleinu'}
URNS={r['key']:REUSE.get(r['key'],UNIQUE.get(r['key'],AMIDAH+'/'+r['key'])) for r in ROWS}


def conditional(key,rubric,condition,body,*,negate=False):
    cid='rosh_chodesh_musaf_'+key
    return cond(cid,note=rubric,fs=condition,negate=negate)+body+endcond(cid)


def shared(lang,prayers):
    side=int(lang=='en');result=[dict(p) for p in prayers]
    for p in result:
        pages={r['page']+side for r in ROWS if r['key'] in REUSE and
               ('corresp="'+REUSE[r['key']]+'"') in p['body']}
        p['printings']=(*p.get('printings',()),*((page,page) for page in sorted(pages)))
    return result


def prayers(lang):
    side=int(lang=='en');result=[]
    for row in ROWS:
        key=row['key']
        if key in REUSE:continue
        raw=row[lang]
        if key in ('rain','modim_derabbanan','al_hanissim','bimei'):raw=raw.removeprefix('(').removesuffix(')')
        if key=='chaddesh':
            raw=raw.replace('(וּלְכַפָּרַת פָּֽשַׁע)','{leap}').replace('(during leap year: and atonement of transgression)','{leap}')
        value=text_xml(raw,SIGIL).replace('\n','<tei:lb/>')
        if key=='chaddesh':
            value=value.replace('{leap}',conditional('leap','during leap year:',LEAP,('וּלְכַפָּרַת פָּֽשַׁע','and atonement of transgression')[side]))
        if key in SOURCES:value=f'<tei:seg source="{SOURCES[key]}">'+value+'</tei:seg>'
        urn=URNS[key];last=581 if key in ('modim','modim_derabbanan') else row['page']
        body=(f'<tei:div corresp="{urn}">'+pb(row['page']+side,sigil=SIGIL)+'<tei:p>'+value+'</tei:p></tei:div>') if key in UNIQUE else '<tei:p>'+pb(row['page']+side,sigil=SIGIL)+marked(urn,value)+'</tei:p>'
        result.append(dict(name='rosh_chodesh_musaf_'+key+'_text',urn=urn,title=key.replace('_',' '),first=row['page']+side,last=last+side,
            body=body))
    return result


def units(project):
    side=int(project!=PROJECT_HE);lang=('he','en')[side];result=[]
    def p(key):return transclude(URNS[key])
    def add(key,he,en,first,last,body,*,printed=False):
        urn=ROOT+('/'+key if key else '')
        head=(f'<tei:head xml:lang="{lang}">'+(he,en)[side]+'</tei:head>') if printed else editorial_head(lang,he,en)
        result.append(dict(name='rosh_chodesh_musaf'+('_'+key.replace('/','_') if key else ''),urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+head+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    ked=''.join(p(k) for k in ('neqaddesh','qadosh'))+pb(577+side,sigil=SIGIL)+''.join(p(k) for k in ('leummatam','barukh','uvedivrei','yimlokh'))+instruction('Reader:')+p('ledor')
    add('amidah/qedushah','קדושה','KEDUSHAH',575,577,ked,printed=bool(side))
    middle=''.join(p(k) for k in ('rashei','offerings','uminchatam','chaddesh'))
    add('amidah/qedushat_hayom','ראשי חדשים','Sanctification of Rosh Hodesh',577,579,middle)
    body=instruction(PAGES[str(575+side)]['rubrics'][0])+instruction(PAGES[str(575+side)]['rubrics'][1])
    body+=''.join(p(k) for k in ('ki_shem','sefatai','avot','melekh','gevurot_open'))
    body+=conditional('rain','Between Sukkoth and Pesaḥ add:',feature(AGG,'geshem'),p('rain'))+p('mekhalkel')+p('veneeman')
    body+=conditional('qedushah','When the Reader repeats the Amidah, the following Kedushah is said.',READER,transclude(AMIDAH+'/qedushah'))
    body+=conditional('silent','In silent devotion:',READER,p('attah_qadosh'),negate=True)
    body+=transclude(AMIDAH+'/qedushat_hayom')+p('retzeh')+p('vetechezeinah')
    body+=conditional('modim','When the Reader repeats the Amidah, the Congregation responds here by saying:',READER,p('modim_derabbanan'))+p('modim')
    body+=conditional('chanukah','On Ḥanukkah add:',holiday('hanukkah',8),p('al_hanissim')+p('bimei'))+p('veal_kullam')+p('hatov')
    body+=conditional('kohanim','Priestly blessing recited by the Reader:',READER,p('kohanim'))+p('sim_shalom')
    body+=conditional('meditation','After the Amidah add the following meditation:',READER,p('elohai'),negate=True)+p('yehi')
    add('amidah','מוּסָף לְרֹאשׁ חֹדֶשׁ','MUSAF FOR ROSH ḤODESH',575,583,body,printed=True)
    # Occasion gates stay outside the reusable Amidah. Sabbath has its own Musaf.
    scope='<j:all>'+holiday('rosh-hodesh',2)+'<j:none>'+feature(AGG,'shabbat')+'</j:none></j:all>'
    fields=''.join(f'<tei:f name="{key}"><tei:binary value="{str(key=="musaf").lower()}"/></tei:f>' for key in ('shaharit','minha','maariv','musaf','neila','slihot'))
    context=f'<j:declare xml:id="rosh_chodesh_musaf_service"><tei:fs type="{SERVICE}">{fields}</tei:fs></j:declare>'
    from .notes_motzaei_shabbat import xml as note_xml
    navigation=PAGES[str(583+side)]['navigation']
    sequence=transclude(AMIDAH)+'<tei:note type="instruction" xml:lang="en">'+note_xml(navigation)+'</tei:note>'
    body=context+conditional('occasion','On Rosh Ḥodesh that falls on a weekday:',scope,sequence)+'<j:endDeclare target="#rosh_chodesh_musaf_service"/>'
    add('','סדר מוסף לראש חודש','Rosh Hodesh Musaf',575,583,body)
    return tuple(result)
