"""Build the expanded electronic siddur from edition-independent transclusions.

Run with --project-directory pointing at opensiddur-projects/project and
--sourcetexts-root pointing at sourcetexts/sources. No prayer words are copied.
"""
import argparse
import json
from pathlib import Path
from lxml import etree as E
import yaml
from .compose import Composer
from .readings import manifest, slots, SHABBAT, YT, CH, RC, HAN, FAST, TISHA, IL, DIASPORA, day
from .xml import *

MAJOR=any_of(SHABBAT,YT)
REGALIM=any_of(holiday('pesah',1,8),holiday('shavuot',1,2),holiday('sukkot',1,7),holiday('shmini-atzeret',1,2))
FESTIVAL=all_of(YT,REGALIM)
HIGH=any_of(holiday('rosh-hashana',1,2),holiday('yom-kippur'))
RH=holiday('rosh-hashana',1,2)
MINYAN=feature('quorum','minyan')
HALLEL=feature('hallel','recite')
MUSAF=any_of(SHABBAT,FESTIVAL,CH,RC)
SIMCHAT=any_of(all_of(IL,holiday('shmini-atzeret',1)),all_of(DIASPORA,holiday('shmini-atzeret',2)))

def label_morning_blessings(root):
    """Name the prayer section, keeping Birnbaum's citation as a source note."""
    labels={
        'מסכת ברכות יא, א; ס, ב':('he','ברכות השחר וברכות התורה','מקורות: '),
        'Talmud Berakhoth 11a; 60b':('en','Morning and Torah blessings','Sources: '),
    }
    headings=[h for h in root.iter('{'+T+'}head') if h.text in labels]
    if not headings:
        return 0
    if len(headings)!=2 or headings[0].getparent() is not headings[1].getparent():
        raise ValueError('Expected one bilingual morning-blessings citation')
    notes=[]
    for heading in headings:
        citation=heading.text;lang,title,prefix=labels[citation]
        heading.text=title
        heading.set('resp','urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein')
        note=E.Element('{'+T+'}note',type='description')
        note.set('{http://www.w3.org/XML/1998/namespace}lang',lang)
        note.text=prefix+citation;notes.append(note)
    for note in reversed(notes):headings[-1].addnext(note)
    return len(headings)

class Builder:
    def __init__(self, project_directory, source_root):
        self.c=Composer(project_directory);self.a=Author();self.readings=manifest(Path(source_root));self.modules={};self.reading_modules={};self.reading_slots={}
    def s(self, name, **kwargs):return self.c.source(name,**kwargs)
    def gate(self,predicate,body,rubric=''):return self.a.gate(predicate,body,rubric)
    def section(self,he,en,body):return '<tei:div>'+head(he,en)+body+'</tei:div>'
    def amidah(self,urn,service_name,repeated=True):
        def occurrence(repetition):
            he,en=('חזרת הש״ץ','Reader’s repetition') if repetition else ('תפילת לחש','Silent Amidah')
            body=self.section(he,en,self.s(urn,mode='repetition' if repetition else 'silent'))
            return self.a.context(body,service_name,repetition)
        result=occurrence(False)
        if repeated:result+=self.gate(MINYAN,occurrence(True),'With a minyan: the reader repeats the Amidah.')
        return result
    def morning_torah_opening(self):
        prefix='siddur:chol/shacharit/torah/'
        opening=self.gate(all_of(MAJOR,none_of(SIMCHAT)),self.s('siddur:shabbat/shacharit/torah/opening'),
                          'On Shabbat and festivals other than Simchat Torah:')
        # The hakafot already conclude with Shema, Echad Eloheinu and Gadlu.
        # Birnbaum's page-turn direction resumes at Lekha, not at the start of
        # the ordinary opening. Include that continuation without repeating it.
        continuation=instruction('Congregation:')+self.s(prefix+'lekha_adonai')+self.s('prayer:al_hakol')
        continuation+=instruction('Reader:')+self.s('prayer:av_harachamim/hu_yerachem')
        continuation+=instruction('The Torah is placed on the desk. The Reader unrolls it and says:')+self.s('prayer:vayaazor')
        opening+=self.gate(all_of(MAJOR,SIMCHAT),
            self.section('המשך הוצאת ספר תורה לאחר ההקפות','Torah procession after the hakafot',continuation),
            'On Simchat Torah, continue after Gadlu at the end of the hakafot:')
        weekday=self.s('siddur:chol/shacharit/torah_intro')+instruction('Open the ark and take out the Torah.')
        weekday+=''.join(self.s(u) for u in [prefix+'vayehi_binsoa','prayer:berikh_shemeh',prefix+'gaddelu',prefix+'lekha_adonai','prayer:av_harachamim/hu_yerachem',prefix+'vetiggaleh'])
        return opening+self.gate(none_of(MAJOR),weekday)
    def torah(self,service_name,major=False):
        selected=[e for e in self.readings if e.service==service_name]
        if service_name not in self.reading_slots:
            content=slots(selected,self.a,self.c,service_name)
            self.reading_slots[service_name]={}
            for slot,body in content.items():
                name=f'readings_{service_name}_{slot}'
                self.reading_modules[name]=document(name,'קריאות התורה וההפטרה','Torah and haftarah selections',body)
                self.reading_slots[service_name][slot]=transclude(ROOT+'/'+name)
        reading=self.reading_slots[service_name]
        prefix='siddur:chol/shacharit/torah/'
        replacements={TEXT+prefix+'barekhu':'',TEXT+prefix+'asher_bachar':reading['torah'],TEXT+'prayer:birkhot_hatorah/asher_natan':''}
        if service_name=='morning':
            # One reading spine serves weekdays, Shabbat and festivals. The
            # opening and communal prayers differ; the selected aliyot do not
            # need to be compiled twice under those alternatives.
            replacements[TEXT+prefix+'asher_bachar']=self.gate(holiday('shavuot',1),self.s('siddur:regalim/aqdamut'))+reading['torah']
            replacements[TEXT+'prayer:kaddish/chatzi']=self.s('prayer:kaddish/chatzi')+reading['maftir']
            replacements[TEXT+'prayer:birkhot_haftarah/after']=reading['haftarah']+self.s('prayer:birkhot_haftarah/after')
            for name in ['barukh_shepetrani','mi_sheberakh/oleh_latorah','mi_sheberakh/yoledet_ubat','mi_sheberakh/choleh','mi_sheberakh/cholah']:
                replacements[TEXT+'prayer:'+name]=self.gate(MAJOR,self.s('prayer:'+name))
            body=self.morning_torah_opening()+self.s('siddur:shabbat/shacharit/torah/reading',replace=replacements)
            body+=self.gate(any_of(MAJOR,TISHA),self.s('siddur:shabbat/shacharit/torah/haftarah',replace=replacements))
            for part in ['yequm_purqan','government','month','memorial']:
                body+=self.gate(MAJOR,self.s('siddur:shabbat/shacharit/torah/'+part))
            body+=self.gate(MAJOR,self.s('siddur:yizkor')+self.s('siddur:shabbat/shacharit/torah/ashrei'))
            body+=self.gate(none_of(MAJOR),self.s('prayer:yehi_ratzon_milifnei_avinu'))
            body+=self.s('siddur:shabbat/shacharit/torah/return')
        elif service_name=='afternoon':
            # Fast-day haftarah follows raising and dressing the Torah; on
            # ordinary Shabbat Minchah there is no haftarah.
            haft=self.gate(any_of(FAST,TISHA,holiday('yom-kippur')),self.s('prayer:birkhot_haftarah/asher_bachar')+reading['haftarah']+self.s('prayer:birkhot_haftarah/after'))
            target='siddur:shabbat/minchah/torah/vezot_hatorah'
            replacements[TEXT+target]=self.s('siddur:chol/shacharit/torah/vezot_hatorah')+haft
            replacements[TEXT+'siddur:shabbat/minchah/torah/uvenuchoh']=self.s('siddur:chol/shacharit/torah/uvenuchoh')
            body=self.s('siddur:shabbat/minchah/torah',replace=replacements)
        else:
            # Tisha B'Av has a morning haftarah too.
            target=prefix+'vezot_hatorah'
            replacements[TEXT+target]=self.s(target)+self.gate(TISHA,self.s('prayer:birkhot_haftarah/asher_bachar')+reading['haftarah']+self.s('prayer:birkhot_haftarah/after'))
            body=self.s('siddur:chol/shacharit/torah_intro')+self.s('siddur:chol/shacharit/torah',replace=replacements)
        eligible=any_of(MAJOR,CH,RC,HAN,FAST,TISHA,holiday('purim-observed'),day(2),day(5)) if service_name=='morning' else any_of(SHABBAT,FAST,TISHA,holiday('yom-kippur'))
        return self.gate(all_of(MINYAN,eligible),body,'Public Torah reading, with a minyan.')
    def musaf(self):
        body=self.gate(all_of(SHABBAT,none_of(FESTIVAL,CH)),self.amidah('siddur:shabbat/musaf/amidah','musaf'))
        body+=self.gate(any_of(FESTIVAL,CH),self.amidah('siddur:regalim/musaf/amidah','musaf'))
        body+=self.gate(all_of(RC,none_of(SHABBAT)),self.amidah('siddur:rosh_chodesh/musaf/amidah','musaf'))
        body+=self.gate(holiday('sukkot',1,7),self.s('prayer:hoshanot'))
        return self.gate(all_of(MUSAF,none_of(HIGH)),self.section('מוסף','Musaf',body),'Musaf on Shabbat, Rosh Chodesh and festivals.')
    def morning(self):
        children=self.s('siddur:all/shacharit/yeladim')
        blessings=parse_fragment(self.s('siddur:all/shacharit/birkhot_hashachar'))
        label_morning_blessings(blessings)
        body=children+''.join(serialize(e) for e in blessings)
        for suffix in ['opening','pesuqei_dezimrah','shema']:
            body+=self.gate(none_of(MAJOR),self.s('siddur:chol/shacharit/'+suffix))
            body+=self.gate(MAJOR,self.s('siddur:shabbat/shacharit/'+suffix))
        body+=self.gate(none_of(MAJOR),self.amidah('siddur:chol/shacharit/amidah','shaharit'))
        body+=self.gate(all_of(SHABBAT,none_of(YT)),self.amidah('siddur:shabbat/shacharit/amidah','shaharit'))
        body+=self.gate(FESTIVAL,self.amidah('siddur:regalim/amidah','shaharit'))
        body+=self.gate(none_of(MAJOR),self.s('siddur:chol/shacharit/avinu_malkenu')+self.s('siddur:chol/shacharit/tachanun'))
        body+=self.gate(all_of(holiday('sukkot',1,7),none_of(SHABBAT)),self.s('prayer:netilat_lulav'))
        body+=self.gate(HALLEL,self.s('siddur:hallel'))
        body+=self.gate(none_of(HALLEL),self.gate(MAJOR,self.s('siddur:shabbat/shacharit/kaddish'))+self.gate(none_of(MAJOR),self.s('siddur:chol/shacharit/kaddish_after_tachanun')))
        body+=self.gate(SIMCHAT,self.s('prayer:haqqafot_simchat_torah'))
        body+=self.torah('morning')
        body+=self.gate(holiday('purim-observed'),self.purim())
        # Weekday Ashrei and Uva Letzion precede Musaf. The final Aleinu is
        # moved to the end, so it occurs once after all the morning services.
        ending=['siddur:chol/shacharit/conclusion/aleinu','prayer:kaddish/yatom','siddur:chol/shacharit/conclusion/al_tira']
        body+=self.gate(none_of(MAJOR),self.s('siddur:chol/shacharit/conclusion',omit=tuple(TEXT+u for u in ending)))
        body+=self.gate(MAJOR,self.s('siddur:shabbat/shacharit/kaddish_before_musaf'))
        body+=self.musaf()
        body+=self.conclusion()
        body+=self.gate(all_of(any_of(SHABBAT,FESTIVAL),none_of(HIGH)),self.day_meal())
        body+=self.gate(none_of(MAJOR),self.s('siddur:chol/shacharit/final_readings'))
        # Eligibility is outside the local service declarations.
        body=self.gate(none_of(HIGH),self.a.context(body,'shaharit'))+self.gate(HIGH,instruction('Birnbaum does not contain a complete Rosh Hashanah or Yom Kippur morning service; use a mahzor.')+self.gate(holiday('yom-kippur'),self.s('siddur:yizkor')))
        return self.gate(service('shaharit'),self.section('תפילת שחרית','Morning service',body))
    def conclusion(self):
        # The Shabbat conclusion also supplies the festival conclusion. Its
        # source container's Amidah is omitted; all other conditions remain.
        major=self.s('siddur:shabbat/musaf',omit=(TEXT+'siddur:shabbat/musaf/amidah',))
        # Discard the outer heading "Shabbat Musaf", since this is also Yom Tov.
        tree=parse_fragment(major)
        for h in tree.xpath('./tei:div/tei:head',namespaces=NS):h.getparent().remove(h)
        major=''.join(serialize(e) for e in tree)
        weekday=self.s('siddur:chol/shacharit/conclusion/aleinu')+self.gate(MINYAN,self.s('prayer:kaddish/yatom'))+self.s('siddur:chol/shacharit/conclusion/al_tira')+self.s('siddur:chol/shacharit/psalms')
        # Weekday Rosh Chodesh needs the post-Musaf full Kaddish too.
        weekday=self.gate(RC,self.s('siddur:shabbat/musaf/kaddish'))+weekday
        return self.section('סיום התפילה','Concluding prayers',self.gate(MAJOR,major)+self.gate(none_of(MAJOR),weekday))
    def day_meal(self):
        return self.section('קידוש וסעודת היום','Daytime Kiddush and meal',self.gate(FESTIVAL,self.s('siddur:regalim/morning_meal'))+self.gate(all_of(SHABBAT,none_of(FESTIVAL)),self.s('siddur:shabbat/day_meal/kiddush'))+self.s('siddur:meals/before')+self.gate(SHABBAT,self.s('siddur:shabbat/day_meal/zemirot'))+self.s('siddur:meals/before_grace')+self.s('prayer:birkat_hamazon'))
    def afternoon(self):
        ordinary=self.amidah('siddur:chol/minchah/amidah','minha')
        major=self.amidah('siddur:shabbat/minchah/amidah','minha')
        festival=self.amidah('siddur:regalim/amidah','minha')
        rh=self.amidah('siddur:rosh_hashanah/minchah_maariv/amidah','minha')
        replace={TEXT+'siddur:chol/minchah/amidah':self.gate(none_of(RH),ordinary)+self.gate(RH,rh),TEXT+'siddur:shabbat/minchah/amidah':major,TEXT+'siddur:regalim/amidah':festival,TEXT+'siddur:shabbat/minchah/torah':self.torah('afternoon')}
        replace[TEXT+'siddur:shabbat/minchah/uva_letziyyon']=self.s('siddur:chol/shacharit/conclusion/uva_letziyyon')
        # The fast-day reading belongs between Ashrei and the Amidah.
        replace[TEXT+'siddur:chol/minchah/opening']=self.s('siddur:chol/minchah/opening')+self.gate(any_of(SHABBAT,FAST,TISHA),self.torah('afternoon')+self.s('siddur:shabbat/minchah/torah_kaddish'))
        preparations=self.gate(TISHA,self.section('טלית ותפילין','Tallit and tefillin for Tisha B’Av afternoon',''.join(self.s('prayer:'+u) for u in ['tallith/barkhi_nafshi','tallith/hineni_mitattef','tallith/lehitattef','tallith/mah_yaqar','tallith/yehi_ratzon','tefillin/hineni_mekhavven','tefillin/lehanniach','tefillin/al_mitzvat','shema/barukh_shem','tefillin/umechokhmatekha','tefillin/verastikh','tefillin/yehi_ratzon'])))
        body=preparations+self.gate(any_of(none_of(MAJOR),RH),self.s('siddur:chol/minchah',replace=replace,include_heading=False))
        body+=self.gate(all_of(MAJOR,none_of(HIGH)),self.s('siddur:shabbat/minchah',replace=replace))
        body+=self.gate(all_of(SHABBAT,feature('pirkei-avot','season')),self.s('siddur:pirqei_avot'))
        body+=self.gate(holiday('yom-kippur'),instruction('Birnbaum does not contain Yom Kippur Minchah; use a mahzor.'))
        erev_hanukkah=all_of(feature('hebrew-date','month',9),feature('hebrew-date','day',24))
        friday_lights=self.s('siddur:chanukah',conditions={'festival_chanukah_first_night':erev_hanukkah})
        body+=self.gate(all_of(day(6),any_of(holiday('hanukkah',1,7),erev_hanukkah)),self.section('נרות חנוכה בערב שבת','Chanukah lights before Shabbat',instruction('On Friday, light the Chanukah candles before the Shabbat candles. The first-night blessing follows the night that is about to begin.')+friday_lights))
        body+=self.gate(day(6),self.s('siddur:shabbat/preparations',omit=(TEXT+'prayer:birkat_horim',))+self.s('siddur:shabbat/qabbalat_service'))
        return self.gate(service('minha'),self.section('תפילת מנחה','Afternoon service',self.a.context(body,'minha')))
    def purim(self):
        return self.s('siddur:purim',replace={TEXT+'prayer:harav_et_riveinu':transclude(TEXT+'bible:esther')+self.s('prayer:harav_et_riveinu')})
    def evening(self):
        ordinary=self.amidah('siddur:chol/arvit/amidah','maariv',False)
        rh=self.amidah('siddur:rosh_hashanah/minchah_maariv/amidah','maariv',False)
        seasonal=self.gate(holiday('purim-observed'),self.purim())+self.gate(all_of(HAN,none_of(SHABBAT)),self.s('siddur:chanukah'))+self.gate(holiday('omer',1,49),self.s('siddur:sefirat_haomer'))+self.gate(SIMCHAT,self.s('prayer:haqqafot_simchat_torah'))
        replace={TEXT+'siddur:chol/arvit/amidah':self.gate(none_of(RH),ordinary)+self.gate(RH,rh),TEXT+'siddur:shabbat/arvit/amidah':self.amidah('siddur:shabbat/arvit/amidah','maariv',False),TEXT+'siddur:regalim/amidah':self.amidah('siddur:regalim/amidah','maariv',False)}
        for u in ['siddur:chol/arvit/conclusion','siddur:shabbat/arvit/conclusion']:replace[TEXT+u]=seasonal+self.s(u)
        motzaei=aggregate('motzaei-shabbat')
        body=self.gate(all_of(SHABBAT,none_of(RH)),self.s('siddur:shabbat/qabbalat_service'))
        body+=self.gate(all_of(none_of(MAJOR,motzaei,HIGH)),self.s('siddur:chol/arvit',replace=replace,include_heading=False))
        body+=self.gate(all_of(motzaei,none_of(YT)),self.s('siddur:shabbat/conclusion',replace=replace))
        body+=self.gate(all_of(MAJOR,none_of(HIGH)),self.s('siddur:shabbat/arvit',replace=replace))
        rh_service=''.join(self.s('siddur:shabbat/arvit/'+part) for part in ['blessings_before_shema','shema','blessings_after_shema'])+rh
        rh_service+=self.gate(SHABBAT,self.s('siddur:shabbat/arvit/after_amidah'))
        rh_service+=''.join(self.s('siddur:shabbat/arvit/'+part) for part in ['kaddish','conclusion','psalm27','adon_olam'])
        rh_service+=self.s('siddur:rosh_hashanah/greeting')+self.s('siddur:rosh_hashanah/kiddush')
        rh_service+=self.s('siddur:meals/before')+self.s('siddur:meals/before_grace')+self.s('prayer:birkat_hamazon')
        body+=self.gate(RH,rh_service)
        body+=self.gate(holiday('yom-kippur'),instruction('Birnbaum does not contain Kol Nidrei or Yom Kippur Maariv; use a mahzor.'))
        home=self.gate(SHABBAT,self.s('prayer:birkat_horim')+self.s('siddur:shabbat/leil_shabbat',omit=(TEXT+'siddur:shabbat/leil_shabbat/zemirot',)))+self.gate(FESTIVAL,self.s('siddur:regalim/kiddush'))+self.gate(holiday('sukkot',1,7),self.s('prayer:ushpizin'))+self.s('siddur:meals/before')+self.gate(SHABBAT,self.s('siddur:shabbat/leil_shabbat/zemirot'))+self.s('siddur:meals/before_grace')+self.s('prayer:birkat_hamazon')
        body+=self.gate(all_of(MAJOR,none_of(HIGH)),self.section('סעודת הערב','Evening meal',home))
        return self.gate(service('maariv'),self.section('תפילת ערבית','Evening service',self.a.context(body,'maariv')))
    def build(self):
        self.modules['morning']=('שחרית','Morning',self.morning())
        self.modules['afternoon']=('מנחה','Afternoon',self.afternoon())
        self.modules['evening']=('ערבית','Evening',self.evening())
        standalone_body=self.gate(none_of(HIGH),self.musaf()+self.conclusion()+self.gate(any_of(SHABBAT,FESTIVAL),self.day_meal()))+self.gate(HIGH,instruction('Birnbaum does not contain a complete High Holiday Musaf; use a mahzor.'))
        standalone=self.gate(all_of(service('musaf'),none_of(service('shaharit'),service('minha'),service('maariv'))),self.section('מוסף בפני עצמו','Musaf selected separately',standalone_body),'An alternative starting point when selecting Musaf separately from the morning service.')
        self.modules['musaf']=('מוסף','Musaf selected separately',standalone)
        roots=['siddur:regalim/eruv_tavshilin','siddur:regalim/candles','siddur:rosh_hashanah/tashlikh','siddur:yom_kippur/kapparot','prayer:hadlaqat_ner_yom_kippur','siddur:berakhot/birkat_halevanah']
        # Use the source index's eligibility for each occasional item. This
        # retains user customs and dates instead of forcing them by declaration.
        index=self.c.units[TEXT+'siddur:siddur']
        occasion=''
        for u in roots:
            if u=='prayer:hadlaqat_ner_yom_kippur':
                occasion+=self.gate(all_of(feature('hebrew-date','month',7),any_of(feature('hebrew-date','day',9),all_of(holiday('yom-kippur'),service('maariv')))),self.s(u));continue
            if u=='siddur:regalim/eruv_tavshilin':
                occasion+=self.gate(aggregate('eruv-tavshilin'),self.s(u));continue
            if u=='siddur:regalim/candles':
                occasion+=self.gate(all_of(FESTIVAL,service('maariv')),self.s(u));continue
            target=TEXT+u
            nodes=index.xpath('.//j:transclude[@target=$target]',namespaces=NS,target=target)
            if nodes:
                e=nodes[0];prev=e.getprevious();nxt=e.getnext()
                if prev is not None and prev.tag==f'{{{J}}}conditional' and nxt is not None and nxt.tag==f'{{{J}}}endConditional':
                    condition=''.join(serialize(x) for x in prev if x.tag!=f'{{{T}}}note')
                    occasion+=self.gate(condition,self.s(u));continue
            occasion+=self.s(u)
        self.modules['occasions']=('מועדים ומנהגים','Occasional rites',occasion)
        roots=['siddur:meals','siddur:marriage','siddur:berit_milah','siddur:pidyon_haben','siddur:tefillat_haderekh','siddur:tefillah_lecholeh','siddur:viddui_shekhiv_mera','siddur:burial','siddur:berakhot/various','siddur:qeriat_shema_al_hamittah','siddur:qeriat_shema_al_hamittah/yeladim','prayer:tefillah_lishlom_medinat_yisrael','prayer:amidah/havinenu']
        appendix=''
        for u in roots:
            if TEXT+u in self.c.units:appendix+=self.s(u)
        self.modules['appendices']=('ברכות ומעגל החיים','Meals, blessings and lifecycle',instruction('These prayers are for the indicated occasion; select the relevant item in the contents.')+appendix)
        intro=instruction('This edition arranges Birnbaum’s Ashkenazi prayer text in recitation order. Hebrew and English share one sequence. Set the date, place, service and minyan in the reader settings. Unresolved choices remain with their rubrics. Rosh Hashanah and Yom Kippur coverage is limited to the services and rites Birnbaum contains; use a mahzor for the remaining services.')
        body=intro+''.join(transclude(ROOT+'/'+name) for name in self.modules)
        return {'index':document('index','סידור אשכנז מורחב','Expanded Ashkenazi Siddur',body),**{name:document(name,he,en,body) for name,(he,en,body) in self.modules.items()},**self.reading_modules}

def build(project_directory,source_root):
    builder=Builder(project_directory,source_root);documents=builder.build();destination=Path(project_directory)/PROJECT
    destination.mkdir(parents=True,exist_ok=True)
    for name,xml in documents.items():
        tree=E.fromstring(xml.encode());E.indent(tree,space='  ')
        path=destination/(name+'.xml')
        content=E.tostring(tree,encoding='UTF-8',xml_declaration=True,pretty_print=True)
        if not path.exists() or path.read_bytes()!=content:path.write_bytes(content)
    return builder

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-directory',type=Path,required=True)
    parser.add_argument('--sourcetexts-root',type=Path,required=True)
    args=parser.parse_args();b=build(args.project_directory,args.sourcetexts_root)
    print(f'Built {len(b.modules)+len(b.reading_modules)+1} files; {len(b.readings)} reading selections; {len(b.c.used)} source references.')
if __name__=='__main__':main()
