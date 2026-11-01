"""Sefirat HaOmer and Akdamut, printed637–654 (IA n661–678)."""
from .common import PRAYER, POEM, SIDDUR, PROJECT_HE, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .festival import conditional
from .milestones import marked
from .shacharit_end import editorial_head
from .tachanun_conditions import holiday
from .omer_akdamut_data import ROWS, AKDAMUT

OMER = PRAYER+'sefirat_haomer'
AKDAMUT_URN = POEM+'aqdamut'
OMER_SERVICE = SIDDUR+'sefirat_haomer'
AKDAMUT_SERVICE = SIDDUR+'regalim/aqdamut'
SIGIL = '1949 omer and akdamut'
SEASON = holiday('omer',49)
OMER_RUBRIC = 'After Ma‘ariv—from the second night of Pesaḥ until the night before Shavuoth'
AKDAMUT_RUBRIC = 'Chanted on the first day of Shavuoth before the reading of the Torah'
URNS = {r['key']: OMER+'/'+r['key'] for r in ROWS}


def xml(value):
    return text_xml(value,SIGIL)


def c(key,rubric,condition,body):
    return conditional('omer_aqdamut_'+key,rubric,condition,body)


def quotation(value,key,lang):
    """Retain each occurrence's punctuation and the two biblical source boundaries."""
    starts=('וּסְפַרְתֶּם','עַד מִמָּחֳרַת') if lang=='he' else ('You shall count','you shall count fifty days')
    a=value.index(starts[0]); b=value.index(starts[1],a)
    end=value.index('יוֹם.',b)+len('יוֹם.') if lang=='he' else value.index('week.',b)+len('week.')
    return (xml(value[:a])+marked(URNS[key]+'/leviticus_23_15',f'<tei:seg source="{BIBLE}leviticus/23/15">'+xml(value[a:b])+'</tei:seg>',unit='verse')
        +marked(URNS[key]+'/leviticus_23_16',f'<tei:seg source="{BIBLE}leviticus/23/16">'+xml(value[b:end])+'</tei:seg>',unit='verse')+xml(value[end:]))


def prayers(lang):
    side=int(lang=='en');out=[]
    for r in ROWS:
        key=r['key']
        if key.startswith('day_'):continue
        value=r[lang];urn=URNS[key]
        if key in ('preparation','ribbono'):
            content='<tei:p>'+quotation(value,key,lang)+'</tei:p>'
        elif key=='psalm_67':
            # This printing has its own wording and apparatus. Biblical identity is
            # carried on every quoted verse, independently of occurrence addresses.
            verses=r[lang+'_verses']
            content='<tei:p>'+' '.join(marked(urn+'/'+str(i),f'<tei:seg source="{BIBLE}psalms/67/{i}">'+xml(v)+'</tei:seg>',unit='verse') for i,v in enumerate(verses,1))+'</tei:p>'
        elif key=='anna_bekhoach':
            content='<tei:lg>'+'\n'.join('<tei:l>'+marked(urn+'/'+str(i),f'<tei:seg source="{POEM}anna_bekhoach/{i}">'+xml(line)+'</tei:seg>',unit='stanza')+'</tei:l>' for i,line in enumerate(value.splitlines(),1))+'</tei:lg>'
        else:content='<tei:p>'+xml(value)+'</tei:p>'
        out.append(dict(name='omer_'+key+'_text',urn=urn,title=key.replace('_',' '),first=r['page']+side,last=r['page']+side,
            body=f'<tei:div corresp="{urn}">'+pb(r['page']+side,sigil=SIGIL)+content+'</tei:div>'))
    return out


def units(project):
    side=int(project!=PROJECT_HE);lang=('he','en')[side];out=[]
    def add(name,urn,he,en,first,last,body,printed=False, heading=True):
        head='<tei:head>'+((he,en)[side])+'</tei:head>' if printed else editorial_head(lang,he,en)
        if not heading:head=''
        out.append(dict(name=name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+head+body+'</tei:div>'))
    counts=''
    for r in ROWS:
        if not r['key'].startswith('day_'):continue
        day=int(r['key'][4:])
        value='<tei:p>'+pb(r['page']+side,sigil=SIGIL)+marked(URNS[r['key']],xml(r[lang]),unit='day')+'</tei:p>'
        counts+=c('day_'+str(day),'On day '+str(day)+' of the Omer:',feature('opensiddur:holiday','omer',f'<tei:numeric value="{day}"/>'),value)
    add('omer_counting',OMER+'/counting','ספירת היום','Counting the day',637,643,counts)
    closing=instruction('After the counting:')+transclude(URNS['harachaman'])
    closing+='<tei:div>'+('<tei:head>Psalm 67</tei:head>' if side else '<tei:head>תהלים סז</tei:head>')+transclude(URNS['psalm_67'])+'</tei:div>'
    closing+=''.join(transclude(URNS[k]) for k in ('anna_bekhoach','barukh_shem','ribbono'))
    add('omer_after_counting',OMER+'/after_counting','לאחר הספירה','After the counting',643,645,closing,heading=False)
    body=transclude(URNS['preparation'])+transclude(URNS['blessing'])+transclude(OMER+'/counting')+transclude(OMER+'/after_counting')
    add('sefirat_haomer',OMER,'סְפִירַת הָעֹמֶר','COUNTING OF THE OMER',637,645,body,True)
    # Only callers gate the whole section; a direct prayer URN remains reusable.
    add('sefirat_haomer_service',OMER_SERVICE,'סדר ספירת העומר','Counting of the Omer',637,645,c('season',OMER_RUBRIC,SEASON,transclude(OMER)),heading=False)
    body=''
    previous=None
    for row in AKDAMUT:
        if row['page']!=previous:body+=pb(row['page']+side,sigil=SIGIL);previous=row['page']
        pair=row['pair'];lines=row[lang].splitlines()
        body+='<tei:lg>'+marked(AKDAMUT_URN+'/'+str(pair),''.join('<tei:l>'+xml(line)+'</tei:l>' for line in lines),unit='stanza')+'</tei:lg>'
    add('aqdamut',AKDAMUT_URN,'אַקְדָּמוּת','AKDAMUTH',647,653,body,True)
    add('aqdamut_service',AKDAMUT_SERVICE,'אקדמות לשבועות','Akdamut for Shavuot',647,653,c('shavuot',AKDAMUT_RUBRIC,holiday('shavuot'),transclude(AKDAMUT_URN)),heading=False)
    return tuple(out)
