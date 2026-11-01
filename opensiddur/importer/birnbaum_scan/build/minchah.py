"""Weekday Minchah: occurrence wrappers around shared prayers and distinct readings."""
from html import escape

from .common import (PRAYER, SIDDUR, AGG, RECITATION, QUORUM, PROJECT_HE,
                     cond, endcond, feature, pb)
from .conclusion import transclude, instruction, URNS as CONCLUSION
from .tachanun import URNS as TACHANUN, NEFILAH, CLOSING
from .tachanun_conditions import date, holiday, TISHREI
from .avinu_malkenu import TEN_DAYS
from .minchah_data import (NACHEM_HE, NACHEM_EN, NACHEM_VERSE_HE, NACHEM_VERSE_EN,
                          NACHEM_SEAL_HE, NACHEM_SEAL_EN, SHALOM_RAV,
                          TACHANUN_RUBRIC, TORAH_RUBRIC)
from .milestones import marked
from .shared_passages import split_paragraph, detach_division

ROOT = SIDDUR + 'chol/minchah'
BIBLE = 'urn:x-opensiddur:text:bible:'
SIGIL = '1949 chol/minchah'
FAST = feature(AGG, 'minor-fast')
TISHA = holiday('tisha-bav')
# Minchah of Tish'ah b'Av is a fast-day Minchah, which minor-fast does not cover: Anenu, the
# priestly blessing and Sim Shalom are said at it. Avinu Malkenu is not.
FAST_DAY = '<j:any>' + FAST + TISHA + '</j:any>'
REPETITION = feature(RECITATION, 'repetition')
MINYAN = feature(QUORUM, 'minyan')
NACHEM = PRAYER + 'amidah/nachem_hashem_eloheinu'
SHALOM = PRAYER + 'amidah/shalom_rav_al'


def conditional(cid, note, fs, content, *, negate=False):
    return '\n'.join([cond('minchah_' + cid, note=note, fs=fs, negate=negate),
                      content, endcond('minchah_' + cid)])


def shared(lang, prayers):
    """Expose fragments used by the Minchah variants, retaining Shacharit wording."""
    result = [dict(p) for p in prayers]
    by_name = {p['name']: p for p in result}
    for name, urn, boundary in (
        ('amidah_yerushalayim', PRAYER + 'amidah/yerushalayim',
         'בָּרוּךְ אַתָּה' if lang == 'he' else 'Blessed art thou'),
        ('amidah_tefillah', PRAYER + 'amidah/tefillah',
         'כִּי אַתָּה שׁוֹמֵֽעַ' if lang == 'he' else 'for thou hearest in mercy'),
        ('amidah_geullah', PRAYER + 'amidah/aneinu',
         'בָּרוּךְ אַתָּה' if lang == 'he' else 'Blessed art thou'),
    ):
        by_name[name]['body'] = split_paragraph(by_name[name]['body'], urn, boundary)
    for parent, urn, name in (
        ('amidah_geullah', PRAYER+'amidah/aneinu', 'amidah_aneinu'),
        ('amidah_shalom', PRAYER+'amidah/shalom/hamevarekh', 'amidah_shalom_hamevarekh'),
        ('amidah_shalom', PRAYER+'amidah/shalom/besefer_chayyim', 'amidah_shalom_besefer_chayyim'),
    ):
        detached = detach_division(by_name[parent], urn, name)
        detached['body'] = detached['body'].replace('<tei:p>(', '<tei:p>').replace(')</tei:p>', '</tei:p>')
        result.append(detached)
    # The one differing Avinu petition is selected inside the shared prayer;
    # the condition for saying Avinu Malkenu stays in each service caller.
    import re
    p = by_name['avinu_malkenu']
    pattern = r'<tei:div><tei:p><tei:milestone unit="petition" corresp="' + re.escape(PRAYER+'avinu_malkenu/tehe') + r'"/>.*?</tei:p></tei:div>'
    old = re.search(pattern, p['body'], re.S)[0]
    service = feature('opensiddur:service-time', 'minha')
    replacement = (conditional('avinu_hour', 'At other services:', service, old, negate=True)
                   + conditional('avinu_year', 'At Minchah:', service,
                                 transclude(ROOT+'/avinu_malkenu/tehe')))
    p['body'] = p['body'].replace(old, replacement)
    from .minchah_printings import apply
    return apply(lang, result)


def prayers(lang):
    side = int(lang == 'en')
    result = []
    def add(name, urn, title, page, content):
        result.append(dict(name=name, urn=urn, title=title, first=page+side,
            last=page+side, body=f'<tei:div corresp="{urn}"><tei:p>{content}</tei:p></tei:div>'))
    add('minchah_ki_shem', BIBLE+'deuteronomy/32/3', 'כי שם יי אקרא' if not side else 'When I proclaim', 159,
        marked(ROOT+'/ki_shem', 'כִּי שֵׁם יְיָ אֶקְרָא, הָבוּ גֹֽדֶל לֵאלֹהֵֽינוּ.' if not side else
               'When I proclaim the name of the Lord, give glory to our God!'))
    text, verse, seal = ((NACHEM_HE, NACHEM_VERSE_HE, NACHEM_SEAL_HE) if not side else
                         (NACHEM_EN, NACHEM_VERSE_EN, NACHEM_SEAL_EN))
    add('amidah_nachem', NACHEM, 'נַחֵם' if not side else 'Comfort the mourners of Zion', 167,
        marked(NACHEM+'/opening', escape(text)) + marked(NACHEM+'/quotation',
        f'<tei:seg source="{BIBLE}zechariah/2/9">{escape(verse)}</tei:seg>') + ' ' + marked(NACHEM+'/seal', escape(seal)))
    add('amidah_shalom_rav', SHALOM, 'שָׁלוֹם רָב' if not side else 'Abundant peace', 173, escape(SHALOM_RAV[lang]))
    # The Hebrew afternoon printing reads “this year”; the morning and English
    # afternoon readings say “this hour”. Preserve the edition's actual variant.
    add('minchah_avinu_tehe', ROOT+'/avinu_malkenu/tehe', 'אבינו מלכנו תהא השנה' if not side else 'Our Father, our King, may this hour', 179,
        'אָבִֽינוּ מַלְכֵּֽנוּ, תְּהֵא הַשָּׁנָה הַזֹּאת שְׁנַת רַחֲמִים וְעֵת רָצוֹן מִלְּפָנֶֽיךָ.' if not side else
        'Our Father, our King, may this hour be an hour of mercy and a time of grace with thee.')
    return result


def head(lang, he, en):
    return f'<tei:head xml:lang="{lang}">{he if lang == "he" else en}</tei:head>'


def passage(urn):
    return transclude(PRAYER + 'amidah/' + urn)


def amidah(lang, by_name):
    from .build_he import ORDER
    parts = [instruction('The Shemoneh Esreh is recited in silent devotion while standing, facing east.'),
             instruction('The Reader repeats the Shemoneh Esreh aloud when a minyan holds service.'),
             transclude(BIBLE+'deuteronomy/32/3')]
    for name in ORDER:
        if name == 'amidah_geullah':
            parts += [passage('geullah/reeh_na'), conditional('reader_aneinu', 'On fast days the Reader adds here:',
                '<j:all>'+FAST_DAY+REPETITION+MINYAN+'</j:all>', passage('aneinu'))]
        elif name == 'amidah_yerushalayim':
            parts += [passage('yerushalayim/opening'),
                conditional('jerusalem_seal', 'Except on Tish‘ah b’Av:', TISHA, passage('yerushalayim/seal'), negate=True),
                conditional('nachem', 'On Tish‘ah b’Av say:', TISHA, transclude(NACHEM))]
        elif name == 'amidah_tefillah':
            # Anenu is inserted before the common conclusion, which prints once.
            parts += [passage('tefillah/opening'),
                conditional('silent_aneinu', 'On fast days, the Congregation recites here:',
                    '<j:all>'+FAST_DAY+feature(RECITATION, 'repetition', '<tei:binary value="false"/>')+'</j:all>',
                    passage('aneinu/opening')), passage('tefillah/seal')]
        elif name == 'amidah_birkat_kohanim':
            # The surrounding rubric is English even in the Hebrew project.
            # Mark the Hebrew title explicitly so its words render right to left.
            peace_title = ('<tei:foreign xml:lang="he">שים שלום</tei:foreign>'
                           if lang == 'he' else '“O grant peace…”')
            parts += [('<tei:note type="instruction" xml:lang="en">'
                'On fast days, the Reader recites here the priestly blessing '
                f'(page {93+int(lang=="en")}) and instead of the following paragraph, '
                + peace_title + f' is said (page {95+int(lang=="en")}).</tei:note>'),
                conditional('priestly_blessing', 'On fast days, in the Reader’s repetition:',
                    '<j:all>'+FAST_DAY+REPETITION+MINYAN+'</j:all>', passage('birkat_kohanim'))]
        elif name == 'amidah_shalom':
            parts += [conditional('sim_shalom', 'On fast days:', FAST_DAY, passage('shalom/sim_shalom')),
                conditional('shalom_rav', 'Except on fast days:', FAST_DAY, transclude(SHALOM), negate=True),
                conditional('peace_seal', 'Except during the Ten Days of Repentance:', TEN_DAYS, passage('shalom/hamevarekh'), negate=True),
                conditional('peace_ten_days', 'Between Rosh Hashanah and Yom Kippur say:', TEN_DAYS, passage('shalom/besefer_chayyim'))]
        else:
            if name == 'amidah_qedushah':
                parts.append(cond('weekday_qedushah', fs='<j:all>'+REPETITION+MINYAN+'</j:all>')
                    +'<tei:div>'+head(lang, 'קְדֻשָּׁה', 'KEDUSHAH')+transclude(by_name[name]['urn'])+'</tei:div>'+endcond('weekday_qedushah'))
            elif name == 'amidah_qedushat_hashem':
                parts.append(cond('weekday_silent_qedushat_hashem', fs='<j:none><j:all>'+REPETITION+MINYAN+'</j:all></j:none>')
                    +transclude(by_name[name]['urn'])+endcond('weekday_silent_qedushat_hashem'))
            elif name == 'amidah_elohai_netzor':
                parts.append(cond('weekday_silent_meditation', fs='<j:none><j:all>'+REPETITION+MINYAN+'</j:all></j:none>')+transclude(by_name[name]['urn'])+endcond('weekday_silent_meditation'))
            elif name == 'amidah_yehi_ratzon':
                parts.append(transclude(by_name[name]['urn']))
            else:
                parts.append(transclude(by_name[name]['urn']))
    return '\n'.join(parts)


def avinu(lang):
    return conditional('avinu', 'Between Rosh Hashanah and Yom Kippur and on fast days:',
                       '<j:any>'+TEN_DAYS+FAST+'</j:any>', transclude(PRAYER+'avinu_malkenu'))


def tachanun_occasion():
    # Erev Rosh Hodesh is day 29 in a short month, day 30 in a long
    # month (already Rosh Hodesh), or day 29 before a two-day Rosh Hodesh.
    # Therefore every 29th is omitted, as well as Rosh Hodesh itself.
    omissions = (feature('opensiddur:day-of-week', 'hebrew-day', '<tei:numeric value="6" max="7"/>')
        + feature('opensiddur:hebrew-date', 'day', '<tei:numeric value="29"/>')
        + holiday('rosh-hodesh',2) + date(1,1,30) + date(2,17,18) + date(3,1,8)
        + date(5,8,9) + date(5,14,15) + TISHREI + date(9,24,30)
        + holiday('hanukkah',8) + date(11,14,15) + date(12,13,15) + date(13,13,15)
        + ''.join(feature('opensiddur:override', key) for key in ('omit-tahanun','house-of-mourning','brit-milah')))
    return '<j:none>'+omissions+'</j:none>'


def kaddish(parts, cid, *, full=False, mourner=False, lang='he'):
    text = []
    def occurrence(key, target):
        return ('<tei:div>'+marked(ROOT+'/conclusion/kaddish/'+key,
                                  transclude(target), unit='kaddish-part')+'</tei:div>')
    if mourner:
        text += [transclude(PRAYER+'kaddish/yitgaddal'),
                 occurrence('response', PRAYER+'kaddish/yehe_shemeh'),
                 pb(187+int(lang=='en'),sigil=SIGIL+'/conclusion'),
                 occurrence('praise', PRAYER+'kaddish/yitbarakh')]
    else:
        text += [instruction('Reader:')]
        text += [transclude(PRAYER+'kaddish/'+p) for p in ('yitgaddal','yehe_shemeh','yitbarakh')]
    if full:
        text.append(transclude(PRAYER+'kaddish/titqabbal'))
    if full or mourner:
        text.append(transclude(PRAYER+'kaddish/yatom/yehe_shelama'))
        text.append(occurrence('peace', PRAYER+'kaddish/yatom/oseh_shalom') if mourner
                    else transclude(PRAYER+'kaddish/yatom/oseh_shalom'))
    parts.append(conditional(cid, 'When a minyan holds service:', MINYAN, '\n'.join(text)))


def units(project, by_name):
    from .build_he import declaration
    from .shacharit_end import editorial_head
    lang = 'he' if project==PROJECT_HE else 'en'
    side = int(lang=='en')
    result = []
    def unit(key, he, en, first, last, content, *, printed=False):
        urn = ROOT+('/'+key if key else '')
        title = head(lang,he,en) if printed else editorial_head(lang,he,en)
        body = '\n'.join([f'<tei:div corresp="{urn}">',title,
            declaration('minha'),pb(first+side,sigil=SIGIL+('/'+key if key else '')),
            content,'<j:endDeclare target="#unit_service"/>','</tei:div>'])
        result.append(dict(name='chol_minchah'+('_'+key if key else ''), urn=urn,
            title_he=he,title_en=en,pages=(first+side,last+side),body=body))
    opening = [transclude(PRAYER+'ashrei')]
    kaddish(opening,'half_kaddish')
    # The scan supplies a direction, not the Torah/Haftarah text here.
    opening.append(conditional('torah_rubric', '', FAST, instruction(TORAH_RUBRIC)))
    unit('opening','אַשְׁרֵי וַחֲצִי קַדִּישׁ','Ashrei and Half Kaddish',157,159,'\n'.join(opening))
    unit('amidah','תפילת העמידה','SHEMONEH ESREH',159,175,amidah(lang,by_name))
    unit('avinu_malkenu','אָבִֽינוּ מַלְכֵּֽנוּ','Avinu Malkenu',175,179,avinu(lang))
    text = []
    for key in NEFILAH+CLOSING:
        if key=='mitratzeh':
            text.append(pb(183+side,sigil=SIGIL+'/tachanun'))
        text.append(transclude(TACHANUN[key]))
    unit('tachanun','תַּחֲנוּן','TAḤANUN',181,183,
         conditional('tachanun',TACHANUN_RUBRIC,tachanun_occasion(),'\n'.join(text)),printed=True)
    text = []
    kaddish(text,'full_kaddish',full=True)
    unit('kaddish','קדיש תתקבל','Full Kaddish',183,183,'\n'.join(text))
    text = [transclude(CONCLUSION['aleinu']),f'<tei:div corresp="{ROOT}/conclusion/kaddish">',head(lang,'קדיש יתום','MOURNERS’ KADDISH')]
    kaddish(text,'mourners_kaddish',mourner=True,lang=lang)
    text.append('</tei:div>')
    text.append(transclude(CONCLUSION['al_tira']))
    unit('conclusion','עלינו וסיום התפילה','Alenu and conclusion',185,187,'\n'.join(text))
    content = '\n'.join(transclude(u['urn']) for u in result)
    unit('','תְּפִלַּת מִנְחָה','AFTERNOON SERVICE',157,187,content,printed=True)
    return tuple(result)
