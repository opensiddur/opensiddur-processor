"""Memorial service, IA n625–n632; occasion gates belong to callers."""
from .common import PRAYER, PROJECT_HE, SIDDUR, feature, pb
from .conclusion import BIBLE, instruction, text_xml, transclude
from .festival import conditional
from .milestones import marked
from .shacharit_end import editorial_head
from .tachanun_conditions import DIASPORA, ISRAEL
from .yizkor_data import AV_ROWS, PAGES, ROWS

ROOT = SIDDUR+'yizkor'
SERVICE = PRAYER+'yizkor'
SIGIL = '1949 yizkor'
RUBRIC = PAGES['601']['items'][0]['text']
def day(name, value):
    return feature('opensiddur:holiday',name,f'<tei:numeric value="{value}"/>')
OCCASION = ('<j:any>'+day('yom-kippur',1)+day('shmini-atzeret',1)+
    '<j:all>'+ISRAEL+'<j:any>'+day('pesah',7)+day('shavuot',1)+'</j:any></j:all>'+
    '<j:all>'+DIASPORA+'<j:any>'+day('pesah',8)+day('shavuot',2)+'</j:any></j:all></j:any>')
SELECTORS = {k:feature('opensiddur:yizkor',k.replace('_','-')) for k in
             ('father','mother','husband','wife','el_male_man','el_male_woman')}
URNS = {r['key']:(PRAYER+'el_male_rachamim/'+r['key'].removeprefix('el_male_')
    if r['key'].startswith('el_male_') else SERVICE+'/'+r['key']
    if r['key'] in ('father','mother','husband','wife','martyrs') else ROOT+'/text/'+r['key']) for r in ROWS}
BIBLICAL = dict(zip((r['key'] for r in ROWS[:8]),
    (BIBLE+s for s in ('psalms/144/3','psalms/144/4','psalms/90/6','psalms/90/12',
                       'psalms/37/37','psalms/49/16','psalms/73/26','ecclesiastes/12/7'))))
BIBLICAL.update({'91_'+str(v):BIBLE+'psalms/91/'+str(v) for v in range(1,17)})


def prayers(lang):
    side=int(lang=='en');result=[]
    for row in ROWS:
        key=row['key'];urn=URNS[key]
        value=text_xml(row[lang],SIGIL).replace('\n','<tei:lb/>')
        value=value.replace('{reader}',instruction('Reader'))
        value=value.replace('…','. . .')
        if '. . .' in value:
            value=value.replace('. . .','. . .'+instruction('The name of the deceased is supplied.'))
        if key in BIBLICAL:value=f'<tei:seg source="{BIBLICAL[key]}">'+value+'</tei:seg>'
        if key=='av_harachamim':
            chunks=[]
            for part in AV_ROWS:
                part_urn=urn+'/'+part['key']
                source=BIBLE+part['source'] if part['source'] else PRAYER+'av_harachamim/shokhen_meromim/'+part['key']
                # Even the two text-identical leaves have different surrounding
                # rubrics/apparatus in the earlier Torah-service occurrence.
                # Keep this occurrence local to avoid inheriting those notes.
                value=text_xml(part[lang],SIGIL).replace('{reader}',instruction('Reader'))
                value=f'<tei:seg source="{source}">'+value+'</tei:seg>'
                chunks.append(marked(part_urn,value,unit='memorial-part'))
            value=' '.join(chunks)
        if key!='av_harachamim':
            value=marked(urn,value,unit='verse' if key in BIBLICAL else 'prayer-part')
        body='<tei:p>'+pb(row['page']+side,sigil=SIGIL)+value+'</tei:p>'
        if key=='av_harachamim':body=f'<tei:div corresp="{urn}">'+body+'</tei:div>'
        result.append(dict(name='yizkor_'+key+'_text',urn=urn,title=key.replace('_',' '),
            first=row['page']+side,last=row['page']+side,
            body=body))
    return result


def caller():
    return conditional('yizkor_occasion','',OCCASION,transclude(SERVICE))


def units(project):
    side=int(project!=PROJECT_HE);lang=('he','en')[side];result=[]
    def add(name,urn,he,en,first,last,body):
        head=editorial_head(lang,he,en) if name=='yizkor_opening' else '<tei:head>'+((he,en)[side])+'</tei:head>'
        result.append(dict(name=name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),
            body=f'<tei:div corresp="{urn}">'+head+body+'</tei:div>'))
    add('yizkor_opening',ROOT+'/opening','פסוקי פתיחה','Opening verses',601,601,
        instruction('Responsively')+''.join(transclude(URNS[r['key']]) for r in ROWS[:8]))
    add('yizkor_psalm91',ROOT+'/psalm91','תהלים צא','Psalm 91',601,603,
        ''.join(transclude(URNS['91_'+str(v)]) for v in range(1,17)))
    body=instruction(RUBRIC)+transclude(ROOT+'/opening')+transclude(ROOT+'/psalm91')
    for key,label in [('father','In memory of a father:'),('mother','In memory of a mother:'),
        ('husband','In memory of a husband:'),('wife','In memory of a wife:'),
        ('martyrs','In memory of Jewish martyrs:'),('el_male_man','For a man:'),
        ('el_male_woman','For a woman:'),('av_harachamim','Congregation:')]:
        text=transclude(URNS[key])
        body+=conditional('yizkor_'+key,label,SELECTORS[key],text) if key in SELECTORS else instruction(label)+text
    add('yizkor_service',SERVICE,'הַזְכָּרַת נְשָׁמוֹת','MEMORIAL SERVICE',601,607,body)
    # The caller has no second heading or duplicated occasion rubric.
    result.append(dict(name='yizkor',urn=ROOT,title_he='הזכרת נשמות',title_en='Memorial service',
        pages=(601+side,607+side),body=f'<tei:div corresp="{ROOT}">'+caller()+'</tei:div>'))
    return tuple(result)


def extend_services(units_):
    """The shared Sabbath/festival Torah service returns to Ashrei after Yizkor."""
    result=[dict(u) for u in units_]
    for u in result:
        if u['urn']!=SIDDUR+'shabbat/shacharit/torah':continue
        marker=transclude(SIDDUR+'shabbat/shacharit/torah/ashrei')
        if u['body'].count(marker)!=1:raise ValueError('Expected Ashrei return point')
        u['body']=u['body'].replace(marker,transclude(ROOT)+marker)
    return tuple(result)
