"""Shabbat and festival Mincha, printed 437–476; festival Amidah is a later installment."""
import re
from .common import PRAYER, SIDDUR, PROJECT_HE, SERVICE, AGG, RECITATION, feature, cond, endcond, pb
from .conclusion import instruction, transclude, text_xml, MINYAN, BIBLE, URNS as CONCLUSION
from .shacharit_end import editorial_head
from .milestones import marked, Correspondences
from .shared_passages import detach_division
from .shabbat_amidah import READER
from .shabbat_arvit import SHABBAT_AMIDAH, URNS as ARVIT
from .tachanun_conditions import date, holiday, ISRAEL, TACHANUN_OMITTED
from .avinu_malkenu import TEN_DAYS
from .torah import URNS as TORAH
from .minchah import SHALOM
from . import shabbat_minchah_data as data

ROOT = SIDDUR+'shabbat/minchah'
SIGIL = '1949 shabbat/minchah'
ATAH = PRAYER+'amidah/attah_echad'
SHABBAT = feature(AGG,'shabbat')
YOM_TOV = feature(AGG,'yom-tov')
WINTER = '<j:any>'+date(7,24,30)+'<j:all>'+date(7,23)+ISRAEL+'</j:all>'+''.join(date(m,1,30) for m in (8,9,10,11,12,13))+date(1,1,14)+'</j:any>'
WINTER_RUBRIC = 'The following psalms are recited on the Sabbaths between Sukkoth and Pesaḥ.'
TZIDKATKHA_RUBRIC = 'The following paragraph is omitted on occasions when the Taḥanun (page {page}) is omitted on weekdays.'


def conditional(cid,rubric,condition,body,*,negate=False):
    cid='shabbat_minchah_'+cid
    return cond(cid,note=rubric,fs=condition,negate=negate)+body+endcond(cid)


def shared(lang,prayers):
    side=int(lang=='en');result=[dict(p) for p in prayers];by_name={p['name']:p for p in result}
    # The weekday Kedushah owns a weekday gate. Detach the remaining common
    # sentences so Mincha can reuse them without inheriting that gate.
    for part in ('neqaddesh','leummatam','uvdivrei'):
        result.append(detach_division(by_name['amidah_qedushah'],PRAYER+'amidah/qedushah/'+part,
            'amidah_qedushah_'+part,first=83+side,last=83+side))
    ranges={'ashrei':(437,439),'conclusion_uva_letziyyon':(439,441),
      'minchah_ki_shem':(449,449),'amidah_adonai_sefatai':(449,449),'amidah_avot':(449,451),
      'amidah_gevurot':(451,451),'amidah_qedushat_hashem':(453,453),'shabbat_arvit_retzeh_text':(453,453),
      'amidah_avodah':(453,455),'yaaleh_veyavo':(453,455),'amidah_hodaah':(455,457),
      'amidah_hodaah_modim_derabbanan':(455,455),'amidah_hodaah_ukhtov':(457,457),
      'al_hanissim_chanukah':(457,457),'amidah_shalom_rav':(457,457),
      'amidah_shalom_hamevarekh':(457,457),'amidah_shalom_besefer_chayyim':(459,459),
      'amidah_elohai_netzor':(459,459),'amidah_yehi_ratzon':(459,459),
      'conclusion_titqabbal':(461,461),'conclusion_aleinu':(461,463),'conclusion_al_tira':(463,465)}
    for k in ('vayehi_binsoa','berikh_shemeh'):ranges['torah_'+k]=(443,443)
    for k in ('gaddelu','lekha_adonai','av_harachamim','vetiggaleh','veattem','barekhu','asher_bachar'):ranges['torah_'+k]=(445,445)
    for k in ('asher_natan','vezot_hatorah','yehalelu','psalm24'):ranges['torah_'+k]=(447,447)
    ranges['torah_uvnucho']=(449,449)
    for p in result:
        if p['name'] in ranges:
            a,b=ranges[p['name']];p['printings']=(*p.get('printings',()),(a+side,b+side))
        if p['name'].startswith('amidah_qedushah_'):
            a=453 if p['name'].endswith(('ledor_vador','hael_haqadosh','hamelekh_haqadosh')) else 451
            p['printings']=(*p.get('printings',()),(a+side,a+side))
        if p['name'] in ('kaddish_derabbanan_yitgaddal','kaddish_derabbanan_yehe_shemeh','kaddish_derabbanan_yitbarakh','kaddish_yatom'):
            p['printings']=(*p.get('printings',()),*((a+side,a+side) for a in (441,449,461,463)))
    turns = {
      'ashrei':(('פּוֹתֵחַ','Thou openest'),439),
      'amidah_avot':(('זָכְרֵנוּ','Remember us to life'),451),
      'conclusion_uva_letziyyon':(('צִדְקָתְךָ צֶדֶק','is eternal'),441),
      'yaaleh_veyavo':(('וְיִשָּׁמַע','of our fathers, of Messiah'),455),
      'conclusion_aleinu':(('עַל כֵּן נְקַוֶּה','We hope therefore'),463),
      'conclusion_al_tira':(('אֲנִי הוּא','same; when'),465),
    }
    for p in result:
        if p['name'] not in turns:continue
        anchors,page=turns[p['name']];anchor=anchors[side]
        pattern=''.join(re.escape(c)+'[\u05bd]*' for c in anchor)
        matches=list(re.finditer(pattern,p['body']))
        if len(matches)!=1:raise ValueError(f'Ambiguous Mincha page turn: {p["name"]}: {anchor}')
        i=matches[0].start();p['body']=p['body'][:i]+pb(page+side,sigil=SIGIL)+p['body'][i:]
    return result


def prayers(lang,earlier):
    side=int(lang=='en');result=[];seen=set(re.findall(r'corresp="([^"]+)"',''.join(p['body'] for p in earlier)))
    def add(key,urn,first,last,body,title=''):
        result.append(dict(name='shabbat_minchah_'+key+'_text',urn=urn,title=title or key.replace('_',' '),
          first=first+side,last=last+side,body=f'<tei:div corresp="{urn}">'+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    def paragraph(value):return '<tei:p>'+text_xml(value,SIGIL)+'</tei:p>'
    add('attah_echad',ATAH,453,453,paragraph(data.ATAH_ECHAD[side]),'Atah Eḥad')
    # Psalm 69:14 was quoted earlier but has no canonical realization yet.
    source=BIBLE+'psalms/69/14';urn=ROOT+'/vaani_tefillati'
    add('vaani',urn,443,443,'<tei:p>'+marked(source,text_xml(data.VAANI[side],SIGIL),unit='verse')+'</tei:p>')
    body='<tei:p>'
    for ref,he,en in data.TZIDKATKHA:
        source=BIBLE+ref;urn=source if source not in seen else ROOT+'/tzidqatekha/'+ref.replace('/','_')
        value=text_xml((he,en)[side],SIGIL)
        if urn!=source:value=f'<tei:seg source="{source}">'+value+'</tei:seg>'
        body+=marked(urn,value,unit='verse')+' ';seen.add(urn)
    add('tzidqatekha',ROOT+'/tzidqatekha',459,459,body+'</tei:p>','Tzidkatekha')
    for number,rows in data.PSALMS.items():
        first,last=data.PSALM_PAGES[number]
        urn=BIBLE+f'psalms/{number}' if number!=134 else ROOT+'/psalms/134'
        head=f'<tei:head xml:lang="{lang}">'+('תהלים '+{104:'קד',120:'קכ',121:'קכא',122:'קכב',123:'קכג',124:'קכד',125:'קכה',126:'קכו',127:'קכז',128:'קכח',129:'קכט',130:'קל',131:'קלא',132:'קלב',133:'קלג',134:'קלד'}[number] if not side else f'Psalm {number}')+'</tei:head>'
        body=head+'<tei:p>';marks=Correspondences()
        for verse,pair in enumerate(rows,1):
            value=pair[side]
            # Paragraphs follow the English printing, not verse boundaries.
            if '{p}' in value:
                value=value.replace('{p}','');body+=marks.close()+'</tei:p><tei:p>'
            source=BIBLE+f'psalms/{number}/{verse}'
            ref=source if source not in seen else ROOT+f'/psalms/{number}/{verse}'
            value=text_xml(value,SIGIL)
            if ref!=source:value=f'<tei:seg source="{source}">'+value+'</tei:seg>'
            body+=marks.start(ref,unit='verse')+value+' ';seen.add(ref)
        body+=marks.close()+'</tei:p>'
        add('psalm_'+str(number),urn,first,last,body,f'Psalm {number}')
    return result


def kaddish(full=False,mourner=False):
    value='' if mourner else instruction('Reader:')
    value+=''.join(transclude(PRAYER+'kaddish/'+k) for k in ('yitgaddal','yehe_shemeh','yitbarakh'))
    if full:value+=transclude(PRAYER+'kaddish/titqabbal')
    if full or mourner:value+=''.join(transclude(PRAYER+'kaddish/yatom/'+k) for k in ('yehe_shelama','oseh_shalom'))
    return value


def amidah(lang):
    tr=lambda k:transclude(PRAYER+'amidah/'+k)
    text=instruction('The Amidah is recited in silent devotion while standing, facing east.')+instruction('The Reader repeats the Amidah aloud when a minyan holds service.')
    text+=transclude(SIDDUR+'chol/minchah/ki_shem')+''.join(tr(k) for k in ('adonai_sefatai','avot','gevurot'))
    text+=conditional('qedushah','When the Reader repeats the Amidah, the following Kedushah is said:',READER,transclude(ROOT+'/amidah/qedushah'))
    text+=conditional('silent','In silent devotion:',READER,tr('qedushat_hashem'),negate=True)
    text+=transclude(ATAH)+transclude(ARVIT['retzeh'])+tr('avodah')
    text+=conditional('modim','When the Reader repeats the Amidah, the Congregation responds here by saying:',READER,transclude(ROOT+'/amidah/modim_derabbanan'))+transclude(ROOT+'/amidah/modim')
    text+=conditional('chanukah','On Ḥanukkah add:',holiday('hanukkah',8),transclude(ROOT+'/amidah/chanukah'))+tr('hodaah/veal_kullam')
    text+=conditional('ukhtov','Between Rosh Hashanah and Yom Kippur add:',TEN_DAYS,tr('hodaah/ukhtov'))+tr('hodaah/hatov_shimkha')
    text+=transclude(SHALOM)
    text+=conditional('peace_seal','Except during the Ten Days of Repentance:',TEN_DAYS,tr('shalom/hamevarekh'),negate=True)
    text+=conditional('peace_ten_days','Between Rosh Hashanah and Yom Kippur say:',TEN_DAYS,tr('shalom/besefer_chayyim'))
    text+=conditional('meditation','After the Amidah add the following meditation:',READER,tr('elohai_netzor/text'),negate=True)+tr('yehi_ratzon')
    return text


def units(project,by_name):
    lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');result=[]
    def add(key,he,en,first,last,content,printed=False):
        urn=ROOT+('/'+key if key else '')
        head=f'<tei:head xml:lang="{lang}">{(he,en)[side]}</tei:head>' if printed else editorial_head(lang,he,en)
        result.append(dict(name='shabbat_minchah'+('_'+key.replace('/','_') if key else ''),urn=urn,title_he=he,title_en=en,
          pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+head+pb(first+side,sigil=SIGIL)+content+'</tei:div>'))
    add('opening','אשרי ובא לציון','Ashrei and Uva Letzion',437,441,transclude(PRAYER+'ashrei')+transclude(ROOT+'/uva_letziyyon'))
    from .conclusion import ANCHORS
    from .conclusion_data import PASSAGES
    rows=PASSAGES['uva_letziyyon']['rows'];old=CONCLUSION['uva_letziyyon']
    def span(first,last):
        return f'<j:transclude type="external" target="{ANCHORS[old,first]}" targetEnd="{ANCHORS[old,last]}"/>'
    barukh=next(r for r in rows if r[0]=='barukh')
    value=barukh[2+side].replace('בָּרוּךְ יְיָ','בָּרוּךְ אֲדֹנָי')
    local='<tei:p>'+marked(ROOT+'/uva_letziyyon/barukh',f'<tei:seg source="{BIBLE}psalms/68/20">'+text_xml(value,SIGIL)+'</tei:seg>')+'</tei:p>'
    add('uva_letziyyon','ובא לציון','Uva Letzion',439,441,
        span(rows[0][0],'titten')+local+span('tzevaot',rows[-1][0]))
    for key,first,full,mourner in [('opening_kaddish',441,False,False),('torah_kaddish',449,False,False),('kaddish',461,True,False),('mourners_kaddish',463,False,True)]:
        he,en=('קדיש יתום','MOURNERS’ KADDISH') if mourner else ('קדיש שלם','Full Kaddish') if full else ('חצי קדיש','Half Kaddish')
        add(key,he,en,first,first,conditional(key,'When a minyan holds service:',MINYAN,kaddish(full,mourner)))
    text=instruction('The ark is opened.')+instruction('Reader and Congregation:')
    for key in ('vayehi_binsoa','berikh_shemeh'):text+=transclude(TORAH[key])
    text+=pb(445+side,sigil=SIGIL)+instruction('The Reader takes the Torah and says:')+transclude(TORAH['gaddelu'])+instruction('Congregation:')+transclude(TORAH['lekha_adonai'])
    text+=instruction('Reader:')+transclude(TORAH['av_harachamim'])
    text+=instruction('The Torah is placed on the desk. The Reader unrolls it and says:')+transclude(ROOT+'/torah/vetiggaleh')
    text+=instruction('Congregation and Reader:')+transclude(TORAH['veattem'])
    text+=instruction('The person called to the Torah recites:')+transclude(TORAH['barekhu'])
    text+=instruction('He repeats the response and continues:')+transclude(TORAH['asher_bachar'])
    text+=pb(447+side,sigil=SIGIL)+instruction('The Torah is read; then he recites:')+transclude(TORAH['asher_natan'])
    text+=instruction('When the Torah is raised, the Congregation recites:')+transclude(ROOT+'/torah/vezot_hatorah')
    text+=instruction('The Reader takes the Torah and says:')+transclude(TORAH['yehalelu'])+transclude(TORAH['psalm24'])
    text+=pb(449+side,sigil=SIGIL)+instruction('While the Torah is being placed in the ark:')+transclude(ROOT+'/torah/uvnucho')
    add('torah','קְרִיאַת הַתּוֹרָה','READING OF THE TORAH',443,449,text,True)
    # The Mincha call has no Psalm 19 / 29 / Deuteronomy 32 verses after Veatem.
    # Added below without a heading.
    from .torah_data import PASSAGES as TORAH_PASSAGES
    def passage_range(first,last):
        return f'<j:transclude type="external" target="{first}" targetEnd="{last}"/>'
    def variant(key,row_name,english):
        row=next(r for r in TORAH_PASSAGES[key]['rows'] if r[0]==row_name)
        value=text_xml((row[2],english)[side],SIGIL)
        urn=ROOT+'/torah/'+key+'/'+row_name
        return '<tei:p>'+marked(urn,f'<tei:seg source="{BIBLE+row[1]}">'+value+'</tei:seg>',unit='verse')+'</tei:p>'
    def unheaded(key,content,first,last):
        urn=ROOT+'/'+key
        result.append(dict(name='shabbat_minchah_'+key.replace('/','_'),urn=urn,title_he=key,title_en=key,
            pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+content+'</tei:div>'))
    unheaded('torah/vetiggaleh',passage_range(TORAH['vetiggaleh']+'/vetiggaleh',TORAH['vetiggaleh']+'/barukh'),445,445)
    unheaded('torah/vezot_hatorah',passage_range(BIBLE+'deuteronomy/4/44',BIBLE+'proverbs/3/16')+
        variant('vezot_hatorah','adonai_chafetz','The Lord is pleased, for the sake of his righteousness, to render the Torah great and glorious.'),447,447)
    unheaded('torah/uvnucho',passage_range(BIBLE+'numbers/10/36',BIBLE+'psalms/132/8')+
        variant('uvnucho','kohanekha','May thy priests be clothed in righteousness; may thy faithful followers shout for joy.')+
        transclude(BIBLE+'psalms/132/10')+
        variant('uvnucho','ki_leqach','I give you good instruction; forsake not my Torah.')+
        passage_range(TORAH['uvnucho']+'/etz',BIBLE+'lamentations/5/21'),449,449)
    ked=''.join(transclude(PRAYER+'amidah/qedushah/'+k) for k in ('neqaddesh','qadosh','leummatam','barukh_kevod','uvdivrei','yimlokh','ledor_vador'))
    for key,negate,rubric in [('hael_haqadosh',True,'Except during the Ten Days of Repentance:'),('hamelekh_haqadosh',False,'Between Rosh Hashanah and Yom Kippur say:')]:
        ked+=conditional('qedushah_'+key,rubric,TEN_DAYS,transclude(PRAYER+'amidah/qedushah/'+key),negate=negate)
    add('amidah/qedushah','קדושה','KEDUSHAH',451,453,ked)
    for key,source,page in [('modim',PRAYER+'amidah/hodaah/modim',455),('modim_derabbanan',PRAYER+'amidah/hodaah/modim_derabbanan',455),('chanukah',PRAYER+'al_hanissim/chanukah',457)]:
        # Occurrence anchors attach this printing's own commentary.
        urn=ROOT+'/amidah/'+key
        result.append(dict(name='shabbat_minchah_amidah_'+key,urn=urn,title_he=key,title_en=key,
            pages=(page+side,page+side),body=f'<tei:div corresp="{urn}">'+transclude(source)+'</tei:div>'))
    add('amidah','תפילת העמידה לשבת במנחה','AMIDAH',449,459,amidah(lang))
    add('aleinu','עלינו','ALENU',461,463,transclude(CONCLUSION['aleinu']))
    add('al_tira','אל תירא','Be not afraid',463,465,transclude(CONCLUSION['al_tira']))
    psalms=''.join(transclude(BIBLE+f'psalms/{n}' if n!=134 else ROOT+'/psalms/134') for n in data.PSALMS)
    add('psalms','מזמורים לשבתות החורף','Psalms for winter Sabbaths',465,475,psalms)
    svc=''.join(f'<tei:f name="{n}"><tei:binary value="{str(n=="minha").lower()}"/></tei:f>' for n in ('shaharit','minha','maariv','musaf','neila','slihot'))
    sequence=f'<j:declare xml:id="shabbat_minchah_service"><tei:fs type="{SERVICE}">{svc}</tei:fs></j:declare>'
    sequence+=transclude(ROOT+'/opening')+transclude(ROOT+'/opening_kaddish')
    sequence+=instruction(f'On festivals the Minḥah service is continued on page {585+side}.')
    sequence+=conditional('sabbath_torah','On Sabbaths:',SHABBAT,transclude(ROOT+'/vaani_tefillati')+conditional('torah_minyan','When a minyan holds service:',MINYAN,transclude(ROOT+'/torah'))+transclude(ROOT+'/torah_kaddish'))
    sequence+=conditional('sabbath_amidah','On the Sabbath, including Ḥol ha-Mo‘ed, but not Yom Tov:',SHABBAT_AMIDAH,transclude(ROOT+'/amidah'))
    sequence+=conditional('tzidqatekha',TZIDKATKHA_RUBRIC.format(page=103+side),'<j:none>'+YOM_TOV+TACHANUN_OMITTED+'<j:none>'+SHABBAT+'</j:none></j:none>',transclude(ROOT+'/tzidqatekha'))
    sequence+=''.join(transclude(ROOT+'/'+k) for k in ('kaddish','aleinu','mourners_kaddish','al_tira'))
    sequence+=conditional('winter_psalms',WINTER_RUBRIC,'<j:all>'+SHABBAT+WINTER+'</j:all>',transclude(ROOT+'/psalms'))
    sequence+='<j:endDeclare target="#shabbat_minchah_service"/>'
    add('','מִנְחָה לְשַׁבָּת וְיוֹם טוֹב','AFTERNOON SERVICE FOR SABBATHS AND FESTIVALS',437,475,sequence,True)
    return tuple(result)
