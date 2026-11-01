"""Sabbath/festival Shacharit through Half Kaddish, printed 299–336.

The Reader's entry points within Nishmat are performance rubrics, not boundaries
of Shacharit or Pesukei dezimrah. Whole-prayer occasion gates live in the callers.
"""
import re
from .common import AGG, feature, PRAYER, SIDDUR, PROJECT_HE, SERVICE, cond, endcond, pb
from .conclusion import BIBLE, instruction, transclude, text_xml, MINYAN
from .milestones import Correspondences, marked
from .shacharit_end import editorial_head
from . import shabbat_pesukei_data as data

ROOT = SIDDUR+'shabbat/shacharit'
PESUKEI = ROOT+'/pesuqei_dezimrah'
SIGIL = '1949 shabbat/shacharit/pesuqei_dezimrah'
NISHMAT = PRAYER+'nishmat'
HAEL = PRAYER+'hael_betaatzumot'
SHOKHEN = PRAYER+'shokhen_ad'
BEFI = PRAYER+'befi_yesharim'
BEMAKHALOT = PRAYER+'uvemaqhalot'
REPEAT91 = PESUKEI+'/psalm_91_repeat'
OLD_REFERENCES = {
 'torah_vetiggaleh': ('psalms/19/8','psalms/19/9'),
 'leil_shabbat_guard_text': ('psalms/91/11',),
 'hoshiah_et_ammekha': ('psalms/33/20','psalms/33/21','psalms/33/22'),
 'yehi_khevod': ('psalms/135/13','psalms/33/10','psalms/33/11','psalms/33/9','psalms/135/4'),
 'barukh_adonai': ('psalms/135/21',),
}
RANGES = {
 'mizmor_shir_chanukat_habayit':(299,299), 'kaddish_yatom':(299,301),
 'hareini_mezammen':(301,301),'barukh_sheamar':(301,301),'hodu':(301,303),
 'romemu':(303,303),'vehu_rachum':(303,305),'hoshiah_et_ammekha':(305,305),
 'qabbalat_psalm_92':(317,317),'conclusion_psalm_93':(317,317),
 'yehi_khevod':(319,319),'ashrei':(319,321),'psalm_146':(321,323),
 'psalm_147':(323,323),'psalm_148':(323,325),'psalm_149':(325,325),'psalm_150':(325,325),
 'barukh_adonai':(327,327),'vayevarekh_david':(327,327),'attah_hu':(327,327),
 'vayyosha':(329,329),'az_yashir':(329,329),'ki_ladonai':(331,331),'yishtabbach':(335,335),
 'kaddish_chatzi':(335,335),
}


def xml(value):
    return text_xml(value,SIGIL).replace('|','<tei:lb/>').replace('{reader}',instruction('Reader')+' ')


def shared(lang,prayers):
    result=[dict(p) for p in prayers]; side=int(lang=='en')
    for p in result:
        # The new complete chapters own their biblical verse addresses. Earlier
        # collected quotations retain their actual wording and local milestones.
        for ref in OLD_REFERENCES.get(p['name'],()):
            source=BIBLE+ref; local=p['urn']+'/'+ref.replace('/','_')
            pattern=r'(<tei:milestone\b[^>]*corresp="'+re.escape(source)+r'"[^>]*/>)(.*?)(?=<tei:milestone\b)'
            def move(m):
                return m[1].replace(source,local)+f'<tei:seg source="{source}">'+m[2]+'</tei:seg>'
            p['body'],count=re.subn(pattern,move,p['body'],flags=re.S)
            if count!=1:raise ValueError(f'Expected one earlier {source} in {p["name"]}')
        if p['name'] in RANGES:
            a,b=RANGES[p['name']];p['printings']=(*p.get('printings',()),(a+side,b+side))
        if p['name'] in ('kaddish_derabbanan_yitgaddal','kaddish_derabbanan_yehe_shemeh','kaddish_derabbanan_yitbarakh'):
            p['printings']=(*p.get('printings',()),(299+side,299+side),(335+side,335+side))
    by_name={p['name']:p for p in result}
    def before(name,he,en,page):
        p=by_name[name];anchor=(he,en)[side]
        if p['body'].count(anchor)!=1:raise ValueError(f'Ambiguous page turn {page}: {name}: {anchor!r}')
        p['body']=p['body'].replace(anchor,pb(page+side,sigil=SIGIL)+anchor,1)
    before('kaddish_yatom','יְהֵא שְׁלָמָא','May there be abundant peace',301)
    before('hodu','מְתֵי מִסְפָּר','very few, and strangers',303)
    before('vehu_rachum','סֶּֽלָה.','God of Jacob is our Stronghold.',305)
    before('ashrei','זֵֽכֶר רַב','They spread the fame',321)
    before('psalm_146','פֹּקֵֽחַ עִוְרִים','blind, raises',323)
    before('psalm_148','וַיַּעֲמִידֵם','a law which none',325)
    return result


def prayers(lang):
    side=int(lang=='en');result=[]
    for number,he in data.HE.items():
        urn=BIBLE+f'psalms/{number}';title=f'Psalm {number}' if side else 'תהלים '+{19:'יט',34:'לד',90:'צ',91:'צא',135:'קלה',136:'קלו',33:'לג'}[number]
        first,last=data.PAGES[number]
        body=[f'<tei:div corresp="{urn}"><tei:head xml:lang="{lang}">{title}</tei:head>',pb(first+side,sigil=SIGIL),'<tei:p>'];marks=Correspondences()
        for n,text in enumerate((data.EN if side else data.HE)[number].splitlines(),1):
            if n>1 and number in (34,136):body.append('</tei:p><tei:p>')
            if not side and n==data.READER.get(number):body.append(marks.close()+instruction('Reader'))
            body += [marks.start(urn+'/'+str(n)),xml(text),' ']
        body += [marks.close(),'</tei:p></tei:div>']
        result.append(dict(name='shabbat_pesuqei_psalm_'+str(number),urn=urn,title=title,first=first+side,last=last+side,body=''.join(body)))
    def add(key,urn,he,en,first,last,body):
        result.append(dict(name='shabbat_pesuqei_'+key+'_text',urn=urn,title=(he,en)[side],first=first+side,last=last+side,body=f'<tei:div corresp="{urn}">'+body+'</tei:div>'))
    # The English does not translate the repeated final verse of Psalm 91.
    repeat='' if side else '<tei:p>'+marked(REPEAT91+'/text',f'<tei:seg source="{BIBLE}psalms/91/16">'+xml(data.HE[91].splitlines()[-1])+'</tei:seg>',unit='verse')+'</tei:p>'
    add('psalm_91_repeat',REPEAT91,'ארך ימים','Repeated final verse of Psalm 91',311,311,repeat)
    body=''
    for i,(key,he,en) in enumerate(data.NISHMAT):
        value=xml((he,en)[side])
        if key=='al_ken':
            quotes=[('psalms/35/10','כָּל עַצְמוֹתַי','מִגֹּזְלוֹ.','All my being','rob him.'),
                    ('psalms/103/1','לְדָוִד,','קָדְשׁוֹ.','by David:','holy name.')]
            for ref,hs,he_,es,ee in quotes:
                start=value.index((hs,es)[side]);end=value.index((he_,ee)[side],start)+len((he_,ee)[side])
                # Complete biblical verses nested in this liturgical paragraph.
                value=value[:start]+marked(BIBLE+ref,value[start:end],unit='verse')+value[end:]
        if i==0:value=pb(331+side,sigil=SIGIL)+value
        # Hebrew opening and elohei are one printed paragraph; the English splits.
        if side or i in (0,2):body+='<tei:p>'
        body+=marked(NISHMAT+'/'+key,value)+' '
        if side or i in (1,3):body+='</tei:p>'
    add('nishmat',NISHMAT,'נשמת כל חי','Nishmath',331,333,body)
    add('hael',HAEL,'האל בתעצמות','God in thy tremendous power',333,333,'<tei:p>'+xml(data.HAEL[side])+'</tei:p>')
    for (key,he,en),urn,title in zip(data.SHOKHEN,(SHOKHEN,BEFI,BEMAKHALOT),('Shochen Ad','Befi Yesharim','Uvmakhalot')):
        value=xml((he,en)[side])
        if key=='opening':
            start=value.index(('רַנְּנוּ','Rejoice')[side]);end=len(value)-(1 if side else 0)
            quotation=f'<tei:seg source="{BIBLE}psalms/33/1">'+value[start:end]+'</tei:seg>'
            value=value[:start]+marked(SHOKHEN+'/psalms_33_1',quotation)+value[end:]
        add(key,urn,he.split(',')[0],title,333,335 if key=='uvemaqhalot' else 333,'<tei:p>'+value+'</tei:p>')
    return result


def declaration():
    # The shared service serves both Shabbat and festivals; don't force a date.
    svc=''.join(f'<tei:f name="{n}"><tei:binary value="{str(n=="shaharit").lower()}"/></tei:f>' for n in ('shaharit','minha','maariv','musaf','neila','slihot'))
    return f'<j:declare xml:id="shabbat_shacharit_service"><tei:fs type="{SERVICE}">{svc}</tei:fs></j:declare>'


def units(project,by_name):
    lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');result=[]
    def tr(name):return transclude(by_name[name]['urn'])
    def gate(cid,body):
        cid='shabbat_pesuqei_'+cid
        return cond(cid,note='With a minyan:',fs=MINYAN)+body+endcond(cid)
    def add(key,he,en,first,last,body,*,printed=False):
        urn=ROOT+('/'+key if key else '')
        heading=(f'<tei:head xml:lang="{lang}">{(he,en)[side]}</tei:head>' if printed else editorial_head(lang,he,en))
        result.append(dict(name='shabbat_shacharit'+('_'+key.replace('/','_') if key else ''),urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body=f'<tei:div corresp="{urn}">'+heading+pb(first+side,sigil=SIGIL)+body+'</tei:div>'))
    add('opening/kaddish','קדיש יתום','MOURNERS’ KADDISH',299,301,gate('yatom',tr('kaddish_yatom')),printed=True)
    add('opening','פתיחת שחרית','Morning service opening',299,301,tr('mizmor_shir_chanukat_habayit')+transclude(ROOT+'/opening/kaddish'))
    add('pesuqei_dezimrah/nishmat','נשמת','NISHMATH',331,335,
        transclude(NISHMAT)+cond('nishmat_reader_festival', fs=feature(AGG, 'yom-tov'))
        +instruction('On festivals the Reader begins here:')+endcond('nishmat_reader_festival')+transclude(HAEL)
        +cond('nishmat_reader_shabbat', fs='<j:all>'+feature(AGG, 'shabbat')+'<j:none>'+feature(AGG, 'yom-tov')+'</j:none></j:all>')
        +instruction('On Sabbaths the Reader begins here:')+endcond('nishmat_reader_shabbat')+transclude(SHOKHEN)+transclude(BEFI)+transclude(BEMAKHALOT)+tr('yishtabbach'),printed=True)
    add('pesuqei_dezimrah/kaddish','חצי קדיש','Half Kaddish',335,335,gate('chatzi',tr('kaddish_chatzi')))
    body=''.join(tr(k) for k in ('hareini_mezammen','barukh_sheamar','hodu','romemu','vehu_rachum','hoshiah_et_ammekha'))
    for n in (19,34,90,91,135,136,33,92,93):
        body+=transclude(BIBLE+f'psalms/{n}')
        if n==91:body+=transclude(REPEAT91)
    body+=''.join(tr(k) for k in ('yehi_khevod','ashrei','psalm_146','psalm_147','psalm_148','psalm_149','psalm_150','barukh_adonai','vayevarekh_david','attah_hu','vayyosha','az_yashir','ki_ladonai'))
    body+=transclude(PESUKEI+'/nishmat')+transclude(PESUKEI+'/kaddish')
    add('pesuqei_dezimrah','פסוקי דזמרה','Pesukei Dezimrah',301,335,body)
    add('','שַׁחֲרִית לְשַׁבָּת וְיוֹם טוֹב','MORNING SERVICE FOR SABBATHS AND FESTIVALS',299,335,
        declaration()+instruction('The Preliminary Morning Service (pages 11–48) is read as on weekdays.')
        +transclude(SIDDUR+'all/shacharit/birkhot_hashachar')+transclude(ROOT+'/opening')+transclude(PESUKEI)
        +'<j:endDeclare target="#shabbat_shacharit_service"/>',printed=True)
    return tuple(result)
