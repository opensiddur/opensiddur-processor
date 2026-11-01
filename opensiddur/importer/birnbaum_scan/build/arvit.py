"""Weekday Arvit, printed 189–220: service callers and reusable readings."""
import re
from .common import PRAYER, SIDDUR, PROJECT_HE, RECITATION, feature, cond, endcond, pb
from .conclusion import (transclude, instruction, text_xml, URNS as CONCLUSION,
                         MINYAN, ELUL_SEASON, SEASON_RUBRIC, MOURNING, MOURNING_RUBRIC)
from .tachanun_conditions import date, DIASPORA
from .avinu_malkenu import TEN_DAYS
from .milestones import marked
from .shared_passages import split_paragraph
from .arvit_data import (PSALM134, OPENING_VERSES, VEHU, MAARIV, AHAVAT, EMET,
                         HASHKIVENU, BARUKH_VERSES, BARUKH, CHONANTANU)

ROOT = SIDDUR+'chol/arvit'
BIBLE = 'urn:x-opensiddur:text:bible:'
SIGIL = '1949 chol/arvit'
SATURDAY_NIGHT = feature('opensiddur:day-of-week', 'hebrew-day', '<tei:numeric value="1"/>')
AFTER_MINCHA = feature('opensiddur:service-context', 'immediately-after-minha')
# These are the Hebrew dates of the night following the last festival day.
# Arvit's weekday caller already excludes a night that begins Shabbat or Yom Tov.
AFTER_FESTIVAL = ('<j:any>'+date(7,3)+date(7,11)
    + '<j:all><j:none>'+DIASPORA+'</j:none><j:any>'
    + date(1,16)+date(1,22)+date(3,7)+date(7,16)+date(7,23)+'</j:any></j:all>'
    + '<j:all>'+DIASPORA+'<j:any>'+date(1,17)+date(1,23)+date(3,8)+date(7,17)+date(7,24)
    + '</j:any></j:all></j:any>')
HAVDALAH = '<j:any>'+SATURDAY_NIGHT+AFTER_FESTIVAL+'</j:any>'
URNS = {'psalm134': BIBLE+'psalms/134', 'opening_verses': ROOT+'/opening/verses',
        'vehu': ROOT+'/shema/vehu_rachum', 'maariv': PRAYER+'maariv_aravim',
        'ahavat': PRAYER+'ahavat_olam_arvit', 'emet': PRAYER+'emet_veemunah',
        'hashkivenu': PRAYER+'hashkivenu', 'barukh': ROOT+'/barukh_adonai',
        'chonantanu': PRAYER+'amidah/attah_chonantanu'}
ANCHORS = {}


def conditional(cid, rubric, fs, content, *, negate=False):
    return '\n'.join([cond('arvit_'+cid, note=rubric, fs=fs, negate=negate), content, endcond('arvit_'+cid)])


def prayers(lang, earlier):
    side = int(lang=='en')
    seen = set(re.findall(r'corresp="([^"]+)"','\n'.join(p['body'] for p in earlier)))
    result = []
    def add(key, he, en, first, last, rows, *, biblical=False):
        urn = URNS[key]
        parts = ['<tei:p>']
        for ref, hebrew, english in rows:
            text = (hebrew,english)[side]
            if text.startswith('{p}'):
                parts.append('</tei:p><tei:p>')
                text=text[3:]
            if text.startswith('{reader}'):
                parts.append(instruction('Reader'))
                text=text[8:]
            value=text_xml(text,SIGIL)
            is_bible = biblical or bool(re.fullmatch(r'[a-z_0-9]+/\d+/\d+',ref))
            source=BIBLE+ref if is_bible else None
            target = source if source and source not in seen else urn+'/'+ref.replace('/','_')
            if source and source in seen:
                value=f'<tei:seg source="{source}">{value}</tei:seg>'
            quotes={'mi_khamokhah':'exodus/15/11','yimlokh':'exodus/15/18'} if key=='emet' else {}
            if ref in quotes:
                value=f'<tei:seg source="{BIBLE+quotes[ref]}">{value}</tei:seg>'
            parts.append(marked(target,value,unit='verse' if source else 'prayer-part')+' ')
            seen.add(target)
            ANCHORS[key,ref]=target
        parts.append('</tei:p>')
        heading = f'<tei:head xml:lang="{lang}">{(he,en)[side]}</tei:head>' if key=='psalm134' else ''
        result.append(dict(name='arvit_'+key,urn=urn,title=(he,en)[side],first=first+side,last=last+side,
            body=f'<tei:div corresp="{urn}">{heading}'+''.join(parts)+'</tei:div>'))
    add('psalm134','תהלים קלד','Psalm 134',189,189,PSALM134,biblical=True)
    add('opening_verses','יי צבאות עמנו','The Lord of hosts is with us',189,189,OPENING_VERSES,biblical=True)
    add('vehu','והוא רחום','He, being merciful',191,191,VEHU,biblical=True)
    add('maariv','המעריב ערבים','Who bringest on the evenings',191,191,MAARIV)
    add('ahavat','אהבת עולם','Everlasting love',191,191,AHAVAT)
    add('emet','אמת ואמונה','True and trustworthy',195,195,EMET)
    add('hashkivenu','השכיבנו','Grant that we lie down in peace',197,197,HASHKIVENU)
    # The collected verses and subsequent liturgical paragraphs remain one prayer;
    # biblical correspondence locations stay independent of the paragraph layout.
    add('barukh','ברוך יי לעולם','Blessed be the Lord forever',197,199,
        BARUKH_VERSES+[(r, ('{p}' if i==0 else '')+h, ('{p}' if i==0 else '')+e)
                       for i,(r,h,e) in enumerate(BARUKH)])
    add('chonantanu','אתה חוננתנו','Thou hast favored us',201,201,
        [('text',CHONANTANU['he'],CHONANTANU['en'])])
    return result


def shared(lang, prayers):
    result=[dict(p) for p in prayers]
    by_name={p['name']:p for p in result}
    p=by_name['amidah_binah']
    p['body']=split_paragraph(p['body'],PRAYER+'amidah/binah',
                             'חָנֵּֽנוּ' if lang=='he' else 'O grant us',suffix='conclusion')
    if lang=='he':
        boundary=f'<tei:milestone unit="prayer-part" corresp="{PRAYER}amidah/binah/conclusion"/>'
        # Printed (וְ)חָנֵּנוּ: the parentheses mark the prefix as Saturday night's. Joined
        # with nothing between, or the prefix would print as a word of its own.
        prefix=(cond('arvit_vechanenu', fs='<j:all>'+feature('opensiddur:service-time','maariv')
                     +HAVDALAH+'</j:all>', marked=True).strip()
                +'וְ'+endcond('arvit_vechanenu').strip())
        p['body']=p['body'].replace(boundary,boundary+prefix)
    from .arvit_printings import apply
    return apply(lang,result)


def kaddish(cid, *, full=False, mourner=False, lang='he'):
    text=[] if mourner else [instruction('Reader:')]
    text.extend(transclude(PRAYER+'kaddish/'+key) for key in ('yitgaddal','yehe_shemeh','yitbarakh'))
    if full:
        # The printed Saturday-night instruction redirects after Half Kaddish.
        rest=(pb(213+int(lang=='en'),sigil=SIGIL+'/kaddish')
              +transclude(PRAYER+'kaddish/titqabbal')
              +''.join(transclude(PRAYER+'kaddish/yatom/'+key) for key in ('yehe_shelama','oseh_shalom')))
        text.append(conditional(cid+'_completion','Except on Saturday night:',SATURDAY_NIGHT,rest,negate=True))
    elif mourner:
        text.extend(transclude(PRAYER+'kaddish/yatom/'+key) for key in ('yehe_shelama','oseh_shalom'))
    return conditional(cid,'When a minyan holds service:',MINYAN,'\n'.join(text))


def amidah(lang, by_name):
    from .build_he import ORDER
    parts=[instruction('The Shemoneh Esreh is recited in silent devotion while standing, facing east.')]
    for name in ORDER:
        if name in ('amidah_qedushah','amidah_birkat_kohanim'):
            continue
        if name=='amidah_binah':
            parts += [transclude(PRAYER+'amidah/binah/opening'),
                conditional('chonantanu','On the night following the Sabbath or any other holy day, add:',HAVDALAH,transclude(URNS['chonantanu']))]
            parts.append(transclude(PRAYER+'amidah/binah/conclusion'))
        elif name=='amidah_geullah':
            parts.append(transclude(PRAYER+'amidah/geullah/reeh_na'))
        elif name=='amidah_shalom':
            parts += [transclude(PRAYER+'amidah/shalom_rav_al'),
                conditional('peace_seal','Except during the Ten Days of Repentance:',TEN_DAYS,transclude(PRAYER+'amidah/shalom/hamevarekh'),negate=True),
                conditional('peace_ten_days','Between Rosh Hashanah and Yom Kippur say:',TEN_DAYS,transclude(PRAYER+'amidah/shalom/besefer_chayyim'))]
        else:
            parts.append(transclude(by_name[name]['urn']))
    return '\n'.join(parts)


def units(project, by_name):
    from .build_he import declaration
    from .shacharit_end import editorial_head
    lang='he' if project==PROJECT_HE else 'en'
    side=int(lang=='en')
    result=[]
    def unit(key,he,en,first,last,content,*,printed=False):
        urn=ROOT+('/'+key if key else '')
        title=f'<tei:head xml:lang="{lang}">{he if not side else en}</tei:head>' if printed else editorial_head(lang,he,en)
        # Arvit never has an Amidah repetition, even if a surrounding document is
        # configured to show a Reader's repetition for the daytime services.
        decl=declaration('maariv').replace('</j:declare>',
            f'<tei:fs type="{RECITATION}"><tei:f name="repetition"><tei:binary value="false"/></tei:f>'
            '<tei:f name="silent"><tei:binary value="true"/></tei:f></tei:fs></j:declare>')
        body=f'<tei:div corresp="{urn}">{title}'+decl+pb(first+side,sigil=SIGIL+('/'+key if key else ''))+content+'<j:endDeclare target="#unit_service"/></tei:div>'
        result.append(dict(name='chol_arvit'+('_'+key if key else ''),urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=body))
    opening=instruction(f'On Saturday night, Ma‘ariv is preceded by Psalms 144 and 67 (page {535+side}).')
    opening+=conditional('opening','On weekdays, if Ma‘ariv is not recited immediately after Minḥah, the evening service begins on this page.',
        '<j:none>'+AFTER_MINCHA+SATURDAY_NIGHT+'</j:none>',
        transclude(URNS['psalm134'])+transclude(URNS['opening_verses'])+kaddish('opening_kaddish'))
    unit('opening','פתיחה לערבית','Opening of the evening service',189,189,opening)
    before=(instruction('The Ma‘ariv service properly begins here.')+transclude(URNS['vehu'])
        +conditional('barekhu','When a minyan holds service:',MINYAN,transclude(PRAYER+'barekhu'))
        +transclude(URNS['maariv'])+transclude(URNS['ahavat']))
    unit('blessings_before_shema','ברכות לפני קריאת שמע','Blessings before Shema',191,191,before)
    unit('shema','קריאת שמע','Shema',193,195,transclude(PRAYER+'shema'))
    unit('blessings_after_shema','ברכות לאחר קריאת שמע','Blessings after Shema',195,199,
         ''.join(transclude(URNS[k]) for k in ('emet','hashkivenu','barukh'))+kaddish('before_amidah'))
    unit('amidah','תפילת העמידה','SHEMONEH ESREH',199,211,amidah(lang,by_name))
    unit('kaddish','קדיש לאחר העמידה','Kaddish after the Amidah',211,213,
         instruction(f'On Saturday night, after the recital of half-Kaddish, Ma‘ariv is continued on page {537+side}.')+kaddish('after_amidah',full=True,lang=lang))
    conclusion=instruction(f'The counting of the omer between Pesaḥ and Shavuoth is on page {637+side}.')+transclude(CONCLUSION['aleinu'])
    conclusion+='<tei:div>'+editorial_head(lang,'קדיש יתום','MOURNERS’ KADDISH')+kaddish('after_alenu',mourner=True)+'</tei:div>'+transclude(CONCLUSION['al_tira'])
    unit('conclusion','עלינו וסיום התפילה','Alenu and conclusion',213,215,conclusion)
    unit('psalm27','לדוד יי אורי','Psalm 27 for the season of repentance',215,217,
        conditional('psalm27',SEASON_RUBRIC,ELUL_SEASON,transclude(CONCLUSION['psalm_27'])+kaddish('after_psalm27',mourner=True)))
    unit('mourning','מזמור בבית האבל','Psalm in the house of mourning',217,219,
        conditional('mourning',MOURNING_RUBRIC,MOURNING,transclude(CONCLUSION['psalm_49'])+kaddish('after_psalm49',mourner=True)))
    unit('','תְּפִלַּת עַרְבִית','EVENING SERVICE',189,219,''.join(transclude(u['urn']) for u in result),printed=True)
    return tuple(result)
