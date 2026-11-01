"""Journey, illness, burial, circumcision and redemption, IA n755–n776."""
import re
from .common import PRAYER, POEM, SIDDUR, PROJECT_HE, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .festival import conditional
from .tachanun_conditions import COMMON_OMISSIONS, TISHREI, date, holiday
from .shacharit_end import editorial_head
from .milestones import marked
from .notes_motzaei_shabbat import xml as note_xml
from .lifecycle_data import ROWS, RUBRICS

ROOT = SIDDUR+'lifecycle'
JOURNEY = SIDDUR+'tefillat_haderekh'
SICK = SIDDUR+'tefillah_lecholeh'
BURIAL = SIDDUR+'burial'
TZIDDUK = PRAYER+'tzidduq_hadin'
KADDISH = PRAYER+'kaddish/deitchadata'
CHAPEL = BURIAL+'/chapel'
MILAH = SIDDUR+'berit_milah'
GRACE = MILAH+'/grace'
RESHUT = POEM+'birshut_el_ayom'
HARACHAMAN = POEM+'harachaman_berit_milah'
PIDYON = SIDDUR+'pidyon_haben'
SIGIL = '1949 lifecycle'
# Date-only Tachanun calendar. A funeral itself must not suppress Tzidduk
# Hadin through the contextual house-of-mourning or brit-milah overrides.
TZIDDUK_OCCASION = ('<j:none>'+COMMON_OMISSIONS+date(1,1,30)+holiday('lag-baomer')
    +date(3,1,8)+holiday('tisha-bav')+date(5,15)+date(6,29)+TISHREI+date(11,15)
    +feature('opensiddur:day-of-week','hebrew-day','<tei:numeric value="7"/>')+'</j:none>')
URNS={r['key']:ROOT+'/text/'+r['key'] for r in ROWS}
URNS.update({'haderekh':PRAYER+'tefillat_haderekh',
 'sick_psalm23':BIBLE+'psalms/23','sick_refaenu':PRAYER+'amidah/refuah',
 'haderekh_exodus':BIBLE+'exodus/23/20', 'tzidduq_1':BIBLE+'deuteronomy/32/4',
 'tzidduq_jeremiah':BIBLE+'jeremiah/32/19','burial_leaving':BIBLE+'isaiah/25/8',
 'milah_wine':PRAYER+'borei_peri_hagafen','pidyon_shehecheyanu':PRAYER+'shehecheyanu',
 'milah_blessing':PRAYER+'al_hamilah','milah_father_blessing':PRAYER+'lehakhniso_bivrito',
 'milah_covenant':PRAYER+'asher_qiddesh_yedid','pidyon_blessing':PRAYER+'al_pidyon_haben',
 'burial_kaddish_open':KADDISH+'/opening',
 **{'tzidduq_'+str(i):TZIDDUK+'/'+str(i) for i in range(1,11)},
 **{'milah_poem_'+str(i):RESHUT+'/'+str(i) for i in range(1,5)},
 'milah_poem_refrain':RESHUT+'/refrain',
 **{'milah_harachaman_'+str(i):HARACHAMAN+'/'+str(i) for i in range(1,7)}})
URNS['tzidduq_1']=BIBLE+'deuteronomy/32/4'
# The chapel repeats the eight Yizkor verses verbatim, including its translation.
for key in [r['key'] for r in ROWS if r['key'].startswith('chapel_')]:
 suffix=key.removeprefix('chapel_')
 URNS[key]=SIDDUR+'yizkor/text/opening_'+('ecclesiastes_12_7' if suffix=='ecclesiastes' else suffix)
REUSED={'sick_refaenu','milah_wine','pidyon_shehecheyanu'}|{k for k in URNS if k.startswith('chapel_')}
BIBLICAL={
 'haderekh_exodus':'exodus/23/20','tzidduq_1':'deuteronomy/32/4',
 'tzidduq_jeremiah':'jeremiah/32/19','tzidduq_psalm92':'psalms/92/16',
 'tzidduq_job':'job/1/21','tzidduq_psalm78':'psalms/78/38','burial_leaving':'isaiah/25/8',
 'milah_grace_response':'psalms/113/2','milah_all':'psalms/65/5',
}
# Starts identify verse boundaries independently of sentence and paragraph breaks.
# These local witnesses keep the punctuation of this printing, while source points
# to the Bible. Psalm 23 is the first complete witness encoded in this project.
VERSE_STARTS={
 'haderekh_genesis':('genesis/32',2,['וְיַעֲקֹב','וַיֹּֽאמֶר'],['Jacob went','On seeing']),
 'haderekh_kohanim':('numbers/6',24,['יְבָרֶכְךָ','יָאֵר','יִשָּׂא'],['May the Lord bless','may the Lord countenance','may the Lord favor']),
 'haderekh_psalm91':('psalms/91',1,['יֹשֵׁב','אֹמַר','כִּי הוּא','בְּאֶבְרָתוֹ','לֹא תִירָא','מִדֶּֽבֶר בָּאֹֽפֶל','יִפֹּל','רַק','כִּי אַתָּה','לֹא תְאֻנֶּה','כִּי מַלְאָכָיו','עַל כַּפַּֽיִם','עַל שַׁחַל','כִּי בִי','יִקְרָאֵֽנִי','אֹֽרֶךְ'],['He who','I call','He saves','With his','Fear not','nor the pestilence','Though a','You have','Thou, O Lord','no disaster','For he will','They will','You shall tread','“Because','When he calls','I enrich']),
 'sick_psalm6':('psalms/6',2,['יְיָ,','חָנֵּֽנִי','וְנַפְשִׁי','שׁוּבָה','כִּי אֵין','יָגַֽעְתִּי','עָשְׁשָׁה','סֽוּרוּ','שָׁמַע','יֵבֹֽשׁוּ'],['O Lord, punish','Have pity','My soul','O Lord, deliver','For in death','I am worn','My eye','Depart','The Lord has','All my foes']),
 'sick_psalm23':('psalms/23',1,['מִזְמוֹר','בִּנְאוֹת','נַפְשִׁי','גַּם כִּי','תַּעֲרֹךְ','אַךְ טוֹב'],['A psalm','He makes','He restores','Even though','Thou spreadest','Only goodness']),
}


def xml(raw):
    return text_xml(raw,SIGIL)


def verse_text(key, raw, lang):
    book,first,he,en=VERSE_STARTS[key]
    starts=he if lang=='he' else en
    offsets=[];at=0
    for start in starts:
        # NFC is not identical to the keyboard ordering of Hebrew marks.
        import unicodedata
        start=unicodedata.normalize('NFC',start)
        at=raw.index(start,at);offsets.append(at);at+=len(start)
    assert offsets[0]==0,(key,lang)
    offsets.append(len(raw));parts=[]
    for i,(a,b) in enumerate(zip(offsets,offsets[1:]),first):
        source=BIBLE+book+'/'+str(i)
        canonical=key in ('sick_psalm23','haderekh_genesis')
        urn=source if canonical else URNS[key]+'/'+str(i)
        value=xml(raw[a:b])
        if not canonical:value=f'<tei:seg source="{source}">'+value+'</tei:seg>'
        parts.append(marked(urn,value,unit='verse'))
    return ''.join(parts)


# Bounded quotations embedded in non-biblical prayers. The repeated half-verse
# in the Hebrew milah passage has no second translation in this edition.
QUOTATIONS={
 'milah_ready': [('genesis/17/12','וּבֶן־','“Every male',None,None)],
 'milah_verses': [
  ('genesis/49/18','לִישׁוּעָתְךָ','O Lord,','שִׂבַּֽרְתִּי','I wait'),
  ('psalms/119/166','שִׂבַּֽרְתִּי','I wait','שָׂשׂ','I delight'),
  ('psalms/119/162','שָׂשׂ','I delight','שָׁלוֹם','Abundant peace'),
  ('psalms/119/165','שָׁלוֹם','Abundant peace','אַשְׁרֵי','Happy is'),
  ('psalms/65/5','אַשְׁרֵי','Happy is',None,None)],
 'milah_name': [
  ('proverbs/23/25','יִשְׂמַח אָבִֽיךָ','“Let your','וְנֶאֱמַר','\n'),
  ('ezekiel/16/6','וָאֶעֱבֹר','“I passed','וְנֶאֱמַר','\n'),
  ('psalms/105/8','זָכַר','“He remembers','אֲשֶׁר כָּרַת','the covenant he'),
  ('psalms/105/9','אֲשֶׁר כָּרַת','the covenant he','וַיַּעֲמִידֶֽהָ','He confirmed'),
  ('psalms/105/10','וַיַּעֲמִידֶֽהָ','He confirmed','וְנֶאֱמַר','\n'),
  ('genesis/21/4','וַיָּֽמָל','“Abraham','הוֹדוּ','\n'),
  ('psalms/118/1','הוֹדוּ','“Give thanks','זֶה הַקָּטֹן','May this child')],
 'pidyon_present': [
  ('numbers/18/16','וּפְדוּיָו','“The redemption','וְנֶאֱמַר','And it is said'),
  ('exodus/13/2','קַדֶּשׁ','“Consecrate',None,None)],
 'pidyon_child_blessing':[
  ('genesis/48/20','יְשִׂמְךָ','May God','יְבָרֶכְךָ','May the Lord'),
  ('numbers/6/24','יְבָרֶכְךָ','May the Lord','יָאֵר','may the Lord countenance'),
  ('numbers/6/25','יָאֵר','may the Lord countenance','יִשָּׂא','may the Lord favor'),
  ('numbers/6/26','יִשָּׂא','may the Lord favor',None,None)],
 'pidyon_closing':[
  ('psalms/121/5','יְיָ שֹׁמְרֶֽךָ','The Lord guards','כִּי אֹֽרֶךְ','A long'),
  ('proverbs/3/2','כִּי אֹֽרֶךְ','A long','יְיָ יִשְׁמָרְךָ','The Lord will'),
  ('psalms/121/7','יְיָ יִשְׁמָרְךָ','The Lord will','אָמֵן','Amen.')],
}


def quoted_text(key, raw, lang):
    import unicodedata
    result='';offset=0
    for source,he,en,he_end,en_end in QUOTATIONS[key]:
        start=unicodedata.normalize('NFC',he if lang=='he' else en)
        end=he_end if lang=='he' else en_end
        a=raw.index(start,offset)
        b=raw.index(unicodedata.normalize('NFC',end),a+len(start)) if end else len(raw)
        quoted=xml(raw[a:b])
        if key=='pidyon_present' and source=='numbers/18/16':
            quoted=marked(URNS[key]+'/shekel_haqodesh',quoted,unit='quotation')
        result+=xml(raw[offset:a])+f'<tei:seg source="{BIBLE+source}">'+quoted+'</tei:seg>'
        offset=b
    return (result+xml(raw[offset:])).replace('\n','</tei:p><tei:p>')


def shared(lang, prayers):
    result=[dict(p) for p in prayers];side=int(lang=='en')
    for p in result:
        pages=[r['page']+side for r in ROWS if r['key'] in REUSED and URNS[r['key']]==p['urn']]
        if pages:p['printings']=(*p.get('printings',()),*((page,page) for page in sorted(set(pages))))
    return result


def prayers(lang):
    result=[];side=int(lang=='en')
    for r in ROWS:
        key=r['key']
        if key in REUSED:continue
        urn=URNS[key];page=r['page']+side;raw=r[lang]
        poem=key.startswith(('milah_poem_','milah_harachaman_'))
        if key in VERSE_STARTS:value=verse_text(key,raw,lang)
        else:
            value=quoted_text(key,raw,lang) if key in QUOTATIONS else xml(raw).replace('\n','</tei:p><tei:p>')
            if key in BIBLICAL:value=f'<tei:seg source="{BIBLE+BIBLICAL[key]}">'+value+'</tei:seg>'
            if poem:value=''.join('<tei:l>'+xml(line)+'</tei:l>' for line in raw.splitlines())
            value=marked(urn,value,unit='stanza' if poem else 'verse' if key in BIBLICAL else 'prayer-part')
        tag='lg' if poem else 'p'
        body=f'<tei:{tag}>'+pb(page,sigil=SIGIL)+value+f'</tei:{tag}>'
        if key in VERSE_STARTS:body=f'<tei:div corresp="{urn}">'+body+'</tei:div>'
        result.append(dict(name='lifecycle_'+key+'_text',urn=urn,title=key.replace('_',' '),first=page,
            last=(733+side if key=='haderekh_psalm91' else page),body=body))
    return result


def units(project):
    side=int(project!=PROJECT_HE);lang=('he','en')[side];out=[]
    def p(key):return transclude(URNS[key])
    def rubric(key):return '<tei:note type="instruction" xml:lang="en">'+note_xml(RUBRICS.get(key+'_'+lang,RUBRICS.get(key,'')))+'</tei:note>'
    def add(name,urn,he,en,first,last,body,printed=True):
        head='<tei:head'+(' xml:lang="en"' if lang=='he' and not re.search('[א-ת]',he) else '')+'>'+((he,en)[side])+'</tei:head>' if printed else editorial_head(lang,he,en)
        out.append(dict(name=name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+head+body+'</tei:div>'))
    add('tefillat_haderekh_psalm91',JOURNEY+'/psalm91','תהלים צא','Psalm 91',731,733,p('haderekh_psalm91'))
    add('tefillat_haderekh',JOURNEY,'תְּפִלַּת הַדֶּרֶךְ','BEFORE A JOURNEY',731,733,
        ''.join(p(k) for k in ('haderekh','haderekh_genesis','haderekh_exodus','haderekh_kohanim'))+transclude(JOURNEY+'/psalm91'))
    add('tefillah_lecholeh_psalm23',SICK+'/psalm23','תהלים כג','Psalm 23',733,733,p('sick_psalm23'))
    add('tefillah_lecholeh',SICK,'תְּפִלָּה לְחוֹלֶה','PRAYER FOR THE SICK',733,733,
        p('sick_psalm6')+transclude(SICK+'/psalm23')+p('sick_refaenu'))
    add('tzidduq_hadin',TZIDDUK,'צִדּוּק הַדִּין','ACKNOWLEDGMENT OF DIVINE JUSTICE',735,737,
        ''.join(p(r['key']) for r in ROWS if r['key'].startswith('tzidduq_')))
    add('burial_kaddish',KADDISH,'MOURNERS’ KADDISH','MOURNERS’ KADDISH',737,739,
        rubric('burial_kaddish')+''.join(p(r['key']) for r in ROWS if r['key'].startswith('burial_kaddish_')))
    add('burial_chapel',CHAPEL,'FUNERAL SERVICE AT THE CHAPEL','FUNERAL SERVICE AT THE CHAPEL',739,739,
        ''.join(p(r['key']) for r in ROWS if r['key'].startswith('chapel_'))+rubric('chapel')+p('sick_psalm23'))
    burial=conditional('tzidduq_calendar',RUBRICS['tzidduq_'+lang],TZIDDUK_OCCASION,transclude(TZIDDUK))
    # User-supplied editorial rule, not an instruction printed in Birnbaum:
    # the expanded burial Kaddish accompanies Tzidduk Hadin; otherwise Yatom.
    minyan=feature('opensiddur:quorum','minyan')
    expanded='<j:none><j:none>'+minyan+'</j:none><j:none>'+TZIDDUK_OCCASION+'</j:none></j:none>'
    regular='<j:none><j:none>'+minyan+'</j:none>'+TZIDDUK_OCCASION+'</j:none>'
    burial+=conditional('burial_expanded','With a minyan, when Tzidduk Hadin is recited:',expanded,transclude(KADDISH))
    burial+=conditional('burial_regular','With a minyan, when Tzidduk Hadin is omitted, recite regular Mourner’s Kaddish:',regular,transclude(PRAYER+'kaddish/yatom'))
    burial+=rubric('leaving')+p('burial_leaving')+transclude(CHAPEL)
    add('burial',BURIAL,'סדר קבורה','Burial service',735,739,burial,False)
    poem=rubric('all')+p('milah_poem_refrain')
    for i in range(1,5):poem+=rubric('leader')+p('milah_poem_'+str(i))+rubric('all')+p('milah_poem_refrain')
    add('milah_reshut',RESHUT,'ברשות אל איום','Birshut El Ayom',745,747,poem,False)
    add('milah_harachaman',HARACHAMAN,'הרחמן לברית מילה','Harachaman for Brit Milah',747,749,
        ''.join(p('milah_harachaman_'+str(i)) for i in range(1,7)),False)
    add('berit_milah_grace',GRACE,'בִּרְכַּת הַמָּזוֹן לִבְרִית מִילָה','GRACE AFTER THE BRITH MILAH',745,749,
        rubric('leader')+p('milah_grace_invitation')+rubric('company')+p('milah_grace_response')
        +transclude(RESHUT)+rubric('grace')
        +transclude(PRAYER+'birkat_hamazon/zimmun/nevarekh')
        +transclude(PRAYER+'birkat_hamazon/zimmun/barukh_sheakhalnu')
        +transclude(PRAYER+'birkat_hamazon/zimmun/barukh_hu')
        +transclude(PRAYER+'birkat_hamazon/four_blessings')
        +transclude(PRAYER+'birkat_hamazon/harachaman/before_insert')
        +rubric('insert')+transclude(HARACHAMAN)
        +transclude(PRAYER+'birkat_hamazon/harachaman/after_insert'))
    body=''
    for label,keys in [('milah_welcome',['milah_welcome']),('milah_father',['milah_ready']),
        ('milah_seat',['milah_elijah','milah_verses']),('all',['milah_all']),
        ('mohel_before',['milah_blessing']),('father_after',['milah_father_blessing']),
        ('all',['milah_response']),('mohel',['milah_wine','milah_covenant','milah_name'])]:
        body+=rubric(label)+''.join(p(k) for k in keys)
    add('berit_milah',MILAH,'בְּרִית מִילָה','BRITH MILAH',741,749,body+transclude(GRACE))
    body=rubric('pidyon')+rubric('present')+p('pidyon_present')+rubric('kohen')+p('pidyon_question')
    body+=rubric('father')+p('pidyon_answer')+p('pidyon_blessing')+p('pidyon_shehecheyanu')
    body+=rubric('exchange')+p('pidyon_exchange')+rubric('hand')+p('pidyon_child_blessing')+p('pidyon_closing')
    add('pidyon_haben',PIDYON,'פִּדְיוֹן הַבֵּן','REDEMPTION OF THE FIRST-BORN SON',749,751,body)
    add('lifecycle',ROOT,'תפילות וברכות למאורעות החיים','Prayers and blessings for life events',731,751,
        ''.join(transclude(u) for u in (JOURNEY,SICK,BURIAL,MILAH,PIDYON)),False)
    return tuple(out)
