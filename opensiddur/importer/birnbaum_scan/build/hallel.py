"""Hallel, printed565–574: reusable psalms and an occasion-gated caller."""
import re
from .common import PRAYER, SIDDUR, PROJECT_HE, AGG, feature, pb, cond, endcond
from .conclusion import BIBLE, MOURNING, MINYAN, instruction, transclude, text_xml
from .milestones import marked
from .shabbat_minchah import kaddish
from .hallel_data import ROWS, PAGES
from .tachanun_conditions import holiday
from .shacharit_end import editorial_head

ROOT = PRAYER+'hallel'
SERVICE = SIDDUR+'hallel'
FS = 'opensiddur:hallel'
SIGIL = '1949 hallel'


def xml(value):
    return text_xml(value,SIGIL).replace('\n','<tei:lb/>').replace('{reader}',instruction('Reader'))


def conditional(key,rubric,condition,body):
    cid='hallel_'+key
    return cond(cid,note=rubric,fs=condition)+body+endcond(cid)


def shared(lang,prayers):
    """Complete psalms own canonical references; earlier quotations keep local addresses."""
    result=[]
    pattern=r'<tei:milestone unit="verse" corresp="('+re.escape(BIBLE)+r'psalms/(?:113|114|115|116|117|118)/\d+)"/>(.*?)(?=<tei:milestone unit="verse")'
    for original in prayers:
        p=dict(original)
        def quote(match):
            source,value=match.groups()
            local=p['urn']+'/quoted_'+source.split('psalms/')[1].replace('/','_')
            return marked(local,f'<tei:seg source="{source}">{value}</tei:seg>',unit='verse')
        p['body']=re.sub(pattern,quote,p['body'],flags=re.S)
        result.append(p)
    return result


def prayers(lang):
    side=int(lang=='en');result=[]
    for chapter in range(113,119):
        rows=[r for r in ROWS if r['key'].startswith(str(chapter)+'/') and '-repeat' not in r['key']]
        urn=BIBLE+'psalms/'+str(chapter);body='';previous=None;paragraph_open=False
        for row in rows:
            key=row['key'];value=xml(row[lang])
            if key.endswith('25b'):continue
            if row['page']!=previous:body+=pb(row['page']+side,sigil=SIGIL);previous=row['page']
            if key.endswith('25a'):
                other=next(r for r in rows if r['key']=='118/25b')
                value=marked(ROOT+'/anna/hoshiah',value)+ ' '+marked(ROOT+'/anna/hatzlichah',xml(other[lang]))
                key='118/25'
            verse=int(key.split('/')[-1])
            separate=chapter==118 and (verse<=4 or verse>=21)
            if not paragraph_open:
                body+='<tei:p>';paragraph_open=True
            body+=marked(BIBLE+'psalms/'+key,value,unit='verse')+' '
            if separate or key in ('115/11','116/11','118/20'):
                body+='</tei:p>';paragraph_open=False
        if paragraph_open:body+='</tei:p>'
        result.append(dict(name='hallel_psalm_'+str(chapter)+'_text',urn=urn,title='Psalm '+str(chapter),first=rows[0]['page']+side,last=rows[-1]['page']+side,body=f'<tei:div corresp="{urn}">'+body+'</tei:div>'))
    for key,address,title in [('opening','blessing','Blessing before Hallel'),('closing','yehalelukha','Yehallelukha')]:
        row=next(r for r in ROWS if r['key']==key);urn=ROOT+'/'+address
        result.append(dict(name='hallel_'+address,urn=urn,title=title,first=row['page']+side,last=row['page']+side,body=f'<tei:div corresp="{urn}">'+pb(row['page']+side,sigil=SIGIL)+'<tei:p>'+xml(row[lang])+'</tei:p></tei:div>'))
    return result


def verses(chapter,first,last):
    base=BIBLE+f'psalms/{chapter}/'
    return f'<j:transclude target="{base}{first}" targetEnd="{base}{last}"/>'


def units(project):
    side=int(project!=PROJECT_HE);lang=('he','en')[side];result=[]
    def add(name,urn,he,en,first,last,body,*,printed=False,gate=None):
        head=(f'<tei:head xml:lang="{lang}">'+(he,en)[side]+'</tei:head>') if printed else editorial_head(lang,he,en)
        if gate is not None:
            body=cond('hallel_occasion', note='On Hallel occasions, except in a house of mourning during shiv‘ah:', fs=gate)+head+body+endcond('hallel_occasion')
            head=''
        result.append(dict(name=name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+head+body+'</tei:div>'))
    for chapter,count,first,last in [(113,9,565,567),(114,8,567,567),(115,18,567,569),(116,19,569,569),(117,2,571,571),(118,29,571,573)]:
        if chapter in (115,116):
            first_label=instruction(f'Psalm {chapter}:1-11') if side else ''
            second_label=instruction(f'Psalm {chapter}:12-{count}') if side else ''
            body=conditional('full_'+str(chapter),PAGES[str(first+side)]['rubrics'][0],feature(FS,'full'),first_label+verses(chapter,1,11))+second_label+verses(chapter,12,count)
        elif chapter==118:
            body=(instruction('Psalm 118:1-4') if side else '')+instruction('Responsively')+verses(118,1,4)+(instruction('Psalm 118:5-29') if side else '')+verses(118,5,20)
            body+=instruction('Each verse is chanted twice:')+verses(118,21,24)+instruction('Responsively')
            body+=''.join(transclude(ROOT+'/anna/'+part) for part in ['hoshiah','hoshiah','hatzlichah','hatzlichah'])
            body+=instruction('Each verse is chanted twice:')+verses(118,26,29)
        else:body=transclude(BIBLE+'psalms/'+str(chapter))
        add('hallel_psalm_'+str(chapter),ROOT+'/psalm_'+str(chapter),'תהלים '+str(chapter),'Psalm '+str(chapter),first,last,body,printed=bool(side and chapter in (113,114,117)))
    body=transclude(ROOT+'/blessing')+''.join(transclude(ROOT+'/psalm_'+str(c)) for c in range(113,119))+transclude(ROOT+'/yehalelukha')
    add('hallel',ROOT,'הַלֵּל','HALLEL',565,573,body,printed=True)
    # On Rosh Hodesh during Hanukkah, full Hallel and Full Kaddish coexist.
    full='<j:any>'+holiday('rosh-hodesh',2)+feature(AGG,'yom-tov')+feature(AGG,'chol-hamoed')+'</j:any>'
    following=conditional('full_kaddish','Full-Kaddish on Rosh Ḥodesh and festivals:',full,kaddish(full=True))
    half='<j:all>'+holiday('hanukkah',8)+'<j:none>'+full+'</j:none></j:all>'
    following+=conditional('half_kaddish','Half-Kaddish on Ḥanukkah:',half,kaddish())
    add('hallel_kaddish',SERVICE+'/kaddish','קדיש לאחר הלל','Kaddish after Hallel',573,573,conditional('minyan','When a minyan holds service:',MINYAN,following))
    scope='<j:all>'+feature(FS,'recite')+'<j:none>'+MOURNING+'</j:none></j:all>'
    body=instruction(PAGES[str(565+side)]['rubrics'][0])
    body+=transclude(ROOT)+transclude(SERVICE+'/kaddish')
    # Preserve the book's continuation directions outside the reusable Hallel.
    from .notes_motzaei_shabbat import xml as note_xml
    body+='<tei:note type="instruction" xml:lang="en">'+note_xml(PAGES[str(573+side)]['rubrics'][-1])+'</tei:note>'
    add('hallel_service',SERVICE,'סדר הלל','Hallel service',565,573,body,gate=scope)
    return tuple(result)
