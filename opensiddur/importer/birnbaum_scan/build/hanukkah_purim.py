"""Hanukkah, Megillat Hashmonaim and Purim, IA n733–n754."""
import re
from .common import PRAYER, POEM, SIDDUR, PROJECT_HE, SERVICE, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .festival import conditional
from .tachanun_conditions import holiday
from .shacharit_end import editorial_head
from .milestones import marked
from .hanukkah_purim_data import ROWS, RUBRICS

CHANUKAH = SIDDUR+'chanukah'
PURIM = SIDDUR+'purim'
HASHMONAIM = PRAYER+'megillat_hachashmonaim'
MAOZ = POEM+'maoz_tzur'
ASHER = POEM+'asher_heni'
SHOSHANAT = POEM+'shoshannat_yaaqov'
LIGHTS = PRAYER+'hadlaqat_ner_chanukah'
SIGIL = '1949 hanukkah_purim'
FIRST_NIGHT = holiday('hanukkah')
MORNING = feature(SERVICE,'shaharit')
URNS = {
 'lights_blessing':LIGHTS+'/blessing', 'miracles':PRAYER+'sheasah_nissim',
 'shehecheyanu':PRAYER+'shehecheyanu', 'hanerot':PRAYER+'hanerot_halalu',
 'megillah_blessing':PRAYER+'al_miqra_megillah',
 'purim_miracles':PRAYER+'sheasah_nissim', 'purim_shehecheyanu':PRAYER+'shehecheyanu',
 'after_megillah':PRAYER+'harav_et_riveinu', 'shoshannat':SHOSHANAT+'/shoshannat',
 'arur_haman':SHOSHANAT+'/arur_haman', 'charvonah':SHOSHANAT+'/charvonah',
 **{'maoz_'+str(n):MAOZ+'/'+str(n) for n in range(1,7)},
 **{'asher_'+str(n):ASHER+'/'+str(n) for n in range(1,21)},
 **{'hachashmonaim_'+str(n):HASHMONAIM+'/'+str(n) for n in range(1,77)},
}
REUSED = {'shehecheyanu','purim_miracles','purim_shehecheyanu'}


def xml(raw):
    return text_xml(raw,SIGIL).replace('\n','<tei:lb/>')


def shared(lang,prayers):
    """Record both additional printings of the unchanged Shehecheyanu blessing."""
    result=[dict(p) for p in prayers]
    for p in result:
        if p['urn']==URNS['shehecheyanu']:
            side=int(lang=='en')
            p['printings']=(*p.get('printings',()),(709+side,709+side),(725+side,725+side))
    return result


def verse_number(n):
    tens,ones=divmod(n,10)
    if n in (15,16):return 'ט'+('ו' if n==15 else 'ז')
    return ('יכלמנסע'[tens-1] if tens else '')+('אבגדהוזחט'[ones-1] if ones else '')


def hashmonaim(lang):
    """Verse boundaries and printed paragraphs are independent on the two sides."""
    body=f'<tei:div corresp="{HASHMONAIM}"><tei:head>'+('מְגִלַּת הַחַשְׁמוֹנָאִים' if lang=='he' else 'THE SCROLL OF THE HASMONEANS')+'</tei:head>'
    current_page=None
    for r in (r for r in ROWS if r['key'].startswith('hachashmonaim_')):
        n=int(r['key'].split('_')[1]);page=r['page'] if lang=='he' else r['en_page']
        if r['paragraph' if lang=='he' else 'en_paragraph']:
            if n>1:body+='</tei:p>'
            body+='<tei:p>'
        else:body+=' '
        if current_page!=page:body+=pb(page,sigil=SIGIL)
        raw=r[lang];value=xml(raw)
        if n==39:
            # The scroll quotes two parts of the Sabbath command, not a complete
            # biblical verse. Source spans do not redefine canonical Bible URNs.
            start,end=('שֵׁשֶׁת','וּבַיּוֹם') if lang=='he' else ('Six days','on the seventh')
            # English quotation starts with a typographic opening quote; retain it.
            a=raw.index(start);b=raw.index(end,a)
            c=raw.index('עַתָּה' if lang=='he' else 'It is better',b)
            value=xml(raw[:a])+f'<tei:seg source="{BIBLE}exodus/20/9">'+xml(raw[a:b])+'</tei:seg>'
            value+=f'<tei:seg source="{BIBLE}exodus/34/21">'+xml(raw[b:c])+'</tei:seg>'+xml(raw[c:])
        passage=marked(URNS[r['key']],value,unit='verse')
        if lang=='he':
            passage=passage.replace('<tei:milestone unit="verse" corresp=', '<tei:milestone n="'+verse_number(n)+'" unit="verse" corresp=',1)
        body+=passage
        internal=[int(p) for p in re.findall(r'\{pb:(\d+)\}',raw)]
        current_page=internal[-1] if internal else page
    return body+'</tei:p></tei:div>'


def prayers(lang):
    result=[]
    for r in ROWS:
        key=r['key']
        if key in REUSED or key.startswith('hachashmonaim_'):continue
        urn=URNS[key];page=r['page'] if lang=='he' else r['en_page'];raw=r[lang]
        poem=key.startswith(('maoz_','asher_')) or key in ('shoshannat','arur_haman','charvonah')
        # The sixth Maoz stanza has no English translation in this printing.
        # Keep an empty parallel anchor rather than supplying another edition.
        value=''.join('<tei:l>'+xml(line)+'</tei:l>' for line in raw.splitlines()) if poem else xml(raw)
        tag='lg' if poem and raw else 'p'
        body=f'<tei:{tag}>'+pb(page,sigil=SIGIL)+marked(urn,value,unit='stanza' if poem else 'prayer-part')+f'</tei:{tag}>'
        result.append(dict(name='chanukah_purim_'+key+'_text',urn=urn,title=key.replace('_',' '),first=page,last=page,body=body,
            printings=((725+int(lang=='en'),725+int(lang=='en')),) if key=='miracles' else ()))
    result.append(dict(name='megillat_hachashmonaim',urn=HASHMONAIM,title='Megillat Hashmonaim',first=713+int(lang=='en'),last=725+int(lang=='en'),body=hashmonaim(lang)))
    return result


def units(project):
    side=int(project!=PROJECT_HE);lang=('he','en')[side];out=[]
    def p(key):return transclude(URNS[key])
    def add(name,urn,he,en,first,last,body,printed=False):
        head='<tei:head>'+((he,en)[side])+'</tei:head>' if printed else editorial_head(lang,he,en)
        out.append(dict(name=name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+head+body+'</tei:div>'))
    lights=p('lights_blessing')+p('miracles')
    lights+=conditional('chanukah_first_night',RUBRICS['first_night'],FIRST_NIGHT,p('shehecheyanu'))
    lights+=instruction(RUBRICS['kindling'])+p('hanerot')
    add('chanukah_lights',LIGHTS,'הַדְלָקַת נֵר שֶׁל חֲנֻכָּה','LIGHTING THE ḤANUKKAH LIGHTS',709,709,lights,True)
    maoz=''.join(p('maoz_'+str(n)) for n in range(1,6))+instruction(RUBRICS['late_stanza'])+p('maoz_6')
    add('maoz_tzur',MAOZ,'מָעוֹז צוּר','MAOZ TSUR',709,711,maoz)
    add('chanukah',CHANUKAH,'חֲנֻכָּה','ḤANUKKAH',709,725,transclude(LIGHTS)+transclude(MAOZ)+transclude(HASHMONAIM))
    add('asher_heni',ASHER,'אֲשֶׁר הֵנִיא','Asher Heni',727,729,''.join(p('asher_'+str(n)) for n in range(1,21)))
    add('shoshannat_yaaqov',SHOSHANAT,'שׁוֹשַׁנַּת יַעֲקֹב','Shoshanat Yaakov',729,729,p('shoshannat')+p('arur_haman')+p('charvonah'))
    before=instruction(RUBRICS['before_megillah'])+p('megillah_blessing')+p('purim_miracles')+p('purim_shehecheyanu')
    after=instruction(RUBRICS['after_megillah'])+p('after_megillah')
    after+=conditional('purim_asher_heni',RUBRICS['omit_morning'],MORNING,transclude(ASHER),negate=True)
    # This is the morning starting point, not an instruction to omit these lines
    # at night. Keep the rubric in the caller, outside the reusable poem.
    after+=instruction(RUBRICS['morning'])+transclude(SHOSHANAT)
    add('purim',PURIM,'לְפוּרִים','FOR PURIM',725,729,before+after,True)
    return tuple(out)
