"""Saturday-night additions and Birkat Halevanah, printed535–566."""
from html import escape
import re
from .common import SIDDUR, PRAYER, POEM, PROJECT_HE, AGG, feature, pb
from .conclusion import BIBLE, MINYAN, instruction, transclude, text_xml
from .milestones import marked
from .shabbat_minchah import conditional, kaddish
from .shacharit_end import editorial_head
from .tachanun_conditions import holiday
from .motzaei_data import READINGS

ROOT = SIDDUR+'shabbat/conclusion'
LEVANAH = SIDDUR+'berakhot/birkat_halevanah'
SIGIL = '1949 shabbat/conclusion'
FS = 'opensiddur:motzaei-shabbat'
NO_FESTIVAL = '<j:none>'+feature(FS,'omit-vihi-noam')+'</j:none>'
POEMS = ('hamavdil_bein_qodesh_lechol','bemotzaei_yom_menuchah','bemotzaei_yom_gilah','amar_adonai_leyaaqov')


def reading(page,key):
    values=READINGS[str(page)]['text']
    return dict(values)[key] if isinstance(key,str) else values[key]


def xml(text):
    value=text_xml(text,SIGIL).replace(' | ',' ').replace('\\n','<tei:lb/>').replace('\n','<tei:lb/>')
    value=re.sub(r'\{q:([^}]+)\}',lambda m:'<tei:seg source="'+BIBLE+m[1]+'">',value)
    return value.replace('{/q}','</tei:seg>')


def paragraph(urn,text,*,source=None,unit='prayer-part'):
    value=xml(text)
    if source:value=f'<tei:seg source="{source}">'+value+'</tei:seg>'
    return '<tei:p>'+marked(urn,value,unit=unit)+'</tei:p>'


def psalm(number,value,lang,urn,seen):
    from .motzaei_refs import PSALMS, split
    he,en=PSALMS[number]
    boundaries=[(BIBLE+f'psalms/{number}/{i}',h,e) for i,(h,e) in enumerate(zip(he,en),1)]
    parts=[]
    for source,text in split(value,boundaries,lang):
        ref=source if source not in seen else urn+'/'+source.rsplit('/',1)[1]
        parts.append(marked(ref,('<tei:seg source="'+source+'">'+xml(text)+'</tei:seg>') if ref!=source else xml(text),unit='verse'))
        seen.add(ref)
    return '<tei:p>'+' '.join(parts)+'</tei:p>'


def shared(lang,prayers):
    result=[dict(p) for p in prayers];page=541+int(lang=='en')
    references={PRAYER+'kaddish/'+k for k in ('yitgaddal','yehe_shemeh','yatom/yehe_shelama','yatom/oseh_shalom')}
    for p in result:
        if p['urn'] in references:p['printings']=(*p.get('printings',()),(page,page))
    return result


def prayers(lang,earlier):
    side=int(lang=='en');result=[]
    def add(key,urn,first,last,body,he,en):
        result.append(dict(name='motzaei_'+key+'_text',urn=urn,title=(he,en)[side],
            first=first+side,last=last+side,body=f'<tei:div corresp="{urn}">'+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    seen=set(re.findall(r'corresp="([^"]+)"',''.join(p['body'] for p in earlier)))
    for number in (144,67):
        add('psalm'+str(number),BIBLE+'psalms/'+str(number),535,535,
            psalm(number,reading(535+side,'psalm'+str(number)),lang,ROOT+'/psalm'+str(number),seen),'תהלים '+str(number),'Psalm '+str(number))
    for key,first,count,he,en in [
        (POEMS[0],553,9,'המבדיל בין קדש לחול','Ha-mavdil'),
        (POEMS[1],555,10,'במוצאי יום מנוחה','At the close of the day of rest')]:
        urn=POEM+key;body=''
        for i in range(count):
            value=reading(first+side,i) if side else '\n'.join(READINGS[str(first)]['text'][i*2:i*2+2])
            body+=paragraph(urn+'/'+str(i+1),value,unit='stanza')
        if side and key==POEMS[0]:body='<tei:head xml:lang="en">HA-MAVDIL</tei:head>'+body
        add(("hymn_"+key) if key==POEMS[0] else key,urn,first,first,body,he,en)
    urn=POEM+POEMS[2]
    add(POEMS[2],urn,557,557,paragraph(urn+'/1',reading(557+side,0),unit='stanza'),'במוצאי יום גילה','At the close of the joyous day')
    urn=POEM+POEMS[3];body=''
    for i in range(22):
        if i<16:value=reading(557+side,i+1)
        else:
            if i==16:body+=pb(559+side,sigil=SIGIL)
            value=READINGS['560']['text_en'][i-16] if side else reading(559,i-16)
        body+=paragraph(urn+'/'+str(i+1),value,unit='stanza')
    add(POEMS[3],urn,557,559,body,'אמר יי ליעקב','The Lord says to Jacob')
    # An empty English realization preserves the edition's untranslated pages.
    # The prayers continue across an even page; their page sigils stay Hebrew.
    for key,he,en,value in [
        ('ribbon_haolamim','רבון העולמים','Master of the universe',reading(559,6)),
        ('ufetach_lanu','ופתח לנו','Open for us',reading(559,7)+' {pb:560}'+READINGS['560']['text_he'][0]+' {pb:561}'+READINGS['561']['continuation'])]:
        urn=PRAYER+key
        add(key,urn,559,561,paragraph(urn+'/text',value) if not side else '',he,en)
    # Distinct blessings have their own reusable prayer addresses.
    for key,idx,he,en in [
        ('borei_minei_vesamim',3,'בורא מיני בשמים','Blessing over spices'),
        ('borei_meorei_haesh',4,'בורא מאורי האש','Blessing over fire'),
        ('hamavdil_bein_qodesh_lechol',5,'המבדיל בין קדש לחול','Blessing of separation')]:
        urn=PRAYER+key
        add(key,urn,551,551,'<tei:p>'+xml(reading(551+side,idx-side))+'</tei:p>',he,en)
    return result


def units(project,by_name):
    lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');result=[]
    seen=set(re.findall(r'corresp="([^"]+)"',''.join(p['body'] for p in by_name.values())))
    def add(key,he,en,first,last,content,*,root=ROOT,printed=False):
        urn=root+('/'+key if key else '')
        head=f'<tei:head xml:lang="{lang}">{escape((he,en)[side])}</tei:head>' if printed else editorial_head(lang,he,en)
        result.append(dict(name=('birkat_halevanah' if root==LEVANAH else 'motzaei_shabbat')+('_'+key if key else ''),
            urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),
            body=f'<tei:div corresp="{urn}">'+head+pb(first+side,sigil=SIGIL)+content+'</tei:div>'))
    def passage(key,text,source=None,root=ROOT):
        return paragraph(root+'/'+key,text,source=source)
    # These Psalm occurrences retain the text/translation of their own printing.
    for number,page in [(144,535),(67,535),(91,537),(128,549)]:
        key='psalm'+str(number)
        value=reading(page+side,key)
        add(key,'תהלים '+{144:'קמד',67:'סז',91:'צא',128:'קכח'}[number],'Psalm '+str(number),page,page,
            transclude(BIBLE+'psalms/'+str(number)) if number in (144,67) else psalm(number,value,lang,ROOT+'/'+key,seen),printed=True)
    add('opening','למוצאי שבת','Before the evening service',535,535,
        instruction(READINGS[str(535+side)]['rubrics'][0])+transclude(ROOT+'/psalm144')+transclude(ROOT+'/psalm67'))
    vihi=passage('vihi_noam/text',reading(537+side,'vihi_noam'),BIBLE+'psalms/90/17')+transclude(ROOT+'/psalm91')
    if not side:vihi+=passage('vihi_noam/repeat',reading(537,'repeat91_16'),BIBLE+'psalms/91/16')
    add('vihi_noam','ויהי נעם','Vihi Noam',537,537,vihi)
    value=reading(537+side,'veattah_qadosh')+' {pb:'+str(539+side)+'} '
    if side:value+=' '.join(t for k,t in READINGS['540']['text'])
    else:value+=reading(539,'veattah_qadosh_cont')
    from .motzaei_refs import split
    from .conclusion_data import PASSAGES
    from .conclusion import URNS as CONCLUSION
    bounds=[]
    for key,ref,he,en in PASSAGES['uva_letziyyon']['rows'][2:]:
        he=re.sub(r'\{[^}]+\}', '', he);en=re.sub(r'\{[^}]+\}', '', en)
        he=' '.join(he.split()[:2]);en=' '.join(en.split()[:4])
        if key=='lemaan':en='May my soul sing'
        if key=='targum_qadosh':he='וּמְקַבְּלִין'
        bounds.append((key,he,en))
    body=''
    for (key,value),(_,ref,_,_) in zip(split(value,bounds,lang),PASSAGES['uva_letziyyon']['rows'][2:]):
        source=(BIBLE+ref) if ref and not key.startswith('targum') else CONCLUSION['uva_letziyyon']+'/'+key
        value=value.replace('*','')
        encoded=xml(value)
        if key.startswith('targum'):
            encoded=('<tei:hi rend="italic">'+encoded+'</tei:hi>') if side else '<tei:foreign xml:lang="arc-Hebr">'+encoded+'</tei:foreign>'
        body+='<tei:p>'+marked(ROOT+'/veattah_qadosh/'+key,'<tei:seg source="'+source+'">'+encoded+'</tei:seg>',unit='verse' if ref and not key.startswith('targum') else 'prayer-part')+'</tei:p>'
    add('veattah_qadosh','ואתה קדוש','Veatah Kadosh',537,539,body)
    addition=conditional('motzaei_vihi','Except on Tish‘ah b’Av:',holiday('tisha-bav'),transclude(ROOT+'/vihi_noam'),negate=True)
    addition+=transclude(ROOT+'/veattah_qadosh')
    add('after_amidah','תוספות לאחר העמידה','Additions after the Amidah',537,539,
        conditional('motzaei_week','Unless Yom Tov occurs Sunday–Friday of the coming week:',NO_FESTIVAL,addition))
    # This printing has its own punctuation and Titkabal vowel/translation.
    from .avinu_malkenu import TEN_DAYS
    printed_kaddish = kaddish(full=True)
    for part, index in [('yitbarakh', 2), ('titqabbal', 3)]:
        value = reading(542, 'kaddish'+str(index+1)) if side else reading(541, 'kaddish').splitlines()[index]
        variant = passage('kaddish/'+part, value, PRAYER+'kaddish/'+part)
        if not side and part == 'yitbarakh':
            variant = variant.replace('(לְעֵֽלָּא)', conditional(
                'motzaei_second_leella', 'During the Ten Days of Repentance, add:',
                TEN_DAYS, xml('לְעֵֽלָּא')))
        printed_kaddish = printed_kaddish.replace(transclude(PRAYER+'kaddish/'+part), variant)
    add('kaddish','קדיש שלם','Full Kaddish',541,541,
        conditional('motzaei_full_kaddish','When a minyan holds service:',MINYAN,printed_kaddish))
    # Biblical blessing anthology: page boundaries remain inside continued paragraphs.
    from .motzaei_refs import VEYITTEN, split
    value=''
    for page in range(541+side,551+side,2):
        if page>541+side:value+=' {pb:'+str(page)+'} '
        value+=' '.join(text for key,text in READINGS[str(page)]['text']
                        if not key.startswith('kaddish') and key!='psalm128')+' '
    body=''
    for source,value in split(value,VEYITTEN,lang):
        if ':talmud:' in source:
            from .motzaei_refs import megillah_quotes
            value=megillah_quotes(value,lang)
            body+=f'<tei:note type="instruction" xml:lang="{lang}">'+('Talmud Megillah 31a' if side else 'מסכת מגילה לא, א')+'</tei:note>'
        urn=source if source not in seen else ROOT+'/veyitten_lekha/'+source.split(':')[-1]
        body+=paragraph(urn,value,source=source if urn!=source else None,
                        unit='verse' if ':bible:' in source else 'prayer-part')
        seen.add(urn)
    body+=transclude(ROOT+'/psalm128')
    add('veyitten_lekha','ויתן לך','Veyitten Lekha',541,549,body)
    from .motzaei_refs import HAVDALAH
    intro=''
    for ref,value in split(reading(551+side,0),HAVDALAH,lang):
        intro+=passage('havdalah/intro/'+ref, value, BIBLE+ref if ref!='ken_tihyeh' else None)

    add('havdalah_intro','פסוקי הבדלה','Havdalah opening verses',551,551,intro)
    havdalah=instruction(READINGS[str(551+side)]['rubrics'][0])
    havdalah+=conditional('havdalah_private','Outside the synagogue:',feature('opensiddur:observance','synagogue-havdalah'),transclude(ROOT+'/havdalah_intro'),negate=True)
    havdalah+=instruction('In the synagogue, the Reader begins here:')
    if not side:havdalah+=passage('havdalah/savri',reading(551,1))
    havdalah+=passage('havdalah/wine',reading(551+side,2-side),PRAYER+'borei_peri_hagafen')
    havdalah+=conditional('havdalah_spices','Except when a festival immediately follows the Sabbath:',feature(AGG,'yom-tov'),transclude(PRAYER+'borei_minei_vesamim'),negate=True)
    havdalah+=transclude(PRAYER+'borei_meorei_haesh')+transclude(PRAYER+'hamavdil_bein_qodesh_lechol')
    add('havdalah','הַבְדָּלָה','HAVDALAH',551,551,havdalah,printed=True)
    hymns=''.join(transclude(POEM+p) for p in POEMS)
    hymns+=transclude(PRAYER+'ribbon_haolamim')+transclude(PRAYER+'ufetach_lanu')
    add('zemirot','זְמִירוֹת','HYMNS',553,561,hymns,printed=True)
    arvit=SIDDUR+'chol/arvit/'
    sequence=transclude(ROOT+'/opening')
    sequence+=''.join(transclude(arvit+k) for k in ('blessings_before_shema','shema','blessings_after_shema','amidah'))
    sequence+=conditional('motzaei_half_kaddish','When a minyan holds service:',MINYAN,kaddish())
    sequence+=transclude(ROOT+'/after_amidah')+transclude(ROOT+'/kaddish')
    sequence+=instruction('Between Pesaḥ and Shawuoth, the Omer is counted.')+instruction('On Ḥanukkah, the Reader lights the Ḥanukkah lights.')
    sequence+=transclude(ROOT+'/veyitten_lekha')+transclude(ROOT+'/havdalah')
    sequence+=instruction(READINGS[str(551+side)]['rubrics'][-1])
    sequence+=''.join(transclude(arvit+k) for k in ('conclusion','psalm27','mourning'))+transclude(ROOT+'/zemirot')
    sequence=('<j:declare xml:id="motzaei_context"><tei:fs type="opensiddur:day-of-week"><tei:f name="hebrew-day"><tei:numeric value="1"/></tei:f></tei:fs></j:declare>'+sequence+'<j:endDeclare target="#motzaei_context"/>')
    add('','לְמוֹצָאֵי שַׁבָּת','FOR THE CONCLUSION OF SABBATH',535,561,sequence,printed=True)
    moon=instruction(READINGS[str(561+side)]['rubrics'][0])
    for page,keys in [(561,['psalm148','blessing','barukh_yotzerekh','keshem','tippol']),
                      (563,['david','greetings','simman_tov','kol_dodi','psalm121','psalm150','tana']),
                      (565,['mi_zot','yehi_ratzon','psalm67'])]:
        for idx,key in enumerate(keys):
            source={'psalm148':BIBLE+'psalms/148','psalm121':BIBLE+'psalms/121','psalm150':BIBLE+'psalms/150',
                    'psalm67':BIBLE+'psalms/67','kol_dodi':BIBLE+'song_of_songs/2','mi_zot':BIBLE+'song_of_songs/8/5'}.get(key)
            value=reading(page+side,idx)
            source_index={'psalm148':0,'blessing':1,'psalm121':0,'psalm150':1,'tana':2,'psalm67':0}.get(key)
            if source_index is not None:
                moon+=f'<tei:note type="instruction" xml:lang="{lang}">'+escape(READINGS[str(page+side)]['sources'][source_index])+'</tei:note>'
            if key=='greetings':moon+=instruction(READINGS[str(page+side)]['rubrics'][0])
            moon+=pb(page+side,sigil=SIGIL) if idx==0 else ''
            moon+=psalm(int(key[5:]),value,lang,LEVANAH+'/'+key,seen) if key.startswith('psalm') else passage(key,value,source,root=LEVANAH)
    moon+=conditional('levanah_kaddish','When a minyan holds service:',MINYAN,kaddish(mourner=True))
    add('','בִּרְכַּת הַלְּבָנָה','NEW MOON BLESSING',561,565,moon,root=LEVANAH,printed=True)
    return tuple(result)
