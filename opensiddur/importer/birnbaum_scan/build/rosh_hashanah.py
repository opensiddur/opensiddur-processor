"""Rosh Hashanah Minḥah/Ma‘ariv, Kiddush, Tashlikh and Kapparot, IA n679–698."""
import re
from .common import cond, endcond, PRAYER, SIDDUR, PROJECT_HE, SERVICE, AGG, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .festival import conditional, MINCHAH, MAARIV, SATURDAY_NIGHT
from .shabbat_amidah import READER as AMIDAH_READER
from .shabbat_arvit import SHABBAT
from .tachanun_conditions import holiday, date
from .shacharit_end import editorial_head
from .milestones import marked
from .rosh_hashanah_data import ROWS, RUBRICS

ROOT = SIDDUR+'rosh_hashanah'
AMIDAH = ROOT+'/minchah_maariv/amidah'
KIDDUSH = ROOT+'/kiddush'
TASHLIKH = PRAYER+'tashlikh'
KAPPAROT = PRAYER+'kapparot'
CANDLES = PRAYER+'hadlaqat_ner_yom_kippur'
SIGIL = '1949 rosh hashana and erev yom kippur'
RH = holiday('rosh-hashana',2)
READER = '<j:all>'+MINCHAH+AMIDAH_READER+'</j:all>'
TASHLIKH_DAY = '<j:any><j:all>'+date(7,1)+'<j:none>'+SHABBAT+'</j:none></j:all><j:all>'+date(7,2)+feature('opensiddur:day-of-week','hebrew-day','<tei:numeric value="1"/>')+'</j:all></j:any>'
KAPPAROT_DAY = date(7,9)
KAPPAROT_OBJECT = 'kapparot-object'

def object_condition(value):
    return feature('opensiddur:practice',KAPPAROT_OBJECT,f'<tei:symbol value="{value}"/>')

# Newly encountered liturgical paragraphs have reusable prayer addresses. The
# repeated printings below keep this occurrence's wording and its own apparatus.
UNIQUE = {'uvekhen_pachdekha':PRAYER+'amidah/uvekhen_ten_pachdekha',
 'uvekhen_kavod':PRAYER+'amidah/uvekhen_ten_kavod',
 'uvekhen_tzaddiqim':PRAYER+'amidah/uvekhen_tzaddiqim',
 'vetimlokh':PRAYER+'amidah/vetimlokh_attah_hashem',
 'qadosh_ata':PRAYER+'amidah/qadosh_attah_venora',
 'melokh':PRAYER+'amidah/melokh_al_kol_haolam',
 'kadsheinu':PRAYER+'amidah/sof_birkat_hazeman_lerosh_hashanah',
 'greeting':PRAYER+'leshanah_tovah_tikkatev',
 'kiddush':PRAYER+'kiddush_rosh_hashanah',
 'apple':PRAYER+'shetechaddesh_aleinu_shanah_tovah',
 'yk_candle_blessing':CANDLES+'/blessing'}
SOURCES = {'ki_shem':BIBLE+'deuteronomy/32/3','adonai_sefatai':BIBLE+'psalms/51/17',
 'avot':PRAYER+'amidah/avot/barukh_attah','zokhrenu':PRAYER+'amidah/avot/zokhrenu',
 'melekh_ozer':PRAYER+'amidah/avot/magen_avraham','gevurot_start':PRAYER+'amidah/gevurot/attah_gibbor',
 'mekhalkel':PRAYER+'amidah/gevurot/mekhalkel_chayyim','mi_khamokha':PRAYER+'amidah/gevurot/mi_khamokha',
 'neeman':PRAYER+'amidah/gevurot/mechayyeh_hametim','neqaddesh':PRAYER+'amidah/qedushah/neqaddesh',
 'qadosh':BIBLE+'isaiah/6/3','barukh':BIBLE+'ezekiel/3/12','yimlokh':BIBLE+'psalms/146/10',
 'leummatam':PRAYER+'amidah/qedushah/leummatam','uvdivrei':PRAYER+'amidah/qedushah/uvdivrei',
 'ledor_vador':PRAYER+'amidah/qedushah/ledor_vador','attah_qadosh':PRAYER+'amidah/qedushat_hashem',
 'attah_vechartanu':PRAYER+'amidah/attah_vechartanu_mikol','vattodienu':PRAYER+'amidah/vattodienu',
 'yaaleh_veyavo':PRAYER+'yaaleh_veyavo','retzeh':PRAYER+'amidah/avodah/retzeh',
 'vetechezeinah':PRAYER+'amidah/avodah/vetechezeinah','modim':PRAYER+'amidah/hodaah/modim',
 'modim_derabbanan':PRAYER+'amidah/hodaah/modim_derabbanan','veal_kullam':PRAYER+'amidah/hodaah/veal_kullam',
 'vekhol_hachayyim':PRAYER+'amidah/hodaah/hatov_shimkha','shalom_rav':PRAYER+'amidah/shalom_rav_al',
 'elohai_netzor':PRAYER+'amidah/elohai_netzor/text','yehi_ratzon_temple':PRAYER+'amidah/yehi_ratzon',
 'wine':PRAYER+'borei_peri_hagafen','havdalah':PRAYER+'hamavdil_bein_qodesh_leqodesh',
 'shehecheyanu':PRAYER+'shehecheyanu','yk_shehecheyanu':PRAYER+'shehecheyanu',
 'isaiah11_9':BIBLE+'isaiah/11/9'}
URNS = {r['key']:UNIQUE.get(r['key'],ROOT+'/text/'+r['key']) for r in ROWS}
URNS.update(benei_adam=KAPPAROT+'/verses',zeh_halifatenu=KAPPAROT+'/fowl')


def xml(value):
    return text_xml(value,SIGIL).replace('\n','<tei:lb/>')


def c(key,rubric,condition,body,negate=False):
    return conditional('rh_'+key,rubric,condition,body,negate=negate)


def quotation(value,source):
    return f'<tei:seg source="{source}">'+value+'</tei:seg>'


def prayers(lang):
    side=int(lang=='en');out=[]
    for r in ROWS:
        key=r['key'];urn=URNS[key]
        if key=='zeh_halifatenu':continue
        raw=r[lang]
        if key in ('ki_shem','vattodienu','modim_derabbanan','vayekhulu','fire','havdalah'):
            raw=raw.removeprefix('(').removesuffix(')')
        value=xml(raw)
        if key in ('vattitten_lanu','kadsheinu','kiddush','yk_candle_blessing'):
            n=iter(range(20))
            value=re.sub(r'\(([^()]*)\)',lambda m:c(key+'_shabbat_'+str(next(n)),
                'On the Sabbath:',SHABBAT,m[1]),value)
        if 'verse_refs' in r:
            chunks=[]
            previous=''
            for ref,v in zip(r['verse_refs'],r[lang+'_verses']):
                if chunks and not previous.endswith('—'):chunks.append(' ')
                chunks.append(marked(urn+'/'+ref,quotation(xml(v),BIBLE+ref) if ref!='intro' else xml(v),unit='verse'))
                previous=v
            value=''.join(chunks)
        elif key in SOURCES:value=quotation(value,SOURCES[key])
        # Mark explicit quotations embedded in liturgical prose independently.
        if key in ('vetimlokh','qadosh_ata'):
            if lang=='he':
                start=('יִמְל' if key=='vetimlokh' else 'וַיִּגְבַּהּ')
                # Pointing varies by printing; locate the consonants, retain points.
                pat=''.join(ch+'[\u0591-\u05c7]*' for ch in re.sub('[\u0591-\u05c7]','',start))
                m=re.search(pat,value);a=m.start()
                b=len(value) if key=='vetimlokh' else value.index(' בָּרוּךְ',a)
            else:
                a=value.index('“');b=value.index('”',a)+1
            source=BIBLE+('psalms/146/10' if key=='vetimlokh' else 'isaiah/5/16')
            value=value[:a]+quotation(value[a:b],source)+value[b:]
        if key=='greeting' and lang=='he':
            singular,plural=value.split('<tei:lb/>')
            value=instruction('Singular')+singular+'<tei:lb/>'+instruction('Plural')+plural
        last=max([r['page']+side]+[int(n) for n in re.findall(r'\{pb:(\d+)\}',raw)])
        out.append(dict(name='rh_'+key+'_text',urn=urn,title=key.replace('_',' '),first=r['page']+side,last=last,
            body=(f'<tei:div corresp="{urn}">'+pb(r['page']+side,sigil=SIGIL)+'<tei:p>'+value+'</tei:p></tei:div>') if key in UNIQUE else '<tei:p>'+pb(r['page']+side,sigil=SIGIL)+marked(urn,value)+'</tei:p>'))
    return out


def units(project):
    side=int(project!=PROJECT_HE);lang=('he','en')[side];out=[]
    def p(key):return transclude(URNS[key])
    def add(name,urn,he,en,first,last,body,printed=False,heading=True):
        head=('<tei:head>'+((he,en)[side])+'</tei:head>') if printed else editorial_head(lang,he,en)
        if not heading:head=''
        out.append(dict(name=name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),
            body=f'<tei:div corresp="{urn}">'+head+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    def group(name,he,en,first,last,keys):
        add('rh_'+name,AMIDAH+'/'+name,he,en,first,last,''.join(p(k) for k in keys))
    group('avot','אבות','Patriarchs',655,655,['avot','zokhrenu','melekh_ozer'])
    group('gevurot','גבורות','Divine power',655,655,['gevurot_start','mekhalkel','mi_khamokha','neeman'])
    kedushah=''.join(p(k) for k in ('neqaddesh','qadosh','leummatam','barukh','uvdivrei','yimlokh'))+instruction('Reader:')+p('ledor_vador')
    add('rh_qedushah',AMIDAH+'/qedushah','קדושה','Kedushah',655,657,kedushah)
    body=c('qedushah',RUBRICS['qedushah_rubric'],READER,transclude(AMIDAH+'/qedushah'))
    body+=''.join(p(k) for k in ('attah_qadosh','uvekhen_pachdekha','uvekhen_kavod','uvekhen_tzaddiqim','vetimlokh','qadosh_ata'))
    add('rh_qedushat_hashem',AMIDAH+'/qedushat_hashem','קדושת השם','Sanctification of God’s name',655,659,body)
    body=p('attah_vechartanu')+c('vattodienu',RUBRICS['vattodienu_rubric'],'<j:all>'+MAARIV+SATURDAY_NIGHT+'</j:all>',p('vattodienu'))
    body+=''.join(p(k) for k in ('vattitten_lanu','yaaleh_veyavo','melokh','kadsheinu'))
    add('rh_qedushat_hayom',AMIDAH+'/qedushat_hayom','קדושת היום','Sanctification of the day',659,661,body)
    group('avodah','עבודה','Temple service',661,661,['retzeh','vetechezeinah'])
    body=p('modim')+c('modim_derabbanan',RUBRICS['modim_derabbanan_rubric'],READER,p('modim_derabbanan'))+''.join(p(k) for k in ('veal_kullam','ukhtov','vekhol_hachayyim'))
    add('rh_hodaah',AMIDAH+'/hodaah','הודאה','Thanksgiving',663,663,body)
    group('shalom','שלום','Peace',663,663,['shalom_rav','besefer'])
    body=instruction(RUBRICS['amidah_rubric'])+c('ki_shem','At Minḥah:',MINCHAH,p('ki_shem'))+p('adonai_sefatai')
    body+=''.join(transclude(AMIDAH+'/'+k) for k in ('avot','gevurot','qedushat_hashem','qedushat_hayom','avodah','hodaah','shalom'))
    body+=c('meditation',RUBRICS['elohai_netzor_rubric'],READER,p('elohai_netzor'),negate=True)+p('yehi_ratzon_temple')
    add('rh_amidah',AMIDAH,'מִנְחָה וְעַרְבִית לְרֹאשׁ הַשָּׁנָה','MINḤAH AND MA‘ARIV FOR ROSH HASHANAH',655,665,body,True)
    add('rh_greeting',ROOT+'/greeting','ברכה לשנה החדשה','Rosh Hashanah Greeting',665,665,instruction(RUBRICS['greeting_rubric'])+p('greeting'),heading=False)
    body=c('vayekhulu',RUBRICS['vayekhulu_rubric'],SHABBAT,p('vayekhulu'))+p('savri')+p('wine')+p('kiddush')
    body+=c('havdalah',RUBRICS['havdalah_rubric'],SATURDAY_NIGHT,p('fire')+p('havdalah'))+p('shehecheyanu')
    body+=instruction(RUBRICS['apple_rubric'])+p('apple')
    add('rh_kiddush',KIDDUSH,'קִדּוּשׁ לְרֹאשׁ הַשָּׁנָה','KIDDUSH FOR ROSH HASHANAH',665,667,body,True)
    for key,num,first,last in [('psalm33',33,669,671),('psalm130',130,671,671)]:
        add('tashlikh_'+key,TASHLIKH+'/'+key,'תהלים '+('לג' if num==33 else 'קל'),'Psalm '+str(num),first,last,p(key),True)
    body=p('micah')+p('min_hametzar')+transclude(TASHLIKH+'/psalm33')+p('isaiah11_9')+transclude(TASHLIKH+'/psalm130')
    add('tashlikh',TASHLIKH,'תַּשְׁלִיךְ','TASHLIKH',669,671,body,True)
    add('tashlikh_service',ROOT+'/tashlikh','סדר תשליך','Tashlikh',669,671,c('tashlikh_day',RUBRICS['tashlikh_rubric'],TASHLIKH_DAY,transclude(TASHLIKH)),heading=False)
    row=next(r for r in ROWS if r['key']=='zeh_halifatenu')
    # One printed English rendering serves both genders of bird. Keep the
    # masculine/feminine Hebrew choice inside that common alignment segment.
    body=''
    if not side:
        for key,v in [('rooster',row['he']),('hen',row['he_feminine'])]:
            body+=c('bird_'+key,'With a '+key+':',object_condition(key),xml(v.removeprefix('(').removesuffix(')')))+' '
    else:body=xml(row['en'])
    add('kapparot_fowl',URNS['zeh_halifatenu'],'כפרות בעוף','Kapparot with a fowl',673,673,'<tei:p>'+body+'</tei:p>',heading=False)
    # The money clause is printed in the footnote. Only its English translation
    # is editorial, explicitly attributed, rather than silently ascribed to Birnbaum.
    if not side:
        v=row['he'];a=v.index('זֶה הַתַּרְנְ');b=v.index('וַאֲנַ',a)
        money=xml(v[:a]+'זֶה הַכֶּסֶף יִנָּתֵן לִצְדָקָה, '+v[b:])
    else:
        v=row['en'];money=xml(v).replace('This fowl shall meet death', '<tei:seg resp="urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein">This money shall be given to charity</tei:seg>')
    add('kapparot_money',KAPPAROT+'/money','כפרות בכסף','Kapparot with money',673,673,'<tei:p>'+money+'</tei:p>',heading=False)
    birds='<j:any>'+object_condition('rooster')+object_condition('hen')+'</j:any>'
    body=p('benei_adam')+c('fowl',RUBRICS['waving_rubric'],birds,transclude(KAPPAROT+'/fowl'))
    body+=c('money','When money is used in the Kapparoth ceremony:',object_condition('money'),transclude(KAPPAROT+'/money'))
    add('kapparot',KAPPAROT,'כַּפָּרוֹת','KAPPAROTH',673,673,body,True)
    add('kapparot_service',SIDDUR+'yom_kippur/kapparot','סדר כפרות','Kapparot',673,673,c('kapparot_day',RUBRICS['kapparot_rubric'],KAPPAROT_DAY,transclude(KAPPAROT)),heading=False)
    add('yom_kippur_candles',CANDLES,'הַדְלָקַת נֵר שֶׁל יוֹם הַכִּפּוּרִים','BLESSING OVER THE YOM KIPPUR LIGHTS',673,673,p('yk_candle_blessing')+p('yk_shehecheyanu'),True)
    body=c('rh_occasion','On Rosh Hashanah:',RH,cond('rh_amidah_service', fs='<j:any>'+MINCHAH+MAARIV+'</j:any>')+transclude(AMIDAH)+endcond('rh_amidah_service')
        +cond('rh_evening_greeting', fs=MAARIV)+transclude(ROOT+'/greeting')+endcond('rh_evening_greeting')
        +cond('rh_evening_kiddush', fs=MAARIV)+transclude(KIDDUSH)+endcond('rh_evening_kiddush'))
    body+=transclude(ROOT+'/tashlikh')+transclude(SIDDUR+'yom_kippur/kapparot')
    body+=c('yk_candles','Before Yom Kippur begins:','<j:all>'+date(7,9)+MINCHAH+'</j:all>',transclude(CANDLES))
    add('rh_rites',ROOT+'/minchah_maariv_and_rites','ראש השנה וערב יום הכיפורים','Rosh Hashanah and Erev Yom Kippur',655,673,body)
    return tuple(out)
