"""Ushpizin, Lulav, Hoshanot, Geshem and Hakafot, IA n699–732."""
import re
from .common import PRAYER, POEM, SIDDUR, PROJECT_HE, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .festival import conditional
from .shabbat_arvit import SHABBAT
from .shabbat_amidah import READER
from .tachanun_conditions import date, holiday, ISRAEL, DIASPORA
from .shacharit_end import editorial_head
from .milestones import marked
from .notes_motzaei_shabbat import xml as rubric_xml
from .sukkot_rites_data import ROWS, RUBRICS

ROOT = SIDDUR+'sukkot'
USHPIZIN = PRAYER+'ushpizin'
LULAV = PRAYER+'netilat_lulav'
HOSHANOT = PRAYER+'hoshanot'
GESHEM = PRAYER+'tefillat_geshem'
HAKAFOT = PRAYER+'hakafot_simchat_torah'
SIGIL = '1949 sukkot rites'
SUKKOT = date(7,15,21)
RABBAH = date(7,21)
FIRST_USE = feature('opensiddur:practice','lulav-first-use')
GESHEM_OCCASION = '<j:all>'+READER+date(7,22)+'</j:all>'
SIMCHAT_TORAH = '<j:any><j:all>'+ISRAEL+date(7,22)+'</j:all><j:all>'+DIASPORA+date(7,23)+'</j:all></j:any>'
URNS = {r['key']:ROOT+'/text/'+r['key'] for r in ROWS}
BIBLICAL = {
 'hoshanot_a_add':'psalms/89/3','hoshanot_b_add':'psalms/89/14',
 'hoshanot_c_add':'micah/7/20','hoshanot_hoshia_add':'psalms/16/11',
 'hoshanot_adam_add':'psalms/8/2','hoshanot_adamah_add':'psalms/145/17',
 'hakafot_ata_horeta':'deuteronomy/4/35','hakafot_leoseh':'psalms/136/4',
 'hakafot_ein_kamokha':'psalms/86/8','hakafot_yehi_khevod':'psalms/104/31',
 'hakafot_yehi_shem':'psalms/113/2','hakafot_yehi_immanu':'kings_1/8/57',
 'hakafot_veimru':'chronicles_1/16/35','hakafot_strength':'psalms/29/11',
 'hakafot_vayehi':'numbers/10/35','hakafot_kuma':'psalms/132/8',
 'hakafot_kohanim':'psalms/132/9','hakafot_david':'psalms/132/10',
 'hakafot_veamar':'isaiah/25/9','hakafot_malkhut':'psalms/145/13',
 'hakafot_zion':'isaiah/2/3','hakafot_shema':'deuteronomy/6/4','hakafot_exalt':'psalms/34/4'}
SOURCES = {'lulav_shehecheyanu':PRAYER+'shehecheyanu',
 'geshem_avot':PRAYER+'amidah/avot', 'geshem_avot_close':PRAYER+'amidah/avot/magen_avraham',
 'geshem_gevurot':PRAYER+'amidah/gevurot/attah_gibor',
 'hakafot_father':PRAYER+'av_harachamim/heytivah/text','hakafot_one':PRAYER+'echad_elohenu/text'}
# The same verse has distinct punctuation/pointing and apparatus in these
# printings. Occurrence addresses retain that evidence; source is canonical.

def xml(value):
    return text_xml(value,SIGIL).replace('\n','<tei:lb/>').replace('\t',' ')


def c(key,rubric,expr,body,negate=False):
    return conditional('sukkot_'+key,rubric,expr,body,negate=negate)


def quoted(raw,ref):
    return '<tei:seg source="'+BIBLE+ref+'">'+xml(raw)+'</tei:seg>'



def split_starts(raw, starts):
    """Locate scan-authored boundaries without changing the edition's points."""
    positions=[]
    for start in starts:
        pat=''.join(re.escape(ch)+'[\u0591-\u05c7]*' if '\u05d0'<=ch<='\u05ea' else re.escape(ch) for ch in start)
        m=re.search(pat,raw)
        if not m:raise ValueError((start,raw))
        positions.append(m.start())
    assert positions==sorted(positions)
    return [raw[a:b] for a,b in zip(positions,positions[1:]+[len(raw)])]


def anthology(raw,key):
    refs=['psalms/28/9','kings_1/8/59','kings_1/8/60']
    starts=['הושיעה','ויהיו','למען']
    if key=='hoshanot_lekha':
        refs=['chronicles_1/29/11','zechariah/14/9',None,'deuteronomy/6/4',None]
        starts=['לך','והיה','ובתורתך','שמע','ברוך שם']
    chunks=split_starts(raw,starts)
    return ''.join(marked(URNS[key]+'/'+ref,quoted(v,ref),unit='verse') if ref else xml(v) for ref,v in zip(refs,chunks))


def lulav_quotations(raw,lang,key):
    starts=['הריני','ולקחתם','ובנענועי','ויהי נעם','ברוך'] if lang=='he' else ['I am ready','“On the first day',' As I wave','May the favor','Blessed be']
    chunks=split_starts(raw,starts)
    refs=[None,'leviticus/23/40',None,'psalms/90/17','psalms/89/53']
    return ''.join(marked(URNS[key]+'/'+ref,quoted(v,ref),unit='verse') if ref else xml(v) for ref,v in zip(refs,chunks))


def prayers(lang):
    out=[]
    for r in ROWS:
        key=r['key'];urn=URNS[key];raw=r[lang];page=r['page'] if lang=='he' else r['en_page']
        value=xml(raw)
        if key in BIBLICAL:value=quoted(raw,BIBLICAL[key])
        elif key in SOURCES:value='<tei:seg source="'+SOURCES[key]+'">'+value+'</tei:seg>'
        if key in ('geshem_blessing','geshem_life','geshem_plenty'):
            a,b=raw.split('\t');value=instruction('Congregation and Reader:')+xml(a)+' '+instruction('Congregation:')+xml(b)
        if key=='lulav_lulav_intent':value=lulav_quotations(raw,lang,key)
        if key=='hoshanot_lekha' or key.startswith('hoshanot_hoshia_et_ammekha'):
            value=anthology(raw,key) if raw else ''
        # Hoshanot has no facing English translation: the English document
        # provides matching empty anchors for Birnbaum's explanatory apparatus.
        body='<tei:p>'+pb(page,sigil=SIGIL)+marked(urn,value,unit='verse' if key in BIBLICAL else 'prayer-part')+'</tei:p>'
        if key=='hakafot_sisu':
            # Eight Hebrew lines, with paired hemistichs, correspond to three
            # English stanzas of six, four and six lines.
            stanzas=[raw.splitlines()[:3],raw.splitlines()[3:5],raw.splitlines()[5:]] if lang=='he' else [s.splitlines() for s in raw.split('\n\n')]
            body='<tei:div corresp="'+urn+'">'+pb(page,sigil=SIGIL)
            for i,lines in enumerate(stanzas,1):
                body+='<tei:lg>'+marked(POEM+'sisu_vesimchu/'+str(i),''.join('<tei:l>'+xml(line)+'</tei:l>' for line in lines),unit='stanza')+'</tei:lg>'
            body+='</tei:div>'
        elif r['group']=='geshem' and '\n' in raw:
            body='<tei:lg>'+pb(page,sigil=SIGIL)+marked(urn,''.join('<tei:l>'+xml(line)+'</tei:l>' for line in raw.splitlines()),unit='stanza')+'</tei:lg>'
        last=max([page]+[int(n) for n in re.findall(r'\{pb:(\d+)\}',raw)])
        out.append(dict(name='sukkot_'+key+'_text',urn=urn,title=key.replace('_',' '),first=page,last=last,body=body))
    return out


# Birnbaum's printed six-day table. Derive the first day's weekday from the
# current Hebrew date and weekday, keeping unknown inputs three-valued.
ORDER = {2:(1,2,5,3,6,8),3:(1,2,5,6,8,4),5:(1,2,8,5,6,4),7:(8,1,5,2,6,4)}
def hoshana_day(number):
    clauses=[]
    for first,order in ORDER.items():
        for offset,n in enumerate(order):
            if n==number:
                weekday=(first-1+offset)%7+1
                clauses.append('<j:all>'+date(7,15+offset)+feature('opensiddur:day-of-week','hebrew-day',f'<tei:numeric value="{weekday}"/>')+'</j:all>')
    clauses.append(RABBAH)
    return '<j:any>'+''.join(clauses)+'</j:any>'


def units(project):
    side=int(project!=PROJECT_HE);lang=('he','en')[side];out=[]
    def p(k):return transclude(URNS[k])
    def seq(*keys):return ''.join(p(k) for k in keys)
    def add(name,urn,he,en,first,last,body,printed=False,heading=True):
        head=('<tei:head>'+((he,en)[side])+'</tei:head>') if printed else editorial_head(lang,he,en)
        if not heading:head=''
        delta=0 if 679<=first<=696 else side
        out.append(dict(name='sukkot_'+name,urn=urn,title_he=he,title_en=en,pages=(first+delta,last+delta),body=f'<tei:div corresp="{urn}">'+head+body+'</tei:div>'))
    def rubric(page,key):
        return '<tei:note type="instruction" xml:lang="en">'+rubric_xml(RUBRICS[str(page)][key]).replace('\n','<tei:lb/>')+'</tei:note>'
    ush=rubric(675,'enter')+seq('ushpizin_enter','ushpizin_invite')
    for d in range(1,8):
        k='day'+str(d);ush+=c(k,RUBRICS['675' if d<=5 else '677'][k],date(7,14+d),p('ushpizin_'+k))
    add('ushpizin',USHPIZIN,'אֻשְׁפִּיזִין','GUESTS IN THE SUKKAH',675,677,ush,True)
    lulav=seq('lulav_lulav_intent','lulav_lulav_blessing')+c('first_use',RUBRICS['677']['first'],FIRST_USE,p('lulav_shehecheyanu'))
    add('lulav',LULAV,'נְטִילַת לוּלָב','WAVING THE LULAV',677,677,lulav,True)
    def hp(k):return p('hoshanot_'+k)
    def hseq(*ks):return ''.join(hp(k) for k in ks)
    def star(k):return c(k,'On Hoshana Rabbah add:',RABBAH,hp(k))
    sections=[(1,'למען אמתך','Lema‘an amitekha',679,679,hp('hoshana_a')+star('a_add')),
        (2,'אבן שתיה','Even shetiyah',680,680,hp('hoshana_b')+star('b_add')),
        (3,'אם אני חומה','Om ani chomah',680,680,hp('hoshana_c')+star('c_add')),
        (4,'אדון המושיע','Adon hamoshia',680,682,hp('hoshia_start')+star('hoshia_add')+hp('adam')+star('adam_add')+hp('adamah')+star('adamah_add')+hseq('lemaan_eitan','lekha')),
        (5,'אערוך שועי','E‘erokh shu‘i',682,683,hp('eerokh_start')),
        (6,'אל למושעות','El lemosha‘ot',683,683,hp('el_lemoshaot')),
        (7,'אני והו — לחול','Ani vaho — weekdays',683,684,hseq('ani_vaho_1','kehosha_start','ani_vaho_2','hoshia_et_ammekha')),
        (8,'אם נצורה — לשבת','Om netzurah — Sabbath',684,686,hseq('om_netsurah_start','ani_vaho_3','kehosha_adam_start','ani_vaho_4','hoshia_et_ammekha_repeat'))]
    for n,he,en,first,last,body in sections:
        letter='אבגדהוזח'[n-1]
        add('hoshana_'+str(n),HOSHANOT+'/'+str(n),letter+' — '+he,'<tei:foreign xml:lang="he">'+letter+'</tei:foreign> — '+en,first,last,body)
    daily=rubric(679,'order')+rubric(679,'responsive')+hp('opening')
    for n in range(1,7):daily+=c('hoshana_'+str(n),'Hoshana '+str(n)+' according to the printed daily order:',hoshana_day(n),transclude(HOSHANOT+'/'+str(n)))
    daily+=c('hoshana7',RUBRICS['683']['weekdays'],SHABBAT,transclude(HOSHANOT+'/7'),True)
    daily+=c('hoshana8','On Sabbath:','<j:any>'+SHABBAT+RABBAH+'</j:any>',transclude(HOSHANOT+'/8'))
    # The final-day additions form a separately addressable sequence.
    rab_keys=[r['key'] for r in ROWS if r['group']=='hoshanot']
    rab_keys=rab_keys[rab_keys.index('hoshanot_ani_vaho_rabbah'):]
    rb=''
    before={'ani_vaho_rabbah':('686','rabbah'),'anna_hoshia':('687','response'),'anna_el_na':('688','response'),'anna_avinu':('689','response'),'hosha_na_el_na':('692','response'),'taaneh_emunim_first':('692','willows'),'kol_mevaser_response':('694','response'),'kol_mevaser_end':('696','response'),'yehi_ratzon_aravah':('696','strike')}
    for k in rab_keys:
        short=k.removeprefix('hoshanot_')
        if short in before:
            page,label=before[short]
            if label!='rabbah':rb+=rubric(page,label)
        if short=='kol_mevaser_end':rb+=rubric(696,'repeat')
        rb+=p(k)
    rb+=rubric(696,'continue')
    add('hoshana_rabbah',HOSHANOT+'/rabbah','הושענא רבה','HOSHANA RABBAH',686,696,rb,True)
    daily+=c('rabbah','On Hoshana Rabbah:',RABBAH,transclude(HOSHANOT+'/rabbah'))
    add('hoshanot',HOSHANOT,'הוֹשַׁעְנוֹת','HOSHANOTH',679,696,daily,True)
    gs=rubric(697,'reader')
    for r in ROWS:
        if r['group']!='geshem':continue
        k=r['key']
        if k.endswith('_response'):gs+=instruction('Congregation:')
        if k=='geshem_wind':gs+=instruction('Reader:')
        gs+=p(k)
    # The actual Musaf caller continues at Mekhalkel Chayim without a second opening.
    gs+=rubric(702 if side else 701,'continue')
    add('geshem',GESHEM,'תְּפִלַּת גֶּשֶׁם','PRAYER FOR RAIN',697,701,gs,True)
    hak=rubric(703,'responsive')+''.join(p(r['key']) for r in ROWS if r['group']=='hakafot' and r['page']==703)+p('hakafot_father')+rubric(705,'groups')
    ordinals=('First','Second','Third','Fourth','Fifth','Sixth','Seventh')
    for n in range(1,8):
        ks=['hakafot_'+str(n)+suffix for suffix in ('a','b')] if n in (1,7) else ['hakafot_'+str(n)]
        add('hakafah_'+str(n),HAKAFOT+'/'+str(n),'הקפה '+str(n),ordinals[n-1]+' Hakkafah',707 if n==7 else 705,707 if n==7 else 705,seq(*ks),True)
        hak+=transclude(HAKAFOT+'/'+str(n))
    add('sisu',POEM+'sisu_vesimchu','שישו ושמחו','Sisu Vesimchu',707,707,p('hakafot_sisu'))
    hak+=transclude(POEM+'sisu_vesimchu')+rubric(707,'return')
    for k,label in [('shema','reader_congregation1'),('one','reader_congregation2'),('exalt','reader')]:hak+=rubric(707,label)+p('hakafot_'+k)
    hak+=rubric(708 if side else 707,'continue')
    add('hakafot',HAKAFOT,'הַקָּפוֹת לְשִׂמְחַת תּוֹרָה','HAKKAFOTH FOR SIMḤATH TORAH',703,707,hak,True)
    body=c('ushpizin_occasion','During Sukkoth:',SUKKOT,transclude(USHPIZIN))
    body+=c('lulav_occasion',RUBRICS['677']['during'],'<j:all>'+SUKKOT+'<j:none>'+SHABBAT+'</j:none></j:all>',transclude(LULAV))
    body+=c('hoshanot_occasion','',SUKKOT,transclude(HOSHANOT))
    body+=c('geshem_occasion',RUBRICS['697']['occasion'],GESHEM_OCCASION,transclude(GESHEM))
    body+=c('hakafot_occasion','On Simḥath Torah:',SIMCHAT_TORAH,transclude(HAKAFOT))
    add('rites',ROOT+'/rites','סוכות ושמיני עצרת','Sukkot and Shemini Atzeret',675,707,body)
    return tuple(out)
