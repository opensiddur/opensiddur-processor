"""End of weekday Shacharit and the psalms for days and occasions.

Occasion conditions belong to the service wrappers. Scripture files are reusable;
repeated verses retain source spans rather than duplicate canonical correspondences.
"""
import re
from html import escape

from .common import PRAYER, SIDDUR, PROJECT_EN, PROJECT_HE, QUORUM, AGG, cond, endcond, feature, pb
from .conclusion_data import PASSAGES
from .milestones import Correspondences
from .tachanun_conditions import date, holiday, DIASPORA

BIBLE = 'urn:x-opensiddur:text:bible:'
ROOT = SIDDUR + 'chol/shacharit/conclusion'
PSALMS = SIDDUR + 'chol/shacharit/psalms'
SHIR_SHEL_YOM = SIDDUR + 'chol/shacharit/shir_shel_yom'
SIGIL = '1949 chol/shacharit/conclusion'
PSALMS_SIGIL = '1949 chol/shacharit/psalms'
MINYAN = feature(QUORUM, 'minyan')
PSALM20_RUBRIC = ('The following psalm is omitted on Rosh Ḥodesh, Ḥanukkah, Ḥol ha-Mo‘ed, '
    'the 14th and 15th of Adar and Adar Sheni, the 9th of Av, Erev Pesaḥ and Erev Yom Kippur.')
PSALM20_OCCASION = ('<j:none>' + holiday('rosh-hodesh', 2) + holiday('hanukkah', 8)
    + feature(AGG, 'chol-hamoed') + date(12, 14, 15) + date(13, 14, 15)
    + date(5, 9) + date(1, 14) + date(7, 9) + '</j:none>')
SEASON_RUBRIC = 'The following is recited daily from Rosh Ḥodesh Elul until Simḥath Torah.'
# Confirmed reading: through 21 Tishrei in Israel and 22 in the Diaspora.
ELUL_SEASON = ('<j:any>' + date(5, 30) + date(6, 1, 29) + date(7, 1, 21)
    + '<j:all>' + date(7, 22) + DIASPORA + '</j:all></j:any>')
MOURNING_RUBRIC = 'The following is recited in the house of a mourner during the week of mourning.'
MOURNING = feature('opensiddur:override', 'house-of-mourning')
DAYS = (
    ('sunday', 'Sunday', 'רִאשׁוֹן', 'first', 24, 139),
    ('monday', 'Monday', 'שֵׁנִי', 'second', 48, 139),
    ('tuesday', 'Tuesday', 'שְׁלִישִׁי', 'third', 82, 141),
    ('wednesday', 'Wednesday', 'רְבִיעִי', 'fourth', 94, 143),
    ('thursday', 'Thursday', 'חֲמִישִׁי', 'fifth', 81, 145),
    ('friday', 'Friday', 'שִׁשִּׁי', 'sixth', 93, 147),
)
ANCHORS = {}
HE_NUMBERS = {20: 'כ', 24: 'כד', 27: 'כז', 48: 'מח', 49: 'מט', 81: 'פא', 82: 'פב', 93: 'צג', 94: 'צד'}
URNS = {key: (BIBLE + 'psalms/' + key[6:] if key.startswith('psalm_') and key != 'psalm_95_opening'
              else ROOT + '/' + key) for key in PASSAGES}
URNS['titqabbal'] = PRAYER + 'kaddish/titqabbal'
URNS['psalm_95_opening'] = PSALMS + '/wednesday/psalm_95_opening'


def instruction(text):
    return '<tei:note type="instruction" xml:lang="en">' + escape(text) + '</tei:note>'


def transclude(urn, inline=False):
    return f'<j:transclude type="{"inline" if inline else "external"}" target="{urn}"/>'


def text_xml(value, sigil):
    xml = escape(value)
    xml = re.sub(r'\{pb:(\d+)\}', lambda m: pb(int(m[1]), sigil=sigil), xml)
    return xml.replace('{i}', '<tei:hi rend="italic">').replace('{/i}', '</tei:hi>')


def rows_xml(rows, *, urn, lang, seen, sigil, anchors=None):
    """Keep paragraphing independent of reference boundaries and speaker rubrics."""
    anchors = {} if anchors is None else anchors
    parts = ['<tei:p>']
    marks = Correspondences()
    for name, source, he, en in rows:
        value = he if lang == 'he' else en
        if value.startswith('{p}'):
            parts.append(marks.close() + '</tei:p><tei:p>')
            value = value.removeprefix('{p}')
        if value.startswith('{reader}'):
            parts.append(marks.close() + instruction('Reader'))
            value = value.removeprefix('{reader}')
        xml = text_xml(value, sigil)
        targum = name.startswith('targum_')
        reference = BIBLE + source if source and not targum else urn + '/' + name
        if targum:
            xml = (f'<tei:seg xml:lang="arc" source="{BIBLE}{source}">{xml}</tei:seg>' if lang == 'he'
                   else f'<tei:hi rend="italic"><tei:seg source="{BIBLE}{source}">{xml}</tei:seg></tei:hi>')
        identifier = f' xml:id="ref_{name}"'
        if reference in seen:
            local = (PSALMS + '/' + urn.rsplit('/', 1)[-1] + '/' + name
                     if urn.startswith(BIBLE) else urn + '/' + name)
            parts.append(marks.start(local) + f'<tei:seg{identifier} source="{reference}">{xml}</tei:seg> ')
            anchors[urn, name] = local
        else:
            start = marks.start(reference)
            # Put the annotation ID on the opening marker, not the preceding terminator.
            pos = start.rfind('/>')
            parts.append(start[:pos] + identifier + start[pos:] + xml + ' ')
            seen.add(reference)
            anchors[urn, name] = reference
    parts.append(marks.close() + '</tei:p>')
    return ''.join(parts)


def prayers(lang, earlier):
    side = 0 if lang == 'he' else 1
    seen = set(re.findall(r'corresp="([^"]+)"', '\n'.join(p['body'] for p in earlier)))
    result = []
    for key, item in PASSAGES.items():
        urn = URNS[key]
        sigil = PSALMS_SIGIL if item['first'] >= 139 else SIGIL
        body = [f'<tei:div corresp="{urn}">']
        if key.startswith('psalm_') and key != 'psalm_95_opening':
            number = int(key[6:])
            title = 'תהלים ' + HE_NUMBERS[number] if lang == 'he' else f'Psalm {number}'
            # Wednesday's citation covers both psalms and is in the caller.
            if number != 94:
                body.append(f'<tei:head xml:lang="{lang}">{title}</tei:head>')
        else:
            title = {'uva_letziyyon': ('וּבָא לְצִיּוֹן', 'Uva Letzion'),
                     'aleinu': ('עָלֵֽינוּ', 'Alenu'),
                     'al_tira': ('אַל תִּירָא', 'Be not afraid'),
                     'titqabbal': ('תִּתְקַבֵּל', 'May the prayers be accepted'),
                     'psalm_95_opening': ('לְכוּ נְרַנְּנָה', 'Come, let us sing')}[key][side]
            if key == 'aleinu' and lang == 'en':
                body.append('<tei:head xml:lang="en">ALENU</tei:head>')
        body.append(rows_xml(item['rows'], urn=urn, lang=lang, seen=seen, sigil=sigil, anchors=ANCHORS))
        body.append('</tei:div>')
        result.append(dict(name='conclusion_' + key, title=title, urn=urn,
            first=item['first'] + side, last=item['last'] + side, body='\n'.join(body)))
    result.append(full_kaddish(lang))
    result.extend(shir_shel_yom_files(lang))
    return result


def kaddish(cid, *, full=False, page=None, sigil=SIGIL, note='Mourners’ Kaddish.'):
    parts = [cond(cid, fs=MINYAN, note=note)]
    if full:
        parts.append(transclude(PRAYER + 'kaddish/yitgaddal'))
        if page:
            parts.append(pb(page, sigil=sigil))
        parts.extend(transclude(PRAYER + 'kaddish/' + key) for key in ('yehe_shemeh', 'yitbarakh'))
        parts.append(transclude(URNS['titqabbal']))
        parts.extend(transclude(PRAYER + 'kaddish/yatom/' + key) for key in ('yehe_shelama', 'oseh_shalom'))
    else:
        parts.append(transclude(PRAYER + 'kaddish/yatom'))
    parts.append(endcond(cid))
    return '\n'.join(parts)


def unit_body(project):
    from .build_he import declaration
    side = 0 if project == PROJECT_HE else 1
    parts = [f'<tei:div corresp="{ROOT}">', declaration(), pb(127 + side, sigil=SIGIL),
        transclude(PRAYER + 'ashrei'), pb(131 + side, sigil=SIGIL),
        cond('psalm20', fs=PSALM20_OCCASION, note=PSALM20_RUBRIC),
        transclude(URNS['psalm_20']), endcond('psalm20'), transclude(URNS['uva_letziyyon']),
        instruction(f'Musaf for Rosh Ḥodesh, page {575 + side}; for Ḥol ha-Mo‘ed, page {609 + side}.'),
        kaddish('full_kaddish', full=True, page=135 + side, note='Reader:'),
        transclude(URNS['aleinu']), kaddish('kaddish_after_aleinu', note='MOURNERS’ KADDISH'),
        transclude(URNS['al_tira']), '<j:endDeclare target="#unit_service"/>', '</tei:div>']
    return '\n'.join(parts)


def shir_shel_yom_body(lang, days=DAYS):
    """The defined daily-psalm section selects its weekday occurrences."""
    side = 0 if lang == 'he' else 1
    title = 'שִׁיר שֶׁל יוֹם' if lang == 'he' else 'PSALM OF THE DAY'
    parts = [f'<tei:div corresp="{SHIR_SHEL_YOM}">', pb(139 + side, sigil=PSALMS_SIGIL),
        f'<tei:head xml:lang="{lang}">{title}</tei:head>',
        instruction('The following six psalms are recited on the respective days of the week.')]
    for day, (key, name, *_rest) in enumerate(days, 1):
        parts += [cond('day_' + key, note=f'On {name}s:',
            fs=feature('opensiddur:day-of-week', 'hebrew-day', f'<tei:numeric value="{day}"/>')),
            transclude(PSALMS + '/' + key), endcond('day_' + key)]
    return '\n'.join(parts + ['</tei:div>'])


def shir_shel_yom_files(lang):
    """One section file and one reusable occurrence file for each printed weekday."""
    side = 0 if lang == 'he' else 1
    result = []
    for key, name, he, en, number, first in DAYS:
        parts = [f'<tei:div corresp="{PSALMS}/{key}">']
        if first in (141, 143, 145, 147):
            parts.append(pb(first + side, sigil=PSALMS_SIGIL))
        intro = (f'הַיּוֹם יוֹם {he} בַּשַּׁבָּת, שֶׁבּוֹ הָיוּ הַלְוִיִּם אוֹמְרִים בְּבֵית הַמִּקְדָּשׁ:'
                 if lang == 'he' else f'This is the {en} day of the week, on which the Levites in the Temple used to recite:')
        parts += [f'<tei:div corresp="{PSALMS}/{key}/intro"><tei:p>{intro}</tei:p></tei:div>']
        if number == 94:
            citation = 'תהלים צד; צה, א–ג' if lang == 'he' else 'Psalms 94; 95:1–3'
            parts.append(f'<tei:div><tei:head xml:lang="{lang}">{citation}</tei:head></tei:div>')
        if number == 24:
            # This occurrence adds a Reader rubric absent from the Torah service.
            # Keep that edited presentation local, with biblical source references.
            from .torah_data import PASSAGES as TORAH_PASSAGES
            rows = list(TORAH_PASSAGES['psalm24']['rows'])
            row_name, source, he_text, en_text = rows[-1]
            rows[-1] = (row_name, source, '{reader}' + he_text, en_text)
            title = 'תהלים כד' if lang == 'he' else 'Psalm 24'
            urn = PSALMS + '/sunday/psalm_24'
            parts.append(f'<tei:div corresp="{urn}"><tei:head xml:lang="{lang}">{title}</tei:head>')
            parts.append(rows_xml(rows, urn=urn, lang=lang,
                                 seen={BIBLE + r[1] for r in rows}, sigil=PSALMS_SIGIL))
            parts.append('</tei:div>')
        else:
            parts.append(transclude(BIBLE + f'psalms/{number}'))
        if number == 94:
            parts.append(transclude(URNS['psalm_95_opening']))
        parts += [kaddish('kaddish_' + key, sigil=PSALMS_SIGIL), '</tei:div>']
        last = first + 2 if key in ('monday', 'wednesday') else first
        result.append(dict(name='shir_shel_yom_' + key,
            title='שיר ליום ' + he if lang == 'he' else 'Psalm for ' + name,
            urn=PSALMS + '/' + key, first=first + side, last=last + side,
            body='\n'.join(parts)))
    result.append(dict(name='chol_shacharit_shir_shel_yom',
        title='שִׁיר שֶׁל יוֹם' if lang == 'he' else 'Psalm of the day',
        urn=SHIR_SHEL_YOM, first=139 + side, last=147 + side,
        body=shir_shel_yom_body(lang)))
    return result


def psalms_body(project):
    from .build_he import declaration
    parts = [f'<tei:div corresp="{PSALMS}">', declaration(), transclude(SHIR_SHEL_YOM)]
    for key, fs, rubric in (('psalm_27', ELUL_SEASON, SEASON_RUBRIC), ('psalm_49', MOURNING, MOURNING_RUBRIC)):
        parts += [cond(key + '_occasion', fs=fs, note=rubric),
                  transclude(URNS[key]), kaddish('kaddish_' + key, sigil=PSALMS_SIGIL),
                  endcond(key + '_occasion')]
    parts += ['<j:endDeclare target="#unit_service"/>', '</tei:div>']
    return '\n'.join(parts)


def full_kaddish(lang):
    """Reusable complete prayer, bound to this edition rather than caller priorities."""
    project = PROJECT_HE if lang == 'he' else PROJECT_EN
    urn = PRAYER+'kaddish/shalem'
    parts = ('yitgaddal', 'yehe_shemeh', 'yitbarakh', 'titqabbal',
             'yatom/yehe_shelama', 'yatom/oseh_shalom')
    body = f'<tei:div corresp="{urn}">' + instruction('Reader:')
    body += ''.join(transclude(PRAYER+'kaddish/'+part+'@'+project) for part in parts)
    body += '</tei:div>'
    return dict(name='kaddish_shalem', title='קדיש שלם' if lang == 'he' else 'Full Kaddish',
                urn=urn, first=135 if lang == 'he' else 136,
                last=135 if lang == 'he' else 136, body=body)
