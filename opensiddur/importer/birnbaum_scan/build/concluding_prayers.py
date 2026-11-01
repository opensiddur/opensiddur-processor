"""Marriage, meals, blessings, bedtime and Israel, IA n777–n814."""
import re
import unicodedata
from .common import PRAYER, POEM, SIDDUR, PROJECT_HE, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .festival import conditional
from .tachanun_conditions import holiday
from .shacharit_end import editorial_head
from .milestones import marked
from .notes_motzaei_shabbat import xml as note_xml
from .concluding_prayers_data import ROWS, RUBRICS

ROOT = SIDDUR+'concluding_prayers'
MARRIAGE = SIDDUR+'marriage'
SEVEN = PRAYER+'sheva_berakhot'
GRACE = PRAYER+'birkat_hamazon'
MEALS = SIDDUR+'meals'
ABRIDGED = PRAYER+'meein_shalosh'
BLESSINGS = SIDDUR+'berakhot/various'
BED = SIDDUR+'qeriat_shema_al_hamittah'
CHILD = BED+'/yeladim'
ISRAEL = PRAYER+'tefillah_lishlom_medinat_yisrael'
SIGIL='1949 concluding_prayers'
BY_KEY={r['key']:r for r in ROWS}
URNS={r['key']:ROOT+'/text/'+r['key'] for r in ROWS}
URNS.update({'mi_addir':POEM+'mi_addir','erusin':PRAYER+'birkat_erusin',
 'ring':PRAYER+'harei_at_mequddeshet','devai_haser':POEM+'devai_haser',
 'hamotzi':PRAYER+'hamotzi','borei_nefashot':PRAYER+'borei_nefashot',
 'hamappil':PRAYER+'hamappil','psalm137':BIBLE+'psalms/137',
 'bed_psalm3':BED+'/psalm3','hamalakh':BIBLE+'genesis/48/16',
 'bed_exodus':BIBLE+'exodus/15/26','bed_zechariah':BIBLE+'zechariah/3/2',
 'bed_rigzu':BIBLE+'psalms/4/5'})
for k in ('shehakol_bara','yotzer_haadam','asher_yatzar_haadam','sos_tasis','sammeach_tesammach','asher_bara'):URNS[k]=SEVEN+'/'+k
for k,suffix in {'hazan':'hazan','nodeh':'nodeh','veal_hakol':'veal_hakol','rachem':'rachem',
 'retzeh_grace':'retzeh_vehachalitzenu','uveneh':'uveneh_yerushalayim','hatov':'hatov_vehametiv',
 'bamarom':'bamarom','barukh_hu':'zimmun/barukh_hu','zimmun_leader':'zimmun/nevarekh',
 'zimmun_response':'zimmun/barukh_sheakhalnu','harachaman_reign':'harachaman/yimlokh',
 'harachaman_worship':'harachaman/yitbarakh','harachaman_praise':'harachaman/yishtabbach',
 'harachaman_livelihood':'harachaman/yefarnesenu','harachaman_yoke':'harachaman/yishbor_ullenu',
 'harachaman_house':'harachaman/yishlach_berakhah','harachaman_elijah':'harachaman/yishlach_lanu',
 'harachaman_shabbat':'harachaman/yanchilenu_shabbat','harachaman_festival':'harachaman/yanchilenu_tov',
 'harachaman_messiah':'harachaman/yezakkenu'}.items():URNS[k]=GRACE+'/'+suffix
for k in ('rc','rh','sukkot','self','hosts','all'):URNS['harachaman_'+k]=GRACE+'/harachaman/'+k
for r in ROWS:
 k=r['key']
 if k.startswith('meein_'):URNS[k]=ABRIDGED+'/'+k.removeprefix('meein_')
 if k.startswith('israel_'):URNS[k]=ISRAEL+'/'+k.removeprefix('israel_')
for k,s in {'mezonot':'borei_minei_mezonot','shehakol':'shehakol_nihyeh_bidvaro',
 'haetz':'borei_peri_haetz','haadamah':'borei_peri_haadamah','mezuzah':'liqboa_mezuzah',
 'creation':'oseh_maaseh_vereshit','storm':'shekocho_ugevurato','rainbow':'zokher_haberit',
 'ocean':'sheasah_et_hayam_hagadol','beauty':'shekakhah_lo_beolamo','blossoms':'shelo_chissar_beolamo',
 'ruler':'shenatan_mikevodo','appearance':'meshanneh_haberiyyot','torah_sage':'shechalaq_mechokhmato',
 'secular_sage':'shenatan_mechokhmato','bad_news':'dayyan_haemet','good_news':'hatov_vehametiv'}.items():URNS['blessing_'+k]=PRAYER+s
REUSE={'marriage_wine':PRAYER+'borei_peri_hagafen','meal_hands':PRAYER+'al_netilat_yadayim',
 'blessing_wine':PRAYER+'borei_peri_hagafen','blessing_besamim':PRAYER+'borei_minei_vesamim',
 'blessing_shehecheyanu':PRAYER+'shehecheyanu','blessing_bread':URNS['hamotzi'],
 'zimmun_invitation':SIDDUR+'lifecycle/text/milah_grace_invitation',
 'zimmun_name':SIDDUR+'lifecycle/text/milah_grace_response',
 'bed_el_melekh':PRAYER+'torah_tzivvah/el_melekh_neeman',
 'bed_shema':BIBLE+'deuteronomy/6/4','child_shema':BIBLE+'deuteronomy/6/4',
 'bed_barukh_shem':PRAYER+'shema/barukh_shem','child_barukh_shem':PRAYER+'shema/barukh_shem',
 'bed_psalm91':SIDDUR+'lifecycle/text/haderekh_psalm91'}
REUSE['child_veahavta']=URNS['bed_veahavta']
URNS.update(REUSE)
SHABBAT=feature('opensiddur:day-of-week','hebrew-day','<tei:numeric value="7"/>')
RC=holiday('rosh-hodesh',2)
RH=holiday('rosh-hashana',2)
FESTIVAL='<j:any>'+holiday('pesah',8)+holiday('shavuot',2)+holiday('sukkot',7)+holiday('shmini-atzeret',2)+'</j:any>'
YOMTOV=feature('opensiddur:holiday-aggregate','yom-tov')
MUSAF='<j:any>'+SHABBAT+RC+RH+FESTIVAL+holiday('yom-kippur')+'</j:any>'
MINYAN=feature('opensiddur:quorum','minyan')
DAY_CHOICES=(('rc',RC,'Rosh Ḥodesh'),('pesach',holiday('pesah',8),'Pesaḥ'),('shavuot',holiday('shavuot',2),'Shavuoth'),('rh',RH,'Rosh Hashanah'),('sukkot',holiday('sukkot',7),'Sukkoth'),('shemini','<j:any>'+holiday('shmini-atzeret',2)+'</j:any>','Shemini Atzereth / Simḥath Torah'))

def context(name,value=None):
 return feature('opensiddur:meal-context',name,('<tei:symbol value="'+value+'"/>') if value else '<tei:binary value="true"/>')

def xml(raw):return text_xml(raw.replace("\n", "___PARA___"),SIGIL)

def opt(key,label,expr,body):return conditional('concluding_'+key,label,expr,body)

def verse_parts(key,raw,lang):
 book,first,he,en=VERSE_STARTS[key];starts=he if lang=='he' else en
 offsets=[];at=0
 for start in starts:
  start=unicodedata.normalize('NFC',start);at=raw.index(start,at);offsets.append(at);at+=len(start)
 assert offsets[0]==0,(key,lang)
 offsets.append(len(raw));result=[]
 for i,(a,b) in enumerate(zip(offsets,offsets[1:]),first):
  source=BIBLE+book+'/'+str(i);canonical=key=='psalm137' or (key=='bed_psalm3' and i!=9)
  urn=source if canonical else URNS[key]+'/'+str(i)
  text=xml(raw[a:b]);text=text if canonical else '<tei:seg source="'+source+'">'+text+'</tei:seg>'
  result.append(marked(urn,text,unit='verse'))
 return ''.join(result)

VERSE_STARTS={
 'psalm137':('psalms/137',1,['עַל נַהֲרוֹת','עַל עֲרָבִים','כִּי שָׁם','אֵיךְ','אִם אֶשְׁכָּחֵךְ','תִּדְבַּק','זְכֹר','בַּת בָּבֶל','אַשְׁרֵי שֶׁיֹּאחֵז'],['By the rivers','Upon the willows','when our captors','How shall','If ever','May my tongue','Remember,','O Babylon','Happy be he who takes']),
 'psalm126':('psalms/126',1,['שִׁיר','אָז יִמָּלֵא','הִגְדִּיל יְיָ לַעֲשׂוֹת עִמָּֽנוּ','שׁוּבָה','הַזֹּרְעִים','הָלוֹךְ'],['A Pilgrim','Our mouth','The Lord had','Restore','Those are','Sadly']),
 'bed_psalm3':('psalms/3',2,['יְיָ,','רַבִּים אוֹמְרִים','וְאַתָּה','קוֹלִי','אֲנִי','לֹא אִירָא','קוּמָה','לַיְיָ'],['O Lord,','Many are saying','But thou','When I call','When I lie','I am not','Arise','Salvation']),
 'bed_psalm128':('psalms/128',1,['שִׁיר','יְגִֽיעַ','אֶשְׁתְּךָ','הִנֵּה','יְבָרֶכְךָ','וּרְאֵה בָנִים'],['A Pilgrim','When you eat','Your wife','Behold','The Lord bless','may you live']),
 'bed_veahavta':('deuteronomy/6',5,['וְאָהַבְתָּ','וְהָיוּ','וְשִׁנַּנְתָּם','וּקְשַׁרְתָּם','וּכְתַבְתָּם'],['You shall love','And these words','You shall teach','You shall bind','You shall inscribe']),
 'bed_solomon':('song_of_songs/3',7,['הִנֵּה','כֻּלָּם'],['Solomon’s','All of them']),
 'bed_kohanim':('numbers/6',24,['יְבָרֶכְךָ','יָאֵר','יִשָּׂא'],['May the Lord bless','may the Lord countenance','may the Lord favor']),
}
BIBLICAL={'bed_vihi_noam':'psalms/90/17','bed_psalm91_repeat':'psalms/91/16','bed_guardian':'psalms/121/4','child_guardian':'psalms/121/4','child_commit':'psalms/31/6','child_salvation':'genesis/49/18'}

RANGES={
 'bed_veahavta':(BIBLE+'deuteronomy/6/5',BIBLE+'deuteronomy/6/9'),
 'bed_barukh':(SIDDUR+'chol/arvit/barukh_adonai/by_day',SIDDUR+'chol/arvit/barukh_adonai/eloheinu'),
 'child_commit':(BIBLE+'psalms/31/6',None),
 'child_salvation':(BIBLE+'genesis/49/18',None),
}

def range_ref(first,last=None):
 return '<j:transclude type="external" target="'+first+'"'+(' targetEnd="'+last+'"' if last else '')+'/>'

# Each entry identifies a bounded quotation; None terminates at the end of the
# paragraph. Local verse witnesses preserve this occurrence's wording.
QUOTATIONS={
 'veal_hakol':[('deuteronomy/8/10','וְאָכַלְתָּ','“When you','בָּרוּךְ אַתָּה','Blessed art')],
 'israel_3':[('deuteronomy/30/4','אִם יִהְיֶה','“Even if','וֶהֱבִיאֲךָ','The Lord your'),('deuteronomy/30/5','וֶהֱבִיאֲךָ','The Lord your',None,None)],
 'bed_salvation':[('genesis/49/18','לִישׁוּעָתְךָ','For thy salvation','קִוִּֽיתִי, יְיָ,','I hope, O Lord')],
 'grace_verses':[
 ('psalms/34/10','יְראוּ','Revere','כְּפִירִים','Lions'),
 ('psalms/34/11','כְּפִירִים','Lions','הוֹדוּ','Give thanks'),
 ('psalms/118/1','הוֹדוּ','Give thanks','פּוֹתֵֽחַ','Thou openest'),
 ('psalms/145/16','פּוֹתֵֽחַ','Thou openest','בָּרוּךְ הַגֶּֽבֶר','Blessed is'),
 ('jeremiah/17/7','בָּרוּךְ הַגֶּֽבֶר','Blessed is','נַֽעַר','I have'),
 ('psalms/37/25','נַֽעַר','I have','יְיָ עֹז','The Lord will'),
 ('psalms/29/11','יְיָ עֹז','The Lord will',None,None)],
}

def quotations(key,raw,lang):
 result='';offset=0
 for ref,he,en,he_end,en_end in QUOTATIONS[key]:
  start=unicodedata.normalize('NFC',he if lang=='he' else en)
  end=he_end if lang=='he' else en_end
  a=raw.index(start,offset);b=raw.index(unicodedata.normalize('NFC',end),a+len(start)) if end else len(raw)
  quoted='<tei:seg source="'+BIBLE+ref+'">'+xml(raw[a:b])+'</tei:seg>'
  if key=='grace_verses':quoted=marked(URNS[key]+'/'+ref.replace('/','_'),quoted,unit='verse')
  result+=xml(raw[offset:a])+quoted;offset=b
 return result+xml(raw[offset:])


def raw_xml(key,raw,lang):
 if key in ('grace_chanukah','grace_purim','retzeh_grace','grace_yaaleh_open','grace_yaaleh_end'):raw=raw.removeprefix('(').removesuffix(')')
 if key in VERSE_STARTS:return verse_parts(key,raw,lang)
 if key in QUOTATIONS:return quotations(key,raw,lang)
 if key=='magdil' and lang=='he':
  tail=raw.split(') ',1)[1]
  return opt('magdil','On days without Musaf:','<j:none>'+MUSAF+'</j:none>',xml('מַגְדִּיל'))+' '+opt('migdol','On the days when Musaf is recited:',MUSAF,xml('מִגְדּוֹל'))+' '+xml(tail)
 value=xml(raw)
 if key in ('zimmun_leader','zimmun_response'):
  token='אֱלֹהֵֽינוּ' if lang=='he' else 'our';token=unicodedata.normalize('NFC',token)
  value=value.replace('('+token+')',opt(key+'_minyan','With a minyan:',MINYAN,token))
 extras={'harachaman_self':[('wife-and-children','Include wife and children:')],
  'harachaman_hosts':[('father-is-host','When the host is your father:'),('mother-is-host','When the hostess is your mother:')],
  'bamarom':[('guest','When a guest:')]}
 if key in extras:
  for (name,label),m in zip(extras[key],list(re.finditer(r'\(([^()]*)\)',value))):
   value=value.replace(m.group(0),opt(key+'_'+name,label,context(name),m.group(1)),1)
 if key in BIBLICAL:value='<tei:seg source="'+BIBLE+BIBLICAL[key]+'">'+value+'</tei:seg>'
 return value


def shared(lang,prayers):
 result=[dict(p) for p in prayers];side=int(lang=='en')
 for p in result:
  pages={r.get('en_page',r['page']+1) if side else r['page'] for r in ROWS if r['key'] in REUSE and ('corresp="'+REUSE[r['key']]+'"') in p['body']}
  if p['urn']==POEM+'adon_olam':
   pages.add(785+side)
   incipits=('adon_olam','leet_naasah','veacharei','vehu_hayah','vehu_echad','beli_reshit','vehu_eli','vehu_nissi','beyado','veim_ruchi')
   lines=iter(incipits)
   p['body']=re.sub(r'<tei:l>(.*?)</tei:l>',lambda m:'<tei:l>'+marked(POEM+'adon_olam/'+next(lines),m[1],unit='stanza')+'</tei:l>',p['body'],flags=re.S)
  if pages:p['printings']=(*p.get('printings',()),*((p,p) for p in sorted(pages)))
 return result


def prayers(lang):
 result=[];side=int(lang=='en')
 for r in ROWS:
  key=r['key']
  if key in REUSE or key.startswith(('bed_adon_','meein_','grace_yaaleh_')):continue
  page=r.get('en_page',r['page']+1) if side else r['page'];raw=r[lang]
  value=raw_xml(key,raw,lang)
  if key not in VERSE_STARTS and key!='grace_verses' and '\n' not in raw:value=marked(URNS[key],value,unit='verse' if key in BIBLICAL or ':bible:' in URNS[key] else 'prayer-part')
  poem=key in ('mi_addir','devai_haser')
  if poem:value=marked(URNS[key],''.join('<tei:l>'+xml(line)+'</tei:l>' for line in raw.splitlines()),unit='stanza')
  value=value.replace('___PARA___','</tei:p><tei:p>')
  body='<tei:p>'+pb(page,sigil=SIGIL)+value+'</tei:p>'
  if poem:body='<tei:lg>'+pb(page,sigil=SIGIL)+value+'</tei:lg>'
  if key in RANGES:
   first,last=RANGES[key]
   body='<tei:div corresp="'+URNS[key]+'"><tei:p>'+pb(page,sigil=SIGIL)+'</tei:p>'+range_ref(first,last)+'</tei:div>'
  if (key in VERSE_STARTS and key not in RANGES) or key=='grace_verses' or ('\n' in raw and not poem):body='<tei:div corresp="'+URNS[key]+'">'+body+'</tei:div>'
  psalm_titles={'psalm137':('קלז','137'),'psalm126':('קכו','126'),'bed_psalm3':('ג','3'),'bed_psalm128':('קכח','128')}
  if key in psalm_titles:
   he_number,en_number=psalm_titles[key]
   title='תהלים '+he_number if lang=='he' else 'PSALM '+en_number
   body=body.replace('><tei:p>','><tei:head>'+title+'</tei:head><tei:p>',1)
  result.append(dict(name='concluding_'+key+'_text',urn=URNS[key],title=key.replace('_',' '),first=page,last=max([page]+[int(x) for x in re.findall(r'\{pb:(\d+)\}',raw)]),body=body))
 return result


def units(project):
 lang='he' if project==PROJECT_HE else 'en';side=int(lang=='en');out=[]
 def p(k,inline=False):
  if k.startswith(('meein_','grace_yaaleh_')):
   row=BY_KEY[k];page=row.get('en_page',row['page']+1) if side else row['page']
   text=pb(page,sigil=SIGIL)+marked(URNS[k],raw_xml(k,row[lang],lang))
   return text if inline else '<tei:p>'+text+'</tei:p>'
  return transclude(URNS[k],inline=inline)
 def rubric(k):return '<tei:note type="instruction" xml:lang="en">'+note_xml(RUBRICS.get(k+'_'+lang,RUBRICS.get(k,'')))+'</tei:note>'
 def add(name,urn,he,en,first,last,body,printed=True):
  head='<tei:head>'+((he,en)[side])+'</tei:head>' if printed else editorial_head(lang,he,en)
  if name in ('grace_harachaman_before','grace_harachaman_after','grace_core','grace_four_blessings'):head=''
  out.append(dict(name=name,urn=urn,title_he=he,title_en=en,pages=(first+side,last+side),body='<tei:div corresp="'+urn+'">'+head+body+'</tei:div>'))
 six=''.join(p(k) for k in ('shehakol_bara','yotzer_haadam','asher_yatzar_haadam','sos_tasis','sammeach_tesammach','asher_bara'))
 add('seven_wedding_blessings',SEVEN,'שבע ברכות','Seven wedding blessings',753,755,p('marriage_wine')+six,False)
 add('wedding_blessings_after_meal',SEVEN+'/after_meal','שבע ברכות אחרי הסעודה','Wedding blessings after the meal',753,755,six+p('marriage_wine'),False)
 marriage=p('mi_addir')+rubric('rabbi')+p('marriage_wine')+p('erusin')+rubric('ring')+p('ring')
 marriage+=opt('seven','With a minyan: '+RUBRICS['seven'],MINYAN,transclude(SEVEN))
 wedding_grace=rubric('leader')+p('devai_haser')+p('wedding_zimmun')+rubric('company_leader')+p('wedding_response')+transclude(GRACE+'/core')
 wedding_grace+=rubric('wedding_grace')+opt('seven_meal','With a minyan:',MINYAN,transclude(SEVEN+'/after_meal'))
 add('wedding_grace',MARRIAGE+'/grace','ברכת המזון לנשואין','GRACE AFTER THE WEDDING MEAL',755,755,wedding_grace)
 add('marriage',MARRIAGE,'נשואין','MARRIAGE SERVICE',753,755,marriage+transclude(MARRIAGE+'/grace'))
 zimmun=rubric('leader')+p('zimmun_invitation')+rubric('company_leader')+p('zimmun_name')+rubric('leader')+p('zimmun_leader')+rubric('company_leader')+p('zimmun_response')+p('barukh_hu')
 add('grace_zimmun',GRACE+'/zimmun','זימון','Zimmun',759,759,zimmun,False)
 yaaleh='<tei:p>'+p('grace_yaaleh_open',True)+' '
 for k,expr,label in DAY_CHOICES:yaaleh+=opt('yaaleh_'+k,label+':',expr,p('grace_yaaleh_'+k,True))+' '
 yaaleh+=p('grace_yaaleh_end',True)+'</tei:p>'
 add('grace_yaaleh_veyavo',GRACE+'/yaaleh_veyavo','יעלה ויבא','Ya’aleh Veyavo',765,765,yaaleh,False)
 core=p('hazan')+p('nodeh')
 for k,expr in [('chanukah',holiday('hanukkah',8)),('purim',holiday('purim-observed'))]:core+=opt('grace_'+k,RUBRICS[k],expr,p('grace_'+k))
 core+=p('veal_hakol')+p('rachem')+opt('retzeh',RUBRICS['retzeh'],SHABBAT,p('retzeh_grace'))
 core+=opt('yaaleh',RUBRICS['yaaleh'],'<j:any>'+RC+RH+FESTIVAL+'</j:any>',transclude(GRACE+'/yaaleh_veyavo'))+p('uveneh')+p('hatov')
 add('grace_four_blessings',GRACE+'/four_blessings','ברכות המזון','The four blessings',759,765,core,False)
 har=''.join(p('harachaman_'+k) for k in ('reign','worship','praise','livelihood','yoke','house','elijah'))
 har+=rubric('variations')+opt('self','At one’s own table:','<j:none>'+context('guest')+'</j:none>',p('harachaman_self'))+opt('hosts','When a guest:',context('guest'),p('harachaman_hosts'))+p('harachaman_all')+p('bamarom')
 har_before=har;har=''
 for k,expr in [('shabbat',SHABBAT),('rc',RC),('festival',YOMTOV),('rh',RH),('sukkot',holiday('sukkot',7))]:har+=opt('har_'+k,RUBRICS['harachaman_'+k],expr,p('harachaman_'+k))
 har+=p('harachaman_messiah')+p('magdil')+p('grace_oseh')+p('grace_verses')
 add('grace_harachaman_before',GRACE+'/harachaman/before_insert','הרחמן','Harachaman',765,767,har_before,False)
 add('grace_harachaman_after',GRACE+'/harachaman/after_insert','הרחמן','Harachaman conclusion',767,769,har,False)
 add('grace_harachaman',GRACE+'/harachaman','הרחמן','Harachaman',765,769,transclude(GRACE+'/harachaman/before_insert')+transclude(GRACE+'/harachaman/after_insert'),False)
 add('grace_core',GRACE+'/core','ברכת המזון','Grace after meals',759,769,transclude(GRACE+'/four_blessings')+transclude(GRACE+'/harachaman'),False)
 add('birkat_hamazon',GRACE,'בִּרְכַּת הַמָּזוֹן','GRACE AFTER MEALS',759,769,
  opt('zimmun',RUBRICS['zimmun'].replace('The word in parentheses is included','The addition is included'),context('zimmun'),transclude(GRACE+'/zimmun'))+rubric('all')+transclude(GRACE+'/core'))
 before=rubric('hands')+p('meal_hands')+rubric('bread')+p('hamotzi')
 add('before_meals',MEALS+'/before','ברכות לפני הסעודה','Before meals',757,757,before,False)
 before_grace=opt('psalm137',RUBRICS['psalm137'],'<j:none>'+SHABBAT+FESTIVAL+RH+'</j:none>',p('psalm137'))
 before_grace+=opt('psalm126',RUBRICS['psalm126'],'<j:any>'+SHABBAT+FESTIVAL+RH+'</j:any>',p('psalm126'))
 add('before_grace',MEALS+'/before_grace','לפני ברכת המזון','Before grace',757,757,before_grace,False)
 abr=rubric('abridged')+p('meein_open')
 for k in ('wine','fruit','cake','cake_wine'):
  abr+=(opt('meein_begin_'+k,k.replace('_',' and ').capitalize()+':',context('meein-shalosh-food',k),p('meein_begin_'+k)) if lang=='he' else p('meein_begin_'+k))
 abr+=p('meein_body')
 for k,expr in [('shabbat',SHABBAT),('rc',RC),('rh',RH)]:abr+=opt('meein_'+k,RUBRICS['meein_'+k],expr,p('meein_'+k))
 fest='<tei:p>'+p('meein_festival',True)+' '
 for k,expr,label in DAY_CHOICES:
  if k not in ('rc','rh'):fest+=opt('meein_day_'+k,label+':',expr,p('meein_'+k,True))+' '
 fest+=p('meein_festival_end',True)+'</tei:p>'
 abr+=opt('meein_festival',RUBRICS['meein_festival'],FESTIVAL,fest)+p('meein_end')
 for k in ('wine','fruit','cake','cake_wine'):
  abr+=(opt('meein_end_'+k,k.replace('_',' and ').capitalize()+':',context('meein-shalosh-food',k),p('meein_end_'+k)) if lang=='he' else p('meein_end_'+k))
 add('meein_shalosh',ABRIDGED,'ברכה מעין שלוש','ABRIDGED GRACE',771,771,abr)
 out[-1]['pages']=(771+side,772)
 add('borei_nefashot',MEALS+'/borei_nefashot','בורא נפשות','After other foods',773,773,rubric('borei_nefashot')+p('borei_nefashot'),False)
 add('meals',MEALS,'ברכות הסעודה','Meal blessings',757,773,''.join(transclude(u) for u in (MEALS+'/before',MEALS+'/before_grace',GRACE,ABRIDGED,MEALS+'/borei_nefashot')),False)
 blessings=rubric('blessings')+''.join(rubric(r['key'])+p(r['key']) for r in ROWS if r['key'].startswith('blessing_'))
 add('various_blessings',BLESSINGS,'בְּרָכוֹת שׁוֹנוֹת','BLESSINGS',773,777,blessings)
 add('bedtime_psalm91',BED+'/psalm91','תהלים צא','PSALM 91',779,779,p('bed_psalm91'))
 body=rubric('bedtime')+p('hamappil')+p('bed_el_melekh')+p('bed_shema')+p('bed_barukh_shem')+p('bed_veahavta')+p('bed_vihi_noam')+transclude(BED+'/psalm91')
 body+=p('bed_psalm91_repeat')
 body+=''.join(p(k) for k in ('bed_psalm3','bed_hashkivenu','bed_barukh','bed_yiru','hamalakh','bed_exodus','bed_zechariah','bed_solomon','bed_kohanim','bed_guardian','bed_salvation','bed_angels','bed_psalm128','bed_rigzu'))
 add('bedtime_adon_olam',BED+'/adon_olam','אֲדוֹן עוֹלָם','ADON OLAM',785,785,transclude(POEM+'adon_olam'))
 add('bedtime_shema',BED,'קְרִיאַת שְׁמַע עַל הַמִּטָּה','BEDTIME PRAYERS',777,785,body+transclude(BED+'/adon_olam'))
 add('children_bedtime_shema',CHILD,'קריאת שמע לילדים','BEDTIME PRAYERS FOR CHILDREN',787,787,''.join(p(r['key']) for r in ROWS if r['key'].startswith('child_')))
 author='<tei:p'+(' xml:lang="he"' if lang=='he' else '')+'>'+xml(RUBRICS['israel_author_'+lang])+'</tei:p>'
 add('state_of_israel',ISRAEL,'תְּפִלָּה לִשְׁלוֹם מְדִינַת יִשְׂרָאֵל','PRAYER FOR THE STATE OF ISRAEL',789,789,author+''.join(p('israel_'+str(i)) for i in range(1,5)))
 add('concluding_prayers',ROOT,'תפילות וברכות','Concluding prayers and blessings',753,789,''.join(transclude(u) for u in (MARRIAGE,MEALS,BLESSINGS,BED,CHILD,ISRAEL)),False)
 return tuple(out)
