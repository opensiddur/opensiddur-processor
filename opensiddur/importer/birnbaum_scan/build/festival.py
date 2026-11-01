"""Eruv Tavshilin, festival candles, Amidah and Kiddush (IA n609–n624)."""
import re
from .common import PRAYER, SIDDUR, PROJECT_HE, SERVICE, AGG, feature, cond, endcond, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .shabbat_amidah import READER
from .shabbat_arvit import SHABBAT, REGALIM
from .tachanun_conditions import holiday, ISRAEL, DIASPORA
from .shacharit_end import editorial_head
from .milestones import marked
from .festival_data import ROWS, PAGES

ROOT = SIDDUR+'regalim'
AMIDAH = ROOT+'/amidah'
SIGIL = '1949 regalim'
SHACHARIT = feature(SERVICE,'shaharit')
MINCHAH = feature(SERVICE,'minha')
MAARIV = feature(SERVICE,'maariv')
SATURDAY_NIGHT = feature(AGG,'motzaei-shabbat')
IN_SUKKAH = feature('opensiddur:practice','in-sukkah')
HOLIDAYS = [('pesach','Pesaḥ','pesah',8), ('shavuot','Shavuoth','shavuot',2),
            ('sukkot','Sukkoth','sukkot',7), ('shemini','Shemini Atsereth and Simḥath Torah','shmini-atzeret',2)]
# The new festival's first night in Israel, first two nights in the diaspora.
# The last days of Pesach are excluded; Shemini Atzeret is a new festival.
FIRST_NIGHTS = '<j:any>'+''.join(
    '<j:all>'+place+'<j:any>'+''.join(holiday(name,last) for name in ('pesah','shavuot','sukkot','shmini-atzeret'))+'</j:any></j:all>'
    for place,last in ((ISRAEL,1),(DIASPORA,2)))+'</j:any>'
REUSE = {'sefatai': 'urn:x-opensiddur:text:prayer:amidah/adonai_sefatai',
 'avot': 'urn:x-opensiddur:text:prayer:amidah/avot/barukh_attah',
 'melekh': 'urn:x-opensiddur:text:prayer:amidah/avot/magen_avraham',
 'gevurot': 'urn:x-opensiddur:text:prayer:amidah/gevurot/attah_gibbor',
 'mekhalkel': 'urn:x-opensiddur:text:prayer:amidah/gevurot/mekhalkel_chayyim',
 'veneeman': 'urn:x-opensiddur:text:prayer:amidah/gevurot/mechayyeh_hametim',
 'neqaddesh_shacharit': 'urn:x-opensiddur:text:siddur:shabbat/shacharit/amidah/qedushah/neqaddesh',
 'qadosh_shacharit': 'urn:x-opensiddur:text:prayer:amidah/qedushah/qadosh',
 'barukh_shacharit': 'urn:x-opensiddur:text:prayer:amidah/qedushah/barukh_kevod',
 'yimlokh_shacharit': 'urn:x-opensiddur:text:prayer:amidah/qedushah/yimlokh',
 'neqaddesh_minchah': 'urn:x-opensiddur:text:siddur:shabbat/shacharit/amidah/qedushah/neqaddesh',
 'qadosh_minchah': 'urn:x-opensiddur:text:prayer:amidah/qedushah/qadosh',
 'leummatam': 'urn:x-opensiddur:text:prayer:amidah/qedushah/leummatam',
 'barukh_minchah': 'urn:x-opensiddur:text:prayer:amidah/qedushah/barukh_kevod',
 'uvedivrei': 'urn:x-opensiddur:text:prayer:amidah/qedushah/uvedivrei',
 'vetechezeinah': 'urn:x-opensiddur:text:prayer:amidah/avodah/vetechezeinah',
 'veal_kullam': 'urn:x-opensiddur:text:prayer:amidah/hodaah/veal_kullam',
 'hatov': 'urn:x-opensiddur:text:prayer:amidah/hodaah/hatov_shimkha',
 'wine': 'urn:x-opensiddur:text:prayer:borei_peri_hagafen'}
# Unique liturgical paragraphs have prayer addresses; edition-specific variants
# retain local addresses and point to the common passage using source.
UNIQUE = {'eruv_blessing':PRAYER+'eruv_tavshilin/blessing',
          'eruv_declaration':PRAYER+'eruv_tavshilin/declaration',
          'candles':PRAYER+'hadlaqat_ner_yom_tov',
          'shehecheyanu':PRAYER+'shehecheyanu',
          'attah_vechartanu':PRAYER+'amidah/attah_vechartanu_mikol',
          'vattodienu':PRAYER+'amidah/vattodienu',
          'vehasi':PRAYER+'amidah/vehassienu_hashem_eloheinu',
          'havdalah':PRAYER+'hamavdil_bein_qodesh_leqodesh',
          'sukkah':PRAYER+'leshev_basukkah'}
SOURCES = {'ki_shem':BIBLE+'deuteronomy/32/3','rain':PRAYER+'amidah/gevurot/mashiv_haruach',
 'az':PRAYER+'amidah/az_beqol_raash','mimeqomekha':PRAYER+'amidah/mimeqomekha_malkenu_tofia',
 'yimlokh_minchah':BIBLE+'psalms/146/10','ledor':PRAYER+'amidah/qedushah/ledor_vador',
 'attah_qadosh':PRAYER+'amidah/qedushat_hashem','yaaleh':PRAYER+'yaaleh_veyavo',
 'retzeh':PRAYER+'amidah/avodah/retzeh','modim':PRAYER+'amidah/hodaah/modim',
 'modim_derabbanan':PRAYER+'amidah/hodaah/modim_derabbanan','kohanim':PRAYER+'amidah/birkat_kohanim',
 'sim_shalom':PRAYER+'amidah/shalom','shalom_rav':PRAYER+'amidah/shalom_rav_al',
 'elohai':PRAYER+'amidah/elohai_netzor/text','yehi':PRAYER+'amidah/yehi_ratzon',
 'vayehi':BIBLE+'genesis/1/31'}
URNS = {r['key']:REUSE.get(r['key'],UNIQUE.get(r['key'],ROOT+'/text/'+r['key'])) for r in ROWS}
URNS['kiddush_shehecheyanu'] = URNS['shehecheyanu']


def conditional(key,rubric,condition,body,*,negate=False):
    cid='festival_'+key
    return cond(cid,note=rubric,fs=condition,negate=negate).strip()+body+endcond(cid).strip()


def shared(lang,prayers):
    side=int(lang=='en');result=[dict(p) for p in prayers]
    for p in result:
        pages={r['page']+side for r in ROWS if r['key'] in REUSE and
               ('corresp="'+REUSE[r['key']]+'"') in p['body']}
        p['printings']=(*p.get('printings',()),*((page,page) for page in sorted(pages)))
    # A reference into a larger conditional document also inherits surrounding
    # rubrics. Move reused leaf divisions to independent files, leaving the
    # original callers and their conditions in place.
    from .shared_passages import detach_division
    detached=[]
    for urn in dict.fromkeys(REUSE.values()):
        for p in result:
            if p['urn']==urn:continue
            if '<tei:div corresp="'+urn+'">' not in p['body']:continue
            key=next(k for k,u in REUSE.items() if u==urn)
            detached.append(detach_division(p,urn,'festival_shared_'+key))
            break
    return result+detached


def prayers(lang):
    side=int(lang=='en');result=[]
    for row in ROWS:
        key=row['key']
        if key in REUSE or key=='kiddush_shehecheyanu':continue
        raw=row[lang]
        if key in ('ki_shem','rain','vattodienu','modim_derabbanan','vayehi','vaykhulu'):
            raw=raw.removeprefix('(').removesuffix(')')
        value=text_xml(raw,SIGIL).replace('\n','<tei:lb/>')
        # Every remaining parenthesis in these paragraphs is a Sabbath addition.
        if key in ('candles','vattitten','miqra','vehasi','kiddush_open','kiddush_close'):
            n=iter(range(20))
            value=re.sub(r'\(([^()]*)\)',lambda m:conditional(key+'_shabbat_'+str(next(n)),
                'On the Sabbath:',SHABBAT,m[1]),value)
        if key in SOURCES:value=f'<tei:seg source="{SOURCES[key]}">'+value+'</tei:seg>'
        if key=='vaykhulu':
            # The opening is the end of Genesis 1:31; the three complete following
            # verses have biblical source addresses, with this occurrence local.
            chunks=re.split(r'(?<=\.) ',value)
            if len(chunks)!=4:raise ValueError('Expected Genesis 1:31 tail and 2:1–3')
            value=' '.join(marked(ROOT+'/kiddush/genesis/'+v,
                f'<tei:seg source="{BIBLE}genesis/{v}">'+s+'</tei:seg>',unit='verse')
                for v,s in zip(('1/31','2/1','2/2','2/3'),chunks))
        urn=URNS[key];last=max([row['page']+side]+[int(x) for x in re.findall(r'\{pb:(\d+)\}',raw)])
        body=(f'<tei:div corresp="{urn}">'+pb(row['page']+side,sigil=SIGIL)+'<tei:p>'+value+'</tei:p></tei:div>') if key in UNIQUE else '<tei:p>'+pb(row['page']+side,sigil=SIGIL)+marked(urn,value)+'</tei:p>'
        result.append(dict(name='festival_'+key+'_text',urn=urn,title=key.replace('_',' '),
            first=row['page']+side,last=last,body=body,
            printings=((599+side,599+side),) if key=='shehecheyanu' else ()))
    return result


def units(project):
    side=int(project!=PROJECT_HE);lang=('he','en')[side];result=[]
    def p(key):return transclude(URNS[key])
    def add(key,he,en,first,last,body,*,printed=False,english_head=False):
        urn=ROOT+('/'+key if key else '')
        head=(f'<tei:head xml:lang="{("en" if english_head else lang)}">'+(en if english_head else (he,en)[side])+'</tei:head>') if printed else editorial_head(lang,he,en)
        result.append(dict(name='festival'+('_'+key.replace('/','_') if key else ''),urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+head+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    add('eruv_tavshilin','עֵרוּב תַּבְשִׁילִין','ERUV TAVSHILIN',585,585,
        instruction(PAGES['585']['items'][0]['text'])+p('eruv_blessing')+p('eruv_declaration'),printed=True)
    add('candles','הַדְלָקַת נֵר שֶׁל יוֹם טוֹב','LIGHTING THE FESTIVAL LIGHTS',585,585,p('candles')+
        conditional('candles_shehecheyanu','On the first night add:',FIRST_NIGHTS,p('shehecheyanu')),printed=True)
    for service,keys in [('shacharit',('neqaddesh_shacharit','qadosh_shacharit','az','barukh_shacharit','mimeqomekha','yimlokh_shacharit')),
                         ('minchah',('neqaddesh_minchah','qadosh_minchah','leummatam','barukh_minchah','uvedivrei','yimlokh_minchah'))]:
        page=587 if service=='shacharit' else 589
        add('amidah/qedushah/'+service,'קדושה',('KEDUSHAH FOR SHAḤARITH' if service=='shacharit' else 'KEDUSHAH FOR MINḤAH'),page,page,
            ''.join(p(k) for k in keys),printed=True,english_head=True)
    def alternatives(prefix):
        return ''.join(conditional(prefix+'_'+key,label,holiday(name,last),p(prefix+'_'+key)) for key,label,name,last in HOLIDAYS)
    middle=p('attah_vechartanu')+conditional('vattodienu','On Saturday night:',
        '<j:all>'+MAARIV+SATURDAY_NIGHT+'</j:all>',p('vattodienu'))
    middle+=p('vattitten')+alternatives('amidah')+p('miqra')+p('yaaleh')+alternatives('yaaleh')+p('zokhrenu')+p('vehasi')
    add('amidah/qedushat_hayom','קדושת היום','Sanctification of the festival',589,593,middle)
    body=instruction('The Amidah is recited in silent devotion while standing, facing east.')
    body+=conditional('ki_shem','At Minḥah:',MINCHAH,p('ki_shem'))+''.join(p(k) for k in ('sefatai','avot','melekh','gevurot'))
    body+=conditional('rain',PAGES['587']['items'][0]['text'],feature(AGG,'geshem'),p('rain'))+p('mekhalkel')+p('veneeman')
    for svc,expr in [('shacharit',SHACHARIT),('minchah',MINCHAH)]:
        body+=conditional('qedushah_'+svc,'During the Reader’s repetition at '+('Shaḥarith:' if svc=='shacharit' else 'Minḥah:'),
            '<j:all>'+READER+expr+'</j:all>',transclude(AMIDAH+'/qedushah/'+svc))
    body+=conditional('ledor','Reader:',READER,p('ledor'))
    body+=conditional('silent','In silent devotion:',READER,p('attah_qadosh'),negate=True)
    body+=transclude(AMIDAH+'/qedushat_hayom')+p('retzeh')+p('vetechezeinah')
    body+=conditional('modim','When the Reader repeats the Amidah, the Congregation responds here by saying:',READER,p('modim_derabbanan'))+p('modim')+p('veal_kullam')+p('hatov')
    body+=conditional('kohanim','Priestly blessing recited by the Reader:', '<j:all>'+READER+SHACHARIT+'</j:all>',p('kohanim'))
    body+=conditional('sim_shalom','For Shaḥarith:',SHACHARIT,p('sim_shalom'))
    body+=conditional('shalom_rav','For Minḥah and Ma‘ariv:','<j:any>'+MINCHAH+MAARIV+'</j:any>',p('shalom_rav'))
    body+=conditional('meditation','After the Amidah add the following meditation:',READER,p('elohai'),negate=True)+p('yehi')
    # This reusable Amidah is intrinsically Yom Tov. Declare that context so
    # inherited weekday-only commentary does not appear in an undated proof.
    body='<j:declare xml:id="festival_amidah_context">'+feature(AGG,'yom-tov')+'</j:declare>'+body+'<j:endDeclare target="#festival_amidah_context"/>'
    add('amidah','עֲמִידָה לְשָׁלֹשׁ רְגָלִים','AMIDAH FOR FESTIVALS',585,597,body,printed=True)
    body=conditional('vaykhulu','On Sabbath Eve:',SHABBAT,p('vayehi')+p('vaykhulu'))+p('savri')+p('wine')+p('kiddush_open')+alternatives('kiddush')+p('kiddush_close')
    body+=conditional('havdalah','On Saturday night add:',SATURDAY_NIGHT,p('fire')+p('havdalah'))
    last_pesach=feature('opensiddur:holiday','pesah','<tei:numeric value="7" max="8"/>')
    body+=conditional('kiddush_shehecheyanu','On the last two nights of Pesaḥ omit:',last_pesach,p('shehecheyanu'),negate=True)
    body+=conditional('sukkah','In the Sukkah:','<j:all>'+holiday('sukkot',7)+IN_SUKKAH+'</j:all>',p('sukkah'))
    add('kiddush','קִדּוּשׁ לְשָׁלֹשׁ רְגָלִים','KIDDUSH FOR FESTIVALS',597,599,body,printed=True)
    body=conditional('eruv_occasion','',feature(AGG,'eruv-tavshilin'),transclude(ROOT+'/eruv_tavshilin'))
    body+=conditional('festival_occasion','On festivals:',REGALIM,
        cond('festival_evening_candles', fs='<j:any>'+MINCHAH+MAARIV+'</j:any>')+transclude(ROOT+'/candles')+endcond('festival_evening_candles')
        +transclude(ROOT+'/amidah')+cond('festival_evening_kiddush', fs=MAARIV)+transclude(ROOT+'/kiddush')+endcond('festival_evening_kiddush'))
    add('','שלש רגלים','Three Pilgrimage Festivals',585,599,body)
    return tuple(result)


def extend_services(units_):
    """Insert the festival Amidah before the common post-Amidah return points."""
    result=[dict(u) for u in units_]
    markers={SIDDUR+'shabbat/shacharit':'shabbat_amidah_sabbath',
             SIDDUR+'shabbat/arvit':'shabbat_arvit_sabbath_amidah',
             SIDDUR+'shabbat/minchah':'shabbat_minchah_sabbath_amidah'}
    for u in result:
        if u['urn'] not in markers:continue
        marker='<j:endConditional target="#'+markers[u['urn']]+'"/>'
        if u['body'].count(marker)!=1:raise ValueError('Expected Sabbath Amidah gate in '+u['urn'])
        u['body']=u['body'].replace(marker,marker+conditional('service_amidah','On festivals:',REGALIM,transclude(AMIDAH)))
    return tuple(result)
