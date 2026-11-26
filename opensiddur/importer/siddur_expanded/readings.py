"""Static reading selections over the Humash's canonical reading data.

Predicates use existing calendar features. Replacement festivals, ordinary
weekly readings and supplemental scrolls occupy distinct slots; no runtime URN
interpolation or copied Bible text is needed.
"""
from dataclasses import dataclass, field
from pathlib import Path
from pyluach import parshios
from opensiddur.importer.humash.aliyot import parse_readings
from opensiddur.importer.humash.readings import festival_readings, haftarot, triennial, triennial_patterns
from opensiddur.importer.humash.names import PARSHA_NAMES, PAIR_MEMBERS, PAIR_FOR_MEMBER, vocalized_name
from opensiddur.importer.humash.refs import UNIT_ALIYAH, UNIT_WEEKDAY, UNIT_MAFTIR
from opensiddur.importer.humash.festival_names import hebrew_name
from opensiddur.importer.humash.build import DAY_MAFTIR_SUKKOT_DAY
from .xml import *

SHABBAT=aggregate('shabbat'); YT=aggregate('yom-tov'); CH=aggregate('chol-hamoed')
IL=feature('israel','is-israel'); DIASPORA=feature('israel','is-israel',False)
RC=holiday('rosh-hodesh',1,2); HAN=holiday('hanukkah',1,8)
FAST=aggregate('minor-fast'); TISHA=holiday('tisha-bav')
SPECIALS=[('shabbat-shkalim','Shabbat Shekalim'),('shabbat-zachor','Shabbat Zachor'),('shabbat-parah','Shabbat Parah'),('shabbat-hahodesh','Shabbat HaChodesh')]
SPECIAL=any_of(*(feature('torah-reading',f) for f,_ in SPECIALS))
SUPPLEMENT=any_of(RC,HAN,SPECIAL)
THIRD_SCROLL=all_of(RC,any_of(HAN,feature('torah-reading','shabbat-shkalim'),feature('torah-reading','shabbat-hahodesh')))
WEEKDAY=none_of(SHABBAT,YT)
FESTIVALS=any_of(holiday('pesah',1,8),holiday('shavuot',1,2),holiday('sukkot',1,7),holiday('shmini-atzeret',1,2),holiday('rosh-hashana',1,2),holiday('yom-kippur'))
ROMAN={'I':1,'II':2,'VII':7,'VIII':8}

@dataclass
class Entry:
    key: str
    title: str
    predicate: str
    service: str='morning'
    kind: str='replace'
    torah: list=field(default_factory=list)
    maftir: list=field(default_factory=list)
    haftarah: str|None=None
    hebrew_title: str|None=None

def day(n): return feature('day-of-week','hebrew-day',n)
def hdate(month,first,last=None): return all_of(feature('hebrew-date','month',month),feature('hebrew-date','day',first,last))
def weekday_variant(base,on_shabbat): return all_of(base,SHABBAT if on_shabbat else none_of(SHABBAT))
def parsha_value(slug):
    names={s:parshios.PARSHIOS[i] for i,(_,_,s) in enumerate(PARSHA_NAMES)}
    label=', '.join(names[s] for s in PAIR_MEMBERS[slug]) if slug in PAIR_MEMBERS else names[slug]
    return label.lower().replace(' ','-').replace(',','')
def parsha_english(slug):
    names={s:en for _,en,s in PARSHA_NAMES}
    return '–'.join(names[s] for s in PAIR_MEMBERS[slug]) if slug in PAIR_MEMBERS else names[slug]

def parsha_condition(slug,next_reading=False):
    suffix='next-parsha' if next_reading else 'parsha'; value=parsha_value(slug)
    return any_of(all_of(IL,feature('torah-reading','israel-'+suffix,value)),all_of(DIASPORA,feature('torah-reading','diaspora-'+suffix,value)))

def day_maftir_condition(offset):
    """When maftir_day<offset> is the maftir of Shabbat Chol HaMoed Sukkot.

    hebcal numbers these maftirs by the day of Chol HaMoed, which begins on the third day of
    Sukkot in the Diaspora and on the second in Israel; the humash conditions its own copy
    of them the same way (humash.build.DAY_MAFTIR_SUKKOT_DAY).
    """
    return any_of(*(
        all_of(IL if israel else DIASPORA,holiday('sukkot',offset+first))
        for israel,first in DAY_MAFTIR_SUKKOT_DAY.items()
    ))

def festival_cases():
    """Each named reading's eligibility, before choosing its weekday variant."""
    cases={}
    for name,feat in [('Pesach','pesah'),('Sukkot','sukkot'),('Rosh Hashana','rosh-hashana')]:
        for roman,n in ROMAN.items():
            cases[name+' '+roman]=holiday(feat,n)
    cases['Pesach II']=all_of(DIASPORA,holiday('pesah',2))
    cases['Pesach VIII']=all_of(DIASPORA,holiday('pesah',8))
    cases['Sukkot II']=all_of(DIASPORA,holiday('sukkot',2))
    cases['Shavuot']=all_of(IL,holiday('shavuot',1))
    cases['Shavuot I']=all_of(DIASPORA,holiday('shavuot',1))
    cases['Shavuot II']=all_of(DIASPORA,holiday('shavuot',2))
    cases['Shmini Atzeret']=all_of(DIASPORA,holiday('shmini-atzeret',1))
    cases['Simchat Torah']=any_of(all_of(IL,holiday('shmini-atzeret',1)),all_of(DIASPORA,holiday('shmini-atzeret',2)))
    cases['Yom Kippur']=holiday('yom-kippur')
    cases["Pesach II (CH''M)"]=all_of(IL,holiday('pesah',2),none_of(SHABBAT))
    # The weekday Passover sequence skips the Shabbat reading and keeps the
    # first intermediate reading after it. The upstream Sunday/Monday aliases
    # encode the two shifts when the first day was Thursday.
    sunday=all_of(holiday('pesah',4),day(1),DIASPORA)
    monday=all_of(holiday('pesah',5),day(2),DIASPORA)
    for n in range(1,5):
        pred=holiday('pesah',n+2)
        if n==1: pred=any_of(pred,sunday)
        if n==2: pred=any_of(all_of(pred,none_of(sunday)),monday)
        if n==3: pred=all_of(pred,none_of(monday))
        cases[f'Pesach Chol ha-Moed Day {n}']=all_of(pred,CH,none_of(SHABBAT))
    cases['Pesach Shabbat Chol ha-Moed']=all_of(holiday('pesah',1,8),CH,SHABBAT)
    for n in range(1,6):
        cases[f'Sukkot Chol ha-Moed Day {n}']=all_of(DIASPORA,holiday('sukkot',n+2),CH,none_of(SHABBAT))
    cases['Sukkot Shabbat Chol ha-Moed']=all_of(holiday('sukkot',1,7),CH,SHABBAT)
    cases['Sukkot Final Day (Hoshana Raba)']=all_of(DIASPORA,holiday('sukkot',7),none_of(SHABBAT))
    # Prefer the dedicated final-day reading over CHM day five.
    cases['Sukkot Chol ha-Moed Day 5']=all_of(cases['Sukkot Chol ha-Moed Day 5'],none_of(holiday('sukkot',7)))
    cases['Fast Day (Morning)']=all_of(FAST,WEEKDAY)
    cases['Fast Day (Afternoon)']=any_of(FAST,TISHA)
    cases["Tish'a B'Av"]=TISHA
    cases['Yom Kippur (Mincha, Traditional)']=holiday('yom-kippur')
    cases['Purim']=holiday('purim-observed')
    cases['Rosh Chodesh']=all_of(RC,WEEKDAY,none_of(HAN))
    for n in range(1,9):
        cases[f'Chanukah Day {n}']=all_of(holiday('hanukkah',n),none_of(SHABBAT),none_of(RC) if n in [6,7] else all_of())
        cases[f'Chanukah Day {n} (on Shabbat)']=all_of(holiday('hanukkah',n),SHABBAT,none_of(RC,SPECIAL))
    cases['Chanukah Day 6']=all_of(holiday('hanukkah',6),none_of(SHABBAT))
    cases['Chanukah Day 7 (on Rosh Chodesh)']=all_of(holiday('hanukkah',7),RC,none_of(SHABBAT))
    cases['Shabbat Rosh Chodesh Chanukah']=all_of(SHABBAT,RC,HAN)
    cases['Shabbat Rosh Chodesh']=all_of(SHABBAT,RC,none_of(HAN,SPECIAL))
    cases['Shabbat Machar Chodesh']=all_of(SHABBAT,feature('torah-reading','shabbat-mahar-hodesh'),none_of(RC,HAN,SPECIAL,feature('hebrew-date','month',5)))
    for feat,name in SPECIALS:
        p=all_of(SHABBAT,feature('torah-reading',feat))
        cases[name]=all_of(p,none_of(RC)) if feat in ['shabbat-shkalim','shabbat-hahodesh'] else p
        cases[name+' (on Rosh Chodesh)']=all_of(p,RC)
    cases['Shabbat HaGadol']=all_of(SHABBAT,feature('torah-reading','shabbat-hagadol'),none_of(RC))
    for name,slug in [('Vayeilech','vayeilech'),("Ha'azinu",'haazinu')]:
        cases[f'Shabbat Shuva (with {name})']=all_of(SHABBAT,feature('torah-reading','shabbat-shuva'),parsha_condition(slug))
    cases['Kedoshim following Special Shabbat']=all_of(SHABBAT,parsha_condition('kedoshim'),any_of(feature('hebrew-date','day',26),feature('hebrew-date','day',28),feature('hebrew-date','day',6)))
    cases['Ki Teitzei with 3rd Haftarah of Consolation']=all_of(SHABBAT,parsha_condition('ki_teitzei'),feature('hebrew-date','day',14))
    return cases

def cycle_predicate(year):
    return any_of(feature('reading-cycle',f'triennial-year-{year}'),all_of(feature('reading-cycle','triennial'),feature('torah-reading','triennial-year',year)))

def weekly_haftarah_slug(slug,available):
    if slug in available:return slug
    if slug in PAIR_MEMBERS:
        # The final consolation precedes Rosh Hashanah even when Nitzavim is
        # joined to Vayeilech; other pairs take the second member's haftarah.
        selected=PAIR_MEMBERS[slug][0 if slug=='nitzavim_vayeilech' else 1]
        if selected in available:return selected
    raise ValueError('Missing weekly haftarah: '+slug)

def manifest(sourcetexts_root):
    festivals=festival_readings(sourcetexts_root); cases=festival_cases(); entries=[]
    for slug,r in festivals.items():
        name=r['name'];on_shabbat=name.endswith(' (on Shabbat)');plain=name.removesuffix(' (on Shabbat)')
        if name in cases: pred=cases[name]
        elif plain in cases: pred=weekday_variant(cases[plain],True)
        else: continue
        if not on_shabbat and plain+' (on Shabbat)' in {x['name'] for x in festivals.values()}:pred=weekday_variant(pred,False)
        service_name='afternoon' if name in ['Fast Day (Afternoon)','Yom Kippur (Mincha, Traditional)'] else 'morning'
        supplement=name.startswith('Shabbat ') and name not in ['Shabbat Shuva','Shabbat HaGadol','Shabbat Machar Chodesh'] or '(on Shabbat)' in name and name.startswith('Chanukah')
        spans=r['aliyot'];main=[s for s in spans if s.unit==UNIT_ALIYAH];maftir=[s for s in spans if s.unit==UNIT_MAFTIR]
        supplement=supplement and bool(main or maftir)
        if service_name=='afternoon':main+=maftir;maftir=[]
        # On CHM Sukkot Shabbat, only the maftir for that festival day is read.
        if name=='Sukkot Shabbat Chol ha-Moed':
            for offset in range(1,6):
                selected=[s for s in maftir if s.label==f'maftir_day{offset}']
                entries.append(Entry(slug+f'_day{offset}',name,all_of(pred,day_maftir_condition(offset)),torah=main,maftir=selected,haftarah=f'urn:x-opensiddur:text:bible:reading/{slug}/haftarah',hebrew_title=hebrew_name(name)))
            continue
        entries.append(Entry(slug,name,pred,service_name,'supplement' if supplement else 'replace',main,maftir,f'urn:x-opensiddur:text:bible:reading/{slug}/haftarah' if r['haftarot'] else None,hebrew_title=hebrew_name(name)))
    # Israel reads that day's single offering four times on weekday Chol HaMoed.
    from opensiddur.importer.humash.refs import ReadingSpan, VerseRef
    for n in range(2,8):
        start=17+(n-2)*3
        spans=[ReadingSpan(UNIT_ALIYAH,str(i),VerseRef('numbers',29,start),VerseRef('numbers',29,start+2)) for i in range(1,5)]
        entries.append(Entry(f'sukkot_israel_{n}',f'Sukkot, Israel, day {n}',all_of(IL,holiday('sukkot',n),none_of(SHABBAT)),torah=spans,hebrew_title=f'סוכות בארץ ישראל – יום {n}'))
    available_haftarot=haftarot(sourcetexts_root)
    singles,pairs=parse_readings(sourcetexts_root);divisions=triennial(sourcetexts_root);patterns=triennial_patterns(sourcetexts_root)
    annual=all_of(feature('reading-cycle','annual'),none_of(feature('reading-cycle','triennial'),*(feature('reading-cycle',f'triennial-year-{i}') for i in [1,2,3])))
    for p in [*singles,*pairs]:
        # Vezot Haberakhah is read as the Simchat Torah reading above.
        is_vezot = p.slug=='vezot_haberakhah'
        pred=all_of(SHABBAT,none_of(FESTIVALS),parsha_condition(p.slug))
        aliyot=[s for s in p.spans if s.unit in [UNIT_ALIYAH,'aliyah.combined']]
        maftir=[s for s in p.spans if s.unit in [UNIT_MAFTIR,'maftir.combined']]
        if not aliyot:raise ValueError('Missing annual aliyot: '+p.slug)
        haft=f'urn:x-opensiddur:text:bible:haftarah/{weekly_haftarah_slug(p.slug,available_haftarot)}'
        if not is_vezot: entries.append(Entry('weekly_'+p.slug,parsha_english(p.slug),all_of(pred,annual),kind='weekly',torah=aliyot,maftir=maftir,haftarah=haft,hebrew_title=p.hebrew_name))
        for (variation,year),spans in divisions.get(p.slug,{}).items():
            variant=''
            if variation not in [None,'combined']:
                pair=PAIR_FOR_MEMBER[p.slug];choices=[feature('torah-reading','triennial-pattern-'+pair.replace('_','-'),pattern) for pattern,v in patterns[pair].items() if v==variation]
                variant=any_of(*choices)
            entries.append(Entry(f'weekly_{p.slug}_{variation or "single"}_{year}',parsha_english(p.slug),all_of(pred,cycle_predicate(year),variant),kind='weekly',torah=[s for s in spans if s.unit.startswith('aliyah.')],maftir=[s for s in spans if s.unit.startswith('maftir.')],haftarah=haft,hebrew_title=p.hebrew_name))
        weekday=[s for s in p.spans if s.unit in [UNIT_WEEKDAY,'aliyah.weekday.combined']]
        if weekday:
            morning=all_of(WEEKDAY,any_of(day(2),day(5)),none_of(FESTIVALS,RC,HAN,FAST,TISHA,holiday('purim-observed')),parsha_condition(p.slug,True))
            afternoon=all_of(SHABBAT,none_of(FAST,TISHA,holiday('yom-kippur')),parsha_condition(p.slug,True))
            entries.append(Entry('weekday_'+p.slug,parsha_english(p.slug),morning,torah=weekday,hebrew_title=p.hebrew_name))
            entries.append(Entry('mincha_'+p.slug,parsha_english(p.slug),afternoon,'afternoon',torah=weekday,hebrew_title=p.hebrew_name))
    # The first two haftarot of admonition follow the season. Pinchas can
    # occur on either side of 17 Tammuz, so matching the parshah alone is not
    # sufficient. These also take precedence over Rosh Chodesh Av.
    first_admonition=all_of(SHABBAT,hdate(4,18,24))
    second_admonition=all_of(SHABBAT,any_of(hdate(4,25,29),hdate(5,1,2)))
    entries.extend([
        Entry('admonition_1','First haftarah of admonition',first_admonition,kind='seasonal',haftarah=TEXT+'bible:haftarah/matot'),
        Entry('admonition_2','Second haftarah of admonition',second_admonition,kind='seasonal',haftarah=TEXT+'bible:haftarah/masei'),
    ])
    return entries


def slots(entries, author, composer, service_name):
    """Torah aliyot, maftir and haftarah, each at its proper blessing boundary."""
    before=composer.source('siddur:chol/shacharit/torah/barekhu')+composer.source('siddur:chol/shacharit/torah/asher_bachar')
    after=transclude(TEXT+'prayer:birkhot_hatorah/asher_natan')
    result={'torah':'','maftir':'','haftarah':''}
    seasonal_entries=[e.predicate for e in entries if e.kind=='seasonal']
    seasonal=any_of(*seasonal_entries) if seasonal_entries else ''
    replacements=[e.predicate for e in entries if e.kind=='replace' and e.haftarah and not e.torah]
    haft_special=any_of(*([seasonal] if seasonal else []),SUPPLEMENT,*replacements)
    def aliyah(span,label):
        return head('עלייה '+str(label),'Aliyah '+str(label))+before+transclude(span.start.range_urn(span.end))+after
    for e in entries:
        if e.service!=service_name:continue
        pred=e.predicate
        if e.kind=='weekly':
            main=e.torah
            ordinary=''.join(aliyah(s,i) for i,s in enumerate(main,1))
            if len(main)==7:
                from dataclasses import replace
                # The first five aliyot are identical in both arrangements.
                # Share them, then select separate sixth/seventh or one combined
                # sixth, before the extra scroll. This also makes undated output
                # show the common text once with labeled alternatives.
                common=''.join(aliyah(s,i) for i,s in enumerate(main[:5],1))
                separate=''.join(aliyah(s,i) for i,s in enumerate(main[5:],6))
                combined=aliyah(replace(main[5],end=main[6].end),6)
                torah=common+author.gate(none_of(THIRD_SCROLL),separate,'With fewer than three Torah scrolls, read the sixth and seventh aliyot separately.')+author.gate(THIRD_SCROLL,combined,'With three Torah scrolls, combine the usual sixth and seventh as the sixth aliyah. The supplemental reading follows.')
            else:torah=ordinary
            m=author.gate(none_of(SUPPLEMENT),''.join(aliyah(s,'מפטיר / Maftir') for s in e.maftir))
            h=author.gate(none_of(haft_special),transclude(e.haftarah))
        else:
            torah=''.join(aliyah(s,s.label) for s in e.torah)
            m=''.join(aliyah(s,'מפטיר / Maftir') for s in e.maftir)
            h=transclude(e.haftarah) if e.haftarah else ''
            if e.kind=='supplement' and h and seasonal:h=author.gate(none_of(seasonal),h)
        if torah:result['torah']+=author.gate(pred,head(e.hebrew_title or e.title,e.title)+torah,e.title)
        if m:result['maftir']+=author.gate(pred,m,e.title)
        if h:result['haftarah']+=author.gate(pred,h,e.title)
    return result
